from gdcapi.repositories import annotations


def get(pid, params):
    response = annotations.get(pid, params)
    return response


def search(params=None):
    return annotations.search(params)


def multi_match(params):
    return annotations.multi_match(params)
