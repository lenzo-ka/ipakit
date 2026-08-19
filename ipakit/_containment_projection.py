"""Read-only containment projection from ipakit graphs onto tiergraph.

Only event identity and containment incidence cross this seam.  Profile values,
clock coordinates, timing, roots, choices, and every other ipakit graph concern
remain authoritative in the source graph.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import tiergraph as tg

from ._tiergraph import EndpointKind, Graph

_NAMESPACE = "https://ipakit.dev/tiergraph/containment-projection/v1"
_PREFIX = "ipakit-containment"
_EVENT_TYPE = tg.QualifiedName(_NAMESPACE, "event")


def _name(local_name: str) -> tg.QualifiedName:
    return tg.QualifiedName(_NAMESPACE, local_name)


@dataclass(frozen=True)
class ContainmentProjection:
    """Single-source ordered containment view with lossless event identity.

    Navigation is identical to the legacy implementation on every accepted
    graph.  Accepted containment instances have exactly one event source and
    only event targets (including a declared empty target side).  Source
    cardinalities other than one and boundary endpoints are refused by name.
    """

    source: Graph
    graph: tg.Graph
    old_to_new: dict[str, tg.ItemRef]
    new_to_old: dict[tg.ItemRef, str]
    tier_names: dict[str, tg.QualifiedName]
    containment_names: dict[str, tg.QualifiedName]
    parent_order: dict[tuple[str, str, str], int]
    traversal_order: tuple[str, ...]

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
            if relation.name in containment_names_set and any(
                source.resolve(endpoint).kind is not EndpointKind.EVENT
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
            traversal_order,
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
        """Return validated traversals in canonical relation-instance order."""
        return tuple(
            tg.OrderedContainment(self.graph, self.containment_names[name])
            for name in self.traversal_order
        )

    def _traversals_for_parent(
        self, parent: str
    ) -> tuple[tuple[str, tg.OrderedContainment], ...]:
        active = tuple(
            relation.name
            for relation in self.source.relations
            if relation.name in self.containment_names and relation.sources == (parent,)
        )
        order = (
            *active,
            *(name for name in self.traversal_order if name not in active),
        )
        return tuple(
            (name, tg.OrderedContainment(self.graph, self.containment_names[name]))
            for name in order
        )

    def _admits(self, relation_name: str, tier_name: str | None, *, side: str) -> bool:
        declaration = next(
            declaration
            for declaration in self.source.declarations.relations
            if declaration.name == relation_name and declaration.containment
        )
        tiers = getattr(declaration, f"{side}_tiers")
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
            if self._admits(
                relation_name, self.source.resolve(parent).tier, side="source"
            )
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
                    relation_name, self.source.resolve(origin).tier, side="source"
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
            per_relation = tuple(
                tuple(
                    self._old_reference(node)
                    for node in traversal.leaves(self.old_to_new[item]).nodes
                )
                for relation_name, traversal in zip(
                    self.traversal_order, self.traversals(), strict=True
                )
                if self._admits(
                    relation_name, self.source.resolve(item).tier, side="source"
                )
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
            if self._admits(
                relation_name, self.source.resolve(child).tier, side="target"
            )
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
                    relation_name, self.source.resolve(origin).tier, side="target"
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
