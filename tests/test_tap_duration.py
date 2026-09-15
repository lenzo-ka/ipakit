"""Taps are complete closures with inherent, conditionally priced brevity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.metric import segment_terms
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


def test_tap_query_still_selects_all_four(ipa: IPAFeatures) -> None:
    assert set(ipa.phones_matching({"manner": "tap"})) == INHERENTLY_BRIEF


def test_public_features_show_inherent_duration() -> None:
    assert ipakit.features("ɾ")["inherent-duration"] == "brief"


def test_written_and_inherent_brevity_remain_distinct(ipa: IPAFeatures) -> None:
    tap = ipa.get_features("ɾ", with_defaults=False)
    written = ipa.get_features("d̆", with_defaults=False)
    assert tap["inherent-duration"] == "brief"
    assert "inherent-duration" not in written
    assert "length" not in tap and "length" not in written
    assert ipa.segment("d̆").prosody == ("̆",)
    assert ipa.distance("ɾ", "d̆") > 0.0


def test_explain_names_the_segmental_term_without_calling_it_length(
    ipa: IPAFeatures,
) -> None:
    labels = [row[0] for row in segment_terms(ipa, ipa.segment("ɾ"), ipa.segment("d"))]
    assert labels.count("inherent-duration") == 1
    assert "inherent-duration (prosodic)" not in labels


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
