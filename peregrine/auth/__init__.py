"""
The authutils to use will depend on the downstream dependency
and how it installs authutils.

eg:
``pip install git+https://git@github.com/NCI-GDC/authutils.git@1.2.3#egg=authutils``
or
``pip install git+https://git@github.com/uc-cdis/authutils.git@1.2.3#egg=authutils``
"""

# import modules from authutils
from authutils import dbgap
from authutils import ROLES, AuthError
from authutils.token import current_token
from authutils.user import current_user
import flask

from peregrine import models


def get_program_project_roles(program, project):
    """
    Args:
        program (str): program name (NOT id)
        project (str): project name (NOT id)

    Return:
        Set[str]: roles
    """
    # Get the actual CurrentUser instance behind the werkzeug proxy so we can
    # slap this attributes on it
    user = current_user._get_current_object()

    if not hasattr(user, 'sheepdog_roles'):
        user.sheepdog_roles = dict()

    if not (program, project) in user.sheepdog_roles:
        user_roles = set()
        with flask.current_app.db.session_scope():
            if program:
                program_node = (
                    flask.current_app.db
                    .nodes(models.Program)
                    .props(name=program)
                    .scalar()
                )
                if program_node:
                    program_id = program_node.dbgap_accession_number
                    roles = user.projects.get(program_id, set())
                    user_roles.update(set(roles))
            if project:
                project_node = (
                    flask.current_app.db
                    .nodes(models.Project)
                    .props(code=project)
                    .scalar()
                )
                if project_node:
                    project_id = project_node.dbgap_accession_number
                    roles = user.projects.get(project_id, set())
                    user_roles.update(set(roles))
        user.sheepdog_roles[(program, project)] = user_roles

    return user.sheepdog_roles[(program, project)]
