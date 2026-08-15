"""Exercise the Lane C fixture ownership through canonical construction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ipakit._containment_projection import ContainmentProjection
from ipakit._tiergraph import (
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    Graph,
    GraphValidationError,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import (
    EventSpec,
    GraphBuilder,
    LegacyCoordinates,
    LegacyOccurrence,
    PositionHandle,
    add_event_copy,
    add_relation_copy,
    remove_events_copy,
    remove_relations_copy,
)

LANE_C_FIXTURE_CASES = (
    "clock-consumption",
    "builder-lane-order",
    "chained-phantom-scan-order",
    "a-dot-dot-b-mora",
    "boundary-zero-whitespace-units",
    "inserted-site",
    "deleted-boundary-run-site",
    "interval-crosses-tier-boundary",
)
FIXTURES = Path(__file__).parent / "fixtures"


def declarations() -> Declarations:
    return Declarations(
        tuple(
            TierDeclaration(name, frozenset({"value"}))
            for name in ("top", "input", "boundary", "derived")
        ),
        (FeatureDeclaration("value"),),
        (
            RelationDeclaration("contains", containment=True, acyclic=True),
            RelationDeclaration(
                "inserts",
                source_kinds=frozenset({EndpointKind.COARSE_TICK}),
            ),
            RelationDeclaration("rewrites-to", allow_empty_target=True),
        ),
    )


def value(name: str) -> dict[str, str]:
    return {"value": name}


def lane_c_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for name in ("clock_and_ordering.json", "compatibility_coordinates.json"):
        data = json.loads((FIXTURES / name).read_text())
        cases.extend(
            case for case in data["cases"] if case["id"] in LANE_C_FIXTURE_CASES
        )
    return cases


@pytest.mark.parametrize("case", lane_c_cases(), ids=lambda case: str(case["id"]))
def test_lane_c_owned_fixture_verdicts_execute_through_builder(
    case: dict[str, object],
) -> None:
    """Keep Lane C ownership executable instead of acknowledging exclusions."""
    case_id = str(case["id"])
    expected = case["expected"]
    assert isinstance(expected, dict)
    result: dict[str, object]

    if case_id == "clock-consumption":
        builder = GraphBuilder(declarations())
        occurrences = case["occurrences"]
        assert isinstance(occurrences, list)
        for occurrence in occurrences:
            if occurrence["consumes_span"]:
                builder.append_input_atom("input", value(occurrence["surface"]))
            else:
                builder.append_input_occurrence(
                    "boundary",
                    value(occurrence["surface"]),
                    refines_tick=occurrence["refines_tick"],
                )
        result = {"verdict": "valid", "clock_entries": len(builder.build().clock)}
    elif case_id == "builder-lane-order":
        builder = GraphBuilder(declarations())
        handles = {}
        events = sorted(
            case["events"],
            key=lambda event: (event["tier_order"], event["lane_position"]),
        )
        for event in events:
            handles[event["handle"]] = builder.add_event(
                "top" if event["tier_order"] == 1 else "derived",
                event["clock"],
                value(event["handle"]),
                duration=0,
            )
        ordered_names = [
            next(name for name, handle in handles.items() if handle == item)
            for item in builder.scan_order()
        ]
        result = {"verdict": "canonical-form", "handles": ordered_names}
    elif case_id == "chained-phantom-scan-order":
        builder = GraphBuilder(declarations())
        names = {}
        groups: dict[tuple[int, int, int], list[dict[str, object]]] = {}
        for phantom in case["phantoms"]:
            coordinate = tuple(phantom["coordinate"])
            groups.setdefault(coordinate[:3], []).append(phantom)
        for coordinate, phantoms in groups.items():
            ordered = sorted(phantoms, key=lambda item: item["coordinate"][3])
            handles = builder.add_ordered_sequence(
                "derived",
                0,
                tuple(EventSpec(value(phantom["name"])) for phantom in ordered),
                derivation_step=coordinate[0],
                source_site_order=coordinate[1],
                application_order=coordinate[2],
            )
            names.update(
                (handle, phantom["name"])
                for handle, phantom in zip(handles, ordered, strict=True)
            )
        result = {
            "verdict": "canonical-form",
            "scan": [names[handle] for handle in builder.scan_order("derived")],
        }
    elif case_id == "a-dot-dot-b-mora":
        builder = GraphBuilder(declarations())
        builder.append_input_atom("input", value("a"))
        for boundary in case["tick_refiners"]["1"]:
            builder.append_input_occurrence(
                "boundary", value(boundary), refines_tick=True
            )
        builder.append_input_atom("input", value("b"))
        span = case["graph_span"]
        builder.add_span(
            "derived",
            PositionHandle(0),
            PositionHandle(1, 1),
            value("mora"),
        )
        graph = builder.build()
        result = {
            "verdict": "canonical-form",
            "clock_entries": len(graph.clock),
            "gap_counts": {
                str(i): node.gap_count for i, node in enumerate(graph.clock)
            },
        }
        assert graph.clock[0].groups[-1].events[0].span is not None
        assert graph.clock[0].groups[-1].events[0].span.end == span["end"]
    elif case_id == "boundary-zero-whitespace-units":
        builder = GraphBuilder(declarations())
        for index, consumes in enumerate(case["consumes_span"]):
            if consumes:
                builder.append_input_atom("input", value(str(index)))
            else:
                builder.append_input_occurrence(
                    "boundary", value(str(index)), refines_tick=index in {1, 2}
                )
        result = {"verdict": "valid", "clock_entries": len(builder.build().clock)}
    elif case_id == "inserted-site":
        builder = GraphBuilder(declarations())
        builder.append_input_atom("input", value("a"))
        inserted = builder.add_event("derived", 1, value("x"), duration=0)
        builder.relate((PositionHandle(1),), "inserts", (inserted,))
        graph = builder.build()
        assert graph.resolve(case["graph_anchor"]).kind is EndpointKind.COARSE_TICK
        result = {"verdict": "valid", "kind": "insertion"}
    elif case_id == "deleted-boundary-run-site":
        coordinates = LegacyCoordinates(
            (
                LegacyOccurrence(True),
                LegacyOccurrence(False, True),
                LegacyOccurrence(False, True),
                LegacyOccurrence(True),
            )
        )
        site = case["legacy_site"]
        span = case["graph_span"]
        assert coordinates.to_graph(site["start"]) == PositionHandle(1, 0)
        assert coordinates.to_graph(site["end"]) == PositionHandle(1, 2)
        assert span == {
            "start": "/clock/1/gaps/0",
            "end": "/clock/1/gaps/2",
        }
        result = {"verdict": "valid", "kind": "deletion"}
    elif case_id == "interval-crosses-tier-boundary":
        units = case["legacy_units"]
        builder = GraphBuilder(declarations())
        for unit in units:
            if unit in {".", "‿"}:
                builder.append_input_occurrence(
                    "boundary", value(unit), refines_tick=True
                )
            else:
                builder.append_input_atom("input", value(unit))
        builder.build()
        coordinates = builder.compatibility_coordinates()
        interval = case["legacy_interval"]
        start = coordinates.to_graph(interval["start"])
        end = coordinates.to_graph(interval["end"])
        round_tripped_start = coordinates.to_legacy(start)
        round_tripped_end = coordinates.to_legacy(end)
        contained = [
            item for item in units[round_tripped_start:round_tripped_end] if item == "‿"
        ]
        result = {"verdict": "valid", "contains_boundaries": contained}
    else:
        raise AssertionError(f"unexecuted Lane C fixture: {case_id}")

    assert result == expected


def test_lane_c_fixture_ownership_is_explicit_and_complete() -> None:
    assert tuple(case["id"] for case in lane_c_cases()) == LANE_C_FIXTURE_CASES


def test_clock_consumption_and_boundary_coordinate_fixtures() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("a"))
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_occurrence("boundary", value("stress"), refines_tick=False)
    builder.append_input_atom("input", value("zero"))
    builder.append_input_occurrence("boundary", value("#"), refines_tick=True)
    current = builder.build()
    assert len(current.clock) == 3
    assert [node.gap_count for node in current.clock] == [1, 2, 2]

    # a . # zero space b: only the two declared boundaries refine positions.
    longer = GraphBuilder(declarations())
    longer.append_input_atom("input", value("a"))
    longer.append_input_occurrence("boundary", value("."), refines_tick=True)
    longer.append_input_occurrence("boundary", value("#"), refines_tick=True)
    longer.append_input_atom("input", value("zero"))
    longer.append_input_occurrence("boundary", value("space"), refines_tick=False)
    longer.append_input_atom("input", value("b"))
    assert len(longer.build().clock) == 4


def test_builder_lane_order_is_independent_of_containment() -> None:
    builder = GraphBuilder(declarations())
    input_handle = builder.append_input_atom("input", value("x"))
    first = builder.add_event("derived", 1, value("first"), duration=0)
    later = builder.add_event("derived", 1, value("later"), duration=0)
    parent = builder.add_event("top", 1, value("parent"), duration=0)
    builder.contain(parent, (later, first))
    current = builder.build()
    assert builder.scan_order() == (input_handle, parent, first, later)
    assert [event.features["value"] for event in current.clock[1].groups[1].events] == [
        "first",
        "later",
    ]
    assert ContainmentProjection.build(current).direct_children("/clock/1/top/0") == (
        "/clock/1/derived/1",
        "/clock/1/derived/0",
    )


def test_chained_phantom_sequences_have_pinned_subsequent_scan_order() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("x"))
    p3 = builder.add_ordered_sequence(
        "derived",
        0,
        (EventSpec(value("p3")),),
        derivation_step=2,
        source_site_order=0,
        application_order=0,
    )[0]
    p1_sequence = builder.add_ordered_sequence(
        "derived",
        0,
        (EventSpec(value("p0")), EventSpec(value("p1"))),
        derivation_step=1,
        source_site_order=0,
        application_order=0,
    )
    p2 = builder.add_ordered_sequence(
        "derived",
        0,
        (EventSpec(value("p2")),),
        derivation_step=1,
        source_site_order=1,
        application_order=0,
    )[0]
    assert builder.scan_order("derived") == (*p1_sequence, p2, p3)
    graph = builder.build()
    assert [event.features["value"] for event in graph.clock[0].groups[1].events] == [
        "p0",
        "p1",
        "p2",
        "p3",
    ]


def test_repeated_boundary_run_span_and_legacy_round_trip() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("a"))
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_atom("input", value("b"))
    builder.add_span("derived", builder.tick(0), builder.gap(1, 1), value("mora"))
    current = builder.build()
    assert len(current.clock) == 3
    assert [node.gap_count for node in current.clock] == [1, 3, 1]
    assert current.to_data()["clock"][0]["derived"][0]["span"] == {
        "start": "/clock/0",
        "end": "/clock/1/gaps/1",
    }
    coordinates = builder.compatibility_coordinates()
    assert coordinates.to_graph(2) == PositionHandle(1, 1)
    assert coordinates.to_legacy(PositionHandle(1, 1)) == 2


def test_insertion_deletion_and_cross_tier_fixture_positions() -> None:
    coordinates = LegacyCoordinates(
        (
            LegacyOccurrence(True),
            LegacyOccurrence(False, True),
            LegacyOccurrence(False, True),
            LegacyOccurrence(True),
        )
    )
    assert coordinates.to_graph(1) == PositionHandle(1, 0)
    assert coordinates.to_graph(3) == PositionHandle(1, 2)
    assert coordinates.to_legacy(PositionHandle(1, 0)) == 1
    assert coordinates.to_legacy(PositionHandle(1, 2)) == 3

    crossing = LegacyCoordinates(
        tuple(
            (
                LegacyOccurrence(False, True)
                if item in {".", "‿"}
                else LegacyOccurrence(True)
            )
            for item in ("p", "ə", ".", "t", "i", "‿", "a", ".", "m", "i")
        )
    )
    start, end = crossing.to_graph(3), crossing.to_graph(7)
    assert crossing.to_legacy(start) == 3
    assert crossing.to_legacy(end) == 7


def test_equivalent_construction_paths_are_byte_identical() -> None:
    def construct(parsed: bool) -> Graph:
        builder = GraphBuilder(declarations())
        atoms = ("a", "b") if parsed else tuple(["a", "b"])
        handles = [builder.append_input_atom("input", value(atom)) for atom in atoms]
        group = builder.begin("top", value("word"), start=0)
        builder.end(group, 2)
        builder.contain(group, handles)
        builder.add_root(group)
        return builder.build()

    left, right = construct(True), construct(False)
    assert left == right
    assert json.dumps(left.to_data(), separators=(",", ":")) == json.dumps(
        right.to_data(), separators=(",", ":")
    )


def test_insertions_before_between_and_after_input_keep_handles_resolvable() -> None:
    builder = GraphBuilder(declarations())
    before = builder.add_event("derived", 0, value("before"), duration=0)
    inputs = [builder.append_input_atom("input", value(item)) for item in ("a", "b")]
    between = builder.add_event("derived", 1, value("between"), duration=0)
    after = builder.add_event("derived", 2, value("after"), duration=0)
    builder.relate((builder.tick(0),), "inserts", (before,))
    builder.relate((builder.tick(1),), "inserts", (between,))
    builder.relate((builder.tick(2),), "inserts", (after,))
    builder.relate(inputs, "rewrites-to", (before, between, after))
    current = builder.build()
    for relation in current.relations:
        for reference in (*relation.sources, *relation.targets):
            current.resolve(reference)
    assert len(current.clock) == 3


def test_endpoint_canonicalization_before_within_and_after_boundary_run() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("a"))
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_atom("input", value("b"))
    builder.add_span("derived", builder.gap(0, 0), builder.gap(1, 1), value("left"))
    builder.add_span("derived", builder.gap(1, 0), builder.gap(1, 2), value("run"))
    builder.add_span("derived", builder.gap(1, 2), builder.gap(2, 0), value("right"))
    current = builder.build()
    spans = [
        event.span
        for node in current.clock
        for group in node.groups
        if group.tier == "derived"
        for event in group.events
    ]
    assert [(span.start, span.end) for span in spans if span is not None] == [
        ("/clock/0", "/clock/1/gaps/1"),
        ("/clock/1/gaps/0", "/clock/1/gaps/2"),
        ("/clock/1/gaps/2", "/clock/2"),
    ]


def test_unfinished_open_is_refused() -> None:
    builder = GraphBuilder(declarations())
    builder.begin("top", value("open"))
    with pytest.raises(GraphValidationError, match="unfinished open"):
        builder.build()


def test_build_restore_and_persistent_edits_preserve_order_without_ids() -> None:
    builder = GraphBuilder(declarations())
    handles = [builder.append_input_atom("input", value(item)) for item in ("a", "b")]
    builder.relate((handles[0],), "rewrites-to", (handles[1],))
    current = builder.build()
    restored = Graph.from_data(declarations(), current.to_data())
    assert restored == current
    assert all(
        "id" not in event
        for node in current.to_data()["clock"]
        for tier, events in node.items()
        if tier != "gaps"
        for event in events
    )

    added = add_event_copy(current, "derived", 0, value("x"), duration=0)
    linked = add_relation_copy(
        added, ("/clock/0/input/0",), "rewrites-to", ("/clock/0/derived/0",)
    )
    added_relation = next(
        relation
        for relation in linked.relations
        if relation.targets == ("/clock/0/derived/0",)
    )
    unlinked = remove_relations_copy(linked, (added_relation,))
    removed = remove_events_copy(unlinked, ("/clock/0/derived/0",))
    assert removed == current


def test_persistent_event_removal_rejects_clock_consuming_input_atom() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("a"))
    builder.append_input_atom("input", value("b"))

    with pytest.raises(
        GraphValidationError,
        match=(
            r"clock-consuming input atom /clock/1/input/0: "
            r"the structural clock is immutable and input-owned"
        ),
    ):
        remove_events_copy(builder.build(), ("/clock/1/input/0",))


def test_persistent_refiner_removal_preserves_input_owned_gaps_and_spans() -> None:
    builder = GraphBuilder(declarations())
    builder.append_input_atom("input", value("a"))
    builder.append_input_occurrence("boundary", value("."), refines_tick=True)
    builder.append_input_occurrence("boundary", value("‿"), refines_tick=True)
    builder.append_input_atom("input", value("b"))
    builder.add_span("derived", builder.gap(1, 0), builder.gap(1, 2), value("syllable"))
    current = builder.build()

    removed = remove_events_copy(current, ("/clock/1/boundary/0",))

    assert [node.gap_count for node in removed.clock] == [1, 3, 1]
    assert removed.to_data()["clock"][1]["derived"][0]["span"] == {
        "start": "/clock/1/gaps/0",
        "end": "/clock/1/gaps/2",
    }
