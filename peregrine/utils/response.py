import json
import logging
import subprocess
import defusedxml.minidom as minidom
from datetime import datetime

import dicttoxml
import os
from cdispyutils.log import get_handler
from flask import Response, Markup
from peregrine import VERSION
from peregrine.utils.json2csv import to_csv

defusedxml.defuse_stdlib()
logger = logging.getLogger("peregrine.utils.response")
logger.addHandler(get_handler())

try:
    repo_subdir = os.path.dirname(os.path.realpath(__file__))
    commit_cmd = "cd {}; git rev-parse HEAD".format(repo_subdir)
    COMMIT = subprocess.check_output(commit_cmd, shell=True).strip()
    logger.info('API from commit {}'.format(COMMIT))
except Exception as e:
    logger.warning(str(e))
    COMMIT = None


def get_data_release():
    """TODO: Unhard code this"""
    return 'Data Release 3.0 - September 21, 2016'


def get_status():
    status = {'status': 'OK', 'version': 1, 'tag': VERSION, 'data_release': get_data_release()}
    if COMMIT:
        status["commit"] = COMMIT
    return status


def tryToInt(value):
    new_value = value
    try:
        new_value = int(value)
    except ValueError:
        pass
    return new_value


def striptags_from_dict(data):
    """
        Strips tags from both keys and values in a dict
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.iteritems():
            cleanedK = tryToInt(Markup(k).striptags())
            if isinstance(v, dict):
                new_dict[cleanedK] = striptags_from_dict(v)
            else:
                # striptags converts everything to str, so convert back to int if possible
                new_dict[cleanedK] = tryToInt(Markup(v).striptags())
    return new_dict


def add_content_disposition(request_headers, request_options, response, file_name="file"):
    """
        Returns response as a file if attachment parameter in request is true

        Args:
            request_headers (dict): headers from the Request object
            request_options (dict): args or form fields from Request object
            response (Response): the response to modify
            file_name (string): the filename used if response is sent as a file (no extension, extension determined by content-type)

        Returns:
            A Flask Response object, with Content-Disposition set if attachment was true. Unmodified otherwise.
    """
    if 'attachment' in request_options.keys():
        if (isinstance(request_options['attachment'], bool) and request_options['attachment']) or request_options[
            'attachment'].lower() == 'true':
            file_extension = request_options.get('format', 'json').lower()
            response.headers.add('Content-Disposition', 'attachment',
                                 filename='{}.{}.{}'.format(request_options.get('filename', file_name),
                                                            datetime.now().isoformat(), file_extension))
            response = remove_download_token_from_cookie(request_options, response)
    return response


def is_pretty(options):
    return options.get('pretty', 'false').lower() == 'true'


def to_json(options, data):
    return (json.dumps(data, indent=2, separators=(', ', ': ')) if is_pretty(options)
        else json.dumps(data))


def to_xml(options, data):
    """
        Converts a dict to xml string with <reponse> as the root

        Args:
            options (dict): request options
            hits (dict or list): the data to convert

        Returns:
            xml string
    """
    xml = dicttoxml.dicttoxml(data, attr_type=False, custom_root="response")
    if is_pretty(options):
        xml = minidom.parseString(xml).toprettyxml()
    return xml


def format_response(request_options, data, mimetype):
    """
        Returns data as a response with the format specified either as a parameter (priority)
        or as a Accept header in the request.

        Args:
            request_options (dict): args or form fields from Request object
            data (dict): data to be formatted and returned in the Response body
            mimetype (string)

        Returns:
            A Flask Response object, with the data formatted as specified and the Content-Type set
    """
    if (request_options.get('attachment', '').lower() == 'true' or
            "text/csv" in mimetype or
            "text/tab-separated-values" in mimetype):
        if 'hits' in data['data']:
            data = data['data']['hits']
        else:
            data = [data['data']]

    if isinstance(data, dict):
        pagination = data.get('data', {}).get('pagination', None)
        if pagination:
            data['data']['pagination'] = striptags_from_dict(pagination)
        warnings = data.get('warnings', None)
        if warnings:
            data['warnings'] = striptags_from_dict(warnings)

    if "text/xml" in mimetype:
        data = to_xml(request_options, data)
    elif "text/csv" in mimetype:
        data = to_csv(data, dialect='excel')
    elif "text/tab-separated-values" in mimetype:
        data = to_csv(data, dialect='excel-tab')
    else:
        mimetype = "application/json"
        data = to_json(request_options, data)

    response = Response(data, mimetype=mimetype)
    for key, value in get_status().iteritems():
        response.headers.extend({'X-GDC-{}'.format(key): value})

    return response


def remove_download_token_from_cookie(options, response):
    """
        Removes a download token in cookie as an indicator that download is ready.

        Args:
            options (dict): args or form fields from Request object
            response: Response object

        Returns:
            The response object that is passed in
    """
    cookie_key = options.get('downloadCookieKey', '')
    cookie_path = options.get('downloadCookiePath', '/')

    if cookie_key != '':
        response.set_cookie(cookie_key, expires=0, path=cookie_path)

    return response
