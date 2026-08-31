"""Immutable primitives for model-declared, structurally timed graphs.

This module deliberately has no profile vocabulary.  It exists below public
construction APIs so profiles can share addressing and validation laws without
making those laws depend on a spelling system.  Roots are declared one layer
up, on :class:`ipakit._containment_projection.ContainmentProjectionInput`, and
may be empty; root-reachability diagnostics belong to higher profile lanes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[
    str, JsonValue
]
type FrozenValue = object

_NODE_STRUCTURAL_KEYS = frozenset({"gaps"})


class GraphValidationError(ValueError):
    """Identify graph-contract failures separately from ordinary API mistakes."""


class EndpointKind(StrEnum):
    COARSE_TICK = "coarse-tick"
    REFINED_GAP = "refined-gap"
    EVENT = "event"


@dataclass(frozen=True)
class FeatureDeclaration:
    name: str

    def __post_init__(self) -> None:
        _validate_name(self.name, "feature")


@dataclass(frozen=True)
class TierDeclaration:
    name: str
    features: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _validate_name(self.name, "tier")


@dataclass(frozen=True)
class RelationDeclaration:
    name: str
    ordered: bool = True
    acyclic: bool = False
    source_tiers: frozenset[str] | None = None
    target_tiers: frozenset[str] | None = None
    source_kinds: frozenset[EndpointKind] = frozenset({EndpointKind.EVENT})
    target_kinds: frozenset[EndpointKind] = frozenset({EndpointKind.EVENT})
    source_arity: tuple[int, int | None] = (1, None)
    target_arity: tuple[int, int | None] = (1, None)
    allow_empty_source: bool = False
    allow_empty_target: bool = False
    semantic_precedence: bool = False
    containment: bool = False
    choice: bool = False
    member_of: str | None = None

    def __post_init__(self) -> None:
        _validate_name(self.name, "relation")
        _validate_arity(self.source_arity, "source")
        _validate_arity(self.target_arity, "target")
        if self.containment and not self.acyclic:
            raise GraphValidationError("containment relation requires acyclic=True")
        if self.member_of is not None and self.target_arity != (1, 1):
            raise GraphValidationError("member_of relation requires target arity 1")


@dataclass(frozen=True)
class Declarations:
    tiers: tuple[TierDeclaration, ...]
    features: tuple[FeatureDeclaration, ...]
    relations: tuple[RelationDeclaration, ...]
    closed: bool = True
    _tier_by_name: Mapping[str, TierDeclaration] = field(
        init=False, repr=False, compare=False
    )
    _relation_by_name: Mapping[str, RelationDeclaration] = field(
        init=False, repr=False, compare=False
    )
    _tier_order: Mapping[str, int] = field(init=False, repr=False, compare=False)
    _feature_names: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _unique((item.name for item in self.tiers), "tier declaration")
        _unique((item.name for item in self.features), "feature declaration")
        _unique((item.name for item in self.relations), "relation declaration")
        feature_names = {item.name for item in self.features}
        relation_names = {item.name for item in self.relations}
        if any(tier.name in _NODE_STRUCTURAL_KEYS for tier in self.tiers):
            raise GraphValidationError("tier name is reserved for graph structure")
        for tier in self.tiers:
            if not tier.features <= feature_names:
                raise GraphValidationError("tier permits an undeclared feature")
        for relation in self.relations:
            if (
                relation.member_of is not None
                and relation.member_of not in relation_names
            ):
                raise GraphValidationError("member_of names an undeclared relation")
        object.__setattr__(
            self,
            "_tier_by_name",
            MappingProxyType({item.name: item for item in self.tiers}),
        )
        object.__setattr__(
            self,
            "_relation_by_name",
            MappingProxyType({item.name: item for item in self.relations}),
        )
        object.__setattr__(
            self,
            "_tier_order",
            MappingProxyType(
                {item.name: index for index, item in enumerate(self.tiers)}
            ),
        )
        object.__setattr__(self, "_feature_names", frozenset(feature_names))

    def tier(self, name: str) -> TierDeclaration | None:
        return self._tier_by_name.get(name)

    def relation(self, name: str) -> RelationDeclaration | None:
        return self._relation_by_name.get(name)


@dataclass(frozen=True, order=True)
class Position:
    tick: int
    gap: int = 0


@dataclass(frozen=True)
class RefinedSpan:
    start: str
    end: str


@dataclass(frozen=True)
class Timing:
    start: float
    duration: float


@dataclass(frozen=True)
class Event:
    features: Mapping[str, FrozenValue]
    duration: int | None = None
    span: RefinedSpan | None = None
    timing: Timing | None = None
    durable_id: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.duration == 1:
            object.__setattr__(self, "duration", None)
        object.__setattr__(
            self,
            "features",
            MappingProxyType(
                {
                    name: _freeze(cast(JsonValue, value))
                    for name, value in self.features.items()
                }
            ),
        )
        if self.duration is not None and self.span is not None:
            raise GraphValidationError("span and duration are mutually exclusive")

    @property
    def structural_duration(self) -> int | None:
        return (
            None
            if self.span is not None
            else (1 if self.duration is None else self.duration)
        )


@dataclass(frozen=True)
class EventGroup:
    tier: str
    events: tuple[Event, ...]


@dataclass(frozen=True)
class ClockNode:
    gap_count: int = 1
    groups: tuple[EventGroup, ...] = ()


@dataclass(frozen=True)
class Relation:
    sources: tuple[str, ...]
    name: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedReference:
    pointer: str
    kind: EndpointKind
    tick: int
    gap: int | None = None
    tier: str | None = None
    event: Event | None = None


def _validate_name(name: str, kind: str) -> None:
    if not name:
        raise GraphValidationError(f"{kind} name must not be empty")


def _validate_arity(arity: tuple[int, int | None], side: str) -> None:
    low, high = arity
    if low < 0 or (high is not None and high < low):
        raise GraphValidationError(f"invalid {side} arity")


def _unique(names: Iterable[str], kind: str) -> None:
    values = list(names)
    if len(values) != len(set(values)):
        raise GraphValidationError(f"duplicate {kind}")


def _pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/") or pointer == "/":
        raise GraphValidationError("malformed JSON Pointer reference")
    raw = pointer[1:].split("/")
    for part in raw:
        index = 0
        while index < len(part):
            if part[index] == "~" and (
                index + 1 == len(part) or part[index + 1] not in "01"
            ):
                raise GraphValidationError("malformed JSON Pointer reference")
            index += 2 if part[index] == "~" else 1
    return [part.replace("~1", "/").replace("~0", "~") for part in raw]


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _freeze(value: object) -> FrozenValue:
    """Freeze JSON containers while preserving profile-owned scalar values.

    Profiles may store immutable domain objects such as ``Segment``.  Their
    value codecs remain authoritative about whether those opaque values have a
    valid wire representation.
    """
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return MappingProxyType({name: _freeze(item) for name, item in value.items()})
    return value


def _thaw(value: FrozenValue) -> JsonValue:
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Mapping):
        return {name: _thaw(value[name]) for name in sorted(value)}
    return cast(JsonValue, value)
