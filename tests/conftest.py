import os
import sys

from indexclient.client import IndexClient
from multiprocessing import Process
from psqlgraph import PsqlGraphDriver
import json
import pytest
import requests
import sheepdog

import peregrine
from peregrine.api import app as _app, app_init
from peregrine.auth import ROLES
import utils

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, here)


@pytest.fixture(scope='session')
def pg_config():
    return dict(
        host='localhost',
        user='test',
        password='test',
        database='automated_test',
    )


@pytest.fixture(scope='session')
def app(request):

    _app.config.from_object("peregrine.test_settings")
    app_init(_app)
    
    sheepdog_blueprint = sheepdog.blueprint.create_blueprint('submission')
    _app.register_blueprint(sheepdog_blueprint, url_prefix='/v0/submission')

    _app.logger.info('Initializing IndexClient')
    _app.index_client = IndexClient(
        _app.config['INDEX_CLIENT']['host'],
        version=_app.config['INDEX_CLIENT']['version'],
        auth=_app.config['INDEX_CLIENT']['auth'])
    try:
        _app.logger.info('Initializing Auth driver')
    except Exception:
        _app.logger.exception("Couldn't initialize auth, continuing anyway")


    _app.logger.setLevel(os.environ.get("GDC_LOG_LEVEL", "WARNING"))
    _app.jwt_public_keys = {_app.config['USER_API']: {
        'key-test': utils.read_file('resources/keys/test_public_key.pem')
    }}
    return _app


@pytest.fixture
def pg_driver_clean(request, pg_driver):
    from datamodelutils.models import Edge, Node

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

    tearDown() #cleanup potential last test data
    request.addfinalizer(tearDown)
    return pg_driver


@pytest.fixture(scope="session")
def pg_driver(request):
    pg_driver = PsqlGraphDriver(**pg_config())

    def closeConnection():
        pg_driver.engine.dispose()

    request.addfinalizer(closeConnection)
    return pg_driver


@pytest.fixture(scope='session')
def encoded_jwt(app):

    def encoded_jwt_function(private_key, user):
        """
        Return an example JWT containing the claims and encoded with the private
        key.

        Args:
            private_key (str): private key
            user (generic User object): user object

        Return:
            str: JWT containing claims encoded with private key
        """
        kid = peregrine.test_settings.JWT_KEYPAIR_FILES.keys()[0]
        scopes = ['openid']
        token = utils.generate_signed_access_token(
            kid, private_key, user, 3600, scopes, forced_exp_time=None,
            iss=app.config['USER_API'],
        )
        return token.token

    return encoded_jwt_function

@pytest.fixture(scope='session')
def random_user(encoded_jwt):
    private_key = utils.read_file('resources/keys/test_private_key.pem')
    # set up a fake User object which has all the attributes needed
    # to generate a token
    project_ids = []
    user_properties = {
        'id': 2,
        'username': 'random_user',
        'is_admin': False,
        'project_access': {project: ROLES.values() for project in project_ids},
        'policies': [],
        'google_proxy_group_id': None,
    }
    user = type('User', (object,), user_properties)
    token = encoded_jwt(private_key, user)
    return {'Authorization': 'bearer ' + token}


@pytest.fixture(scope='session')
def submitter(encoded_jwt):
    private_key = utils.read_file('resources/keys/test_private_key.pem')
    # set up a fake User object which has all the attributes needed
    # to generate a token
    project_ids = ['phs000218', 'phs000235', 'phs000178']
    user_properties = {
        'id': 1,
        'username': 'submitter',
        'is_admin': False,
        'project_access': {project: ROLES.values() for project in project_ids},
        'policies': [],
        'google_proxy_group_id': None,
    }
    user = type('User', (object,), user_properties)
    token = encoded_jwt(private_key, user)
    return {'Authorization': 'bearer ' + token}


@pytest.fixture(scope='session')
def admin(encoded_jwt):
    private_key = utils.read_file('resources/keys/test_private_key.pem')
    project_ids = ['phs000218', 'phs000235', 'phs000178']
    user_properties = {
        'id': 2,
        'username': 'admin',
        'is_admin': True,
        'project_access': {project: ROLES.values() for project in project_ids},
        'policies': [],
        'google_proxy_group_id': None,
    }
    user = type('User', (object,), user_properties)
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


@pytest.fixture
def public_dataset_api(request):
    os.environ["PUBLIC_DATASETS"] = "true"
    def tearDown():
        os.environ["PUBLIC_DATASETS"] = "false"
    request.addfinalizer(tearDown)
