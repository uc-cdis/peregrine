import json
import os
import shutil

import pytest
from flask import g
from datamodelutils import models
from psqlgraph import Node

import peregrine
from tests.graphql import utils
from tests.graphql.utils import data_fnames

BLGSP_PATH = '/v0/submission/CGCI/BLGSP/'
BRCA_PATH = '/v0/submission/TCGA/BRCA/'

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')

path = '/v0/submission/graphql'
export_path = '/v0/submission/export'

# ======================================================================
# Fixtures

@pytest.fixture
def graphql_client(client, submitter):
    def execute(query, variables={}):
        return client.post(path, headers=submitter, data=json.dumps({
            'query': query,
            'variables': variables,
        }))
    return execute


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

# ======================================================================
# Tests

def post_example_entities_together(
        client, pg_driver_clean, submitter, data_fnames=data_fnames):
    path = BLGSP_PATH
    data = []
    for fname in data_fnames:
        with open(os.path.join(DATA_DIR, fname), 'r') as f:
            data.append(json.loads(f.read()))
    return client.post(path, headers=submitter, data=json.dumps(data))


def put_example_entities_together(client, pg_driver_clean, submitter):
    path = BLGSP_PATH
    data = []
    for fname in data_fnames:
        with open(os.path.join(DATA_DIR, fname), 'r') as f:
            data.append(json.loads(f.read()))
    return client.put(path, headers=submitter, data=json.dumps(data))

def put_cgci(client, auth=None):
    path = '/v0/submission'
    data = json.dumps({
        'name': 'CGCI', 'type': 'program',
        'dbgap_accession_number': 'phs000235'
    })
    r = client.put(path, headers=auth, data=data)
    return r

def put_cgci_blgsp(client, auth=None):
    put_cgci(client, auth=auth)
    path = '/v0/submission/CGCI/'
    data = json.dumps({
        "type": "project",
        "code": "BLGSP",
        "dbgap_accession_number": 'phs000527',
        "name": "Burkitt Lymphoma Genome Sequencing Project",
        "state": "open"
    })
    r = client.put(path, headers=auth, data=data)
    assert r.status_code == 200, r.data
    del g.user
    return r


# def test_node_subclasses(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     for cls in Node.get_subclasses():
#         print cls
#         data = json.dumps({
#             'query': """query Test {{ {} {{ id }}}}""".format(cls.label)
#         })
#         r = client.post(path, headers=submitter, data=data)
#         print r.data
#         assert cls.label in r.json['data'], r.data


# def test_alias(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     data = json.dumps({
#         'query': """query Test { alias1: case { id } }"""
#     })
#     r = client.post(path, headers=submitter, data=data)
#     assert 'alias1' in r.json.get('data', {}), r.data


# def test_types(client, submitter, pg_driver_clean, cgci_blgsp):
#     post = post_example_entities_together(client, pg_driver_clean, submitter)
#     assert post.status_code == 201
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test {
#         boolean: sample (first: 1) { is_ffpe }
#         float  : aliquot(first: 1) { concentration }
#         }"""
#     }))

#     print("types data is " + str(r.json))
#     assert isinstance(r.json['data']['boolean'][0]['is_ffpe'], bool)
#     assert isinstance(r.json['data']['float'][0]['concentration'], float)


# def test_unauthorized_graphql_query(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers={}, data=json.dumps({
#         'query': """query Test { alias1: case { id } }"""
#     }))
#     assert r.status_code == 403, r.data

# def test_fragment(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {
#           case { ... caseFragment  }
#         }

#         fragment caseFragment on case { id type   }
#         """}))
#     assert r.json.get('data', {}).get('case'), r.data
#     for case in r.json.get('data', {}).get('case'):
#         assert case.get('type') == 'case', case
#         assert 'amount' not in case


# def test_viewer(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test { viewer { case { id type } } }
#         """}))
#     assert r.json.get('data', {}).get('viewer', {}).get('case'), r.data
#     for case in r.json.get('data', {}).get('viewer', {}).get('case'):
#         assert 'type' in case


# def test_node_interface(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { node {
#         id type project_id created_datetime
#         }}"""}))
#     results = r.json.get('data', {}).get('node', {})
#     assert len(results) == len(utils.data_fnames)
#     for node in results:
#         assert 'type' in node
#         assert 'id' in node
#         assert 'project_id' in node
#         assert 'created_datetime' in node


# def test_quicksearch(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope():
#         aliquot = pg_driver_clean.nodes(models.Aliquot).first()
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test {
#         aliquot(quick_search: "%s") { id type project_id submitter_id  }}
#         """ % aliquot.submitter_id[15:]
#     }))
#     assert r.json == {
#         "data": {
#             "aliquot": [{
#                 "id": aliquot.node_id,
#                 "submitter_id": aliquot.submitter_id,
#                 "project_id": "CGCI-BLGSP",
#                 "type": "aliquot"
#             }]
#         }
#     }


# def test_node_interface_project_id(client, admin, submitter, pg_driver_clean):
#     assert put_cgci_blgsp(client, auth=admin).status_code == 200
#     post = post_example_entities_together(client, pg_driver_clean, submitter)
#     assert post.status_code == 201
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test {
#         a: node(project_id: "CGCI-BLGSP"  ) { id }
#         b: node(project_id: "FAKE-PROJECT") { id }
#         }"""}))
#     assert r.json['data']['a']
#     assert not r.json['data']['b']


# def test_node_interface_of_type(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     data = json.dumps({
#         'query': """
#             query Test {
#                 node (of_type: ["case"]) {
#                     id
#                     type
#                 }
#             }
#         """
#     })
#     r = client.post(path, headers=submitter, data=data)
#     print r.data
#     types = {d['type'] for d in r.json['data']['node']}
#     assert not {'case'}.symmetric_difference(types)


# def test_arg_props(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test { sample (project_id: "CGCI-BLGSP") { project_id }}
#         """}))
#     data = r.json.get('data')
#     assert data, r.data
#     assert data['sample'][0]['project_id'] == "CGCI-BLGSP"

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test { sample (project_id: "fake-project") { project_id }}
#         """}))
#     data = r.json.get('data')
#     assert data, r.data
#     assert not data['sample']


# def test_project_project_id_filter(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {
#         a: project (project_id: "CGCI-BLGSP") { project_id }
#         b: project (project_id: "FAKE") { project_id }
#         c: project (project_id: "FAKE_PROJECT") { project_id }
#         d: project (project_id: ["CGCI-BLGSP", "FAKE", "FAKE-PROJECT"]) {
#           project_id
#         }
#         }
#         """}))
#     assert r.json == {
#         "data": {
#             "a": [{"project_id": "CGCI-BLGSP"}],
#             "b": [],
#             "c": [],
#             "d": [{"project_id": "CGCI-BLGSP"}]
#         }
#     }


# def test_arg_first(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """ query Test { case (first: 1) { submitter_id }} """}))
#     assert r.json == {
#         'data': {
#             'case': [{
#                 'submitter_id': 'BLGSP-71-06-00019'
#             }]
#         }
#     }, r.data


# def test_arg_offset(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """ query Test { case (first: 5) { id }} """}))
#     first = {c['id'] for c in r.json['data']['case']}
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """ query Test { case (offset: 5) { id }} """}))
#     data = r.json.get('data')
#     assert data, r.data
#     offset = {c['id'] for c in r.json['data']['case']}
#     assert not offset.intersection(first)


# @pytest.mark.skip(reason='must rewrite query')
# def test_with_path(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     data = json.dumps({
#         'query': """
#             query Test {
#                 case (
#                         order_by_desc: "created_datetime",
#                         with_path_to: {
#                             type: "portion", submitter_id: "BLGSP-71-06-00019-99A"
#                         }
#                     ) {
#                     submitter_id
#                 }
#             }
#         """
#     })
#     r = client.post(path, headers=submitter, data=data)
#     print r.data
#     assert len(r.json['data']['case']) == 1
#     assert r.json['data']['case'][0]['submitter_id'] == "BLGSP-71-06-00019",\
#         r.data


# def test_with_path_to_any(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)

#     with pg_driver_clean.session_scope() as s:
#         props = dict(project_id='CGCI-BLGSP', state='validated')
#         case1 = models.Case('case1', submitter_id='case1', **props)
#         case2 = models.Case('case2', submitter_id='case2', **props)
#         sample1 = models.Sample('sample1', submitter_id='sample1', **props)
#         sample2 = models.Sample('sample2', submitter_id='sample2', **props)
#         case1.samples = [sample1]
#         case2.samples = [sample2]
#         s.add_all((case1, case2))

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test($sampleId1: String, $sampleId2: String) {
#         a: _case_count (with_path_to_any: [
#           {type: "sample", submitter_id: $sampleId1}
#           {type: "sample", submitter_id: $sampleId2}
#         ])
#         b: _case_count (with_path_to_any: [
#           {type: "sample", submitter_id: $sampleId1}
#         ])
#         c: _case_count (with_path_to_any: [
#           {type: "sample", submitter_id: $sampleId2}
#         ])
#         d: _case_count (with_path_to: [
#           {type: "sample", submitter_id: $sampleId1}
#         ])
#         e: _case_count (with_path_to: [
#           {type: "sample", submitter_id: $sampleId2}
#         ])
#         f: _case_count (with_path_to: [
#           {type: "sample", submitter_id: $sampleId1}
#           {type: "sample", submitter_id: $sampleId2}
#         ])
#         }""",
#         'variables': {
#             "sampleId1": sample1.submitter_id,
#             "sampleId2": sample2.submitter_id,
#         }
#     }))

#     assert r.status_code == 200, r.data
#     assert r.json == {
#         'data': {
#             'a': 2,
#             'b': 1,
#             'c': 1,
#             'd': 1,
#             'e': 1,
#             'f': 0,
#         }
#     }, r.data


# def test_with_path_to_invalid_type(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {
#         case (order_by_desc: "created_datetime",
#               with_path_to: {type: "BAD_TYPE"})
#         { submitter_id } }
#         """}))
#     print r.data
#     assert len(r.json['data']['case']) == 0


# @pytest.mark.skip(reason='test is wrong')
# def test_without_path(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope():
#         blgsp = pg_driver_clean.nodes(models.Project).props(code='BLGSP').one()
#         blgsp.cases += [models.Case('id1', project_id='CGCI-BLGSP')]
#     data = json.dumps({
#         'query': """
#             query Test {
#                 with   : _case_count(with_path_to   : {type: "aliquot"})
#                 without: _case_count(without_path_to: {type: "aliquot"})
#                 total  : _case_count
#             }
#         """
#     })
#     r = client.post(path, headers=submitter, data=data)
#     print r.data
#     data = r.json['data']
#     assert data['with']
#     assert data['without']
#     assert data['with'] + data['without'] == data['total']


# @pytest.mark.skip(reason='test does not conform to latest dictionary')
# def test_counts_with_path_filter_multiple_paths(
#         client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)

#     # create multiple paths
#     with pg_driver_clean.session_scope() as s:
#         aliquot = pg_driver_clean.nodes(models.Aliquot).first()
#         print(dir(aliquot))
#         sample = aliquot.analytes[0].portions[0].samples[0]
#         aliquot.samples = [sample]
#         s.merge(aliquot)

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {
#             with: _sample_count(with_path_to: {type: "aliquot"})
#         }
#         """}))
#     print r.data
#     data = r.json['data']
#     assert data['with'] == 1


# def test_with_path_negative(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
# query Test {
#   case (with_path_to: {
#     type: "portion", submitter_id: "incorrect"}) {
#       submitter_id
#   }
# }
# """}))
#     assert len(r.json['data']['case']) == 0, r.data


# @pytest.mark.skip(reason='test does not conform to latest dictionary')
# def test_with_path_multiple(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
# query Test {
#         case (with_path_to: [
#         {type: "sample", submitter_id: "BLGSP-71-06-00019s"},
#         {type: "portion", submitter_id: "BLGSP-71-06-00019-99A"}]) {
#       submitter_id
#   }
# }
# """}))
#     assert r.json['data']['case'][0]['submitter_id'] == "BLGSP-71-06-00019",\
#         r.data


# def test_order_by_asc_id(client, submitter, pg_driver_clean, cgci_blgsp):
#     utils.reset_transactions(pg_driver_clean)
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case (order_by_asc: "id") { id }}"""}))
#     print r.data
#     _original = r.json['data']['case']
#     _sorted = sorted(_original, cmp=(lambda a, b: cmp(a['id'], b['id'])))
#     assert _original == _sorted, r.data


# def test_order_by_desc_id(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case (order_by_desc: "id") { id }}"""}))
#     print r.data
#     _original = r.json['data']['case']
#     _sorted = sorted(_original, cmp=(lambda a, b: cmp(b['id'], a['id'])))
#     assert _original == _sorted, r.data


# def test_order_by_asc_prop(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case (order_by_asc: "submitter_id") {
#           submitter_id
#         }}"""}))
#     print r.data
#     _original = r.json['data']['case']
#     _sorted = sorted(_original, cmp=(
#         lambda a, b: cmp(a['submitter_id'], b['submitter_id'])))
#     assert _original == _sorted, r.data


# def test_order_by_desc_prop(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case (order_by_desc: "submitter_id") {
#           submitter_id
#         }}"""}))
#     print r.data
#     _original = r.json['data']['case']
#     _sorted = sorted(_original, cmp=(
#         lambda a, b: cmp(b['submitter_id'], a['submitter_id'])))
#     assert _original == _sorted, r.data


# @pytest.mark.skip(reason='test does not conform to latest dictionary')
# def test_auth_node_subclass(client, submitter, pg_driver_clean, cgci_blgsp):
#     with pg_driver_clean.session_scope():
#         blgsp = pg_driver_clean.nodes(models.Project).props(code='BLGSP').one()
#         blgsp.cases += [models.Case('id1', project_id='CGCI-BLGSP')]
#         blgsp.cases += [models.Case('id2', project_id='OTHER-OTHER')]
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case { project_id }}"""}))
#     with pg_driver_clean.session_scope():
#         assert len(r.json['data']['case']) == 1


# def test_auth_node_subclass_links(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope() as s:
#         cases = pg_driver_clean.nodes(models.Case).subq_path('samples').all()
#         for case in cases:
#             for sample in case.samples:
#                 sample.project_id = 'OTHER-OTHER'
#                 s.merge(sample)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { case (with_links: ["samples"]) {
#             submitter_id samples { id } _samples_count }}"""}))
#     print r.data
#     with pg_driver_clean.session_scope():
#         for case in r.json['data']['case']:
#             assert len(case['samples']) == 0, r.data
#             assert case['_samples_count'] == 0, r.data


# @pytest.mark.skip(reason='"clinicals" is not a link name')
# def test_with_links_any(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope():
#         ncases = pg_driver_clean.nodes(models.Case).count()
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test {
#         a: _case_count (with_links_any: [])
#         b: _case_count (with_links_any: ["clinicals"])
#         c: _case_count (with_links_any: ["samples"])
#         d: _case_count (with_links_any: ["samples", "clinicals"])
#         e: _case_count (with_links_any: ["clinicals", "samples"])
#         f: _case_count (with_links_any: ["clinicals", "samples", "projects"])
#         }"""}))
#     assert r.json == {
#         'data': {
#             'a': 1,
#             'b': 0,
#             'c': 1,
#             'd': 1,
#             'e': 1,
#             'f': ncases,
#         }
#     }, r.data


# def test_auth_counts(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     #: number of nodes to change project_id on, there should
#     #: actually only be 1
#     n = 1
#     with pg_driver_clean.session_scope() as s:
#         cases = pg_driver_clean.nodes(models.Case).limit(n).all()
#         for case in cases:
#             case.project_id = 'OTHER-OTHER'
#             s.merge(case)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { _case_count }"""}))
#     with pg_driver_clean.session_scope():
#         assert r.json['data']['_case_count'] == 0

# def test_transaction_logs(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { transaction_log(first:1) { project_id, submitter } }"""}))
#     assert len(r.json['data']['transaction_log']) == 1, r.data
#     assert r.json == {
#         "data": {
#             "transaction_log": [{
#             'project_id': 'CGCI-BLGSP', 'submitter': None
#             }]
#         }
#     }
    

# def test_auth_transaction_logs(client, submitter, pg_driver_clean, cgci_blgsp):
#     utils.reset_transactions(pg_driver_clean)
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope() as s:
#         log = pg_driver_clean.nodes(models.submission.TransactionLog).one()
#         log.program = 'OTHER'
#         s.merge(log)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """query Test { transaction_log { id } }"""}))
#     with pg_driver_clean.session_scope():
#         assert len(r.json['data']['transaction_log']) == 0, r.data


# def test_with_path_to(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope():
#         case_sub_id = pg_driver_clean.nodes(models.Case).path('samples')\
#                                               .first().submitter_id
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {{
#           aliquot (with_path_to: {{type: "case", submitter_id: "{}"}}) {{
#             a: submitter_id
#           }}
#         }}""".format(case_sub_id)}))
#     assert r.json['data']['aliquot'] == [{'a': 'BLGSP-71-06-00019-01A-11D'}]


# def test_variable(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope():
#         case = pg_driver_clean.nodes(models.Case).path('samples').one()
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test ($caseId: String) {
#           a: case (id: $caseId) {
#             submitter_id
#           }
#           b: sample (with_path_to: {type: "case", id: $caseId}) {
#             cases { submitter_id }
#           }
#         }
#         """,
#         'variables': {'caseId': case.node_id}
#     }))

#     print r.data
#     assert r.json == {
#         "data": {
#             'a': [{"submitter_id": case.submitter_id}],
#             'b': [{'cases': [{"submitter_id": case.submitter_id}]}],
#         }
#     }


# def test_null_variable(client, submitter, pg_driver_clean, cgci_blgsp):
#     utils.reset_transactions(pg_driver_clean)
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test ($projectId: [String]) {
#           a: _case_count (project_id: $projectId)
#           t: _transaction_log_count(project_id: $projectId)
#         }
#         """,
#     }))
#     with pg_driver_clean.session_scope():
#         cases = pg_driver_clean.nodes(models.Case).count()

#     print r.data
#     assert r.json == {
#         "data": {
#             'a': cases,
#             't': 1,
#         }
#     }


# def test_property_lists(client, submitter, pg_driver_clean, cgci_blgsp):
#     utils.reset_transactions(pg_driver_clean)
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope() as s:
#         s.merge(
#             models.Case('case1', submitter_id='s1', project_id='CGCI-BLGSP')
#         )
#         s.merge(
#             models.Case('case2', submitter_id='s2', project_id='CGCI-BLGSP')
#         )
#     data = json.dumps({
#         'query': """{
#           case (submitter_id: ["s1", "s2"]) {
#             id submitter_id
#           },
#           c1: _transaction_log_count(project_id: ["CGCI-BLGSP"])
#           c2: _transaction_log_count(project_id: ["CGCI-FAKE"])
#           c3: _transaction_log_count(project_id: "CGCI-BLGSP")
#         }""",
#     })
#     response = client.post(path, headers=submitter, data=data)
#     # fix for the unicode artifacts
#     expected_json = json.loads(json.dumps({
#         "data": {
#             'case': [
#                 {"id": "case1", "submitter_id": "s1"},
#                 {"id": "case2", "submitter_id": "s2"},
#             ],
#             'c1': 1,
#             'c2': 0,
#             'c3': 1,
#         }
#     }))
#     assert response.json == expected_json, response.data


# def test_not_property(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     with pg_driver_clean.session_scope() as s:
#         s.merge(
#             models.Case('case1', submitter_id='s1', project_id='CGCI-BLGSP')
#         )
#         s.merge(
#             models.Case('case2', submitter_id='s2', project_id='CGCI-BLGSP')
#         )
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{
#           case (not: {submitter_id: "s1"}, submitter_id: ["s1", "s2"]) {
#             id submitter_id
#           }
#         }""",
#     }))
#     assert r.json == {
#         "data": {
#             'case': [
#                 {"id": "case2", "submitter_id": "s2"},
#             ],
#         }
#     }, r.data


# def test_schema(client, submitter, pg_driver_clean):
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#           query IntrospectionQuery {
#             __schema {
#               queryType { name }
#               mutationType { name }
#               types {
#                 ...FullType
#               }
#               directives {
#                 name
#                 description
#                 args {
#                   ...InputValue
#                 }
#                 onOperation
#                 onFragment
#                 onField
#               }
#             }
#           }

#           fragment FullType on __Type {
#             kind
#             name
#             description
#             fields {
#               name
#               description
#               args {
#                 ...InputValue
#               }
#               type {
#                 ...TypeRef
#               }
#               isDeprecated
#               deprecationReason
#             }
#             inputFields {
#               ...InputValue
#             }
#             interfaces {
#               ...TypeRef
#             }
#             enumValues {
#               name
#               description
#               isDeprecated
#               deprecationReason
#             }
#             possibleTypes {
#               ...TypeRef
#             }
#           }

#           fragment InputValue on __InputValue {
#             name
#             description
#             type { ...TypeRef }
#             defaultValue
#           }

#           fragment TypeRef on __Type {
#             kind
#             name
#             ofType {
#               kind
#               name
#               ofType {
#                 kind
#                 name
#                 ofType {
#                   kind
#                   name
#                 }
#               }
#             }
#           }
#         """}))

#     assert r.status_code == 200
#     # Check the watermark of known types
#     assert len(r.json['data']['__schema']['types']) > 30


# def test_special_case_project_id(
#         client, submitter, pg_driver_clean, cgci_blgsp, put_tcga_brca):
#     data = json.dumps({
#         'query': """
#             {
#                 valid:   project (project_id: "CGCI-BLGSP") { ...f }
#                 invalid: project (project_id: "TCGA-TEST")  { ...f }
#                 multiple: project (project_id: ["TCGA-BRCA", "CGCI-BLGSP"]) { ...f }
#             }
#             fragment f on project { project_id code }
#         """
#     })
#     r = client.post(path, headers=submitter, data=data)
#     print r.data
#     assert r.json == {
#         "data": {
#             'valid': [{
#                 'project_id': 'CGCI-BLGSP',
#                 'code': 'BLGSP'
#             }],
#             'invalid': [],
#             'multiple': [{
#                 'project_id': 'TCGA-BRCA',
#                 'code': 'BRCA'
#             }, {
#                 'project_id': 'CGCI-BLGSP',
#                 'code': 'BLGSP'
#             }],
#         }
#     }


# def test_catch_language_error(client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{ case-1: case (first: 1) { id }} """}))
#     assert r.status_code == 400, r.data
#     {
#         "data": None,
#         "errors": [(
#             "Syntax Error GraphQL request (1:7) Expected Name, found Int"
#             " \"-1\"\n\n1: { case-1: case (first: 1) { id }} \n         ^\n"
#         )]
#     }

# @pytest.mark.skip(reason='must rewrite query')
# def test_filter_empty_prop_list(
#         client, submitter, pg_driver_clean, cgci_blgsp, monkeypatch):
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     utils.put_entity_from_file(client, 'read_group.json', submitter)
#     utils.patch_indexclient(monkeypatch)
#     utils.put_entity_from_file(
#         client, 'submitted_unaligned_reads.json', submitter
#     )

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{
#         a: _case_count(submitter_id: [])
#         b: _submitted_unaligned_reads_count
#         c: _submitted_unaligned_reads_count(file_state: [])
#         }"""
#     }))

#     assert r.json == {
#         'data': {
#             'a': 1,
#             'b': 1,
#             'c': 1,
#         }
#     }


# def test_submitted_unaligned_reads_with_path_to_read_group(
#         client, submitter, pg_driver_clean, cgci_blgsp):
#     """Regression for incorrect counts"""
#     post_example_entities_together(client, pg_driver_clean, submitter)
#     utils.put_entity_from_file(client, 'read_group.json', submitter)

#     files = [
#         models.SubmittedUnalignedReads(
#             'file_{}'.format(i), project_id='CGCI-BLGSP'
#         )
#         for i in range(3)
#     ]

#     with pg_driver_clean.session_scope() as s:
#         rg = pg_driver_clean.nodes(models.ReadGroup).one()
#         rg.submitted_unaligned_reads_files = files
#         rg = s.merge(rg)

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{
#         read_group(id: "%s") {
#            id
#            _submitted_unaligned_reads_files_count
#          }
#          submitted_unaligned_reads(with_path_to:{type: "read_group"}) {
#            id
#         }
#         }""" % rg.node_id
#     }))

#     assert r.json == {
#         "data": {
#             "read_group": [{
#                 "_submitted_unaligned_reads_files_count": 3,
#                 "id": rg.node_id
#             }],
#             "submitted_unaligned_reads": [{
#                 "id": "file_0"
#             }, {
#                 "id": "file_1"
#             }, {
#                 "id": "file_2"
#             }]
#         }
#     }


# def test_without_path_order(client, submitter, pg_driver_clean, cgci_blgsp):
#     """Assert that the ordering is applied after the exception"""
#     put_example_entities_together(client, pg_driver_clean, submitter)
#     utils.put_entity_from_file(client, 'case.json', submitter)
#     utils.put_entity_from_file(client, 'sample.json', submitter)

#     with pg_driver_clean.session_scope():
#         c = pg_driver_clean.nodes(models.Case).one()
#         c.samples = []

#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """
#         query Test {
#         case (
#           order_by_desc: "created_datetime",
#           without_path_to: { type: "sample" })
#         { submitter_id }
#         }"""}))

#     assert r.json == {
#         "data": {
#             "case": [{
#                 "submitter_id": "BLGSP-71-06-00019"
#             }]
#         }
#     }, r.data


# def test_read_group_with_path_to_case(
#         client, submitter, pg_driver_clean, cgci_blgsp):
#     """Regression for incorrect counts"""
#     put_example_entities_together(client, pg_driver_clean, submitter)
#     utils.put_entity_from_file(client, 'read_group.json', submitter)
#     data = json.dumps({
#         'query': """
#             {
#                 _read_group_count (with_path_to: {type: "case"})
#             }
#         """,
#     })
#     r = client.post(path, headers=submitter, data=data)
#     assert r.json == {
#         "data": {
#             "_read_group_count": 1,
#         }
#     }




# def test_tx_logs_async_fields(pg_driver_clean, graphql_client, cgci_blgsp):
#     assert graphql_client("""{
#         tx_log: transaction_log {
#             is_dry_run, state, committed_by
#         }
#     }""").json == {
#         "data": {
#             'tx_log': [{
#                 "is_dry_run": False,
#                 "state": "PENDING",
#                 "committed_by": None
#             }],
#         }
#     }


# def test_tx_logs_state(pg_driver_clean, graphql_client, cgci_blgsp, mock_tx_log):
#     assert graphql_client("""{
#         total: _transaction_log_count
#         succeeded: _transaction_log_count(state: "SUCCEEDED")
#         failed: _transaction_log_count(state: "FAILED")
#     }""").json == {
#         "data": {
#             "total": 1,
#             "succeeded": 1,
#             "failed": 0,
#         }
#     }


# def test_tx_logs_is_dry_run(pg_driver_clean, cgci_blgsp, mock_tx_log, graphql_client):
#     assert graphql_client("""{
#         total: _transaction_log_count
#         is: _transaction_log_count(is_dry_run: true)
#         isnt: _transaction_log_count(is_dry_run: false)
#     }""").json == {
#         "data": {
#             "total": 1,
#             "is": 1,
#             "isnt": 0,
#         }
#     }


# def test_tx_logs_committed_by(pg_driver_clean, cgci_blgsp, mock_tx_log, graphql_client):
#     assert graphql_client("""{
#         total: _transaction_log_count
#         right: _transaction_log_count(committed_by: 12345)
#         wrong: _transaction_log_count(committed_by: 54321)
#     }""").json == {
#         "data": {
#             "total": 1,
#             "right": 1,
#             "wrong": 0,
#         }
#     }


# def test_tx_logs_committable(pg_driver_clean, graphql_client, cgci_blgsp, mock_tx_log):
#     assert graphql_client("""{
#         total: _transaction_log_count
#         committable: _transaction_log_count(committable: true)
#         not_committable: _transaction_log_count(committable: false)
#     }""").json == {
#         "data": {
#             "total": 1,
#             "committable": 0,
#             "not_committable": 1,
#         }
#     }

# @pytest.mark.skip(reason='we have different data')
# def test_tx_logs_deletion(pg_driver_clean, graphql_client, cgci_blgsp, failed_deletion_transaction):
#     response = graphql_client("""{
#         transaction_log(id: %s) {
#             id
#             type
#             documents {
#             response {
#               entities {
#                 unique_keys
#                 related_cases { submitter_id }
#                 errors {
#                   message
#                 }
#               }
#             }
#           }
#         }
#       }
#     """ % failed_deletion_transaction)

#     assert response.json == {
#         "data": {
#             "transaction_log": [{
#                 "documents": [{
#                     "response": {
#                         "entities": [{
#                             'related_cases': [{
#                                 'submitter_id': 'BLGSP-71-06-00019'
#                             }],
#                             'unique_keys': json.dumps([{
#                                 "project_id": "CGCI-BLGSP",
#                                 "submitter_id": "BLGSP-71-06-00019s",
#                             }]),
#                             "errors": [{
#                                 "message": "Unable to delete entity because 4 others directly or indirectly depend on it. You can only delete this entity by deleting its dependents prior to, or during the same transaction as this one."
#                             }]
#                         }]
#                     }
#                 }],
#                 "id": failed_deletion_transaction,
#                 "type": "delete"
#             }]
#         }
#     }


# #: Transaction log query that is representative of a query from the
# #: Submission UI
# COMPREHENSIVE_TX_LOG_QUERY = """
# query TransactionDetailsQuery {
#   item: transaction_log {
#     id
#     project_id
#     type
#     state
#     committed_by
#     submitter
#     is_dry_run
#     closed
#     created_datetime
#     documents {
#       id
#       name
#       doc
#       doc_size
#       doc_format
#       response_json
#       response {
#         message
#         entities {
#           id
#           unique_keys
#           action
#           type
#           related_cases {
#             id
#             submitter_id
#           }
#           errors {
#             keys
#             type
#             message
#             dependents {
#               id
#               type
#             }
#           }
#         }
#       }
#     }
#   }
# }"""


# def test_tx_log_comprehensive_query_failed_upload(
#         pg_driver_clean, graphql_client, cgci_blgsp, failed_upload_transaction):
#     """Test a comprehensive tx_log query for a failed upload"""

#     response = graphql_client(COMPREHENSIVE_TX_LOG_QUERY)
#     assert response.status_code == 200, response.data
#     assert 'errors' not in response.json, response.data


# def test_tx_log_comprehensive_query_upload(
#         pg_driver_clean, graphql_client, populated_blgsp):
#     """Test a comprehensive tx_log query for a successful upload"""

#     response = graphql_client(COMPREHENSIVE_TX_LOG_QUERY)
#     assert response.status_code == 200, response.data
#     assert 'errors' not in response.json, response.data


# def test_tx_log_comprehensive_query_failed_deletion(
#         pg_driver_clean, graphql_client, cgci_blgsp, failed_deletion_transaction):
#     """Test a comprehensive tx_log query for a failed deletion"""

#     response = graphql_client(COMPREHENSIVE_TX_LOG_QUERY)
#     assert response.status_code == 200, response.data
#     assert 'errors' not in response.json, response.data

# def test_export(client, submitter, monkeypatch):
#     data = json.dumps({'bag_path':'manifest_bag',
#         "export_data":
#             {"data": {
#                 "project": [
#                 {
#                     "code": "BLGSP",
#                     "experiments": [],
#                     "id": "daa208a7-f57a-562c-a04a-7a7c77542c98",
#                     "name": "Burkitt Lymphoma Genome Sequencing Project",
#                     "programs": [
#                     {
#                         "id": "f6bd2676-33f6-5671-ac2f-38aa1ceedcd8",
#                         "name": "DEV"
#                     }
#                     ]
#                 },
#                 {
#                     "code": "test",
#                     "experiments": [
#                     {
#                         "id": "8307c663-af58-4b01-8fd0-9b63f55dac10"
#                     },
#                     {
#                         "id": "f6e00607-7f38-49ea-b64b-c45ccf0ff990"
#                     }
#                     ],
#                     "id": "a77f549b-c74b-563e-80bb-570b5a4dde88",
#                     "name": "test",
#                     "programs": [
#                     {
#                         "id": "f6bd2676-33f6-5671-ac2f-38aa1ceedcd8",
#                         "name": "DEV"
#                     }
#                     ]
#                 },
#                 {
#                     "code": "open",
#                     "experiments": [],
#                     "id": "9a2fe4bf-5484-5fe4-b882-0d61ecade7cc",
#                     "name": "Open access Project",
#                     "programs": [
#                     {
#                         "id": "f6bd2676-33f6-5671-ac2f-38aa1ceedcd8",
#                         "name": "DEV"
#                     }
#                     ]
#                 }
#                 ]
#             }
#         }
#     })
#     monkeypatch.setattr(
#         peregrine.utils,'contain_node_with_category',
#         lambda x,y: True
#     )

#     r = client.post(export_path, headers=submitter, data=data)
#     assert r.status_code == 200

#     #tear down
#     os.remove('manifest_bag.zip')
#     shutil.rmtree('manifest_bag')


# def test_export_with_no_data_file_node(client, submitter,monkeypatch):

#     data = json.dumps({'bag_path':'manifest_bag',
#         "export_data":
#             {"data": {
#                 "a": [{"project_id": "CGCI-BLGSP"}],
#                 "b": [],
#                 "c": [],
#                 "d": [{"project_id": "CGCI-BLGSP"}]
#             }
#         }})

#     monkeypatch.setattr(
#         peregrine.utils,'contain_node_with_category',
#         lambda x,y: False
#     )

#     r = client.post(export_path, headers=submitter, data=data)
#     assert r.status_code == 400

# def test_export_bagit(monkeypatch,client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
    
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{
#         a: project (project_id: "CGCI-BLGSP") { project_id }
#         b: project (project_id: "FAKE") { project_id }
#         c: project (project_id: "FAKE_PROJECT") { project_id }
#         d: project (project_id: ["CGCI-BLGSP", "FAKE", "FAKE-PROJECT"]) {
#           project_id
#         }
#         }"""
#         }))

#     monkeypatch.setattr(
#         peregrine.utils,'contain_node_with_category',
#         lambda x,y: True
#     )

#     ret_data = json.loads(r.data)

#     data = json.dumps({'bag_path':'manifest_bag',
#         'export_data': ret_data})

#     r = client.post(export_path, headers=submitter, data=data)
#     assert r.status_code == 200
#     assert os.path.exists('manifest_bag.zip')
#     assert os.path.exists('manifest_bag/bag-info.txt')
#     assert os.path.exists('manifest_bag/bagit.txt')
#     assert os.path.exists('manifest_bag/data/manifest.tsv')
#     assert os.path.exists('manifest_bag/manifest-sha512.txt')
#     assert os.path.exists('manifest_bag/tagmanifest-sha512.txt')
#     assert os.path.exists('manifest_bag/manifest-sha256.txt')
#     assert os.path.exists('manifest_bag/tagmanifest-sha256.txt')

#     #tear down
#     os.remove('manifest_bag.zip')
#     shutil.rmtree('manifest_bag')


def test_special_case_project_id(
        client, submitter, pg_driver_clean, cgci_blgsp, put_tcga_brca):
    data = json.dumps({
        'format': 'bdbag',
        'path': 'manifest_bag',
        'query': """
            {
                valid:   project (project_id: "CGCI-BLGSP") { ...f }
                invalid: project (project_id: "TCGA-TEST")  { ...f }
                multiple: project (project_id: ["TCGA-BRCA", "CGCI-BLGSP"]) { ...f }
            }
            fragment f on project { project_id code }
        """
    })
    r = client.post(path, headers=submitter, data=data)
    print r.data
    import pdb; pdb.set_trace()



# def test_export_bagit(monkeypatch,client, submitter, pg_driver_clean, cgci_blgsp):
#     post_example_entities_together(client, pg_driver_clean, submitter)
    
#     r = client.post(path, headers=submitter, data=json.dumps({
#         'query': """{
#         a: project (project_id: "CGCI-BLGSP") { project_id }
#         b: project (project_id: "FAKE") { project_id }
#         c: project (project_id: "FAKE_PROJECT") { project_id }
#         d: project (project_id: ["CGCI-BLGSP", "FAKE", "FAKE-PROJECT"]) {
#           project_id
#         }
#         }"""
#         }))

#     monkeypatch.setattr(
#         peregrine.utils,'contain_node_with_category',
#         lambda x,y: True
#     )

#     ret_data = json.loads(r.data)

#     data = json.dumps({'bag_path':'manifest_bag',
#         'export_data': ret_data})

#     r = client.post(export_path, headers=submitter, data=data)
#     assert r.status_code == 200
#     assert os.path.exists('manifest_bag.zip')
#     assert os.path.exists('manifest_bag/bag-info.txt')
#     assert os.path.exists('manifest_bag/bagit.txt')
#     assert os.path.exists('manifest_bag/data/manifest.tsv')
#     assert os.path.exists('manifest_bag/manifest-sha512.txt')
#     assert os.path.exists('manifest_bag/tagmanifest-sha512.txt')
#     assert os.path.exists('manifest_bag/manifest-sha256.txt')
#     assert os.path.exists('manifest_bag/tagmanifest-sha256.txt')

#     #tear down
#     os.remove('manifest_bag.zip')
#     shutil.rmtree('manifest_bag')

