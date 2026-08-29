"""Regression tests for the shared cost-model parameter surface."""

from __future__ import annotations

import math
from itertools import combinations_with_replacement
from pathlib import Path

import pytest
from ipakit.bridges.costmodel import (
    CHEAP_INDEL,
    FAITHFUL,
    CostPolicy,
    Normalization,
    Segmentation,
    align_under,
    compare,
    house_pack,
)
from ipakit.features import IPAFeatures

CORPUS = Path(__file__).parent / "panphon" / "shared-corpus.txt"


def _words() -> list[str]:
    return CORPUS.read_text(encoding="utf-8").splitlines()


def test_default_policy_is_faithful_and_identity_names_every_field() -> None:
    assert FAITHFUL.is_faithful
    assert FAITHFUL.identity == ("costmodel/1.0 sub_scale=1.0 indel=1.0 norm=raw")
    assert not CHEAP_INDEL.is_faithful


def test_negative_or_nonfinite_policy_values_are_refused_at_construction() -> None:
    for field in ("substitution_scale", "indel_weight"):
        for value in (-1.0, math.inf, -math.inf, math.nan):
            with pytest.raises(ValueError, match=field):
                CostPolicy(**{field: value})


def test_a_bad_policy_is_refused_before_the_fold_prices_a_phone() -> None:
    with pytest.raises(ValueError, match="indel_weight") as error:
        CostPolicy(indel_weight=-1.0)
    assert "phone" not in str(error.value)


def test_house_pack_reproduces_word_distance_exactly_over_the_shared_corpus() -> None:
    ipa = IPAFeatures()
    for source, target in combinations_with_replacement(_words(), 2):
        actual = compare(ipa, house_pack(ipa), source, target).edit_cost
        assert actual == ipa.word_distance(source, target).edit_cost


def test_indel_weight_scales_indels_and_never_the_substitution() -> None:
    ipa = IPAFeatures()
    pack = house_pack(ipa, CHEAP_INDEL)
    assert compare(ipa, pack, "kat", "kot").edit_cost == 0.32352092352092354
    assert compare(ipa, pack, "mbanda", "banda").edit_cost == 0.25


def test_the_house_arm_never_drops_and_raises_on_unconvertible_input() -> None:
    ipa = IPAFeatures()
    tokenize = house_pack(ipa).tokenize
    for word in _words():
        assert tokenize(word).dropped == ()
    with pytest.raises(ValueError):
        tokenize("☃")


def test_div_null_alignment_reproduces_word_distance_similarity() -> None:
    ipa = IPAFeatures()
    policy = CostPolicy(normalization=Normalization.DIV_NULL_ALIGNMENT)
    for source, target in combinations_with_replacement(_words(), 2):
        row = compare(ipa, house_pack(ipa, policy), source, target)
        result = ipa.word_distance(source, target)
        assert 1.0 - row.normalized == result.similarity


def test_align_under_is_the_only_foreign_call_site_of_the_fold() -> None:
    root = Path(__file__).parents[1] / "ipakit"
    calls: list[str] = []
    for path in root.rglob("*.py"):
        calls.extend(
            str(path.relative_to(root))
            for _ in range(path.read_text().count("._align("))
        )
    assert sorted(calls) == [
        "bridges/costmodel.py",
        "distance.py",
        "distance_model.py",
        "distance_model.py",
    ]


def test_align_under_refuses_bare_token_lists() -> None:
    ipa = IPAFeatures()
    pack = house_pack(ipa)
    with pytest.raises(AttributeError):
        align_under(ipa, pack, ["k", "a"], ["k", "o"])
    assert (
        align_under(ipa, pack, Segmentation(("k", "a")), Segmentation(("k", "o")))[0]
        >= 0.0
    )
