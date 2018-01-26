# -*- coding: utf-8 -*-

"""
peregrine.resources.submission.graphql.util
----------------------------------------

Defines utility functions for GraphQL implementation.
"""

from flask import current_app as capp
from flask import g as fg
from peregrine.errors import AuthError, UserError
from datamodelutils import models
from graphql import GraphQLError

from graphql.utils.ast_to_dict import ast_to_dict
from sqlalchemy.orm import load_only

import psqlgraph

# from peregrine.resources.submission.constants import (
#     FILTER_ACTIVE,
# )

DEFAULT_LIMIT = 10


def set_session_timeout(session, timeout):
    session.execute(
        'SET LOCAL statement_timeout = {}'
        .format(int(float(timeout)*1000))
    )

def get_column_names(entity):
    """Returns an iterable of column names the entity has"""
    if hasattr(entity, '__pg_properties__'):
        return (k for k in entity.__pg_properties__)

    return (c.name for c in entity.__table__.columns)


def column_dict(row, skip=set()):
    """Returns a dict with all columns except those in :param:`skip`"""

    return {
        column: getattr(row, column)
        for column in get_column_names(row)
        if column not in skip
    }


def filtered_column_dict(row, info, fields_depend_on_columns=None):
    """Returns a dict with only columns required for query"""

    columns = get_loaded_columns(row, info, fields_depend_on_columns)

    return {
        column: getattr(row, column)
        for column in columns
    }



def get_active_project_ids():
    return [
        '{}-{}'.format(project.programs[0].name, project.code)
        for project in capp.db.nodes(Project)
        .filter(models.Project._props['state'].astext != 'closed')
        .filter(models.Project._props['state'].astext != 'legacy')
        .all()
    ]


def active_project_filter(q):
    """Takes a query and applies a filter to select only nodes that have a
    ``project_id`` relating to an active project.

    :param q: a SQLAlchemy ``Query`` object
    :returns: the filtered ``Query`` object

    ..note::

        For security reasons, if the selected query entity is a
        :class:`psqlgraph.Node` object, apply the filter on project
        id.  This removes things that do not have a ``project_id`` from
        the results.  TODO: make allow result types that do not have
        ``project_id`` while maintaining filter correctness.


    """

    cls = q.entity()

    if cls.label == 'project':
        return (q.filter(models.Project._props['state'].astext != 'closed')
                .filter(models.Project._props['state'].astext != 'legacy'))

    fg.active_project_ids = fg.get('active_project_ids') or get_active_project_ids()
    if cls == psqlgraph.Node or hasattr(cls, 'project_id'):
        project_id_attr = cls._props['project_id'].astext
        q = q.filter(project_id_attr.in_(fg.active_project_ids))

    return q


def authorization_filter(q):
    """Takes a query and applies a filter to select only nodes that the
    current request user has access to based on ``project_id``.

    :param q: a SQLAlchemy ``Query`` object
    :returns: the filtered ``Query`` object

    ..note::

        For security reasons, if the selected query entity is a
        :class:`psqlgraph.Node` object, apply the filter on project
        id.  This removes things that do not have a ``project_id`` from
        the results.  TODO: make allow result types that do not have
        ``project_id`` while maintaining filter correctness.

    """
 
    cls = q.entity()
    if cls == psqlgraph.Node or hasattr(cls, 'project_id'):
        q = q.filter(cls._props['project_id'].astext.in_(fg.read_access_projects))

    # if FILTER_ACTIVE:
    #     q = active_project_filter(q)

    return q


def get_authorized_query(cls):
    return authorization_filter(capp.db.nodes(cls))


def apply_arg_limit(q, args, info):
    limit = args.get('first', DEFAULT_LIMIT)
    if limit > 0:
        q = q.limit(limit)
    return q


def apply_arg_offset(q, args, info):
    offset = args.get('offset', 0)
    if offset > 0:
        q = q.offset(offset)
    return q

def get_loaded_columns(entity, info, fields_depend_on_columns=None):
    """Returns a set of columns loaded from database
    because some fields depend on columns of a different name,
    :param:`depends_on` is there to map to the so we know to load them
    """

    fields = set(get_fields(info))

    if fields_depend_on_columns:
        fields.update({
            column
            for field in fields
            for column in fields_depend_on_columns.get(field, {})
        })

    all_columns = set(get_column_names(entity))
    used_columns = fields.intersection(all_columns)

    return used_columns


def apply_load_only(query, info, fields_depend_on_columns=None):
    """Returns optimized q by selecting only the necessary columns"""

    # if the entity doesn't have a backing table then don't do this
    # this happens when using the generic node property
    if not hasattr(query.entity(), '__table__'):
        return query

    columns = get_loaded_columns(query.entity(), info, fields_depend_on_columns)

    return query.options(load_only(*columns))


# The below is lifted from
# https://gist.github.com/mixxorz/dc36e180d1888629cf33

def collect_fields(node, fragments):
    """Recursively collects fields from the AST
    Args:
        node (dict): A node in the AST
        fragments (dict): Fragment definitions
    Returns:
        A dict mapping each field found, along with their sub fields.
        {'name': {},
         'sentimentsPerLanguage': {'id': {},
                                   'name': {},
                                   'totalSentiments': {}},
         'slug': {}}
    """

    field = {}

    if node.get('selection_set'):
        for leaf in node['selection_set']['selections']:
            if leaf['kind'] == 'Field':
                field.update({
                    leaf['name']['value']: collect_fields(leaf, fragments)
                })
            elif leaf['kind'] == 'FragmentSpread':
                field.update(collect_fields(fragments[leaf['name']['value']],
                                            fragments))

    return field


def get_fields(info):
    """A convenience function to call collect_fields with info
    Args:
        info (ResolveInfo)
    Returns:
        dict: Returned from collect_fields
    """

    fragments = {}
    node = ast_to_dict(info.field_asts[0])

    for name, value in info.fragments.items():
        fragments[name] = ast_to_dict(value)

    return collect_fields(node, fragments)
