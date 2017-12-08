import json

import pytest
from gdcdatamodel import models
from tests.submission.test_endpoints import (
    post_example_entities_together,
)

from peregrine.resources.submission import graphql
from tests.graphql import utils

path = '/v0/submission/graphql'


query_dry_run = """
    {
        total: _transaction_log_count
        is: _transaction_log_count(is_dry_run: true)
        isnt: _transaction_log_count(is_dry_run: false)
    }
"""
result_dry_run = {"data": {"total": 1, "is": 1, "isnt": 0}}

query_state = """
    {
        total: _transaction_log_count
        succeeded: _transaction_log_count(state: "SUCCEEDED")
        failed: _transaction_log_count(state: "FAILED")
    }
"""
result_state = {"data": {"total": 1, "succeeded": 1, "failed": 0}}

query_committed_by = """
    {
        total: _transaction_log_count
        right: _transaction_log_count(committed_by: 12345)
        wrong: _transaction_log_count(committed_by: 54321)
    }
"""
result_committed_by = {"data": {"total": 1, "right": 1, "wrong": 0}}

query_committable = """
    {
        total: _transaction_log_count
        committable: _transaction_log_count(committable: true)
        not_committable: _transaction_log_count(committable: false)
    }
"""
result_committable = {
    "data": {"total": 1, "committable": 0, "not_committable": 1}
}

query_async_fields = """
    {
        tx_log: transaction_log {
            is_dry_run, state, committed_by
        }
    }
"""
result_async_fields = json.loads(json.dumps({
    'data': {
        'tx_log': [{
            "is_dry_run": True,
            "state": "SUCCEEDED",
            "committed_by": '12345',
        }],
    }
}))


@pytest.mark.parametrize(
    'query, expected_json',
    [
        (query_dry_run, result_dry_run),
        (query_state, result_state),
        (query_committed_by, result_committed_by),
        (query_committable, result_committable),
        (query_async_fields, result_async_fields),
    ],
    ids=[
        'dry_run',
        'state',
        'committed_by',
        'committable',
        'async_fields',
    ]
)
def test_transaction_logs_queries(
        pg_driver, cgci_blgsp, mock_tx_log, graphql_client, query,
        expected_json):
    with pg_driver.session_scope() as session:
        session.query(models.submission.TransactionSnapshot).delete()
        session.query(models.submission.TransactionDocument).delete()
        session.query(models.submission.TransactionLog).delete()
        session.merge(models.submission.TransactionLog(
            is_dry_run=True,
            program='CGCI',
            project='BLGSP',
            role='create',
            state='SUCCEEDED',
            committed_by=12345,
            closed=False,
        ))
    assert graphql_client(query).json == expected_json


@pytest.mark.skip(reason='fails with AuthError in failed_deletion_transaction')
def test_transaction_logs_deletion(
        pg_driver, graphql_client, failed_deletion_transaction):
    query = """
    {
      transaction_log(id: %s) {
          id
          type
          documents {
          response {
            entities {
              unique_keys
              related_cases { submitter_id }
              errors {
                message
              }
            }
          }
        }
      }
    }
    """
    response = graphql_client(query % failed_deletion_transaction)
    expected_json = {
        "data": {
            "transaction_log": [{
                "documents": [{
                    "response": {
                        "entities": [{
                            'related_cases': [{
                                'submitter_id': 'BLGSP-71-06-00019'
                            }],
                            'unique_keys': json.dumps([{
                                "project_id": "CGCI-BLGSP",
                                "submitter_id": "BLGSP-71-06-00019s",
                            }]),
                            "errors": [{
                                "message": (
                                    'Unable to delete entity because 4 others'
                                    ' directly or indirectly depend on it. You'
                                    ' can only delete this entity by deleting'
                                    ' its dependents prior to, or during the'
                                    ' same transaction as this one.'
                                )
                            }]
                        }]
                    }
                }],
                "id": failed_deletion_transaction,
                "type": "delete"
            }]
        }
    }
    assert response.json == expected_json


#: Transaction log query that is representative of a query from the
#: submission API.
COMPREHENSIVE_TRANSACTION_LOG_QUERY = """
query TransactionDetailsQuery {
  item: transaction_log {
    id
    project_id
    type
    state
    committed_by
    submitter
    is_dry_run
    closed
    created_datetime
    documents {
      id
      name
      doc
      doc_size
      doc_format
      response_json
      response {
        message
        entities {
          id
          unique_keys
          action
          type
          related_cases {
            id
            submitter_id
          }
          errors {
            keys
            type
            message
            dependents {
              id
              type
            }
          }
        }
      }
    }
  }
}"""


@pytest.mark.skip(reason='fails with AuthError in failed_upload_transaction')
def test_transaction_log_comprehensive_query_failed_upload(
        pg_driver, graphql_client, cgci_blgsp, failed_upload_transaction):
    """Test a comprehensive transaction_log query for a failed upload"""
    response = graphql_client(COMPREHENSIVE_TRANSACTION_LOG_QUERY)
    assert response.status_code == 200, response.data
    assert 'errors' not in response.json, response.data


def test_transaction_log_comprehensive_query_upload(
        pg_driver, graphql_client, populated_blgsp):
    """Test a comprehensive transaction_log query for a successful upload"""
    response = graphql_client(COMPREHENSIVE_TRANSACTION_LOG_QUERY)
    assert response.status_code == 200, response.data
    assert 'errors' not in response.json, response.data


@pytest.mark.skip(reason='fails with AuthError in failed_deletion_transaction')
def test_transaction_log_comprehensive_query_failed_deletion(
        pg_driver, graphql_client, failed_deletion_transaction):
    """Test a comprehensive transaction_log query for a failed deletion"""
    response = graphql_client(COMPREHENSIVE_TRANSACTION_LOG_QUERY)
    assert response.status_code == 200, response.data
    assert 'errors' not in response.json, response.data


def test_transaction_logs(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    with pg_driver.session_scope():
        assert pg_driver.nodes(models.submission.TransactionLog).count() == 1


@pytest.mark.skip(reason='deprecated')
def test_transaction_log_related_cases(
        client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)

    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """
        query Test {
          a: transaction_log (first: 1) {
            type documents {response { entities {related_cases {
              id submitter_id
            }}}}}
        }"""}))
    assert r.status_code == 200
    print(r.data)
    related_case = (r.json['data']
                    ['a'][0]
                    ['documents'][0]
                    ['response']
                    ['entities'][1]
                    ['related_cases'][0])
    assert 'submitter_id' in related_case
    assert 'id' in related_case


@pytest.mark.skip(reason='deprecated')
def test_transaction_log_related_cases_filter(
        client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    data = json.dumps({
        'query': """
            {a: transaction_log (first: 1) { related_cases { id }}}
        """
    })
    r = client.post(path, headers=submitter(path, 'post'), data=data)
    assert r.status_code == 200
    print r.data
    case_id = r.json['data']['a'][0]['related_cases'][0]['id']
    data = json.dumps({
        'query': """
            query Test($caseId: String) {
                a: transaction_log (related_cases: [$caseId]) {
                    related_cases { id submitter_id }
                }
            }
        """,
        "variables": {"caseId": case_id},
    })
    r = client.post(path, headers=submitter(path, 'post'), data=data)
    assert r.status_code == 200
    print r.data
    related_case_doc = r.json['data']['a'][0]['related_cases'][0]
    assert related_case_doc['id'] == case_id
    assert related_case_doc['submitter_id']


def test_transaction_log_type(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{ a: transaction_log { role type }}"""}))
    print r.data
    type_ = graphql.transaction.TransactionLog.TYPE_MAP['create']
    assert r.json['data']['a'][0]['type'] == type_
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{
        a: transaction_log(type: "%s") { role type }
        }""" % type_}))
    print r.data
    assert r.json['data']['a']


def test_transaction_log_type_map():
    assert graphql.transaction.TransactionLog.TYPE_MAP == {
        "update": "upload",
        "create": "upload",
    }, (
        "The type map has changed.  This is external facing and should "
        "not be changed unless all clients are likewise updated."
    )


def test_transaction_log_entities(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{ log: transaction_log {
        doc: documents { resp: response { ent: entities { type }}}}}"""}))
    print r.data
    assert r.status_code == 200
    entities = r.json['data']['log'][0]['doc'][0]['resp']['ent']
    assert all(e['type'] for e in entities)


def test_transaction_log_entities_errors(
        client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    put_response = utils.put_entity_from_file(
        client, 'read_group_invalid.json', submitter=submitter, validate=False
    )
    transaction_id = put_response.json.get('transaction_id')
    query = """
    {{ log: transaction_log( id: {} ) {{
        doc: documents {{ resp: response {{ ent: entities {{
        err: errors {{ type keys message }} }} }} }} }} }}
    """
    query = query.format(transaction_id)
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': query
    }))
    assert r.status_code == 200
    error = r.json['data']['log'][0]['doc'][0]['resp']['ent'][0]['err'][0]
    assert all(key in error for key in ('type', 'keys', 'message'))


def test_transaction_log_documents(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{ log: transaction_log {
        doc: documents { doc_size name }}}"""}))
    print r.data
    doc = r.json['data']['log'][0]['doc'][0]
    assert doc['name'] is None
    assert isinstance(doc['doc_size'], int)


def test_transaction_logs_order_asc(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    with pg_driver.session_scope():
        assert pg_driver.nodes(models.submission.TransactionLog).count() == 1
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{
          a: transaction_log (order_by_asc: "id") {
            id
            project_id
            created_datetime
          }
        }"""}))
    print r.data
    _original = r.json['data']['a']
    _sorted = sorted(_original, cmp=(lambda a, b: cmp(a['id'], b['id'])))
    assert _original == _sorted, r.data


def test_transaction_logs_order_desc(client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    with pg_driver.session_scope():
        assert pg_driver.nodes(models.submission.TransactionLog).count() == 1
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{
          a: transaction_log (order_by_desc: "id") {
            id
            project_id
            created_datetime
          }
        }"""}))
    print r.data
    _original = r.json['data']['a']
    _sorted = sorted(_original, cmp=(lambda a, b: cmp(b['id'], a['id'])))
    assert _original == _sorted, r.data


def test_transaction_logs_quick_search(
        client, submitter, pg_driver, cgci_blgsp):
    utils.reset_transactions(pg_driver)
    post_example_entities_together(client, pg_driver, submitter)
    with pg_driver.session_scope():
        id_ = str(pg_driver.nodes(models.submission.TransactionLog).first().id)
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """{
          a: transaction_log (quick_search: "%s") { id }
          b: transaction_log (quick_search: %s)   { id }
          c: transaction_log (quick_search: "A") { id }
        }""" % (id_, id_)}))
    assert r.json == {
        'data': {
            'a': [{'id': id_}],
            'b': [{'id': id_}],
            'c': [],
        }
    }, r.data
