"""Data models for IPA feature handling."""

from __future__ import annotations

import functools
from collections.abc import Iterator, Mapping
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
    # Combining values are spelled as their ordered components joined by
    # the combiner (bilabial^velar): the name IS the expansion. They are
    # valid values but hold NO position on the ordinal scale - an overlap
    # is not a point on the continuum - and compare by expansion. Friendly
    # display names (labial-velar) are value aliases, resolved everywhere.
    #
    # The glyph is "^", not "+", because "+" is already the positive
    # value of every binary feature. Sharing one glyph made "+" parse as a
    # combining spelling: expand("+") returned two empty components, and
    # _value_index dropped "+" from its own scale. "^" is ASCII, appears
    # nowhere else in the data, and reads as the conjunction it is: a
    # double articulation is both places at once.
    COMBINER = "^"
    value_aliases: dict[str, str] = field(default_factory=dict)
    # The reference-frame axis this ordinal ascends (+x lips->glottis,
    # +y jaw->palate, +constriction, +t, ...), declared in the data.
    axis: str | None = None
    # Values that hold no position on the continuum (silence on the
    # constriction axis: absence of signal, equidistant from every value).
    offscale: frozenset[str] = field(default_factory=frozenset)
    # Tract coordinates per value (arc along the midline, offset from it),
    # declared in the data; see ipakit.tract.
    coordinates: dict[str, dict[str, float]] = field(default_factory=dict)
    # Default active articulator per value: place names the constriction
    # target, this names the organ that gets there.
    articulators: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Feature({self.name!r}, type={self.type!r}, values={self.values!r})"

    @functools.cached_property
    def values_set(self) -> set[str]:
        return set(self.values)

    @functools.cached_property
    def _value_index(self) -> dict[str, int]:
        """value -> scale index, for O(1) ordinal distance.

        Combining values (bilabial^velar) are skipped: an overlap is not a
        point on the continuum, so it must not pad the scale between its
        neighbours.
        """
        scale = [
            v for v in self.values if self.COMBINER not in v and v not in self.offscale
        ]
        return {v: i for i, v in enumerate(scale)}

    @functools.cached_property
    def _anchor_axis(self) -> str | None:
        """The coordinate this feature's values are anchored on, if any."""
        for attr in ("arc", "offset"):
            if any(attr in coords for coords in self.coordinates.values()):
                return attr
        return None

    @functools.cached_property
    def _anchor_span(self) -> float:
        attr = self._anchor_axis
        if attr is None:
            return 0.0
        vals = [c[attr] for c in self.coordinates.values() if attr in c]
        return (max(vals) - min(vals)) if len(vals) > 1 else 0.0

    def _anchor_distance(self, v1: str, v2: str) -> float | None:
        """Distance between two values by their physical anchors, scaled to
        the feature's own span so it stays in [0, 1]. None if either value
        is unanchored (the feature then falls back to scale index)."""
        attr = self._anchor_axis
        if attr is None or not self._anchor_span:
            return None
        c1 = self.coordinates.get(self.value_aliases.get(v1, v1), {}).get(attr)
        c2 = self.coordinates.get(self.value_aliases.get(v2, v2), {}).get(attr)
        if c1 is None or c2 is None:
            return None
        return min(abs(c1 - c2) / self._anchor_span, 1.0)

    def _malformed(self, value: str) -> ValueError:
        return ValueError(
            f"malformed value {value!r} for feature {self.name!r}: a value is "
            f"a non-empty name, or non-empty names joined by {self.COMBINER!r}"
        )

    def _components(self, value: str) -> tuple[str, ...]:
        """A value's alias resolved and the result split on the combiner,
        with the spelling checked for structure. Every component must be
        non-empty: "", "^", "a^" and "a^^b" name nothing under any data,
        so they are refused rather than answered."""
        resolved = self.value_aliases.get(value, value)
        if self.COMBINER not in resolved:
            if not resolved:
                raise self._malformed(value)
            return (resolved,)
        parts = tuple(resolved.split(self.COMBINER))
        if not all(parts):
            raise self._malformed(value)
        return parts

    def expand(self, value: str) -> tuple[str, ...]:
        """A value's components: the value itself, or its ordered parts for
        a combining value (``bilabial^velar`` -> ``(bilabial, velar)``).

        Aliases resolve per component, not only on the whole spelling, so
        ``labial-velar`` and ``labial-velar^palatal`` alike expand to
        declared components. (Resolving only the whole string left an
        alias standing unresolved inside the combination, and the caller
        then compared a name the data never declares.)

        Generative: any well-formed ``^``-joined spelling expands,
        declared or not. Raises :class:`ValueError` on a *structurally*
        malformed spelling -- one with an empty component. That is the
        line: an undeclared component is a question about this data, which
        comparison already answers with maximal distance, but an empty
        component is not a value under any data.
        """
        parts = self._components(value)
        if len(parts) == 1:
            return parts
        # One nesting level: an alias names a declared value, so a
        # component's alias expands at most once more. The bound also
        # keeps a cyclic alias in the data from recursing forever.
        return tuple(sub for part in parts for sub in self._components(part))

    def combine(self, values: set[str] | tuple[str, ...]) -> str:
        """The canonical combining spelling for a set of values: components
        ordered by their scale position (declaration order as fallback),
        joined by ``^``. One spelling per combination -- palatal^alveolar
        cannot occur, only alveolar^palatal.

        Members are expanded first, so an alias (``labial-velar``) or an
        already-combined member contributes its components rather than
        being spelled into the result verbatim; the answer is therefore
        always a spelling :meth:`expand` reads back. Raises
        :class:`ValueError` on a malformed member, and on no values at all
        -- there is no combination of nothing to name.
        """
        components = {c for v in values for c in self.expand(v)}
        if not components:
            raise ValueError(
                f"combine() needs at least one value for feature {self.name!r}"
            )

        def position(v: str) -> tuple[int, str]:
            idx = self._value_index.get(v)
            if idx is not None:
                return (idx, v)
            try:
                return (self.values.index(v), v)
            except ValueError:
                return (len(self.values), v)

        unique = sorted(components, key=position)
        if len(unique) == 1:
            return unique[0]
        return self.COMBINER.join(unique)

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
        # A combining spelling (and an empty one, which is malformed) goes
        # through expand, which carries the per-component alias resolution
        # and the structure check: a malformed value is refused rather
        # than answered with a number built from a phantom component. A
        # plain value skips it -- this is the metric's hottest loop.
        if isinstance(v1, str):
            v1 = self.value_aliases.get(v1, v1)
            if self.COMBINER in v1 or not v1:
                v1 = self.expand(v1)
        if isinstance(v2, str):
            v2 = self.value_aliases.get(v2, v2)
            if self.COMBINER in v2 or not v2:
                v2 = self.expand(v2)
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
        # Anchored features measure distance in physical tract space
        # rather than by scale index: the step between two values is what
        # anatomy says it is, not 1/(n-1). This keeps place and backness
        # commensurable (both are positions on one arc) and makes existing
        # distances stable when a value is added to the inventory.
        if (anchored := self._anchor_distance(v1, v2)) is not None:
            return anchored
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
    """A phone with its features.

    ``features`` is read-only: the module API is backed by one cached
    IPAFeatures instance, so a write here would corrupt the inventory
    every later call reads.
    """

    symbol: str
    features: Mapping[str, str]

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
