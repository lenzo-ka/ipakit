"""Assemble ipakit's containment view natively as a tiergraph graph.

Canonical facts supply event identity, containment incidence, profile values,
clock coordinates, timing, roots, choices, and the other graph concerns used to
construct the authoritative tiergraph graph.

``ContainmentProjection.from_input`` is memoized in a bounded, thread-safe LRU
keyed by content signature, so equal inputs reuse a single built projection.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import tiergraph as tg

from ._graph_facts import (
    ClockNode,
    Declarations,
    EndpointKind,
    Event,
    GraphValidationError,
    Relation,
    ResolvedReference,
    _escape,
    _pointer_parts,
)

_NAMESPACE = "https://ipakit.dev/tiergraph/containment-projection/v1"
_PREFIX = "ipakit-containment"
_EVENT_TYPE = tg.QualifiedName(_NAMESPACE, "event")
# Bounded LRU of built projections, keyed by content signature. The bound is
# sized to a realistic working set: the IPA inventory is ~210 declared
# symbols / ~140 single-unit phones, so 1024 entries hold every distinct
# single phone many times over alongside the few hundred distinct multi-unit
# forms a read loop revisits, while capping retained built graphs (and their
# memory) at 1024. A workload whose distinct-form count exceeds this evicts
# LRU-first rather than growing without bound.
_PROJECTION_CACHE_MAXSIZE = 1024
# Guards the whole read-modify-write of the OrderedDict, its LRU touch and
# eviction, and the non-atomic counters below. The expensive graph build in
# from_input runs OUTSIDE this lock.
_projection_cache_lock = threading.Lock()
_projection_cache: OrderedDict[tuple[object, ...], ContainmentProjection] = (
    OrderedDict()
)
_projection_cache_hits = 0
_projection_cache_misses = 0
_projection_cache_evictions = 0

_PAYLOAD_DECLARATIONS = (
    ("text", tg.XsdType.STRING),
    ("spelling", tg.XsdType.STRING),
    ("prominence", tg.XsdType.STRING),
    ("atom", tg.XsdType.STRING),
    ("output", tg.XsdType.STRING),
    ("exemplar", tg.XsdType.STRING),
    ("notes", tg.XsdType.STRING),
    ("input", tg.XsdType.BOOLEAN),
    ("compatibility-index", tg.XsdType.INTEGER),
    ("compatibility-interval", tg.XsdType.INTEGER),
    ("timing-start", tg.XsdType.DOUBLE),
    ("timing-duration", tg.XsdType.DOUBLE),
    ("span-start", tg.XsdType.STRING),
    ("span-end", tg.XsdType.STRING),
    ("structural-duration", tg.XsdType.INTEGER),
    ("segment-json", tg.XsdType.STRING),
    ("symbol", tg.XsdType.STRING),
    ("features-json", tg.XsdType.STRING),
    ("prosody-json", tg.XsdType.STRING),
    ("provenance-json", tg.XsdType.STRING),
    ("kind", tg.XsdType.STRING),
    ("arc", tg.XsdType.DOUBLE),
    ("offset", tg.XsdType.DOUBLE),
    ("articulator", tg.XsdType.STRING),
    ("source-value", tg.XsdType.STRING),
    ("target-index", tg.XsdType.INTEGER),
)


def _name(local_name: str) -> tg.QualifiedName:
    return tg.QualifiedName(_NAMESPACE, local_name)


def _json(value: object) -> str:
    """Encode an ordered primitive payload without reordering mappings."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _event_payload(event: Event) -> tuple[tuple[str, tg.XsdType, str], ...]:
    """Lower one compatibility event to scalar tiergraph item attributes."""
    unit = event.features.get("compatibility-unit")
    interval = event.features.get("compatibility-interval")
    if unit is not None:
        from .form import Unit, _DerivedMapping, _DerivedProvenance

        if not isinstance(unit, Unit):
            raise TypeError("compatibility-unit must be a Unit")
        values: list[tuple[str, tg.XsdType, str]] = [
            ("text", tg.XsdType.STRING, unit.text),
        ]
        if unit.spelling is not None:
            values.append(("spelling", tg.XsdType.STRING, unit.spelling))
        values.extend(
            (
                (
                    "input",
                    tg.XsdType.BOOLEAN,
                    "true" if event.features["input"] is True else "false",
                ),
                (
                    "compatibility-index",
                    tg.XsdType.INTEGER,
                    str(event.features["compatibility-index"]),
                ),
            )
        )
        if unit.segment is not None:
            values.append(
                (
                    "segment-json",
                    tg.XsdType.STRING,
                    _json(
                        {
                            "constituents": [
                                {
                                    "base": constituent.base,
                                    "modifiers": list(constituent.modifiers),
                                    "approach": list(constituent.approach),
                                }
                                for constituent in unit.segment.constituents
                            ],
                            "junctures": list(unit.segment.junctures),
                            "prosody": list(unit.segment.prosody),
                        }
                    ),
                )
            )
            namespace = unit.__dict__
            if not namespace.get("_views_pending") and not (
                isinstance(namespace["features"], _DerivedMapping)
                and isinstance(namespace["prosody"], _DerivedMapping)
                and isinstance(namespace["provenance"], _DerivedProvenance)
            ):
                values.extend(
                    (
                        (
                            "features-json",
                            tg.XsdType.STRING,
                            _json(dict(unit.features)),
                        ),
                        (
                            "prosody-json",
                            tg.XsdType.STRING,
                            _json(dict(unit.prosody)),
                        ),
                        (
                            "provenance-json",
                            tg.XsdType.STRING,
                            _json(unit.provenance),
                        ),
                    )
                )
        else:
            values.extend(
                (
                    ("symbol", tg.XsdType.STRING, unit.text),
                    ("features-json", tg.XsdType.STRING, _json(dict(unit.features))),
                    ("prosody-json", tg.XsdType.STRING, _json(dict(unit.prosody))),
                    (
                        "provenance-json",
                        tg.XsdType.STRING,
                        _json(unit.provenance),
                    ),
                )
            )
    elif isinstance(interval, int):
        values = [
            ("compatibility-interval", tg.XsdType.INTEGER, str(interval)),
        ]
    else:
        values = []
        for name in ("spelling", "prominence", "atom", "output", "exemplar", "notes"):
            value = event.features.get(name)
            if isinstance(value, str):
                values.append((name, tg.XsdType.STRING, value))
        for name in ("kind", "articulator", "source-value"):
            value = event.features.get(name)
            if isinstance(value, str):
                values.append((name, tg.XsdType.STRING, value))
        for name in ("arc", "offset"):
            value = event.features.get(name)
            if isinstance(value, (int, float)):
                values.append((name, tg.XsdType.DOUBLE, str(value)))
        target_index = event.features.get("target-index")
        if isinstance(target_index, int):
            values.append(("target-index", tg.XsdType.INTEGER, str(target_index)))
    if event.timing is not None:
        values.extend(
            (
                ("timing-start", tg.XsdType.DOUBLE, str(event.timing.start)),
                ("timing-duration", tg.XsdType.DOUBLE, str(event.timing.duration)),
            )
        )
    if event.span is not None:
        values.extend(
            (
                ("span-start", tg.XsdType.STRING, event.span.start),
                ("span-end", tg.XsdType.STRING, event.span.end),
            )
        )
    else:
        duration = event.structural_duration
        assert duration is not None
        values.append(("structural-duration", tg.XsdType.INTEGER, str(duration)))
    return tuple(values)


def _unit_from_attributes(attributes: dict[str, str], inventory: Any) -> Any:
    """Raise one compatibility Unit from its lowered attribute payload."""
    from .form import Timing, Unit
    from .segment import Constituent, Segment, Sense

    timing = (
        Timing(
            float(attributes["timing-start"]),
            float(attributes["timing-duration"]),
        )
        if "timing-start" in attributes
        else None
    )
    if "segment-json" in attributes:
        encoded = json.loads(attributes["segment-json"])
        segment = Segment(
            tuple(
                Constituent(
                    part["base"],
                    tuple(part["modifiers"]),
                    tuple(part["approach"]),
                )
                for part in encoded["constituents"]
            ),
            tuple(Sense(value) for value in encoded["junctures"]),
            tuple(encoded["prosody"]),
            _features=inventory,
        )
        views = (
            {
                "features": json.loads(attributes["features-json"]),
                "prosody": json.loads(attributes["prosody-json"]),
                "provenance": tuple(
                    tuple(value) for value in json.loads(attributes["provenance-json"])
                ),
            }
            if "features-json" in attributes
            else {}
        )
        return Unit(
            attributes["text"],
            segment,
            timing=timing,
            spelling=attributes.get("spelling"),
            _inventory=inventory,
            **views,
        )
    return Unit(
        attributes["symbol"],
        features=json.loads(attributes["features-json"]),
        prosody=json.loads(attributes["prosody-json"]),
        provenance=tuple(
            tuple(value) for value in json.loads(attributes["provenance-json"])
        ),
        timing=timing,
        spelling=attributes.get("spelling"),
    )


@dataclass(frozen=True)
class ContainmentProjectionInput:
    """Scaffold-free facts needed to build the authoritative projection."""

    refs: tuple[str, ...]
    declarations: Declarations
    relations: tuple[Relation, ...]
    event_tiers: dict[str, str]
    events: dict[str, Event]
    endpoint_kinds: dict[str, EndpointKind]
    clock: tuple[ClockNode, ...]
    roots: tuple[str, ...]

    @classmethod
    def from_facts(
        cls,
        declarations: Declarations,
        clock: Iterable[ClockNode],
        relations: Iterable[Relation] = (),
        roots: Iterable[str] = (),
    ) -> ContainmentProjectionInput:
        """Collect projection facts without constructing an embedded graph."""
        held_clock = tuple(clock)
        held_relations = tuple(relations)
        held_roots = tuple(roots)
        refs = tuple(
            f"/clock/{tick}/{_escape(group.tier)}/{index}"
            for tick, node in enumerate(held_clock)
            for group in node.groups
            for index in range(len(group.events))
        )
        event_tiers = {
            f"/clock/{tick}/{_escape(group.tier)}/{index}": group.tier
            for tick, node in enumerate(held_clock)
            for group in node.groups
            for index in range(len(group.events))
        }
        events = {
            f"/clock/{tick}/{_escape(group.tier)}/{index}": event
            for tick, node in enumerate(held_clock)
            for group in node.groups
            for index, event in enumerate(group.events)
        }
        endpoints = {
            ref
            for relation in held_relations
            for ref in (*relation.sources, *relation.targets)
        }
        collected = cls(
            refs,
            declarations,
            held_relations,
            event_tiers,
            events,
            {},
            held_clock,
            held_roots,
        )
        endpoint_kinds = {ref: collected.resolve(ref).kind for ref in endpoints}
        return cls(
            refs,
            declarations,
            held_relations,
            event_tiers,
            events,
            endpoint_kinds,
            held_clock,
            held_roots,
        )

    def resolve(self, pointer: str) -> ResolvedReference:
        """Resolve against captured immutable presentation facts."""
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
            group = next(
                (candidate for candidate in node.groups if candidate.tier == tier),
                None,
            )
            if group is None or index >= len(group.events):
                raise GraphValidationError("dangling JSON Pointer reference")
            return ResolvedReference(
                pointer,
                EndpointKind.EVENT,
                tick,
                tier=tier,
                event=group.events[index],
            )
        raise GraphValidationError("malformed JSON Pointer reference")


def _projection_signature(
    source: ContainmentProjectionInput,
    preserved_relation_names: frozenset[str],
) -> tuple[object, ...]:
    """Return the complete, inventory-independent input to graph lowering.

    Event domain objects are reduced through the same scalar payload codec as
    the builder. The remaining fields are immutable structural facts consumed
    directly by ``_build_from_input``.
    """
    return (
        source.refs,
        tuple(
            (ref, source.event_tiers[ref], _event_payload(source.events[ref]))
            for ref in source.refs
        ),
        tuple(sorted(source.event_tiers.items())),
        source.declarations,
        source.relations,
        tuple(sorted(source.endpoint_kinds.items())),
        tuple(node.gap_count for node in source.clock),
        source.roots,
        preserved_relation_names,
    )


def _projection_cache_clear() -> None:
    """Clear the bounded projection memo and its testable counters.

    Test helper: assumes no concurrent builds are in flight. A miss whose
    build is still running could reinsert its entry after this clear.
    """
    global _projection_cache_hits, _projection_cache_misses
    global _projection_cache_evictions
    with _projection_cache_lock:
        _projection_cache.clear()
        _projection_cache_hits = _projection_cache_misses = 0
        _projection_cache_evictions = 0


def _projection_cache_info() -> tuple[int, int, int, int, int]:
    """Return hits, misses, evictions, current size, and maximum size."""
    with _projection_cache_lock:
        return (
            _projection_cache_hits,
            _projection_cache_misses,
            _projection_cache_evictions,
            len(_projection_cache),
            _PROJECTION_CACHE_MAXSIZE,
        )


@dataclass(frozen=True)
class ContainmentProjection:
    """Single-source ordered containment view with lossless event identity.

    Navigation preserves the compatibility contract on every accepted graph.
    Accepted containment instances have exactly one event source and
    only event targets (including a declared empty target side).  Source
    cardinalities other than one and boundary endpoints are refused by name.
    """

    graph: tg.Graph
    old_to_new: Mapping[str, tg.ItemRef]
    new_to_old: Mapping[tg.ItemRef, str]
    tier_names: Mapping[str, tg.QualifiedName]
    containment_names: Mapping[str, tg.QualifiedName]
    relation_names: Mapping[str, tg.QualifiedName]
    roots_name: tg.QualifiedName
    parent_order: Mapping[tuple[str, str, str], int]
    traversal_order: tuple[str, ...]
    event_tiers: Mapping[str, str]
    admitted_sources: Mapping[str, frozenset[str] | None]
    admitted_targets: Mapping[str, frozenset[str] | None]
    active_by_parent: Mapping[str, tuple[str, ...]]

    @classmethod
    def from_input(
        cls,
        source: ContainmentProjectionInput,
        *,
        preserved_relation_names: frozenset[str] = frozenset(),
    ) -> ContainmentProjection:
        """Build the authoritative native graph from scaffold-free facts."""
        global _projection_cache_hits, _projection_cache_misses
        global _projection_cache_evictions

        key = _projection_signature(source, preserved_relation_names)
        with _projection_cache_lock:
            try:
                cached = _projection_cache.pop(key)
            except KeyError:
                _projection_cache_misses += 1
            else:
                _projection_cache_hits += 1
                _projection_cache[key] = cached  # LRU touch: newest at the end
                return cached

        # Build outside the lock: graph construction is expensive and does not
        # mutate the frozen input, so concurrent callers must not serialize on
        # it.
        result = cls._build_from_input(source, preserved_relation_names)

        with _projection_cache_lock:
            # Double-check: another caller may have built and inserted this key
            # while we were building. Prefer the stored entry so every reader of
            # one signature shares a single projection instance; discard ours.
            existing = _projection_cache.get(key)
            if existing is not None:
                _projection_cache.move_to_end(key)
                return existing
            _projection_cache[key] = result
            if len(_projection_cache) > _PROJECTION_CACHE_MAXSIZE:
                _projection_cache.popitem(last=False)
                _projection_cache_evictions += 1
            return result

    @classmethod
    def _build_from_input(
        cls,
        source: ContainmentProjectionInput,
        preserved_relation_names: frozenset[str],
    ) -> ContainmentProjection:
        """Build an uncached projection from content-complete facts."""
        from tiergraph.machine import (
            AddItem,
            AttachValue,
            DeclareAttribute,
            DeclareNamespace,
            DeclareRelation,
            DeclareTier,
            Opcode,
            Program,
            Relate,
        )

        refs = source.refs
        payloads = {ref: _event_payload(source.events[ref]) for ref in refs}
        tier_names = {
            declaration.name: _name(f"tier-{index}")
            for index, declaration in enumerate(source.declarations.tiers)
        }
        by_tier = {
            tier: tuple(ref for ref in refs if source.event_tiers[ref] == tier)
            for tier in tier_names
        }
        old_to_new = {
            ref: tg.ItemRef(tier_names[tier], index)
            for tier, tier_refs in by_tier.items()
            for index, ref in enumerate(tier_refs)
        }
        new_to_old = {value: key for key, value in old_to_new.items()}
        if len(old_to_new) != len(refs) or len(new_to_old) != len(refs):
            raise ValueError("containment projection did not preserve event identity")

        tiers = tuple(
            tg.Tier(
                tg.TierDeclaration(tier_names[tier], tier),
                tuple(
                    tg.Item(
                        durable_id=ref,
                        attributes=tuple(
                            tg.AttributeValue(_name(name), value_type, lexical)
                            for name, value_type, lexical in payloads[ref]
                        ),
                    )
                    for ref in by_tier[tier]
                ),
            )
            for tier in tier_names
        )
        memberships = tuple(
            tg.SimpleRelationDeclaration(
                _name(f"members-{index}"), tier_name, _EVENT_TYPE
            )
            for index, tier_name in enumerate(tier_names.values())
        )
        containment = tuple(
            declaration
            for declaration in source.declarations.relations
            if declaration.containment
        )
        containment_names_set = {declaration.name for declaration in containment}
        for index, relation in enumerate(source.relations):
            if relation.name in containment_names_set and len(relation.sources) != 1:
                raise ValueError(
                    "containment projection refuses multi-source containment "
                    f"instance {index} ({relation.name!r})"
                )
            if relation.name in containment_names_set and any(
                source.endpoint_kinds[endpoint] is not EndpointKind.EVENT
                for endpoint in (*relation.sources, *relation.targets)
            ):
                raise ValueError(
                    "containment projection refuses boundary-endpoint containment "
                    f"relation {relation.name!r}: tiergraph OrderedContainment "
                    "supports item endpoints only"
                )
        containment_names = {
            declaration.name: _name(f"contains-{index}")
            for index, declaration in enumerate(containment)
        }
        boundary_relation_names = {
            relation.name
            for relation in source.relations
            if any(
                source.endpoint_kinds[endpoint] is not EndpointKind.EVENT
                for endpoint in (*relation.sources, *relation.targets)
            )
        }
        relation_names = {
            declaration.name: (
                _name(declaration.name)
                if declaration.name in boundary_relation_names
                or declaration.name in preserved_relation_names
                or declaration.choice
                or declaration.member_of is not None
                else containment_names.get(declaration.name, _name(f"relation-{index}"))
            )
            for index, declaration in enumerate(source.declarations.relations)
        }
        roots_name = _name("roots")
        clock_name = _name("clock")
        tick_name = _name("tick")
        gap_name = _name("gap")
        clock_positions = tuple(
            (tick, encoded_gap)
            for tick, node in enumerate(source.clock)
            for encoded_gap in range(node.gap_count + 1)
        )
        clock_position_indices = {
            position: index for index, position in enumerate(clock_positions)
        }

        def durable_position(pointer: str) -> tg.DurablePositionRef:
            resolved = source.resolve(pointer)
            gap = 0
            if resolved.kind is EndpointKind.REFINED_GAP:
                assert resolved.gap is not None
                gap = resolved.gap
            boundary_index = clock_position_indices[(resolved.tick, gap)]
            cell_count = max(0, len(clock_positions) - 1)
            if boundary_index < cell_count:
                anchor: tg.DurableItemRef | tg.QualifiedName = tg.DurableItemRef(
                    f"ipakit-clockcell-{boundary_index}"
                )
                side = tg.BoundarySide.BEFORE
            elif cell_count:
                anchor = tg.DurableItemRef(f"ipakit-clockcell-{cell_count - 1}")
                side = tg.BoundarySide.AFTER
            else:
                anchor = clock_name
                side = tg.BoundarySide.BEFORE
            return tg.DurablePositionRef(anchor, side)

        root_tiers = _ordered_unique(source.event_tiers[root] for root in source.roots)

        def item_side(declaration: object, side: str) -> tg.RelationSideDeclaration:
            arity = getattr(declaration, f"{side}_arity")
            tiers = getattr(declaration, f"{side}_tiers")
            return tg.RelationSideDeclaration(
                (tg.RelationEndpointKind.ITEM,),
                None if tiers is None else tuple(tier_names[tier] for tier in tiers),
                minimum=arity[0],
                maximum=arity[1],
                allow_empty=getattr(declaration, f"allow_empty_{side}"),
            )

        def relation_side(declaration: object, side: str) -> tg.RelationSideDeclaration:
            """Lower compatibility endpoint kinds without perturbing item-only sides."""
            kinds = getattr(declaration, f"{side}_kinds")
            if kinds == frozenset({EndpointKind.EVENT}):
                return tg.RelationSideDeclaration(
                    (tg.RelationEndpointKind.ITEM,),
                    None,
                    minimum=getattr(declaration, f"{side}_arity")[0],
                    maximum=getattr(declaration, f"{side}_arity")[1],
                    allow_empty=getattr(declaration, f"allow_empty_{side}"),
                )
            endpoint_kinds = (
                *(
                    (tg.RelationEndpointKind.ITEM,)
                    if EndpointKind.EVENT in kinds
                    else ()
                ),
                *(
                    (tg.RelationEndpointKind.BOUNDARY,)
                    if kinds
                    & frozenset({EndpointKind.COARSE_TICK, EndpointKind.REFINED_GAP})
                    else ()
                ),
            )
            return tg.RelationSideDeclaration(
                endpoint_kinds,
                None,
                minimum=getattr(declaration, f"{side}_arity")[0],
                maximum=getattr(declaration, f"{side}_arity")[1],
                allow_empty=getattr(declaration, f"allow_empty_{side}"),
            )

        declarations: tuple[
            tg.SimpleRelationDeclaration | tg.PolyadicRelationDeclaration, ...
        ] = (
            *memberships,
            *(
                tg.PolyadicRelationDeclaration(
                    name,
                    item_side(declaration, "source"),
                    item_side(declaration, "target"),
                    unique_sources=True,
                    acyclic=True,
                )
                for declaration in containment
                for name in (containment_names[declaration.name],)
            ),
            *(
                tg.PolyadicRelationDeclaration(
                    relation_names[declaration.name],
                    relation_side(declaration, "source"),
                    relation_side(declaration, "target"),
                    unique_sources=(
                        declaration.choice or declaration.member_of is not None
                    ),
                    distinct_targets=declaration.choice,
                    acyclic=declaration.acyclic,
                    targets_subset_of=(
                        None
                        if declaration.member_of is None
                        else relation_names[declaration.member_of]
                    ),
                )
                for declaration in source.declarations.relations
                if not declaration.containment
            ),
            tg.PolyadicRelationDeclaration(
                roots_name,
                tg.RelationSideDeclaration(
                    (tg.RelationEndpointKind.ITEM,),
                    minimum=0,
                    maximum=0,
                    allow_empty=True,
                ),
                tg.RelationSideDeclaration(
                    (tg.RelationEndpointKind.ITEM,),
                    tuple(tier_names[tier] for tier in root_tiers),
                    minimum=0,
                    allow_empty=True,
                ),
                # No distinct_targets: the legacy roots list did not forbid a
                # repeated root, so requiring distinctness here would refuse a
                # duplicate-root graph the old Form.roots returned verbatim.
            ),
        )
        relations = tuple(
            tg.PolyadicRelationInstance(
                containment_names[relation.name],
                tuple(old_to_new[source_ref] for source_ref in relation.sources),
                tuple(old_to_new[target] for target in relation.targets),
            )
            for relation in source.relations
            if relation.name in containment_names
        ) + tuple(
            tg.PolyadicRelationInstance(
                relation_names[relation.name],
                tuple(
                    (
                        old_to_new[item]
                        if source.endpoint_kinds[item] is EndpointKind.EVENT
                        else durable_position(item)
                    )
                    for item in relation.sources
                ),
                tuple(
                    (
                        old_to_new[item]
                        if source.endpoint_kinds[item] is EndpointKind.EVENT
                        else durable_position(item)
                    )
                    for item in relation.targets
                ),
            )
            for relation in _dependency_ordered_relations(
                tuple(
                    relation
                    for relation in source.relations
                    if relation.name not in containment_names
                ),
                source.declarations,
            )
        )
        parent_order = {
            (target, source_ref, relation.name): rank
            for rank, relation in enumerate(source.relations)
            if relation.name in containment_names
            for target in relation.targets
            for source_ref in relation.sources
        }
        traversal_order = tuple(
            dict.fromkeys(
                relation.name
                for relation in source.relations
                if relation.name in containment_names
            )
        ) + tuple(
            declaration.name
            for declaration in containment
            if declaration.name
            not in {
                relation.name
                for relation in source.relations
                if relation.name in containment_names
            }
        )

        opcodes: tuple[Opcode, ...] = (
            DeclareNamespace(tg.NamespaceDeclaration(_PREFIX, _NAMESPACE)),
            *(DeclareTier(tier.declaration) for tier in tiers),
            DeclareTier(tg.TierDeclaration(clock_name, "clock")),
            *(DeclareRelation(declaration) for declaration in declarations),
            DeclareAttribute(
                tg.AttributeDeclaration(
                    tick_name, tg.AttributeDomain.POSITION, tg.XsdType.INTEGER
                )
            ),
            DeclareAttribute(
                tg.AttributeDeclaration(
                    gap_name, tg.AttributeDomain.POSITION, tg.XsdType.INTEGER
                )
            ),
            *(
                DeclareAttribute(
                    tg.AttributeDeclaration(
                        _name(name), tg.AttributeDomain.ITEM, value_type
                    )
                )
                for name, value_type in _PAYLOAD_DECLARATIONS
            ),
            *(
                AddItem(tier.declaration.name, item)
                for tier in tiers
                for item in tier.items
            ),
            *(
                AddItem(clock_name, tg.Item(durable_id=f"ipakit-clockcell-{index}"))
                for index in range(max(0, len(clock_positions) - 1))
            ),
            *(
                opcode
                for boundary_index, (tick, gap) in enumerate(clock_positions)
                for opcode in (
                    AttachValue(
                        tg.AttributeDomain.POSITION,
                        tg.PositionRef(clock_name, boundary_index),
                        tg.AttributeValue(tick_name, tg.XsdType.INTEGER, str(tick)),
                    ),
                    AttachValue(
                        tg.AttributeDomain.POSITION,
                        tg.PositionRef(clock_name, boundary_index),
                        tg.AttributeValue(gap_name, tg.XsdType.INTEGER, str(gap)),
                    ),
                )
            ),
            *(Relate(relation) for relation in relations),
            Relate(
                tg.PolyadicRelationInstance(
                    roots_name,
                    (),
                    tuple(old_to_new[root] for root in source.roots),
                )
            ),
        )
        projected = Program(opcodes).unroll().graph
        event_tiers = dict(source.event_tiers)
        admitted_sources = {
            declaration.name: (
                None
                if declaration.source_tiers is None
                else frozenset(declaration.source_tiers)
            )
            for declaration in containment
        }
        admitted_targets = {
            declaration.name: (
                None
                if declaration.target_tiers is None
                else frozenset(declaration.target_tiers)
            )
            for declaration in containment
        }
        active_by_parent = {
            parent: tuple(
                relation.name
                for relation in source.relations
                if relation.name in containment_names and relation.sources == (parent,)
            )
            for parent in refs
        }
        result = cls(
            projected,
            MappingProxyType(old_to_new),
            MappingProxyType(new_to_old),
            MappingProxyType(tier_names),
            MappingProxyType(containment_names),
            MappingProxyType(relation_names),
            roots_name,
            MappingProxyType(parent_order),
            traversal_order,
            MappingProxyType(event_tiers),
            MappingProxyType(admitted_sources),
            MappingProxyType(admitted_targets),
            MappingProxyType(active_by_parent),
        )
        result._verify_identity(refs)
        return result

    def _verify_identity(self, refs: tuple[str, ...]) -> None:
        projected = tuple(
            item
            for item in self.graph.canonical_items()
            if item.tier in self.tier_names.values()
        )
        if len(projected) != len(refs) or set(projected) != set(self.new_to_old):
            raise ValueError("containment projection event corpus is not bijective")
        for old, new in self.old_to_new.items():
            if self.new_to_old.get(new) != old:
                raise ValueError(
                    "containment projection identity map is not reversible"
                )
            if self.graph.resolve_item(tg.DurableItemRef(old)) != new:
                raise ValueError(
                    "tiergraph durable identity does not resolve losslessly"
                )

    def traversals(self) -> tuple[tg.OrderedContainment, ...]:
        """Return validated traversals in canonical relation-instance order."""
        return tuple(
            tg.OrderedContainment(self.graph, self.containment_names[name])
            for name in self.traversal_order
        )

    def _traversals_for_parent(
        self, parent: str
    ) -> tuple[tuple[str, tg.OrderedContainment], ...]:
        active = self.active_by_parent[parent]
        order = (
            *active,
            *(name for name in self.traversal_order if name not in active),
        )
        return tuple(
            (name, tg.OrderedContainment(self.graph, self.containment_names[name]))
            for name in order
        )

    def _admits(self, relation_name: str, tier_name: str | None, *, side: str) -> bool:
        tiers = (
            self.admitted_sources[relation_name]
            if side == "source"
            else self.admitted_targets[relation_name]
        )
        # The compatibility traversal returns an empty fiber for a non-admitted
        # origin, so skipping it preserves that answer. Admitted origins are
        # unchanged,
        # and Graph construction already rejects non-admitted stored endpoints.
        return tiers is None or (tier_name is not None and tier_name in tiers)

    def _old_reference(self, node: tg.Node) -> str:
        if not isinstance(node.reference, tg.ItemRef):
            raise ValueError("ordered containment returned a non-item node")
        return self.new_to_old[node.reference]

    def direct_children(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        item = self.old_to_new.get(parent)
        if item is None:
            return ()
        children = tuple(
            self._old_reference(node)
            for relation_name, traversal in self._traversals_for_parent(parent)
            if self._admits(relation_name, self.event_tiers[parent], side="source")
            for node in traversal.direct_children(item).nodes
        )
        if tier is None:
            return children
        tier_name = self.tier_names.get(tier)
        return tuple(
            child for child in children if self.old_to_new[child].tier == tier_name
        )

    def descendants(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        if parent not in self.old_to_new:
            return ()
        reachable: set[str] = set()
        frontier = [parent]
        while frontier:
            origin = frontier.pop()
            for relation_name, traversal in zip(
                self.traversal_order, self.traversals(), strict=True
            ):
                if not self._admits(
                    relation_name, self.event_tiers[origin], side="source"
                ):
                    continue
                for node in traversal.descendants(self.old_to_new[origin]).nodes:
                    descendant = self._old_reference(node)
                    if descendant not in reachable and descendant != parent:
                        reachable.add(descendant)
                        frontier.append(descendant)

        # OrderedContainment owns transitive reachability.  This consumer-side
        # pass composes its per-relation answer into the legacy canonical
        # cross-relation depth-first order and cycle de-duplication.
        result: list[str] = []
        pending = list(self.direct_children(parent))
        visited = {parent}
        while pending:
            item = pending.pop(0)
            if item in reachable and item not in visited:
                visited.add(item)
                if tier is None or self.event_tiers[item] == tier:
                    result.append(item)
                pending[0:0] = self.direct_children(item)
        return tuple(result)

    def leaves(self, parent: str) -> tuple[str, ...]:
        if parent not in self.old_to_new:
            return (parent,)
        visited: set[str] = set()

        def walk(item: str) -> tuple[str, ...]:
            if item in visited:
                return ()
            visited.add(item)
            per_relation = tuple(
                tuple(
                    self._old_reference(node)
                    for node in traversal.leaves(self.old_to_new[item]).nodes
                )
                for relation_name, traversal in zip(
                    self.traversal_order, self.traversals(), strict=True
                )
                if self._admits(relation_name, self.event_tiers[item], side="source")
            )
            if all(leaves == (item,) for leaves in per_relation):
                return (item,)
            return tuple(
                leaf for child in self.direct_children(item) for leaf in walk(child)
            )

        return walk(parent)

    def parents(self, child: str) -> tuple[str, ...]:
        item = self.old_to_new.get(child)
        if item is None:
            return ()
        parents = [
            (self._old_reference(node), relation_name)
            for relation_name, traversal in zip(
                self.traversal_order, self.traversals(), strict=True
            )
            if self._admits(relation_name, self.event_tiers[child], side="target")
            for node in traversal.parents(item).nodes
        ]
        return tuple(
            parent
            for parent, relation_name in sorted(
                parents,
                key=lambda pair: self.parent_order.get((child, pair[0], pair[1]), -1),
            )
        )

    def ancestors(self, child: str) -> tuple[str, ...]:
        if child not in self.old_to_new:
            return ()
        reachable: set[str] = set()
        frontier = [child]
        while frontier:
            origin = frontier.pop()
            for relation_name, traversal in zip(
                self.traversal_order, self.traversals(), strict=True
            ):
                if not self._admits(
                    relation_name, self.event_tiers[origin], side="target"
                ):
                    continue
                for node in traversal.ancestors(self.old_to_new[origin]).nodes:
                    ancestor = self._old_reference(node)
                    if ancestor not in reachable:
                        reachable.add(ancestor)
                        frontier.append(ancestor)

        # Kernel inverse reachability is set-valued.  Parent incidence carries
        # the relation identity needed to restore legacy breadth-first order.
        result: list[str] = []
        pending = list(self.parents(child))
        while pending:
            item = pending.pop(0)
            if item in reachable and item not in result:
                result.append(item)
                pending.extend(self.parents(item))
        return tuple(result)


def _dependency_ordered_relations(
    relations: tuple[Relation, ...], declarations: Declarations
) -> tuple[Relation, ...]:
    """Topologically order subset-constrained relations without moving others."""
    dependencies = {
        declaration.name: declaration.member_of
        for declaration in declarations.relations
        if declaration.member_of is not None
    }
    participating = frozenset(dependencies) | frozenset(dependencies.values())
    if not participating:
        return relations

    declaration_order = {
        declaration.name: index
        for index, declaration in enumerate(declarations.relations)
    }
    remaining = set(participating)
    ordered_names: list[str] = []
    while remaining:
        ready = sorted(
            (name for name in remaining if dependencies.get(name) not in remaining),
            key=declaration_order.__getitem__,
        )
        if not ready:
            # Declaration validation owns dependency-cycle rejection. Keep the
            # input stable here so lowering does not obscure that diagnostic.
            return relations
        ordered_names.extend(ready)
        remaining.difference_update(ready)

    rank = {name: index for index, name in enumerate(ordered_names)}
    dependent_relations = iter(
        sorted(
            (relation for relation in relations if relation.name in participating),
            key=lambda relation: rank[relation.name],
        )
    )
    return tuple(
        next(dependent_relations) if relation.name in participating else relation
        for relation in relations
    )


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
