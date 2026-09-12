"""Declared finite scalar re-encodings, without an implicit model pivot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import prod
from types import MappingProxyType
from typing import Literal

from ._identity import identity_fingerprint
from ._provenance import SourceMetadata
from .finite_model import (
    FeatureBundle,
    FeatureSchema,
    FiniteModel,
    InvalidFeature,
    Scalar,
)


class InvalidTransform(ValueError):
    """A map does not satisfy its declared source/target contract."""


class MissingFeature(ValueError):
    """The explicit complete-input precondition is not satisfied."""


class OutsideImage(ValueError):
    """A valid target-domain bundle is not in the transformation's image."""


def _typed(values: tuple[Scalar, ...]) -> tuple[tuple[type, Scalar], ...]:
    return tuple((type(value), value) for value in values)


@dataclass(frozen=True)
class ScalarCase:
    """One typed scalar and its ordered output tuple."""

    value: Scalar = field(compare=False)
    output: tuple[Scalar, ...] = field(compare=False)
    _key: tuple[tuple[type, Scalar], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", tuple(self.output))
        if any(
            type(value) not in (str, int, bool) for value in (self.value, *self.output)
        ):
            raise InvalidTransform("cases require finite scalar values, not absence")
        object.__setattr__(self, "_key", _typed((self.value, *self.output)))


@dataclass(frozen=True)
class FeatureMap:
    """A complete scalar map into a disjoint ordered group of target fields."""

    source: str
    targets: tuple[str, ...]
    cases: tuple[ScalarCase, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "cases", tuple(self.cases))


@dataclass(frozen=True)
class TransformedBundle:
    """Forward witness retaining both model identities and the operation."""

    source: FeatureBundle
    target: FeatureBundle
    operation_id: str
    provenance: SourceMetadata | None


@dataclass(frozen=True)
class Preimage:
    """Factored full-domain preimage, plus observed inventory spellings.

    Every choice is independent for these scalar maps. Count is the number of
    complete source bundles, not the number of inventory spelling candidates.
    """

    target: FeatureBundle
    source_model_id: str
    operation_id: str
    choices: tuple[tuple[str, tuple[Scalar, ...]], ...] = field(compare=False)
    inventory_candidates: tuple[str, ...]
    _key: tuple[tuple[str, tuple[tuple[type, Scalar], ...]], ...] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        choices = tuple((name, tuple(values)) for name, values in self.choices)
        object.__setattr__(self, "choices", choices)
        object.__setattr__(
            self, "inventory_candidates", tuple(self.inventory_candidates)
        )
        object.__setattr__(
            self, "_key", tuple((name, _typed(values)) for name, values in choices)
        )

    @property
    def count(self) -> int:
        return prod(len(values) for _, values in self.choices)


@dataclass(frozen=True)
class InventoryCollision:
    """Different source bundles mapped to one output, not merely aliases."""

    target: FeatureBundle
    sources: tuple[FeatureBundle, ...]
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class FiniteTransform:
    """A total scalar re-encoding on complete bundles of one bound model.

    Composition and general relational rewrites are deliberately not exposed.
    Domain loss is distinct from observed inventory collisions and from any
    claim about phonetic equivalence or house-model expressivity.
    """

    name: str = field(compare=False)
    source: FiniteModel = field(compare=False)
    target_schema: FeatureSchema = field(compare=False)
    maps: tuple[FeatureMap, ...] = field(compare=False)
    missing: Literal["require-complete"] = field(compare=False)
    provenance: SourceMetadata | None = field(default=None, compare=False)
    identity: str = field(init=False)
    target: FiniteModel = field(init=False, compare=False)
    _groups: Mapping[FeatureBundle, tuple[str, ...]] = field(
        init=False, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "maps", tuple(self.maps))
        if not isinstance(self.name, str) or not self.name:
            raise InvalidTransform("a transform requires a nonempty name")
        if self.missing != "require-complete":
            raise InvalidTransform(
                "only explicit missing='require-complete' is supported"
            )
        sources = tuple(mapping.source for mapping in self.maps)
        targets = tuple(name for mapping in self.maps for name in mapping.targets)
        if len(set(sources)) != len(sources) or set(sources) != set(
            self.source.schema.features
        ):
            raise InvalidTransform("maps must cover every source feature exactly once")
        if len(set(targets)) != len(targets) or set(targets) != set(
            self.target_schema.features
        ):
            raise InvalidTransform("maps must cover every target feature exactly once")
        for mapping in self.maps:
            expected = set(_typed(self.source.schema.domains[mapping.source]))
            actual = [_typed((case.value,))[0] for case in mapping.cases]
            if len(set(actual)) != len(actual) or set(actual) != expected:
                raise InvalidTransform(
                    f"incomplete or duplicate domain cases: {mapping.source!r}"
                )
            for case in mapping.cases:
                if len(case.output) != len(mapping.targets):
                    raise InvalidTransform(
                        "case output width does not match target fields"
                    )
                self.target_schema.validate(
                    dict(zip(mapping.targets, case.output, strict=True))
                )
        object.__setattr__(
            self,
            "identity",
            identity_fingerprint(
                {
                    "format": "finite-transform/1",
                    "name": self.name,
                    "source": self.source.identity,
                    "target-schema": list(self.target_schema.domains.items()),
                    "maps": [
                        {
                            "source": mapping.source,
                            "targets": mapping.targets,
                            "cases": [
                                (case.value, case.output) for case in mapping.cases
                            ],
                        }
                        for mapping in self.maps
                    ],
                    "missing": self.missing,
                    "provenance": (
                        self.provenance.to_dict()
                        if self.provenance is not None
                        else None
                    ),
                }
            ),
        )
        rows = {
            token: self._encode(self.source.read(token)) for token in self.source.rows
        }
        object.__setattr__(
            self,
            "target",
            FiniteModel(self.identity, self.target_schema, rows, self.source.source),
        )
        groups: dict[FeatureBundle, list[str]] = {}
        for token in self.source.rows:
            groups.setdefault(self.target.read(token), []).append(token)
        object.__setattr__(
            self,
            "_groups",
            MappingProxyType(
                {bundle: tuple(tokens) for bundle, tokens in groups.items()}
            ),
        )

    def _encode(self, bundle: FeatureBundle) -> tuple[Scalar, ...]:
        # Reuse the model's public validation, including actual content identity.
        checked = self.source.edit(bundle, {})
        if any(value is None for value in checked.values):
            raise MissingFeature("require-complete refuses absent source feature cells")
        values = dict(zip(self.source.schema.features, checked.values, strict=True))
        output: dict[str, Scalar] = {}
        for mapping in self.maps:
            value = values[mapping.source]
            case = next(
                case
                for case in mapping.cases
                if type(case.value) is type(value) and case.value == value
            )
            output.update(zip(mapping.targets, case.output, strict=True))
        return tuple(output[name] for name in self.target_schema.features)

    def apply(self, bundle: FeatureBundle) -> TransformedBundle:
        """Apply to a validated bound source bundle, including novel edits."""
        target = FeatureBundle(self.target.identity, self._encode(bundle))
        return TransformedBundle(bundle, target, self.identity, self.provenance)

    def decode(self, bundle: FeatureBundle) -> Preimage:
        """Return all factored preimages; reject impossible codes such as 11."""
        checked = self.target.edit(bundle, {})
        if any(value is None for value in checked.values):
            raise MissingFeature("require-complete refuses absent target feature cells")
        values = dict(zip(self.target_schema.features, checked.values, strict=True))
        choices: dict[str, tuple[Scalar, ...]] = {}
        for mapping in self.maps:
            candidates = tuple(
                case.value
                for case in mapping.cases
                if all(
                    type(value) is type(values[name]) and value == values[name]
                    for name, value in zip(mapping.targets, case.output, strict=True)
                )
            )
            if not candidates:
                raise OutsideImage(
                    f"target code has no preimage for {mapping.source!r}"
                )
            choices[mapping.source] = candidates
        return Preimage(
            bundle,
            self.source.identity,
            self.identity,
            tuple((name, choices[name]) for name in self.source.schema.features),
            self._groups.get(bundle, ()),
        )

    @property
    def injective(self) -> bool:
        """Injectivity on complete declared domains, not spelling uniqueness."""
        return all(
            len({_typed(case.output) for case in mapping.cases}) == len(mapping.cases)
            for mapping in self.maps
        )

    def collisions(self) -> tuple[InventoryCollision, ...]:
        """Report observed collapses of distinct source bundles in row order."""
        collisions = []
        for target, tokens in self._groups.items():
            sources = tuple(dict.fromkeys(self.source.read(token) for token in tokens))
            if len(sources) > 1:
                collisions.append(InventoryCollision(target, sources, tuple(tokens)))
        return tuple(collisions)


class BinaryEncoding(StrEnum):
    """Explicit alternative meanings for a ternary-to-binary operation."""

    TWO_PREDICATE = "two-predicate"
    POSITIVE_ONLY = "positive-only"


def ternary_to_binary(
    source: FiniteModel,
    encoding: BinaryEncoding,
    *,
    missing: Literal["require-complete"],
) -> FiniteTransform:
    """Declare one selected encoding; no negative/zero collapse is implicit."""
    if not isinstance(encoding, BinaryEncoding):
        raise InvalidTransform("select a BinaryEncoding explicitly")
    expected = _typed((-1, 0, 1))
    maps = []
    domains: dict[str, tuple[Scalar, ...]] = {}
    for name, domain in source.schema.domains.items():
        if set(_typed(domain)) != set(expected):
            raise InvalidFeature(
                f"feature {name!r} does not have an integer ternary domain"
            )
        targets = (
            (f"{name}:positive", f"{name}:negative")
            if encoding is BinaryEncoding.TWO_PREDICATE
            else (f"{name}:positive",)
        )
        for target in targets:
            domains[target] = (0, 1)
        cases = tuple(
            ScalarCase(
                value,
                (
                    (int(value == 1), int(value == -1))
                    if encoding is BinaryEncoding.TWO_PREDICATE
                    else (int(value == 1),)
                ),
            )
            for value in domain
        )
        maps.append(FeatureMap(name, targets, cases))
    return FiniteTransform(
        f"ternary/{encoding.value}/1",
        source,
        FeatureSchema(domains),
        tuple(maps),
        missing,
    )
