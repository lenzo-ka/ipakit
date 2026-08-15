import json
from pathlib import Path

import pytest
from ipakit._containment_projection import ContainmentProjection
from ipakit._tiergraph import (
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    Graph,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder
from scripts import containment_oracle
from scripts.containment_oracle import corpus, verify

from tiergraph import OrderedContainment, PolyadicRelationDeclaration


def test_exhaustive_ordered_containment_oracle() -> None:
    coverage = verify()
    assert coverage.fixtures >= 11
    assert coverage.events > 0
    assert coverage.comparisons > coverage.events


def test_projection_retains_polyadic_incidence_for_ordered_containment() -> None:
    graph = corpus()[0][1]
    projected = ContainmentProjection.build(graph)
    declarations = projected.graph.relation_declarations
    containment = tuple(
        declaration
        for declaration in declarations
        if isinstance(declaration, PolyadicRelationDeclaration)
    )

    assert len(containment) == 1
    assert projected.graph.relations == ()
    assert projected.graph.polyadic_relations
    assert isinstance(
        OrderedContainment(projected.graph, containment[0].name), OrderedContainment
    )


def test_unknown_origin_compatibility_is_unchanged_in_oracle_corpus() -> None:
    graph = corpus()[0][1]
    projected = ContainmentProjection.build(graph)
    missing = "/clock/999/item/0"
    assert projected.direct_children(missing) == ()
    assert projected.descendants(missing) == ()
    assert projected.leaves(missing) == (missing,)
    assert projected.parents(missing) == ()
    assert projected.ancestors(missing) == ()


def test_projection_names_and_refuses_joint_containment_instance() -> None:
    declarations = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        (
            RelationDeclaration(
                "contains",
                containment=True,
                acyclic=True,
                source_arity=(2, 2),
            ),
        ),
    )
    builder = GraphBuilder(declarations)
    a = builder.append_input_atom("item", {"label": "a"})
    c = builder.append_input_atom("item", {"label": "c"})
    d = builder.append_input_atom("item", {"label": "d"})
    builder.relate((a, c), "contains", (d,))
    graph = builder.build()

    with pytest.raises(
        ValueError,
        match=r"multi-source containment instance 0 \('contains'\)",
    ):
        ContainmentProjection.build(graph)


def test_projection_preserves_independent_containment_relations() -> None:
    name, graph = next(
        row for row in corpus() if row[0] == "fixture:cross-relation-cycle"
    )
    projected = ContainmentProjection.build(graph)

    assert name == "fixture:cross-relation-cycle"
    assert len(set(projected.containment_names.values())) == 2
    assert projected.descendants("/clock/0/item/0") == ("/clock/1/item/0",)
    assert projected.ancestors("/clock/0/item/0") == (
        "/clock/1/item/0",
        "/clock/0/item/0",
    )


def test_adversarial_constructions_match_legacy_oracle_answers() -> None:
    graphs = dict(corpus())
    ordered = ContainmentProjection.build(graphs["fixture:canonical-relation-order"])
    repeated = ContainmentProjection.build(graphs["fixture:shared-parent-incidence"])
    empty = ContainmentProjection.build(graphs["fixture:empty-target"])

    root = "/clock/0/item/0"
    first = "/clock/1/item/0"
    second = "/clock/2/item/0"
    assert ordered.direct_children(root) == (first, second)
    assert repeated.parents(first) == (root, root)
    assert empty.direct_children(root) == ()
    assert empty.leaves(root) == (root,)


def test_boundary_target_containment_is_refused_by_relation_name() -> None:
    declarations = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        (
            RelationDeclaration(
                "boundary-owns",
                containment=True,
                acyclic=True,
                target_kinds=frozenset({EndpointKind.COARSE_TICK}),
            ),
        ),
    )
    builder = GraphBuilder(declarations)
    builder.append_input_atom("item", {"label": "root"})
    base = builder.build()
    graph = Graph(
        base.declarations,
        base.clock,
        (Relation(("/clock/0/item/0",), "boundary-owns", ("/clock/1",)),),
    )

    recorded = json.loads(containment_oracle.GOLDEN.read_text(encoding="utf-8"))
    assert recorded["refused_constructions"]["boundary-owns"][
        "legacy_direct_children"
    ] == ["/clock/1"]
    with pytest.raises(
        ValueError,
        match=(
            "boundary-endpoint containment relation 'boundary-owns': "
            "tiergraph OrderedContainment supports item endpoints only"
        ),
    ):
        ContainmentProjection.build(graph)


@pytest.mark.parametrize("operation", ("descendants", "leaves", "ancestors"))
def test_reachability_operations_delegate_to_ordered_containment(
    operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = dict(corpus())["fixture:diamond"]
    projected = ContainmentProjection.build(graph)

    class Sentinel(RuntimeError):
        pass

    def stop(*args: object, **kwargs: object) -> object:
        raise Sentinel(operation)

    monkeypatch.setattr(OrderedContainment, operation, stop)
    reference = (
        graph.event_references()[-1]
        if operation == "ancestors"
        else graph.event_references()[0]
    )
    with pytest.raises(Sentinel, match=operation):
        getattr(projected, operation)(reference)


def test_oracle_refuses_mutated_fixture_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.loads(containment_oracle.GOLDEN.read_text(encoding="utf-8"))
    payload["fixtures"]["fixture:heterogeneous"]["class"][
        "containment_declarations"
    ] = 999
    corrupted = tmp_path / "containment-navigation.json"
    corrupted.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(containment_oracle, "GOLDEN", corrupted)

    with pytest.raises(
        AssertionError,
        match="fixture:heterogeneous: structural class differs",
    ):
        containment_oracle.verify()
