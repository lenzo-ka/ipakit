"""Ordering invariant for the clustered inventory comparison example."""

from __future__ import annotations

import ipakit
from scripts._comparison_order import aligned_orders


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
