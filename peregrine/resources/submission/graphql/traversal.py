# -*- coding: utf-8 -*-
"""
peregrine.resource.submission.graphql.traversal
----------------------------------

Defines traversals between node types in the graph and functions to
execute those traversal queries in the database
"""

import flask
from psqlgraph import Node, Edge
import sqlalchemy as sa
import time

terminal_nodes = [
    'annotations',
    'centers',
    'archives',
    'tissue_source_sites',
    'files',
    'related_files',
    'describing_files'
]

# Assign categories levels
#
# If we were to naively generate the possible traversals between two
# types of nodes, then we would end up with paths that 'wander' away
# from and towards Case.  Because we know a little about our graph, we
# can define one-way barriers to traversal based on category.
#
# For example, if we want the paths from case to annotation, we don't
# want to traverse from biospec to databundle to biospec to datafile
# to annotation.
#
# See :func:`is_valid_direction` for more details.
CATEGORY_LEVEL = {
    'administrative': 0,
    'biospecimen': 1,
    'clinical': 1,
    'data_file': 3,
}


def is_valid_direction(node, visited):
    """Determine if the direction we are traveling is valid.

    We've defined category levels (see `CATEGORY_LEVEL`) above. If we
    think of these zones as having a semipermeable barrier between
    them, we can programmatically cut down on how much 'wandering' the
    traversal queries do.

    This function uses those category levels to ensure that the level
    as a function of path is monotonic, i.e. if we're traveling out
    from case, don't turn back in, if we're traveling toward case,
    don't turn back out.

    :returns:
        A boolean stating whether the direction we are traveling
        is valid.
    """
    max_level = max(CATEGORY_LEVEL.values()) + 1
    first_level = CATEGORY_LEVEL.get(
        visited[0]._dictionary['category'],
        max_level
    )
    last_level = CATEGORY_LEVEL.get(
        visited[-1]._dictionary['category'],
        max_level
    )
    this_level = CATEGORY_LEVEL.get(
        node._dictionary['category'],
        max_level
    )
    if first_level > last_level:
        # If we are traveling from case out
        return this_level <= last_level
    else:
        # If we are traveling in towards case
        return this_level >= last_level


def construct_traversals_from_node_recursively(root_node, label_to_subclass):

    traversals = {node.label: set() for node in Node.get_subclasses()}

    def recursively_construct_traversals(node, visited, path):

        traversals[node.label].add('.'.join(path))

        def should_recurse_on(neighbor):
            """Check whether to recurse on a path."""
            return (
                neighbor
                # no backtracking:
                and neighbor not in visited
                # No 0 length edges:
                and neighbor != node
                # Don't walk back up the tree:
                and is_valid_direction(node, visited)
                # no traveling THROUGH terminal nodes:
                and (
                    (path and path[-1] not in terminal_nodes)
                    if path else neighbor.label not in terminal_nodes
                )
            )

        for edge in Edge._get_edges_with_src(node.__name__):
            neighbor = label_to_subclass[edge.__dst_class__]
            if should_recurse_on(neighbor):
                recursively_construct_traversals(
                    neighbor, visited + [node], path + [edge.__src_dst_assoc__]
                )

        for edge in Edge._get_edges_with_dst(node.__name__):
            neighbor = label_to_subclass[edge.__src_class__]
            if should_recurse_on(neighbor):
                recursively_construct_traversals(
                    neighbor, visited + [node], path + [edge.__dst_src_assoc__]
                )

    # Build up the traversals dictionary recursively.
    recursively_construct_traversals(root_node, [root_node], [])
    # Remove empty entries.
    traversals = {
        label: list(paths) for label, paths in traversals.iteritems() if bool(paths)
    }
    return traversals


def construct_traversals_from_node(root_node, label_to_subclass):
    traversals = {node.label: set() for node in Node.get_subclasses()}
    to_visit = [(root_node, [], [])]
    path = []
    while to_visit:
        node, path, visited = to_visit.pop()
        if path:
            path_string = '.'.join(path)
            if path_string in traversals[node.label]:
                continue
            traversals[node.label].add(path_string)
            # stop at terminal nodes
            if path[-1] in terminal_nodes:
                continue
        # Don't walk back up the tree
        if not is_valid_direction(node, visited or [root_node]):
            continue
        neighbors_dst = {
            (label_to_subclass[edge.__dst_class__], edge.__src_dst_assoc__)
            for edge in Edge._get_edges_with_src(node.__name__)
            if label_to_subclass[edge.__dst_class__]
        }
        neighbors_src = {
            (label_to_subclass[edge.__src_class__], edge.__dst_src_assoc__)
            for edge in Edge._get_edges_with_dst(node.__name__)
            if label_to_subclass[edge.__src_class__]
        }
        to_visit.extend([
            (neighbor, path + [edge], visited + [node])
            for neighbor, edge in neighbors_dst.union(neighbors_src)
            if neighbor not in visited
        ])
    return {label: list(paths) for label, paths in traversals.iteritems() if paths}


def make_graph_traversal_dict(app_logger):
    start = time.time()
    label_to_subclass = {
        n.__name__: n
        for n in Node.get_subclasses()
    }
    data = {
        node.label: construct_traversals_from_node(node, label_to_subclass)
        for node in Node.get_subclasses()
    }
    end = int(round(time.time() - start))
    app_logger.info('Traversed the graph in {} sec'.format(end))
    return data


def union_subq_without_path(q, *args, **kwargs):
    return q.except_(union_subq_path(q, *args, **kwargs))


def union_subq_path(q, src_label, dst_label, post_filters=[]):
    edges = (
        flask.current_app
        .graph_traversals
        .get(src_label, {})
        .get(dst_label, {})
    )
    if not edges:
        return q
    paths = list(flask.current_app.graph_traversals[src_label][dst_label])
    base = q.subq_path(paths.pop(), post_filters)
    while paths:
        base = base.union(q.subq_path(paths.pop(), post_filters))
    return base


def subq_paths(q, dst_label, post_filters=None):
    """Given a query and the label of the destination type, filter the
    selected entity (in the query) on the criteria that it has a path
    to at least one node with label :param:`dst_label` that matches
    any lambda filters in :param:`post_filters` (see psqlgraph.query
    for details on `subq_path`).

    Because ordering a union results in an exception, this function is
    a workaround to create a union of all `q.entity()` (the source
    type) and, instead of returning that, creates a new query which
    selects from all the entities that that union would have returned.
    This allows us to create a fresh query with the correct filtering
    that we can later filter/order/etc. as necessary.

    :param q:
        PsqlGraph graph query object
    :param dst_label:
        The label of the type to which the select must have a pat
    :param post_filters:
        A list of functions `f(sq)` that take a sub query `sq` apply
        sqlalchemy compatible filters
    :returns:
        PsqlGraph graph query object that selects for the same type of
        entity as the original :param:`q`

    """

    post_filters = post_filters or []

    paths = (
        flask.current_app
        .graph_traversals
        .get(q.entity().label, {})
        .get(dst_label, {})
    )
    if not paths:
        return q.filter(sa.sql.false())

    nodes = flask.current_app.db.nodes(q.entity())
    subquery_paths = [
        q.subq_path(path, post_filters).subquery().select()
        for path in paths
    ]
    return nodes.select_entity_from(sa.union_all(*subquery_paths))
