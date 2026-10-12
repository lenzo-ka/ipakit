"""The form-level doculect-spread law."""

import json
from dataclasses import replace

import ipakit
import ipakit.disagreement as disagreement
import pytest
from scripts.disagreement_demo import report


def retained(identity: str, text: str) -> ipakit.ProvenancedForm:
    return ipakit.ProvenancedForm(identity, ipakit.read(text))


def test_anonymous_and_singleton_inputs_are_refused_loudly() -> None:
    with pytest.raises(ValueError, match="provenance"):
        retained("", "kat")
    with pytest.raises(ValueError, match="two or more"):
        ipakit.DisagreementSpread.compare(retained("one", "kat"))
    with pytest.raises(TypeError, match="anonymous"):
        ipakit.DisagreementSpread.compare(retained("one", "kat"), ipakit.read("kat"))  # type: ignore[arg-type]


def test_alignment_partitions_and_reads_named_metric_terms() -> None:
    spread = ipakit.DisagreementSpread.compare(
        retained("cmudict:cat", "kæt"), retained("ipa-dict/en_US:cat", "kɛt")
    )
    pair = spread.comparisons[0]
    assert [item.unit for item in pair.agreements] == ["k", "t"]
    assert len(pair.disagreements) == 1
    difference = pair.disagreements[0]
    assert difference.kind is ipakit.DisagreementKind.FEATURE
    assert "height" in difference.terms
    assert difference.cost == pair.alignment.steps[1].cost


def test_structure_timing_and_tier_claims_are_typed_without_adjudication() -> None:
    left = ipakit.read("a͜ɪ")
    right = ipakit.read("aɪ")
    timed = replace(right.units[0], timing=ipakit.Timing(0.0, 0.2))
    right = ipakit.Form((timed, *right.units[1:]), (ipakit.Interval("syllable", 0, 2),))
    spread = ipakit.DisagreementSpread.compare(
        ipakit.ProvenancedForm("cmu:eye", left),
        ipakit.ProvenancedForm("other:eye", right),
    )
    kinds = {item.kind for item in spread.disagreements}
    assert kinds == {ipakit.DisagreementKind.STRUCTURE, ipakit.DisagreementKind.TIMING}
    assert any(
        item.claim and "tier claim" in item.claim for item in spread.disagreements
    )
    assert spread.inputs[0].form is left  # retained, not replaced by a winner


def test_tied_material_stays_structure_but_carries_itemized_terms() -> None:
    spread = ipakit.DisagreementSpread.compare(
        retained("one", "a͜ɪ"), retained("two", "a")
    )
    difference = spread.disagreements[0]
    assert difference.kind is ipakit.DisagreementKind.STRUCTURE
    assert "segmental" not in difference.terms
    assert any("unmatched part" in label for label in difference.terms)
    assert any("juncture" in label for label in difference.terms)


def test_eligible_contiguous_tier_segmentation_is_priced_once() -> None:
    base = ipakit.read("kat")
    left = ipakit.Form.of(
        base.units,
        (ipakit.Interval("syllable", 0, 1), ipakit.Interval("syllable", 1, 3)),
    )
    right = ipakit.Form.of(
        base.units,
        (ipakit.Interval("syllable", 0, 2), ipakit.Interval("syllable", 2, 3)),
    )
    spread = ipakit.DisagreementSpread.compare(
        ipakit.ProvenancedForm("left", left),
        ipakit.ProvenancedForm("right", right),
    )
    priced = [
        item
        for item in spread.disagreements
        if item.claim == "contiguous tier segmentation distance"
    ]
    assert len(priced) == 1
    assert priced[0].cost == 1.0
    assert (
        sum(
            item.claim == "tier claim (unpriced by segment metric)"
            for item in spread.disagreements
        )
        == 4
    )
    wire = spread.to_json()
    assert ipakit.DisagreementSpread.from_json(wire) == spread
    assert ipakit.DisagreementSpread.from_json(wire).to_json() == wire


@pytest.mark.parametrize(
    ("left_spans", "right_spans"),
    [
        (((0, 1), (1, 2), (2, 3)), ((0, 3),)),
        (((0, 3),), ((0, 1), (1, 2), (2, 3))),
    ],
)
def test_contiguous_tier_split_and_merge_cost_one_each(
    left_spans: tuple[tuple[int, int], ...],
    right_spans: tuple[tuple[int, int], ...],
) -> None:
    base = ipakit.read("kat")
    left = ipakit.Form.of(
        base.units,
        tuple(ipakit.Interval("syllable", *span) for span in left_spans),
    )
    right = ipakit.Form.of(
        base.units,
        tuple(ipakit.Interval("syllable", *span) for span in right_spans),
    )
    spread = ipakit.DisagreementSpread.compare(
        ipakit.ProvenancedForm("left", left),
        ipakit.ProvenancedForm("right", right),
    )
    priced = [
        item
        for item in spread.disagreements
        if item.claim == "contiguous tier segmentation distance"
    ]
    assert len(priced) == 1
    assert priced[0].cost == 2.0


def test_identical_contiguous_tiers_do_not_run_segmentation_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = ipakit.read("kat")
    intervals = (
        ipakit.Interval("syllable", 0, 1),
        ipakit.Interval("syllable", 1, 3),
    )
    left = ipakit.Form.of(base.units, intervals)
    right = ipakit.Form.of(base.units, intervals)

    def unexpected_distance(*args: object, **kwargs: object) -> float:
        raise AssertionError("equal segmentations must bypass the cubic distance")

    monkeypatch.setattr(
        disagreement, "contiguous_segmentation_distance", unexpected_distance
    )
    spread = ipakit.DisagreementSpread.compare(
        ipakit.ProvenancedForm("left", left),
        ipakit.ProvenancedForm("right", right),
    )
    assert all(
        item.claim != "contiguous tier segmentation distance"
        for item in spread.disagreements
    )


def test_ineligible_tier_claims_keep_unpriced_fallback() -> None:
    base = ipakit.read("kat")
    left = ipakit.Form.of(base.units, (ipakit.Interval("syllable", 0, 2),))
    right = ipakit.Form.of(base.units, (ipakit.Interval("syllable", 1, 3),))
    spread = ipakit.DisagreementSpread.compare(
        ipakit.ProvenancedForm("left", left),
        ipakit.ProvenancedForm("right", right),
    )
    assert all(
        item.claim != "contiguous tier segmentation distance"
        for item in spread.disagreements
    )
    assert sum(item.cost for item in spread.disagreements) == 0.0


def test_json_is_canonical_complete_and_round_trips() -> None:
    spread = ipakit.DisagreementSpread.compare(
        retained("a", "kat"), retained("b", "kæt")
    )
    wire = spread.to_json()
    assert list(json.loads(wire)) == sorted(json.loads(wire))
    assert ipakit.DisagreementSpread.from_json(wire) == spread
    assert ipakit.DisagreementSpread.from_json(wire).to_json() == wire
    assert [row["provenance"] for row in json.loads(wire)["inputs"]] == ["a", "b"]


def test_three_forms_are_independent_pairwise_comparisons() -> None:
    spread = ipakit.DisagreementSpread.compare(
        retained("a", "kat"), retained("b", "kæt"), retained("c", "kad"), reference=1
    )
    assert [pair.source for pair in spread.comparisons] == [0, 2]
    assert spread.reference == 1


def test_checked_cmudict_ipa_dict_convention_control() -> None:
    measured = report()
    assert measured["raw"] == {"feature": 1, "structure": 6, "timing": 0}
    assert measured["convention_removed"] == {"feature": 0, "structure": 6, "timing": 0}
    assert measured["substantive_after_normalization"] == {
        "feature": 1,
        "structure": 0,
        "timing": 0,
    }
