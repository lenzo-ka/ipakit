"""Guard: registered tie-barred entries match what composition derives.

A registered tie-barred phone should decode to the same features the
on-the-fly composer would produce from its parts **under the entry's
sense** -- registration is a cache of composition, not a divergent
hand-encoding. Simultaneous entries compare against the over-tie merge;
sequential entries (the diphthongs, per the transitional sense rule)
compare against the under-tie first-element projection, which is exactly
how they are stored. The exception list must shrink, never grow.
"""

import pytest
from ipakit import IPAFeatures

# Entries whose sense-correct spelling the composer cannot resolve, with
# the reason. Empty since composition learned to resolve diacritic-bearing
# parts (ʊ̯ = base + modifier); every tied entry is now derived. The list
# must stay empty -- a new entry here means a regression.
KNOWN_UNCOMPOSABLE: dict[str, str] = {}

# Keys that are metadata rather than phonetic content.
_META = ("class", "href")


def _stored(ipa: IPAFeatures, sym: str) -> dict[str, str]:
    return {k: v for k, v in ipa.phones[sym].features.items() if k not in _META}


def _composed(ipa: IPAFeatures, sym: str) -> dict[str, str] | None:
    """What the fallback composer would produce for this entry's
    sense-correct spelling, were it not registered."""
    spelling = ipa.segment(sym).to_ipa()
    feats = ipa._compose_tie_bar_features(spelling)
    if feats is None:
        return None
    return {k: v for k, v in feats.items() if k not in _META}


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_derivable_entries_ship_without_explicit_features(
    ipa: IPAFeatures,
) -> None:
    """Registered == composed holds by construction: derivable tied entries
    carry no feature attributes in the data — the loader derives them —
    so there is nothing to drift. Only the pinned exceptions may carry
    explicit features."""
    for sym in ipa.phones:
        if not ipa.tie_bars & set(sym):
            continue
        if sym in KNOWN_UNCOMPOSABLE:
            assert sym not in ipa.derived_phones
        else:
            assert sym in ipa.derived_phones, (
                f"{sym!r} carries explicit features in ipa.xml; tied entries "
                "are derived at load — drop the feature attributes"
            )


def test_registered_ties_match_sense_aware_composition(ipa: IPAFeatures) -> None:
    mismatches = {}
    for sym in ipa.phones:
        if not ipa.tie_bars & set(sym) or sym in KNOWN_UNCOMPOSABLE:
            continue
        if (composed := _composed(ipa, sym)) != _stored(ipa, sym):
            mismatches[sym] = (_stored(ipa, sym), composed)
    assert mismatches == {}


def test_known_uncomposable_entries_still_do_not_compose(ipa: IPAFeatures) -> None:
    # Pin the exceptions: if one starts composing, it must leave the list
    # (and is expected to converge when it does).
    for sym in KNOWN_UNCOMPOSABLE:
        assert sym in ipa.phones, f"{sym!r} no longer registered"
        assert _composed(ipa, sym) is None, (
            f"{sym!r} now composes; remove it from KNOWN_UNCOMPOSABLE and "
            "let the convergence test cover it"
        )
