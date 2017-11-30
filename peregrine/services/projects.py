from gdcapi.repositories import projects


def get(pid, params):
    response = projects.get(pid, params)
    return response


def search(params, nest_fields=True):
    return projects.search(params)


def multi_match(params):
    return projects.multi_match(params)
