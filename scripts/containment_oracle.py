#!/usr/bin/env python3
"""Ordered old/tiergraph containment differential over a named corpus.

The corpus includes every checked-in profile sample plus adversarial structural
fixtures.  Agreement is therefore a corpus-bounded result, not a claim that no
possible graph changes answer.  The one known difference is declared below so
the oracle measures it without disguising it as agreement.
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
    changes: int


@dataclass(frozen=True)
class KnownChange:
    fixture: str
    label: str
    operation: str
    old_labels: tuple[str, ...]
    new_labels: tuple[str, ...]


# Found by adversarial review after the migration, not predicted before it.
# One relation may name the same child twice: the old kernel preserves that in
# direct_children, but parents uses membership and returns its parent once.
# The projection preserves each incidence in both directions, making the two
# reads coherent.  A route starts with parents, so it changes for the same
# reason.  Ancestors remains de-duplicated by both implementations.
KNOWN_CHANGES = (
    KnownChange(
        "fixture:duplicate-child",
        "leaf",
        "parents",
        ("root",),
        ("root", "root"),
    ),
    KnownChange(
        "fixture:duplicate-child",
        "leaf",
        "routes",
        ("root",),
        ("root", "root"),
    ),
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
    fixture_count = event_count = comparison_count = change_count = 0
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
                    label = _label(old, ref)
                    if operation == "routes":
                        old_labels = tuple(_label(old, route[0]) for route in expected)
                        new_labels = tuple(_label(old, route[0]) for route in actual)
                    else:
                        old_labels = _labels(old, expected)
                        new_labels = _labels(old, actual)
                    change = KnownChange(name, label, operation, old_labels, new_labels)
                    if change not in KNOWN_CHANGES:
                        raise AssertionError(
                            f"{name} {ref} {operation}: {actual!r} != {expected!r}"
                        )
                    change_count += 1
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
    if change_count != len(KNOWN_CHANGES):
        raise AssertionError(
            f"known containment changes exercised {change_count} times; "
            f"expected {len(KNOWN_CHANGES)}"
        )
    return Coverage(fixture_count, event_count, comparison_count, change_count)


if __name__ == "__main__":
    seed = os.environ.get("PYTHONHASHSEED")
    if seed is None:
        raise SystemExit("PYTHONHASHSEED must be fixed")
    coverage = verify()
    print(
        f"containment oracle: {coverage.events} events over "
        f"{coverage.fixtures} fixtures; {coverage.comparisons} ordered comparisons; "
        f"{coverage.changes} attributed changes; corpus-bounded; "
        f"PYTHONHASHSEED={seed}"
    )
