
from cdispyutils.hmac4 import get_auth
import requests
from flask.testing import make_test_environ_builder
from cdispyutils.hmac4.hmac4_auth_utils import get_request_date
import datetime
import sys
from peregrine.auth import roles
import os
from signpost import Signpost
from multiprocessing import Process
from gdcdatamodel.models import Edge, Node
from peregrine.auth import AuthDriver
from psqlgraph import PsqlGraphDriver
import pytest
import time
from tests.api import app as _app, app_init
from mock import patch
from elasticsearch import Elasticsearch
from peregrine.test_settings import PSQL_USER_DB_CONNECTION
from peregrine.test_settings import Fernet, HMAC_ENCRYPTION_KEY
import peregrine.test_settings

from fence.jwt.token import generate_signed_access_token
from userdatamodel import models as usermd
from userdatamodel import Base as usermd_base
from userdatamodel.driver import SQLAlchemyDriver
from cdisutilstest.code.storage_client_mock import get_client
import json
from peregrine.config import LEGACY_MODE

#from sheepdog_api import sheepdog_blueprint
import gdcdictionary
import gdcdatamodel

import utils

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, here)


class UserapiTestSettings(object):
    from boto.s3.connection import OrdinaryCallingFormat
    MOCK_AUTH = True
    MOCK_STORAGE = True
    SHIBBOLETH_HEADER = ''
    DB = 'postgresql://postgres@localhost:5432/test_userapi'
    STORAGE_CREDENTIALS = {
        "cleversafe": {
            'aws_access_key_id': '',
            'aws_secret_access_key': '',
            'host': 'somemanager.osdc.io',
            'public_host': 'someobjstore.datacommons.io',
            'port': 443,
            'is_secure': True,
            'username': 'someone',
            'password': 'somepass',
            "calling_format": OrdinaryCallingFormat(),
            "is_mocked": True
        }
    }
    CEPH = {
        'aws_access_key_id': '',
        'aws_secret_access_key': '',
        'host': '',
        'port': 443,
        'is_secure': True}
    AWS = {
        'aws_access_key_id': '',
        'aws_secret_access_key': '',
    }

    APPLICATION_ROOT = '/'
    DEBUG = True
    HOST_NAME = ''
    SHIBBOLETH_HEADER = 'persistent_id'
    SSO_URL = ''
    SINGLE_LOGOUT = ''

    LOGOUT = ""
    BIONIMBUS_ACCOUNT_ID = -1
    ENABLE_CSRF_PROTECTION = False


@pytest.fixture(scope='session')
def pg_config():
    return dict(
        host='localhost',
        user='test',
        password='test',
        database='automated_test',
    )


def wait_for_signpost_alive(port):
    url = 'http://localhost:{}'.format(port)
    try:
        requests.get(url)
    except requests.ConnectionError:
        return wait_for_signpost_alive(port)
    else:
        return


def wait_for_signpost_not_alive(port):
    url = 'http://localhost:{}'.format(port)
    try:
        requests.get(url)
    except requests.ConnectionError:
        return
    else:
        return wait_for_signpost_not_alive(port)


def run_signpost(port):
    Signpost({"driver": "inmemory", "layers": ["validator"]}).run(
        host="localhost", port=port, debug=False)

@pytest.fixture(scope="session")
def start_signpost(request):
    port = 8000
    signpost = Process(target=run_signpost, args=[port])
    signpost.start()
    wait_for_signpost_alive(port)

    def teardown():
        signpost.terminate()
        wait_for_signpost_not_alive(port)

    request.addfinalizer(teardown)


@pytest.fixture(scope='session')
def app(request, start_signpost):

    # import sheepdog
    # sheepdog_blueprint = sheepdog.blueprint.create_blueprint(
    #     gdcdictionary.gdcdictionary, gdcdatamodel.models
    # )


    _app.config.from_object("peregrine.test_settings")
    app_init(_app)
    #_app.register_blueprint(sheepdog_blueprint, url_prefix='/v0/submission')

    _app.logger.setLevel(os.environ.get("GDC_LOG_LEVEL", "WARNING"))
    _app.jwt_public_keys = {_app.config['USER_API']: {
            'key-test': utils.read_file('resources/keys/test_public_key.pem')
    }}
    return _app


@pytest.fixture
def pg_driver_clean(request, pg_driver):

    def tearDown():
        with pg_driver.engine.begin() as conn:
            for table in Node().get_subclass_table_names():
                if table != Node.__tablename__:
                    conn.execute('delete from {}'.format(table))
            for table in Edge().get_subclass_table_names():
                if table != Edge.__tablename__:
                    conn.execute('delete from {}'.format(table))
            conn.execute('delete from versioned_nodes')
            conn.execute('delete from _voided_nodes')
            conn.execute('delete from _voided_edges')
            conn.execute('delete from transaction_snapshots')
            conn.execute('delete from transaction_documents')
            conn.execute('delete from transaction_logs')
            user_teardown()

    tearDown() #cleanup potential last test data
    user_setup()
    request.addfinalizer(tearDown)
    return pg_driver

@pytest.fixture(scope="session")
def pg_driver(request):
    pg_driver = PsqlGraphDriver(**pg_config())

    def closeConnection():
        pg_driver.engine.dispose()

    request.addfinalizer(closeConnection)
    return pg_driver

def user_setup():
    key = Fernet(HMAC_ENCRYPTION_KEY)
    user_driver = SQLAlchemyDriver(PSQL_USER_DB_CONNECTION)
    with user_driver.session as s:
        for username in [
                'admin', 'unauthorized', 'submitter', 'member', 'test']:
            user = usermd.User(username=username, is_admin=(username=='admin'))
            keypair = usermd.HMACKeyPair(
                access_key=username + 'accesskey',
                secret_key=key.encrypt(username),
                expire=1000000,
                user=user)
            s.add(user)
            s.add(keypair)
        users = s.query(usermd.User).all()
        test_user = s.query(usermd.User).filter(
            usermd.User.username == 'test').first()
        test_user.is_admin =True
        projects = ['phs000218', 'phs000235', 'phs000178']
        admin = s.query(usermd.User).filter(
            usermd.User.username == 'admin').first()
        admin.is_admin = True
        user = s.query(usermd.User).filter(
            usermd.User.username == 'submitter').first()
        member = s.query(usermd.User).filter(
            usermd.User.username == 'member').first()
        for phsid in projects:
            p = usermd.Project(
                name=phsid, auth_id=phsid)
            ua = usermd.AccessPrivilege(
                user=user, project=p, privilege=roles.values())
            s.add(ua)
            ua = usermd.AccessPrivilege(
                user=member, project=p, privilege=['_member_'])
            s.add(ua)

    return user_driver


def user_teardown():
    user_driver = SQLAlchemyDriver(PSQL_USER_DB_CONNECTION)
    with user_driver.session as session:
        meta = usermd_base.metadata
        for table in reversed(meta.sorted_tables):
            session.execute(table.delete())


def encoded_jwt(private_key, user):
    """
    Return an example JWT containing the claims and encoded with the private
    key.

    Args:
        private_key (str): private key
        user (userdatamodel.models.User): user object

    Return:
        str: JWT containing claims encoded with private key
    """
    kid = peregrine.test_settings.JWT_KEYPAIR_FILES.keys()[0]
    scopes = ['openid']
    return generate_signed_access_token(
        kid, private_key, user, 3600, scopes, forced_exp_time=None)


@pytest.fixture()
def submitter(app, request, pg_driver_clean):
    private_key = utils.read_file('resources/keys/test_private_key.pem')

    user_driver = SQLAlchemyDriver(PSQL_USER_DB_CONNECTION)
    with user_driver.session as s:
        user = s.query(usermd.User).filter_by(username='submitter').first()
        token = encoded_jwt(private_key, user)
        return {'Authorization': 'bearer ' + token}


@pytest.fixture()
def admin(app, request, pg_driver_clean):
    private_key = utils.read_file('resources/keys/test_private_key.pem')

    user_driver = SQLAlchemyDriver(PSQL_USER_DB_CONNECTION)
    with user_driver.session as s:
        user = s.query(usermd.User).filter_by(username='admin').first()
        token = encoded_jwt(private_key, user)
        return {'Authorization': 'bearer ' + token}

@pytest.fixture(scope='session')
def es_setup(request):
    es = Elasticsearch(["localhost"], port=9200)

    def es_teardown():
        es.indices.delete(
            index=INDEX,
            ignore=404,  # ignores error if index doesn't exists
        )
    request.addfinalizer(es_teardown)

    es.indices.create(
        index=INDEX,
        body=mappings.index_settings(),
        ignore=400,  # ignores error if index already exists
    )

    es.indices.put_mapping(index=INDEX, doc_type="file", body=mappings.get_file_es_mapping())
    es.indices.put_mapping(index=INDEX, doc_type="project", body=mappings.get_project_es_mapping())
    es.indices.put_mapping(index=INDEX, doc_type="case", body=mappings.get_case_es_mapping())
    es.indices.put_mapping(index=INDEX, doc_type="annotation", body=mappings.get_annotation_es_mapping())

    json_data = open(os.path.join(os.path.dirname(__file__), 'data/projects.json'))
    data = json.load(json_data)
    for p in data["data"]["hits"]:
        es.index(index=INDEX, doc_type=project_model.doc_type, body=p)

    json_data = open(os.path.join(os.path.dirname(__file__), 'data/files.json'))
    data = json.load(json_data)
    for f in data["data"]["hits"]:
        es.index(index=INDEX, doc_type=f_model.doc_type, body=f)

    json_data = open(os.path.join(os.path.dirname(__file__), 'data/cases.json'))
    data = json.load(json_data)
    for pa in data["data"]["hits"]:
        es.index(index=INDEX, doc_type=case_model.doc_type, body=pa)

    json_data = open(os.path.join(os.path.dirname(__file__), 'data/annotations.json'))
    data = json.load(json_data)
    for a in data["data"]["hits"]:
        es.index(index=INDEX, doc_type=annotation_model.doc_type, body=a)

    es.indices.refresh(index=INDEX)

    json_data.close()
