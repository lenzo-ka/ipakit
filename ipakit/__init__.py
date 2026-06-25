"""ipakit - IPA phonetic features library.

Simple API:
    import ipakit as ipa

    ipa.distance("p", "b")              # 0.12
    ipa.features("p")                   # {'manner': 'plosive', ...}
    ipa.to_cmu("ˈhɛloʊ")                # ['HH', 'EH1', 'L', 'OW0']
    ipa.to_ipa(["HH", "EH1", "L"])      # 'ˈhɛl'
    ipa.tokenize("t͡ʃe͡ɪnd͡ʒ")          # ['t͡ʃ', 'e͡ɪ', 'n', 'd͡ʒ']
    ipa.normalize("tʃ eɪ n dʒ")         # 't͡ʃe͡ɪnd͡ʒ'

Class API:
    from ipakit import IPAFeatures, CMUMapper
"""

from __future__ import annotations

import functools
from pathlib import Path

__version__ = "0.1.0"

# Re-export classes
from .constants import (
    DATA_DIR,
    DEFAULT_CMU_MAP,
    DEFAULT_IPA_FEATS,
    PHONEMAPS_DIR,
    STRESS_MARKERS,
    TIE_BAR,
)
from .distance import WordDistanceResult
from .features import IPAFeatures
from .mapper import CMUMapper
from .models import Feature, Phone, PhoneMapping, Phoneset
from .phonemaps import from_kirshenbaum, from_timit, to_kirshenbaum, to_timit

# =============================================================================
# Module-level API (lazy singletons)
# =============================================================================


@functools.lru_cache(maxsize=1)
def _get_ipa() -> IPAFeatures:
    return IPAFeatures()


@functools.lru_cache(maxsize=1)
def _get_cmu() -> CMUMapper:
    return CMUMapper()


def load_ipa_features(xml_path: Path = DEFAULT_IPA_FEATS) -> IPAFeatures:
    """Convenience function to load IPA features."""
    return IPAFeatures(xml_path)


# --- Distance & Features ---


def distance(phone1: str, phone2: str) -> float:
    """Compute phonetic distance between two IPA phones (0.0-1.0)."""
    return _get_ipa().distance(phone1, phone2)


def word_distance(
    ipa1: str,
    ipa2: str,
    weighted: bool = True,
    return_alignment: bool = False,
) -> WordDistanceResult:
    """Compute phonetic edit distance between two IPA words.

    Uses Levenshtein-style dynamic programming with phonetic feature costs.

    Args:
        ipa1: First IPA string
        ipa2: Second IPA string
        weighted: If True, use feature distance for substitution costs.
        return_alignment: If True, include the alignment path in result.

    Returns:
        WordDistanceResult with distance, similarity, and optional alignment.

    Examples:
        >>> ipakit.word_distance("kæt", "kæd")
        WordDistanceResult(distance=0.04..., similarity=0.98..., alignment=None)
        >>> ipakit.word_distance("kæt", "dɒɡ")
        WordDistanceResult(distance=..., similarity=..., alignment=None)
    """
    return _get_ipa().word_distance(
        ipa1, ipa2, weighted=weighted, return_alignment=return_alignment
    )


def word_similarity(ipa1: str, ipa2: str, weighted: bool = True) -> float:
    """Compute phonetic similarity between two IPA words.

    Returns a value from 0.0 (completely different) to 1.0 (identical).
    Similarity = 1 - (edit_distance / max_length), with lower bound of 0.

    Args:
        ipa1: First IPA string
        ipa2: Second IPA string
        weighted: If True, use feature distance for substitution costs.

    Examples:
        >>> ipakit.word_similarity("kæt", "kæd")
        0.98...
        >>> ipakit.word_similarity("kæt", "dɒɡ")
        0.3...
    """
    return _get_ipa().word_similarity(ipa1, ipa2, weighted=weighted)


def features(phone: str, with_defaults: bool = True) -> dict[str, str]:
    """Get phonetic features for an IPA phone."""
    return _get_ipa().get_features(phone, with_defaults=with_defaults)


def features_from_cmu(
    cmu_symbols: list[str], with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get feature bundles from CMU ARPABET symbols."""
    ipa_str = _get_cmu().cmu_to_ipa(cmu_symbols)
    return _get_ipa().compose(ipa_str, with_defaults=with_defaults)


@functools.lru_cache(maxsize=1)
def _get_xsampa_map() -> dict[str, str]:
    """Load X-SAMPA to IPA mapping."""
    import xml.etree.ElementTree as ET

    from .constants import PHONEMAPS_DIR

    xsampa_file = PHONEMAPS_DIR / "xsampa.xml"
    if not xsampa_file.exists():
        return {}
    root = ET.parse(xsampa_file).getroot()
    mapping: dict[str, str] = {}
    for m in root.findall("map"):
        xs, ip = m.get("xsampa"), m.get("ipa")
        if xs and ip:
            mapping[xs] = ip
    return mapping


def xsampa_to_ipa(xsampa: str) -> str:
    """Convert X-SAMPA string to IPA."""
    mapping = _get_xsampa_map()
    result = []
    i = 0
    while i < len(xsampa):
        # Try longest match first (some X-SAMPA symbols are multi-char)
        matched = False
        for length in range(min(4, len(xsampa) - i), 0, -1):
            candidate = xsampa[i : i + length]
            if candidate in mapping:
                result.append(mapping[candidate])
                i += length
                matched = True
                break
        if not matched:
            i += 1  # Skip unknown
    return "".join(result)


def features_from_xsampa(
    xsampa: str, with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get feature bundles from X-SAMPA string."""
    ipa_str = xsampa_to_ipa(xsampa)
    return _get_ipa().compose(ipa_str, with_defaults=with_defaults)


# --- CMU ARPABET Conversion ---


def to_cmu(
    ipa_string: str, with_stress: bool = True, include_extras: bool = False
) -> list[str]:
    """Convert IPA string to list of CMU ARPABET symbols."""
    return _get_cmu().ipa_to_cmu(
        ipa_string, with_stress=with_stress, include_extras=include_extras
    )


def to_ipa(cmu_symbols: list[str], include_extras: bool = True) -> str:
    """Convert list of CMU ARPABET symbols to IPA string."""
    return _get_cmu().cmu_to_ipa(cmu_symbols, include_extras=include_extras)


# --- Tokenization & Normalization ---


def tokenize(ipa_string: str) -> list[str]:
    """Parse IPA string into list of segment tokens."""
    return _get_ipa().tokenize_ipa(ipa_string)


def segment(ipa_string: str) -> str:
    """Parse IPA string and return whitespace-separated segments."""
    return _get_ipa().segment_ipa(ipa_string)


def normalize(segments: str) -> str:
    """Normalize whitespace-separated IPA segments into decodable IPA string."""
    return _get_ipa().normalize_ipa(segments)


def normalize_lookalikes(text: str) -> str:
    """Replace lookalike characters with proper IPA equivalents.

    Converts visually similar keyboard characters to their
    correct IPA Unicode codepoints (e.g., 'g' → 'ɡ', ':' → 'ː').
    """
    return _get_ipa().normalize_lookalikes(text)


def add_ties(segment: str) -> str:
    """Add tie bars between base phones in a multi-phone segment."""
    return _get_ipa().add_tie_bars(segment)


def feature_bundles(
    ipa_string: str, with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get list of feature dicts for each segment in an IPA string."""
    return _get_ipa().compose(ipa_string, with_defaults=with_defaults)


def phones_matching(
    query: dict[str, str] | list[str] | set[str], with_defaults: bool = True
) -> list[str]:
    """Get all phones matching features. Accepts dict or list/set of short names."""
    return _get_ipa().phones_matching(query, with_defaults=with_defaults)


def features_to_shorts(bundle: dict[str, str]) -> list[str]:
    """Convert a feature dict to list of short names."""
    return _get_ipa().features_to_shorts(bundle)


def shorts_to_features(shorts: list[str] | set[str]) -> dict[str, str]:
    """Convert list of short names to feature dict."""
    return _get_ipa().shorts_to_features(shorts)


def _make_wiki_url(ipa: IPAFeatures, href: str | None) -> str | None:
    """Construct full Wikipedia URL from article name."""
    if href and ipa.wiki_base and not href.startswith("http"):
        return ipa.wiki_base + href
    return href


def wiki(phone: str) -> str | None:
    """Get Wikipedia URL for an IPA phone symbol.

    Example:
        >>> ipakit.wiki("p")
        'https://en.wikipedia.org/wiki/Voiceless_bilabial_plosive'
    """
    ipa = _get_ipa()
    href = None
    if phone in ipa.phones:
        href = ipa.phones[phone].features.get("href")
    elif phone in ipa.diacritics:
        href = ipa.diacritics[phone].features.get("href")
    return _make_wiki_url(ipa, href)


def wiki_ref(name: str) -> str | None:
    """Get Wikipedia URL for a general IPA reference.

    Example:
        >>> ipakit.wiki_ref("IPA")
        'https://en.wikipedia.org/wiki/International_Phonetic_Alphabet'
        >>> ipakit.wiki_ref("X-SAMPA")
        'https://en.wikipedia.org/wiki/X-SAMPA'
    """
    ipa = _get_ipa()
    href = ipa.references.get(name)
    return _make_wiki_url(ipa, href)


def wiki_refs() -> dict[str, str]:
    """Get all general IPA reference URLs.

    Returns dict mapping reference names to full Wikipedia URLs.
    """
    ipa = _get_ipa()
    return {
        name: url
        for name, href in ipa.references.items()
        if (url := _make_wiki_url(ipa, href)) is not None
    }


# --- Analysis functions ---


def describe(phone: str, with_defaults: bool = True) -> str:
    """Generate human-readable IPA description for a phone.

    Examples:
        >>> ipakit.describe("p")
        'voiceless bilabial plosive'
        >>> ipakit.describe("ɛ")
        'open-mid front unrounded vowel'
        >>> ipakit.describe("t͡ʃ")
        'voiceless postalveolar affricate'
    """
    return _get_ipa().describe(phone, with_defaults=with_defaults)


def natural_class(
    phones: list[str],
    with_defaults: bool = True,
    exclude_features: set[str] | None = None,
) -> dict[str, str]:
    """Find features shared by all phones in a set (natural class).

    Examples:
        >>> ipakit.natural_class(["p", "t", "k"])
        {'manner': 'plosive', 'voiced': '-'}
        >>> ipakit.natural_class(["i", "e", "ɛ"])
        {'manner': 'vowel', 'backness': 'front'}
    """
    return _get_ipa().natural_class(
        phones, with_defaults=with_defaults, exclude_features=exclude_features
    )


def minimal_pairs(
    phone: str,
    with_defaults: bool = True,
    max_distance: float = 0.3,
) -> list[tuple[str, str, str | None]]:
    """Find phones that differ by approximately one feature (minimal pairs).

    Returns list of (phone, differing_feature, differing_value) tuples.

    Examples:
        >>> ipakit.minimal_pairs("p")
        [('b', 'voiced', '+'), ('t', 'place', 'alveolar'), ...]
    """
    return _get_ipa().minimal_pairs(
        phone, with_defaults=with_defaults, max_distance=max_distance
    )


def nearest_phones(
    phone: str,
    n: int = 10,
    with_defaults: bool = True,
) -> list[tuple[str, float]]:
    """Find the n nearest phones by phonetic distance.

    Returns list of (phone, distance) tuples sorted by distance.

    Examples:
        >>> ipakit.nearest_phones("p", n=3)
        [('b', 0.08), ('t', 0.12), ('k', 0.15)]
    """
    return _get_ipa().nearest_phones(phone, n=n, with_defaults=with_defaults)


def validate_ipa(ipa: str, strict: bool = False) -> list[dict[str, str]]:
    """Validate an IPA string for well-formedness.

    Returns a list of issue dicts. Empty list means valid.

    Examples:
        >>> ipakit.validate_ipa("kæt")
        []
        >>> ipakit.validate_ipa("xyz")
        [{'type': 'error', 'code': 'unknown_symbol', ...}, ...]
    """
    return _get_ipa().validate_ipa(ipa, strict=strict)


def is_valid_ipa(ipa: str) -> bool:
    """Check if an IPA string is valid (no errors).

    Examples:
        >>> ipakit.is_valid_ipa("kæt")
        True
        >>> ipakit.is_valid_ipa("xyz")
        False
    """
    return _get_ipa().is_valid_ipa(ipa)


__all__ = [
    # Classes
    "CMUMapper",
    "Feature",
    "IPAFeatures",
    "Phone",
    "PhoneMapping",
    "Phoneset",
    "WordDistanceResult",
    # Constants
    "DATA_DIR",
    "DEFAULT_CMU_MAP",
    "DEFAULT_IPA_FEATS",
    "PHONEMAPS_DIR",
    "STRESS_MARKERS",
    "TIE_BAR",
    # Functions
    "add_ties",
    "describe",
    "distance",
    "feature_bundles",
    "features",
    "features_from_cmu",
    "features_from_xsampa",
    "features_to_shorts",
    "from_kirshenbaum",
    "from_timit",
    "is_valid_ipa",
    "load_ipa_features",
    "minimal_pairs",
    "natural_class",
    "nearest_phones",
    "normalize",
    "normalize_lookalikes",
    "phones_matching",
    "segment",
    "shorts_to_features",
    "to_cmu",
    "to_ipa",
    "to_kirshenbaum",
    "to_timit",
    "tokenize",
    "validate_ipa",
    "wiki",
    "wiki_ref",
    "wiki_refs",
    "word_distance",
    "word_similarity",
    "xsampa_to_ipa",
]
