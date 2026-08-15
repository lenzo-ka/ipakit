from ipakit._containment_projection import ContainmentProjection
from scripts.containment_oracle import corpus, verify


def test_exhaustive_ordered_containment_oracle() -> None:
    coverage = verify()
    assert coverage.fixtures >= 11
    assert coverage.events > 0
    assert coverage.comparisons > coverage.events
    assert coverage.changes == 2


def test_unknown_origin_compatibility_is_unchanged_in_oracle_corpus() -> None:
    graph = corpus()[0][1]
    projected = ContainmentProjection.build(graph)
    missing = "/clock/999/item/0"
    assert projected.direct_children(missing) == graph.direct_children(missing) == ()
    assert projected.descendants(missing) == graph.descendants(missing) == ()
    assert projected.leaves(missing) == graph.leaves(missing) == (missing,)
    assert projected.parents(missing) == graph.parents(missing) == ()
    assert projected.ancestors(missing) == graph.ancestors(missing) == ()
