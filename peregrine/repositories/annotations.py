from functools import partial

from ..esutils import search as repo
from ..models import annotation

DEFAULT_GET_PARAMS = {
    'fields': ','.join(annotation.defaults['fields']),
    'expand': ''
}

DEFAULT_SEARCH_PARAMS = {
    'size': 10,
    'from': 0,
    'sort': '',
    'fields': ','.join(annotation.defaults['fields']),
    'expand': '',
    'facets': '',
    'query': '',
    'filters': '{}'
}

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(annotation.MULTI_MATCH_FIELDS),
    'filters': '{}',
    'expand': '',
    'from': 0,
    'sort': '',
    'facets': '',
    "size": 5
}

get = partial(repo.get, annotation.doc_type, DEFAULT_GET_PARAMS, annotation.allowed)
search = partial(repo.search, annotation.doc_type, DEFAULT_SEARCH_PARAMS, annotation.allowed, annotation.nested_fields)
multi_match = partial(repo.quick_search, annotation.doc_type, annotation.quick_search_fields, DEFAULT_MULTI_PARAMS,
                      annotation.allowed, annotation.nested_fields)
