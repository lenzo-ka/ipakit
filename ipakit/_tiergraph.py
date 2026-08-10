"""Immutable primitives for model-declared, structurally timed graphs.

This module deliberately has no profile vocabulary.  It exists below public
construction APIs so profiles can share addressing and validation laws without
making those laws depend on a spelling system.  ``Graph.roots`` may be empty;
root-reachability diagnostics belong to higher profile lanes.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TypeAlias, cast

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
FrozenValue: TypeAlias = object

_NODE_STRUCTURAL_KEYS = frozenset({"gaps"})


class GraphValidationError(ValueError):
    """Identify graph-contract failures separately from ordinary API mistakes."""


class EndpointKind(StrEnum):
    COARSE_TICK = "coarse-tick"
    REFINED_GAP = "refined-gap"
    EVENT = "event"


@dataclass(frozen=True)
class FeatureDeclaration:
    name: str

    def __post_init__(self) -> None:
        _validate_name(self.name, "feature")


@dataclass(frozen=True)
class TierDeclaration:
    name: str
    features: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _validate_name(self.name, "tier")


@dataclass(frozen=True)
class RelationDeclaration:
    name: str
    ordered: bool = True
    acyclic: bool = False
    source_tiers: frozenset[str] | None = None
    target_tiers: frozenset[str] | None = None
    source_kinds: frozenset[EndpointKind] = frozenset({EndpointKind.EVENT})
    target_kinds: frozenset[EndpointKind] = frozenset({EndpointKind.EVENT})
    source_arity: tuple[int, int | None] = (1, None)
    target_arity: tuple[int, int | None] = (1, None)
    allow_empty_source: bool = False
    allow_empty_target: bool = False
    semantic_precedence: bool = False
    containment: bool = False
    choice: bool = False
    member_of: str | None = None

    def __post_init__(self) -> None:
        _validate_name(self.name, "relation")
        _validate_arity(self.source_arity, "source")
        _validate_arity(self.target_arity, "target")
        if self.member_of is not None and self.target_arity != (1, 1):
            raise GraphValidationError("member_of relation requires target arity 1")


@dataclass(frozen=True)
class Declarations:
    tiers: tuple[TierDeclaration, ...]
    features: tuple[FeatureDeclaration, ...]
    relations: tuple[RelationDeclaration, ...]
    closed: bool = True

    def __post_init__(self) -> None:
        _unique((item.name for item in self.tiers), "tier declaration")
        _unique((item.name for item in self.features), "feature declaration")
        _unique((item.name for item in self.relations), "relation declaration")
        feature_names = {item.name for item in self.features}
        relation_names = {item.name for item in self.relations}
        if any(tier.name in _NODE_STRUCTURAL_KEYS for tier in self.tiers):
            raise GraphValidationError("tier name is reserved for graph structure")
        for tier in self.tiers:
            if not tier.features <= feature_names:
                raise GraphValidationError("tier permits an undeclared feature")
        for relation in self.relations:
            if (
                relation.member_of is not None
                and relation.member_of not in relation_names
            ):
                raise GraphValidationError("member_of names an undeclared relation")

    def tier(self, name: str) -> TierDeclaration | None:
        return next((item for item in self.tiers if item.name == name), None)

    def relation(self, name: str) -> RelationDeclaration | None:
        return next((item for item in self.relations if item.name == name), None)


@dataclass(frozen=True, order=True)
class Position:
    tick: int
    gap: int = 0


@dataclass(frozen=True)
class RefinedSpan:
    start: str
    end: str


@dataclass(frozen=True)
class Timing:
    start: float
    duration: float


@dataclass(frozen=True)
class Event:
    features: Mapping[str, FrozenValue]
    duration: int | None = None
    span: RefinedSpan | None = None
    timing: Timing | None = None

    def __post_init__(self) -> None:
        if self.duration == 1:
            object.__setattr__(self, "duration", None)
        object.__setattr__(
            self,
            "features",
            MappingProxyType(
                {
                    name: _freeze(cast(JsonValue, value))
                    for name, value in self.features.items()
                }
            ),
        )
        if self.duration is not None and self.span is not None:
            raise GraphValidationError("span and duration are mutually exclusive")

    @property
    def structural_duration(self) -> int | None:
        return (
            None
            if self.span is not None
            else (1 if self.duration is None else self.duration)
        )


@dataclass(frozen=True)
class EventGroup:
    tier: str
    events: tuple[Event, ...]


@dataclass(frozen=True)
class ClockNode:
    gap_count: int = 1
    groups: tuple[EventGroup, ...] = ()


@dataclass(frozen=True)
class Relation:
    sources: tuple[str, ...]
    name: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedReference:
    pointer: str
    kind: EndpointKind
    tick: int
    gap: int | None = None
    tier: str | None = None
    event: Event | None = None


@dataclass(frozen=True)
class Graph:
    declarations: Declarations
    clock: tuple[ClockNode, ...]
    relations: tuple[Relation, ...] = ()
    roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relations",
            tuple(
                sorted(
                    self.relations,
                    key=lambda relation: (
                        relation.sources,
                        relation.name,
                        relation.targets,
                    ),
                )
            ),
        )
        self.validate()

    def resolve(self, pointer: str) -> ResolvedReference:
        parts = _pointer_parts(pointer)
        if len(parts) < 2 or parts[0] != "clock" or not parts[1].isdigit():
            raise GraphValidationError("malformed JSON Pointer reference")
        tick = int(parts[1])
        if tick >= len(self.clock):
            raise GraphValidationError("dangling JSON Pointer reference")
        node = self.clock[tick]
        if len(parts) == 2:
            return ResolvedReference(pointer, EndpointKind.COARSE_TICK, tick)
        if len(parts) == 4 and parts[2] == "gaps" and parts[3].isdigit():
            gap = int(parts[3])
            if gap >= node.gap_count:
                raise GraphValidationError("gap does not belong to named tick")
            return ResolvedReference(pointer, EndpointKind.REFINED_GAP, tick, gap)
        if len(parts) == 4 and parts[3].isdigit():
            tier, index = parts[2], int(parts[3])
            group = next((group for group in node.groups if group.tier == tier), None)
            if group is None or index >= len(group.events):
                raise GraphValidationError("dangling JSON Pointer reference")
            return ResolvedReference(
                pointer, EndpointKind.EVENT, tick, tier=tier, event=group.events[index]
            )
        raise GraphValidationError("malformed JSON Pointer reference")

    def canonical_endpoint(self, pointer: str) -> str:
        resolved = self.resolve(pointer)
        if (
            resolved.kind is EndpointKind.REFINED_GAP
            and resolved.gap == 0
            and self.clock[resolved.tick].gap_count == 1
        ):
            return f"/clock/{resolved.tick}"
        return pointer

    def position(self, pointer: str, *, span_endpoint: bool = False) -> Position:
        resolved = self.resolve(pointer)
        if resolved.kind is EndpointKind.EVENT:
            raise GraphValidationError("span endpoint must name a clock position")
        refined = self.clock[resolved.tick].gap_count > 1
        if span_endpoint and refined and resolved.kind is EndpointKind.COARSE_TICK:
            raise GraphValidationError("refined span endpoint must name a gap")
        if resolved.kind is EndpointKind.REFINED_GAP:
            if not refined:
                raise GraphValidationError("noncanonical placement")
            assert resolved.gap is not None
            return Position(resolved.tick, resolved.gap)
        return Position(resolved.tick)

    def event_references(self) -> tuple[str, ...]:
        refs: list[str] = []
        for tick_index, node in enumerate(self.clock):
            for group in node.groups:
                refs.extend(
                    f"/clock/{tick_index}/{_escape(group.tier)}/{index}"
                    for index in range(len(group.events))
                )
        return tuple(refs)

    def direct_children(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        children = tuple(
            target
            for relation in self.relations
            if self._is_containment(relation) and relation.sources == (parent,)
            for target in relation.targets
        )
        if tier is None:
            return children
        return tuple(child for child in children if self.resolve(child).tier == tier)

    def descendants(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        result: list[str] = []
        pending = list(self.direct_children(parent))
        while pending:
            item = pending.pop(0)
            if tier is None or self.resolve(item).tier == tier:
                result.append(item)
            pending[0:0] = self.direct_children(item)
        return tuple(result)

    def leaves(self, parent: str) -> tuple[str, ...]:
        children = self.direct_children(parent)
        if not children:
            return (parent,)
        return tuple(leaf for child in children for leaf in self.leaves(child))

    def parents(self, child: str) -> tuple[str, ...]:
        return tuple(
            source
            for relation in self.relations
            if self._is_containment(relation) and child in relation.targets
            for source in relation.sources
        )

    def ancestors(self, child: str) -> tuple[str, ...]:
        result: list[str] = []
        pending = list(self.parents(child))
        while pending:
            item = pending.pop(0)
            if item not in result:
                result.append(item)
                pending.extend(self.parents(item))
        return tuple(result)

    def _is_containment(self, relation: Relation) -> bool:
        declaration = self.declarations.relation(relation.name)
        return declaration is not None and declaration.containment

    def validate(self) -> None:
        if not self.clock:
            raise GraphValidationError("clock requires a final tick")
        tier_order = {
            tier.name: index for index, tier in enumerate(self.declarations.tiers)
        }
        feature_names = {feature.name for feature in self.declarations.features}
        for tick_index, node in enumerate(self.clock):
            if node.gap_count < 1:
                raise GraphValidationError("noncanonical gap cardinality")
            order = [tier_order.get(group.tier, -1) for group in node.groups]
            if any(index < 0 for index in order):
                raise GraphValidationError("undeclared tier")
            if order != sorted(order) or len(order) != len(set(order)):
                raise GraphValidationError("noncanonical tier order")
            for group in node.groups:
                tier = self.declarations.tier(group.tier)
                assert tier is not None
                for event in group.events:
                    unknown = set(event.features) - feature_names
                    if self.declarations.closed and unknown:
                        raise GraphValidationError("undeclared feature")
                    if not set(event.features) <= tier.features:
                        raise GraphValidationError("feature not permitted on tier")
                    self._validate_event(tick_index, event)
        for root in self.roots:
            if self.resolve(root).kind is not EndpointKind.EVENT:
                raise GraphValidationError("root must resolve to an event")
        if len(self.relations) != len(set(self.relations)):
            raise GraphValidationError("duplicate relation")
        for relation in self.relations:
            self._validate_relation(relation)
        self._validate_choices()
        for declaration in self.declarations.relations:
            if declaration.acyclic:
                self._validate_acyclic(declaration.name)

    def _validate_event(self, tick: int, event: Event) -> None:
        if event.duration is not None and event.duration < 0:
            raise GraphValidationError("negative structural duration")
        if event.span is None:
            duration = event.structural_duration
            if duration is None:
                raise GraphValidationError("unfinished open event")
            if tick + duration > len(self.clock) - 1:
                raise GraphValidationError("structural span extends past final tick")
        else:
            start = self.position(event.span.start, span_endpoint=True)
            end = self.position(event.span.end, span_endpoint=True)
            if start.tick != tick:
                raise GraphValidationError(
                    "event path inconsistent with canonical placement"
                )
            if end < start:
                raise GraphValidationError("refined span end precedes start")
        if event.timing is not None:
            values = (event.timing.start, event.timing.duration)
            if not all(math.isfinite(value) for value in values):
                raise GraphValidationError("non-finite physical timing")
            if event.timing.duration < 0:
                raise GraphValidationError("negative physical duration")

    def _validate_relation(self, relation: Relation) -> None:
        declaration = self.declarations.relation(relation.name)
        if declaration is None:
            raise GraphValidationError("undeclared relation")
        _check_side(
            relation.sources,
            declaration.source_arity,
            declaration.allow_empty_source,
            "source",
        )
        _check_side(
            relation.targets,
            declaration.target_arity,
            declaration.allow_empty_target,
            "target",
        )
        self._validate_endpoints(
            relation.sources,
            declaration.source_kinds,
            declaration.source_tiers,
            "source",
        )
        self._validate_endpoints(
            relation.targets,
            declaration.target_kinds,
            declaration.target_tiers,
            "target",
        )

    def _validate_endpoints(
        self,
        pointers: tuple[str, ...],
        kinds: frozenset[EndpointKind],
        tiers: frozenset[str] | None,
        side: str,
    ) -> None:
        for pointer in pointers:
            resolved = self.resolve(pointer)
            if resolved.kind not in kinds:
                names = ", ".join(kind.value for kind in sorted(kinds, key=str))
                raise GraphValidationError(f"relation {side} requires {names} endpoint")
            if (
                resolved.kind is EndpointKind.REFINED_GAP
                and self.canonical_endpoint(pointer) != pointer
            ):
                raise GraphValidationError("noncanonical placement")
            if tiers is not None and resolved.tier not in tiers:
                raise GraphValidationError(f"invalid {side} tier")

    def _validate_choices(self) -> None:
        by_source: dict[tuple[str, str], list[Relation]] = {}
        for relation in self.relations:
            declaration = self.declarations.relation(relation.name)
            assert declaration is not None
            if declaration.choice or declaration.member_of is not None:
                for source in relation.sources:
                    by_source.setdefault((source, relation.name), []).append(relation)
            if declaration.choice and len(relation.targets) != len(
                set(relation.targets)
            ):
                raise GraphValidationError("choice candidates must be distinct")
        for (source, name), links in by_source.items():
            declaration = self.declarations.relation(name)
            assert declaration is not None
            if len(links) > 1:
                label = "alternatives" if declaration.choice else name
                raise GraphValidationError(
                    f"choice event owns at most one {label} relation"
                )
            if declaration.member_of is not None:
                candidates = by_source.get((source, declaration.member_of), [])
                if not candidates:
                    raise GraphValidationError(
                        "selection source owns no alternatives relation"
                    )
                if any(
                    target not in candidates[0].targets for target in links[0].targets
                ):
                    raise GraphValidationError(
                        "selection is not a member of alternatives"
                    )

    def _validate_acyclic(self, name: str) -> None:
        edges: dict[str, set[str]] = {}
        for relation in self.relations:
            if relation.name == name:
                for source in relation.sources:
                    edges.setdefault(source, set()).update(relation.targets)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise GraphValidationError("cycle in acyclic relation")
            if node in visited:
                return
            visiting.add(node)
            for target in edges.get(node, ()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in edges:
            visit(node)

    def to_data(self) -> dict[str, JsonValue]:
        return {
            "tiers": [tier.name for tier in self.declarations.tiers],
            "features": [feature.name for feature in self.declarations.features],
            "clock": [_node_data(node) for node in self.clock],
            "roots": list(self.roots),
            "links": [
                [list(link.sources), link.name, list(link.targets)]
                for link in self.relations
            ],
        }

    @classmethod
    def from_data(
        cls, declarations: Declarations, data: Mapping[str, JsonValue]
    ) -> Graph:
        """Restore kernel data while keeping model declarations out of its wire shape."""
        if data.get("tiers") != [tier.name for tier in declarations.tiers]:
            raise GraphValidationError("tier declarations do not match graph data")
        if data.get("features") != [feature.name for feature in declarations.features]:
            raise GraphValidationError("feature declarations do not match graph data")
        raw_clock = data.get("clock")
        raw_roots = data.get("roots")
        raw_links = data.get("links")
        if (
            not isinstance(raw_clock, list)
            or not isinstance(raw_roots, list)
            or not isinstance(raw_links, list)
        ):
            raise GraphValidationError("malformed graph data")
        clock: list[ClockNode] = []
        tier_names = {tier.name for tier in declarations.tiers}
        for raw_node in raw_clock:
            if not isinstance(raw_node, dict):
                raise GraphValidationError("malformed clock node")
            raw_gaps = raw_node.get("gaps")
            if not isinstance(raw_gaps, list):
                raise GraphValidationError("malformed clock node")
            groups: list[EventGroup] = []
            for tier in declarations.tiers:
                raw_events = raw_node.get(tier.name)
                if raw_events is None:
                    continue
                if not isinstance(raw_events, list):
                    raise GraphValidationError("malformed event group")
                groups.append(
                    EventGroup(
                        tier.name, tuple(_event_from_data(item) for item in raw_events)
                    )
                )
            if set(raw_node) - tier_names - _NODE_STRUCTURAL_KEYS:
                raise GraphValidationError("undeclared tier")
            clock.append(ClockNode(len(raw_gaps), tuple(groups)))
        roots = tuple(_require_string(item) for item in raw_roots)
        relations = tuple(_relation_from_data(raw) for raw in raw_links)
        return cls(declarations, tuple(clock), relations, roots)


def _node_data(node: ClockNode) -> JsonValue:
    result: dict[str, JsonValue] = {"gaps": [{} for _ in range(node.gap_count)]}
    for group in node.groups:
        values: list[JsonValue] = []
        for event in group.events:
            value: dict[str, JsonValue] = {
                "features": {
                    name: _thaw(value) for name, value in sorted(event.features.items())
                }
            }
            if event.span is not None:
                value["span"] = {"start": event.span.start, "end": event.span.end}
            elif event.structural_duration != 1:
                value["duration"] = event.structural_duration
            if event.timing is not None:
                value["timing"] = {
                    "start": event.timing.start,
                    "duration": event.timing.duration,
                }
            values.append(value)
        result[group.tier] = values
    return result


def _event_from_data(raw: JsonValue) -> Event:
    if not isinstance(raw, dict):
        raise GraphValidationError("malformed event")
    raw_features = raw.get("features")
    if not isinstance(raw_features, dict):
        raise GraphValidationError("malformed event")
    features = dict(raw_features)
    duration = raw.get("duration")
    if duration is not None and (
        not isinstance(duration, int) or isinstance(duration, bool)
    ):
        raise GraphValidationError("malformed structural duration")
    raw_span = raw.get("span")
    span = None
    if raw_span is not None:
        if not isinstance(raw_span, dict):
            raise GraphValidationError("malformed refined span")
        span = RefinedSpan(
            _require_string(raw_span.get("start")),
            _require_string(raw_span.get("end")),
        )
    raw_timing = raw.get("timing")
    timing = None
    if raw_timing is not None:
        if not isinstance(raw_timing, dict):
            raise GraphValidationError("malformed physical timing")
        start = raw_timing.get("start")
        physical_duration = raw_timing.get("duration")
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(physical_duration, (int, float))
            or isinstance(physical_duration, bool)
        ):
            raise GraphValidationError("malformed physical timing")
        timing = Timing(float(start), float(physical_duration))
    allowed = {"features", "duration", "span", "timing"}
    if set(raw) - allowed:
        raise GraphValidationError("malformed event")
    return Event(cast(Mapping[str, FrozenValue], features), duration, span, timing)


def _relation_from_data(raw: JsonValue) -> Relation:
    if not isinstance(raw, list) or len(raw) != 3:
        raise GraphValidationError("malformed relation")
    raw_sources, raw_name, raw_targets = raw
    if not isinstance(raw_sources, list) or not isinstance(raw_targets, list):
        raise GraphValidationError("malformed relation")
    return Relation(
        tuple(_require_string(item) for item in raw_sources),
        _require_string(raw_name),
        tuple(_require_string(item) for item in raw_targets),
    )


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        raise GraphValidationError("malformed graph data")
    return value


def _validate_name(name: str, kind: str) -> None:
    if not name:
        raise GraphValidationError(f"{kind} name must not be empty")


def _validate_arity(arity: tuple[int, int | None], side: str) -> None:
    low, high = arity
    if low < 0 or (high is not None and high < low):
        raise GraphValidationError(f"invalid {side} arity")


def _unique(names: Iterable[str], kind: str) -> None:
    values = list(names)
    if len(values) != len(set(values)):
        raise GraphValidationError(f"duplicate {kind}")


def _check_side(
    values: tuple[str, ...], arity: tuple[int, int | None], allow_empty: bool, side: str
) -> None:
    if not values:
        if allow_empty:
            return
        raise GraphValidationError(f"empty relation {side}")
    low, high = arity
    if len(values) < low or (high is not None and len(values) > high):
        raise GraphValidationError(f"relation {side} arity violation")


def _pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/") or pointer == "/":
        raise GraphValidationError("malformed JSON Pointer reference")
    raw = pointer[1:].split("/")
    for part in raw:
        index = 0
        while index < len(part):
            if part[index] == "~" and (
                index + 1 == len(part) or part[index + 1] not in "01"
            ):
                raise GraphValidationError("malformed JSON Pointer reference")
            index += 2 if part[index] == "~" else 1
    return [part.replace("~1", "/").replace("~0", "~") for part in raw]


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _freeze(value: object) -> FrozenValue:
    """Freeze JSON containers while preserving profile-owned scalar values.

    Profiles may store immutable domain objects such as ``Segment``.  Their
    value codecs remain authoritative about whether those opaque values have a
    valid wire representation.
    """
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return MappingProxyType({name: _freeze(item) for name, item in value.items()})
    return value


def _thaw(value: FrozenValue) -> JsonValue:
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Mapping):
        return {name: _thaw(value[name]) for name in sorted(value)}
    return cast(JsonValue, value)
