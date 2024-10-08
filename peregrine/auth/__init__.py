"""
The authutils to use will depend on the downstream dependency
and how it installs authutils.

eg:
``pip install git+https://git@github.com/NCI-GDC/authutils.git@1.2.3#egg=authutils``
or
``pip install git+https://git@github.com/uc-cdis/authutils.git@1.2.3#egg=authutils``
"""

from authutils.user import current_user
from cdislogging import get_logger
from datamodelutils import models
from gen3authz.client.arborist.errors import ArboristError
import flask
import itertools
from operator import itemgetter


logger = get_logger(__name__)


def resource_path_to_project_ids(resource_path):
    parts = resource_path.strip("/").split("/")

    # resource path ignored by peregrine
    if resource_path != "/" and parts[0] != "programs":
        return []

    if len(parts) > 8 or (len(parts) > 2 and parts[2] != "projects") or (len(parts) > 4 and (flask.current_app.subject_entity is None or parts[4] != "persons")) or (len(parts) > 6 and (flask.current_app.node_authz_entity_name is None or flask.current_app.node_authz_entity is None or parts[6] != (flask.current_app.node_authz_entity_name + "s"))):
        logger.warn(
            "ignoring resource path {} because peregrine cannot handle a permission more granular than program/project/node level".format(
                resource_path
            )
        )
        return []

    # "/" or "/programs": access to all programs
    if len(parts) == 1:
        programs = flask.current_app.db.nodes(models.Program).all()
        return [
            { 'project_id': program.name + "-" + project.code, 'node_id': '*' }
            for program in programs
            for project in program.projects
        ]

    # "/programs/[...]" or "/programs/[...]/projects/":
    # access to all projects of a program
    if len(parts) < 4:
        program_name = parts[1]
        program = (
            flask.current_app.db.nodes(models.Program).props(name=program_name).first()
        )
        if not program:
            logger.debug(
                "program {} in resource path {} does not exist".format(
                    program_name, resource_path
                )
            )
            return []
        return [{ 'project_id': program.name + "-" + project.code, 'node_id': '*' } for project in program.projects]

    # "/programs/[...]/projects/[...]" or "/programs/[...]/projects/[...]/{node}s": access to a specific project
    # access to all nodes in a project
    if len(parts) < 6:
        project_code = parts[3]
        project = (
            flask.current_app.db.nodes(models.Project).props(code=project_code).first()
        )
        if not project:
            logger.warn(
                "project {} in resource path {} does not exist".format(
                    project_code, resource_path
                )
            )
            return []
        return [ { 'project_id': program.name + "-" + project.code, 'node_id': '*' } for program in project.programs]


    #"/programs/[...]/projects/[...]/persons/[...]" or "/programs/[...]/projects/[...]/persons/[...]/{node}s": access to a specific person
    # access to a person in the project
    if len(parts) < 8:
        program_name = parts[1]
        project_code = parts[3]
        node_submitter_id = parts[5]
        # TODO we can handle this as person or return an array of all the subject under the person
        return [ { 'project_id': program_name + "-" + project_code, 'node_id': node_submitter_id } ]

    # "/programs/[...]/projects/[...]/{node}s/{submitter_id}": access to a specific project's child node subbranch
    # here, len(parts) == 8 and parts[4] == (flask.current_app.node_authz_entity_name + "s")
    program_name = parts[1]
    project_code = parts[3]
    node_submitter_id = parts[7]
    return [ { 'project_id': program_name + "-" + project_code, 'node_id': node_submitter_id } ]

def get_read_access_resources():
    """
    Get all resources the user has read access to and parses the Arborist resource paths into a program.name, project.code and node id.
    """
    try:
        mapping = flask.current_app.auth.auth_mapping(current_user.username)
    except ArboristError as e:
        # Arborist errored, or this user is unknown to Arborist
        logger.warn(
            "Unable to retrieve auth mapping for user `{}`: {}".format(
                current_user.username, e
            )
        )
        mapping = {}

    with flask.current_app.db.session_scope():
        access_resources = [
            node
            for resource_path, permissions in mapping.items()
            for node in resource_path_to_project_ids(resource_path)
            # ignore resource if no peregrine read access:
            if any(
                permission.get("service") in ["*", "peregrine"]
                and permission.get("method") in ["*", "read"]
                for permission in permissions
            )
        ]

        sorted_resources = sorted(access_resources, key=itemgetter('project_id'))
        read_access_resources = {key:[item["node_id"] for item in list(group)] for key, group in itertools.groupby(sorted_resources, key=lambda x:x['project_id'])}
    
    # return dictionary of resources with read permissions
    return read_access_resources
