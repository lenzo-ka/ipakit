"""Read-only oral-tract traversal with explicit progressive fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import tiergraph

from ._gesture_graph import GESTURE_TIER, TARGET_TIER
from ._graph_facts import Event, Timing
from ._ipa_graph import SEGMENT_TIER
from .features import IPAFeatures
from .segment import Segment
from .tract import Head, TractPoint, constrictions, head

FrameLevel = Literal["timed-targets", "gestures", "segments"]


@dataclass(frozen=True)
class ArticulatoryFrame:
    """One declared posture sample; no interpolation or implicit clock."""

    level: FrameLevel
    source: str
    point: TractPoint
    projected: tuple[float, float] | None
    timing: Timing | None = None


def oral_tract_frames(
    graph: Any,
    inventory: IPAFeatures,
    *,
    head_shape: Head | None = None,
) -> tuple[ArticulatoryFrame, ...]:
    """Use complete timed targets, else gestures, else structural segments.

    A partially timed target tier is deliberately not treated as a timeline:
    doing so would silently discard its untimed members.  Structural fallback
    preserves graph scan order and leaves ``timing`` absent.
    """

    drawing_head = head_shape or head()
    targets = _tier_events(graph, TARGET_TIER)
    if targets and all(event.timing is not None for _, event in targets):
        ordered = sorted(
            enumerate(targets),
            key=lambda item: (item[1][1].timing.start, item[0]),  # type: ignore[union-attr]
        )
        return tuple(
            _declared_frame("timed-targets", ref, event, drawing_head)
            for _, (ref, event) in ordered
        )

    gestures = _tier_events(graph, GESTURE_TIER)
    if gestures:
        return tuple(
            _declared_frame("gestures", ref, event, drawing_head)
            for ref, event in gestures
        )

    frames: list[ArticulatoryFrame] = []
    for reference, event in _tier_events(graph, SEGMENT_TIER):
        value = event.features.get("value")
        if not isinstance(value, Segment):
            continue
        for point in constrictions(inventory, inventory.get_features(value.to_ipa())):
            frames.append(
                ArticulatoryFrame(
                    "segments", reference, point, drawing_head.project(point), None
                )
            )
    return tuple(frames)


def _tier_events(graph: Any, tier: str) -> list[tuple[str, Event]]:
    if not isinstance(graph, tiergraph.Graph):
        return [
            (reference, graph.events[reference])
            for reference in graph.refs
            if graph.event_tiers[reference] == tier
        ]
    native_events = []
    for native_tier in graph.tiers:
        if native_tier.declaration.long_name != tier:
            continue
        for index, item in enumerate(native_tier.items):
            attributes = {
                value.name.local_name: value.lexical for value in item.attributes
            }
            timing = (
                Timing(
                    float(attributes["timing-start"]),
                    float(attributes["timing-duration"]),
                )
                if "timing-start" in attributes
                else None
            )
            features: dict[str, object] = {
                name: attributes[name]
                for name in ("kind", "articulator", "source-value")
                if name in attributes
            }
            features.update(
                {
                    name: float(attributes[name])
                    for name in ("arc", "offset")
                    if name in attributes
                }
            )
            if "target-index" in attributes:
                features["target-index"] = int(attributes["target-index"])
            reference = tiergraph.ItemRef(native_tier.declaration.name, index)
            native_events.append((str(reference), Event(features, timing=timing)))
    return native_events


def _declared_frame(
    level: FrameLevel, reference: str, event: Event, drawing_head: Head
) -> ArticulatoryFrame:
    raw_arc = event.features.get("arc")
    raw_offset = event.features.get("offset")
    raw_articulator = event.features.get("articulator")
    point = TractPoint(
        arc=float(raw_arc) if isinstance(raw_arc, (int, float)) else None,
        offset=float(raw_offset) if isinstance(raw_offset, (int, float)) else None,
        articulator=raw_articulator if isinstance(raw_articulator, str) else None,
    )
    return ArticulatoryFrame(
        level,
        reference,
        point,
        drawing_head.project(point),
        event.timing,
    )
