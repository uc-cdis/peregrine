from collections import defaultdict
import functools
import json

import cdis_oauth2client
from cdis_oauth2client import OAuth2Error
from cdispyutils.hmac4 import verify_hmac
from cdispyutils.hmac4.hmac4_auth_utils import HMAC4Error
from cryptography.fernet import Fernet
import flask
from flask import request, g, session
from flask import current_app as app
from flask_sqlalchemy_session import current_session
from peregrine.errors import InternalError, AuthError, NotFoundError, InvalidTokenError
from gdcdatamodel.models import Project, Program
from gdcdictionary import gdcdictionary
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
import userdatamodel
from userdatamodel.user import User, AccessPrivilege, HMACKeyPair


SERVICE = 'submission'
roles = dict(
    ADMIN='admin',
    CREATE='create',
    DELETE='delete',
    DOWNLOAD='download',
    GENERAL='_member_',
    READ='read',
    RELEASE='release',
    UPDATE='update',
)

MEMBER_DOWNLOADABLE_STATES = ["submitted", "processing", "processed"]
SUBMITTER_DOWNLOADABLE_STATES = [
    "uploaded", "validating", "validated",
    "error", "submitted", "processing", "processed"]


def get_error_msg(user_name, roles, project):
    role_names = [{
        '_member_': 'read (_member_)'
    }.get(role, role) for role in roles]
    return ("User {} doesn't have {} access in {}"
            .format(user_name, ' or '.join(role_names), project))


class AuthDriver(object):
    """
    Responsible for checking user's access permission and getting user
    information from the token passed to peregrine.
    """

    def __init__(self, auth_conf, internal_auth):
        return

    def get_user_projects(self, user):
        if not user:
            raise AuthError('Please authenticate as a user')
        if not g.user:
            g.user = FederatedUser(user)
        results = (
            current_session.query(
                userdatamodel.user.Project.auth_id, AccessPrivilege
            )
            .join(AccessPrivilege.project)
            .filter(AccessPrivilege.user_id == g.user.id)
            .all()
        )
        return_res = {}
        if not results:
            raise AuthError("No project access")
        for item in results:
            dbgap_no, user_access = item
            return_res[dbgap_no] = user_access.privilege
        return return_res

    def check_nodes(self, nodes):
        """
        Check if user have access to all of the dids, return 403 if user
        doesn't have access on any of the file, 404 if any of the file
        is not in psqlgraph, 200 if user can access all dids
        """
        for node in nodes:
            node_acl = node.acl
            if node_acl == ['open']:
                continue
            elif node_acl == []:
                raise AuthError(
                    'Requested file %s does not allow read access' %
                    node.node_id, code=403)
            else:
                if g.user.token is None:
                    raise AuthError('Please specify a X-Auth-Token')
                else:
                    user_acl = (
                        g.user.get_phs_ids(self.get_role(node)))
                    if not(set(node_acl) & set(user_acl)):
                        raise AuthError(
                            "You don't have access to the data")
        return 200

    def get_role(self, node):
        state = node.state
        file_state = node.file_state
        # if state is live, it's a processed legacy file
        if state == 'live':
            return roles['GENERAL']
        elif node.project_id:
            with app.db.session_scope():
                program, project = node.project_id.split('-', 1)
                try:
                    project = (app.db.nodes(Project)
                               .props(code=project)
                               .path('programs')
                               .props(name=program)
                               .one())
                except MultipleResultsFound:
                    raise InternalError(
                        "Multiple results found for file {}'s project {}"
                        .format(node.node_id, node.project_id))
                except NoResultFound:
                    raise InternalError(
                        "No results found for file {}'s project {}"
                        .format(node.node_id, node.project_id))

                # for general users with '_member_' role, allow
                # download if project is released and file is submitted
                # and file_state is at or after "submitted"
                allow_general_access = (
                    project.released is True and
                    state == 'submitted' and
                    file_state in MEMBER_DOWNLOADABLE_STATES)

                # for submitters with "download" role, allow download
                # if file_state is at or after "uploaded"
                allow_submitter_access = file_state in SUBMITTER_DOWNLOADABLE_STATES

                if allow_general_access:
                    return roles['GENERAL']

                elif allow_submitter_access:
                    return roles['DOWNLOAD']

                else:
                    raise NotFoundError(
                        "Data with id {} not found"
                        .format(node.node_id))

        else:
            # node does not have project_id and is not live
            raise NotFoundError("Data with id {} not found".format(node.node_id))

    def filter_nodes(self, nodes):
        """
        Filters nodes that are not authorized for the user.
        """
        for node in nodes:
            if node.acl == ['open']:
                yield node
            else:
                try:
                    user_acl = set(g.user.get_phs_ids(self.get_role(node)))
                    if set(node.acl) & user_acl:
                        yield node
                except:
                    pass

    def has_protected(self, nodes):
        """
        Checks if any of the nodes are protected.
        """
        return any(map(lambda n: n.acl != ['open'], nodes))


class FederatedUser(object):

    def __init__(self, hmac_keypair=None, user = None):
        self._phsids = {}
        if hmac_keypair is None:
            self.hmac_keypair = None
            self.user = user
            self.username = user.username
            self.id = user.id
        else:
            self.hmac_keypair = hmac_keypair
            self.user = hmac_keypair.user
            self.username = hmac_keypair.user.username
            self.id = hmac_keypair.user.id
        self.project_ids = {}
        self._roles = defaultdict(set)
        self.role = None
        self.mapping = {}

    def get_projects_mapping(self, phsid):
        if phsid in self.mapping:
            return self.mapping[phsid]
        with app.db.session_scope():
            project = app.db.nodes(Project).props(
                dbgap_accession_number=phsid).first()
            self.mapping[phsid] = []
            if project:
                self.mapping[phsid] = [project.programs[0].name + '-' + project.code]
            else:
                program = app.db.nodes(Program).props(
                    dbgap_accession_number=phsid).first()
                if program:
                    self.mapping[phsid] = [
                        program.name + '-' + node.code for node in program.projects]
        return self.mapping[phsid]

    def __str__(self):
        str_out = {
            'id': self.user.id,
            'access_key': self.hmac_keypair.access_key if self.hmac_keypair else None,
            'username': self.user.username,
            'is_admin': self.user.is_admin
        }
        return json.dumps(str_out)

    def logged_in(self):
        if not self.user.username:
            raise InvalidTokenError()

    @property
    def roles(self):
        if not self._roles:
            self.set_roles()
        return self._roles

    @property
    def phsids(self):
        if not self._phsids:
            self.set_phs_ids()
        return self._phsids

    def set_roles(self):
        for phsid, roles in self.phsids.iteritems():
            for project in self.get_projects_mapping(phsid):
                for role in roles:
                    self._roles[project].add(role)

    def set_phs_ids(self):
        self._phsids = app.auth.get_user_projects(self.user)
        return self._phsids

    def get_role_by_dbgap(self, dbgap_no):
        project = current_session.query(userdatamodel.user.Project)\
                .filter(userdatamodel.user.Project.auth_id == dbgap_no)\
                .first()
        if not project:
            raise InternalError("Don't have project with {0}".format(dbgap_no))
        roles = current_session.query(AccessPrivilege)\
            .filter(AccessPrivilege.user_id == g.user.id)\
            .filter(AccessPrivilege.project_id == project.id)\
            .first()
        if not roles:
            raise AuthError("You don't have access to the data")
        return roles

    def fetch_project_ids(self, role='_member_'):
        result = []
        for phsid, roles in self.phsids.iteritems():
            if role in roles:
                result += self.get_projects_mapping(phsid)
        return result

    def get_project_ids(self, role='_member_'):
        self.logged_in()
        if role not in self.project_ids:
            self.project_ids[role] = self.fetch_project_ids(role)
        return self.project_ids[role]


def get_secret_key_and_user(access_key):
    hmac_keypair = (
        current_session.query(HMACKeyPair)
        .filter(HMACKeyPair.access_key == access_key)
        .first()
    )
    if not hmac_keypair:
        raise AuthError("Access key doesn't exist.")
    g.user = g.get('user', FederatedUser(hmac_keypair=hmac_keypair))
    key = Fernet(bytes(app.config['HMAC_ENCRYPTION_KEY']))
    return key.decrypt(bytes(hmac_keypair.secret_key))


def check_user_credential():
    try:
        username = cdis_oauth2client.get_username()
        get_user(username)
    except OAuth2Error:
        try:
            verify_hmac(
                request, SERVICE, get_secret_key_and_user
            )
        except HMAC4Error as e:
            app.logger.exception("Fail to verify hmac")
            raise AuthError(e.message)


def get_user(username):
    user = (
        current_session.query(User)
        .filter(User.username == username)
        .first()
    )
    if not user:
        raise AuthError("User doesn't exist.")
    g.user = g.get('user', FederatedUser(user=user))


def set_g_user(func):
    """Wrapper for flask blueprint route which sets the global user"""
    @functools.wraps(func)
    def f(*args, **kwargs):
        check_user_credential()
        return func(*args, **kwargs)
    return f


def require_auth():
    """checks if this is an authenticated request"""
    check_user_credential()
    if not g.user:
        raise AuthError("This endpoints require authentication")


def authorize_for_project(*roles):
    """
    Wrapper for flask blueprint route which does the following:

    1. Allows access to the handler iff the user has at least one of
       the roles requested on the given project
    2. Sets the global flask, variable `g.user` to be a `FederatedUser`
    """

    def wrapper(func):
        @functools.wraps(func)
        def authorize_and_call(program, project, *args, **kwargs):
            project_id = '{}-{}'.format(program, project)
            check_user_credential()
            # Get intersection of user's roles and requested roles
            if not set(g.user.roles[project_id]) & set(roles):
                raise AuthError(
                    get_error_msg(g.user.username, roles, project_id))
            return func(program, project, *args, **kwargs)
        return authorize_and_call
    return wrapper


def parse_service(req):
    return "submission"  # TODO: list all provided service from API
