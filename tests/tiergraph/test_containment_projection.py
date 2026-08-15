from ipakit._containment_projection import ContainmentProjection
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
    assert projected.direct_children(missing) == graph.direct_children(missing) == ()
    assert projected.descendants(missing) == graph.descendants(missing) == ()
    assert projected.leaves(missing) == graph.leaves(missing) == (missing,)
    assert projected.parents(missing) == graph.parents(missing) == ()
    assert projected.ancestors(missing) == graph.ancestors(missing) == ()
