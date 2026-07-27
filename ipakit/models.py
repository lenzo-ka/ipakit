"""Data models for IPA feature handling."""

from __future__ import annotations

import functools
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self


@dataclass
class Feature:
    """A phonological feature definition.

    ``type`` is the declared value-set type from the XML (e.g. ``"ordinal"``);
    it drives :attr:`is_ordinal` (scale distance) vs categorical comparison.
    :attr:`is_binary` is a *separate*, value-derived notion -- true iff the
    values are exactly ``{"+", "-"}`` -- and does not depend on ``type``.
    """

    name: str
    values: list[str]  # Ordered - defines dimensional scale for ordinal
    default: str | None = None
    type: str = "ordinal"  # declared value-set type (from XML); see is_ordinal
    desc: str | None = None  # Brief description
    # Values that are display names over several true values (a combined
    # place like labial-velar over its two articulations). They are valid
    # values but hold NO position on the ordinal scale - an overlap is not
    # a point on the continuum - and compare by expansion.
    expansions: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Feature({self.name!r}, type={self.type!r}, values={self.values!r})"

    @functools.cached_property
    def values_set(self) -> set[str]:
        return set(self.values)

    @functools.cached_property
    def _value_index(self) -> dict[str, int]:
        """value -> scale index, for O(1) ordinal distance.

        Expanding values (combined places) are skipped: they are display
        names over several true values, not points on the continuum, so
        they must not pad the scale between their neighbours.
        """
        scale = [v for v in self.values if v not in self.expansions]
        return {v: i for i, v in enumerate(scale)}

    @property
    def is_binary(self) -> bool:
        return self.values_set == {"+", "-"}

    @property
    def is_ordinal(self) -> bool:
        return self.type == "ordinal"

    def value_distance(
        self,
        v1: str | tuple[str, ...] | None,
        v2: str | tuple[str, ...] | None,
    ) -> float:
        """Compute distance between two values of this feature.

        For ordinal features, uses scale distance based on declaration order.
        For categorical/binary features, returns 0 if same, 1 if different.
        Either side may be a tuple of values (a multi-valued feature, e.g. a
        double articulation's places): the distance is then the directional
        best-match mean, max of the two directions.
        """
        if isinstance(v1, str) and v1 in self.expansions:
            v1 = self.expansions[v1]
        if isinstance(v2, str) and v2 in self.expansions:
            v2 = self.expansions[v2]
        if isinstance(v1, tuple) or isinstance(v2, tuple):
            c1 = v1 if isinstance(v1, tuple) else (v1,)
            c2 = v2 if isinstance(v2, tuple) else (v2,)
            if not c1 or not c2:
                return 1.0

            def direction(
                src: tuple[str | None, ...], dst: tuple[str | None, ...]
            ) -> float:
                return sum(
                    min(self.value_distance(a, b) for b in dst) for a in src
                ) / len(src)

            return max(direction(c1, c2), direction(c2, c1))
        if v1 == v2:
            return 0.0
        if v1 is None or v2 is None:
            return 1.0
        if self.is_ordinal:
            idx = self._value_index
            if v1 in idx and v2 in idx:
                # Guard against a single-value ordinal feature (span == 0).
                span = len(self._value_index) - 1
                if span <= 0:
                    return 0.0
                return abs(idx[v1] - idx[v2]) / span
            return 1.0
        return 1.0


@dataclass
class Phone:
    """A phone with its features."""

    symbol: str
    features: dict[str, str]

    def __repr__(self) -> str:
        manner = self.features.get("manner", "?")
        place = self.features.get("place", "")
        return f"Phone({self.symbol!r}, {manner}" + (f", {place})" if place else ")")

    def get(self, feature: str, default: str | None = None) -> str | None:
        return self.features.get(feature, default)

    def __getitem__(self, feature: str) -> str:
        return self.features[feature]

    def __contains__(self, feature: str) -> bool:
        return feature in self.features


@dataclass
class PhoneMapping:
    """A single IPA to CMU mapping."""

    cmu: str
    ipa: str
    stress: set[int]  # Valid stress levels: {0, 1, 2} or subset


@dataclass
class Phoneset:
    """A custom phoneset (list of phones)."""

    name: str
    phones: list[str]

    @functools.cached_property
    def _phones_set(self) -> frozenset[str]:
        return frozenset(self.phones)

    @classmethod
    def from_file(cls, path: Path) -> Self:
        """Load phoneset from text file (one phone per line)."""
        path = Path(path)
        phones = [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and line.strip() not in ("SIL", "␣")
        ]
        return cls(name=path.stem, phones=phones)

    @classmethod
    def from_list(cls, phones: list[str], name: str = "custom") -> Self:
        """Build a Phoneset from a list of phone strings."""
        return cls(name=name, phones=phones)

    def __contains__(self, phone: str) -> bool:
        return phone in self._phones_set

    def __iter__(self) -> Iterator[str]:
        return iter(self.phones)

    def __len__(self) -> int:
        return len(self.phones)
