"""Experimental, versioned views of finite inventory membership.

The adapters in this module snapshot existing :class:`Inventory` accounting.
They do not resolve correspondences or compute comparisons.  This interface is
experimental: consumers must check the schema identifier and version.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ._identity import identity_fingerprint
from ._provenance import SourceMetadata
from .inventories import (
    Inventory,
    Style,
    inventories,
    inventory,
    inventory_from_dictionary,
)

if TYPE_CHECKING:
    from .features import IPAFeatures

INVENTORY_VIEW_SCHEMA_ID = "ipakit.inventory-view"
INVENTORY_VIEW_SCHEMA_VERSION = 1

MemberStatus = Literal[
    "present",
    "filtered",
    "dropped",
    "unreadable",
    "refused",
    "unavailable",
    "unresolved",
]
Availability = Literal["available", "unavailable"]

_STATUSES = frozenset(
    {
        "present",
        "filtered",
        "dropped",
        "unreadable",
        "refused",
        "unavailable",
        "unresolved",
    }
)


@dataclass(frozen=True)
class InventoryMemberCounts:
    """Attestation counts retained from a derived dictionary inventory."""

    entries: int
    tokens: int

    def __post_init__(self) -> None:
        if type(self.entries) is not int or self.entries < 0:
            raise ValueError("member entry count must be a nonnegative integer")
        if type(self.tokens) is not int or self.tokens < 0:
            raise ValueError("member token count must be a nonnegative integer")
        if self.entries > self.tokens:
            raise ValueError("member entry count cannot exceed its token count")

    @classmethod
    def from_mapping(cls, value: Mapping[str, int]) -> InventoryMemberCounts:
        """Copy the exact two-field ``Inventory.counts`` value."""
        if set(value) != {"entries", "tokens"}:
            raise ValueError("member counts must contain exactly entries and tokens")
        return cls(value["entries"], value["tokens"])

    def to_dict(self) -> dict[str, int]:
        """Return canonical JSON-ready counts."""
        return {"entries": self.entries, "tokens": self.tokens}


@dataclass(frozen=True)
class InventoryViewMember:
    """One declared source item assigned to exactly one admission status."""

    index: int
    source_token: str
    status: MemberStatus
    house_form: str | None = None
    counts: InventoryMemberCounts | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("member index must be a nonnegative integer")
        if not isinstance(self.source_token, str) or not self.source_token:
            raise ValueError("member source token must be a nonempty string")
        if self.status not in _STATUSES:
            raise ValueError(f"unknown inventory member status {self.status!r}")
        if self.house_form is not None and (
            not isinstance(self.house_form, str) or not self.house_form
        ):
            raise ValueError("member house form must be a nonempty string or None")
        if self.status in {"present", "filtered", "dropped"}:
            if self.house_form is None:
                raise ValueError(f"{self.status} member must retain its house form")
        elif self.status == "unavailable" and self.house_form is not None:
            raise ValueError("unavailable member cannot have a house form")
        if self.status == "dropped" and self.counts is None:
            raise ValueError("dropped member must retain its counts")
        if self.status in {"unreadable", "refused", "unavailable", "unresolved"}:
            if not self.reason:
                raise ValueError(f"{self.status} member must state a reason")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not self.reason
        ):
            raise ValueError("member reason must be a nonempty string or None")

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-ready member shape."""
        result: dict[str, object] = {
            "index": self.index,
            "source_token": self.source_token,
            "status": self.status,
            "house_form": self.house_form,
        }
        if self.counts is not None:
            result["counts"] = self.counts.to_dict()
        if self.reason is not None:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class InventoryView:
    """Immutable source inventory snapshot under schema version 1.

    ``members`` is declaration ordered.  Its indices must be contiguous and
    every row has one scalar status, so a source item cannot silently enter two
    accounting buckets.  ``identity`` fingerprints the complete canonical
    snapshot apart from the identity field itself.
    """

    name: str
    kind: str
    provenance: str
    availability: Availability
    members: tuple[InventoryViewMember, ...]
    style: str | None = None
    version: str | None = None
    source: SourceMetadata | None = None
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("kind", self.kind),
            ("provenance", self.provenance),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"inventory view {label} must be a nonempty string")
        if self.availability not in {"available", "unavailable"}:
            raise ValueError(f"unknown inventory availability {self.availability!r}")
        if not isinstance(self.members, tuple):
            raise ValueError("inventory view members must be a tuple")
        if tuple(member.index for member in self.members) != tuple(
            range(len(self.members))
        ):
            raise ValueError("inventory view member indices must be contiguous")
        unavailable = [
            member for member in self.members if member.status == "unavailable"
        ]
        if self.availability == "available" and unavailable:
            raise ValueError("available inventory view cannot have unavailable members")
        if self.availability == "unavailable":
            if len(self.members) != 1 or len(unavailable) != 1:
                raise ValueError(
                    "unavailable inventory view must contain one unavailable member"
                )
        object.__setattr__(self, "identity", identity_fingerprint(self._material()))

    @property
    def schema_version(self) -> int:
        """Return the version callers must check before consuming the shape."""
        return INVENTORY_VIEW_SCHEMA_VERSION

    @property
    def declared_population(self) -> tuple[str, ...]:
        """Return source tokens in the adapter's stable declaration order."""
        return tuple(member.source_token for member in self.members)

    def _material(self) -> dict[str, object]:
        return {
            "schema": {
                "id": INVENTORY_VIEW_SCHEMA_ID,
                "version": INVENTORY_VIEW_SCHEMA_VERSION,
            },
            "name": self.name,
            "kind": self.kind,
            "provenance": self.provenance,
            "availability": self.availability,
            "style": self.style,
            "version": self.version,
            "source": None if self.source is None else self.source.to_dict(),
            "declared_population": list(self.declared_population),
            "members": [member.to_dict() for member in self.members],
        }

    def to_dict(self) -> dict[str, object]:
        """Return the canonical experimental schema, including its identity."""
        return {**self._material(), "identity": self.identity}


def _counts(value: Mapping[str, int]) -> InventoryMemberCounts:
    return InventoryMemberCounts.from_mapping(value)


def inventory_view(item: Inventory, *, kind: str | None = None) -> InventoryView:
    """Snapshot one existing registry or derived ``Inventory``.

    ``Inventory.phones`` and its accounting mappings remain authoritative.  A
    missing finite population becomes one explicit ``unavailable`` row rather
    than an available view with an empty population.
    """
    resolved_kind = kind or (
        item.source.kind if item.source is not None else "inventory"
    )
    if item.phones is None:
        if item.counts or item.dropped:
            raise ValueError("inventory without a finite population has member counts")
        reason = f"{item.name} has no available finite inventory population"
        return InventoryView(
            item.name,
            resolved_kind,
            item.provenance,
            "unavailable",
            (InventoryViewMember(0, item.name, "unavailable", reason=reason),),
            item.style.name,
            item.version,
            item.source,
        )

    phones = tuple(item.phones)
    if len(set(phones)) != len(phones):
        raise ValueError("inventory phones must be unique")
    dropped = tuple(item.dropped)
    if set(phones) & set(dropped):
        raise ValueError("inventory phone cannot be both present and dropped")
    refused = tuple(item.refusals)
    if (set(phones) | set(dropped)) & set(refused):
        raise ValueError("inventory token must partition into exactly one status")

    if item.counts:
        population = tuple(item.counts)
        if set(population) != set(phones) | set(dropped):
            raise ValueError(
                "inventory counts must cover exactly present and dropped phones"
            )
        for phone in dropped:
            if dict(item.dropped[phone]) != dict(item.counts[phone]):
                raise ValueError(f"dropped counts for {phone!r} do not match counts")
    else:
        if dropped:
            raise ValueError("inventory drops require complete counts")
        population = phones

    members: list[InventoryViewMember] = []
    present = set(phones)
    dropped_set = set(dropped)
    for token in population:
        status: MemberStatus
        status = "present" if token in present else "dropped"
        member_counts = _counts(item.counts[token]) if item.counts else None
        members.append(
            InventoryViewMember(
                len(members),
                token,
                status,
                house_form=token,
                counts=member_counts,
                reason=(
                    "below the requested minimum entry count"
                    if token in dropped_set
                    else None
                ),
            )
        )
    for token, reason in item.refusals.items():
        members.append(
            InventoryViewMember(len(members), token, "refused", reason=reason)
        )
    return InventoryView(
        item.name,
        resolved_kind,
        item.provenance,
        "available",
        tuple(members),
        item.style.name,
        item.version,
        item.source,
    )


def registry_inventory_view(name: str) -> InventoryView:
    """Load and adapt one currently registered inventory by name."""
    return inventory_view(inventory(name))


def registry_inventory_views() -> tuple[InventoryView, ...]:
    """Adapt every name returned by the current registry in stable name order."""
    return tuple(registry_inventory_view(name) for name in inventories())


def inventory_view_from_dictionary(
    path: Path,
    style: str | Style,
    *,
    name: str | None = None,
    ipa: IPAFeatures | None = None,
    min_entries: int | None = None,
    refuse_unreadable: bool = False,
) -> InventoryView:
    """Derive and adapt a pronunciation dictionary without losing accounting."""
    item = inventory_from_dictionary(
        path,
        style,
        name=name,
        ipa=ipa,
        min_entries=min_entries,
        refuse_unreadable=refuse_unreadable,
    )
    return inventory_view(item, kind="pronunciation-dictionary")


__all__ = [
    "INVENTORY_VIEW_SCHEMA_ID",
    "INVENTORY_VIEW_SCHEMA_VERSION",
    "InventoryMemberCounts",
    "InventoryView",
    "InventoryViewMember",
    "MemberStatus",
    "inventory_view",
    "inventory_view_from_dictionary",
    "registry_inventory_view",
    "registry_inventory_views",
]
