from auth_mock import Config as conf
from peregrine.errors import AuthError
from peregrine.auth import FederatedUser
import pytest
from gdcdatamodel.models import *
from uuid import uuid4
from auth_mock import mock

def setup_projects(graph):
    with graph.session_scope() as session:
        program = Program(
            str(uuid4()),
            name='TCGA',
            dbgap_accession_number='phs000178')
        project = Project(
            str(uuid4()), code='LAML')
        session.add(program)
        project.programs.append(program)
        session.add(project)
        program2 = Program(
            str(uuid4()),
            name='CGCI',
            dbgap_accession_number='phs000235')
        project2 = Project(
            str(uuid4()), code='BLGSP', dbgap_accession_number='phs000527')
        project2.programs.append(program2)
        session.add(project2)
        session.add(program2)
        program3 = Program(
            str(uuid4()),
            name='TARGET',
            dbgap_accession_number='phs000218')
        project3 = Project(
            str(uuid4()), code='MDLS', dbgap_accession_number='phs000469')
        project3.programs.append(program3)
        session.add(project3)
        session.add(program3)


def test_get_user_projects(auth, client):
    assert auth.get_user_projects(conf.SUBMITTER_MEMBER_TOKEN)\
        == {'phs000178': ['_member_'],
            'phs000235': ['_member_'],
            'phs000218': ['_member_']}


def test_user_role_for_invalid_roles(auth, client):
    with pytest.raises(AuthError):
        auth.get_user_projects('test')


def test_admin_token(auth, client):
    assert auth.is_admin_token(conf.ADMIN_TOKEN)


def test_invalid_admin_token(auth, client):
    assert not auth.is_admin_token(conf.SUBMITTER_TOKEN_A)


def test_federated_user_get_roles(app, auth, client):
    setup_projects(app.db)
    with mock():
        user = FederatedUser(conf.SUBMITTER_TOKEN_A)
    result = user.roles
    assert len(result['TCGA-LAML']) == 8
    assert len(result['CGCI-BLGSP']) == 0
    assert len(result['TARGET-MDLS']) == 0


def test_federated_user_get_projects(app, auth, client):
    setup_projects(app.db)
    with mock():
        user = FederatedUser(conf.SUBMITTER_TOKEN_B)
    projects = user.get_project_ids('_member_')
    assert 'CGCI-BLGSP' in projects
    assert 'TARGET-MDLS' not in projects
    assert 'TCGA-LAML' not in projects
