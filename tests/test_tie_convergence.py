"""Guard: registered tie-barred entries match what composition derives.

A registered tie-barred phone should decode to the same features the
on-the-fly composer would produce from its parts -- registration is a cache
of composition, not a divergent hand-encoding. This test pins that
invariant, with an explicit exception list for the entries known to
diverge. Each exception names the planned work that will remove it; the
lists must shrink, not grow.
"""

import pytest
from ipakit import IPAFeatures
from ipakit.constants import TIE_BAR

# Entries whose stored features intentionally differ from composition, with
# the reason. The diphthongs store the first element's features while the
# composer merges last-wins; both are lossy readings of a sequential unit,
# to be reconciled by the sequential-tie / union re-encoding work.
KNOWN_DIVERGENT = {
    "a͡ɪ": "diphthong: stored first-element vs composed last-wins",
    "a͡ʊ": "diphthong: stored first-element vs composed last-wins",
    "e͡ɪ": "diphthong: stored first-element vs composed last-wins",
    "o͡ʊ": "diphthong: stored first-element vs composed last-wins",
    "ɔ͡ɪ": "diphthong: stored first-element vs composed last-wins",
    "ɪ͡ə": "diphthong: stored first-element vs composed last-wins",
    "e͡ə": "diphthong: stored first-element vs composed last-wins",
    "ʊ͡ə": "diphthong: stored first-element vs composed last-wins",
    # ʊ̯ carries a diacritic; the composer cannot resolve diacritic-bearing
    # parts, so this entry does not compose at all.
    "a͡ʊ̯": "diacritic-bearing part: composer cannot resolve ʊ̯",
}

# Keys that are metadata rather than phonetic content.
_META = ("class", "href")


def _stored(ipa: IPAFeatures, sym: str) -> dict[str, str]:
    return {k: v for k, v in ipa.phones[sym].features.items() if k not in _META}


def _composed(ipa: IPAFeatures, sym: str) -> dict[str, str] | None:
    feats = ipa._compose_tie_bar_features(sym)
    if feats is None:
        return None
    return {k: v for k, v in feats.items() if k not in _META}


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_registered_ties_match_composition(ipa: IPAFeatures) -> None:
    mismatches = {}
    for sym in ipa.phones:
        if TIE_BAR not in sym or sym in KNOWN_DIVERGENT:
            continue
        if (composed := _composed(ipa, sym)) != _stored(ipa, sym):
            mismatches[sym] = (_stored(ipa, sym), composed)
    assert mismatches == {}


def test_known_divergent_entries_actually_diverge(ipa: IPAFeatures) -> None:
    # Pin the exceptions: if one converges, it must leave the list.
    for sym in KNOWN_DIVERGENT:
        assert sym in ipa.phones, f"{sym!r} no longer registered"
        assert _composed(ipa, sym) != _stored(
            ipa, sym
        ), f"{sym!r} now matches composition; remove it from KNOWN_DIVERGENT"
