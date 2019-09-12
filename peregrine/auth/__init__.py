"""
The authutils to use will depend on the downstream dependency
and how it installs authutils.

eg:
``pip install git+https://git@github.com/NCI-GDC/authutils.git@1.2.3#egg=authutils``
or
``pip install git+https://git@github.com/uc-cdis/authutils.git@1.2.3#egg=authutils``
"""

from authutils import ROLES # TODO check if uses of this should be replaced
from authutils.user import current_user
from cdislogging import get_logger
from datamodelutils import models
from gen3authz.client.arborist.errors import ArboristError
import flask

from peregrine.errors import AuthNError


logger = get_logger(__name__)


def resource_path_to_project_ids(resource_path):
    parts = resource_path.strip('/').split('/')
    if resource_path == "/" or (parts and parts[0] == "programs"):

        if len(parts) > 4 or (len(parts) > 2 and parts[2] != "projects"):
            logger.warn(
                "ignoring resource path {} because peregrine cannot handle a permission more granular than program/project level".format(resource_path)
            )
            return []

        #  "/" or "/programs": access to all programs
        if len(parts) == 1:
            programs = (
                flask.current_app.db
                .nodes(models.Program)
                .all()
            )
            return [
                program.name + '-' + project.code
                for program in programs
                for project in program.projects
            ]

        #  "/programs/[...]" or "/programs/[...]/projects/":
        # access to all projects of a program
        if len(parts) < 4:
            program_name = parts[1]
            program = (
                flask.current_app.db
                .nodes(models.Program)
                .props(name=program_name)
                .first()
            )
            if not program:
                logger.warn(
                    "program {} in resource path {} does not exist".format(program_name, resource_path)
                )
                return []
            return [
                program.name + '-' + project.code
                for project in program.projects
            ]

        #  "/programs/[...]/projects/[...]": access to a specific project
        if parts[2] == "projects":
            project_code = parts[3]
            project = (
                flask.current_app.db
                .nodes(models.Project)
                .props(code=project_code)
                .first()
            )
            if not project:
                logger.warn(
                    "project {} in resource path {} does not exist".format(project_code, resource_path)
                )
                return []
            return [
                program.name + '-' + project.code
                for program in project.programs
            ]

    return []


def get_read_access_projects():
    """
    Get all resources the user has read access to and parses the Arborist resource paths into a program.name and a project.code.
    """
    try:
        mapping = flask.current_app.auth.auth_mapping(current_user.username)
    except ArboristError as e:
        raise AuthNError("Unable to retrieve auth mapping: {}".format(e))

    with flask.current_app.db.session_scope():
        read_access_projects = [
            project_id
            for resource_path, permissions in mapping.items()
            for project_id in resource_path_to_project_ids(resource_path)
            # ignore resource if no peregrine read access:
            if any(permission.get("service") in ["*", "peregrine"] for permission in permissions)
            if any(permission.get("method") == "read" for permission in permissions)
        ]

    # return unique project_ids
    return list(set(read_access_projects))
