"""
Construct the blueprint for gdcapi submissions, using the blueprint from
:py:mod:``sheepdog``.
"""

import os

import flask
import gdcdatamodel
from gdcdatamodel import models
import gdcdictionary
import sheepdog

from . import graphql


blueprint = sheepdog.create_blueprint(
    gdcdictionary.gdcdictionary, gdcdatamodel.models
)


def get_open_project_ids():
    """
    List project ids corresponding to projects with ``availability_type ==
    "Open"``.

    Return:
        Tuple[List[str], List[str]]:
            list of project ids for open projects and list of error messages
            generated from running graphql
    """
    with flask.current_app.db.session_scope():
        projects = (
            flask.current_app.db
            .nodes(models.Project)
            .filter(models.Project.availability_type.astext == "Open")
            .all()
        )
    return [project['code'] for project in projects]


def set_read_access_projects():
    """
    Assign the list of projects (as strings of project ids) for which the user
    has read access to ``flask.g.read_access_projects``.

    The user has read access, firstly, to the projects for which they directly
    have read permissions, and also to projects with availability type marked
    "Open".

    Return:
        None

    Raises:
        sheepdog.errors.AuthError:
            if ``flask.g.user`` does not exist or if the user is not logged in
            (does not have a username), then an InvalidTokenError (inheriting
            from AuthError) is raised by ``FederatedUser.get_project_ids``

    Side Effects:
        assigns result from ``get_open_project_ids`` to
        ``flask.g.read_access_projects``.
    """
    if not hasattr(flask.g, 'read_access_projects'):
        if not hasattr(flask.g, 'user'):
            raise sheepdog.errors.AuthError('user does not exist')
        flask.g.read_access_projects = flask.g.user.get_project_ids('read')
        open_project_ids = get_open_project_ids()
        flask.g.read_access_projects.extend(open_project_ids)


@blueprint.route('/graphql', methods=['POST'])
@sheepdog.auth.set_global_user
def root_graphql_query():
    """
    Run a graphql query.
    """
    # Short circuit if user is not recognized. Make sure that the list of
    # projects that the user has read access to is set.
    try:
        set_read_access_projects()
    except sheepdog.errors.AuthError:
        data = flask.jsonify({'data': {}, 'errors': ['Unauthorized query.']})
        return data, 403
    payload = sheepdog.utils.parse.parse_request_json()
    query = payload.get('query')
    variables, errors = sheepdog.utils.get_variables(payload)
    if errors:
        return flask.jsonify({'data': None, 'errors': errors}), 400
    return sheepdog.utils.jsonify_check_errors(
        graphql.execute_query(query, variables)
    )


def get_introspection_query():
    """
    Load the graphql introspection query from its file.

    Return:
        str: the graphql introspection query
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.join(current_dir, 'graphql', 'introspection_query.txt')
    with open(filename, 'r') as introspection_query:
        return introspection_query.read()


@blueprint.route('/getschema', methods=['GET'])
def root_graphql_schema_query():
    """
    Get the graphql schema.

    Dig up the introspection query string from file, run it through graphql,
    and jsonify the result.
    """
    return (
        sheepdog.utils.jsonify_check_errors(
            graphql.execute_query(get_introspection_query())
        )
    )
