# -*- coding: utf-8 -*-
"""
peregrine.resources.submission.util
----------------------------------

Provides utility functions for the submission resource.
"""

import os
from collections import Counter

import json
from flask import current_app as capp
from flask import request
from functools import wraps
from psqlgraph import Node
import sqlalchemy
from threading import Thread
import simplejson
import yaml

import datamodelutils.models as models
from peregrine.errors import UserError
from peregrine.resources.submission.constants import (
    project_seed,
    program_seed,
    ERROR_STATE,
    FLAG_IS_ASYNC,
    submitted_state,
    UPLOADING_STATE,
    SUCCESS_STATE,
)


def get_external_proxies():
    """Get any custom proxies set in the config.

    This is a rather specific use case, but here we want to reach out
    to an external resource via a proxy but do not want to set the
    proxy environment variable proper.

    This value should be added to ``app.config['EXTERNAL_PROXIES']``.
    And should look something like

    .. codeblock::

        {
            'http': "http://<http_proxy:port>",
            'http': "https://<https_proxy:port>",
        }

    :returns:
        A Dictionary ``{'http': ..., 'https': ...}`` with proxies.  If
        a certain proxy is not specified, it should be absent from the
        dictionary.

    """

    return capp.config.get('EXTERNAL_PROXIES', {})


def oph_raise_for_duplicates(object_pairs):
    """Given an list of ordered pairs, contstruct a dict as with the
    normal JSON ``object_pairs_hook``, but raise an exception if there
    are duplicate keys with a message describing all violations.

    """

    counter = Counter(p[0] for p in object_pairs)
    duplicates = filter(lambda p: p[1] > 1, counter.iteritems())

    if duplicates:
        raise ValueError(
            'The document contains duplicate keys: {}'
            .format(','.join(d[0] for d in duplicates)))

    return {
        pair[0]: pair[1]
        for pair in object_pairs
    }


def parse_json(raw):
    """Returns a python representation of a JSON document.

    :param str raw: Load this provided string.
    :raises: UserError if any exception is raised parsing the JSON body

    ..note:: Uses :func:`oph_raise_for_duplicates` in parser.

    """

    try:
        return simplejson.loads(
            raw, object_pairs_hook=oph_raise_for_duplicates)
    except Exception as e:
        raise UserError('Unable to parse json: {}'.format(e))


def parse_request_json(expected_types=(dict, list)):
    """Returns a python representation of a JSON POST body.

    :param str raw:
        Load this provided string.  If raw is not provided, pull the body
        from global request object
    :raises: UserError if any exception is raised parsing the JSON body
    :raises: UserError if the result is not of the expected type

    """

    parsed = parse_json(request.get_data())
    if not isinstance(parsed, expected_types):
        raise UserError('JSON parsed from request is an invalid type: {}'
                        .format(parsed.__class__.__name__))
    return parsed


def parse_request_yaml():
    """Returns a python representation of a YAML POST body.

    :raises: UserError if any exception is raised parsing the YAML body

    """

    raw = request.get_data()
    try:
        return yaml.safe_load(raw)
    except Exception as e:
        raise UserError('Unable to parse yaml: {}'.format(e))


def lookup_node(psql_driver, label, node_id=None, secondary_keys=None):
    """Return a query for nodes by id and secondary keys"""

    cls = Node.get_subclass(label)
    query = psql_driver.nodes(cls)

    if node_id is None and not secondary_keys:
        return query.filter(sqlalchemy.sql.false())

    if node_id is not None:
        query = query.ids(node_id)

    if all(all(keys) for keys in secondary_keys):
        query = query.filter(cls._secondary_keys == secondary_keys)

    return query


def lookup_project(psql_driver, program, project):
    """Return a project by Project.code if attached to Program.name"""

    return (psql_driver.nodes(models.Project).props(code=project)
            .path('programs')
            .props(name=program)
            .scalar())


def lookup_program(psql_driver, program):
    """Return a program by Program.name"""

    return psql_driver.nodes(models.Program).props(name=program).scalar()


def get_entities(psql_driver, node_ids):
    """Lookup entities from graph by node_id"""

    query = psql_driver.nodes().ids(node_ids)
    nodes = query.all()
    entities = {n.node_id: n for n in nodes}

    return entities


def parse_boolean(value):
    """Try parse boolean. raises UserError if unable. """

    if isinstance(value, bool):
        return value
    elif value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False
    else:
        raise UserError('Boolean value not one of [true, false]')


def is_flag_set(flag, default=False):
    """Did the user specify the value of a flag (default: False)

    Example:

        ?async=true

    Requires request context.

    """

    return parse_boolean(request.args.get(flag, default))


def async(f):
    """Decorator to run function in background"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        """Wrapper for async call"""

        thread = Thread(target=f, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper


def get_introspection_query():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    f = open(os.path.join(cur_dir, 'graphql', 'introspection_query.txt'), 'r')
    return f.read()


def get_variables(payload):
    var_payload = payload.get('variables')
    variables = None
    errors = None
    if isinstance(var_payload, dict):
        variables = var_payload
    else:
        try:
            variables = json.loads(var_payload) if var_payload else {}
        except Exception as e:
            errors = ['Unable to parse variables', str(e)]
    return variables, errors
