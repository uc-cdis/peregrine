from .schema import SchemaQuery
from psqlgraph import Node
import base


# Brittle, changinge this may result in circular dependencies
import node_subclass as ns
import transaction

from .base import (
    assert_type,
    munge,
)

from gdcgraphql import (
    Query,
)


class NodeCountQuery(base.GraphQLQuery):

    DEFINES_SCHEMA = True

    def parse(self):
        name = self.top.name
        if name == "_{}_count".format(transaction.TransactionLogQuery.name):
            self.get_transaction_log_count_result(self.top)
        else:
            self.get_node_count_result(self.top)

    def get_transaction_log_count_result(self, field):
        query = transaction.TransactionLogQuery(self.g, field, self.fragments)
        q = query.get_base_query(field)
        q = query.apply_query_args(q, field, use_defaults=False)
        self.result = {self.top.key: q.count()}

    def get_node_count_result(self, field):
        label = '_'.join(self.top.name.split('_')[1:-1])
        cls = Node.get_subclass(label)

        if not cls:
            self.errors.append('Unable to execute {} count'.format(label))
            return None

        node_query = ns.NodeSubclassQuery(
            self.g, None, self.fragments)

        q = self.get_authorized_query(cls)
        for arg in self.top.arguments:
            q = node_query.add_arg_filter(q, arg)
        self.result = {self.top.key: q.count()}

    @staticmethod
    def _queries():
        return [
            Query.schema(
                args=ns.NodeSubclassQuery.get_node_query_args(cls),
                name=NodeCountQuery._query_name(cls),
                type=graphene.Int,
            )
            for cls in Node.get_subclasses()
        ] + [
            Query.schema(
                args=transaction.TransactionLogQuery._args(),
                name="_{}_count".format(transaction.TransactionLogQuery.name),
                type=graphene.Int,
            )
        ]

    @staticmethod
    def _types():
        return []

    @staticmethod
    def _query_name(cls):
        return '_{}_count'.format(cls.label)
