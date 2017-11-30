import json
from gdcdatamodel import models
from psqlgraph import Node
import pytest

from tests.submission import utils
from tests.submission.test_endpoints import (
    post_example_entities_together,
    put_example_entities_together,
    put_cgci_blgsp,
)


path = '/v0/submission/graphql'

# def test_node_subclasses(client, submitter, pg_driver, cgci_blgsp):
#     post_example_entities_together(client, pg_driver, submitter)
#     for cls in Node.get_subclasses():
#         #print cls
#         data = json.dumps({
#             'query': """query Test {{ {} {{ id }}}}""".format(cls.label)
#         })
#         r = client.post(path, headers=submitter(path, 'post'), data=data)
#         #print r.data
#         assert cls.label in r.json['data'], r.data


# def test_alias(client, submitter, pg_driver, cgci_blgsp):
#     post_example_entities_together(client, pg_driver, submitter)
#     data = json.dumps({
#         'query': """query Test { alias1: case { id } }"""
#     })
#     r = client.post(path, headers=submitter(path, 'post'), data=data)
#     assert 'alias1' in r.json.get('data', {}), r.data


#     print r.data
#     assert isinstance(r.json['data']['boolean'][0]['is_ffpe'], bool)
#     assert isinstance(r.json['data']['float'][0]['concentration'], float)


# def test_unauthorized_graphql_query(client, submitter, pg_driver, cgci_blgsp):
#     post_example_entities_together(client, pg_driver, submitter)
#     r = client.post(path, headers={}, data=json.dumps({
#         'query': """query Test { alias1: case { id } }"""
#     }))
#     assert r.status_code == 403, r.data

def test_with_path_to(client, submitter, pg_driver, cgci_blgsp):
    post_example_entities_together(client, pg_driver, submitter)

    with pg_driver.session_scope():
        case_sub_id = pg_driver.nodes(models.Case).path('samples')\
                                              .first().submitter_id
    r = client.post(path, headers=submitter(path, 'post'), data=json.dumps({
        'query': """
        query Test {{
          aliquot (with_path_to: {{type: "case", submitter_id: "{}"}}) {{
            a: submitter_id
          }}
        }}""".format(case_sub_id)}))
    print(json.dumps({
        'query': """
        query Test {{
          aliquot (with_path_to: {{type: "case", submitter_id: "{}"}}) {{
            a: submitter_id
          }}
        }}""".format(case_sub_id)}))
    assert r.json['data']['aliquot'] == [{'a': 'BLGSP-71-06-00019-01A-11D'}]

