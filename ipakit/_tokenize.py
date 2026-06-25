"""Shared greedy longest-match scanner for IPA/symbol tokenization.

Several converters (feature parsing, stress normalization, IPA validation, CMU
and phonemap conversion) all walk a string left to right, taking the longest
substring that is a key in some lookup. This is that one loop, extracted.

Per-site state (diacritic collection, stress handling, validation tracking)
stays in the caller; only the match step is shared.
"""

from __future__ import annotations

from collections.abc import Collection

from .constants import TIE_BAR


def longest_match(
    text: str,
    start: int,
    lookup: Collection[str],
    max_len: int,
    tie_set: Collection[str] | None = None,
) -> tuple[str | None, int]:
    """Find the longest ``text[start:]`` prefix (up to ``max_len``) in ``lookup``.

    Returns ``(matched_substring, length)``, or ``(None, 0)`` if nothing matches.
    The caller maps the substring to a value (``lookup[match]``) when needed.

    If ``tie_set`` is given, a candidate containing the tie bar also matches when
    every tie-bar-separated part is in ``tie_set`` (handles composed phones like
    ``t͡ʃ`` that are not themselves keys). ``max_len`` must be wide enough to span
    such composites, so it is a deliberate bound, not the longest key length.
    """
    for length in range(min(max_len, len(text) - start), 0, -1):
        candidate = text[start : start + length]
        if candidate in lookup:
            return candidate, length
        if tie_set is not None and TIE_BAR in candidate:
            parts = candidate.split(TIE_BAR)
            if all(p in tie_set or p == "" for p in parts):
                return candidate, length
    return None, 0
