from __future__ import annotations

from ipakit import Form, IPAFeatures
from ipakit._gesture_backend import oral_tract_frames
from ipakit._gesture_graph import (
    GESTURE_TIER,
    PROJECTS_TO,
    TARGET_TIER,
    GestureValues,
    declarations,
    project,
)
from ipakit._tiergraph import Timing
from ipakit._tiergraph_json import Model, dumps, loads
from ipakit.form import _graph_from_compatibility
from ipakit.tract import constrictions


def _inventory_and_graph(text: str = "ata"):
    inventory = IPAFeatures()
    form = Form.parse(text, inventory)
    return inventory, _graph_from_compatibility(form.units, form.intervals)


def _timings(*values: tuple[float, float]):
    return {
        f"/clock/{index}/segment/0": (Timing(start, duration),)
        for index, (start, duration) in enumerate(values)
    }


def test_profile_declares_gesture_and_target_tiers_outside_kernel() -> None:
    inventory, _ = _inventory_and_graph()
    declared = declarations(inventory)

    assert declared.tier(GESTURE_TIER) is not None
    assert declared.tier(TARGET_TIER) is not None
    relation = declared.relation(PROJECTS_TO)
    assert relation is not None
    assert relation.source_tiers == frozenset({"segment", GESTURE_TIER})


def test_projection_reads_inventory_tract_vocabulary() -> None:
    inventory, graph = _inventory_and_graph("w")
    projected = project(graph, inventory)
    expected = constrictions(inventory, inventory.get_features("w"))
    gestures = next(
        group for group in projected.clock[0].groups if group.tier == GESTURE_TIER
    ).events

    assert len(gestures) == len(expected) == 2
    assert tuple(event.features["arc"] for event in gestures) == tuple(
        point.arc for point in expected
    )
    assert tuple(event.features["articulator"] for event in gestures) == tuple(
        point.articulator for point in expected
    )


def test_timed_targets_follow_time_while_fallbacks_follow_structure() -> None:
    inventory, segments = _inventory_and_graph()
    gestures = project(segments, inventory)
    timed = project(
        segments,
        inventory,
        target_timing=_timings((0.90, 0.08), (0.50, 0.0), (0.10, 0.12)),
    )

    timed_frames = oral_tract_frames(timed, inventory)
    gesture_frames = oral_tract_frames(gestures, inventory)
    segment_frames = oral_tract_frames(segments, inventory)

    assert {frame.level for frame in timed_frames} == {"timed-targets"}
    assert [(f.timing.start, f.timing.duration) for f in timed_frames] == [
        (0.10, 0.12),
        (0.50, 0.0),
        (0.90, 0.08),
    ]
    assert [frame.source for frame in timed_frames] == [
        f"/clock/2/{TARGET_TIER}/0",
        f"/clock/1/{TARGET_TIER}/0",
        f"/clock/0/{TARGET_TIER}/0",
    ]
    assert {frame.level for frame in gesture_frames} == {"gestures"}
    assert all(frame.timing is None for frame in gesture_frames)
    assert [frame.source for frame in gesture_frames] == [
        f"/clock/0/{GESTURE_TIER}/0",
        f"/clock/1/{GESTURE_TIER}/0",
        f"/clock/2/{GESTURE_TIER}/0",
    ]
    assert {frame.level for frame in segment_frames} == {"segments"}
    assert all(frame.timing is None for frame in segment_frames)
    assert [frame.source for frame in segment_frames] == [
        "/clock/0/segment/0",
        "/clock/1/segment/0",
        "/clock/2/segment/0",
    ]
    assert [frame.point for frame in gesture_frames] == [
        frame.point for frame in segment_frames
    ]


def test_equal_start_targets_keep_numeric_graph_order_past_ten_ticks() -> None:
    inventory, segments = _inventory_and_graph("a" * 12)
    timed = project(
        segments,
        inventory,
        target_timing=_timings(*((0.25, 0.0),) * 12),
    )

    frames = oral_tract_frames(timed, inventory)

    assert [frame.source for frame in frames] == [
        f"/clock/{tick}/{TARGET_TIER}/0" for tick in range(12)
    ]


def test_partial_target_timing_falls_back_without_dropping_occurrences() -> None:
    inventory, segments = _inventory_and_graph("at")
    partial = project(
        segments,
        inventory,
        target_timing={"/clock/0/segment/0": (Timing(0.0, 0.1),)},
    )
    frames = oral_tract_frames(partial, inventory)

    assert len(frames) == 2
    assert {frame.level for frame in frames} == {"gestures"}
    assert all(frame.timing is None for frame in frames)


def test_occurrence_timing_overlap_point_targets_and_round_trip() -> None:
    inventory, segments = _inventory_and_graph("aa")
    first_value = segments.clock[0].groups[0].events[0].features["value"]
    second_value = segments.clock[1].groups[0].events[0].features["value"]
    assert first_value == second_value

    projected = project(
        segments,
        inventory,
        gesture_timing=_timings((0.0, 0.20), (0.10, 0.25)),
        target_timing=_timings((0.05, 0.0), (0.30, 0.0)),
    )
    model = Model(
        "ipakit-gesture", "1", declarations(inventory), GestureValues(inventory)
    )
    restored = loads(dumps(projected, model), model)
    gesture_events = [
        event
        for node in restored.clock
        for group in node.groups
        if group.tier == GESTURE_TIER
        for event in group.events
    ]
    target_events = [
        event
        for node in restored.clock
        for group in node.groups
        if group.tier == TARGET_TIER
        for event in group.events
    ]

    assert [event.timing for event in gesture_events] == [
        Timing(0.0, 0.20),
        Timing(0.10, 0.25),
    ]
    assert (
        gesture_events[0].timing.start + gesture_events[0].timing.duration
        > gesture_events[1].timing.start
    )
    assert [event.structural_duration for event in target_events] == [0, 0]
    assert [event.timing.duration for event in target_events] == [0.0, 0.0]
    assert restored == projected
    assert not hasattr(first_value, "timing")
