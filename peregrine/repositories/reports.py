from functools import partial

from ..esutils import search as repo
from gdcapi.models import report


DEFAULT_GET_PARAMS = {
    'fields': ','.join(report.defaults['fields']),
    'expand': ''
}

DEFAULT_SEARCH_PARAMS = {
    'size': 10,
    'from': 0,
    'sort': '',
    'fields': ','.join(report.defaults['fields']),
    'expand': '',
    'facets': '',
    'query': '',
    'filters': '{}'
}

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(report.MULTI_MATCH_FIELDS),
    'filters': '{}'
}

get = partial(repo.get, report.doc_type, DEFAULT_GET_PARAMS, report.allowed)
search = partial(repo.search, report.doc_type, DEFAULT_SEARCH_PARAMS, report.allowed, report.nested_fields)
