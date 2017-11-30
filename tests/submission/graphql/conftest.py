import json

import flask
from gdcdatamodel import models
from gdcdatamodel.models.submission import TransactionLog
import pytest

from tests.submission import utils
from tests.submission.test_endpoints import (
    put_cgci,
    post_example_entities_together,
)
from tests.auth_mock import Config as auth_conf


SUBMITTER_HEADERS = {"X-Auth-Token": auth_conf.SUBMITTER_ADMIN_TOKEN}
ADMIN_HEADERS = {"X-Auth-Token": auth_conf.ADMIN_TOKEN}


path = '/v0/submission/graphql'


@pytest.fixture
def graphql_client(client, submitter):
    def execute(query, variables=None):
        if variables is None:
            variables = {}
        data = json.dumps({'query': query, 'variables': variables})
        return client.post(path, headers=submitter(path, 'post'), data=data)
    return execute


@pytest.fixture
def cgci_blgsp(client, submitter):
    """
    TODO: Docstring for put_cgci_blgsp.
    """
    role = 'admin'
    put_cgci(client, auth=submitter, role=role)
    path = '/v0/submission/CGCI/'
    headers = submitter(path, 'put', role)
    data = json.dumps({
        "type": "project",
        "code": "BLGSP",
        "dbgap_accession_number": 'phs000527',
        "name": "Burkitt Lymphoma Genome Sequencing Project",
        "state": "open"
    })
    r = client.put(path, headers=headers, data=data)
    assert r.status_code == 200, r.data
    del flask.g.user
    return r


@pytest.fixture
def put_tcga_brca():
    def wrapped_function(client, submitter=None):
        headers = submitter('/v0/submission/', 'put', 'admin')
        data = json.dumps({
            'name': 'TCGA', 'type': 'program',
            'dbgap_accession_number': 'phs000178'
        })
        r = client.put('/v0/submission/', headers=headers, data=data)
        assert r.status_code == 200, r.data
        headers = submitter('/v0/submission/TCGA/', 'put', 'admin')
        data = json.dumps({
            "type": "project",
            "code": "BRCA",
            "name": "TEST",
            "dbgap_accession_number": "phs000178",
            "state": "open"
        })
        r = client.put('/v0/submission/TCGA/', headers=headers, data=data)
        assert r.status_code == 200, r.data
        del flask.g.user
        return r
    return wrapped_function


@pytest.fixture
def mock_tx_log(pg_driver):
    utils.reset_transactions(pg_driver)
    with pg_driver.session_scope() as session:
        return session.merge(TransactionLog(
            is_dry_run=True,
            program='CGCI',
            project='BLGSP',
            role='create',
            state='SUCCEEDED',
            committed_by=12345,
            closed=False,
        ))


@pytest.fixture
def populated_blgsp(client, submitter, pg_driver, cgci_blgsp):
    post_example_entities_together(client, pg_driver, submitter)


@pytest.fixture
def failed_deletion_transaction(client, submitter, pg_driver, populated_blgsp):
    with pg_driver.session_scope():
        node_id = pg_driver.nodes(models.Sample).first().node_id
    r = client.delete(
        '/v0/submission/CGCI/BLGSP/entities/{}'.format(node_id),
        headers=submitter(path, 'delete')
    )
    assert r.status_code == 400, r.data
    return str(r.json['transaction_id'])


@pytest.fixture
def failed_upload_transaction(client, submitter, pg_driver):
    data = json.dumps({
        'type': 'sample',
        'cases': [{'id': 'no idea'}],
        'sample_type': 'teapot',
        'how_heavy': 'no',
    }),
    r = client.put(
        '/v0/submission/CGCI/BLGSP/',
        headers=submitter(path, 'put'),
        data=data,
    )
    assert r.status_code == 400, r.data
    return str(r.json['transaction_id'])
