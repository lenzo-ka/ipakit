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


def _position(pointer: str) -> tuple[int, int]:
    match = POINTER.match(pointer)
    assert match, pointer
    return int(match["tick"]), int(match["gap"] or 0)


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
    assert _position(case["span"]["start"]) > _position(case["span"]["end"])


def test_endpoint_rejections_are_derived_from_the_fixture_data() -> None:
    by_id = {case["id"]: case for case in _load("endpoints.json")["cases"]}
    outside = by_id["gap-outside-named-tick"]
    match = POINTER.match(outside["input"])
    assert match
    assert int(match["gap"]) > len(outside["refiners"][match["tick"]])

    coarse = by_id["coarse-refined-span-endpoint"]
    refined_ticks = {int(tick) for tick, values in coarse["refiners"].items() if values}
    assert any(
        _position(endpoint)[0] in refined_ticks and "/gaps/" not in endpoint
        for endpoint in coarse["span"].values()
    )


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
        "selects-without-alternatives",
        "selection-outside-candidates",
    }
    bare = by_id["selects-without-alternatives"]["links"]
    assert any(relation == "selects" for _, relation, _ in bare)
    assert not any(relation == "alternatives" for _, relation, _ in bare)


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


def test_structural_duration_and_refined_span_forms_are_exclusive() -> None:
    cases = _load("duration_and_relation_endpoints.json")["cases"]
    for case in cases:
        event = case.get("event")
        if event is None:
            continue
        assert not ("duration" in event and "span" in event)
    refined = next(
        case for case in cases if case["id"] == "refined-span-excludes-duration"
    )
    assert refined["expected"]["duration_field"] == "forbidden"


def test_relation_endpoint_constraints_cover_ticks_gaps_and_events() -> None:
    cases = _load("duration_and_relation_endpoints.json")["cases"]
    endpoint_kinds = {
        kind
        for case in cases
        for kinds in case.get("endpoint_constraints", {}).values()
        for kind in kinds
    }
    assert endpoint_kinds == {"coarse-tick", "refined-gap", "event"}
