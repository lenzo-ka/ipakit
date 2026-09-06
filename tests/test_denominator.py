"""The distance denominator is a caller choice with a stable default."""

from __future__ import annotations

import json

import ipakit
from ipakit.constants import DEFAULT_CONFUSION
from ipakit.metric import metric_fingerprint


def test_default_fingerprint_stays_the_shipped_space() -> None:
    ipa = ipakit.IPAFeatures()
    saved = json.loads(DEFAULT_CONFUSION.read_text(encoding="utf-8"))
    assert metric_fingerprint(ipa, saved["phones"]) == saved["metric"]


def test_applicability_is_opt_in_and_names_another_space() -> None:
    ipa = ipakit.IPAFeatures()
    basic = ipa.distance("a", "e")
    scoped = ipa.distance("a", "e", applicable_only=True)
    assert basic == ipakit.distance("a", "e")
    assert scoped == ipakit.distance("a", "e", applicable_only=True)
    assert scoped > basic
    assert metric_fingerprint(ipa, ["a", "e"]) != metric_fingerprint(
        ipa, ["a", "e"], applicable_only=True
    )


def test_every_named_public_read_carries_the_choice() -> None:
    ipa = ipakit.IPAFeatures()
    expected = ipa.distance("a", "e", applicable_only=True)
    assert ipa.segment_distance("a", "e", applicable_only=True) == expected
    assert ipa.word_distance("a", "e", applicable_only=True).edit_cost == 2 * expected
    assert ipa.word_similarity("a", "e", applicable_only=True) == 1 - expected
    assert (
        ipakit.phoneset_mapping(["a"], ["e"], ipa=ipa, applicable_only=True)
        .correspondences[0]
        .distance
        == expected
    )
    assert ipakit.phoneset_comparison(
        ["a"], ["e"], ipa=ipa, applicable_only=True
    ).matrix == ((1 - expected,),)
