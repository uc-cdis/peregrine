import json

import flask
import pytest
from datamodelutils import models
#from datamodelutils.models.submission import TransactionLog
from tests.graphql import utils

from tests.graphql.test_graphql import (
    put_cgci,
    post_example_entities_together,
)

path = '/v0/submission/graphql'

@pytest.fixture
def graphql_client(client, submitter):
    def execute(query, variables={}):
        return client.post(path, headers=submitter, data=json.dumps({
            'query': query,
            'variables': variables,
        }))
    return execute


@pytest.fixture
def cgci_blgsp(client, admin):
    """
    TODO: Docstring for put_cgci_blgsp.
    """
    put_cgci(client, auth=admin)
    path = '/v0/submission/CGCI/'
    data = json.dumps({
        "type": "project",
        "code": "BLGSP",
        "dbgap_accession_number": 'phs000527',
        "name": "Burkitt Lymphoma Genome Sequencing Project",
        "state": "open"
    })
    r = client.put(path, headers=admin, data=data)
    assert r.status_code == 200, r.data
    del flask.g.user
    return r


@pytest.fixture
def put_tcga_brca(admin, client):
    data = json.dumps({
        'name': 'TCGA', 'type': 'program',
        'dbgap_accession_number': 'phs000178'
    })
    r = client.put('/v0/submission/', headers=admin, data=data)
    assert r.status_code == 200, r.data
    data = json.dumps({
        "type": "project",
        "code": "BRCA",
        "name": "TEST",
        "dbgap_accession_number": "phs000178",
        "state": "open"
    })
    r = client.put('/v0/submission/TCGA/', headers=admin, data=data)
    assert r.status_code == 200, r.data
    return r


@pytest.fixture
def mock_tx_log(pg_driver_clean):
    utils.reset_transactions(pg_driver_clean)
    with pg_driver_clean.session_scope() as session:
        return session.merge(models.submission.TransactionLog(
            is_dry_run=True,
            program='CGCI',
            project='BLGSP',
            role='create',
            state='SUCCEEDED',
            committed_by=12345,
            closed=False,
        ))


@pytest.fixture
def populated_blgsp(client, submitter, pg_driver_clean):
    utils.reset_transactions(pg_driver_clean)
    post_example_entities_together(client, pg_driver_clean, submitter)


@pytest.fixture
def failed_deletion_transaction(client, submitter, pg_driver_clean, populated_blgsp):
    with pg_driver_clean.session_scope():
        node_id = pg_driver_clean.nodes(models.Sample).first().node_id
    delete_path = '/v0/submission/CGCI/BLGSP/entities/{}'.format(node_id)
    r = client.delete(
        delete_path,
        headers=submitter)
    assert r.status_code == 400, r.data
    return str(r.json['transaction_id'])


@pytest.fixture
def failed_upload_transaction(client, submitter, pg_driver_clean):
    put_path = '/v0/submission/CGCI/BLGSP/'
    r = client.put(
        put_path,
        data=json.dumps({
            'type': 'sample',
            'cases': [{'id': 'no idea'}],
            'sample_type': 'teapot',
            'how_heavy': 'no',
        }),
        headers=submitter)
    assert r.status_code == 400, r.data
    return str(r.json['transaction_id'])
