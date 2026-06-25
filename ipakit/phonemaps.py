"""Generic phonemap loading and conversion utilities."""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET

from .constants import PHONEMAPS_DIR, TIE_BAR


@functools.lru_cache(maxsize=8)
def _load_phonemap(name: str) -> tuple[dict[str, str], dict[str, str]]:
    """Load a phonemap XML file and return (ipa_to_target, target_to_ipa) dicts.

    Args:
        name: Name of the phonemap (e.g., "timit", "kirshenbaum")

    Returns:
        Tuple of (ipa_to_target, target_to_ipa) mapping dicts
    """
    xml_path = PHONEMAPS_DIR / f"{name}.xml"
    if not xml_path.exists():
        raise FileNotFoundError(f"Phonemap not found: {xml_path}")

    root = ET.parse(xml_path).getroot()

    # Determine the target attribute name from the 'to' attribute
    target_name = root.get("to", name)

    ipa_to_target: dict[str, str] = {}
    target_to_ipa: dict[str, str] = {}

    def load_section(section: ET.Element) -> None:
        for elem in section.findall("map"):
            ipa = elem.get("ipa", "")
            target = elem.get(target_name, "")
            if ipa and target:
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

    return ipa_to_target, target_to_ipa


def _normalize_for_map(ipa: str, ipa_to_target: dict[str, str]) -> str:
    """Normalize IPA string by adding tie bars where the map expects them."""
    # Check if any keys have tie bars
    for key in ipa_to_target:
        if TIE_BAR in key:
            # Try to add tie bar if the untied version is in the string
            untied = key.replace(TIE_BAR, "")
            if untied in ipa and key not in ipa:
                ipa = ipa.replace(untied, key)
    return ipa


def ipa_to_phonemap(ipa: str, phonemap: str) -> list[str]:
    """Convert IPA string to target phonemap symbols.

    Args:
        ipa: IPA string to convert
        phonemap: Name of phonemap ("timit", "kirshenbaum")

    Returns:
        List of target symbols
    """
    ipa_to_target, _ = _load_phonemap(phonemap)
    ipa = _normalize_for_map(ipa, ipa_to_target)

    result = []
    i = 0

    while i < len(ipa):
        # Try longest match first
        matched = False
        for length in range(min(6, len(ipa) - i), 0, -1):
            candidate = ipa[i : i + length]
            if candidate in ipa_to_target:
                result.append(ipa_to_target[candidate])
                i += length
                matched = True
                break

        if not matched:
            # Skip unknown characters (stress markers, etc.)
            i += 1

    return result


def phonemap_to_ipa(symbols: list[str], phonemap: str) -> str:
    """Convert phonemap symbols to IPA string.

    Args:
        symbols: List of phonemap symbols
        phonemap: Name of phonemap ("timit", "kirshenbaum")

    Returns:
        IPA string
    """
    _, target_to_ipa = _load_phonemap(phonemap)

    result = []
    for symbol in symbols:
        if symbol in target_to_ipa:
            result.append(target_to_ipa[symbol])
        # Skip unknown symbols

    return "".join(result)


# --- TIMIT-specific functions ---


def to_timit(ipa: str) -> list[str]:
    """Convert IPA string to TIMIT phoneset symbols.

    TIMIT uses a 61-phone set with lowercase symbols.
    Commonly used in speech recognition research.

    Examples:
        >>> to_timit("kæt")
        ['k', 'ae', 't']
        >>> to_timit("hɛloʊ")
        ['hh', 'eh', 'l', 'ow']
    """
    return ipa_to_phonemap(ipa, "timit")


def from_timit(symbols: list[str]) -> str:
    """Convert TIMIT phoneset symbols to IPA string.

    Examples:
        >>> from_timit(["k", "ae", "t"])
        'kæt'
    """
    return phonemap_to_ipa(symbols, "timit")


# --- Kirshenbaum-specific functions ---


def to_kirshenbaum(ipa: str) -> str:
    """Convert IPA string to Kirshenbaum ASCII-IPA notation.

    Kirshenbaum is an ASCII representation of IPA for plain text.
    Uses uppercase for IPA extensions and special character combinations.

    Examples:
        >>> to_kirshenbaum("ʃɑk")
        'SAk'
        >>> to_kirshenbaum("kæt")
        'k&t'
    """
    symbols = ipa_to_phonemap(ipa, "kirshenbaum")
    return "".join(symbols)


def from_kirshenbaum(text: str) -> str:
    """Convert Kirshenbaum ASCII-IPA notation to IPA string.

    Parses Kirshenbaum notation and converts to proper IPA Unicode.

    Examples:
        >>> from_kirshenbaum("SAk")
        'ʃɑk'
        >>> from_kirshenbaum("k&t")
        'kæt'
    """
    _, target_to_ipa = _load_phonemap("kirshenbaum")

    result = []
    i = 0

    while i < len(text):
        matched = False
        # Try longest match first (some Kirshenbaum symbols are multi-char)
        for length in range(min(8, len(text) - i), 0, -1):
            candidate = text[i : i + length]
            if candidate in target_to_ipa:
                result.append(target_to_ipa[candidate])
                i += length
                matched = True
                break

        if not matched:
            # Keep unknown characters as-is
            i += 1

    return "".join(result)
