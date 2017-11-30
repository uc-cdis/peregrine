from functools import partial

from ..esutils import search as repo
from ..models import file as f

DEFAULT_GET_PARAMS = {
    'fields': ','.join(f.defaults['fields']),
    'expand': ''
}

DEFAULT_SEARCH_PARAMS = {
    'size': 10,
    'from': 0,
    'sort': '',
    'fields': ','.join(f.defaults['fields']),
    'expand': '',
    'facets': '',
    'query': '',
    'filters': '{}'
}

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(f.MULTI_MATCH_FIELDS),
    'filters': '{}',
    'expand': '',
    'from': 0,
    'sort': '',
    'facets': '',
    "size": 5
}

get = partial(repo.get, f.doc_type, DEFAULT_GET_PARAMS, f.allowed)
get_source = partial(repo.get_source, f.doc_type)
search = partial(repo.search, f.doc_type, DEFAULT_SEARCH_PARAMS, f.allowed, f.nested_fields)
multi_match = partial(repo.quick_search, f.doc_type, f.quick_search_fields, DEFAULT_MULTI_PARAMS,
                      f.allowed, f.nested_fields)

scroll_search = partial(repo.scroll_search,
    f.doc_type,
    DEFAULT_SEARCH_PARAMS,
    f.allowed,
    f.nested_fields)
