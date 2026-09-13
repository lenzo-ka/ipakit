"""Shared comparison readouts refuse accumulated numeric overflow."""

from dataclasses import replace

import pytest
from ipakit.bridges.costmodel import (
    CostPolicy,
    Normalization,
    Segmentation,
    compare,
    compare_token_corpus,
    compare_tokens,
    normalized,
    set_feature_pack,
)
from ipakit.distance_registry import DistanceRegistry, Metric
from ipakit.feature_sets import FeatureSets
from ipakit.features import IPAFeatures


def _pack(normalization, gap):
    features = FeatureSets("accumulation", {"Q": {"feature"}})
    return replace(
        set_feature_pack(features, CostPolicy(normalization=normalization)),
        insert_cost=gap,
        delete_cost=gap,
        validate_token=features.features,
        tokenize=lambda text: Segmentation(tuple(text)),
    )


@pytest.fixture(scope="module")
def ipa():
    return IPAFeatures()


@pytest.mark.parametrize("normalization", list(Normalization))
@pytest.mark.parametrize("left,right", [("QQ", ""), ("", "QQ")])
def test_direct_comparison_refuses_accumulation(ipa, normalization, left, right):
    pack = _pack(normalization, 1e308)
    with pytest.raises(ValueError, match="accumulated cost"):
        compare_tokens(ipa, pack, Segmentation(tuple(left)), Segmentation(tuple(right)))
    with pytest.raises(ValueError, match="accumulated cost"):
        compare(ipa, pack, left, right)
    row = compare_token_corpus(ipa, [pack], [list(left), list(right)])["rows"][0]
    assert row["status"] == "refused"
    assert "accumulated cost" in row["message"]


@pytest.mark.parametrize("normalization", list(Normalization))
@pytest.mark.parametrize("raw", [float("inf"), float("-inf"), float("nan"), -1.0])
def test_normalized_validates_raw_before_empty_shortcuts(normalization, raw):
    with pytest.raises(ValueError, match="accumulated cost"):
        normalized(_pack(normalization, 1), Segmentation(()), Segmentation(()), raw)


@pytest.mark.parametrize("normalization", list(Normalization))
@pytest.mark.parametrize("left,right", [("QQ", ""), ("", "QQ")])
def test_large_finite_costs_and_empty_convention(ipa, normalization, left, right):
    pack = _pack(normalization, 1e307)
    result = compare(ipa, pack, left, right)
    assert result.edit_cost == 2e307
    expected = {
        Normalization.RAW: 2e307,
        Normalization.DIV_MAXLEN: 1e307,
        Normalization.DIV_NULL_ALIGNMENT: 1.0,
    }[normalization]
    assert result.normalized == expected
    empty = compare(ipa, pack, "", "")
    assert empty.edit_cost == empty.normalized == 0.0


def test_registry_retains_healthy_arm_after_shared_refusal():
    bad = _pack(Normalization.RAW, 1e308)
    good = _pack(Normalization.RAW, 1)
    registry = DistanceRegistry(
        [
            Metric("overflow", bad.geometry, {}, lambda _: bad),
            Metric("healthy", good.geometry, {}, lambda _: good),
        ]
    )
    rows = registry.distances(["Q", "Q"], [])["rows"]
    assert rows[0]["status"] == "refused"
    assert "accumulated cost" in rows[0]["error"]["message"]
    assert rows[1]["status"] == "scored"
    assert rows[1]["edit_cost"] == rows[1]["normalized"] == 2.0
