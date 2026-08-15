"""Profile-neutral navigation over declared tier-graph containment."""

from __future__ import annotations

from ._containment_projection import ContainmentProjection
from ._tiergraph import Graph


def _project(graph: Graph) -> ContainmentProjection:
    return ContainmentProjection.build(graph)


def direct_children(
    graph: Graph, parent: str, *, tier: str | None = None
) -> tuple[str, ...]:
    """Return immediate children in their declared sequence order."""
    return _project(graph).direct_children(parent, tier)


def expanded_leaves(graph: Graph, parent: str) -> tuple[str, ...]:
    """Recursively replace containers with their ordered leaf contents."""
    return _project(graph).leaves(parent)


def descendants_on_tier(graph: Graph, parent: str, *, tier: str) -> tuple[str, ...]:
    """Return reachable descendants on ``tier`` in containment walk order.

    The walk is stable depth-first declaration order and visits a canonical
    child path once: when the same child is reachable through repeated
    containment routes, its first occurrence fixes its place in the result.
    """
    return _project(graph).descendants(parent, tier)


def parents(graph: Graph, child: str) -> tuple[str, ...]:
    """Return immediate containers in canonical relation order."""
    return _project(graph).parents(child)


def ancestor_routes(graph: Graph, child: str) -> tuple[tuple[str, ...], ...]:
    """Return every maximal route from an immediate parent to a root container.

    Routes are ordered depth-first by the canonical order of ``Graph.parents``.
    A route contains the immediate parent first and its outermost ancestor last.
    """

    projection = _project(graph)

    def routes_from(item: str, route: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        outer = projection.parents(item)
        if not outer:
            return (route,)
        return tuple(
            result
            for parent in outer
            if parent not in route
            for result in routes_from(parent, (*route, parent))
        )

    return tuple(
        route
        for parent in projection.parents(child)
        for route in routes_from(parent, (parent,))
    )


def lexical_projection(
    graph: Graph, container: str, *, lexical_tier: str
) -> tuple[str, ...]:
    """Project direct lexical children, excluding heterogeneous siblings."""
    return direct_children(graph, container, tier=lexical_tier)


def expand_phrase(graph: Graph, phrase: str) -> tuple[str, ...]:
    """Expand a heterogeneous phrase while retaining direct leaf events."""
    return expanded_leaves(graph, phrase)
