from gdcapi.repositories import reports


def search(params, **kwargs):
    return reports.search(params, **kwargs)
