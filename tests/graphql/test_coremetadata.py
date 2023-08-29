import json
import uuid

from cdiserrors import NotFoundError
from datamodelutils import models
import pytest

from peregrine.blueprints.coremetadata import (
    translate_dict_to_bibtex,
    flatten_dict,
)
from tests.graphql import utils
from tests.graphql.test_graphql import post_example_entities_together


def test_translate_dict_to_bibtex():
    input = {"object_id": "object_id_test", "key2": "value2", "key3": "value3"}
    output = translate_dict_to_bibtex(input)
    expected = '@misc {object_id_test, object_id = "object_id_test", key2 = "value2", key3 = "value3"}'
    assert output == expected


def test_flatten_dict():
    input = {
        "data_type_test": [
            {
                "core_metadata_collections": [
                    {"creator": "creator_test", "description": "description_test"}
                ],
                "file_name_test": "file_name",
                "object_id": "object_id_test",
            }
        ]
    }
    output = flatten_dict(input)
    expected = {
        "creator": "creator_test",
        "description": "description_test",
        "file_name_test": "file_name",
        "object_id": "object_id_test",
    }
    assert output == expected


def test_flatten_dict_without_core_metadata():
    """
    An exception should be raised if the core_metadata_collections field does not contain any data.
    """
    input1 = {
        "data_type_test": [
            {
                "core_metadata_collections": [],
                "file_name_test": "file_name",
                "object_id": "object_id_test",
            }
        ]
    }
    output = flatten_dict(input1)
    expected = {"file_name_test": "file_name", "object_id": "object_id_test"}
    assert output == expected

    input2 = {
        "data_type_test": [
            {"file_name_test": "file_name", "object_id": "object_id_test"}
        ]
    }
    output = flatten_dict(input2)
    assert output == expected


def test_flatten_dict_raises_exception():
    """
    An exception should be raised if a requested field was not found for this file. The details of the error should be in the exception message.
    """
    input = {"data": "null", "errors": ["error_details_test"]}
    with pytest.raises(NotFoundError) as e:
        flatten_dict(input)
    assert "error_details_test" in e.value.args[0]


def test_endpoint(client, submitter, pg_driver_clean, cgci_blgsp, graphql_client):
    obj_id = str(uuid.uuid4())
    post_example_entities_together(client, pg_driver_clean, submitter)
    utils.put_entity_from_file(client, "read_group.json", submitter)

    files = [
        models.SubmittedUnalignedReads(
            "file_131", project_id="CGCI-BLGSP", object_id=obj_id
        )
    ]

    with pg_driver_clean.session_scope() as s:
        rg = pg_driver_clean.nodes(models.ReadGroup).one()
        rg.submitted_unaligned_reads_files = files
        s.merge(rg)

    res = client.get(f"/coremetadata/{obj_id}", headers=submitter)
    assert res.status_code == 200, res.text
    data = json.loads(res.data)
    assert data.get("object_id") == obj_id
    assert data.get("project_id") == "CGCI-BLGSP"
    assert data.get("type") == "submitted_unaligned_reads"
    assert obj_id in data.get("citation", "")
