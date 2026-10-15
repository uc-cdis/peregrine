"""
The authutils to use will depend on the downstream dependency
and how it installs authutils.

eg:
``pip install git+https://git@github.com/NCI-GDC/authutils.git@1.2.3#egg=authutils``
or
``pip install git+https://git@github.com/uc-cdis/authutils.git@1.2.3#egg=authutils``
"""

from authutils.user import current_user
from authutils.token.validate import current_token
from cdislogging import get_logger
from datamodelutils import models
from gen3authz.client.arborist.errors import ArboristError
import flask

logger = get_logger(__name__)


def resource_path_to_project_ids(resource_path):
    parts = resource_path.strip("/").split("/")

    # resource path ignored by peregrine
    if resource_path != "/" and parts[0] != "programs":
        return []

    if len(parts) > 4 or (len(parts) > 2 and parts[2] != "projects"):
        logger.warn(
            "ignoring resource path {} because peregrine cannot handle a permission more granular than program/project level".format(
                resource_path
            )
        )
        return []

    # "/" or "/programs": access to all programs
    if len(parts) == 1:
        programs = flask.current_app.db.nodes(models.Program).all()
        return [
            program.name + "-" + project.code
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
        return [program.name + "-" + project.code for project in program.projects]

    # "/programs/[...]/projects/[...]": access to a specific project
    # here, len(parts) == 4 and parts[2] == "projects"
    project_code = parts[3]
    project = (
        flask.current_app.db.nodes(models.Project).props(code=project_code).first()
    )
    if not project:
        logger.debug(
            "project {} in resource path {} does not exist".format(
                project_code, resource_path
            )
        )
        return []
    return [program.name + "-" + project.code for program in project.programs]


def get_read_access_projects():
    """
    Get all resources the caller has read access to and parses the Arborist resource paths into a program.name and a project.code.

    Supports both user tokens and ``client_credentials`` tokens. User tokens
    carry a username (``context.user.name``) and are resolved against Arborist
    by username. ``client_credentials`` tokens have no user identity but carry
    the client id in the ``azp`` claim; they are resolved against Arborist by
    client id.
    """
    username = current_user.username
    # client_credentials tokens have no user identity but carry the client id
    # in the `azp` claim.
    client_id = (current_token or {}).get("azp")

    try:
        if not username and client_id:
            mapping = flask.current_app.auth.client_auth_mapping(client_id)
        else:
            mapping = flask.current_app.auth.auth_mapping(username)
    except ArboristError as e:
        # Arborist errored, or this caller is unknown to Arborist
        caller = (
            "user `{}`".format(username)
            if username
            else "client `{}`".format(client_id)
        )
        logger.warning("Unable to retrieve auth mapping for {}: {}".format(caller, e))
        mapping = {}

    with flask.current_app.db.session_scope():
        read_access_projects = [
            project_id
            for resource_path, permissions in mapping.items()
            for project_id in resource_path_to_project_ids(resource_path)
            # ignore resource if no peregrine read access:
            if any(
                permission.get("service") in ["*", "peregrine"]
                and permission.get("method") in ["*", "read"]
                for permission in permissions
            )
        ]

    # return unique project_ids
    return list(set(read_access_projects))
