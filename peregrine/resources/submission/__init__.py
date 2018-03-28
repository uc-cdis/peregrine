"""
Construct the blueprint for peregrine submissions, using the blueprint from
:py:mod:``peregrine``.
"""

import datetime
import os
import os.path

import flask
import json
import shutil
from flask import Response, send_file, stream_with_context
import datamodelutils.models as models
import peregrine.blueprints
from . import graphql

from peregrine.utils import jsonify_check_errors


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
        peregrine.errors.AuthError:
            if ``flask.g.user`` does not exist or if the user is not logged in
            (does not have a username), then an InvalidTokenError (inheriting
            from AuthError) is raised by ``FederatedUser.get_project_ids``

    Side Effects:
        assigns result from ``get_open_project_ids`` to
        ``flask.g.read_access_projects``.
    """
    if not hasattr(flask.g, 'read_access_projects'):
        if not hasattr(flask.g, 'user'):
            raise peregrine.errors.AuthError('user does not exist')
        flask.g.read_access_projects = flask.g.user.get_project_ids('read')
        open_project_ids = get_open_project_ids()
        flask.g.read_access_projects.extend(open_project_ids)


@peregrine.blueprints.blueprint.route('/graphql', methods=['POST'])
@peregrine.auth.set_global_user
def root_graphql_query():
    """
    Run a graphql query and export to supported formats(json, bdbag)

    """
    # Short circuit if user is not recognized. Make sure that the list of
    # projects that the user has read access to is set.

    print("=====root_graphql_query. Run a graphql query in resource/submission/__init__=====")
    try:
        set_read_access_projects()
    except peregrine.errors.AuthError:
        data = flask.jsonify({'data': {}, 'errors': ['Unauthorized query.']})
        return data, 403
    payload = peregrine.utils.parse_request_json()
    query = payload.get('query')
    export_format = payload.get('format')
    variables, errors = peregrine.utils.get_variables(payload)
    if errors:
        return flask.jsonify({'data': None, 'errors': errors}), 400

    return_data = jsonify_check_errors(graphql.execute_query(query, variables))
    data, code = return_data

    if code != 200:
        return data, code

    # if export_format == 'tsv':
    #     res = peregrine.utils.json2tbl(json.loads(data.data), '', "-")
    #     tsv = peregrine.utils.dicts2tsv(res)
    #     return flask.Response(tsv, mimetype='text/tab-separated-values'), 200

    if export_format == 'bdbag':
        res = peregrine.utils.flatten_json(json.loads(data.data), '', "-")

        bag_info = {'organization': 'CDIS',
                    'data_type': 'TOPMed',
                    'date_created': datetime.date.today().isoformat()}
        args = dict(
            bag_info=bag_info,
            payload=res)
        bag = peregrine.utils.create_bdbag(**args)  # bag is a compressed file
        data = send_file(bag, attachment_filename='manifest_bag.zip')
        shutil.rmtree(os.path.abspath(os.path.join(bag, os.pardir)))
        return data, 200
    else:
        return return_data


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


@peregrine.blueprints.blueprint.route('/getschema', methods=['GET'])
def root_graphql_schema_query():
    """
    Get the graphql schema.

    Dig up the introspection query string from file, run it through graphql,
    and jsonify the result.
    """
    return (
        peregrine.utils.jsonify_check_errors(
            graphql.execute_query(get_introspection_query())
        )
    )

# @peregrine.blueprints.blueprint.route('/export', methods=['POST'])
# def get_manifest():
#     """
#     Creates and returns a manifest based on the filters pased on
#     to this endpoint
#     parameters:
#         - name: filters
#           in: graphql result in json format
#           description: Filters to be applied when generating the manifest
#     :return: A manifest that the user can use to download the files in there
#     """
#     payload = peregrine.utils.parse_request_json()
#     export_data = payload.get('export_data')
#     bag_path = payload.get('bag_path')

#     if(bag_path is None):
#         return flask.jsonify({'bag_path': None, 'errors': 'bag_path is required!!!'}), 400

#     if peregrine.utils.contain_node_with_category(export_data, 'data_file') == False:
#         return flask.jsonify({'errors': 'No data_file node'}), 400

#     res = peregrine.utils.json2tbl(export_data, '', "_")
#     tsv = peregrine.utils.dicts2tsv(res)

#     bag_info = {'organization': 'CDIS',
#                 'data_type': 'TOPMed',
#                 'date_created': datetime.date.today().isoformat()}
#     args = dict(
#         bag_path=bag_path,
#         bag_info=bag_info,
#         payload=res)
#     # bag is a compressed file
#     return peregrine.utils.create_bdbag(**args), 200

#     # return flask.jsonify({'data': res}), 200