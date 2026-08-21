"""Read-only containment projection from ipakit graphs onto tiergraph.

Only event identity and containment incidence cross this seam.  Profile values,
clock coordinates, timing, roots, choices, and every other ipakit graph concern
remain authoritative in the source graph.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

import tiergraph as tg

from ._tiergraph import (
    ClockNode,
    Declarations,
    EndpointKind,
    Event,
    Graph,
    GraphValidationError,
    Position,
    Relation,
    ResolvedReference,
    _escape,
    _pointer_parts,
)

_NAMESPACE = "https://ipakit.dev/tiergraph/containment-projection/v1"
_PREFIX = "ipakit-containment"
_EVENT_TYPE = tg.QualifiedName(_NAMESPACE, "event")

_PAYLOAD_DECLARATIONS = (
    ("text", tg.XsdType.STRING),
    ("spelling", tg.XsdType.STRING),
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
        from .form import Unit

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
        return ()
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
    def capture(cls, source: Graph) -> ContainmentProjectionInput:
        refs = source.event_references()
        endpoints = {
            ref
            for relation in source.relations
            for ref in (*relation.sources, *relation.targets)
        }
        resolved = {ref: source.resolve(ref) for ref in (*refs, *endpoints)}
        event_tiers = {ref: resolved[ref].tier for ref in refs}
        assert all(tier is not None for tier in event_tiers.values())
        return cls(
            refs,
            source.declarations,
            tuple(source.relations),
            {ref: tier for ref, tier in event_tiers.items() if tier is not None},
            {
                ref: cast(Event, resolved[ref].event)
                for ref in refs
                if resolved[ref].event is not None
            },
            {ref: resolved[ref].kind for ref in endpoints},
            tuple(source.clock),
            tuple(source.roots),
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

    def position(self, pointer: str, *, span_endpoint: bool = False) -> Position:
        """Resolve a captured clock position without retaining its scaffold."""
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
        """Return captured events in canonical presentation order."""
        return tuple(
            f"/clock/{tick}/{_escape(group.tier)}/{index}"
            for tick, node in enumerate(self.clock)
            for group in node.groups
            for index in range(len(group.events))
        )


@dataclass(frozen=True)
class ContainmentProjection:
    """Single-source ordered containment view with lossless event identity.

    Navigation is identical to the legacy implementation on every accepted
    graph.  Accepted containment instances have exactly one event source and
    only event targets (including a declared empty target side).  Source
    cardinalities other than one and boundary endpoints are refused by name.
    """

    graph: tg.Graph
    old_to_new: dict[str, tg.ItemRef]
    new_to_old: dict[tg.ItemRef, str]
    tier_names: dict[str, tg.QualifiedName]
    containment_names: dict[str, tg.QualifiedName]
    relation_names: dict[str, tg.QualifiedName]
    roots_name: tg.QualifiedName
    parent_order: dict[tuple[str, str, str], int]
    traversal_order: tuple[str, ...]
    event_tiers: dict[str, str]
    admitted_sources: dict[str, frozenset[str] | None]
    admitted_targets: dict[str, frozenset[str] | None]
    active_by_parent: dict[str, tuple[str, ...]]

    @classmethod
    def build(cls, source: Graph) -> ContainmentProjection:
        """Project event identity and single-source containment incidence.

        Projection or identity validation failure is a hard runtime error by
        design.  Falling back to the old kernel would make navigation answers
        depend silently on whether projection happened to succeed.
        """
        return cls.build_captured(ContainmentProjectionInput.capture(source))

    @classmethod
    def build_captured(
        cls, source: ContainmentProjectionInput
    ) -> ContainmentProjection:
        """Build from facts captured while the build-only scaffold was resident."""
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
        relation_names = {
            declaration.name: containment_names.get(
                declaration.name, _name(f"relation-{index}")
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
                    tg.RelationSideDeclaration(
                        (tg.RelationEndpointKind.ITEM,),
                        None,
                        minimum=declaration.source_arity[0],
                        maximum=declaration.source_arity[1],
                        allow_empty=declaration.allow_empty_source,
                    ),
                    tg.RelationSideDeclaration(
                        (tg.RelationEndpointKind.ITEM,),
                        None,
                        minimum=declaration.target_arity[0],
                        maximum=declaration.target_arity[1],
                        allow_empty=declaration.allow_empty_target,
                    ),
                    acyclic=declaration.acyclic,
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
                tuple(old_to_new[item] for item in relation.sources),
                tuple(old_to_new[item] for item in relation.targets),
            )
            for relation in source.relations
            if relation.name not in containment_names
            and all(
                item in old_to_new for item in (*relation.sources, *relation.targets)
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
            old_to_new,
            new_to_old,
            tier_names,
            containment_names,
            relation_names,
            roots_name,
            parent_order,
            traversal_order,
            event_tiers,
            admitted_sources,
            admitted_targets,
            active_by_parent,
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
        # The legacy traversal returned an empty fiber for a non-admitted origin,
        # so skipping it preserves that answer.  Admitted origins are unchanged,
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


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
