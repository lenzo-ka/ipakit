"""Generic phonemap loading and conversion utilities."""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET

from ._convert import (
    convert_greedy,
    convert_structured_ipa,
    ipa_features,
    report_unconvertible,
    resolve_aliases,
)
from .constants import PHONEMAPS_DIR


@functools.lru_cache(maxsize=8)
def _load_phonemap(name: str) -> tuple[dict[str, str], dict[str, str]]:
    """Load a phonemap XML file and return (ipa_to_target, target_to_ipa) dicts.

    The document's ``to`` attribute names the column its rows write the
    target spelling in, and that is the only place it is said. There is no
    fallback to the file's stem: a stem agrees with the column in some
    tables and not others, so a reader holding two sources for one fact
    takes the wrong one wherever they part company and hands back a table
    of nothing.

    A phonemap that maps nothing is not a phonemap, so this raises rather
    than warning. Two empty dicts are a well-formed answer that every
    caller downstream reads as "no mapping exists for anything" instead of
    "this file did not load", which is the silent wrong answer
    ``docs/reviewing.md`` is about. These files ship with the package, so a
    column no row spells is a packaging or declaration error rather than
    anything a caller did or can respond to, and the place to say so is
    the load, where the document can still be named.

    Args:
        name: Name of the phonemap (e.g., "timit", "kirshenbaum")

    Returns:
        Tuple of (ipa_to_target, target_to_ipa) mapping dicts

    Raises:
        FileNotFoundError: if there is no such phonemap.
        ValueError: if the document names no target column, if a row fails
            to spell the column the document names, or if it has no rows.
    """
    xml_path = PHONEMAPS_DIR / f"{name}.xml"
    if not xml_path.exists():
        raise FileNotFoundError(f"Phonemap not found: {xml_path}")

    root = ET.parse(xml_path).getroot()

    target_name = root.get("to")
    if not target_name:
        raise ValueError(
            f"{xml_path.name} declares no `to`, so which of its attributes "
            f"carries the target spelling is unstated and nothing can be read "
            f"out of it"
        )

    ipa_to_target: dict[str, str] = {}
    target_to_ipa: dict[str, str] = {}
    unread: list[dict[str, str]] = []

    def load_section(section: ET.Element) -> None:
        for elem in section.findall("map"):
            ipa = elem.get("ipa", "")
            target = elem.get(target_name, "")
            if not target:
                # Per row rather than only over the whole table, so one row
                # spelling the column differently from its neighbours is as
                # loud as a whole document doing it.
                unread.append(dict(elem.attrib))
            elif ipa:
                # First mapping wins (don't overwrite)
                if ipa not in ipa_to_target:
                    ipa_to_target[ipa] = target
                if target not in target_to_ipa:
                    target_to_ipa[target] = ipa

    # Load main mappings
    load_section(root)

    # Load extras section if present
    if (extras := root.find("extras")) is not None:
        load_section(extras)

    if unread:
        raise ValueError(
            f"{xml_path.name} maps to `{target_name}`, but these rows spell no "
            f"such attribute, so they map nothing: {unread}"
        )
    if not ipa_to_target:
        raise ValueError(f"{xml_path.name} has no rows, so it maps nothing")

    return ipa_to_target, target_to_ipa


def _normalize_for_map(ipa: str, ipa_to_target: dict[str, str]) -> str:
    """Normalize IPA string by adding tie bars where the map expects them."""
    # Which characters tie is declared in ipa.xml, so it is read from
    # there (`IPAFeatures.tie_bars`) rather than restated here.
    ties = ipa_features().tie_bars
    for key in ipa_to_target:
        if ties & set(key):
            # Try to add tie bar if the untied version is in the string
            untied = key
            for glyph in ties:
                untied = untied.replace(glyph, "")
            if untied in ipa and key not in ipa:
                ipa = ipa.replace(untied, key)
    return ipa


def ipa_to_phonemap(ipa: str, phonemap: str, strict: bool = False) -> list[str]:
    """Convert IPA string to target phonemap symbols.

    Args:
        ipa: IPA string to convert
        phonemap: Name of phonemap ("timit", "kirshenbaum")
        strict: If True, raise ValueError for unconvertible symbols instead of
            skipping them.

    Returns:
        List of target symbols
    """
    ipa_to_target, _ = _load_phonemap(phonemap)
    ipa = resolve_aliases(ipa)
    if ipa in ipa_to_target:
        return [ipa_to_target[ipa]]
    # The generic phonemap contract historically repairs an omitted tie when
    # a table declares only the tied sequence (notably TIMIT ``oʊ`` -> OW).
    # That compatibility normalization is necessarily string-level because
    # it changes where the structured segment boundary will be read.
    ipa = _normalize_for_map(ipa, ipa_to_target)
    return convert_structured_ipa(
        ipa,
        ipa_to_target,
        strict=strict,
        what=f"IPA -> {phonemap}",
        stacklevel=5,
    )


def phonemap_to_ipa(symbols: list[str], phonemap: str, strict: bool = False) -> str:
    """Convert phonemap symbols to IPA string.

    Args:
        symbols: List of phonemap symbols
        phonemap: Name of phonemap ("timit", "kirshenbaum")
        strict: If True, raise ValueError for unknown symbols; otherwise
            they are dropped with a warning naming them.

    Returns:
        IPA string
    """
    _, target_to_ipa = _load_phonemap(phonemap)

    result = []
    skipped = []
    for symbol in symbols:
        if symbol in target_to_ipa:
            result.append(target_to_ipa[symbol])
        else:
            skipped.append(symbol)

    report_unconvertible(skipped, f"{phonemap} -> IPA", strict=strict)
    return "".join(result)


# --- TIMIT-specific functions ---


def to_timit(ipa: str, strict: bool = False) -> list[str]:
    """Convert IPA string to TIMIT phoneset symbols.

    TIMIT uses a 61-phone set with lowercase symbols.
    Commonly used in speech recognition research. With ``strict=True``, raise
    ``ValueError`` on unconvertible symbols instead of skipping them.

    Examples:
        >>> to_timit("kæt")
        ['k', 'ae', 't']
        >>> to_timit("hɛloʊ")
        ['hh', 'eh', 'l', 'ow']
    """
    return ipa_to_phonemap(ipa, "timit", strict=strict)


def from_timit(symbols: list[str], strict: bool = False) -> str:
    """Convert TIMIT phoneset symbols to IPA string.

    With ``strict=True``, raise ``ValueError`` on unknown symbols.

    Examples:
        >>> from_timit(["k", "ae", "t"])
        'kæt'
    """
    return phonemap_to_ipa(symbols, "timit", strict=strict)


# --- Kirshenbaum-specific functions ---


def to_kirshenbaum(ipa: str, strict: bool = False) -> str:
    """Convert IPA string to Kirshenbaum ASCII-IPA notation.

    Kirshenbaum is an ASCII representation of IPA for plain text. Uses uppercase
    for IPA extensions and special character combinations. With ``strict=True``,
    raise ``ValueError`` on unconvertible symbols instead of skipping them.

    Examples:
        >>> to_kirshenbaum("ʃɑk")
        'SAk'
        >>> to_kirshenbaum("kæt")
        'k&t'
    """
    symbols = ipa_to_phonemap(ipa, "kirshenbaum", strict=strict)
    return "".join(symbols)


def from_kirshenbaum(text: str, strict: bool = False) -> str:
    """Convert Kirshenbaum ASCII-IPA notation to IPA string.

    Parses Kirshenbaum notation and converts to proper IPA Unicode. With
    ``strict=True``, raise ``ValueError`` on unknown symbols instead of skipping.

    Examples:
        >>> from_kirshenbaum("SAk")
        'ʃɑk'
        >>> from_kirshenbaum("k&t")
        'kæt'
    """
    _, target_to_ipa = _load_phonemap("kirshenbaum")
    return "".join(
        convert_greedy(text, target_to_ipa, strict=strict, what="Kirshenbaum -> IPA")
    )
