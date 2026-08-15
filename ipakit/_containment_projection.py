"""Read-only containment projection from ipakit graphs onto tiergraph.

Only event identity and containment incidence cross this seam.  Profile values,
clock coordinates, timing, roots, choices, and every other ipakit graph concern
remain authoritative in the source graph.
"""

from __future__ import annotations

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
    """Lossless event-identity and containment view of one completed graph."""

    source: Graph
    graph: tg.Graph
    old_to_new: dict[str, tg.ItemRef]
    new_to_old: dict[tg.ItemRef, str]
    tier_names: dict[str, tg.QualifiedName]
    downward_names: dict[str, tg.QualifiedName]
    upward_names: dict[str, tg.QualifiedName]

    @classmethod
    def build(cls, source: Graph) -> ContainmentProjection:
        """Project every event and every navigation-visible containment edge.

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
        downward_names = {
            declaration.name: _name(f"contains-down-{index}")
            for index, declaration in enumerate(containment)
        }
        upward_names = {
            declaration.name: _name(f"contains-up-{index}")
            for index, declaration in enumerate(containment)
        }
        declarations: tuple[
            tg.SimpleRelationDeclaration | tg.BipartiteRelationDeclaration, ...
        ] = (
            *memberships,
            *(
                tg.BipartiteRelationDeclaration(
                    name, _EVENT_TYPE, _EVENT_TYPE, acyclic=True
                )
                for name in (*downward_names.values(), *upward_names.values())
            ),
        )

        downward: list[tg.RelationInstance] = []
        upward: list[tg.RelationInstance] = []
        for relation in source.relations:
            declaration = source.declarations.relation(relation.name)
            if declaration is None or not declaration.containment:
                continue
            # The old downward API admits only a singleton source tuple, while
            # its upward API returns every source of any matching relation.
            if len(relation.sources) == 1:
                downward.extend(
                    tg.RelationInstance(
                        downward_names[relation.name],
                        old_to_new[relation.sources[0]],
                        old_to_new[target],
                    )
                    for target in relation.targets
                )
            upward.extend(
                tg.RelationInstance(
                    upward_names[relation.name],
                    old_to_new[target],
                    old_to_new[parent],
                )
                for target in relation.targets
                for parent in relation.sources
            )

        projected = tg.Graph(
            (tg.NamespaceDeclaration(_PREFIX, _NAMESPACE),),
            tiers,
            declarations,
            tuple((*downward, *upward)),
        )
        result = cls(
            source,
            projected,
            old_to_new,
            new_to_old,
            tier_names,
            downward_names,
            upward_names,
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

    def _selection(self, reference: str) -> tg.NodeSet:
        item = self.old_to_new[reference]
        return tg.NodeSet(self.graph, (tg.Node(tg.NodeKind.ITEM, item),))

    def _step(
        self, reference: str, relations: tuple[tg.QualifiedName, ...]
    ) -> set[tg.ItemRef]:
        walked = tuple(
            tg.Walk(
                self._selection(reference), relation, tg.WalkDirection.FORWARD, 1
            ).evaluate()
            for relation in relations
        )
        return {
            node.reference
            for result in walked
            for node in result.nodes.nodes
            if node.kind is tg.NodeKind.ITEM and isinstance(node.reference, tg.ItemRef)
        }

    def direct_children(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        if parent not in self.old_to_new:
            return ()
        names = tuple(self.downward_names.values())
        admitted = self._step(parent, names)
        origin = self.old_to_new[parent]
        children = tuple(
            self.new_to_old[relation.right]
            for relation in self.graph.relations
            if relation.declaration in names
            and relation.left == origin
            and isinstance(relation.right, tg.ItemRef)
            and relation.right in admitted
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
                if tier is None or self.old_to_new[item].tier == self.tier_names.get(
                    tier
                ):
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
        if child not in self.old_to_new:
            return ()
        names = tuple(self.upward_names.values())
        admitted = self._step(child, names)
        origin = self.old_to_new[child]
        return tuple(
            self.new_to_old[relation.right]
            for relation in self.graph.relations
            if relation.declaration in names
            and relation.left == origin
            and isinstance(relation.right, tg.ItemRef)
            and relation.right in admitted
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
