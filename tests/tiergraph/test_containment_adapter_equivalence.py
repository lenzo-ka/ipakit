"""Independent equivalence checks for the native containment adapter."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from ipakit._containment_projection import ContainmentProjection
from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder
from scripts.containment_oracle import (
    _answers,
    _as_json,
    _NativeContainment,
    _routes,
    _structural_class,
    corpus,
)

import tiergraph


def _embedded_cmu_fixture() -> Graph:
    """Build the pre-migration CMU shape without calling the native reader."""
    declarations = Declarations(
        (TierDeclaration("phone", frozenset({"phone", "stress"})),),
        (FeatureDeclaration("phone"), FeatureDeclaration("stress")),
        (),
    )
    builder = GraphBuilder(declarations)
    builder.append_input_atom("phone", {"phone": "K"})
    builder.append_input_atom("phone", {"phone": "AE", "stress": "primary"})
    builder.append_input_atom("phone", {"phone": "T"})
    return builder.build()


def _embedded_mora_fixture() -> Graph:
    """Build the pre-migration mora shape without calling the native builder."""
    declarations = Declarations(
        (
            TierDeclaration("mora", frozenset({"value"})),
            TierDeclaration("tone", frozenset({"tone"})),
        ),
        (FeatureDeclaration("value"), FeatureDeclaration("tone")),
        (
            RelationDeclaration(
                "associates-with",
                source_tiers=frozenset({"tone"}),
                target_tiers=frozenset({"mora"}),
                target_arity=(1, None),
            ),
        ),
    )
    builder = GraphBuilder(declarations)
    hosts = tuple(
        builder.append_input_atom("mora", {"value": value}) for value in ("to", "o")
    )
    tone = builder.add_event("tone", 0, {"tone": "high"}, duration=0)
    builder.relate((tone,), "associates-with", hosts)
    return builder.build()


def _normalize(value: object, native_to_embedded: Mapping[str, str]) -> object:
    """Translate only complete native item references, preserving all structure."""
    if isinstance(value, str):
        return native_to_embedded.get(value, value)
    if isinstance(value, tuple):
        return tuple(_normalize(item, native_to_embedded) for item in value)
    if isinstance(value, list):
        return [_normalize(item, native_to_embedded) for item in value]
    if isinstance(value, dict):
        return {
            _normalize(key, native_to_embedded): _normalize(item, native_to_embedded)
            for key, item in value.items()
        }
    return value


def _paths(
    name: str, graph: Graph | tiergraph.Graph
) -> tuple[Graph, tiergraph.Graph, dict[str, str]]:
    if isinstance(graph, tiergraph.Graph):
        assert name in {"profile:cmu", "profile:mora"}
        embedded = (
            _embedded_cmu_fixture()
            if name == "profile:cmu"
            else _embedded_mora_fixture()
        )
        native = graph
        embedded_by_tier = {
            tier: tuple(
                ref
                for ref in embedded.event_references()
                if embedded.resolve(ref).tier == tier
            )
            for tier in (
                declaration.name for declaration in embedded.declarations.tiers
            )
        }
        native_to_embedded = {
            str(ref): embedded_by_tier[ref.tier.local_name][ref.index]
            for ref in native.canonical_items()
        }
        return embedded, native, native_to_embedded

    embedded = graph
    projection = ContainmentProjection.build(embedded)
    return (
        embedded,
        projection.graph,
        {str(native): old for native, old in projection.new_to_old.items()},
    )


def _native_answers(
    native: tiergraph.Graph,
    embedded: Graph,
    native_to_embedded: Mapping[str, str],
) -> dict[str, object]:
    adapter = _NativeContainment.build(native)
    tiers = tuple(declaration.name for declaration in embedded.declarations.tiers)
    return {
        str(ref): {
            "direct": adapter.direct_children(str(ref)),
            "descendants": adapter.descendants(str(ref)),
            "leaves": adapter.leaves(str(ref)),
            "parents": adapter.parents(str(ref)),
            "ancestors": adapter.ancestors(str(ref)),
            "routes": _routes(adapter, str(ref)),
            "direct_by_tier": {
                tier: adapter.direct_children(str(ref), tier) for tier in tiers
            },
            "descendants_by_tier": {
                tier: adapter.descendants(str(ref), tier) for tier in tiers
            },
        }
        for ref in native.canonical_items()
        if str(ref) in native_to_embedded
    }


_CORPUS = corpus()


@pytest.mark.parametrize("name, graph", _CORPUS, ids=[name for name, _ in _CORPUS])
def test_native_adapter_equals_embedded_projection(
    name: str, graph: Graph | tiergraph.Graph
) -> None:
    embedded, native, native_to_embedded = _paths(name, graph)

    native_answers = _native_answers(native, embedded, native_to_embedded)
    assert _normalize(native_answers, native_to_embedded) == _answers(embedded)
    assert _as_json(_structural_class(native)) == _as_json(_structural_class(embedded))


def test_pinyin_polyadic_projection_is_admitted_and_equivalent() -> None:
    embedded = next(graph for name, graph in corpus() if name == "profile:pinyin")
    assert isinstance(embedded, Graph)
    projection = ContainmentProjection.build(embedded)
    adapter = _NativeContainment.build(projection.graph)
    native_to_embedded = {
        str(native): old for native, old in projection.new_to_old.items()
    }

    actual = {
        native_to_embedded[str(native)]: _normalize(
            {
                "direct": adapter.direct_children(str(native)),
                "descendants": adapter.descendants(str(native)),
                "leaves": adapter.leaves(str(native)),
                "parents": adapter.parents(str(native)),
                "ancestors": adapter.ancestors(str(native)),
            },
            native_to_embedded,
        )
        for native in projection.new_to_old
    }
    expected = {
        ref: {
            operation: answers[operation]
            for operation in (
                "direct",
                "descendants",
                "leaves",
                "parents",
                "ancestors",
            )
        }
        for ref, answers in _answers(embedded).items()
    }
    assert actual == expected
