#!/usr/bin/env python3
"""Verify the tiergraph containment projection against its committed golden."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path

import tiergraph

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests/tiergraph/baselines/containment-navigation.json"
sys.path.insert(0, str(ROOT))

from ipakit import Form, FormBuilder, IPAFeatures  # noqa: E402
from ipakit._cmu_graph import read as read_cmu  # noqa: E402
from ipakit._containment_projection import ContainmentProjection  # noqa: E402
from ipakit._gesture_graph import project as project_gestures  # noqa: E402
from ipakit._mora_graph import build as build_mora  # noqa: E402
from ipakit._panphon_graph import declaration as panphon_declaration  # noqa: E402
from ipakit._pinyin_graph import build as build_pinyin  # noqa: E402
from ipakit._rewrite_graph import (  # noqa: E402
    japanese_moraic_fixture,
    japanese_moraic_fixtures,
)
from ipakit._tiergraph import (  # noqa: E402
    Declarations,
    FeatureDeclaration,
    Graph,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder  # noqa: E402
from ipakit.form import _graph_from_compatibility  # noqa: E402


@dataclass(frozen=True)
class Coverage:
    fixtures: int
    events: int
    comparisons: int


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


def _adversarial_fixture(kind: str) -> Graph:
    relation_names = ("b", "a") if kind == "canonical-relation-order" else ("a", "b")
    declarations = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        tuple(
            RelationDeclaration(
                name,
                containment=True,
                acyclic=True,
                target_arity=(0, None) if kind == "empty-target" else (1, None),
                allow_empty_target=kind == "empty-target",
            )
            for name in relation_names
        ),
    )
    builder = GraphBuilder(declarations)
    root = builder.append_input_atom("item", {"label": "root"})
    first = builder.append_input_atom("item", {"label": "first"})
    second = builder.append_input_atom("item", {"label": "second"})
    if kind == "canonical-relation-order":
        builder.contain(root, (second,), relation="b")
        builder.contain(root, (first,), relation="a")
    elif kind == "shared-parent-incidence":
        builder.contain(root, (first,), relation="a")
        builder.contain(root, (first,), relation="b")
    else:
        builder.contain(root, (), relation="a")
    return builder.build()


def _legacy_containment_sample(form: Form) -> Graph:
    """Materialize only this legacy-oracle's build-scaffold fixture."""
    index = form.__dict__["_tiergraph_index"]
    projection = form._containment
    feature_names = frozenset(
        key for _, event in index.events.values() for key in event.features
    )
    tiers = tuple(
        TierDeclaration(name, feature_names) for name in projection.tier_names
    )
    containment = tuple(
        RelationDeclaration(name, acyclic=True, containment=True)
        for name in projection.containment_names
    )
    by_name = {value: key for key, value in projection.containment_names.items()}
    relations = tuple(
        Relation(
            tuple(projection.new_to_old[item] for item in relation.sources),
            by_name[relation.declaration],
            tuple(projection.new_to_old[item] for item in relation.targets),
        )
        for relation in form._graph.polyadic_relations
        if relation.declaration in by_name
    )
    return Graph(
        Declarations(
            tiers,
            tuple(FeatureDeclaration(name) for name in feature_names),
            containment,
        ),
        index.clock,
        relations,
        form.roots,
    )


@lru_cache(maxsize=1)
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
        (
            "fixture:canonical-relation-order",
            _adversarial_fixture("canonical-relation-order"),
        ),
        (
            "fixture:shared-parent-incidence",
            _adversarial_fixture("shared-parent-incidence"),
        ),
        ("fixture:empty-target", _adversarial_fixture("empty-target")),
        ("profile:ipa", _legacy_containment_sample(hierarchy.build())),
        ("profile:cmu", read_cmu(("K", "AE1", "T"))),
        ("profile:pinyin", build_pinyin("shui", "sh", "ui", 3)),
        ("profile:mora", build_mora(("to", "o"), "high")),
    ]
    native_form = Form.parse("ata", inventory)
    native = _graph_from_compatibility(native_form.units, native_form.intervals)
    graphs.append(("profile:gesture", project_gestures(native, inventory)))
    panphon_builder = GraphBuilder(panphon_declaration(()))
    for spelling in ("p", "a", "t"):
        panphon_builder.append_input_atom("segment", {"spelling": spelling})
    panphon = panphon_builder.build()
    graphs.append(("profile:panphon", panphon))
    graphs.extend(
        (
            f"profile:japanese-rewrite:{name}",
            _legacy_containment_sample(japanese_moraic_fixture(name, inventory)),
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


def _answers(graph: Graph) -> dict[str, object]:
    if isinstance(graph, tiergraph.Graph):
        raise NotImplementedError(
            "native tg.Graph containment adapter lands in Phase 1 (cmu)"
        )
    projected = ContainmentProjection.build(graph)
    answers: dict[str, object] = {}
    tiers = tuple(declaration.name for declaration in graph.declarations.tiers)
    for ref in graph.event_references():
        answers[ref] = {
            "direct": projected.direct_children(ref),
            "descendants": projected.descendants(ref),
            "leaves": projected.leaves(ref),
            "parents": projected.parents(ref),
            "ancestors": projected.ancestors(ref),
            "routes": _routes(projected, ref),
            "direct_by_tier": {
                tier: projected.direct_children(ref, tier) for tier in tiers
            },
            "descendants_by_tier": {
                tier: projected.descendants(ref, tier) for tier in tiers
            },
        }
    return answers


def _surface() -> dict[str, object]:
    functions = (
        RelationDeclaration.__post_init__,
        Graph._validate_relation,
        Graph._validate_endpoints,
        Graph._validate_acyclic,
        GraphBuilder.contain,
    )
    source = "\n".join(inspect.getsource(function) for function in functions)
    return {
        "relation_declaration_fields": [
            field.name for field in fields(RelationDeclaration)
        ],
        "constructor_validator_sha256": hashlib.sha256(source.encode()).hexdigest(),
    }


def _structural_class(graph: Graph) -> dict[str, object]:
    if isinstance(graph, tiergraph.Graph):
        raise NotImplementedError(
            "native tg.Graph containment adapter lands in Phase 1 (cmu)"
        )
    containment = {
        declaration.name
        for declaration in graph.declarations.relations
        if declaration.containment
    }
    relations = tuple(
        relation for relation in graph.relations if relation.name in containment
    )
    targets = [target for relation in relations for target in relation.targets]
    return {
        "containment_declarations": len(containment),
        "source_arities": sorted({len(relation.sources) for relation in relations}),
        "target_arities": sorted({len(relation.targets) for relation in relations}),
        "repeated_target_incidence": any(
            len(relation.targets) != len(set(relation.targets))
            for relation in relations
        ),
        "shared_targets": len(targets) != len(set(targets)),
        "target_tier_cardinalities": sorted(
            {
                len({graph.resolve(target).tier for target in relation.targets})
                for relation in relations
            }
        ),
    }


def _as_json(value: object) -> object:
    if isinstance(value, tuple):
        return [_as_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _as_json(item) for key, item in value.items()}
    return value


def verify() -> Coverage:
    payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if payload["population"]["surface"] != _surface():
        raise AssertionError(
            "containment constructor/validator surface drifted; regenerate and "
            "review the fixture-derived population"
        )
    fixture_count = event_count = comparison_count = 0
    seen: set[str] = set()
    for name, graph in corpus():
        if isinstance(graph, tiergraph.Graph):
            raise NotImplementedError(
                "native tg.Graph containment adapter lands in Phase 1 (cmu)"
            )
        expected = payload["fixtures"].get(name)
        if expected is None:
            raise AssertionError(f"containment golden has no named fixture {name!r}")
        seen.add(name)
        fixture_count += 1
        refs = graph.event_references()
        event_count += len(refs)
        comparison_count += sum(6 + 2 * len(graph.declarations.tiers) for _ in refs)
        if _as_json(_structural_class(graph)) != expected["class"]:
            raise AssertionError(
                f"{name}: structural class differs from committed golden"
            )
        if _as_json(_answers(graph)) != expected["answers"]:
            raise AssertionError(f"{name}: navigation differs from committed golden")
    stale = set(payload["fixtures"]) - seen
    if stale:
        raise AssertionError(
            f"containment golden has stale fixtures: {sorted(stale)!r}"
        )
    return Coverage(fixture_count, event_count, comparison_count)


if __name__ == "__main__":
    seed = os.environ.get("PYTHONHASHSEED")
    if seed != "0":
        raise SystemExit("PYTHONHASHSEED=0 is required")
    coverage = verify()
    print(
        f"containment oracle: {coverage.events} events over "
        f"{coverage.fixtures} fixtures; {coverage.comparisons} ordered comparisons; "
        f"matched committed golden; fixture-sample-bounded; PYTHONHASHSEED={seed}"
    )
