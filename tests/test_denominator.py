"""The distance denominator is a caller choice with a stable default."""

from __future__ import annotations

import json

import ipakit
from ipakit.constants import DEFAULT_CONFUSION
from ipakit.metric import _bundle_terms, metric_fingerprint


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


def test_explicit_out_of_class_value_survives_scoping() -> None:
    ipa = ipakit.IPAFeatures()
    for marked, plain in (("sʴ", "s"), ("r˞", "r"), ("wʴ", "w")):
        assert ipa.is_valid_ipa(marked)
        assert ipa.describe(marked) != ipa.describe(plain)
        assert ipa.segment_distance(marked, plain) == 0.05
        assert ipa.segment_distance(marked, plain, applicable_only=True) > 0.0


def test_neighbor_and_segment_reads_carry_the_choice() -> None:
    ipa = ipakit.IPAFeatures()
    expected = ipa.distance("sʴ", "s", applicable_only=True)
    nearest = dict(ipa.nearest_phones("sʴ", n=len(ipa.phones), applicable_only=True))
    assert nearest["s"] == expected
    assert (
        dict(ipakit.nearest_phones("sʴ", n=len(ipa.phones), applicable_only=True))["s"]
        == expected
    )
    assert (
        ipa.segment("sʴ").distance(ipa.segment("s"), applicable_only=True) == expected
    )


def test_every_restricted_feature_is_resolved_from_its_declaration() -> None:
    ipa = ipakit.IPAFeatures()
    hosts = {
        "channel": ("a", "e"),
        "constriction-location": ("p", "t"),
        "fortis": ("a", "e"),
        "retroflex": ("a", "e"),
        "rhotacized": ("p", "t"),
    }
    for key, pair in hosts.items():
        left = ipa.segment(pair[0]).constituents[0]
        right = ipa.segment(pair[1]).constituents[0]
        host1 = left.bundle(ipa, with_defaults=False)
        host2 = right.bundle(ipa, with_defaults=False)
        assert not (ipa.feature_applies(key, host1) and ipa.feature_applies(key, host2))
        basic_terms = _bundle_terms(ipa, left, right)[1]
        scoped_terms = _bundle_terms(ipa, left, right, applicable_only=True)[1]
        assert scoped_terms < basic_terms


def test_every_distance_returning_wrapper_forwards_the_choice() -> None:
    ipa = ipakit.IPAFeatures()
    expected = ipa.distance("a", "e", applicable_only=True)
    assert (
        ipa.directional_word_distance("a", "e", applicable_only=True).edit_cost
        == 2 * expected
    )
    assert (
        ipa.sequence_distance(["a"], ["e"], applicable_only=True).edit_cost
        == 2 * expected
    )
    assert ipa.sequence_similarity(["a"], ["e"], applicable_only=True) == 1 - expected
    assert (
        ipa.rank_sequences(["a"], [["e"]], applicable_only=True)[0].result.edit_cost
        == 2 * expected
    )
    assert (
        ipa.nearest_pronunciation("a", ["e"], applicable_only=True).result.edit_cost
        == 2 * expected
    )
    assert (
        ipa.rank_pronunciations("a", ["e"], applicable_only=True)[0].result.edit_cost
        == 2 * expected
    )
    assert ipakit.explain_word_distance("a", "e", applicable_only=True)[-1][
        "cost"
    ] == round(expected, 4)
