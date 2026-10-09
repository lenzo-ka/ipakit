"""Shared tokenization/conversion helpers.

Several converters (feature parsing, stress normalization, IPA validation, CMU,
X-SAMPA and phonemap conversion) all walk a string left to right, taking the
longest substring that is a key in some lookup. That one loop is ``longest_match``.

They also share an opt-in ``strict`` error policy: collect the symbols that could
not be converted and, when strict, raise via ``require_convertible``.

The ones whose input is an IPA string share one more step: ``resolve_aliases``,
the same alias resolution ``IPAFeatures.parse`` runs. Their tables are keyed on
house-canonical spellings, so without it an accepted alias spelling matches
nothing and is dropped.

Per-site state (diacritic collection, stress handling, validation tracking)
stays in the caller; only these shared steps live here.
"""

from __future__ import annotations

import ast
import functools
import re
import warnings
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .features import IPAFeatures
    from .form import Form


class InputLossWarning(UserWarning):
    """A public soft read returned an answer after losing supplied input."""


@functools.lru_cache(maxsize=1)
def ipa_features() -> IPAFeatures:
    """The inventory these helpers read, built on first use.

    Imported lazily because ``features`` imports this module.
    """
    from .features import IPAFeatures

    return IPAFeatures()


def resolve_aliases(ipa: str) -> str:
    """Resolve registered ligature aliases in an IPA string.

    The string converters match raw IPA against their own tables rather
    than through :meth:`IPAFeatures.parse`, so they have to run the parser's
    alias resolution themselves -- through this one call, not a private copy,
    or the two spellings of one word drift apart. ``ʧ`` is an input spelling
    this package documents as accepted; a converter matching it against a
    table keyed on ``t͡ʃ`` found nothing, dropped it, and returned a word one
    phoneme short and well formed enough to pass for an answer.
    """
    return ipa_features().expand_ligatures(ipa)


def require_convertible(
    skipped: list[str], what: str, *, preserve_order: bool = False
) -> None:
    """Raise ``ValueError`` if any input symbols could not be converted.

    Used by converters called with ``strict=True``. ``what`` names the
    conversion, e.g. ``"to CMU ARPABET"`` or ``"IPA -> X-SAMPA"``.
    """
    if skipped:
        unknown = (
            list(dict.fromkeys(skipped)) if preserve_order else sorted(set(skipped))
        )
        raise ValueError(f"Cannot convert {what}: unknown symbols {unknown}")


def report_unconvertible(
    skipped: list[str],
    what: str,
    *,
    strict: bool,
    stacklevel: int = 3,
    preserve_order: bool = False,
) -> None:
    """Say what the conversion could not carry: raise, or warn.

    The converters' half of the policy ``docs/ties.md`` states for the
    parser -- **dropped audibly, never silently**. They had only the
    first half: they collected what they skipped and spoke about it
    solely under their own ``strict=``, so every default-path
    conversion returned a well-formed answer one or more symbols short
    and said nothing. ``ipakit convert to-cmu k@t`` printed ``K T`` and
    exited 0, which is the same defect the parser's warning exists to
    prevent, on the same input, one module over.

    A warning rather than a return value because that is what the
    parser already does, and because the report then reaches the exit
    status for free: the CLI promotes an untyped ``UserWarning`` raised
    from inside this package (other than a declared non-input warning), or
    any ``InputLossWarning`` wherever its ``stacklevel`` points, to status 3. So the six ``convert`` subcommands
    join the existing policy with no change to the command line at all.

    Raising and warning live in one function so the two branches cannot
    drift into disagreeing about what counts as a loss -- the recurring
    failure this repo has fixed twice.
    """
    if not skipped:
        return
    if strict:
        require_convertible(skipped, what, preserve_order=preserve_order)
        return
    unknown = list(dict.fromkeys(skipped)) if preserve_order else sorted(set(skipped))
    warnings.warn(
        f"dropped {len(skipped)} unconvertible symbol(s) "
        f"{unknown} converting {what}: the result is shorter "
        "than the input. Pass strict=True to raise instead.",
        InputLossWarning,
        stacklevel=stacklevel,
    )


def longest_match(
    text: str,
    start: int,
    lookup: Collection[str],
    max_len: int,
    tie_set: Collection[str] | None = None,
    ties: Collection[str] = (),
) -> tuple[str | None, int]:
    """Find the longest ``text[start:]`` prefix (up to ``max_len``) in ``lookup``.

    Returns ``(matched_substring, length)``, or ``(None, 0)`` if nothing matches.
    The caller maps the substring to a value (``lookup[match]``) when needed.

    If ``tie_set`` is given, a candidate containing a tie bar also matches when
    every tie-separated part is a non-empty member of ``tie_set`` (handles
    composed phones like ``t͡ʃ`` that are not themselves keys). A lone or dangling
    tie bar -- which produces an empty part -- is therefore not a match, so the
    caller can flag it. ``max_len`` must be wide enough to span such composites,
    so it is a deliberate bound, not the longest key length.

    ``ties`` names the characters that bind, and comes from the caller
    rather than from a constant here: which glyphs are ties is declared
    in ipa.xml (``IPAFeatures.tie_bars``), and every caller passing a
    ``tie_set`` is reading its own inventory anyway. Without it nothing
    spans a juncture, which is what a caller matching a table that has no
    tied keys wants.
    """
    for length in range(min(max_len, len(text) - start), 0, -1):
        candidate = text[start : start + length]
        if candidate in lookup:
            return candidate, length
        if tie_set is not None and any(t in candidate for t in ties):
            parts = [candidate]
            for glyph in ties:
                parts = [piece for part in parts for piece in part.split(glyph)]
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
    skipped: list[str] | None = None,
    report: bool = True,
) -> list[str]:
    """Greedy longest-match conversion of ``text`` through a string->string map.

    Walks left to right, replacing the longest matching key with its value;
    unmatched characters are reported through ``report_unconvertible`` --
    ``strict=True`` raises, and the default path warns rather than dropping
    them in silence (``what`` names the direction). ``max_len`` defaults to
    the longest key length.
    """
    if not lookup:
        return []
    if max_len is None:
        max_len = max(len(k) for k in lookup)
    out: list[str] = []
    lost: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        key, length = longest_match(text, i, lookup, max_len)
        if key is not None:
            out.append(lookup[key])
            i += length
        else:
            lost.append(text[i])
            i += 1
    # stacklevel 4: report_unconvertible -> here -> the converter that
    # called it (to_kirshenbaum, to_xsampa, ...) -> that converter's
    # caller, which is the frame worth naming.
    if skipped is not None:
        skipped.extend(lost)
    if report:
        report_unconvertible(lost, what, strict=strict, stacklevel=4)
    return out


_PARSER_LOSS = re.compile(r"dropped (\d+) .*? (\[[^\n]*?\]) while parsing IPA")


def structured_ipa_read(text: str) -> tuple[Form, list[str]]:
    """Read IPA once while turning parser losses into converter-owned losses.

    A converter is one diagnostic boundary.  The IPA reader remains the sole
    tokenizer, but its warnings are captured here so a converter entry point
    never leaks a parser-framed warning (or raises before later units are read).
    """

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        form = ipa_features().read(text, strict=False)
    lost: list[str] = []
    for warning in caught:
        match = _PARSER_LOSS.search(str(warning.message))
        if match is None:
            warnings.warn(warning.message, warning.category, stacklevel=2)
            continue
        count = int(match.group(1))
        values = [str(value) for value in ast.literal_eval(match.group(2))]
        occurrences = [value for value in values for _ in range(text.count(value))]
        lost.extend(occurrences if len(occurrences) == count else values)
    return form, lost


def convert_written_ipa(
    text: str,
    lookup: Mapping[str, str],
    *,
    what: str,
    strict: bool,
    stacklevel: int = 4,
) -> list[str]:
    """Convert IPA in written order under one diagnostic boundary.

    Parsing may attach a mark to a neighboring unit and respell that unit in
    semantic order. A lossy notation still has to name omissions where the
    caller wrote them, so string conversion walks the resolved source directly.
    """

    source = "".join("#" if character.isspace() else character for character in text)
    lost: list[str] = []
    result = convert_greedy(source, lookup, skipped=lost, report=False)
    # stacklevel 4: reporter -> this route -> public converter -> caller.
    report_unconvertible(
        lost,
        what,
        strict=strict,
        stacklevel=stacklevel,
        preserve_order=True,
    )
    return result
