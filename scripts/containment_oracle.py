#!/usr/bin/env python3
"""Ordered old/tiergraph containment differential over a named sample.

The constructible population is derived from the builder and graph validator;
fixture reach is reported separately. Agreement is bounded by the named sample,
and structural classes outside that reach remain explicitly untested.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ipakit import Form, FormBuilder, IPAFeatures  # noqa: E402
from ipakit._cmu_graph import read as read_cmu  # noqa: E402
from ipakit._containment_projection import ContainmentProjection  # noqa: E402
from ipakit._gesture_graph import project as project_gestures  # noqa: E402
from ipakit._mora_graph import build as build_mora  # noqa: E402
from ipakit._panphon_graph import build as build_panphon  # noqa: E402
from ipakit._pinyin_graph import build as build_pinyin  # noqa: E402
from ipakit._rewrite_graph import (  # noqa: E402
    japanese_moraic_fixture,
    japanese_moraic_fixtures,
)
from ipakit._tiergraph import (  # noqa: E402
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder  # noqa: E402


@dataclass(frozen=True)
class Coverage:
    fixtures: int
    events: int
    comparisons: int


# This is a class enumeration, not an instance enumeration. Arity and depth are
# unbounded, so the population is finitely described rather than finite-sized.
STRUCTURAL_POPULATION = (
    "zero, one, or multiple named containment declarations",
    "declared source and target arity ranges, including admitted empty sides",
    "event or boundary endpoints, homogeneous or heterogeneous tier restrictions",
    "source-unique incidence with arbitrary ordered targets and repeated targets",
    "finite acyclic depth per relation, including isolated nodes and branching",
    "shared targets and diamonds; multiple relations whose union may be cyclic",
)

FIXTURE_REACH = (
    "event-only singleton sources with nonempty unary and polyadic targets",
    "homogeneous and heterogeneous incidence",
    "declared forward and reverse target order, plus repeated targets",
    "isolated, shallow, deep, branching, and diamond-shaped graphs",
    "multiple independently acyclic relations, including a cyclic union",
)

UNTESTED_CLASSES = (
    "multi-source containment instances",
    "admitted empty source or target sides",
    "boundary-endpoint containment",
    "the full range of declared arity bounds and target permutations",
    "sharing patterns beyond the named diamond and unbounded-depth families",
    "the same source participating in more than one containment relation",
)


def _structural_fixture(kind: str) -> Graph:
    declared = Declarations(
        tuple(TierDeclaration(name, frozenset({"label"})) for name in ("a", "b")),
        (FeatureDeclaration("label"),),
        (RelationDeclaration("contains", containment=True, acyclic=True),),
    )
    builder = GraphBuilder(declared)
    root = builder.begin("a", {"label": "root"})
    first = builder.begin("a", {"label": "first"})
    second = builder.begin("b", {"label": "second"})
    leaf = builder.append_input_atom("b", {"label": "leaf"})
    builder.end(second)
    builder.end(first)
    builder.end(root)
    if kind == "heterogeneous":
        builder.contain(root, (leaf, first, second), relation="contains")
    elif kind == "duplicate-child":
        builder.contain(root, (leaf, leaf), relation="contains")
    elif kind == "diamond":
        builder.contain(root, (first, second), relation="contains")
        builder.contain(first, (leaf,), relation="contains")
        builder.contain(second, (leaf,), relation="contains")
    else:
        builder.contain(root, (second, first), relation="contains")
    return builder.build()


def _cross_relation_cycle_fixture() -> Graph:
    declared = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        (
            RelationDeclaration("a", containment=True, acyclic=True),
            RelationDeclaration("b", containment=True, acyclic=True),
        ),
    )
    builder = GraphBuilder(declared)
    first = builder.append_input_atom("item", {"label": "first"})
    second = builder.append_input_atom("item", {"label": "second"})
    builder.contain(first, (second,), relation="a")
    builder.contain(second, (first,), relation="b")
    return builder.build()


def corpus() -> tuple[tuple[str, Graph], ...]:
    """Build every named checked-in navigation fixture and profile sample."""
    inventory = IPAFeatures()
    hierarchy = FormBuilder(inventory)
    utterance = hierarchy.begin("utterance")
    phrase = hierarchy.begin("phrase")
    segments = hierarchy.append_ipa("kæt")
    hierarchy.end(phrase)
    hierarchy.end(utterance)
    hierarchy.contain(phrase, segments)
    hierarchy.contain(utterance, (phrase,))
    hierarchy.add_root(utterance)

    graphs: list[tuple[str, Graph]] = [
        ("fixture:heterogeneous", _structural_fixture("heterogeneous")),
        ("fixture:duplicate-child", _structural_fixture("duplicate-child")),
        ("fixture:diamond", _structural_fixture("diamond")),
        ("fixture:declared-reverse-order", _structural_fixture("reverse")),
        ("fixture:cross-relation-cycle", _cross_relation_cycle_fixture()),
        ("profile:ipa", hierarchy.build()._graph),
        ("profile:cmu", read_cmu(("K", "AE1", "T"))),
        ("profile:pinyin", build_pinyin("shui", "sh", "ui", 3)),
        ("profile:mora", build_mora(("to", "o"), "high")),
    ]
    native = Form.parse("ata", inventory)._graph
    graphs.append(("profile:gesture", project_gestures(native, inventory)))
    panphon, _ = build_panphon(("p", "a", "t"))
    graphs.append(("profile:panphon", panphon))
    graphs.extend(
        (
            f"profile:japanese-rewrite:{name}",
            japanese_moraic_fixture(name, inventory)._graph,
        )
        for name in japanese_moraic_fixtures()
    )
    return tuple(graphs)


def _routes(graph: object, child: str) -> tuple[tuple[str, ...], ...]:
    def parents(item: str) -> tuple[str, ...]:
        return graph.parents(item)  # type: ignore[attr-defined,no-any-return]

    def from_item(item: str, route: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        outer = parents(item)
        if not outer:
            return (route,)
        return tuple(
            result
            for parent in outer
            if parent not in route
            for result in from_item(parent, (*route, parent))
        )

    return tuple(
        route for parent in parents(child) for route in from_item(parent, (parent,))
    )


def _label(graph: Graph, ref: str) -> str:
    event = graph.resolve(ref).event
    assert event is not None
    return str(event.features.get("label", ref))


def _labels(graph: Graph, refs: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_label(graph, ref) for ref in refs)


def verify() -> Coverage:
    fixture_count = event_count = comparison_count = 0
    for name, old in corpus():
        fixture_count += 1
        projected = ContainmentProjection.build(old)
        refs = old.event_references()
        event_count += len(refs)
        tiers = tuple(declaration.name for declaration in old.declarations.tiers)
        for ref in refs:
            observations = (
                ("direct", old.direct_children(ref), projected.direct_children(ref)),
                ("descendants", old.descendants(ref), projected.descendants(ref)),
                ("leaves", old.leaves(ref), projected.leaves(ref)),
                ("parents", old.parents(ref), projected.parents(ref)),
                ("ancestors", old.ancestors(ref), projected.ancestors(ref)),
                ("routes", _routes(old, ref), _routes(projected, ref)),
            )
            for operation, expected, actual in observations:
                comparison_count += 1
                if actual != expected:
                    raise AssertionError(
                        f"{name} {ref} {operation}: {actual!r} != {expected!r}"
                    )
            for tier in tiers:
                for operation, expected, actual in (
                    (
                        "direct-tier",
                        old.direct_children(ref, tier),
                        projected.direct_children(ref, tier),
                    ),
                    (
                        "descendants-tier",
                        old.descendants(ref, tier),
                        projected.descendants(ref, tier),
                    ),
                ):
                    comparison_count += 1
                    if actual != expected:
                        raise AssertionError(
                            f"{name} {ref} {operation} {tier}: "
                            f"{actual!r} != {expected!r}"
                        )
    return Coverage(fixture_count, event_count, comparison_count)


if __name__ == "__main__":
    seed = os.environ.get("PYTHONHASHSEED")
    if seed is None:
        raise SystemExit("PYTHONHASHSEED must be fixed")
    coverage = verify()
    print(
        f"containment oracle: {coverage.events} events over "
        f"{coverage.fixtures} fixtures; {coverage.comparisons} ordered comparisons; "
        f"no answer differences; fixture-sample-bounded; PYTHONHASHSEED={seed}"
    )
    print("constructible/admitted classes: " + "; ".join(STRUCTURAL_POPULATION))
    print("fixture classes reached: " + "; ".join(FIXTURE_REACH))
    print("untested classes: " + "; ".join(UNTESTED_CLASSES))
