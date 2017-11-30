from functools import partial

from ..esutils import search as repo
from ..models import project

DEFAULT_GET_PARAMS = {
    'fields': ','.join(project.defaults['fields']),
    'expand': ''
}

DEFAULT_SEARCH_PARAMS = {
    'size': 10,
    'from': 0,
    'sort': '',
    'fields': ','.join(project.defaults['fields']),
    'expand': '',
    'facets': '',
    'query': '',
    'filters': '{}'
}

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(project.MULTI_MATCH_FIELDS),
    'filters': '{}',
    'expand': '',
    'from': 0,
    'sort': '',
    'facets': '',
    "size": 5
}

get = partial(repo.get, project.doc_type, DEFAULT_GET_PARAMS, project.allowed)
search = partial(repo.search, project.doc_type, DEFAULT_SEARCH_PARAMS, project.allowed, project.nested_fields)
multi_match = partial(repo.quick_search, project.doc_type, project.quick_search_fields, DEFAULT_MULTI_PARAMS,
                      project.allowed, project.nested_fields)
