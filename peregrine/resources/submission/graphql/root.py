from .fragment import FragmentQuery
from .node_subclass import NodeSubclassQuery
from .base import GraphQLQuery
from .counts import NodeCountQuery
import stopit

from psqlgraph import Node
from graphql.ast import FragmentSpread


class RootQuery(GraphQLQuery):

    def parse(self):
        """To allow 'arbitrary' complexity but not denial of service, set both
        database and application level timeouts

        """

        queries = {cls.name: cls for cls in GraphQLQuery.__subclasses__()}

        self.set_database_timeout()
        with stopit.ThreadingTimeout(self.timeout) as cm:
            for field in self.top.selections:
                query_class = queries.get(field.name, None)
                self.parse_field(field, query_class)

        if not cm:
            self.errors += [self.timeout_msg]

    def parse_field(self, field, query_class):
        """Lookup the correct query class and add results, errors to this
        instance

        """

        if query_class and hasattr(query_class, 'parse'):
            pass
        elif isinstance(field, FragmentSpread):
            query_class = FragmentQuery
        elif Node.get_subclass(field.name):
            query_class = NodeSubclassQuery
        elif field.name.endswith('_count'):
            query_class = NodeCountQuery

        if query_class:
            self.subquery(query_class, field, self.result)
        else:
            self.errors.append(
                "Cannot query field '{}' on 'Root'"
                .format(field.name))
