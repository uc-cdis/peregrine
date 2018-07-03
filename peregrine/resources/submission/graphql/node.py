# -*- coding: utf-8 -*-
"""
peregrine.resources.submission.graphql.node
----------------------------------

Implements GraphQL queries for each gdcdatamodel.model node type
using the Graphene GraphQL library
"""


from flask import current_app as capp
import dateutil
import graphene
import logging
import psqlgraph
import sqlalchemy as sa

from datamodelutils import models as md  # noqa
from peregrine import dictionary
from .util import (
    apply_arg_limit,
    apply_arg_offset,
    get_authorized_query,
    get_fields as util_get_fields,
    filtered_column_dict
)

from . import transaction
from .traversal import (
    subq_paths,
)

from peregrine.resources.submission.constants import (
    case_cache_enabled,
)

logging.root.setLevel(level=logging.ERROR)

COUNT_NAME = '_{}_count'
__gql_object_classes = {}


def get_link_attr(cls, link):
    """getattr with added constraint"""

    if link not in cls._pg_edges.keys():
        raise RuntimeError("Invalid link name '{}'".format(link))

    return getattr(cls, link)


# ======================================================================
# Filters


def filter_project_project_id(q, value, info):
    """This is a special case; because project does not have a stored
    ``project_id``, we have to parse the id walk to program check the
    program.name

    """

    project_ids = value
    if not isinstance(project_ids, (list, tuple)):
        project_ids = [project_ids]

    subqs = []
    for project_id in project_ids:
        split = project_id.split('-', 1)
        if len(split) == 2:
            program_name, project_code = split
            subq = q.props(code=project_code)\
                    .path('programs')\
                    .props(name=program_name)
            subqs.append(subq)
    if not subqs:
        q = q.filter(sa.sql.false())
    else:
        q = capp.db.nodes(q.entity()).select_entity_from(sa.union_all(*[
            sq.subquery().select() for sq in subqs
        ]))

    return q


def with_path_to(q, value, info, union=False, name='with_path_to'):
    """This will traverse any (any meaning any paths specified in the path
    generation heuristic which prunes some redundant/wandering paths)
    from the source entity to the given target type where it will
    apply a given query.

    This filter is a logical conjunction (*AND*) over subfilters.

    """

    if not isinstance(value, list):
        value = [value]

    union_qs = []

    for entry in value:
        entry = dict(entry)

        # Check target type
        dst_type = entry.pop('type', None)
        if not dst_type:
            raise RuntimeError(
                'Please specify a {{type: <type>}} in the {} filter.'
                .format(name))

        # Prevent traversal to Node interface
        if q.entity() is Node:
            raise RuntimeError(
                '{} filter cannot be used with "node" interface'
                .format(name))

        # Define end of traversal filter
        def end_of_traversal_filter(q, entry=entry):
            if not entry:
                return q
            for key, val in entry.iteritems():
                if key == 'id':
                    q = q.ids(val)
                else:
                    q = q.filter(q.entity()._props.contains({key: val}))
            return q

        # Special case for traversing TO case
        if case_cache_enabled() and dst_type == 'case':
            # Rely on shortcut link to case, if it doesn't exist, then
            # this entity does not relate to any cases
            if hasattr(q.entity(), '_related_cases'):
                subq = q.subq_path('_related_cases', end_of_traversal_filter)
            else:
                subq = q.filter(sa.sql.false())

        # Special case for traversing FROM case
        elif case_cache_enabled() and q.entity().label == 'case':
            link = '_related_{}'.format(dst_type)
            q = q.limit(None)
            if hasattr(q.entity(), link):
                subq = q.subq_path(link, end_of_traversal_filter)
            else:
                subq = q.filter(sa.sql.false())

        # Otherwise do a full traversal
        else:
            subq = subq_paths(q, dst_type, end_of_traversal_filter)

        # Add the subq for this dst_type (multiplex on :param:`union`)
        if union:
            union_qs += [subq]
        else:
            q = subq

    # Construct final query (multiplex on :param:`union`)
    if union and union_qs:
        # If we are taking a union of the paths (i.e. OR) compile the union
        q = union_qs.pop(0)
        for union_q in union_qs:
            q = q.union(union_q)
    elif union and not union_qs:
        q = q.filter(sa.sql.false())

    return q


def apply_arg_quicksearch(q, args, info):
    """The quicksearch filter searches for case insensitive substrings
    within the node UUID as well as in the unique keys of the JSONB.

    Currently, for simplicity and performance, only the
    ``submitter_id`` is being used in this filter.

    TODO: make this filter more general. Previous attempts:

        1. included taking a query over subqueries for each unique key
           in the dictionary. Each was sorted by the length of the
           value for that key.  This failed

        2. use the `select_entitiy_from` feature of SQLAlchemy in a
           similar manner to the above attempt. This failed on
           execution when failing to find the '*.node_id' columns for
           node classes.

        - jsm

    """

    search_phrase = args.get('quick_search', None)
    if search_phrase is None:
        # Safety check to make sure that the quicksearch filter is
        # actually being used
        return q

    # This is the phrase we'll be looking for
    search_phrase = search_phrase.lower()
    # The node class
    cls = q.entity()

    node_id_attr = sa.func.lower(cls.node_id)
    sub_id_attr = cls._props['submitter_id'].astext

    # Search for ids that contain the search_phrase
    node_id_query = q.filter(node_id_attr.contains(search_phrase))
    # Search for submitter_ids that contain the search phrase
    sub_id_query = q.filter(sa.func.lower(sub_id_attr).contains(search_phrase))
    # Take the union of those queries
    q = node_id_query.union(sub_id_query)
    # Heuristic ordering based on length
    q.order_by(sa.func.length(sub_id_attr))

    return q


def apply_query_args(q, args, info):
    pg_props = set(getattr(q.entity(), '__pg_properties__', {}).keys())

    # *: filter for those with matching dictionary properties
    for key in set(args.keys()).intersection(pg_props):
        val = args[key]
        val = val if isinstance(val, list) else [val]
        if val:
            q = q.filter(q.entity()._props[key].astext.in_([
                str(v) for v in val]))

    # not: nest a NOT filter for props, filters out matches
    not_props = args.get('not', {})
    not_props = {item.keys()[0]: item.values()[0] for item in not_props}
    for key in set(not_props.keys()).intersection(pg_props):
        val = not_props[key]
        val = val if isinstance(val, list) else [val]
        q = q.filter(sa.not_(q.entity()._props[key].astext.in_([
            str(v) for v in val])))

    # ids: filter for those with ids in a given list
    if 'id' in args:
        q = q.ids(args.get('id'))

    # ids: filter for those with ids in a given list (alias of `id` filter)
    if 'ids' in args:
        q = q.ids(args.get('ids'))

    # quick_search: see ``apply_arg_quicksearch``
    if 'quick_search' in args:
        q = apply_arg_quicksearch(q, args, info)

    # created_after: filter by created datetime
    if 'created_after' in args:
        q = q.filter(q.entity()._props['created_datetime'].cast(sa.DateTime)
                     > dateutil.parser.parse(args['created_after']))

    # created_before: filter by created datetime
    if 'created_before' in args:
        q = q.filter(q.entity()._props['created_datetime'].cast(sa.DateTime)
                     < dateutil.parser.parse(args['created_before']))

    # updated_after: filter by update datetime
    if 'updated_after' in args:
        q = q.filter(q.entity()._props['updated_datetime'].cast(sa.DateTime)
                     > dateutil.parser.parse(args['updated_after']))

    # updated_before: filter by update datetime
    if 'updated_before' in args:
        q = q.filter(q.entity()._props['updated_datetime'].cast(sa.DateTime)
                     < dateutil.parser.parse(args['updated_before']))

    # with_links: (AND) (filter for those with given links)
    if 'with_links' in args:
        for link in set(args['with_links']):
            q = q.filter(get_link_attr(q.entity(), link).any())

    # with_links_any: (OR) (filter for those with given links)
    if 'with_links_any' in args:
        links = set(args['with_links_any'])
        if links:
            subqs = []
            for link in links:
                subqs.append(q.filter(get_link_attr(q.entity(), link).any()))
            q = capp.db.nodes(q.entity()).select_entity_from(sa.union_all(*[
                subq.subquery().select() for subq in subqs
            ]))

    # without_links (AND) (filter for those missing given links)
    if 'without_links' in args:
        for link in args['without_links']:
            q = q.filter(sa.not_(get_link_attr(q.entity(), link).any()))

    # with_path_to: (filter for those with a given traversal)
    if 'with_path_to' in args:
        q = with_path_to(q, args['with_path_to'], info, union=False)

    if 'with_path_to_any' in args:
        q = with_path_to(q, args['with_path_to_any'], info, union=True)

    # without_path_to: (filter for those missing a given traversal)
    if 'without_path_to' in args:
        q = q.except_(with_path_to(
            q, args['without_path_to'], info, name='without_path_to'))

    # project.project_id: Filter projects by logical project_id
    if 'project_id' in args and q.entity().label == 'project':
        # Special case for filtering project by project_id
        q = filter_project_project_id(q, args['project_id'], info)

    # order_by_asc: Apply an ordering to the results
    # (ascending). NOTE: should be after all other non-ordering,
    # before limit, offset queries
    if 'order_by_asc' in args:
        key = args['order_by_asc']
        if key == 'id':
            q = q.order_by(q.entity().node_id)
        elif key in ['type']:
            pass
        elif key in q.entity().__pg_properties__:
            q = q.order_by(q.entity()._props[key])
        else:
            raise RuntimeError('Cannot order by {} on {}'.format(
                key, q.entity().label))

    # order_by_desc: Apply an ordering to the results (descending)
    # NOTE: should be after all other non-ordering, before limit,
    # offset queries
    if 'order_by_desc' in args:
        key = args['order_by_desc']
        if key == 'id':
            q = q.order_by(q.entity().node_id.desc())
        elif key in ['type']:
            pass
        elif key in q.entity().__pg_properties__:
            q = q.order_by(q.entity()._props[key].desc())
        else:
            raise RuntimeError('Cannot order by {} on {}'.format(
                key, q.entity().label))

    # first: truncate result list
    q = apply_arg_limit(q.from_self(), args, info)

    # offset: slice result list with offset from head of list
    q = apply_arg_offset(q, args, info)

    return q


# ======================================================================
# Node interface

def load_node(n, info, fields_depend_on_columns=None):
    """Turns a node into a dictionary (including ``type, id``).  This
    dictionary will prune any unexpected properties from the JSONB.
    (This could happen when somebody else has written a node using a
    schema that has a property definition that our current schema does
    not.  The safest thing to do here is to drop it, because this code
    was tested against a version of the schema that did not have that
    property, the worst case is that the information content is
    behind, but this prevents local code from encountering unexpected
    properities (in particular graphene is not the most graceful about
    it.))

    :returns: A dict representation of the node and its properties.

    """
    return dict(
        filtered_column_dict(n, info, fields_depend_on_columns),
        id=n.node_id,
        type=n.label,
    )

class Node(graphene.Interface):
    """The query object that represents the psqlgraph.Node base"""

    id = graphene.ID()
    type = graphene.String()
    project_id = graphene.String()
    created_datetime = graphene.String()
    updated_datetime = graphene.String()

    # These fields depend on these columns being loaded
    fields_depend_on_columns = {
        "project_id": {"program", "code"},
    }


def resolve_node(self, info, **args):
    """The root query for the :class:`Node` node interface.

    :returns:
        A list of graphene object classes (e.g. a Case query object
        (not a gdcdatamodel Case)).

    """

    q = get_authorized_query(psqlgraph.Node)
    if 'project_id' in args:
        q = q.filter(q.entity()._props['project_id'].astext
                     == args['project_id'])

    q = apply_query_args(q, args, info)

    if 'of_type' in args:
        # TODO: (jsm) find a better solution.  currently this filter
        # will do a subquery for each type AND LOAD THE IDS of all the
        # nodes, then perform a second query given those ids.  We
        # cannot do a ``select_from`` because it does not work
        # properly for the abstract base class with concrete table
        # inheritance (a.k.a it can't find the colums for Node)
        of_types = set(args['of_type'])
        entities = [psqlgraph.Node.get_subclass(label) for label in of_types]
        entities = [e for e in entities if e]

        ids = []
        for label in of_types:
            entity = psqlgraph.Node.get_subclass(label)
            q = get_authorized_query(entity)
            q = apply_query_args(q, args, info)
            try:
                ids += [n.node_id for n in q.all()]
            except Exception as e:
                capp.logger.exception(e)
                raise
        q = get_authorized_query(psqlgraph.Node).ids(ids)
        q = apply_arg_limit(q, args, info)
        q = apply_arg_offset(q, args, info)

    return [__gql_object_classes[n.label](**load_node(n, info, Node.fields_depend_on_columns)) for n in q.all()]


def lookup_graphql_type(T):
    return {
        bool: graphene.Boolean,
        float: graphene.Float,
        int: graphene.Int,
    }.get(T, graphene.String)


# ======================================================================
# Node classes (which implement the Node Interface)


def get_node_class_property_args(cls, not_props_io={}):
    args = {
        name: lookup_graphql_type(types[0])
        for name, types in cls.__pg_properties__.iteritems()
    }
    if cls.label == 'project':
        args['project_id'] = graphene.List(graphene.String)

    not_props_io_name = 'NotPropertiesInput_{}'.format(cls.label)
    if not_props_io_name not in not_props_io:
        args_not = {}
        args_not.update(get_node_class_property_attrs(cls))
        not_props_io[not_props_io_name] = type(
            not_props_io_name,
            (graphene.InputObjectType,),
            args_not,
        )
        globals()[not_props_io[not_props_io_name].__name__] = not_props_io[not_props_io_name]
    args['not'] = graphene.List(__name__ + '.' + not_props_io_name)
    return args


def get_base_node_args():
    return dict(
        id=graphene.String(),
        ids=graphene.List(graphene.String),
        quick_search=graphene.String(),
        first=graphene.Int(default_value=10),
        offset=graphene.Int(),
        created_before=graphene.String(),
        created_after=graphene.String(),
        updated_before=graphene.String(),
        updated_after=graphene.String(),
        order_by_asc=graphene.String(),
        order_by_desc=graphene.String(),
    )


def get_node_interface_args():
    return dict(get_base_node_args(), **dict(
        of_type=graphene.List(graphene.String),
        project_id=graphene.String(),
    ))


def get_node_class_args(cls, _cache={}, _type_cache={}):
    if 'WithPathToInput' not in _type_cache:
        WithPathToInput = get_withpathto_type()
        _type_cache['WithPathToInput'] = WithPathToInput
    else:
        WithPathToInput = _type_cache['WithPathToInput']
    if cls in _cache:
        return _cache[cls]

    args = get_base_node_args()
    args.update(dict(
        with_links=graphene.List(graphene.String),
        with_links_any=graphene.List(graphene.String),
        without_links=graphene.List(graphene.String),
        with_path_to=graphene.List(WithPathToInput),
        with_path_to_any=graphene.List(WithPathToInput),
        without_path_to=graphene.List(WithPathToInput),
    ))
    property_args = {
        name: graphene.List(val)
        if not isinstance(val, graphene.List)
        else val
        for name, val in get_node_class_property_args(cls).items()
    }
    args.update(property_args)

    for key in args:
        if isinstance(args[key], graphene.String):
            args[key] = graphene.Argument(graphene.String, name=key)
        elif isinstance(args[key], graphene.Int):
            args[key] = graphene.Argument(graphene.Int, name=key)
        elif not isinstance(args[key], graphene.Argument):
            args[key] = graphene.Argument(args[key], name=key)

    _cache[cls] = args
    return args


def get_node_class_property_attrs(cls, _cache={}):
    if cls in _cache:
        return _cache[cls]

    def resolve_type(self, info, *args):
        return self.__class__.__name__
    attrs = {
        name: graphene.Field(lookup_graphql_type(types[0]))
        for name, types in cls.__pg_properties__.iteritems()
    }
    attrs['resolve_type'] = resolve_type

    if cls.label == 'project':
        def resolve_project_id(self, info, *args):
            program = get_authorized_query(md.Program).subq_path(
                'projects', lambda q: q.ids(self.id)).one()
            return '{}-{}'.format(program.name, self.code)
        attrs['project_id'] = graphene.String()
        attrs['resolve_project_id'] = resolve_project_id

    attrs.update(get_node_class_special_attrs(cls))

    _cache[cls] = attrs
    return attrs


def get_node_class_special_attrs(cls):
    """Return attrs conditional on the type of node.  This function was
    originally introduced to conditionally add _data_bundle
    completeness_ which requires condensing the information of
    traversals into an apparently scalar and queryable property.  Data
    bundles are now gone, but I'm leaving this function here for
    extensibility in spite of the function call overhead.

    """

    attrs = {}

    return attrs


def get_node_class_link_attrs(cls):
    attrs = {name: graphene.List(
        __name__ + '.' + link['type'].label,
        args=get_node_class_args(link['type']),
    ) for name, link in cls._pg_edges.iteritems()}

    def resolve__related_cases(self, info, args):
        if not case_cache_enabled():
	    return []
        # Don't resolve related cases for cases
        if cls.label == 'case':
            return []

        q = with_path_to(get_authorized_query(md.Case), {
            'type': cls.label,
            'id': self.id,
        }, info, name='related_cases')
        qcls = __gql_object_classes['case']
        try:
            return [qcls(**load_node(n, info, Node.fields_depend_on_columns)) for n in q.all()]
        except Exception as e:
            capp.logger.exception(e)
            raise

    if case_cache_enabled():
        attrs['resolve__related_cases'] = resolve__related_cases
        attrs['_related_cases'] = graphene.List(
            'peregrine.resources.submission.graphql.node.case',
            args=get_node_class_args(md.Case)
        )

    for link in cls._pg_edges:
        name = COUNT_NAME.format(link)
        attrs[name] = graphene.Field(
            graphene.Int, args=get_node_class_args(cls))

    # transaction logs that affected this node
    def resolve_transaction_logs_count(self, info, **args):
        args = dict(args, **{'entities': [self.id]})
        return transaction.resolve_transaction_log_count(self, info, **args)

    attrs['resolve__transaction_logs_count'] = resolve_transaction_logs_count
    attrs['_transaction_logs_count'] = graphene.Field(
        graphene.Int,
        args=transaction.get_transaction_log_args(),
    )

    def resolve_transaction_logs(self, info, **args):
        args = dict(args, **{'entities': [self.id]})
        return transaction.resolve_transaction_log(self, info, **args)

    attrs['resolve__transaction_logs'] = resolve_transaction_logs
    attrs['_transaction_logs'] = graphene.List(
        transaction.TransactionLog,
        args=transaction.get_transaction_log_args(),
    )

    _links_args = get_node_interface_args()
    _links_args.pop('of_type', None)
    attrs['_links'] = graphene.List(Node, args=_links_args)

    return attrs


def get_node_class_link_resolver_attrs(cls):
    link_resolver_attrs = {}
    for link_name, link in cls._pg_edges.iteritems():

        def link_query(self, info, cls=cls, link=link, **args):
            try:
                target, backref = link['type'], link['backref']
                # Subquery for neighor connected to node
                sq = get_authorized_query(target).filter(
                    getattr(target, backref)
                    .any(node_id=self.id)).subquery()
                q = get_authorized_query(target).filter(
                    target.node_id == sq.c.node_id)
                q = apply_query_args(q, args, info)
                return q
            except Exception as e:
                capp.logger.exception(e)
                raise

        # Nesting links
        def resolve_link(self, info, cls=cls, link=link, **args):
            try:
                q = link_query(self, info, cls=cls, link=link, **args)
                qcls = __gql_object_classes[link['type'].label]
                return [qcls(**load_node(n, info, Node.fields_depend_on_columns)) for n in q.all()]
            except Exception as e:
                capp.logger.exception(e)
                raise
        lr_name = 'resolve_{}'.format(link_name)
        resolve_link.__name__ = lr_name
        link_resolver_attrs[lr_name] = resolve_link

        # Link counts
        def resolve_link_count(self, info, cls=cls, link=link, **args):
            try:
                q = link_query(self, info, cls=cls, link=link, **args)
                q = q.with_entities(sa.distinct(link['type'].node_id))
                q = q.limit(None)
                return q.count()
            except Exception as e:
                capp.logger.exception(e)
                raise
        lr_count_name = 'resolve_{}'.format(COUNT_NAME.format(link_name))
        resolve_link_count.__name__ = lr_count_name
        link_resolver_attrs[lr_count_name] = resolve_link_count

        # Arbitrary link
        def resolve_links(self, info, cls=cls, **args):
            try:
                edge_out_sq = capp.db.edges().filter(
                    psqlgraph.Edge.src_id == self.id).subquery()
                edge_in_sq = capp.db.edges().filter(
                    psqlgraph.Edge.dst_id == self.id).subquery()
                q1 = get_authorized_query(psqlgraph.Node).filter(
                    psqlgraph.Node.node_id == edge_in_sq.c.src_id)
                q2 = get_authorized_query(psqlgraph.Node).filter(
                    psqlgraph.Node.node_id == edge_out_sq.c.dst_id)
                q1 = apply_query_args(q1, args, info).limit(None)
                q2 = apply_query_args(q2, args, info).limit(None)
                q = q1.union(q2)
                apply_arg_limit(q, args, info)
                return [
                    __gql_object_classes[n.label](**load_node(n, info, Node.fields_depend_on_columns))
                    for n in q.all()
                ]
            except Exception as e:
                capp.logger.exception(e)
                raise

        lr_links_name = 'resolve__links'
        resolve_link_count.__name__ = lr_links_name
        link_resolver_attrs[lr_links_name] = resolve_links

    return link_resolver_attrs


def create_node_class_gql_object(cls):
    def _make_inner_meta_type():
        return type('Meta', (), {'interfaces': (Node, )})
    attrs = {}
    attrs.update(get_node_class_property_attrs(cls))
    attrs.update(get_node_class_link_attrs(cls))
    attrs.update(get_node_class_link_resolver_attrs(cls))
    attrs['Meta'] = _make_inner_meta_type()

    gql_object = type(cls.label, (graphene.ObjectType, ), attrs)

    # Add this class to the global namespace to graphene can load it
    globals()[gql_object.__name__] = gql_object

    # Graphene requires lambda's of the classes now so return that here
    return gql_object


def create_root_fields(fields):
    attrs = {}
    for cls, gql_object in fields.iteritems():
        name = cls.label

        # Object resolver
        def resolver(self, info, cls=cls, gql_object=gql_object, **args):
            q = get_authorized_query(cls)
            q = apply_query_args(q, args, info)
            try:
                return [gql_object(**load_node(n, info, Node.fields_depend_on_columns)) for n in q.all()]
            except Exception as e:
                capp.logger.exception(e)
                raise

        field = graphene.Field(
            graphene.List(gql_object),
            args=get_node_class_args(cls),
        )

        res_name = 'resolve_{}'.format(name)
        resolver.__name__ = res_name
        attrs[name] = field
        attrs[res_name] = resolver

        # Count resolver
        def count_resolver(self, info, cls=cls, gql_object=gql_object, **args):
            q = get_authorized_query(cls)
            q = apply_query_args(q, args, info)
            if 'with_path_to' in args or 'with_path_to_any' in args:
                q = q.with_entities(sa.distinct(cls.node_id))
            q = q.limit(args.get('first', None))
            return q.count()

        count_field = graphene.Field(
            graphene.Int, args=get_node_class_args(cls))
        count_name = COUNT_NAME.format(name)
        count_res_name = 'resolve_{}'.format(count_name)
        count_resolver.__name__ = count_res_name
        attrs[count_name] = count_field
        attrs[count_res_name] = count_resolver

    return attrs

def get_withpathto_type():
    return  type('WithPathToInput', (graphene.InputObjectType,), dict(
        id=graphene.String(),
        type=graphene.String(required=True),
        **{k: graphene.Field(v) for cls_attrs in [
            get_node_class_property_args(cls)
            for cls in psqlgraph.Node.get_subclasses()
        ] for k, v in cls_attrs.iteritems()}
    ))

def get_fields():
    __fields = {
        cls: create_node_class_gql_object(cls)
        for cls in psqlgraph.Node.get_subclasses()
    }

    for cls, gql_object in __fields.iteritems():
        __gql_object_classes[cls.label] = gql_object

    return __fields


NodeField = graphene.List(Node, args=get_node_interface_args())


# ======================================================================
# DataNode


class DataNode(graphene.Interface):
    id = graphene.ID()
    shared_fields = None # fields shared by all data nodes in the dictionary


def get_shared_fields_dict():
    """Return a dictionary containing the fields shared by all data nodes."""

    if not DataNode.shared_fields:

        # fields lists the set of node fields, for every data node in the dictionary schema (nodes ending with '_file')
        fields = [
            set(schema['properties'].keys())
            for schema in dictionary.schema.values()
            if schema['category'].endswith('_file')
        ]

        # shared_fields takes the intersection of all the data node field sets
        shared_fields = set.intersection(*fields)

        shared_fields_dict = {field: graphene.String() for field in shared_fields}
        if 'file_size' in shared_fields:
            shared_fields_dict['file_size'] = graphene.Int()
        DataNode.shared_fields = shared_fields_dict

    return DataNode.shared_fields


def resolve_datanode(self, info, **args):
    """The root query for the :class:`DataNode` node interface.

    :returns:
        A list of graphene object classes.

    """

    # get the list of categories that are data categories
    data_types_labels = [
        node
        for node in dictionary.schema
        if dictionary.schema[node]['category'].endswith('_file')
    ]

    # get the subclasses for the data categories
    data_types = [
        node
        for node in psqlgraph.Node.get_subclasses()
        if node.label in data_types_labels
    ]

    q_all = []
    for data_type in data_types:

        q = get_authorized_query(data_type)
        if 'project_id' in args:
            q = q.filter(q.entity()._props['project_id'].astext
                         == args['project_id'])

        q = apply_query_args(q, args, info)

        if 'of_type' in args:
            of_types = set(args['of_type'])
            entities = [psqlgraph.Node.get_subclass(label) for label in of_types]
            entities = [e for e in entities if e]

            ids = []
            for label in of_types:
                entity = psqlgraph.Node.get_subclass(label)
                q = get_authorized_query(entity)
                q = apply_query_args(q, args, info)
                try:
                    ids += [n.node_id for n in q.all()]
                except Exception as e:
                    capp.logger.exception(e)
                    raise
            q = get_authorized_query(psqlgraph.Node).ids(ids)
            q = apply_arg_limit(q, args, info)
            q = apply_arg_offset(q, args, info)

        q_all.extend(q.all())

    return [__gql_object_classes[n.label](**load_node(n, info)) for n in q_all]


def get_datanode_interface_args():
    args = get_base_node_args()
    args.update(get_shared_fields_dict())
    args.update({
        'of_type': graphene.List(graphene.String),
        'project_id': graphene.String(),
    })
    return args
