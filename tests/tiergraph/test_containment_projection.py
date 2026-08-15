import pytest
from ipakit._containment_projection import ContainmentProjection
from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder
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
