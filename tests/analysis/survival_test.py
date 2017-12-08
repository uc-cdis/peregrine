from survivalpy.survival import Datum
import pytest
from peregrine.services.analysis.survival import (
    prepare_result,
    prepare_donor,
    transform,
    make_data,
    make_datum,
    get_curve
)

def test_make_datum():
    input_data = {'days_to_last_follow_up': None, 'days_to_death': 329.0, 'vital_status': 'dead'}
    datum = make_datum(input_data, 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d')
    assert isinstance(datum, Datum)

def test_make_data_with_death():
    input_data = {'diagnoses': [{'days_to_last_follow_up': None, 'days_to_death': 329.0, 'vital_status': 'dead'}], 'case_id': 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d'}
    data = make_data(input_data["diagnoses"], input_data["case_id"])
    assert isinstance(data, list)
    assert len(data) == 1
    assert isinstance(data[0], Datum)

def test_make_data_with_follow_up():
    input_data = {'diagnoses': [{'days_to_last_follow_up': 129.0, 'days_to_death': None, 'vital_status': 'dead'}], 'case_id': 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d'}
    data = make_data(input_data["diagnoses"], input_data["case_id"])
    assert isinstance(data, list)
    assert len(data) == 1
    assert isinstance(data[0], Datum)

def test_make_data_without_days():
    input_data = {'diagnoses': [{'vital_status': 'dead'}], 'case_id': 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d'}
    data = make_data(input_data["diagnoses"], input_data["case_id"])
    assert isinstance(data, list)
    assert len(data) == 0

def test_make_data_without_days_none():
    input_data = {'diagnoses': [{'days_to_last_follow_up': None, 'days_to_death': None, 'vital_status': 'dead'}], 'case_id': 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d'}
    data = make_data(input_data["diagnoses"], input_data["case_id"])
    assert isinstance(data, list)
    assert len(data) == 0

def test_transform():
    data = {'data': {'hits': [{'diagnoses': [{'days_to_last_follow_up': None, 'days_to_death': 329.0, 'vital_status': 'dead'}], 'case_id': 'c3cc716b-1b9c-4e73-9a40-f1f891a17c2d'}], 'pagination': {'count': 1, 'sort': '', 'from': 1, 'pages': 535, 'total': 535, 'page': 1, 'size': 1}}, 'warnings': {}}
    transformed_data = transform(data)
    assert len(transformed_data) == 1
    assert isinstance(transformed_data[0], Datum)

def test_prepare_donor_with_donor_and_estimate():
    donor = {'meta': {'id': 'f38a6799-11e0-471c-834e-0d97e00aec07'}, 'censored': True, 'time': 0.0}
    estimate = 1
    prepared_donor = prepare_donor(donor, estimate)
    assert isinstance(prepared_donor, dict)
    assert prepared_donor["id"] == donor["id"]
    assert prepared_donor["survivalEstimate"] == estimate
    assert prepared_donor["censored"] == donor["censored"]
    assert prepared_donor["time"] == donor["time"]
    assert "meta" not in prepared_donor

def test_prepare_result_empty_array():
    result = prepare_result([])
    assert isinstance(result, dict)
    assert isinstance(result["donors"], list)
    assert isinstance(result["meta"], dict)
    assert len(result["donors"]) == 0
    assert isinstance(result["meta"]["id"], int)

def test_prepare_result_none():
    with pytest.raises(TypeError):
        prepare_result(None)

def test_get_curve_no_results(es_setup, client):
    curve = get_curve({"op":"=", "content":{"field":"cases.project.project_id", "value":"THIS_VALUE_DOES_NOT_EXIST"}})
    assert isinstance(curve, list)
    assert len(curve) == 0

def test_get_curve_with_results(es_setup, client):
    curve = get_curve({"op":"=", "content":{"field":"project.project_id", "value":"PAAD"}})
    assert isinstance(curve, list)
    assert len(curve) != 0
