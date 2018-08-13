"""
Construct the blueprint for peregrine submissions, using the blueprint from
:py:mod:``peregrine``.
"""

import os
import json

import flask
import datamodelutils.models as models
import peregrine.blueprints

from . import graphql


def get_open_project_ids():
    """
    List project ids corresponding to projects with ``availability_type ==
    "Open"``.

    Return:
        Tuple[List[str], List[str]]:
            list of project ids for open projects and list of error messages
            generated from running graphql
    """
    if not hasattr(models.Project, 'availability_type'):
        return []

    with flask.current_app.db.session_scope():
        projects = (
            flask.current_app.db
            .nodes(models.Project)
            .filter(models.Project.availability_type.astext == "Open")
            .all()
        )
        return [project['programs'][0]['name'] + '-' + project['code'] for project in projects]


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
        peregrine.errors.AuthZError:
            if ``flask.g.user`` does not exist or if the user is not logged in
            (does not have a username), then an InvalidTokenError (inheriting
            from AuthZError) is raised by ``FederatedUser.get_project_ids``

    Side Effects:
        assigns result from ``get_open_project_ids`` to
        ``flask.g.read_access_projects``.
    """
    if not hasattr(flask.g, 'read_access_projects'):
        if not hasattr(flask.g, 'user'):
            raise peregrine.errors.AuthZError('user does not exist')
        flask.g.read_access_projects = flask.g.user.get_project_ids('read')
        open_project_ids = get_open_project_ids()
        flask.g.read_access_projects.extend(open_project_ids)


@peregrine.blueprints.blueprint.route('/graphql', methods=['POST'])
@peregrine.auth.set_global_user
def root_graphql_query():
    """
    Run a graphql query.
    """
    # Short circuit if user is not recognized. Make sure that the list of
    # projects that the user has read access to is set.
    print("root_graphql_query. Run a graphql query in resource/submission/__init__")
    try:
        set_read_access_projects()
    except peregrine.errors.AuthZError:
        data = flask.jsonify({'data': {}, 'errors': ['Unauthorized query.']})
        return data, 403
    payload = peregrine.utils.parse_request_json()
    query = payload.get('query')
    variables, errors = peregrine.utils.get_variables(payload)
    if errors:
        return flask.jsonify({'data': None, 'errors': errors}), 400
    return peregrine.utils.jsonify_check_errors(
        graphql.execute_query(query, variables)
    )


def generate_schema_file(graphql_schema):
    """
    Load the graphql introspection query from its file.

    Return:
        str: the graphql introspection query
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    # relative to current running directory
    schema_file = 'schema.json'

    query_file = os.path.join(
        current_dir, 'graphql', 'introspection_query.txt')
    with open(query_file, 'r') as f:
        query = f.read()

    with open(schema_file, 'w') as f:
        result = graphql_schema.execute(query)
        data = {'data': result.data}
        if result.errors:
            data['errors'] = [err.message for err in result.errors]
        json.dump(data, f)

    return os.path.abspath(schema_file)


@peregrine.blueprints.blueprint.route('/getschema', methods=['GET'])
def root_graphql_schema_query():
    """
    Get the graphql schema.

    Dig up the introspection query string from file, run it through graphql,
    and jsonify the result.
    """
    return flask.send_file(flask.current_app.schema_file)
