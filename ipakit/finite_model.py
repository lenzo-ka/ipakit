"""Finite feature inventories, independent of any preferred phonetic model.

These are schema tables, not occurrence graphs. The ternary declaration codec
also supplies the existing comparison factory; no house-IPA conversion occurs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from ._identity import identity_fingerprint
from ._provenance import SourceMetadata

Scalar = str | int | bool


class InvalidFeature(ValueError):
    """A feature name or value is outside the declared schema."""


class ModelMismatch(ValueError):
    """A bundle belongs to a different model/content identity."""


class MissingToken(KeyError):
    """An input token is absent from the finite inventory."""


@dataclass(frozen=True)
class FeatureSchema:
    """Ordered finite domains; None denotes a missing cell, never domain zero."""

    domains: Mapping[str, tuple[Scalar, ...]]

    def __post_init__(self) -> None:
        copied = {name: tuple(domain) for name, domain in self.domains.items()}
        if not copied:
            raise InvalidFeature("a schema must declare at least one feature")
        for name, domain in copied.items():
            if not isinstance(name, str) or not name:
                raise InvalidFeature("feature names must be nonempty strings")
            if not domain or any(
                type(value) not in (str, int, bool) for value in domain
            ):
                raise InvalidFeature(
                    f"feature {name!r} requires a finite scalar domain"
                )
            if len({(type(value), value) for value in domain}) != len(domain):
                raise InvalidFeature(f"feature {name!r} has duplicate domain values")
        object.__setattr__(self, "domains", MappingProxyType(copied))

    @property
    def features(self) -> tuple[str, ...]:
        return tuple(self.domains)

    def validate(self, constraints: Mapping[str, Scalar | None]) -> None:
        """Validate partial constraints/edits; absence is an explicit value."""
        for name, value in constraints.items():
            if name not in self.domains:
                raise InvalidFeature(f"undeclared feature: {name!r}")
            if value is not None and not any(
                type(value) is type(candidate) and value == candidate
                for candidate in self.domains[name]
            ):
                raise InvalidFeature(f"feature {name!r} has invalid value: {value!r}")


@dataclass(frozen=True)
class FeatureBundle:
    """A complete ordered bundle bound to a model's content identity."""

    model_id: str
    values: tuple[Scalar | None, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))


@dataclass(frozen=True)
class Realization:
    """Exact inverse relation, including zero and multiple candidates."""

    bundle: FeatureBundle
    candidates: tuple[str, ...]
    source: SourceMetadata | None

    @property
    def status(self) -> Literal["none", "unique", "ambiguous"]:
        if not self.candidates:
            return "none"
        return "unique" if len(self.candidates) == 1 else "ambiguous"


@dataclass(frozen=True)
class FiniteModel:
    """Immutable inventory; tokens are opaque and declaration order is retained.

    Direct construction has no Unicode normalization policy. A codec may impose
    one on its own input. Domain types participate in validation and identity.
    """

    name: str
    schema: FeatureSchema
    rows: Mapping[str, tuple[Scalar | None, ...]]
    source: SourceMetadata | None = None
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("a model requires a nonempty name")
        copied = {token: tuple(values) for token, values in self.rows.items()}
        for token, values in copied.items():
            if not isinstance(token, str) or not token:
                raise ValueError("token keys must be nonempty strings")
            self._validate_values(values)
        object.__setattr__(self, "rows", MappingProxyType(copied))
        object.__setattr__(
            self,
            "identity",
            identity_fingerprint(
                {
                    "format": "finite-model/1",
                    "name": self.name,
                    "schema": [
                        (name, domain) for name, domain in self.schema.domains.items()
                    ],
                    "rows": list(copied.items()),
                    "source": (
                        self.source.to_dict() if self.source is not None else None
                    ),
                }
            ),
        )

    def _validate_values(self, values: tuple[Scalar | None, ...]) -> None:
        if len(values) != len(self.schema.features):
            raise InvalidFeature("bundle width does not match schema")
        self.schema.validate(dict(zip(self.schema.features, values, strict=True)))

    def _validate_bundle(self, bundle: FeatureBundle) -> None:
        if bundle.model_id != self.identity:
            raise ModelMismatch("bundle belongs to a different model identity")
        self._validate_values(bundle.values)

    def read(self, token: str) -> FeatureBundle:
        """Read one exact opaque token, without parser or IPA fallback."""
        try:
            values = self.rows[token]
        except KeyError as error:
            raise MissingToken(token) from error
        return FeatureBundle(self.identity, values)

    def query(self, constraints: Mapping[str, Scalar | None]) -> tuple[str, ...]:
        """Return declaration-ordered tokens satisfying partial constraints."""
        constraints = dict(constraints)
        self.schema.validate(constraints)
        positions = {name: index for index, name in enumerate(self.schema.features)}
        return tuple(
            token
            for token, values in self.rows.items()
            if all(
                type(values[positions[name]]) is type(value)
                and values[positions[name]] == value
                for name, value in constraints.items()
            )
        )

    def edit(
        self, bundle: FeatureBundle, changes: Mapping[str, Scalar | None]
    ) -> FeatureBundle:
        """Validate an edit; realization is a separate, possibly empty relation."""
        self._validate_bundle(bundle)
        changes = dict(changes)
        self.schema.validate(changes)
        return FeatureBundle(
            self.identity,
            tuple(
                changes.get(name, value)
                for name, value in zip(self.schema.features, bundle.values, strict=True)
            ),
        )

    def realize(self, bundle: FeatureBundle) -> Realization:
        """Return all exact complete-bundle spellings; never pick a first row."""
        self._validate_bundle(bundle)
        candidates = self.query(
            dict(zip(self.schema.features, bundle.values, strict=True))
        )
        return Realization(bundle, candidates, self.source)

    def respell(self, token: str, changes: Mapping[str, Scalar | None]) -> Realization:
        """Read, edit, and realize a finite inventory entry, preserving ambiguity."""
        return self.realize(self.edit(self.read(token), changes))
