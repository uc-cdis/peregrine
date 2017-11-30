from functools import partial

from gdcapi import esutils
from gdcapi.repositories import quick

def search(params):
    response = quick.search(params)

    return response
