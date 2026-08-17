"""Durable tiergraph item identity behind ipakit's legacy pointer spelling."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from tiergraph import (
    DurableItemRef,
    Item,
    ItemRef,
    NamespaceDeclaration,
    QualifiedName,
    Tier,
    TierDeclaration,
)
from tiergraph import (
    Graph as TiergraphGraph,
)

if TYPE_CHECKING:
    from ._tiergraph import Graph

NAMESPACE = "urn:ipakit:compatibility"


@dataclass(frozen=True)
class DurableEventIdentity:
    """Bidirectional identity seam; paths are coordinates, never identity."""

    graph: TiergraphGraph
    _path_by_id: MappingProxyType[str, str]
    _id_by_path: MappingProxyType[str, str]

    @classmethod
    def build(cls, source: Graph) -> DurableEventIdentity:
        by_tier: dict[str, list[tuple[str, str]]] = {
            declaration.name: [] for declaration in source.declarations.tiers
        }
        for path in source.event_references():
            resolved = source.resolve(path)
            assert resolved.event is not None and resolved.tier is not None
            assert resolved.event.durable_id is not None
            by_tier[resolved.tier].append((path, resolved.event.durable_id))

        tiers = tuple(
            Tier(
                TierDeclaration(QualifiedName(NAMESPACE, name), name),
                tuple(Item(durable_id) for _, durable_id in by_tier[name]),
            )
            for name in by_tier
        )
        carrier = TiergraphGraph(
            (NamespaceDeclaration("ipakit", NAMESPACE),), tiers, ()
        )
        pairs = tuple(pair for values in by_tier.values() for pair in values)
        return cls(
            carrier,
            MappingProxyType({durable_id: path for path, durable_id in pairs}),
            MappingProxyType(dict(pairs)),
        )

    def durable(self, path: str) -> DurableItemRef:
        """Resolve a legacy coordinate to authoritative durable identity."""
        try:
            durable_id = self._id_by_path[path]
        except KeyError as exc:
            raise ValueError(f"unknown event path {path!r}") from exc
        reference = DurableItemRef(durable_id)
        self.graph.resolve_item(reference)
        return reference

    def coordinate(self, reference: DurableItemRef) -> ItemRef:
        """Resolve durable identity to tiergraph's current generic coordinate."""
        return self.graph.resolve_item(reference)

    def path(self, reference: DurableItemRef) -> str:
        """Project durable identity to ipakit's current legacy spelling."""
        self.graph.resolve_item(reference)
        try:
            return self._path_by_id[reference.durable_id]
        except KeyError as exc:
            raise ValueError(
                f"unknown durable item id {reference.durable_id!r}"
            ) from exc
