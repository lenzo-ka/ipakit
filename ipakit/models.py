"""Data models for IPA feature handling."""

from __future__ import annotations

import functools
from collections.abc import Iterator, Mapping, Sequence
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
    # The unmarked interior of an ordinal unit scale. Unlike ``default``,
    # this is not filled into segment feature bundles.
    center: str | None = None
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
    # A sequence-valued feature states a *trajectory*: its values are its
    # declared values joined by the sequencer, read left to right as time
    # order. `tone="low>high"` is one unit's pitch moving from low to
    # high, which is what a contour is. The glyph is ">" because it reads
    # as "then", it appears nowhere else in the data, and it is neither
    # "^" (simultaneity, the opposite claim) nor a space (a value inside
    # a bracketed query is one token).
    SEQUENCER = ">"
    # Whether this feature's values may be sequences, declared in the data.
    sequence: bool = False
    # For a feature whose values name a *move* along another feature's
    # scale (`contour` over `tone`): the scale moved along, and the value
    # naming each sign of the move. Declared, so no direction table stands
    # in Python.
    over: str | None = None
    moves: dict[str, str] = field(default_factory=dict)
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
    # Value -> how that value's constriction is shaped, when the data says.
    # "median" means the articulator closes toward the tract axis rather than
    # toward a wall; `offset` models the one-sided case. Rendering geometry.
    apertures: dict[str, str] = field(default_factory=dict)
    # View-neutral lip controls declared per feature value.  Kept beside the
    # other rendering coordinates and never consulted by the metric.
    lip_dofs: dict[str, dict[str, float]] = field(default_factory=dict)
    # Contribution mode a mark stating this feature makes (docs/ties.md),
    # declared in the data. None means the mode vocabulary's default.
    mode: str | None = None
    # For a secondary articulation (``mode="secondary"``): the place its
    # positive value constricts at, so the metric can carry the
    # articulation as a weighted place component rather than as a key.
    place: str | None = None
    # A feature whose stated presence makes the tract-x constriction
    # unlocalizable: the segment constricts, but at no single point the
    # evidence supports (a rhotacized nucleus -- docs/design/
    # vowel-constriction.md §6). Declared in the data as
    # constriction="unlocalized"; the metric withholds the tract-x term
    # for such a segment rather than asserting a position or a maximal
    # difference. None means the ordinary case: the constriction has a
    # place the reading locates.
    constriction: str | None = None
    # The feature this one takes its value set from, declared in the data.
    # Two features naming the same tract locations must not be two
    # declarations of where those locations are: the values, their
    # aliases and their coordinates are the named feature's, copied at
    # load, so the borrower and the source cannot come to disagree. A
    # feature declaring this declares no values of its own.
    vocabulary: str | None = None
    # The values of this feature that own their bare spelling, declared in
    # the data. Several features may declare a value of the same name --
    # ``nasal`` is a manner, a release phase and an approach phase -- and a
    # query naming one bare has to resolve to exactly one of them. Whichever
    # declares ``bare`` wins the plain term; the others stay reachable as
    # ``feature=value``. Where none declares it the term is contested and
    # refused, which is the point: the alternative is that a bare term means
    # whichever feature ``ipa.xml`` happens to declare first, silently, and
    # reordering the file changes what a rule does.
    bare: frozenset[str] = field(default_factory=frozenset)
    # Manner classes whose descriptions read this feature out; empty means
    # every class. ``channel`` places the airflow channel within a
    # constriction and a vowel has none; ``rhotacized`` is a vowel color
    # and ``retroflex`` the consonant tongue shape.
    applies: frozenset[str] = field(default_factory=frozenset)
    # Value -> the word a description uses for it, declared in the data.
    # An unlabeled value is not read out at all (the unremarkable side of
    # a binary, ``channel=flat``). Distinct from an alias, which is a
    # synonym a reader may write: `plosive` should not print as `stop`.
    labels: dict[str, str] = field(default_factory=dict)
    # Natural classes declared over this feature's values (the obstruent
    # manners), so a class is a property of the values rather than a set
    # standing in Python.
    value_classes: dict[str, frozenset[str]] = field(default_factory=dict)

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
        neighbors.
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

    def steps(self, value: str) -> tuple[str, ...]:
        """A sequence value's elements, in time order.

        ``steps("low>high")`` is ``("low", "high")`` and ``steps("high")``
        is ``("high",)``, so a caller need not ask first whether it holds
        one element or several. A feature the data does not declare
        ``sequence`` never holds a sequence, and its values come back
        whole -- a ``>`` in such a value is part of the name.
        """
        if not self.sequence or self.SEQUENCER not in value:
            return (value,)
        parts = tuple(self.value_aliases.get(p, p) for p in value.split(self.SEQUENCER))
        if not all(parts):
            raise ValueError(
                f"malformed sequence {value!r} for feature {self.name!r}: a "
                f"sequence is non-empty names joined by {self.SEQUENCER!r}"
            )
        return parts

    def sequenced(self, values: Sequence[str]) -> str:
        """The sequence spelling of an ordered run of values."""
        return self.SEQUENCER.join(values)

    def move(self, scale: Feature, start: str, end: str) -> str | None:
        """The value naming the move from ``start`` to ``end`` on ``scale``.

        ``contour`` declares ``over="tone"`` and gives each of its values
        the sign of the move it names, so the direction between two tone
        levels is read off the declaration rather than off a table of
        directions kept here. Returns ``None`` where either level holds no
        position on the scale, or where nothing names that sign.
        """
        first, second = scale._value_index.get(start), scale._value_index.get(end)
        if first is None or second is None:
            return None
        sign = "+" if second > first else "-" if second < first else "0"
        for name, declared in self.moves.items():
            if declared == sign:
                return name
        return None

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


@functools.lru_cache(maxsize=1)
def _silence_spellings() -> frozenset[str]:
    """The strings a phoneset file may write silence with.

    ``␣`` is not spelled here. It is a registered phone and what makes it
    silence is declared -- ``manner="silence"`` -- so the set is read off
    that, and a second silence phone would be dropped by the same rule
    rather than slipping in as a sound. ``SIL`` is written out because it
    is the aligner-file label for the same thing (HTK, Kaldi) and is
    declared by nothing.

    The import is deferred rather than made a field on :class:`Phoneset`,
    and that is the shape of the class, not an oversight: ``features``
    imports this module, so an inventory held here would invert the
    dependency, and a ``Phoneset`` is a name and a list of strings that
    accepts arbitrary, possibly non-IPA phone labels -- it has no
    inventory to check them against and is not supposed to. Same pattern
    and same reason as ``mapper._stress_markers``.
    """
    from .features import IPAFeatures

    ipa = IPAFeatures()
    return frozenset({"SIL"}) | {
        symbol
        for symbol, phone in ipa.phones.items()
        if (phone.features or {}).get("manner") == "silence"
    }


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
        """Load phoneset from text file (one phone per line).

        Silence is dropped: a phoneset is an inventory of sounds and the
        silence label an aligner writes is not one of them. Which strings
        spell it is :func:`_silence_spellings`.
        """
        path = Path(path)
        phones = [
            stripped
            for line in path.read_text().splitlines()
            if (stripped := line.strip()) and stripped not in _silence_spellings()
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
