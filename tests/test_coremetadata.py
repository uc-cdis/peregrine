import pytest
from pidgin import app as _app
from pidgin.errors import PidginException, NoCoreMetadataException


def test_translate_dict_to_bibtex():
    input = {"object_id": "object_id_test", "key2": "value2", "key3": "value3"}
    output = _app.translate_dict_to_bibtex(input)
    expected = '@misc {object_id_test, object_id = "object_id_test", key2 = "value2", key3 = "value3"}'
    assert output == expected


def test_flatten_dict():
    input = {
        "data": {
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
    }
    output = _app.flatten_dict(input)
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
        "data": {
            "data_type_test": [
                {
                    "core_metadata_collections": [],
                    "file_name_test": "file_name",
                    "object_id": "object_id_test",
                }
            ]
        }
    }
    output = _app.flatten_dict(input1)
    expected = {"file_name_test": "file_name", "object_id": "object_id_test"}
    assert output == expected

    input2 = {
        "data": {
            "data_type_test": [
                {"file_name_test": "file_name", "object_id": "object_id_test"}
            ]
        }
    }
    output = _app.flatten_dict(input2)
    assert output == expected


def test_flatten_dict_raises_exception():
    """
    An exception should be raised if a requested field was not found for this file. The details of the error should be in the exception message.
    """
    input = {"data": "null", "errors": ["error_details_test"]}
    with pytest.raises(NoCoreMetadataException) as e:
        _app.flatten_dict(input)
    assert "error_details_test" in e.value.args[0]


def test_peregrine_error(app):
    """
    If Peregrine (at API_URL) does not return valid data, Pidgin
    should not crash.
    """
    app.config["API_URL"] = "https://google.com"
    _app.send_query("{}")
