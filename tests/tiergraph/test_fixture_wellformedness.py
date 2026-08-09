from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).with_name("fixtures")
POINTER = re.compile(
    r"^/clock/(?P<tick>0|[1-9][0-9]*)(?:/gaps/(?P<gap>0|[1-9][0-9]*))?(?:/.*)?$"
)
VERDICTS = {"valid", "rejected-with-reason", "canonical-form"}


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _walk(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)
    elif isinstance(value, str):
        yield value


def test_index_names_every_fixture_once() -> None:
    names = _load("index.json")["fixtures"]
    assert len(names) == len(set(names))
    assert set(names) == {path.name for path in FIXTURES.glob("*.json")} - {
        "index.json"
    }


def test_every_case_has_a_known_expected_verdict() -> None:
    for name in _load("index.json")["fixtures"]:
        data = _load(name)
        cases = data.get("cases", data.get("deliveries", []))
        if "expected" in data:
            assert data["expected"]["verdict"] in VERDICTS
        for case in cases:
            expected = case.get("expected")
            if expected is not None:
                assert expected["verdict"] in VERDICTS
                assert expected.get("must_reject", False) == (
                    expected["verdict"] == "rejected-with-reason"
                )


def test_clock_cardinality_and_gap_counts_are_internally_consistent() -> None:
    clock = _load("clock_and_ordering.json")["cases"]
    n_plus_one = next(case for case in clock if case["id"] == "n-plus-one-clock")
    assert n_plus_one["expected"]["clock_entries"] == len(n_plus_one["input_atoms"]) + 1
    cases = _load("compatibility_coordinates.json")["cases"]
    dots = next(case for case in cases if case["id"] == "a-dot-dot-b-mora")
    assert dots["expected"]["clock_entries"] == len(dots["clock_atoms"]) + 1
    for tick, refiners in dots["tick_refiners"].items():
        assert dots["expected"]["gap_counts"][tick] == len(refiners) + 1


def test_all_clock_references_are_pointer_shaped() -> None:
    for name in _load("index.json")["fixtures"]:
        for value in _walk(_load(name)):
            if value.startswith("/clock/"):
                assert POINTER.match(value), value


def test_reversed_spans_are_explicit_must_reject_cases() -> None:
    cases = _load("endpoints.json")["cases"]
    case = next(case for case in cases if case["id"] == "reversed-refined-span")
    assert case["expected"]["must_reject"] is True
    assert case["span"]["start"] > case["span"]["end"]


def test_choices_pin_zero_or_one_selection_and_all_rejections() -> None:
    data = _load("choices_and_containment.json")
    assert data["relations"]["alternatives"]["choice"] is True
    assert data["relations"]["selects"]["member_of"] == "alternatives"
    by_id = {case["id"]: case for case in data["cases"]}
    assert by_id["choice-no-selection"]["expected"]["selected"] is None
    assert by_id["choice-one-selection"]["expected"]["selected"]
    rejected = {
        key for key, value in by_id.items() if value["expected"].get("must_reject")
    }
    assert rejected == {
        "duplicate-candidate",
        "multiple-alternatives-links",
        "multiple-selects-links",
        "selection-outside-candidates",
    }


def test_signature_slot_counts_match_the_pinned_verdicts() -> None:
    slots = {".", "ˈ", "ˌ"}
    for case in _load("signature_edits.json")["cases"]:
        if "signature" not in case:
            continue
        count = sum(char in slots for char in case["signature"])
        assert count == case["expected"].get("slots", count)
        if case["expected"]["verdict"] == "valid":
            assert count == len(case["hosts"])
        else:
            assert count != len(case["hosts"])
