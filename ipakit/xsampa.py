"""X-SAMPA <-> IPA string conversion.

Single source of truth for X-SAMPA: the phonemap data file
``data/phonemaps/xsampa.xml`` (a bijective IPA <-> X-SAMPA table). Both
directions are derived from that one table, so they stay mutually consistent.

The table itself is reproducible from ICU transliteration plus a small set of
curated overrides; see ``scripts/xsampa_table.py`` for the generator/validator.
"""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET

from ._tokenize import longest_match
from .constants import PHONEMAPS_DIR

_XSAMPA_FILE = PHONEMAPS_DIR / "xsampa.xml"


@functools.lru_cache(maxsize=1)
def _maps() -> tuple[dict[str, str], dict[str, str]]:
    """Load (xsampa->ipa, ipa->xsampa) maps from ``xsampa.xml``."""
    xs2ipa: dict[str, str] = {}
    ipa2xs: dict[str, str] = {}
    if not _XSAMPA_FILE.exists():
        return xs2ipa, ipa2xs
    root = ET.parse(_XSAMPA_FILE).getroot()
    for m in root.findall("map"):
        xs, ip = m.get("xsampa"), m.get("ipa")
        if xs and ip:
            xs2ipa[xs] = ip
            ipa2xs[ip] = xs
    return xs2ipa, ipa2xs


def _convert(text: str, lookup: dict[str, str]) -> str:
    """Greedy longest-match conversion of ``text`` via ``lookup``.

    Unknown characters are skipped (mirrors the historical behavior of the
    X-SAMPA converters).
    """
    if not lookup:
        return ""
    max_len = max(len(k) for k in lookup)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        key, length = longest_match(text, i, lookup, max_len)
        if key:
            out.append(lookup[key])
            i += length
        else:
            i += 1  # skip unknown character
    return "".join(out)


def xsampa_to_ipa(xsampa: str) -> str:
    """Convert an X-SAMPA string to IPA (greedy longest-match)."""
    xs2ipa, _ = _maps()
    return _convert(xsampa, xs2ipa)


def ipa_to_xsampa(ipa: str) -> str:
    """Convert an IPA string to X-SAMPA (greedy longest-match)."""
    _, ipa2xs = _maps()
    return _convert(ipa, ipa2xs)
