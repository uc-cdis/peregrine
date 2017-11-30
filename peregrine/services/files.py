import hashlib
import time

from gdcapi.download import get_nodes, Stream
from gdcapi.download.utils import get_manifest, yield_manifest_from_search
from gdcapi.repositories import files
from flask import current_app as capp
import datetime


def get(pid, params=None):
    response = files.get(pid, params)
    return response


def manifest(params=None):
    result = search(params)

    filename = 'gdc_manifest'

    if 'data' in result and 'hits' in result['data']:
        hits = result['data']['hits']
        if not hits:
            return json.dumps(result), filename
        else:
            return (yield_manifest_from_search(hits),
                    filename)
    else:
        # return error message from search result
        return json.dumps(result), filename


def search(params=None, nest_fields=True):
    return files.search(params)


def multi_match(params):
    return files.multi_match(params)

def scroll_search(params):
    return files.scroll_search(params)
