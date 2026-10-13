"""Range normalization shared by corpus matchers."""

from collections.abc import Iterable
from typing import Any


def result_ranges(
    payloads: Iterable[dict[str, Any]], name: str
) -> tuple[tuple[int, int], ...]:
    """Return sorted, deduplicated, merged ranges from match payloads."""
    values = sorted({tuple(pair) for payload in payloads for pair in payload[name]})
    result: list[tuple[int, int]] = []
    for start, end in values:
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return tuple(result)
