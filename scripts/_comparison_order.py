"""Pure-Python axis assembly for the clustered inventory example."""

from __future__ import annotations

from collections.abc import Sequence


def aligned_orders(
    intersection: Sequence[str],
    only_a: Sequence[str],
    only_b: Sequence[str],
    clustered_intersection: Sequence[str],
    clustered_only_a: Sequence[str],
    clustered_only_b: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Put one clustered intersection before each side's clustered remainder."""

    def require_permutation(
        original: Sequence[str], clustered: Sequence[str], label: str
    ) -> tuple[str, ...]:
        if len(clustered) != len(original) or set(clustered) != set(original):
            raise ValueError(f"{label} clustering did not preserve its phone group")
        return tuple(clustered)

    shared = require_permutation(intersection, clustered_intersection, "intersection")
    left = require_permutation(only_a, clustered_only_a, "A-only")
    right = require_permutation(only_b, clustered_only_b, "B-only")
    return shared + left, shared + right
