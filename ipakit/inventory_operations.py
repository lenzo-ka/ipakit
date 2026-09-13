"""Inventory operations with representation-specific observations and capabilities.

``read`` admits one token. ``declared_tokens`` lists registered entries in order;
house composition can admit additional single units. Query syntax and respelling
results belong to each adapter: finite models enumerate an exact inverse relation,
while house respelling returns its declared canonical spelling.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar, runtime_checkable

from ._identity import identity_fingerprint
from .feature_sets import FeatureSets
from .features import FeatureQuery, IPAFeatures
from .finite_model import FeatureBundle, FiniteModel, Realization, Scalar
from .metric import metric_fingerprint
from .segment import Segment

Observation = TypeVar("Observation", covariant=True)
Query = TypeVar("Query", contravariant=True)
Changes = TypeVar("Changes", contravariant=True)
Result = TypeVar("Result", covariant=True)
Admission = Literal["exact-finite", "declared-only", "single-unit"]


@runtime_checkable
class SoundInventory(Protocol[Observation]):
    """Structural read capability; runtime membership does not validate its laws."""

    @property
    def name(self) -> str: ...

    @property
    def identity(self) -> str: ...

    @property
    def declared_tokens(self) -> tuple[str, ...]: ...

    @property
    def admission(self) -> Admission: ...

    def read(self, token: str) -> Observation: ...


@runtime_checkable
class MatchingInventory(Protocol[Query]):
    """A query capability whose argument type is supplied by the representation."""

    def phones_matching(self, query: Query) -> tuple[str, ...]: ...


@runtime_checkable
class RespellingInventory(Protocol[Changes, Result]):
    """An edit capability with an explicit representation-specific result."""

    def respell(self, token: str, changes: Changes) -> Result: ...


def _token(token: str) -> None:
    if not isinstance(token, str) or not token:
        raise ValueError("an inventory token must be a nonempty string")


@dataclass(frozen=True)
class FiniteInventory:
    """Exact typed lookup, matching and exhaustive realization of a FiniteModel.

    Constraints/changes use declared scalar values, including explicit None for
    missing cells. There is no default filling or interpretation of token text.
    Declaration weights remain on their containing declaration, not this adapter.
    """

    model: FiniteModel

    @property
    def name(self) -> str:
        return self.model.name

    @property
    def identity(self) -> str:
        return self.model.identity

    @property
    def declared_tokens(self) -> tuple[str, ...]:
        return tuple(self.model.rows)

    @property
    def admission(self) -> Literal["exact-finite"]:
        return "exact-finite"

    def read(self, token: str) -> FeatureBundle:
        _token(token)
        return self.model.read(token)

    def phones_matching(self, query: Mapping[str, Scalar | None]) -> tuple[str, ...]:
        return self.model.query(query)

    def respell(self, token: str, changes: Mapping[str, Scalar | None]) -> Realization:
        _token(token)
        return self.model.respell(token, changes)


@dataclass(frozen=True)
class CanonicalRespelling:
    """House canonicalization outcome; spelling is None when realization fails.

    This outcome makes no claim to enumerate aliases or all realizations.
    """

    inventory_id: str
    spelling: str | None

    @property
    def status(self) -> Literal["none", "canonical"]:
        return "none" if self.spelling is None else "canonical"


@dataclass(frozen=True)
class HouseInventory:
    """Bind an IPAFeatures instance for strict single-unit operations.

    The caller must keep ``ipa`` unchanged for the adapter's entire lifetime,
    including before binding if its memoized metric fingerprint has been read.
    This precondition is not enforced: IPAFeatures has no mutation-generation
    contract. Construct a fresh IPAFeatures and adapter after declaration changes.
    Identity records effective metric geometry, declared order and admission;
    it is not a digest of every parser alias or a claim of source provenance.

    Queries retain house signed/name syntax and optional default filling.
    Single-unit admission reads the canonical Form with strict parsing and
    requires exactly one segment unit. Boundary and literal residues refuse.
    Select ``declared_only`` when inputs must be exact registered phone keys.
    Respelling accepts a mapping of house string values, carries existing prosody,
    and delegates the canonicalizer; prosody edits are refused by that operation.
    ``declared_only`` limits input admission, not the canonicalizer's output.
    """

    ipa: IPAFeatures = field(repr=False, compare=False)
    declared_only: bool = False
    declared_tokens: tuple[str, ...] = field(init=False)
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.declared_only) is not bool:
            raise ValueError("declared_only must be a bool")
        tokens = tuple(self.ipa.phones)
        object.__setattr__(self, "declared_tokens", tokens)
        object.__setattr__(
            self,
            "identity",
            identity_fingerprint(
                {
                    "format": "house-inventory-operations/1",
                    "geometry": metric_fingerprint(self.ipa, tokens),
                    "declared_tokens": tokens,
                    "admission": self.admission,
                }
            ),
        )

    @property
    def name(self) -> str:
        return "ipakit"

    @property
    def admission(self) -> Literal["declared-only", "single-unit"]:
        return "declared-only" if self.declared_only else "single-unit"

    def read(self, token: str) -> Segment:
        _token(token)
        if self.declared_only and token not in self.declared_tokens:
            raise ValueError(f"{token!r} is outside the declared house inventory")
        units = self.ipa.read(token, strict=True).units
        if len(units) != 1 or units[0].segment is None:
            raise ValueError("an inventory token must contain exactly one segment")
        return units[0].segment

    def phones_matching(
        self, query: FeatureQuery, *, with_defaults: bool = True
    ) -> tuple[str, ...]:
        return tuple(self.ipa.phones_matching(query, with_defaults=with_defaults))

    def respell(self, token: str, changes: Mapping[str, str]) -> CanonicalRespelling:
        self.read(token)
        if not isinstance(changes, Mapping) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in changes.items()
        ):
            raise ValueError("house changes must map feature names to string values")
        return CanonicalRespelling(self.identity, self.ipa.respell(token, **changes))


@dataclass(frozen=True)
class SetInventory:
    """Read-only exact-key adapter over a FeatureSets geometry.

    Labels supply no scalar query/edit schema. A CLTS Snapshot's source, aliases
    and exclusions stay on that snapshot; this adapter carries its geometry only.
    """

    geometry: FeatureSets

    @property
    def name(self) -> str:
        return self.geometry.name

    @property
    def identity(self) -> str:
        return self.geometry.identity

    @property
    def declared_tokens(self) -> tuple[str, ...]:
        return tuple(self.geometry.values)

    @property
    def admission(self) -> Literal["exact-finite"]:
        return "exact-finite"

    def read(self, token: str) -> frozenset[str]:
        _token(token)
        return self.geometry.features(token)
