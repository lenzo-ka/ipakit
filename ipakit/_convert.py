"""Shared tokenization/conversion helpers.

Several converters (feature parsing, stress normalization, IPA validation, CMU,
X-SAMPA and phonemap conversion) all walk a string left to right, taking the
longest substring that is a key in some lookup. That one loop is ``longest_match``.

They also share an opt-in ``strict`` error policy: collect the symbols that could
not be converted and, when strict, raise via ``require_convertible``.

Per-site state (diacritic collection, stress handling, validation tracking)
stays in the caller; only these shared steps live here.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from .constants import TIE_BAR


def require_convertible(skipped: list[str], what: str) -> None:
    """Raise ``ValueError`` if any input symbols could not be converted.

    Used by converters called with ``strict=True``. ``what`` names the
    conversion, e.g. ``"to CMU ARPABET"`` or ``"IPA -> X-SAMPA"``.
    """
    if skipped:
        unknown = sorted(set(skipped))
        raise ValueError(f"Cannot convert {what}: unknown symbols {unknown}")


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
    every tie-bar-separated part is a non-empty member of ``tie_set`` (handles
    composed phones like ``t͡ʃ`` that are not themselves keys). A lone or dangling
    tie bar -- which produces an empty part -- is therefore not a match, so the
    caller can flag it. ``max_len`` must be wide enough to span such composites,
    so it is a deliberate bound, not the longest key length.
    """
    for length in range(min(max_len, len(text) - start), 0, -1):
        candidate = text[start : start + length]
        if candidate in lookup:
            return candidate, length
        if tie_set is not None and TIE_BAR in candidate:
            parts = candidate.split(TIE_BAR)
            if all(p in tie_set for p in parts):
                return candidate, length
    return None, 0


def convert_greedy(
    text: str,
    lookup: Mapping[str, str],
    *,
    max_len: int | None = None,
    strict: bool = False,
    what: str = "",
) -> list[str]:
    """Greedy longest-match conversion of ``text`` through a string->string map.

    Walks left to right, replacing the longest matching key with its value;
    unmatched characters are skipped. With ``strict=True`` the skipped symbols
    raise ``ValueError`` via ``require_convertible`` (``what`` names the
    direction). ``max_len`` defaults to the longest key length.
    """
    if not lookup:
        return []
    if max_len is None:
        max_len = max(len(k) for k in lookup)
    out: list[str] = []
    skipped: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        key, length = longest_match(text, i, lookup, max_len)
        if key is not None:
            out.append(lookup[key])
            i += length
        else:
            skipped.append(text[i])
            i += 1
    if strict:
        require_convertible(skipped, what)
    return out
