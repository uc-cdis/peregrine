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


def construct_traversals_from_node(root_node, app):
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
        name_to_subclass = getattr(app, 'name_to_subclass', None)
        if name_to_subclass is None:
            name_to_subclass = app.name_to_subclass = {
                n.__name__: n
                for n in Node.get_subclasses()
            }
        neighbors_dst = {
            (name_to_subclass[edge.__dst_class__], edge.__src_dst_assoc__)
            for edge in Edge._get_edges_with_src(node.__name__)
            if name_to_subclass[edge.__dst_class__]
        }
        neighbors_src = {
            (name_to_subclass[edge.__src_class__], edge.__dst_src_assoc__)
            for edge in Edge._get_edges_with_dst(node.__name__)
            if name_to_subclass[edge.__src_class__]
        }
        to_visit.extend([
            (neighbor, path + [edge], visited + [node])
            for neighbor, edge in neighbors_dst.union(neighbors_src)
            if neighbor not in visited
        ])
    return {label: list(paths) for label, paths in traversals.iteritems() if paths}


def make_graph_traversal_dict(app, preload=False):
    """Initialize the graph traversal dict.

    If USE_LAZY_TRAVERSE is False, Peregrine server will preload the full dict at start,
    or it will be initialized as an empty dict.

    You may call this method with `preload=True` to manually preload the full dict.
    """
    app.graph_traversals = getattr(app, 'graph_traversals', {})
    if preload or not app.config.get('USE_LAZY_TRAVERSE', True):
        for node in Node.get_subclasses():
            _get_paths_from(node, app)


def _get_paths_from(src, app):
    if isinstance(src, type) and issubclass(src, Node):
        src_label = src.label
    else:
        src, src_label = Node.get_subclass(src), src
    if src_label not in app.graph_traversals:
        # GOTCHA: lazy initialization is not locked because 1) threading is not enabled
        # in production with uWSGI, and 2) this always generates the same result for the
        # same input so there's no racing condition to worry about
        start = time.time()
        app.graph_traversals[src_label] = construct_traversals_from_node(src, app)
        time_taken = int(round(time.time() - start))
        if time_taken > 0.5:
            app.logger.info('Traversed the graph starting from "%s" in %.2f sec',
                            src_label, time_taken)
    return app.graph_traversals[src_label]


def get_paths_between(src, dest, app=None):
    """Get traversal paths between src and dest.

    src and dest may be Node subclasses or their labels.
    Returns a list of path strings.
    """
    if app is None:
        app = flask.current_app
    if isinstance(dest, type) and issubclass(dest, Node):
        dest = dest.label
    return _get_paths_from(src, app).get(dest, [])


def union_subq_without_path(q, *args, **kwargs):
    return q.except_(union_subq_path(q, *args, **kwargs))


def union_subq_path(q, src_label, dst_label, post_filters=[]):
    paths = get_paths_between(src_label, dst_label)
    if not paths:
        return q
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

    paths = get_paths_between(q.entity(), dst_label)
    if not paths:
        return q.filter(sa.sql.false())

    nodes = flask.current_app.db.nodes(q.entity())
    subquery_paths = [
        q.subq_path(path, post_filters).subquery().select()
        for path in paths
    ]
    return nodes.select_entity_from(sa.union_all(*subquery_paths))
