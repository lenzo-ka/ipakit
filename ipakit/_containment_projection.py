"""Read-only containment projection from ipakit graphs onto tiergraph.

Only event identity and containment incidence cross this seam.  Profile values,
clock coordinates, timing, roots, choices, and every other ipakit graph concern
remain authoritative in the source graph.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import tiergraph as tg

from ._tiergraph import Graph

_NAMESPACE = "https://ipakit.dev/tiergraph/containment-projection/v1"
_PREFIX = "ipakit-containment"
_EVENT_TYPE = tg.QualifiedName(_NAMESPACE, "event")


def _name(local_name: str) -> tg.QualifiedName:
    return tg.QualifiedName(_NAMESPACE, local_name)


@dataclass(frozen=True)
class ContainmentProjection:
    """Single-source ordered containment view with lossless event identity.

    Navigation answers are unchanged on every graph this projection accepts.
    It accepts single-source containment instances and refuses multi-source
    instances by name because joint-containment navigation is not defined.
    """

    source: Graph
    graph: tg.Graph
    old_to_new: dict[str, tg.ItemRef]
    new_to_old: dict[tg.ItemRef, str]
    tier_names: dict[str, tg.QualifiedName]
    containment_names: dict[str, tg.QualifiedName]
    parent_order: dict[tuple[str, str], int]

    @classmethod
    def build(cls, source: Graph) -> ContainmentProjection:
        """Project event identity and single-source containment incidence.

        Projection or identity validation failure is a hard runtime error by
        design.  Falling back to the old kernel would make navigation answers
        depend silently on whether projection happened to succeed.
        """
        refs = source.event_references()
        tier_names = {
            declaration.name: _name(f"tier-{index}")
            for index, declaration in enumerate(source.declarations.tiers)
        }
        by_tier = {
            tier: tuple(ref for ref in refs if source.resolve(ref).tier == tier)
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
                tuple(tg.Item(durable_id=ref) for ref in by_tier[tier]),
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
        containment_names = {
            declaration.name: _name(f"contains-{index}")
            for index, declaration in enumerate(containment)
        }
        item_side = tg.RelationSideDeclaration((tg.RelationEndpointKind.ITEM,))
        declarations: tuple[
            tg.SimpleRelationDeclaration | tg.PolyadicRelationDeclaration, ...
        ] = (
            *memberships,
            *(
                tg.PolyadicRelationDeclaration(
                    name,
                    item_side,
                    item_side,
                    unique_sources=True,
                    acyclic=True,
                )
                for name in containment_names.values()
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
        )
        parent_order = {
            (target, source_ref): rank
            for rank, relation in enumerate(source.relations)
            if relation.name in containment_names
            for target in relation.targets
            for source_ref in relation.sources
        }

        projected = tg.Graph(
            (tg.NamespaceDeclaration(_PREFIX, _NAMESPACE),),
            tiers,
            declarations,
            polyadic_relations=relations,
        )
        result = cls(
            source,
            projected,
            old_to_new,
            new_to_old,
            tier_names,
            containment_names,
            parent_order,
        )
        result._verify_identity(refs)
        return result

    def _verify_identity(self, refs: tuple[str, ...]) -> None:
        projected = self.graph.canonical_items()
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
        """Return validated ordered traversals in declaration order."""
        return tuple(
            tg.OrderedContainment(self.graph, name)
            for name in dict.fromkeys(self.containment_names.values())
        )

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
            for traversal in self.traversals()
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
        result: list[str] = []
        pending = list(self.direct_children(parent))
        visited = {parent}
        while pending:
            item = pending.pop(0)
            if item not in visited:
                visited.add(item)
                if tier is None or self.source.resolve(item).tier == tier:
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
            children = self.direct_children(item)
            if not children:
                return (item,)
            return tuple(leaf for child in children for leaf in walk(child))

        return walk(parent)

    def parents(self, child: str) -> tuple[str, ...]:
        item = self.old_to_new.get(child)
        if item is None:
            return ()
        parents = {
            self._old_reference(node)
            for traversal in self.traversals()
            for node in traversal.parents(item).nodes
        }
        return tuple(
            sorted(
                parents,
                key=lambda parent: self.parent_order.get((child, parent), -1),
            )
        )

    def ancestors(self, child: str) -> tuple[str, ...]:
        if child not in self.old_to_new:
            return ()
        result: list[str] = []
        pending = list(self.parents(child))
        while pending:
            item = pending.pop(0)
            if item not in result:
                result.append(item)
                pending.extend(self.parents(item))
        return tuple(result)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
