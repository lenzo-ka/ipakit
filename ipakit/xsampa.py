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

from ._convert import convert_greedy
from .constants import PHONEMAPS_DIR, SEQ_TIE, TIE_BAR

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


def xsampa_to_ipa(xsampa: str, strict: bool = False) -> str:
    """Convert an X-SAMPA string to IPA (greedy longest-match).

    With ``strict=True``, raise ``ValueError`` on symbols that cannot be
    converted instead of skipping them.
    """
    xs2ipa, _ = _maps()
    return "".join(convert_greedy(xsampa, xs2ipa, strict=strict, what="X-SAMPA -> IPA"))


def ipa_to_xsampa(ipa: str, strict: bool = False) -> str:
    """Convert an IPA string to X-SAMPA (greedy longest-match).

    X-SAMPA has a single tie encoding (``_``), so tie *sense* cannot
    survive this boundary: the under-tie is projected onto the over-tie
    here (unit-hood survives, the sequential/simultaneous distinction does
    not), and round trips return canonical over-tie spellings
    (``t͜s -> t_s -> t͡s``, ``u͜i -> u_i -> u͡i``). This projection is
    legitimate only at a lossy conversion boundary; parsing never does it.
    See docs/ties.md.

    With ``strict=True``, raise ``ValueError`` on symbols that cannot be
    converted instead of skipping them.
    """
    ipa = ipa.replace(SEQ_TIE, TIE_BAR)
    _, ipa2xs = _maps()
    return "".join(convert_greedy(ipa, ipa2xs, strict=strict, what="IPA -> X-SAMPA"))
