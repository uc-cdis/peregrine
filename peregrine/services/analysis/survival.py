import json

from survivalpy.survival import Analyzer
from survivalpy.survival import Datum
from survivalpy.logrank import LogRankTest

from gdcapi.services import cases

from gdcapi.errors import UserError

'''
data = [Datum(1, False, {'id': 'D13'}),
        Datum(1, True, {'id': 'D54'}),
        Datum(3, False, {'id': 'D81'}),
        Datum(4, False, {'id': 'D95'}),
        Datum(6, True, {'id': 'D32'}),
        Datum(6, False, {'id': 'D20'}),
        Datum(9, True, {'id': 'D51'})]
'''


def make_datum(d, cid):
    days = d.get('days_to_death')
    if days is None:
        days = d.get('days_to_last_follow_up')

    return Datum(days, d.get('vital_status', '') == 'alive', {'id': cid})


def make_data(ds, cid):
    r = [make_datum(d, cid) for d in ds if d.get('days_to_death', None) or d.get('days_to_last_follow_up', None)]
    return r


def transform(data):
    r = [make_data(c['diagnoses'], c['case_id']) for c in data['data']['hits'] if 'diagnoses' in c]
    return [item for sublist in r for item in sublist]


def prepare_donor(donor, estimate):
    donor["survivalEstimate"] = estimate
    donor["id"] = donor["meta"]["id"]
    donor.pop("meta", None)
    return donor


def prepare_result(result):
    items = [item.to_json_dict() for item in result]

    return {
        'meta': {
            'id': id(result)
        },
        'donors': [prepare_donor(donor, interval.get("cumulativeSurvival")) for interval in items for donor in interval["donors"]]
    }


def get_curve(filters):
    data = cases.search({
        'fields': 'diagnoses.days_to_last_follow_up,diagnoses.days_to_death,diagnoses.vital_status,case_id',
        'size': 10000,
        'filters': {"op": "and", "content": [
            filters,
            {"op": "or", "content": [
                {"op": "not", "content": {"field": "diagnoses.days_to_death"}},
                {"op": "not", "content": {"field": "diagnoses.days_to_last_follow_up"}}
            ]},
            {"op": "not", "content": {"field": "diagnoses.vital_status"}}
        ]}
    })

    if len(data['data']['hits']) == 0:
        return []

    return Analyzer(transform(data)).compute()


def survival(req_opts):
    stats = {}

    try:
        filters = json.loads(req_opts.get('filters', '[{"op":"not","content":{"field":"diagnoses.vital_status"}}]'))
    except ValueError:
        raise UserError('filters must be valid json')

    if isinstance(filters, dict):
        filters = [filters]

    curves = [get_curve(f) for f in filters]

    if len(curves) > 1 and all(len(c) for c in curves):
        stats = LogRankTest(survival_results=curves).compute()

    return {
        'results': [prepare_result(result) for result in curves],
        'overallStats': stats
    }
