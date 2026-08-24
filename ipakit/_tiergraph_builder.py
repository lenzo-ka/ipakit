"""Canonical construction and address math for the private tier-graph kernel.

Handles keep construction independent of the array indices that canonical
serialization eventually assigns.  Input provenance stays in this layer
because only input occurrences are allowed to refine the structural clock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._tiergraph import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FrozenValue,
    Graph,
    GraphValidationError,
    RefinedSpan,
    Relation,
    Timing,
    _escape,
)

if TYPE_CHECKING:
    from ._containment_projection import ContainmentProjectionInput


@dataclass(frozen=True)
class EventHandle:
    """Name an event without exposing its eventual array position."""

    _owner: object
    _serial: int


@dataclass(frozen=True)
class PositionHandle:
    """Name either a coarse tick or a particular input-owned gap."""

    tick: int
    gap: int | None = None


type Endpoint = EventHandle | PositionHandle


@dataclass(frozen=True)
class EventSpec:
    """Describe one member of an ordered derived sequence compactly."""

    features: Mapping[str, FrozenValue]
    duration: int = 0
    timing: Timing | None = None


@dataclass
class _PendingEvent:
    handle: EventHandle
    tier: str
    start: PositionHandle
    duration: int | None
    end: PositionHandle | None
    features: Mapping[str, FrozenValue]
    timing: Timing | None
    lane: tuple[int, ...]
    durable_id: str
    open: bool = False


@dataclass(frozen=True)
class _PendingRelation:
    sources: tuple[Endpoint, ...]
    name: str
    targets: tuple[Endpoint, ...]


@dataclass(frozen=True)
class LegacyOccurrence:
    """Record whether a legacy unit advances or refines the input clock."""

    consumes_span: bool
    refines_tick: bool = False

    def __post_init__(self) -> None:
        if self.consumes_span and self.refines_tick:
            raise ValueError("an occurrence cannot both consume and refine a tick")
        if not self.consumes_span and not self.refines_tick:
            raise ValueError("a compatibility unit must consume or refine the clock")


class LegacyCoordinates:
    """Provide lossless position math without importing the future Form adapter."""

    def __init__(self, occurrences: Sequence[LegacyOccurrence]) -> None:
        refiners: dict[int, int] = {}
        tick = 0
        for occurrence in occurrences:
            if occurrence.consumes_span:
                tick += 1
            else:
                refiners[tick] = refiners.get(tick, 0) + 1

        positions: list[PositionHandle] = []
        tick = 0
        gap = 0
        positions.append(self._position(tick, gap, refiners))
        for occurrence in occurrences:
            if occurrence.consumes_span:
                tick += 1
                gap = 0
            else:
                gap += 1
            positions.append(self._position(tick, gap, refiners))
        self._positions = tuple(positions)
        self._indices = {position: index for index, position in enumerate(positions)}
        if len(self._indices) != len(self._positions):
            raise ValueError("legacy occurrences do not have unique graph positions")

    @staticmethod
    def _position(tick: int, gap: int, refiners: Mapping[int, int]) -> PositionHandle:
        return (
            PositionHandle(tick, gap) if refiners.get(tick, 0) else PositionHandle(tick)
        )

    def to_graph(self, legacy_gap_index: int) -> PositionHandle:
        """Map a legacy unit gap to its exact coarse or refined position."""
        if legacy_gap_index < 0:
            raise ValueError("legacy gap index is out of range")
        try:
            return self._positions[legacy_gap_index]
        except IndexError as error:
            raise ValueError("legacy gap index is out of range") from error

    def to_legacy(self, position: PositionHandle) -> int:
        """Recover the identical legacy gap index from a graph position."""
        try:
            return self._indices[position]
        except KeyError as error:
            raise ValueError("graph position is not a legacy unit gap") from error


class FactBuilder:
    """Accumulate canonical graph facts from stable intermediate handles."""

    def __init__(self, declarations: Declarations) -> None:
        self.declarations = declarations
        self._owner = object()
        self._events: list[_PendingEvent] = []
        self._relations: list[_PendingRelation] = []
        self._roots: list[EventHandle] = []
        self._refiners: dict[int, list[EventHandle]] = {}
        self._input_occurrences: list[LegacyOccurrence] = []
        self._input_tick = 0
        self._serial = 0
        self._durable_ids: set[str] = set()

    @property
    def current_tick(self) -> int:
        return self._input_tick

    def tick(self, tick: int | None = None) -> PositionHandle:
        """Create a coarse position handle without claiming an interior side."""
        return PositionHandle(self._input_tick if tick is None else tick)

    def gap(self, tick: int, gap: int) -> PositionHandle:
        """Create an input-owned refined position for later validation."""
        return PositionHandle(tick, gap)

    def append_input_atom(
        self,
        tier: str,
        features: Mapping[str, FrozenValue],
        *,
        timing: Timing | None = None,
    ) -> EventHandle:
        """Append the only kind of occurrence that advances the base clock."""
        handle = self.add_event(tier, self.tick(), features, duration=1, timing=timing)
        self._input_occurrences.append(LegacyOccurrence(consumes_span=True))
        self._input_tick += 1
        return handle

    def append_input_occurrence(
        self,
        tier: str,
        features: Mapping[str, FrozenValue],
        *,
        refines_tick: bool,
        timing: Timing | None = None,
    ) -> EventHandle:
        """Append a point occurrence and let declarations decide gap creation."""
        handle = self.add_event(tier, self.tick(), features, duration=0, timing=timing)
        if refines_tick:
            self._refiners.setdefault(self._input_tick, []).append(handle)
            self._input_occurrences.append(
                LegacyOccurrence(consumes_span=False, refines_tick=True)
            )
        return handle

    def add_event(
        self,
        tier: str,
        start: int | PositionHandle,
        features: Mapping[str, FrozenValue],
        *,
        duration: int = 1,
        end: PositionHandle | None = None,
        timing: Timing | None = None,
        durable_id: str | None = None,
    ) -> EventHandle:
        """Record lane order before containment or pointer paths can exist."""
        if self.declarations.tier(tier) is None:
            raise GraphValidationError("undeclared tier")
        position = PositionHandle(start) if isinstance(start, int) else start
        if position.tick < 0:
            raise ValueError("tick must be nonnegative")
        if end is not None and duration != 1:
            raise ValueError("a refined span cannot also specify duration")
        handle = self._new_handle()
        if durable_id is None:
            candidate = f"ipakit-event-{self._serial - 1}"
            while candidate in self._durable_ids:
                candidate = f"ipakit-event-{self._serial}"
                self._serial += 1
            durable_id = candidate
        if durable_id in self._durable_ids:
            raise GraphValidationError("duplicate durable event id")
        self._durable_ids.add(durable_id)
        self._events.append(
            _PendingEvent(
                handle,
                tier,
                position,
                None if end is not None else duration,
                end,
                dict(features),
                timing,
                (0, self._serial),
                durable_id,
            )
        )
        return handle

    def add_span(
        self,
        tier: str,
        start: PositionHandle,
        end: PositionHandle,
        features: Mapping[str, FrozenValue],
        *,
        timing: Timing | None = None,
        durable_id: str | None = None,
    ) -> EventHandle:
        """Construct a half-open span whose endpoints may name refined gaps."""
        return self.add_event(
            tier,
            start,
            features,
            end=end,
            timing=timing,
            durable_id=durable_id,
        )

    def begin(
        self,
        tier: str,
        features: Mapping[str, FrozenValue],
        *,
        start: int | PositionHandle | None = None,
        timing: Timing | None = None,
    ) -> EventHandle:
        """Hold structural extent open while nested input is appended."""
        position = self.tick() if start is None else start
        handle = self.add_event(tier, position, features, duration=0, timing=timing)
        pending = self._pending(handle)
        pending.duration = None
        pending.open = True
        return handle

    def end(self, handle: EventHandle, end: int | PositionHandle | None = None) -> None:
        """Close an open event and derive coarse duration or a refined span."""
        pending = self._pending(handle)
        if not pending.open:
            raise ValueError("event is not open")
        position = self.tick() if end is None else end
        endpoint = PositionHandle(position) if isinstance(position, int) else position
        if pending.start.gap is None and endpoint.gap is None:
            pending.duration = endpoint.tick - pending.start.tick
        else:
            pending.end = endpoint
        pending.open = False

    def attach_timing(self, handle: EventHandle, start: float, duration: float) -> None:
        """Decorate structure without conflating seconds with clock extent."""
        self._pending(handle).timing = Timing(start, duration)

    def relate(
        self, sources: Iterable[Endpoint], name: str, targets: Iterable[Endpoint]
    ) -> None:
        """Retain caller-provided sequence order until handles resolve."""
        self._relations.append(_PendingRelation(tuple(sources), name, tuple(targets)))

    def contain(
        self,
        parent: EventHandle,
        children: Iterable[EventHandle],
        *,
        relation: str = "contains",
    ) -> None:
        """Express membership without letting it influence lane order."""
        self.relate((parent,), relation, children)

    def add_root(self, handle: EventHandle) -> None:
        """Retain root identity across later lane insertions."""
        self._require_handle(handle)
        self._roots.append(handle)

    def add_ordered_sequence(
        self,
        tier: str,
        anchor: int | PositionHandle,
        specs: Sequence[EventSpec],
        *,
        derivation_step: int,
        source_site_order: int,
        application_order: int,
    ) -> tuple[EventHandle, ...]:
        """Interleave rewrite targets by the rule engine's pinned coordinates."""
        handles: list[EventHandle] = []
        for target_index, spec in enumerate(specs):
            handle = self.add_event(
                tier,
                anchor,
                spec.features,
                duration=spec.duration,
                timing=spec.timing,
            )
            self._pending(handle).lane = (
                1,
                derivation_step,
                source_site_order,
                application_order,
                target_index,
            )
            handles.append(handle)
        return tuple(handles)

    def scan_order(self, tier: str | None = None) -> tuple[EventHandle, ...]:
        """Expose the same total event order that build projects to arrays."""
        tier_order = self.declarations._tier_order
        events = (item for item in self._events if tier is None or item.tier == tier)
        return tuple(
            item.handle
            for item in sorted(
                events,
                key=lambda item: (item.start.tick, tier_order[item.tier], item.lane),
            )
        )

    def compatibility_coordinates(self) -> LegacyCoordinates:
        """Expose only the lossless input units recorded by this builder."""
        return LegacyCoordinates(self._input_occurrences)

    def _build_facts(
        self,
    ) -> tuple[tuple[ClockNode, ...], tuple[Relation, ...], tuple[str, ...]]:
        """Resolve handles only after canonical event ordering is final."""
        unfinished = [item for item in self._events if item.open]
        if unfinished:
            raise GraphValidationError("unfinished open event")
        final_tick = self._input_tick
        if any(item.start.tick > final_tick for item in self._events):
            raise GraphValidationError("event starts past final tick")
        gap_counts = {
            tick: len(handles) + 1 for tick, handles in self._refiners.items()
        }
        tier_order = self.declarations._tier_order
        ordered = sorted(
            self._events,
            key=lambda item: (item.start.tick, tier_order[item.tier], item.lane),
        )
        paths: dict[EventHandle, str] = {}
        grouped: dict[tuple[int, str], list[_PendingEvent]] = {}
        for item in ordered:
            values = grouped.setdefault((item.start.tick, item.tier), [])
            paths[item.handle] = (
                f"/clock/{item.start.tick}/{_escape(item.tier)}/{len(values)}"
            )
            values.append(item)

        nodes: list[ClockNode] = []
        for tick in range(final_tick + 1):
            groups: list[EventGroup] = []
            for tier in self.declarations.tiers:
                pending = grouped.get((tick, tier.name))
                if pending:
                    groups.append(
                        EventGroup(
                            tier.name,
                            tuple(
                                self._materialize(item, gap_counts) for item in pending
                            ),
                        )
                    )
            nodes.append(ClockNode(gap_counts.get(tick, 1), tuple(groups)))
        relations = tuple(
            sorted(
                (
                    Relation(
                        tuple(
                            self._resolve(item, paths, gap_counts)
                            for item in relation.sources
                        ),
                        relation.name,
                        tuple(
                            self._resolve(item, paths, gap_counts)
                            for item in relation.targets
                        ),
                    )
                    for relation in self._relations
                ),
                key=lambda relation: (
                    relation.sources,
                    relation.name,
                    relation.targets,
                ),
            )
        )
        roots = tuple(paths[self._validated_handle(item)] for item in self._roots)
        return tuple(nodes), relations, roots

    def build_input(self) -> object:
        """Build scaffold-free facts for the authoritative tiergraph projection."""
        from ._containment_projection import ContainmentProjectionInput

        clock, relations, roots = self._build_facts()
        return ContainmentProjectionInput.from_facts(
            self.declarations, clock, relations, roots
        )

    def _materialize(self, item: _PendingEvent, gap_counts: Mapping[int, int]) -> Event:
        span = None
        if item.end is not None:
            span = RefinedSpan(
                self._resolve_position(item.start, gap_counts, span_endpoint=True),
                self._resolve_position(item.end, gap_counts, span_endpoint=True),
            )
        return Event(
            item.features, item.duration, span, item.timing, durable_id=item.durable_id
        )

    def _resolve(
        self,
        endpoint: Endpoint,
        paths: Mapping[EventHandle, str],
        gap_counts: Mapping[int, int],
    ) -> str:
        if isinstance(endpoint, EventHandle):
            self._require_handle(endpoint)
            return paths[endpoint]
        return self._resolve_position(endpoint, gap_counts)

    def _resolve_position(
        self,
        position: PositionHandle,
        gap_counts: Mapping[int, int],
        *,
        span_endpoint: bool = False,
    ) -> str:
        if position.tick < 0 or position.tick > self._input_tick:
            raise GraphValidationError("position is outside the structural clock")
        count = gap_counts.get(position.tick, 1)
        if position.gap is None:
            if span_endpoint and count > 1:
                raise GraphValidationError("refined span endpoint must name a gap")
            return f"/clock/{position.tick}"
        if position.gap < 0 or position.gap >= count:
            raise GraphValidationError("gap does not belong to named tick")
        if count == 1:
            return f"/clock/{position.tick}"
        return f"/clock/{position.tick}/gaps/{position.gap}"

    def _new_handle(self) -> EventHandle:
        handle = EventHandle(self._owner, self._serial)
        self._serial += 1
        return handle

    def _pending(self, handle: EventHandle) -> _PendingEvent:
        self._require_handle(handle)
        return next(item for item in self._events if item.handle == handle)

    def _validated_handle(self, handle: EventHandle) -> EventHandle:
        self._require_handle(handle)
        return handle

    def _require_handle(self, handle: EventHandle) -> None:
        if handle._owner is not self._owner:
            raise ValueError("handle belongs to a different builder")


class GraphBuilder(FactBuilder):
    """Build the retained embedded graph for legacy, not-yet-migrated callers."""

    def build(self) -> Graph:
        """Materialize the embedded graph from the canonical accumulated facts."""
        clock, relations, roots = self._build_facts()
        return Graph(self.declarations, clock, relations, roots)


def copy_fact_builder(
    source: ContainmentProjectionInput, declarations: Declarations | None = None
) -> tuple[FactBuilder, dict[str, EventHandle]]:
    """Copy scaffold-free Form facts into a native-input builder."""
    builder = FactBuilder(declarations or source.declarations)
    builder._input_tick = len(source.clock) - 1
    builder._refiners = {
        tick: [
            EventHandle(builder._owner, -index - 1)
            for index in range(node.gap_count - 1)
        ]
        for tick, node in enumerate(source.clock)
        if node.gap_count > 1
    }
    handles: dict[str, EventHandle] = {}
    for reference in source.refs:
        event = source.events[reference]
        tier = source.event_tiers[reference]
        tick = int(reference.split("/")[2])
        if event.span is None:
            handle = builder.add_event(
                tier,
                tick,
                event.features,
                duration=event.structural_duration or 0,
                timing=event.timing,
                durable_id=event.durable_id,
            )
        else:
            handle = builder.add_span(
                tier,
                _pointer_position(event.span.start),
                _pointer_position(event.span.end),
                event.features,
                timing=event.timing,
                durable_id=event.durable_id,
            )
        handles[reference] = handle
    for relation in source.relations:
        builder.relate(
            (_copied_endpoint(reference, handles) for reference in relation.sources),
            relation.name,
            (_copied_endpoint(reference, handles) for reference in relation.targets),
        )
    for root in source.roots:
        builder.add_root(handles[root])
    return builder, handles


def add_event_copy(
    graph: Graph,
    tier: str,
    tick: int,
    features: Mapping[str, FrozenValue],
    *,
    duration: int = 1,
    timing: Timing | None = None,
) -> Graph:
    """Add an event while regenerating every reference from stable handles."""
    builder, _ = _copy_builder(graph)
    builder.add_event(tier, tick, features, duration=duration, timing=timing)
    return builder.build()


def remove_events_copy(graph: Graph, references: Iterable[str]) -> Graph:
    """Remove events and dependent links while reindexing surviving references."""
    removed = set(references)
    for reference in removed:
        resolved = graph.resolve(reference)
        if resolved.event is not None and resolved.event.structural_duration == 1:
            raise GraphValidationError(
                f"cannot remove clock-consuming input atom {reference}: "
                "the structural clock is immutable and input-owned"
            )
    builder, _ = _copy_builder(graph, removed)
    return builder.build()


def add_relation_copy(
    graph: Graph, sources: Sequence[str], name: str, targets: Sequence[str]
) -> Graph:
    """Add a relation after translating old pointers to stable copied handles."""
    builder, handles = _copy_builder(graph)
    builder.relate(
        (_copied_endpoint(item, handles) for item in sources),
        name,
        (_copied_endpoint(item, handles) for item in targets),
    )
    return builder.build()


def remove_relations_copy(graph: Graph, relations: Iterable[Relation]) -> Graph:
    """Remove selected immutable relations without retaining stale pointers."""
    removed = set(relations)
    builder, _ = _copy_builder(graph, excluded_relations=removed)
    return builder.build()


def _copy_builder(
    graph: Graph,
    excluded_events: set[str] | None = None,
    excluded_relations: set[Relation] | None = None,
) -> tuple[GraphBuilder, dict[str, EventHandle]]:
    excluded_events = excluded_events or set()
    excluded_relations = excluded_relations or set()
    builder = GraphBuilder(graph.declarations)
    builder._input_tick = len(graph.clock) - 1
    builder._refiners = {
        tick: [] for tick, node in enumerate(graph.clock) if node.gap_count > 1
    }
    # Placeholder handles retain input-owned cardinality when provenance is absent.
    for tick, node in enumerate(graph.clock):
        if node.gap_count > 1:
            builder._refiners[tick] = [
                EventHandle(builder._owner, -index - 1)
                for index in range(node.gap_count - 1)
            ]
    handles: dict[str, EventHandle] = {}
    for tick, node in enumerate(graph.clock):
        for group in node.groups:
            for index, event in enumerate(group.events):
                reference = f"/clock/{tick}/{_escape(group.tier)}/{index}"
                if reference in excluded_events:
                    continue
                if event.span is None:
                    handle = builder.add_event(
                        group.tier,
                        tick,
                        event.features,
                        duration=event.structural_duration or 0,
                        timing=event.timing,
                        durable_id=event.durable_id,
                    )
                else:
                    handle = builder.add_span(
                        group.tier,
                        _pointer_position(event.span.start),
                        _pointer_position(event.span.end),
                        event.features,
                        timing=event.timing,
                        durable_id=event.durable_id,
                    )
                handles[reference] = handle
    for relation in graph.relations:
        if relation in excluded_relations:
            continue
        if any(
            reference in excluded_events
            for reference in (*relation.sources, *relation.targets)
        ):
            continue
        builder.relate(
            (_copied_endpoint(reference, handles) for reference in relation.sources),
            relation.name,
            (_copied_endpoint(reference, handles) for reference in relation.targets),
        )
    for root in graph.roots:
        if root not in excluded_events:
            builder.add_root(handles[root])
    return builder, handles


def _copied_endpoint(pointer: str, handles: Mapping[str, EventHandle]) -> Endpoint:
    if pointer in handles:
        return handles[pointer]
    return _pointer_position(pointer)


def _pointer_position(pointer: str) -> PositionHandle:
    parts = pointer.split("/")
    if len(parts) == 3 and parts[1] == "clock":
        return PositionHandle(int(parts[2]))
    if len(parts) == 5 and parts[1] == "clock" and parts[3] == "gaps":
        return PositionHandle(int(parts[2]), int(parts[4]))
    raise ValueError("pointer does not name a clock position")
