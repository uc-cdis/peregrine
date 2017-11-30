import os

import flask
import graphene
import graphql

from peregrine.utils.pyutils import (
    log_duration,
)
from .node import (
    NodeField,
    create_root_fields,
    resolve_node,
)
from .node import __fields as ns_fields
from .transaction import (
    TransactionLogCountField,
    TransactionLogField,
    resolve_transaction_log,
    resolve_transaction_log_count,
)
from .util import (
    set_session_timeout,
)


GRAPHQL_TIMEOUT = float(os.environ.get('GRAPHQL_TIMEOUT', 20))  # seconds
TIMEOUT_MESSAGE = """

Query exceeded {} second timeout.  Please reduce query complexity and
try again.  Ways to limit query complexity include adding "first: 1"
arguments to limit results, limiting path query filter usage
(e.g. with_path_to), or limiting extensive path traversal field
inclusion (e.g. _related_cases).

""".replace('\n', ' ').strip()


def get_schema():
    """Create GraphQL Schema"""

    root_fields = {}
    root_fields.update(create_root_fields(ns_fields))

    Viewer = type('viewer', (graphene.ObjectType,), root_fields)

    root_fields['node'] = NodeField
    root_fields['resolve_node'] = resolve_node

    root_fields['viewer'] = graphene.Field(Viewer)
    root_fields['resolve_viewer'] = lambda *_: Viewer()

    root_fields['transaction_log'] = TransactionLogField
    root_fields['resolve_transaction_log'] = resolve_transaction_log

    root_fields['_transaction_log_count'] = TransactionLogCountField
    root_fields['resolve__transaction_log_count'] = resolve_transaction_log_count

    Root = type('Root', (graphene.ObjectType,), root_fields)

    Schema = graphene.Schema(query=Root, auto_camelcase=False)

    return Schema


Schema = get_schema()


def execute_query(query, variables=None):
    """
    Pull required parameters from global request and execute GraphQL query.

    :returns: a tuple (``data``, ``errors``)
    """
    variables = variables or {}

    # Execute query
    try:
        session_scope = flask.current_app.db.session_scope()
        timer = log_duration("GraphQL")
        result = None
        with session_scope as session:
            with timer:
                set_session_timeout(session, GRAPHQL_TIMEOUT)
                result = Schema.execute(query, variable_values=variables)
    except graphql.error.GraphQLError as e:
        return None, [str(e)]

    errors = []
    database_timeout = result is None
    if database_timeout:
        errors = [TIMEOUT_MESSAGE.format(GRAPHQL_TIMEOUT)]
        data = {} if result is None else result.data
        return data, errors
    else:
        if result.errors:
            errors = [err.message for err in result.errors]
        # Generate response
        if "TimeoutException" in errors:
            errors.append(TIMEOUT_MESSAGE.format(GRAPHQL_TIMEOUT))

    return result.data, errors
