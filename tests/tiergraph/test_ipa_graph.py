from __future__ import annotations

import json
from pathlib import Path

import pytest
from ipakit import Form, IPAFeatures, Segment, rules
from ipakit._ipa_graph import (
    CLOCK_TREATMENTS,
    OccurrenceKind,
    assign_signature,
    declarations,
    parse_signature,
    prosody_host_tiers,
)
from ipakit._tiergraph import ClockNode, Event, EventGroup, Graph, Relation


def test_structured_segment_fixture_restores_without_tokenizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = IPAFeatures()
    fixture = json.loads(
        (Path(__file__).parent / "structured_segment_v3.json").read_text()
    )

    def tokenizer_was_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("IPA tokenizer was called")

    scan_entry_points = {"segment", "parse", "tokenize", "read"} | {
        name for name in dir(inventory) if name.startswith("_parse")
    }
    for name in scan_entry_points:
        monkeypatch.setattr(inventory, name, tokenizer_was_called)
    segment = Segment.from_dict(fixture["value"], inventory)

    assert [part.base for part in segment.constituents] == ["d", "ʒ"]
    assert [part.approach for part in segment.constituents] == [("ⁿ",), ()]
    assert [part.modifiers for part in segment.constituents] == [(), ("ʷ",)]
    assert [sense.value for sense in segment.junctures] == ["fuse"]
    assert segment.prosody == ("ː",)
    assert segment.to_ipa() == fixture["spelling"]
    unit = Form.from_dict(
        {
            "type": "ipakit.form",
            "v": 1,
            "units": [
                {
                    "text": fixture["spelling"],
                    "segment": fixture["value"],
                    "features": fixture["features"],
                    "prosody": fixture["prosody"],
                    "provenance": fixture["provenance"],
                    "timing": None,
                }
            ],
            "intervals": [],
            "spelling": fixture["spelling"],
        },
        inventory,
    ).units[0]
    assert dict(unit.features) == fixture["features"]
    assert dict(unit.prosody) == fixture["prosody"]
    assert [list(item) for item in unit.provenance] == fixture["provenance"]


@pytest.mark.parametrize("view", ["features", "prosody", "provenance"])
def test_structured_segment_cached_views_must_agree(view: str) -> None:
    inventory = IPAFeatures()
    form = Form.parse("ⁿd͡ʒʷː", inventory).to_dict()
    if view == "provenance":
        form["units"][0][view] = []
    else:
        form["units"][0][view]["wrong"] = "value"
    with pytest.raises(ValueError, match="views disagree with segment"):
        Form.from_dict(form, inventory)


def test_inventory_drives_feature_and_mark_declarations() -> None:
    inventory = IPAFeatures()
    declared = declarations(inventory)
    assert {feature.name for feature in declared.features} >= set(
        inventory.feature_order
    )
    assert parse_signature(".ˈˌ#|‖", inventory).stress == (
        "none",
        "primary",
        "secondary",
    )
    assert prosody_host_tiers(inventory) == {
        "word",
        "syllable",
        "phrase",
        "utterance",
        "foot",
        "segment",
        "prosody",
    }
    assert "capitalized" not in {feature.name for feature in declared.features}


def test_clock_treatment_and_structural_distinctions() -> None:
    inventory = IPAFeatures()
    assert CLOCK_TREATMENTS[OccurrenceKind.SEGMENT].consumes_span
    assert CLOCK_TREATMENTS[OccurrenceKind.ZERO].consumes_span
    assert CLOCK_TREATMENTS[OccurrenceKind.BOUNDARY].refines_tick
    assert not CLOCK_TREATMENTS[OccurrenceKind.ATTACHED_ATTRIBUTE].consumes_span
    assert CLOCK_TREATMENTS[OccurrenceKind.INPUT_SILENCE].consumes_span
    assert CLOCK_TREATMENTS[OccurrenceKind.DERIVED_SILENCE].structural_duration == 0
    assert inventory.segment("ⁿd").to_dict() != inventory.segment("n͡d").to_dict()
    assert assign_signature(".ˈ#", ("a", "b"), inventory) == (
        ("a", "none"),
        ("b", "primary"),
    )


def test_linking_mark_is_not_a_signature_boundary() -> None:
    with pytest.raises(ValueError, match="undeclared prosodic signature symbol"):
        parse_signature("ˈ‿ˈ", IPAFeatures())


def test_declared_phrase_and_utterance_tiers_host_prosody() -> None:
    inventory = IPAFeatures()
    Graph(
        declarations(inventory),
        (
            ClockNode(
                groups=(
                    EventGroup("phrase", (Event({"value": "phrase"}),)),
                    EventGroup("utterance", (Event({"value": "utterance"}),)),
                    EventGroup(
                        "prosody",
                        (Event({"stress": "primary"}), Event({"stress": "secondary"})),
                    ),
                )
            ),
            ClockNode(),
        ),
        (
            Relation(
                ("/clock/0/prosody/0",),
                "associates-with",
                ("/clock/0/phrase/0",),
            ),
            Relation(
                ("/clock/0/prosody/1",),
                "associates-with",
                ("/clock/0/utterance/0",),
            ),
        ),
    )


def test_assigned_stress_values_are_rule_engine_values() -> None:
    inventory = IPAFeatures()
    assigned = assign_signature(".ˈˌ", ("a", "b", "c"), inventory)
    for _, value in assigned:
        rules.parse(f"a -> [stress={value}]", inventory)
