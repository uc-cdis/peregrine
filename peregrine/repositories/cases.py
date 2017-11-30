from functools import partial

from ..esutils import search as repo
from ..models import case

DEFAULT_GET_PARAMS = {
    'fields': ','.join(case.defaults['fields']),
    'expand': ''
}

DEFAULT_SEARCH_PARAMS = {
    'size': 10,
    'from': 0,
    'sort': '',
    'fields': ','.join(case.defaults['fields']),
    'expand': '',
    'facets': '',
    'query': '',
    'filters': '{}'
}

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(case.MULTI_MATCH_FIELDS),
    'filters': '{}',
    'expand': '',
    'from': 0,
    'sort': '',
    'facets': '',
    "size": 5
}

get = partial(repo.get, case.doc_type, DEFAULT_GET_PARAMS, case.allowed)
search = partial(repo.search, case.doc_type, DEFAULT_SEARCH_PARAMS, case.allowed,
                 case.nested_fields)
multi_match = partial(repo.quick_search, case.doc_type, case.quick_search_fields, DEFAULT_MULTI_PARAMS,
                      case.allowed, case.nested_fields)

scroll_search = partial(
    repo.scroll_search,
    case.doc_type,
    DEFAULT_SEARCH_PARAMS,
    case.allowed,
    case.nested_fields)
