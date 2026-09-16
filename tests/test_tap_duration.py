"""Taps and trills are complete closures with marked intrinsic timing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.metric import segment_terms
from ipakit.tract import constrictions, posture
from scripts.invariants import (
    INTRINSICALLY_BRIEF,
    INTRINSICALLY_REPEATED,
    check_intrinsic_timing,
)


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_intrinsic_timing_scale_has_symmetric_marked_values(
    ipa: IPAFeatures,
) -> None:
    timing = ipa.features["intrinsic-timing"]
    assert timing.axis == "+intrinsic-t"
    assert timing.values == ["brief", "ordinary", "repeated"]
    assert timing.center == "ordinary"
    assert timing.default is None
    assert timing.value_distance("brief", "ordinary") == 0.5
    assert timing.value_distance("ordinary", "repeated") == 0.5
    assert timing.value_distance("brief", "repeated") == 1.0
    assert timing.value_distance("brief", None) == 0.5
    assert timing.value_distance(None, "repeated") == 0.5


def test_all_and_only_taps_and_trills_state_intrinsic_timing(
    ipa: IPAFeatures,
) -> None:
    assert check_intrinsic_timing(ipa)
    assert {
        phone
        for phone in ipa.phones
        if ipa.get_features(phone, with_defaults=False).get("intrinsic-timing")
        == "brief"
    } == INTRINSICALLY_BRIEF
    assert {
        phone
        for phone in ipa.phones
        if ipa.get_features(phone, with_defaults=False).get("intrinsic-timing")
        == "repeated"
    } == INTRINSICALLY_REPEATED


def test_taps_and_trills_are_complete_closures(
    ipa: IPAFeatures,
) -> None:
    manner = ipa.features["manner"]
    assert manner.coordinates["tap"]["offset"] == 1.0
    assert manner.coordinates["trill"]["offset"] == 1.0
    assert manner.value_distance("trill", "plosive") == 0.0


@pytest.mark.parametrize("phone", sorted(INTRINSICALLY_BRIEF | INTRINSICALLY_REPEATED))
def test_each_tap_and_trill_reaches_the_same_complete_contact_as_a_plosive(
    ipa: IPAFeatures, phone: str
) -> None:
    closure = posture(ipa, phone).constrictions
    plosive_bundle = ipa.get_features(phone)
    plosive_bundle["manner"] = "plosive"
    plosive_bundle.pop("intrinsic-timing")
    plosive = constrictions(ipa, plosive_bundle)

    assert closure == plosive
    assert len(closure) == 1
    assert closure[0].offset == 1.0


def test_tap_query_still_selects_all_four(ipa: IPAFeatures) -> None:
    assert set(ipa.phones_matching({"manner": "tap"})) == INTRINSICALLY_BRIEF


def test_trill_query_chart_and_natural_class_still_find_all_three(
    ipa: IPAFeatures,
) -> None:
    trills = set(ipa.phones_matching({"manner": "trill"}))
    assert trills == INTRINSICALLY_REPEATED
    assert ipa.natural_class(sorted(trills), with_defaults=False)["manner"] == "trill"
    assert {ipa.notation_of(phone) for phone in trills} == {"chart"}
    assert ipa.is_pure_ipa("".join(sorted(trills)))


def test_public_features_show_intrinsic_timing() -> None:
    assert ipakit.features("ɾ")["intrinsic-timing"] == "brief"
    assert ipakit.features("r")["intrinsic-timing"] == "repeated"


def test_derived_taps_preserve_intrinsic_timing(ipa: IPAFeatures) -> None:
    for phone in ("ɾʲ", "ɾ̃", "ɾˠ", "ɾʷ"):
        assert ipakit.features(phone, with_defaults=False)["intrinsic-timing"] == (
            "brief"
        )
        assert ipa.segment(phone).scalar(with_defaults=False)["intrinsic-timing"] == (
            "brief"
        )

    mfa = ipakit.inventory("mfa")
    mfa_tap = mfa.style.read(mfa.style.spell("ɾʲ"))
    assert mfa_tap == "ɾʲ"
    assert ipakit.features(mfa_tap, with_defaults=False)["intrinsic-timing"] == (
        "brief"
    )


def test_written_and_intrinsic_brevity_remain_distinct(ipa: IPAFeatures) -> None:
    tap = ipa.get_features("ɾ", with_defaults=False)
    written = ipa.get_features("d̆", with_defaults=False)
    assert tap["intrinsic-timing"] == "brief"
    assert "intrinsic-timing" not in written
    assert "length" not in tap and "length" not in written
    assert ipa.segment("d̆").prosody == ("̆",)
    terms = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("d̆"))
    assert [row for row in terms if row[0] == "intrinsic-timing"] == [
        ("intrinsic-timing", "brief", None, 0.5)
    ]
    assert [row for row in terms if row[0] == "length (prosodic)"] == [
        ("length (prosodic)", "normal", "extra-short", 1.0 / 3.0)
    ]
    assert ipa.distance("ɾ", "d̆") == sum(row[3] for row in terms) / len(terms)


def test_live_intrinsic_timing_has_one_conditional_term_of_mass(
    ipa: IPAFeatures,
) -> None:
    tap_stop = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("d"))
    ordinary = segment_terms(ipa, ipa.segment("d"), ipa.segment("t"))
    shared = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("ɽ"))

    assert [row for row in tap_stop if row[0] == "intrinsic-timing"] == [
        ("intrinsic-timing", "brief", None, 0.5)
    ]
    assert not [row for row in ordinary if row[0] == "intrinsic-timing"]
    assert len(ordinary) == len(segment_terms(ipa, ipa.segment("d"), ipa.segment("d")))
    assert float(len(tap_stop) - len(ordinary)) == 1.0
    assert [row for row in shared if row[0] == "intrinsic-timing"] == [
        ("intrinsic-timing", "brief", "brief", 0.0)
    ]
    assert float(len(shared) - len(ordinary)) == 1.0

    for left, right, terms in (
        ("ɾ", "d", tap_stop),
        ("d", "t", ordinary),
        ("ɾ", "ɽ", shared),
    ):
        assert ipa.distance(left, right) == sum(row[3] for row in terms) / len(terms)


def test_spanish_tap_trill_contrast_is_two_phone_distance_steps(
    ipa: IPAFeatures,
) -> None:
    tap_stop = ipa.distance("ɾ", "d")
    trill_stop = ipa.distance("r", "d")
    tap_trill = ipa.distance("ɾ", "r")

    assert tap_stop == 0.022727272727272728
    assert trill_stop == 0.022727272727272728
    assert tap_trill == 0.045454545454545456
    assert tap_trill == 2 * tap_stop == 2 * trill_stop


def test_trill_and_plosive_agree_in_stricture_and_explain_timing(
    ipa: IPAFeatures,
) -> None:
    terms = segment_terms(ipa, ipa.segment("r"), ipa.segment("d"))
    assert [row for row in terms if row[0] == "manner"] == [
        ("manner", "trill", "plosive", 0.0)
    ]
    assert [row for row in terms if row[0] == "intrinsic-timing"] == [
        ("intrinsic-timing", "repeated", None, 0.5)
    ]

    public = ipakit.explain_transcription_distance("r", "d")
    rows = public[0]["terms"]
    assert isinstance(rows, list)
    assert [row for row in rows if row["label"] == "intrinsic-timing"] == [
        {
            "label": "intrinsic-timing",
            "a": "repeated",
            "b": None,
            "cost": 0.5,
        }
    ]


@pytest.mark.parametrize(
    ("left", "right", "expected_brevity_rows"),
    (
        (
            "ɾ",
            "d̆",
            [
                {
                    "label": "intrinsic-timing",
                    "a": "brief",
                    "b": None,
                    "cost": 0.5,
                },
                {
                    "label": "length (prosodic)",
                    "a": "normal",
                    "b": "extra-short",
                    "cost": 0.3333,
                },
            ],
        ),
        (
            "d̆",
            "ɾ",
            [
                {
                    "label": "intrinsic-timing",
                    "a": None,
                    "b": "brief",
                    "cost": 0.5,
                },
                {
                    "label": "length (prosodic)",
                    "a": "extra-short",
                    "b": "normal",
                    "cost": 0.3333,
                },
            ],
        ),
    ),
)
def test_public_explanation_keeps_segmental_and_written_brevity_separate(
    left: str,
    right: str,
    expected_brevity_rows: list[dict[str, object]],
) -> None:
    steps = ipakit.explain_transcription_distance(left, right)
    assert len(steps) == 1
    assert (steps[0]["op"], steps[0]["a"], steps[0]["b"]) == (
        "sub",
        left,
        right,
    )
    rows = steps[0]["terms"]
    assert isinstance(rows, list)
    timing_and_length_rows = [
        row
        for row in rows
        if "timing" in str(row["label"]) or "length" in str(row["label"])
    ]
    assert timing_and_length_rows == [
        expected_brevity_rows[0],
        {"label": "length", "a": "normal", "b": "normal", "cost": 0.0},
        expected_brevity_rows[1],
    ]
    assert [row for row in timing_and_length_rows if row["cost"] != 0.0] == (
        expected_brevity_rows
    )
    assert not [
        row
        for row in rows
        if "intrinsic-timing" in str(row["label"]) and "prosodic" in str(row["label"])
    ]


def test_written_vowel_length_distance_is_unchanged(ipa: IPAFeatures) -> None:
    assert ipa.distance("e", "eː") == 0.02898550724637681


def test_every_pair_lacking_a_tap_or_trill_is_unchanged() -> None:
    matrix = json.loads(
        (
            Path(__file__).parent.parent / "ipakit" / "data" / "confusion.json"
        ).read_text()
    )
    values = []
    index = 0
    for i, left in enumerate(matrix["phones"]):
        for right in matrix["phones"][i + 1 :]:
            value = matrix["triangle"][index]
            index += 1
            marked = INTRINSICALLY_BRIEF | INTRINSICALLY_REPEATED
            if left not in marked and right not in marked:
                values.append(value)
    digest = hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode()
    ).hexdigest()
    assert len(values) == 8646
    assert digest == "2c33c9ac1e74ed29d16517396a9f86026ba70df565a9b564743141b9ee0ef4ae"
