# -*- coding: utf-8 -*-

"""
peregrine.resources.submission.graphql.util
----------------------------------------

Defines utility functions for GraphQL implementation.
"""

from flask import current_app as capp
from flask import g as fg
from peregrine.errors import InternalError, AuthError, UserError
from gdcdatamodel.models import Project
from graphql import GraphQLError

import psqlgraph

DEFAULT_LIMIT = 10


def set_session_timeout(session, timeout):
    session.execute(
        'SET LOCAL statement_timeout = {}'
        .format(int(float(timeout)*1000))
    )


def column_dict(row):
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
    }


def get_active_project_ids():
    return [
        '{}-{}'.format(project.programs[0].name, project.code)
        for project in capp.db.nodes(Project)
        .filter(Project._props['state'].astext != 'closed')
        .filter(Project._props['state'].astext != 'legacy')
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
        return (q.filter(Project._props['state'].astext != 'closed')
                .filter(Project._props['state'].astext != 'legacy'))

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

    try:
        if not hasattr(fg, 'read_access_projects'):
            raise AuthError('no read access projects')
    except (AuthError, UserError) as e:
        capp.logger.exception(e)
        raise GraphQLError(str(e))
    except Exception as e:
        capp.logger.exception(e)
        raise InternalError()

    cls = q.entity()
    if cls == psqlgraph.Node or hasattr(cls, 'project_id'):
        q = q.filter(cls._props['project_id'].astext.in_(fg.read_access_projects))

    q = active_project_filter(q)
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
