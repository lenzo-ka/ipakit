"""Accumulated normalization budgets retain finite arithmetic requirements."""

import math
from dataclasses import replace

import pytest
from ipakit.bridges.costmodel import (
    CostPolicy,
    Normalization,
    Segmentation,
    compare_tokens,
    normalized,
    set_feature_pack,
)
from ipakit.distance_registry import DistanceRegistry, Metric
from ipakit.feature_sets import FeatureSets
from ipakit.features import IPAFeatures


def pack(normalization=Normalization.DIV_NULL_ALIGNMENT, gap=1e308):
    geometry = FeatureSets("normalization-probe", {"a": {"a"}, "b": {"b"}})
    return replace(
        set_feature_pack(geometry, CostPolicy(normalization=normalization), gap=gap),
        validate_token=geometry.features,
    )


def test_null_alignment_refuses_overflow_instead_of_false_zero():
    # Each valid price is finite; the exact ratio is also representable.
    assert (1 / 1e308) / 2 == 5e-309
    with pytest.raises(ValueError, match="finite accumulated budget"):
        compare_tokens(
            IPAFeatures(), pack(), Segmentation(("a",)), Segmentation(("b",))
        )


@pytest.mark.parametrize("normalization", [Normalization.RAW, Normalization.DIV_MAXLEN])
def test_other_normalizations_do_not_accumulate_gap_budget(normalization):
    result = compare_tokens(
        IPAFeatures(), pack(normalization), Segmentation(("a",)), Segmentation(("b",))
    )
    assert result.edit_cost == 1.0
    assert result.normalized == 1.0


def test_large_representable_null_budget_preserves_nonzero_result():
    result = compare_tokens(
        IPAFeatures(), pack(gap=1e307), Segmentation(("a",)), Segmentation(("b",))
    )
    assert result.normalized > 0
    assert math.isclose(result.normalized, 5e-308, rel_tol=1e-14, abs_tol=0)


def test_empty_and_zero_null_budget_keep_existing_convention():
    empty = Segmentation(())
    assert normalized(pack(), empty, empty, 0.0) == 0.0
    zero = replace(pack(), insert_cost=0.0, delete_cost=0.0)
    assert normalized(zero, Segmentation(("a",)), Segmentation(("a",)), 0.0) == 0.0


def test_registry_reports_overflow_refusal_and_keeps_healthy_arm():
    bad = pack()
    healthy = pack(gap=1)
    registry = DistanceRegistry(
        [
            Metric("overflow", bad.geometry, {}, lambda _: bad),
            Metric("healthy", healthy.geometry, {}, lambda _: healthy),
        ]
    )
    report = registry.distances(["a"], ["b"])
    refused, scored = report["rows"]
    assert refused["status"] == "refused"
    assert refused["error"]["type"] == "ValueError"
    assert "finite accumulated budget" in refused["error"]["message"]
    assert scored["status"] == "scored"
    assert scored["edit_cost"] == 1.0
    assert scored["normalized"] == 0.5
