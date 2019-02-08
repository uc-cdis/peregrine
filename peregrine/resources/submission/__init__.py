"""
Construct the blueprint for peregrine submissions, using the blueprint from
:py:mod:``peregrine``.
"""

import os
import json
import time
import fcntl

from cdiserrors import AuthZError
import datamodelutils.models as models
import flask

from peregrine.auth import current_user, get_program_project_roles
import peregrine.blueprints
from peregrine.resources.submission import graphql


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
        return [
            program['name'] + '-' + project['code']
            for project in projects
            for program in project['programs']
        ]


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
            from AuthError) is raised by ``CurrentUser.get_project_ids``

    Side Effects:
        assigns result from ``get_open_project_ids`` to
        ``flask.g.read_access_projects``.
    """
    if not hasattr(flask.g, 'read_access_projects'):
        flask.g.read_access_projects = []
        user_project_ids = current_user.get_project_ids('read')
        # translate the project IDs from user into {program}-{project}
        with flask.current_app.db.session_scope():
            programs = (
                flask.current_app.db
                .nodes(models.Program)
                .prop_in('dbgap_accession_number', user_project_ids)
                .all()
            )
            flask.g.read_access_projects.extend(
                program.name + '-' + project.code
                for program in programs
                for project in program.projects
            )
            projects = (
                flask.current_app.db
                .nodes(models.Project)
                .prop_in('dbgap_accession_number', user_project_ids)
                .all()
            )
            flask.g.read_access_projects.extend(
                program.name + '-' + project.code
                for project in projects
                for program in project.programs
            )
        open_project_ids = get_open_project_ids()
        flask.g.read_access_projects.extend(open_project_ids)


@peregrine.blueprints.blueprint.route('/graphql', methods=['POST'])
def root_graphql_query():
    """
    Run a graphql query.
    """
    # Short circuit if user is not recognized. Make sure that the list of
    # projects that the user has read access to is set.
    try:
        set_read_access_projects()
    except AuthZError:
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


def generate_schema_file(graphql_schema, app_logger):
    """
    Load the graphql introspection query from its file.
    Because uwsgi launches multiple processes in the same container, processes
    eat up memory and CPU generating the schema simultaneously. To avoid this,
    we only give access to schema.json to one process at a time.
    Update: master process now handles app init - leaving the locking system in
    case it's needed later.

    Return:
        str: the graphql introspection query
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    # relative to current running directory
    schema_file = 'schema.json'

    # if the file has already been generated, do not re-generate it
    if os.path.isfile(schema_file):
        try:
            # if we can lock the file, the generation is done -> return
            # if not, another process is currently generating it -> wait
            with open(schema_file, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            app_logger.info('Skipping {} generation (file already exists)'.format(schema_file))
            return os.path.abspath(schema_file)
        except IOError:
            pass

    query_file = os.path.join(
        current_dir, 'graphql', 'introspection_query.txt')
    with open(query_file, 'r') as f:
        query = f.read()

    try:
        with open(schema_file, 'w') as f:
            # lock file (prevents several processes from generating the schema at the same time)
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            app_logger.info('Generating the graphql schema file {}'.format(schema_file))

            # generate the schema file
            start = time.time()
            result = graphql_schema.execute(query)
            data = {'data': result.data}
            if result.errors:
                data['errors'] = [err.message for err in result.errors]
            json.dump(data, f)

            end = int(round(time.time() - start))
            app_logger.info('Generated {} in {} sec'.format(schema_file, end))
            fcntl.flock(f, fcntl.LOCK_UN) # unlock file
    except IOError:
        # wait for file unlock (end of schema generation) before proceeding
        timeout_minutes = 5 # 5 minutes from now
        wait_for_file(schema_file, timeout_minutes, app_logger)

    return os.path.abspath(schema_file)


def wait_for_file(file_name, timeout_minutes, app_logger):
    print('A process is waiting for {} generation.'.format(file_name))
    timeout = time.time() + 60 * timeout_minutes
    while True:
        try:
            with open(file_name, 'r') as f: # try to access+lock the file
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            break # file is available -> schema has been generated -> process can proceed
        except IOError: # file is still unavailable -> process waits
            pass
        if time.time() > timeout:
            app_logger.warning('A process is proceeding without waiting for end of {} generation ({} minutes timeout)'.format(file_name, timeout_minutes))
            break
        time.sleep(0.5)


@peregrine.blueprints.blueprint.route('/getschema', methods=['GET'])
def root_graphql_schema_query():
    """
    Get the graphql schema.

    Dig up the introspection query string from file, run it through graphql,
    and jsonify the result.
    """
    return flask.send_file(flask.current_app.schema_file)
