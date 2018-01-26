# -*- coding: utf-8 -*-
"""
peregrine.resources.submission.graphql.transaction
----------------------------------

GraphQL Models for TransactionLogs
"""

from collections import defaultdict

import json
import flask
import graphene
import sqlalchemy as sa
from sqlalchemy.orm import subqueryload

from cdispyutils.log import get_logger
from datamodelutils import models

logger = get_logger(__name__)

from ..constants import (
    TX_LOG_STATE_SUCCEEDED,
)

from .util import (
    apply_arg_limit,
    apply_arg_offset,
    filtered_column_dict,
    get_fields,
    apply_load_only,
)

from peregrine.resources.submission.constants import (
    case_cache_enabled,
)

def filter_to_cls_fields(cls, doc):
    fields = {f.attname for f in cls._meta.fields}
    doc = {
        key: val
        for key, val in doc.iteritems()
        if key in fields
    }
    dropped = set(doc.keys()) - fields
    if dropped:
        logger.warn("Dropping keys %s", dropped)
    return doc


def instantiate_safely(cls, doc):
    doc = filter_to_cls_fields(cls, doc)
    return cls(**doc)


class GenericEntity(graphene.ObjectType):
    """Skeleton properties to reference generic entities"""

    id = graphene.String()
    type = graphene.String()

    def resolve_type(self, info, **args):
        return lambda: self.type


class TransactionResponseError(graphene.ObjectType):
    keys = graphene.List(graphene.String)
    dependents = graphene.List(GenericEntity, description='List of entities that depend on this entity such that the transaction failed.')
    message = graphene.String()
    type = graphene.String()

    def resolve_type(self, info, **args):
        return self.type

    def resolve_dependents(self, info, **args):
        try:
            return [
                GenericEntity(**dependent)
                for dependent in self.dependents
            ]
        except AttributeError:
            # graphene does unsightly things, if there are no
            # dependents passed to init, then it looks for dependents
            # on the root object, which for us is None
            return []


class TransactionSnapshot(graphene.ObjectType):
    id = graphene.ID()
    transaction_id = graphene.Int()
    action = graphene.String()
    old_props = graphene.String()
    new_props = graphene.String()


class TransactionResponseEntityRelatedCases(graphene.ObjectType):
    id = graphene.String()
    submitter_id = graphene.String()


class TransactionResponseEntity(graphene.ObjectType):
    valid = graphene.Boolean()
    action = graphene.String()
    type = graphene.String()
    id = graphene.String()
    unique_keys = graphene.String()
    related_cases = graphene.List(TransactionResponseEntityRelatedCases)
    errors = graphene.List(TransactionResponseError)
    warnings = graphene.String()

    def resolve_errors(self, info, **args):
        return [
            TransactionResponseError(**error)
            for error in self.errors
        ]

    def resolve_unique_keys(self, info, **args):
        """Return a string dump of the unique keys. This is a string because
        we don't have a polymorphic GraphQL representation of why
        might be defined as a unique key and it is therefore easier to
        just return it as a string and have the client parse it.

        ..note:
            The AttributeError must be handled here now because at one
            point deletion transactions did not have `unique_keys`.
            Because of the silly way that graphene tries to magically
            proxy attributes to root objects wrapped in `self` here,
            we end up calling `None.unique_keys` if `unique_keys` was
            not passed to TransactionResponseEntity.__init__()

        """

        try:
            return json.dumps(self.unique_keys)
        except AttributeError as exception:
            logger.exception(exception)
            return []

    def resolve_type(self, info, **args):
        return lambda: self.type

    def resolve_related_cases(self, info, **args):
        if case_cache_enabled():
            return [
                instantiate_safely(TransactionResponseEntityRelatedCases, case)
                for case in self.related_cases
            ]
        else:
            return []


class TransactionResponse(graphene.ObjectType):
    transaction_id = graphene.ID()
    success = graphene.Boolean()
    entity_error_count = graphene.Int()
    transactional_error_count = graphene.Int()
    code = graphene.Int()
    message = graphene.String()
    transactional_errors = graphene.Int()
    created_entity_count = graphene.Int()
    updated_entity_count = graphene.Int()
    released_entity_count = graphene.Int()
    cases_related_to_updated_entities_count = graphene.Int()
    cases_related_to_created_entities_count = graphene.Int()
    entities = graphene.List(TransactionResponseEntity)

    @classmethod
    def resolve_entities(cls, response, **args):
        try:
            return [
                instantiate_safely(TransactionResponseEntity, entity)
                for entity in response.entities
            ]
        except Exception as exc:
            logger.exception(exc)

    @classmethod
    def resolve_response_json(cls, response, **args):
        return json.dumps(response.response_json)


class TransactionDocument(graphene.ObjectType):
    id = graphene.ID()
    transaction_id = graphene.ID()
    doc_format = graphene.String()
    doc = graphene.String()
    doc_size = graphene.Int()
    name = graphene.String()
    response_json = graphene.String()
    response = graphene.Field(TransactionResponse)

    @classmethod
    def resolve_doc_size(cls, document, *args, **kwargs):
        return len(document.doc)

    @classmethod
    def resolve_response(cls, document, *arg, **kwargss):
        try:
            response_json = json.loads(document.response_json)
            return instantiate_safely(TransactionResponse, response_json)
        except Exception as exc:
            logger.exception(exc)

    @classmethod
    def resolve_response_json(cls, document, *args, **kwargs):
        try:
            return document.response_json
        except Exception as exc:
            logger.exception(exc)

class TransactionLog(graphene.ObjectType):
    id = graphene.ID()
    is_dry_run = graphene.Boolean()
    closed = graphene.Boolean()
    committed_by = graphene.ID()
    state = graphene.String()
    type = graphene.String()
    quick_search = graphene.ID()
    submitter = graphene.String()
    role = graphene.String()
    program = graphene.String()
    project = graphene.String()
    created_datetime = graphene.String()
    canonical_json = graphene.String()
    project_id = graphene.String()
    snapshots = graphene.List(TransactionSnapshot)
    documents = graphene.List(TransactionDocument)
    related_cases = graphene.List(TransactionResponseEntityRelatedCases)

    # These fields depend on these columns being loaded
    fields_depend_on_columns = {
        "type": {"role"},
        "project_id": {"project", "program"},
    }

    TYPE_MAP = {
        "update": "upload",
        "create": "upload",
        # f(x) -> x for all others
    }

    def resolve_project_id(self, info, **args):
        return '{}-{}'.format(self.program, self.project)

    def resolve_documents(self, info, **args):
        return [TransactionDocument(**dict(
            filtered_column_dict(r, info),
            **{'response_json': json.dumps(r.response_json)}
        )) for r in self.documents]

    def resolve_snapshots(self, info, **args):
        return [
            TransactionSnapshot(**filtered_column_dict(r, info))
            for r in self.snapshots
        ]

    def resolve_type(self, info, **args):
        """Classify the type of transaction by the transaction.roll"""
        return self.TYPE_MAP.get(self.role.lower(), self.role.lower())

    def resolve_related_cases(self, info, **args):
	if not case_cache_enabled():
            return []
        related_cases = {}
        for document in self.documents:
            entities = document.response_json.get('entities', [])
            for entity in entities:
                for related_case in entity.get('related_cases', []):
                    related_cases['id'] = {
                        'id': related_case.get('id', None),
                        'submitter_id': related_case.get('submitter_id', None),
                    }

        return [
            instantiate_safely(TransactionResponseEntityRelatedCases, case)
            for case in related_cases.values()
        ]


def get_transaction_log_args():
    return dict(
        id=graphene.ID(),
        type=graphene.String(),
        quick_search=graphene.ID(),
        project_id=graphene.List(graphene.String),
        project=graphene.String(),
        program=graphene.String(),
        order_by_asc=graphene.String(),
        order_by_desc=graphene.String(),
        related_cases=graphene.List(graphene.String),
        first=graphene.Int(),
        last=graphene.Int(),
        offset=graphene.Int(),
        entities=graphene.List(graphene.String),
        is_dry_run=graphene.Boolean(),
        closed=graphene.Boolean(),
        committable=graphene.Boolean(description='(committable: true) means (is_dry_run: true) AND (closed: false) AND (state: "SUCCEEDED") AND (committed_by is None).  Note: committed_by is None cannot be represented in GraphQL, hence this argument.'),
        state=graphene.String(),
        committed_by=graphene.ID(),
    )


def resolve_transaction_log_query(self, info, **args):
    sortable = ['id', 'submitter', 'role', 'program', 'project',
                'created_datetime', 'canonical_json', 'project_id']

    q = flask.current_app.db.nodes(models.submission.TransactionLog).filter(
        models.submission.TransactionLog.project_id.in_(flask.g.read_access_projects)
    )

    if 'quick_search' in args:
        try:
            id_ = int(args['quick_search'])
        except ValueError:
            # Because id is an int, if we couldn't parse it to an int,
            # filter should return 0 results.
            return q.filter(sa.sql.false())
        else:
            q = q.filter(models.submission.TransactionLog.id == id_)

    if 'id' in args:
        q = q.filter(models.submission.TransactionLog.id == args['id'])
    if 'is_dry_run' in args:
        q = q.filter(models.submission.TransactionLog.is_dry_run == args['is_dry_run'])
    if 'state' in args:
        q = q.filter(models.submission.TransactionLog.state == args['state'])
    if 'committed_by' in args:
        q = q.filter(models.submission.TransactionLog.committed_by == args['committed_by'])
    if 'closed' in args:
        q = q.filter(models.submission.TransactionLog.closed == args['closed'])
    if 'committable' in args:
        if args['committable']:
            # is committable
            q = q.filter(sa.and_(
                models.submission.TransactionLog.is_dry_run == True,
                models.submission.TransactionLog.state == TX_LOG_STATE_SUCCEEDED,
                models.submission.TransactionLog.closed == False,
                models.submission.TransactionLog.committed_by == None))
        else:
            # is not committable
            q = q.filter(sa.or_(
                models.submission.TransactionLog.is_dry_run == False,
                models.submission.TransactionLog.state != TX_LOG_STATE_SUCCEEDED,
                models.submission.TransactionLog.closed == True,
                models.submission.TransactionLog.committed_by != None))
    if 'project_id' in args:
        q = q.filter(models.submission.TransactionLog.project_id.in_(args['project_id']))
    if 'project' in args:
        q = q.filter(models.submission.TransactionLog.project == args['project'])
    if 'program' in args:
        q = q.filter(models.submission.TransactionLog.program == args['program'])
    if 'entities' in args:
        q = q.join(models.submission.TransactionLog.entities)\
             .filter(models.submission.TransactionSnapshot.id.in_(args['entities']))\
             .reset_joinpoint()
    if 'related_cases' in args:
        q = q.join(models.submission.TransactionLog.documents)\
             .filter(sa.or_(models.submission.TransactionDocument.response_json.contains({
                 'entities': [{'related_cases': [
                     {'id': r_id}]}]}) for r_id in args['related_cases']))\
             .reset_joinpoint()
    if 'type' in args:
        inv_map = defaultdict(list)
        for k, v in TransactionLog.TYPE_MAP.iteritems():
            inv_map[v].append(k)
        q = q.filter(models.submission.TransactionLog.role.in_(
            inv_map.get(args['type'], [args['type']])))

    if args.get('order_by_asc') in sortable:
        q = q.order_by(getattr(q.entity(), args['order_by_asc']))
    if args.get('order_by_desc') in sortable:
        q = q.order_by(getattr(q.entity(), args['order_by_desc']).desc())

    q = apply_arg_limit(q, args, info)

    if 'last' in args:
        q = q.limit(None)
        q = q.order_by(q.entity().id.desc()).limit(args['last'])

    q = apply_arg_offset(q, args, info)
    return q

def apply_transaction_log_eagerload(q, info):
    """Optimize the transaction_log query to prevent an N+1 query
       problem by eagerly loading relationships from the database
    """

    fields = get_fields(info)

    if 'documents' in fields:
        q = q.options(subqueryload(models.submission.TransactionLog.documents))

    if 'snapshots' in fields:
        q = q.options(subqueryload(models.submission.TransactionLog.entities))

    return q

def resolve_transaction_log(self, info, **args):
    fields_depend_on_columns = TransactionLog.fields_depend_on_columns
    requested_fields = get_fields(info)

    q = resolve_transaction_log_query(self, info, **args)
    q = apply_transaction_log_eagerload(q, info)
    q = apply_load_only(q, info, fields_depend_on_columns)

    results = []

    for tx_log in q.all():
        fields = filtered_column_dict(tx_log, info, fields_depend_on_columns)
        if 'documents' in requested_fields:
            fields['documents'] = tx_log.documents
        if 'snapshots' in requested_fields:
            fields['snapshots'] = tx_log.entities
        results.append(TransactionLog(**fields))
    return results


def resolve_transaction_log_count(self, info, **args):
    q = resolve_transaction_log_query(self, info, **args)
    q = q.limit(args.get('first', None))
    return q.count()


TransactionLogField = graphene.List(
    TransactionLog,
    args=get_transaction_log_args(),
)

TransactionLogCountField = graphene.Field(
    graphene.Int,
    args=get_transaction_log_args(),
)
