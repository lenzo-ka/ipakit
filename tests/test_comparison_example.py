"""Ordering invariant for the clustered inventory comparison example."""

from __future__ import annotations

import ipakit
from scripts._comparison_order import aligned_orders
from scripts.compare_inventories import partition_selections


def test_shared_phones_lead_both_axes_at_the_same_indices() -> None:
    result = ipakit.phoneset_comparison(["p", "t", "k", "a"], ["a", "k", "s", "p"])
    shared = tuple(reversed(result.intersection))
    rows, columns = aligned_orders(
        result.intersection,
        result.only_a,
        result.only_b,
        shared,
        tuple(reversed(result.only_a)),
        tuple(reversed(result.only_b)),
    )

    row_index = {phone: index for index, phone in enumerate(result.a.phones)}
    column_index = {phone: index for index, phone in enumerate(result.b.phones)}
    for phone in result.intersection:
        assert rows.index(phone) == columns.index(phone)
    ordered_matrix = tuple(
        tuple(result.matrix[row_index[left]][column_index[right]] for right in columns)
        for left in rows
    )
    for index in range(len(shared)):
        assert ordered_matrix[index][index] == 1.0


def test_partition_seeding_is_optimal_and_refuses_when_sources_are_too_few() -> None:
    sources = ("a", "b", "c")
    uncovered_targets = ("x", "y")
    targets = ("x", "y", "z")
    scores = {
        ("a", "x"): 1.0,
        ("a", "y"): 0.9,
        ("b", "x"): 0.95,
        ("b", "y"): 0.0,
        ("c", "x"): 0.8,
        ("c", "y"): 0.7,
        ("a", "z"): 0.0,
        ("b", "z"): 0.0,
        ("c", "z"): 0.85,
    }

    partition = partition_selections(sources, uncovered_targets, targets, scores)
    assert not isinstance(partition, str)
    # Greedy target order would spend a on x and force c onto y.  The global
    # solution gives x to b, y to a, and lets c join z, which was already
    # covered before this side-only partition (for example, by an identity).
    assert {(item.source, item.target) for item in partition} == {
        ("a", "y"),
        ("b", "x"),
        ("c", "z"),
    }

    reverse = partition_selections(
        uncovered_targets,
        sources,
        sources,
        {(target, source): value for (source, target), value in scores.items()},
    )
    assert reverse == (
        "refused: partition has 2 side-only sources and 3 side-only targets; "
        "a surjection requires at least as many sources as targets"
    )
