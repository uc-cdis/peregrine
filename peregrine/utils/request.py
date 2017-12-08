import json
from peregrine.errors import UserError

# Need this wrapper when `raise` is used in a lambda
def error_out(error):
    raise error


def parse_request(request):
    """
        Parses the Request object and returns a dictionary of all args and fields from the request.
        Args:
            request (Request): Request object
        Returns:
            options (dict): args or form fields from Request object
            mimetype (string): the mimetype as a string
            is_csv (bool): whether the requested format is CSV or not
        Note:
            Parameters from query string are merged with fields from request (in a form or a JSON). If a parameter appears in both query string and request body, the value from the request body overrides that in the query string.
    """

    def handlers(ct):
        if 'application/x-www-form-urlencoded' in ct:
            # Converts the immutable multi-dict (class type of request.form) into a regular dict,
            # because somewhere downstream this parsed options is checked and sanitized, where
            # mutation occurs which throws an exception (for modifying an immutable).
            # dict returns a regular dictionary; however, because the source is a multi-dict,
            # all values are converted into a list (because form fields can be repeated for
            # multi-value fields). Here we unbox the value for lists of one single element and
            # let the ones with multiple values remain as lists.
            return {key: value if len(value) > 1 else value[0] for key, value in dict(request.form).items()}
        elif 'application/json' in ct:
            return request.get_json() if request.data != '' else {}
        else:
            error_out(UserError(
                "Content-Type header for POST must be 'application/json' or 'application/x-www-form-urlencoded'"
            ))

    all_args = [request.args.to_dict(), {} if request.method == 'GET' else handlers(request.headers.get('Content-Type', '').lower())]
    # Merges two dictionaries in all_args
    options = { k: v for d in all_args for k, v in d.items() }

    mimetype, is_csv = select_mimetype(request.headers, options)
    return options, mimetype, is_csv


def select_mimetype(request_headers, request_options):
    """
        Returns a mimetype based on the format param or Accept header
        Args:
            request_headers (dict): headers from the Request object
            request_options (dict): args or form fields from Request object
        Returns:
            The mimetype as a string
            is_csv (boolean): whether the requested format is CSV or not
    """
    mimetype = request_headers.get('Accept', 'application/json')
    if 'format' in request_options:
        req_format = request_options['format'].lower()
        if req_format == 'xml':
            mimetype = "text/xml"
        elif req_format == 'csv':
            mimetype = "text/csv"
        elif req_format == "tsv":
            mimetype = "text/tab-separated-values"
        else:
            mimetype = "application/json"
    if 'text/csv' in mimetype or 'text/tab-separated-values' in mimetype:
        is_csv = True
    else:
        is_csv = False
    return mimetype, is_csv
