import os

import flask
import graphene
import graphql

from peregrine import dictionary
from peregrine.utils.pyutils import (
    log_duration,
)
from .node import (
    NodeField,
    create_root_fields,
    resolve_node,
    DataNode,
    # call_that_returns_fields_dict,
    get_node_interface_args,
    DataNodeField,
    resolve_datanode,
)
#from .node import __fields as ns_fields
from .node import get_fields
from .transaction import (
    TransactionLogCountField,
    TransactionLogField,
    resolve_transaction_log,
    resolve_transaction_log_count,
)
from .traversal import make_graph_traversal_dict
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
    ns_fields = get_fields()
    root_fields.update(create_root_fields(ns_fields))

    Viewer = type('viewer', (graphene.ObjectType,), root_fields)

    root_fields['node'] = NodeField
    root_fields['resolve_node'] = resolve_node

    # DataNode.init_shared_fiels()
    # DataNode = type('DataNode', (graphene.Interface,), call_that_returns_fields_dict())
    # print(vars(DataNode))
    # flask.current_app.logger.information(vars(DataNode))
    # DataNodeField = graphene.List(DataNode, args=get_node_interface_args())

    def call_that_returns_fields_dict():
        shared_fields = None
        for node in dictionary.schema:
            schema = dictionary.schema[node]
            if schema['category'].endswith('_file'):
                fields = schema['properties'].keys()
                if shared_fields is None:
                    shared_fields = set(fields)
                else:
                    shared_fields = shared_fields.intersection(fields)
        result = {}
        for field in shared_fields:
            result[field] = graphene.String()
        return result
        # return {"object_id": graphene.String(), "testfield": graphene.String()}

    DataNode = type('DataNode', (graphene.ObjectType,), call_that_returns_fields_dict())
    print(vars(DataNode))
    DataNodeField = graphene.List(DataNode, args=get_node_interface_args())

    root_fields['datanode'] = DataNodeField
    root_fields['resolve_datanode'] = resolve_datanode

    root_fields['viewer'] = graphene.Field(Viewer)
    root_fields['resolve_viewer'] = lambda *_: Viewer()

    root_fields['transaction_log'] = TransactionLogField
    root_fields['resolve_transaction_log'] = resolve_transaction_log

    root_fields['_transaction_log_count'] = TransactionLogCountField
    root_fields['resolve__transaction_log_count'] = resolve_transaction_log_count

    Root = type('Root', (graphene.ObjectType,), root_fields)

    Schema = graphene.Schema(query=Root, auto_camelcase=False)

    return Schema



def execute_query(query, variables=None):
    """
    Pull required parameters from global request and execute GraphQL query.

    :returns: a tuple (``data``, ``errors``)
    """
    variables = variables or {}
    # import pdb; pdb.set_trace()
    # Execute query
    try:
        session_scope = flask.current_app.db.session_scope()
        timer = log_duration("GraphQL")
        result = None
        with session_scope as session:
            with timer:
                set_session_timeout(session, GRAPHQL_TIMEOUT)
                #result = Schema.execute(query, variable_values=variables)
                #import pdb; pdb.set_trace()
                # print(vars(DataNode))
                result = flask.current_app.graphql_schema.execute(query, variable_values=variables)
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
