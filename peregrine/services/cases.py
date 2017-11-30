from gdcapi.repositories import cases


def get(pid, params=None):
    return cases.get(pid, params=params)


def search(params=None, nest_fields=True):
    return cases.search(params=params)


def multi_match(params):
    return cases.multi_match(params)

def scroll_search(params):
    return cases.scroll_search(params)
