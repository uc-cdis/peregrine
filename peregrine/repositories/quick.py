from functools import partial

from ..esutils import search as repo
from ..models import case, project, file, annotation

quick_search_fields = (project.quick_search_fields +
                       case.quick_search_fields +
                       file.quick_search_fields +
                       annotation.quick_search_fields)

MULTI_MATCH_FIELDS = quick_search_fields

ALLOWED_FIELDS = (project.allowed["fields"] +
                  case.allowed["fields"] +
                  file.allowed["fields"] +
                  annotation.allowed["fields"])

DEFAULT_MULTI_PARAMS = {
    'query': '',
    'fields': ','.join(MULTI_MATCH_FIELDS),
    'filters': '{}',
    'expand': '',
    'from': 0,
    'sort': '',
    'facets': '',
    "size": 5
}

nested_fields = case.nested_fields + file.nested_fields + project.nested_fields + annotation.nested_fields

allowed = {
    "facets": '',
    "fields": ALLOWED_FIELDS,
    "expand": nested_fields
}

doc_type = ",".join([project.doc_type, case.doc_type, file.doc_type, annotation.doc_type])

search = partial(repo.quick_search, doc_type, quick_search_fields, DEFAULT_MULTI_PARAMS, allowed,
                 nested_fields)
