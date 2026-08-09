"""Plain-JSON transport for tier graphs.

The wire layer stays separate from the kernel so model lookup and profile value
construction cannot weaken the graph's construction-time validation laws.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Protocol, TypeGuard, cast

from ._tiergraph import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FrozenValue,
    Graph,
    GraphValidationError,
    JsonValue,
    RefinedSpan,
    Relation,
    RelationDeclaration,
    Timing,
    _thaw,
)

_TYPE = "tiergraph"
_VERSION = 1
_EVENT_KEYS = {"features", "duration", "span", "timing"}


class ValueCodec(Protocol):
    """Translate profile-owned event facts without teaching the kernel profiles."""

    def encode(self, tier: str, event: Event) -> dict[str, JsonValue]: ...

    def decode(self, tier: str, data: Mapping[str, JsonValue]) -> Event: ...


@dataclass(frozen=True)
class Model:
    """Bind a stable wire identity to the declarations that validate it."""

    name: str
    version: str
    declarations: Declarations
    values: ValueCodec | None = None


class PlainValues:
    """Carry generic kernel features while preserving its canonical recursion."""

    def encode(self, tier: str, event: Event) -> dict[str, JsonValue]:
        del tier
        result: dict[str, JsonValue] = {
            "features": {
                name: _thaw(value) for name, value in sorted(event.features.items())
            }
        }
        _add_extent_and_timing(result, event)
        return result

    def decode(self, tier: str, data: Mapping[str, JsonValue]) -> Event:
        del tier
        if set(data) - _EVENT_KEYS:
            raise GraphValidationError("malformed event")
        raw_features = data.get("features")
        if not isinstance(raw_features, dict):
            raise GraphValidationError("malformed event")
        return _event(dict(raw_features), data)


class IPAValues:
    """Preserve structured IPA occurrences and validate their resolved views."""

    _KEYS = {
        "spelling",
        "value",
        "features",
        "prosody",
        "provenance",
        "duration",
        "span",
        "timing",
    }

    def __init__(self, inventory: object) -> None:
        # The annotation remains structural here to keep generic users from
        # importing the IPA inventory merely by importing this module.
        from .features import IPAFeatures

        if not isinstance(inventory, IPAFeatures):
            raise TypeError("IPAValues requires an IPAFeatures inventory")
        self.inventory = inventory

    def encode(self, tier: str, event: Event) -> dict[str, JsonValue]:
        from .segment import Segment

        value = event.features.get("value")
        if tier != "segment" or not isinstance(value, Segment):
            return PlainValues().encode(tier, event)
        spelling = event.features.get("spelling")
        provenance = event.features.get("provenance", ())
        if not isinstance(spelling, str):
            raise GraphValidationError("structured segment requires exact spelling")
        prosodic = self.inventory.features_by_mode.get("prosodic", frozenset())
        ordinary = {
            name: _thaw(item)
            for name, item in sorted(event.features.items())
            if name not in {"value", "spelling", "provenance"} and name not in prosodic
        }
        prosody = {
            name: _thaw(item)
            for name, item in sorted(event.features.items())
            if name in prosodic
        }
        result: dict[str, JsonValue] = {
            "spelling": spelling,
            "value": cast(JsonValue, value.to_dict()),
            "features": ordinary,
            "prosody": prosody,
            "provenance": _thaw(cast(FrozenValue, provenance)),
        }
        self._validated_features(result)
        _add_extent_and_timing(result, event)
        return result

    def decode(self, tier: str, data: Mapping[str, JsonValue]) -> Event:
        raw_value = data.get("value")
        if tier != "segment" or raw_value is None:
            return PlainValues().decode(tier, data)
        if set(data) - self._KEYS:
            raise GraphValidationError("malformed structured segment event")
        facts = self._validated_features(data)
        return _event(facts, data)

    def _validated_features(self, data: Mapping[str, JsonValue]) -> dict[str, object]:
        from .form import Form

        spelling = data.get("spelling")
        value = data.get("value")
        features = data.get("features")
        prosody = data.get("prosody")
        provenance = data.get("provenance")
        if (
            not isinstance(spelling, str)
            or not isinstance(value, dict)
            or not isinstance(features, dict)
            or not isinstance(prosody, dict)
            or not isinstance(provenance, list)
        ):
            raise GraphValidationError("malformed structured segment event")
        form_data = {
            "type": "ipakit.form",
            "v": 1,
            "units": [
                {
                    "text": spelling,
                    "segment": value,
                    "features": features,
                    "prosody": prosody,
                    "provenance": provenance,
                    "timing": None,
                }
            ],
            "intervals": [],
            "spelling": spelling,
        }
        try:
            unit = Form.from_dict(form_data, self.inventory).units[0]
        except (KeyError, TypeError, ValueError) as error:
            raise GraphValidationError("invalid structured segment event") from error
        return {
            "value": unit.segment,
            "spelling": spelling,
            **dict(unit.features),
            **dict(unit.prosody),
            "provenance": unit.provenance,
        }


def to_data(graph: Graph, model: Model) -> dict[str, JsonValue]:
    """Create the envelope only when its model is the graph's exact contract."""
    if graph.declarations != model.declarations:
        raise GraphValidationError("model declarations do not match graph")
    values = model.values or PlainValues()
    return {
        "type": _TYPE,
        "v": _VERSION,
        "model": {"name": model.name, "version": model.version},
        "tiers": [tier.name for tier in graph.declarations.tiers],
        "relations": {
            relation.name: _relation_declaration(relation)
            for relation in graph.declarations.relations
        },
        "roots": list(graph.roots),
        "clock": [
            _clock_node(node, graph.declarations, values) for node in graph.clock
        ],
        "links": [
            [list(link.sources), link.name, list(link.targets)]
            for link in graph.relations
        ],
    }


def from_data(data: Mapping[str, JsonValue], model: Model) -> Graph:
    """Restore through Event and Graph constructors so wire input earns validity."""
    envelope_keys = {
        "type",
        "v",
        "model",
        "tiers",
        "relations",
        "roots",
        "clock",
        "links",
    }
    if set(data) != envelope_keys:
        raise GraphValidationError("malformed tiergraph envelope")
    if data.get("type") != _TYPE or data.get("v") != _VERSION:
        raise GraphValidationError("unsupported tiergraph representation")
    if data.get("model") != {"name": model.name, "version": model.version}:
        raise GraphValidationError("tiergraph model does not match")
    tiers = [tier.name for tier in model.declarations.tiers]
    if data.get("tiers") != tiers:
        raise GraphValidationError("tier declarations do not match graph data")
    expected_relations = {
        item.name: _relation_declaration(item) for item in model.declarations.relations
    }
    if data.get("relations") != expected_relations:
        raise GraphValidationError("relation declarations do not match graph data")
    raw_clock = data.get("clock")
    raw_roots = data.get("roots")
    raw_links = data.get("links")
    if (
        not isinstance(raw_clock, list)
        or not isinstance(raw_roots, list)
        or not isinstance(raw_links, list)
    ):
        raise GraphValidationError("malformed tiergraph envelope")
    values = model.values or PlainValues()
    clock = tuple(_restore_node(item, model.declarations, values) for item in raw_clock)
    roots = tuple(_string(item) for item in raw_roots)
    links = tuple(_restore_link(item) for item in raw_links)
    return Graph(model.declarations, clock, links, roots)


def dumps(graph: Graph, model: Model) -> str:
    """Emit stable UTF-8-friendly bytes independent of mapping insertion history."""
    return json.dumps(to_data(graph, model), ensure_ascii=False, separators=(",", ":"))


def loads(value: str, model: Model) -> Graph:
    """Reject non-object JSON before handing plain data to restoration."""
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GraphValidationError("malformed tiergraph JSON") from error
    if not isinstance(data, dict):
        raise GraphValidationError("malformed tiergraph envelope")
    return from_data(cast(Mapping[str, JsonValue], data), model)


def _relation_declaration(value: RelationDeclaration) -> JsonValue:
    defaults = RelationDeclaration(value.name)
    result: dict[str, JsonValue] = {}
    for field in fields(RelationDeclaration):
        name = field.name
        if name == "name":
            continue
        current = getattr(value, name)
        if current == getattr(defaults, name):
            continue
        if isinstance(current, frozenset):
            current = sorted(
                item.value if hasattr(item, "value") else item for item in current
            )
        elif isinstance(current, tuple):
            current = list(current)
        result[name] = cast(JsonValue, current)
    return result


def _clock_node(
    node: ClockNode, declarations: Declarations, values: ValueCodec
) -> JsonValue:
    result: dict[str, JsonValue] = {"gaps": [{} for _ in range(node.gap_count)]}
    groups = {group.tier: group for group in node.groups}
    for tier in declarations.tiers:
        group = groups.get(tier.name)
        if group is not None:
            result[tier.name] = [
                values.encode(tier.name, event) for event in group.events
            ]
    return result


def _restore_node(
    raw: JsonValue, declarations: Declarations, values: ValueCodec
) -> ClockNode:
    if not isinstance(raw, dict):
        raise GraphValidationError("malformed clock node")
    raw_gaps = raw.get("gaps")
    if (
        not isinstance(raw_gaps, list)
        or not raw_gaps
        or any(item != {} for item in raw_gaps)
    ):
        raise GraphValidationError("noncanonical gap nodes")
    tier_names = {tier.name for tier in declarations.tiers}
    if set(raw) - tier_names - {"gaps"}:
        raise GraphValidationError("undeclared tier")
    groups: list[EventGroup] = []
    for tier in declarations.tiers:
        raw_events = raw.get(tier.name)
        if raw_events is None:
            continue
        if not isinstance(raw_events, list) or not raw_events:
            raise GraphValidationError("noncanonical event group")
        groups.append(
            EventGroup(
                tier.name,
                tuple(
                    values.decode(tier.name, _mapping(item, "event"))
                    for item in raw_events
                ),
            )
        )
    return ClockNode(len(raw_gaps), tuple(groups))


def _add_extent_and_timing(result: dict[str, JsonValue], event: Event) -> None:
    if event.span is not None:
        result["span"] = {"start": event.span.start, "end": event.span.end}
    elif event.duration is not None:
        result["duration"] = event.duration
    if event.timing is not None:
        result["timing"] = {
            "start": event.timing.start,
            "duration": event.timing.duration,
        }


def _event(features: Mapping[str, object], data: Mapping[str, JsonValue]) -> Event:
    duration = data.get("duration")
    if duration is not None and (
        not isinstance(duration, int) or isinstance(duration, bool)
    ):
        raise GraphValidationError("malformed structural duration")
    raw_span = data.get("span")
    span = None
    if raw_span is not None:
        span_data = _mapping(raw_span, "refined span")
        if set(span_data) != {"start", "end"}:
            raise GraphValidationError("malformed refined span")
        span = RefinedSpan(_string(span_data["start"]), _string(span_data["end"]))
    raw_timing = data.get("timing")
    timing = None
    if raw_timing is not None:
        timing_data = _mapping(raw_timing, "physical timing")
        if set(timing_data) != {"start", "duration"}:
            raise GraphValidationError("malformed physical timing")
        start, physical_duration = timing_data["start"], timing_data["duration"]
        if not _number(start) or not _number(physical_duration):
            raise GraphValidationError("malformed physical timing")
        timing = Timing(float(start), float(physical_duration))
    return Event(cast(Mapping[str, FrozenValue], features), duration, span, timing)


def _restore_link(raw: JsonValue) -> Relation:
    if not isinstance(raw, list) or len(raw) != 3:
        raise GraphValidationError("malformed relation")
    sources, name, targets = raw
    if not isinstance(sources, list) or not isinstance(targets, list):
        raise GraphValidationError("malformed relation")
    return Relation(
        tuple(_string(item) for item in sources),
        _string(name),
        tuple(_string(item) for item in targets),
    )


def _mapping(value: object, label: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise GraphValidationError(f"malformed {label}")
    return cast(Mapping[str, JsonValue], value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise GraphValidationError("malformed graph data")
    return value


def _number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
