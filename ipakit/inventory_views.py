"""Experimental, versioned views of finite inventory membership.

The adapters snapshot existing source accounting and explicit mapping authority.
They never infer correspondence or compute comparisons. This interface is
experimental: consumers must check the schema identifier and version.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    from .bridges.base import Bridge
    from .bridges.phoible import PhoibleInventory
    from .bridges.vocabulary import (
        ProjectionReport,
        VocabularyBridge,
        VocabularyProjection,
    )
    from .clts import Snapshot
    from .clts_mapping import MappingAuthority
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
MappingRelation = Literal["declared-bridge", "reviewed"]

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
class InventoryMemberPosition:
    """A source-native row and field retained for a positioned refusal."""

    row: int
    field: str

    def __post_init__(self) -> None:
        if type(self.row) is not int or self.row < 1:
            raise ValueError("inventory member row must be a positive integer")
        if not isinstance(self.field, str) or not self.field:
            raise ValueError("inventory member field must be a nonempty string")

    def to_dict(self) -> dict[str, object]:
        """Return the source location as canonical JSON-ready data."""
        return {"row": self.row, "field": self.field}


@dataclass(frozen=True)
class InventoryMemberMapping:
    """An explicit source-native mapping, never one inferred by distance."""

    target: str
    relation: MappingRelation
    authority: str

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("inventory mapping target must be a nonempty string")
        if self.relation not in {"declared-bridge", "reviewed"}:
            raise ValueError(f"unknown inventory mapping relation {self.relation!r}")
        if not isinstance(self.authority, str) or not self.authority:
            raise ValueError("inventory mapping authority must be a nonempty string")

    def to_dict(self) -> dict[str, str]:
        """Return the explicit mapping receipt."""
        return {
            "target": self.target,
            "relation": self.relation,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class InventoryExercisedLoss:
    """One positioned bridge loss exercised by a selected projection."""

    direction: str
    name: str
    span: tuple[int, int]
    content: str
    output: str
    projection: int

    def __post_init__(self) -> None:
        if self.direction not in {"external-to-house", "house-to-external"}:
            raise ValueError(f"unknown bridge loss direction {self.direction!r}")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("exercised loss name must be a nonempty string")
        if (
            not isinstance(self.span, tuple)
            or len(self.span) != 2
            or any(type(value) is not int for value in self.span)
            or self.span[0] < 0
            or self.span[1] <= self.span[0]
        ):
            raise ValueError("exercised loss span must be a nonempty half-open span")
        if type(self.projection) is not int or self.projection < 0:
            raise ValueError("exercised loss projection must be nonnegative")

    def to_dict(self) -> dict[str, object]:
        """Return the exercised occurrence without changing its coordinates."""
        return {
            "direction": self.direction,
            "name": self.name,
            "span": list(self.span),
            "content": self.content,
            "output": self.output,
            "projection": self.projection,
        }


@dataclass(frozen=True)
class InventoryBridgeReceipt:
    """Declared bridge capability plus separately observed projection losses."""

    name: str
    version: str
    external_to_house_fidelity: str
    external_to_house_drops: tuple[str, ...]
    external_to_house_tricks: tuple[str, ...]
    house_to_external_fidelity: str
    house_to_external_drops: tuple[str, ...]
    house_to_external_tricks: tuple[str, ...]
    exercised_losses: tuple[InventoryExercisedLoss, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("bridge receipt needs a name and version")
        fidelities = {
            "lossless",
            "lossless-with-declared-tricks",
            "lossy-with-report",
        }
        if self.external_to_house_fidelity not in fidelities:
            raise ValueError("unknown external-to-house bridge fidelity")
        if self.house_to_external_fidelity not in fidelities:
            raise ValueError("unknown house-to-external bridge fidelity")
        declared = {
            "external-to-house": set(self.external_to_house_drops),
            "house-to-external": set(self.house_to_external_drops),
        }
        for loss in self.exercised_losses:
            if loss.name not in declared[loss.direction]:
                raise ValueError(
                    f"exercised bridge loss {loss.name!r} is not declared for "
                    f"{loss.direction}"
                )

    def to_dict(self) -> dict[str, object]:
        """Keep declared capability distinct from exercised occurrences."""
        return {
            "name": self.name,
            "version": self.version,
            "declared": {
                "external-to-house": {
                    "fidelity": self.external_to_house_fidelity,
                    "drops": list(self.external_to_house_drops),
                    "tricks": list(self.external_to_house_tricks),
                },
                "house-to-external": {
                    "fidelity": self.house_to_external_fidelity,
                    "drops": list(self.house_to_external_drops),
                    "tricks": list(self.house_to_external_tricks),
                },
            },
            "exercised": [loss.to_dict() for loss in self.exercised_losses],
        }


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
    position: InventoryMemberPosition | None = None
    mapping: InventoryMemberMapping | None = None

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
        if self.mapping is not None:
            if self.status != "present" or self.house_form is None:
                raise ValueError("only a present member can carry a mapping")
            if self.mapping.target != self.house_form:
                raise ValueError("member mapping target must equal its house form")

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
        if self.position is not None:
            result["position"] = self.position.to_dict()
        if self.mapping is not None:
            result["mapping"] = self.mapping.to_dict()
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
    bridge: InventoryBridgeReceipt | None = None
    mapping_authority: str | None = None
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
        reviewed = tuple(
            member.mapping.authority
            for member in self.members
            if member.mapping is not None and member.mapping.relation == "reviewed"
        )
        if reviewed and self.mapping_authority is None:
            raise ValueError("reviewed members require a view mapping authority")
        if self.mapping_authority is not None and any(
            authority != self.mapping_authority for authority in reviewed
        ):
            raise ValueError("reviewed member authority differs from its view")
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
        material: dict[str, object] = {
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
        if self.bridge is not None:
            material["bridge"] = self.bridge.to_dict()
        if self.mapping_authority is not None:
            material["mapping_authority"] = self.mapping_authority
        return material

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


def _bridge_receipt(
    bridge: Bridge,
    projections: Sequence[ProjectionReport | VocabularyProjection] = (),
) -> InventoryBridgeReceipt:
    from .bridges.vocabulary import VocabularyProjection

    exercised: list[InventoryExercisedLoss] = []
    for projection_index, item in enumerate(projections):
        report = item.report if isinstance(item, VocabularyProjection) else item
        exercised.extend(
            InventoryExercisedLoss(
                "house-to-external",
                loss.name,
                loss.span,
                loss.content,
                loss.output,
                projection_index,
            )
            for loss in report.drops
        )
    outward = bridge.round_trip.external_to_house
    inward = bridge.round_trip.house_to_external
    return InventoryBridgeReceipt(
        bridge.name,
        bridge.version,
        outward.fidelity.value,
        outward.drops,
        outward.tricks,
        inward.fidelity.value,
        inward.drops,
        inward.tricks,
        tuple(exercised),
    )


def vocabulary_inventory_view(
    bridge: VocabularyBridge,
    *,
    projections: Sequence[ProjectionReport | VocabularyProjection] = (),
    ipa: IPAFeatures | None = None,
) -> InventoryView:
    """Adapt one declared phone vocabulary and optional projection evidence."""
    from . import normalize
    from .features import IPAFeatures
    from .phoneset_map import tie_delimited_entry

    if bridge.source is None:
        raise ValueError("vocabulary inventory bridge needs structured source metadata")
    features = ipa or IPAFeatures()
    authority = f"{bridge.name}@{bridge.version}"
    members: list[InventoryViewMember] = []
    for atom in bridge.atoms:
        house = (
            normalize(tie_delimited_entry(atom.spelling, features))
            if atom.kind == "unit"
            else atom.spelling
        )
        is_phone = atom.kind == "unit" and len(features.segments(house)) == 1
        members.append(
            InventoryViewMember(
                len(members),
                atom.output,
                "present" if is_phone else "filtered",
                house_form=house,
                reason=None if is_phone else "not a standalone phone inventory member",
                mapping=(
                    InventoryMemberMapping(house, "declared-bridge", authority)
                    if is_phone
                    else None
                ),
            )
        )
    for refusal in bridge.refusals:
        members.append(
            InventoryViewMember(
                len(members), refusal.spelling, "refused", reason=refusal.reason
            )
        )
    return InventoryView(
        bridge.name,
        bridge.source.kind,
        bridge.provenance,
        "available",
        tuple(members),
        "ipa",
        bridge.version,
        bridge.source,
        _bridge_receipt(bridge, projections),
    )


def phoible_inventory_view(
    item: PhoibleInventory, *, bridge: Bridge | None = None
) -> InventoryView:
    """Adapt one PHOIBLE InventoryID without merging doculect identities."""
    provenance = item.provenance
    authority = (
        f"{bridge.name}@{bridge.version}" if bridge is not None else "PHOIBLE import"
    )
    members = [
        InventoryViewMember(
            index,
            entry.phoneme,
            "present",
            house_form=entry.phoneme,
            position=InventoryMemberPosition(entry.row, "Phoneme"),
            mapping=InventoryMemberMapping(entry.phoneme, "declared-bridge", authority),
        )
        for index, entry in enumerate(item.entries)
    ]
    for refusal in item.refusals:
        members.append(
            InventoryViewMember(
                len(members),
                refusal.value or "<missing>",
                "refused",
                reason=refusal.reason,
                position=InventoryMemberPosition(refusal.row, refusal.field),
            )
        )
    bibliography = ", ".join(provenance.bibtex_keys)
    return InventoryView(
        f"phoible:{provenance.inventory_id}",
        "phoible-doculect-inventory",
        f"PHOIBLE inventory {provenance.inventory_id} from "
        f"{provenance.source}; {bibliography}",
        "available",
        tuple(members),
        "ipa",
        None if bridge is None else bridge.version,
        None if bridge is None else bridge.source,
        None if bridge is None else _bridge_receipt(bridge),
    )


def _unavailable_view(name: str, kind: str, reason: str) -> InventoryView:
    return InventoryView(
        name,
        kind,
        reason,
        "unavailable",
        (InventoryViewMember(0, name, "unavailable", reason=reason),),
        "ipa",
    )


def phoible_inventory_view_from_source(
    inventory_id: str | int,
    *,
    path: str | Path | None = None,
    ipa: IPAFeatures | None = None,
) -> InventoryView:
    """Load one optional PHOIBLE source or report deterministic unavailability."""
    from .bridges.phoible import PhoibleBridge, PhoibleDataUnavailable

    key = str(inventory_id)
    try:
        bridge = PhoibleBridge(path)
        item = bridge.inventory(key, ipa=ipa)
    except PhoibleDataUnavailable:
        return _unavailable_view(
            f"phoible:{key}",
            "phoible-doculect-inventory",
            "PHOIBLE inventory source is unavailable",
        )
    return phoible_inventory_view(item, bridge=bridge)


def _clts_member(
    index: int,
    token: str,
    rule: Mapping[str, object] | None,
    excluded: Mapping[str, str],
    authority: str,
) -> InventoryViewMember:
    if rule is not None:
        target = str(rule["target"])
        return InventoryViewMember(
            index,
            token,
            "present",
            house_form=target,
            mapping=InventoryMemberMapping(target, "reviewed", authority),
        )
    reason = excluded.get(token)
    return InventoryViewMember(
        index,
        token,
        "unresolved",
        reason=(
            f"CLTS snapshot exclusion: {reason}"
            if reason is not None
            else "no reviewed CLTS correspondence"
        ),
    )


def clts_inventory_view(
    snapshot: Snapshot, authority: MappingAuthority
) -> InventoryView:
    """Adapt a frozen CLTS snapshot using only reviewed correspondence authority."""
    from . import load_ipa_features

    data = snapshot.to_data()
    authority_data = authority.to_data()
    authority.validate_context(authority_data["census"], snapshot, load_ipa_features())
    rules = authority_data["rules"]["rules"]
    by_token = {rule["raw"]: rule for rule in rules}
    members = tuple(
        _clts_member(
            index, token, by_token.get(token), data["excluded"], authority.identity
        )
        for index, token in enumerate(data["requested"])
    )
    raw_source = data["source"]["source"]
    source = SourceMetadata(
        raw_source["upstream"],
        raw_source["upstream-url"],
        raw_source["artifact"],
        raw_source["version"],
        raw_source["license"],
        raw_source["kind"],
    )
    return InventoryView(
        f"clts:{data['domain']}",
        "clts-snapshot",
        source.provenance,
        "available",
        members,
        "ipa",
        source.version,
        source,
        mapping_authority=authority.identity,
    )


def clts_inventory_view_from_artifacts(
    *, snapshot_path: Path | None = None, authority_path: Path | None = None
) -> InventoryView:
    """Load optional CLTS artifacts or report deterministic unavailability."""
    from .clts import read_snapshot
    from .clts_mapping import read_authority

    if (snapshot_path is not None and not snapshot_path.is_file()) or (
        authority_path is not None and not authority_path.is_file()
    ):
        return _unavailable_view(
            "clts:core-bipa",
            "clts-snapshot",
            "CLTS snapshot or mapping authority is unavailable",
        )
    try:
        snapshot = read_snapshot(snapshot_path)
        authority = read_authority(authority_path)
    except FileNotFoundError:
        return _unavailable_view(
            "clts:core-bipa",
            "clts-snapshot",
            "CLTS snapshot or mapping authority is unavailable",
        )
    return clts_inventory_view(snapshot, authority)


def clts_inventory_view_from_source(root: Path | None) -> InventoryView:
    """Extract an optional live CLTS source or report stable unavailability."""
    from .clts import ResolverUnavailable, extract_snapshot
    from .clts_mapping import build_authority
    from .extraction import SourceMissingError

    if root is None:
        return _unavailable_view(
            "clts:core-bipa", "clts-snapshot", "live CLTS source is unavailable"
        )
    try:
        snapshot = extract_snapshot(root)
        authority = build_authority(root, snapshot=snapshot)
    except (ResolverUnavailable, SourceMissingError, OSError):
        return _unavailable_view(
            "clts:core-bipa", "clts-snapshot", "live CLTS source is unavailable"
        )
    return clts_inventory_view(snapshot, authority)


__all__ = [
    "INVENTORY_VIEW_SCHEMA_ID",
    "INVENTORY_VIEW_SCHEMA_VERSION",
    "InventoryMemberCounts",
    "InventoryMemberMapping",
    "InventoryMemberPosition",
    "InventoryBridgeReceipt",
    "InventoryExercisedLoss",
    "InventoryView",
    "InventoryViewMember",
    "MemberStatus",
    "inventory_view",
    "inventory_view_from_dictionary",
    "vocabulary_inventory_view",
    "phoible_inventory_view",
    "phoible_inventory_view_from_source",
    "clts_inventory_view",
    "clts_inventory_view_from_artifacts",
    "clts_inventory_view_from_source",
    "registry_inventory_view",
    "registry_inventory_views",
]
