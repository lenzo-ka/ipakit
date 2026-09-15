"""Taps are complete closures with inherent, conditionally priced brevity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.metric import segment_terms
from ipakit.tract import constrictions, posture
from scripts.invariants import INHERENTLY_BRIEF, check_inherent_duration


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_duration_scale_is_a_full_step_with_an_unfilled_center(
    ipa: IPAFeatures,
) -> None:
    duration = ipa.features["inherent-duration"]
    assert duration.axis == "+intrinsic-t"
    assert duration.values == ["brief", "ordinary"]
    assert duration.center == "ordinary"
    assert duration.default is None
    assert duration.value_distance("brief", "ordinary") == 1.0


def test_all_and_only_inherently_brief_phones_state_it(ipa: IPAFeatures) -> None:
    assert check_inherent_duration(ipa)
    assert {
        phone
        for phone in ipa.phones
        if ipa.get_features(phone, with_defaults=False).get("inherent-duration")
        == "brief"
    } == INHERENTLY_BRIEF


def test_taps_are_complete_closures_and_the_trill_is_untouched(
    ipa: IPAFeatures,
) -> None:
    manner = ipa.features["manner"]
    assert manner.coordinates["tap"]["offset"] == 1.0
    assert manner.coordinates["trill"]["offset"] == 0.70


@pytest.mark.parametrize("phone", sorted(INHERENTLY_BRIEF))
def test_each_tap_reaches_the_same_complete_contact_as_a_plosive(
    ipa: IPAFeatures, phone: str
) -> None:
    tap = posture(ipa, phone).constrictions
    plosive_bundle = ipa.get_features(phone)
    plosive_bundle["manner"] = "plosive"
    plosive_bundle.pop("inherent-duration")
    plosive = constrictions(ipa, plosive_bundle)

    assert tap == plosive
    assert len(tap) == 1
    assert tap[0].offset == 1.0


def test_tap_query_still_selects_all_four(ipa: IPAFeatures) -> None:
    assert set(ipa.phones_matching({"manner": "tap"})) == INHERENTLY_BRIEF


def test_public_features_show_inherent_duration() -> None:
    assert ipakit.features("ɾ")["inherent-duration"] == "brief"


def test_derived_taps_preserve_inherent_duration(ipa: IPAFeatures) -> None:
    for phone in ("ɾʲ", "ɾ̃", "ɾˠ", "ɾʷ"):
        assert ipakit.features(phone, with_defaults=False)["inherent-duration"] == (
            "brief"
        )
        assert ipa.segment(phone).scalar(with_defaults=False)["inherent-duration"] == (
            "brief"
        )

    mfa = ipakit.inventory("mfa")
    mfa_tap = mfa.style.read(mfa.style.spell("ɾʲ"))
    assert mfa_tap == "ɾʲ"
    assert ipakit.features(mfa_tap, with_defaults=False)["inherent-duration"] == (
        "brief"
    )


def test_written_and_inherent_brevity_remain_distinct(ipa: IPAFeatures) -> None:
    tap = ipa.get_features("ɾ", with_defaults=False)
    written = ipa.get_features("d̆", with_defaults=False)
    assert tap["inherent-duration"] == "brief"
    assert "inherent-duration" not in written
    assert "length" not in tap and "length" not in written
    assert ipa.segment("d̆").prosody == ("̆",)
    terms = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("d̆"))
    assert [row for row in terms if row[0] == "inherent-duration"] == [
        ("inherent-duration", "brief", None, 1.0)
    ]
    assert [row for row in terms if row[0] == "length (prosodic)"] == [
        ("length (prosodic)", "normal", "extra-short", 1.0 / 3.0)
    ]
    assert ipa.distance("ɾ", "d̆") == sum(row[3] for row in terms) / len(terms)


def test_live_inherent_duration_has_one_conditional_term_of_mass(
    ipa: IPAFeatures,
) -> None:
    tap_stop = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("d"))
    ordinary = segment_terms(ipa, ipa.segment("d"), ipa.segment("t"))
    shared = segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("ɽ"))

    assert [row for row in tap_stop if row[0] == "inherent-duration"] == [
        ("inherent-duration", "brief", None, 1.0)
    ]
    assert not [row for row in ordinary if row[0] == "inherent-duration"]
    assert len(ordinary) == len(segment_terms(ipa, ipa.segment("d"), ipa.segment("d")))
    assert float(len(tap_stop) - len(ordinary)) == 1.0
    assert [row for row in shared if row[0] == "inherent-duration"] == [
        ("inherent-duration", "brief", "brief", 0.0)
    ]
    assert float(len(shared) - len(ordinary)) == 1.0

    for left, right, terms in (
        ("ɾ", "d", tap_stop),
        ("d", "t", ordinary),
        ("ɾ", "ɽ", shared),
    ):
        assert ipa.distance(left, right) == sum(row[3] for row in terms) / len(terms)


def test_public_explanation_keeps_segmental_and_written_brevity_separate() -> None:
    steps = ipakit.explain_transcription_distance("ɾ", "d̆")
    assert len(steps) == 1
    assert (steps[0]["op"], steps[0]["a"], steps[0]["b"]) == ("sub", "ɾ", "d̆")
    rows = steps[0]["terms"]
    assert isinstance(rows, list)
    assert [row for row in rows if row["label"] == "inherent-duration"] == [
        {"label": "inherent-duration", "a": "brief", "b": None, "cost": 1.0}
    ]
    assert [row for row in rows if row["label"] == "length (prosodic)"] == [
        {
            "label": "length (prosodic)",
            "a": "normal",
            "b": "extra-short",
            "cost": 0.3333,
        }
    ]


def test_written_vowel_length_distance_is_unchanged(ipa: IPAFeatures) -> None:
    assert ipa.distance("e", "eː") == 0.02898550724637681


def test_every_pair_lacking_inherent_duration_is_unchanged() -> None:
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
            if left not in INHERENTLY_BRIEF and right not in INHERENTLY_BRIEF:
                values.append(value)
    digest = hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode()
    ).hexdigest()
    assert len(values) == 9045
    assert digest == "3e8d11779972f526c132a279c1a0756329264c5886e145dce0aec9ef6bd997f9"
