"""A transcription as written, before anything is projected away.

:func:`ipakit.segments` answers "what sounds are in this?" and to do so
it drops what is not a sound: the word mark, the syllable break, the
space. That is the right answer to that question, and it is a
**projection** -- ``to_ipa(segments("#kæt.dɒɡ#"))`` is ``"kætdɒɡ"``. The
projection is not marked as one, so a caller who needed the whole
transcription has already lost it by the time they notice.

:class:`Form` is the unprojected reading. It carries every position the
transcription had, sounds and boundaries alike, and spells back out
byte-identical **for well-formed input**. Everything narrower is
reachable from it *by name*:

    form = Form.parse("#kæt.dɒɡ#")
    form.to_ipa()      # '#kæt.dɒɡ#'  -- nothing dropped
    form.segments      # (k, æ, t, d, ɒ, ɡ)  -- boundaries dropped
    form.phones        # ('k','æ','t','d','ɒ','ɡ')  -- identity names
    form.boundaries    # where the dropped ones were

The point is not that projections are bad. It is that each one should
say what it drops, and that dropping should happen where a caller asks
for it rather than on the way in. A projection here is also reversible:
:attr:`Form.boundaries` records where each boundary sat in the segmental
sequence, so :meth:`Form.rebuild` can put a collapsed reading back
together. That matters for more than tidiness -- the syllable break is
what ``normalize_stress_to_syllable`` reads to turn nucleus-marked
stress back into syllable-marked stress, so a form that has been
collapsed and cannot be rebuilt has lost its stress positions.

Three levels, and the difference between them is the whole module:

``to_ipa``
    Everything. Boundaries, prosody, modifiers. Round-trips.
``segments``
    Sounds only. Prosody still rides on each unit; boundaries are gone.
``phones``
    Identity names. ``ˈa`` and ``aː`` are both ``a``, because prosodic
    features live on the unit and not in the bundle (docs/ties.md).

Carry the widest one you can, and collapse at the point of use.

:meth:`Form.tree` reads the levels off ``<feature name="level">`` rather
than naming them, so the ladder is data: ``syllable``, ``word``,
``phrase``, ``utterance`` today, and a further value extends the tree
with no change here. Each node also records **which delimiter supplied
each end of its span** -- ``None`` meaning the form's own edge -- so
``#kæt#`` and ``kæt`` give the same tree and differ only in whether the
brackets were written (:attr:`Node.asserted`). The delimiters stay out of
:attr:`Form.units`, because that sequence is the faithful read of what
was *spelled* and the rule engine's site indices point into it.

:class:`Interval` is the one thing on a form that is **not** a read of
that sequence. A span on a declared tier -- a mora, a morph, a syllable
crossing a word boundary -- is delimited by no glyph, so it cannot be
projected out of the units and is carried beside them instead. It is not
spelled either, which is why ``to_ipa`` round-trips the string and not
the whole form. What it buys is the thing :meth:`Form.tree` cannot state:
an interval makes no claim to nest, so two of them may overlap with
neither containing the other, which is what enchaînement is.
"""

from __future__ import annotations

import dataclasses
import json
import math
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar, cast

from .constants import ZERO_CLASS
from .segment import state_mark_value

if TYPE_CHECKING:  # pragma: no cover
    from ._containment_projection import ContainmentProjection
    from .features import IPAFeatures
    from .segment import Segment

#: Keys on a declaration that name a symbol rather than describe a sound.
_METADATA = frozenset({"class", "href", "xsampa"})
_JSON_VERSION = 2
_JSON_TYPE = "ipakit.form"
_VIEW_ABSENT = object()
_EMPTY_MAPPING: Mapping[str, str] = MappingProxyType({})
_T = TypeVar("_T")


class FormProjectionError(ValueError):
    """A stored graph cannot reproduce Form's compatibility coordinates."""


class FormBuilder:
    """Build an IPA :class:`Form` incrementally without exposing graph internals.

    Event handles returned while editing are intentionally opaque.  Canonical
    JSON Pointer paths become observable only on the immutable built form.
    """

    def __init__(self, features: IPAFeatures | None = None) -> None:
        from ._ipa_graph import declarations
        from ._tiergraph_builder import GraphBuilder

        self.features = _default(features)
        self._builder = GraphBuilder(declarations(self.features))
        self._compatibility_unit_count = 0

    def begin(
        self,
        tier: str,
        features: Mapping[str, Any] | None = None,
        *,
        start: Any | None = None,
    ) -> Any:
        """Begin an event whose structural extent ends with :meth:`end`."""
        return self._builder.begin(tier, features or {}, start=start)

    def end(self, handle: Any, end: Any | None = None) -> None:
        """Close an event opened by :meth:`begin`."""
        self._builder.end(handle, end)

    @property
    def current_tick(self) -> int:
        """The next input-clock position."""
        return self._builder.current_tick

    def add_event(
        self,
        tier: str,
        features: Mapping[str, Any] | None = None,
        *,
        start: int | None = None,
        duration: int = 1,
    ) -> Any:
        """Add an occurrence with arbitrary features permitted by ``tier``."""
        return self._builder.add_event(
            tier,
            self.current_tick if start is None else start,
            features or {},
            duration=duration,
        )

    def append_ipa(self, text: str, *, strict: bool = False) -> tuple[Any, ...]:
        """Scan IPA once and append its input occurrences to the shared clock."""
        parsed = self.features.read(text, strict=strict)
        index_view = parsed.__dict__["_tiergraph_index"]
        by_index: dict[int, tuple[int, str, Any]] = {}
        for tick, node in enumerate(index_view.clock):
            for group in node.groups:
                for event in group.events:
                    index = event.features.get("compatibility-index")
                    if isinstance(index, int):
                        by_index[index] = (tick, group.tier, event)
        handles = []
        for index in range(len(parsed.units)):
            tick, tier, event = by_index[index]
            values = dict(event.features)
            values["compatibility-index"] = self._compatibility_unit_count
            if event.structural_duration == 1:
                handles.append(self._builder.append_input_atom(tier, values))
            else:
                handles.append(
                    self._builder.append_input_occurrence(
                        tier,
                        values,
                        refines_tick=index_view.clock[tick].gap_count > 1,
                    )
                )
            self._compatibility_unit_count += 1
        return tuple(handles)

    def contain(
        self, parent: Any, children: Sequence[Any], *, relation: str = "contains"
    ) -> None:
        """Add one ordered containment sequence."""
        self._builder.contain(parent, children, relation=relation)

    def relate(self, sources: Sequence[Any], name: str, targets: Sequence[Any]) -> None:
        """Add a declared relation while preserving endpoint order."""
        self._builder.relate(sources, name, targets)

    def add_root(self, handle: Any) -> None:
        """Declare an event as a rendering or traversal root."""
        self._builder.add_root(handle)

    def attach_timing(self, handle: Any, start: float, duration: float) -> None:
        """Attach optional physical time without changing structural order."""
        self._builder.attach_timing(handle, start, duration)

    def build(self) -> Form:
        """Validate and return the immutable public representation."""
        return Form._from_graph(self._builder.build())


class _DerivedMapping(Mapping[str, str]):
    """An immutable resolved view that ``replace`` can recognize as pass-through."""

    def __init__(self, value: Mapping[str, str]) -> None:
        self._value = MappingProxyType(dict(value))

    def __getitem__(self, key: str) -> str:
        return self._value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)


class _DerivedProvenance(tuple[tuple[str, str, str], ...]):
    """A resolved provenance tuple tagged as lazy pass-through."""

    def __new__(cls, value: Sequence[tuple[str, str, str]]) -> _DerivedProvenance:
        return tuple.__new__(cls, value)


def _default(features: IPAFeatures | None) -> IPAFeatures:
    """The shipped inventory, unless the caller named another.

    Deferred so this module reads naturally without importing the
    package that imports it.
    """
    if features is not None:
        return features
    from . import _get_ipa

    return _get_ipa()


@dataclass(frozen=True, order=True)
class Timing:
    """An optional time span, in seconds, on an occurrence or tier span.

    Half-open by convention, like :class:`Interval`; zero duration is a
    point target.  Timing belongs to occurrences rather than ``Segment``
    identities, because two instances of the same phone need not last the
    same time.  No interpolation or edit-rebasing policy is implied here.
    """

    start: float
    duration: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", float(self.start))
        object.__setattr__(self, "duration", float(self.duration))
        if not math.isfinite(self.start) or not math.isfinite(self.duration):
            raise ValueError("timing values must be finite")
        if self.start < 0:
            raise ValueError(f"timing starts before zero: {self.start}")
        if self.duration < 0:
            raise ValueError(f"timing duration is negative: {self.duration}")

    @property
    def end(self) -> float:
        """Derived half-open endpoint for interval arithmetic."""
        return self.start + self.duration


@dataclass(frozen=True, eq=False)
class Unit:
    """One position in a form: a segment, or a boundary between segments.

    A boundary is not a segment -- it is a relation, linearized into the
    string as a character. It carries no phonetic features, only the
    declared separator attributes (``level=word``, ``level=syllable``),
    and it is never the target of a feature change.

    Segment views are derived together on first access in a lax parse; a
    strict parse resolves them during parsing so full validation and its
    diagnostics happen before the form is returned. An explicitly supplied
    ``features``, ``prosody``, or ``provenance`` value is already resolved and
    is never replaced by inventory derivation; derivation fills only absent
    views.

    :attr:`features` and :attr:`prosody` are read-only. ``frozen`` stops a
    *field* being rebound and says nothing about the mapping a field points
    at, so a unit whose prosody could be written in place had a spelling
    and a prosody that could come to disagree about the same sound. Build
    a variant with :func:`dataclasses.replace`, or take ``dict(...)`` for
    a copy of your own.
    """

    text: str
    segment: Segment | None = None
    features: Mapping[str, str] = field(
        default=cast(Mapping[str, str], _VIEW_ABSENT), compare=False
    )
    prosody: Mapping[str, str] = field(
        default=cast(Mapping[str, str], _VIEW_ABSENT), compare=False
    )
    #: ``(glyph, feature, value)`` per prosodic mark, resolved when the
    #: unit was built so each attribute can name the mark that declared it.
    provenance: tuple[tuple[str, str, str], ...] = field(
        default=cast(tuple[tuple[str, str, str], ...], _VIEW_ABSENT), compare=False
    )
    timing: Timing | None = None
    #: Exact source glyph for a semantically canonicalized unit.
    spelling: str | None = field(default=None, compare=False)
    _inventory: IPAFeatures | None = field(
        default=None, compare=False, hash=False, repr=False
    )
    _views_resolved: bool = field(
        default=False, init=False, compare=False, hash=False, repr=False
    )

    def __post_init__(self) -> None:
        # Wrapped here rather than at each construction site, so a site
        # added later cannot forget and hand back a writable one.
        namespace = object.__getattribute__(self, "__dict__")
        segment_view = (
            namespace["segment"] is not None and namespace["_inventory"] is not None
        )
        features_absent = namespace["features"] is _VIEW_ABSENT or isinstance(
            namespace["features"], _DerivedMapping
        )
        prosody_absent = namespace["prosody"] is _VIEW_ABSENT or isinstance(
            namespace["prosody"], _DerivedMapping
        )
        provenance_absent = namespace["provenance"] is _VIEW_ABSENT or isinstance(
            namespace["provenance"], _DerivedProvenance
        )
        features = (
            MappingProxyType({})
            if features_absent
            else MappingProxyType(dict(namespace["features"]))
        )
        prosody = (
            MappingProxyType({})
            if prosody_absent
            else MappingProxyType(dict(namespace["prosody"]))
        )
        provenance = () if provenance_absent else tuple(namespace["provenance"])
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "prosody", prosody)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "_views_pending",
            frozenset(
                name
                for name, absent in (
                    ("features", features_absent),
                    ("prosody", prosody_absent),
                    ("provenance", provenance_absent),
                )
                if segment_view and absent
            ),
        )
        object.__setattr__(
            self,
            "_views_resolved",
            not segment_view or not object.__getattribute__(self, "_views_pending"),
        )

    def __getattribute__(self, name: str) -> Any:
        if name in {"features", "prosody", "provenance"}:
            namespace = object.__getattribute__(self, "__dict__")
            inventory = namespace.get("_inventory")
            pending = namespace.get("_views_pending", ())
            if (
                namespace.get("segment") is not None
                and inventory is not None
                and pending
            ):
                resolved = _resolve_unit_views(namespace["segment"], inventory)
                if "features" in pending:
                    object.__setattr__(self, "features", _DerivedMapping(resolved[0]))
                if "prosody" in pending:
                    object.__setattr__(self, "prosody", _DerivedMapping(resolved[1]))
                if "provenance" in pending:
                    object.__setattr__(
                        self, "provenance", _DerivedProvenance(resolved[2])
                    )
                object.__setattr__(self, "_views_pending", frozenset())
                object.__setattr__(self, "_views_resolved", True)
                return object.__getattribute__(self, name)
        return object.__getattribute__(self, name)

    def _identity(self) -> tuple[Any, ...]:
        namespace = object.__getattribute__(self, "__dict__")
        segment = namespace["segment"]
        declared = (
            (
                (),
                (),
                (),
            )
            if segment is not None
            else (
                tuple(namespace["features"].items()),
                tuple(namespace["prosody"].items()),
                namespace["provenance"],
            )
        )
        return (namespace["text"], segment, declared, namespace["timing"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Unit):
            return NotImplemented
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

    @property
    def is_zero(self) -> bool:
        """Whether this position is a declared structural zero.

        A third kind of position, and the reason :attr:`is_boundary` is
        not simply "carries no segment". A boundary is a *relation*
        between two segments; a zero is a **slot** where a segment is
        not. ``le∅ʃjɛ̃`` has five sounds and six positions, and the empty
        one sits inside the word rather than dividing it.
        """
        return self.segment is None and self.features.get("class") == ZERO_CLASS

    @property
    def is_boundary(self) -> bool:
        return self.segment is None and not self.is_zero

    @property
    def level(self) -> str | None:
        """The declared ``level`` of a boundary, else ``None``.

        One of the values ``<feature name="level">`` declares -- today
        ``syllable``, ``word``, ``phrase``, ``utterance``. Every shipped
        boundary glyph declares one, including the linking mark ``‿``,
        which is a *word* boundary that says the words are run together
        without a pause. ``None`` is for a segment.
        """
        return self.features.get("level") if self.is_boundary else None

    @property
    def transparent(self) -> bool:
        """Whether context scanning steps over this unit silently.

        True for a syllable break, because the dot is optional notation
        and must not change which rules fire. False for a word mark and
        for whitespace, which are real edges.
        """
        return self.level == "syllable"

    @property
    def core(self) -> str:
        """The spelling without prosody glyphs: ``ˈa`` has core ``a``.

        This is the phone's identity name. Stress and length are not
        part of it, which is why ``a``, ``ˈa`` and ``aː`` share one.

        Spelled by the segment itself rather than by joining its
        constituents: a tie bar lives in ``junctures``, so hand-joining
        would drop it and ``t͡s`` would stop matching ``ˈt͡s``.
        """
        if self.segment is None:
            return self.text
        if not self.segment.prosody:
            return self.text
        return dataclasses.replace(self.segment, prosody=()).to_ipa()

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        namespace = object.__getattribute__(self, "__dict__")
        if self.segment is not None:
            return (
                f"Unit(text={self.text!r}, segment={self.segment!r}, "
                f"timing={self.timing!r})"
            )
        return (
            f"Unit(text={self.text!r}, segment=None, "
            f"features={dict(namespace['features'])!r}, "
            f"prosody={dict(namespace['prosody'])!r}, "
            f"provenance={namespace['provenance']!r}, timing={self.timing!r})"
        )


@dataclass(frozen=True)
class Boundary:
    """A relation *between* segments, linearized into the string.

    ``at`` counts the segments before it, so it survives the projection
    that drops boundary units and can be used to put them back.

    :attr:`features` is what the mark declared, and it is the faithful
    field: :meth:`Form.rebuild` reproduces the unit from it rather than
    from :attr:`level`, which cannot say that ``‿`` links or that ``|``
    is a minor break. :attr:`level` falls back to ``word`` where a mark
    declares none; every shipped glyph declares one, so the fallback is
    reached only by a hand-made boundary or a mark added without a level.

    :attr:`features` is read-only, for the reason :class:`Unit` gives.
    """

    text: str
    level: str
    at: int
    #: Everything the mark declared, so putting a form back together
    #: reproduces the unit rather than an impoverished copy of it.
    features: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))

    def __repr__(self) -> str:
        # Spelled out rather than generated, so what a reader sees is the
        # bundle and not the wrapper that makes it read-only.
        return (
            f"Boundary(text={self.text!r}, level={self.level!r}, "
            f"at={self.at}, features={dict(self.features)!r})"
        )


@dataclass(frozen=True)
class Attribute:
    """A value attached *to* a segment: stress, length, tone.

    The counterpart of :class:`Boundary`. Both are things a
    transcription carries that are not themselves sounds, and they
    differ in how they attach: a boundary sits between two segments, an
    attribute rides on one. ``at`` indexes the segment it rides on.

    Attributes are declared like anything else -- ``ˈ`` says
    ``stress="primary"``, ``ː`` says ``length="long"`` -- and they are
    exactly the ``mode="prosodic"`` features, which live on the unit
    rather than in the feature bag (docs/ties.md). That is why they are
    not part of a phone's identity: ``a``, ``ˈa`` and ``aː`` are one
    phone wearing different attributes.
    """

    feature: str
    value: str
    at: int
    glyph: str = ""


@dataclass(frozen=True)
class Node:
    """A node of the transcription tree.

    Internal nodes carry a declared boundary tier as :attr:`level`
    (``word``, ``syllable``); leaves carry a :class:`Unit` and the level
    ``segment``. The root is ``form``, which is the whole reading rather
    than a declared tier.

    :attr:`opened_by` and :attr:`closed_by` say *which delimiter supplied
    each end of the span*, and ``None`` means the form's own edge -- a
    boundary that was inferred rather than written. The node's brackets
    are its span endpoints either way, so this adds no shape: ``#kæt#``
    and ``kæt`` are the same word and give the same tree, and they differ
    only in whether the delimiters were typed (:attr:`asserted`). The
    delimiters are not units of the form, because ``Form.units`` is the
    faithful read of what was *spelled* and :attr:`Site.start` indexes
    into it.
    """

    level: str
    children: tuple[Node, ...] = ()
    unit: Unit | None = None
    #: The delimiter this node's left edge came from; ``None`` for the
    #: form edge, which delimits without being written.
    opened_by: Boundary | None = None
    #: The delimiter this node's right edge came from; ``None`` as above.
    closed_by: Boundary | None = None

    @property
    def is_leaf(self) -> bool:
        return self.unit is not None

    @property
    def asserted(self) -> bool:
        """Whether both of this node's delimiters were written.

        ``#kæt#`` asserts its word; ``kæt`` is the same word with both
        ends inferred from the form edge, and ``kæt dɒɡ`` asserts one end
        of each. A leaf and the root are never asserted -- a segment has
        no delimiters, and the form is what the edges are the edges *of*.
        """
        return self.opened_by is not None and self.closed_by is not None

    @property
    def units(self) -> tuple[Unit, ...]:
        if self.unit is not None:
            return (self.unit,)
        return tuple(u for child in self.children for u in child.units)

    def to_ipa(self) -> str:
        """What this node spells, boundaries between siblings excluded."""
        return "".join(u.text for u in self.units)

    def at(self, level: str) -> tuple[Node, ...]:
        """Every node on a given tier, in order."""
        if self.level == level:
            return (self,)
        return tuple(n for child in self.children for n in child.at(level))

    def __iter__(self) -> Iterator[Node]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __repr__(self) -> str:
        if self.is_leaf:
            return f"Node({self.level}, {self.to_ipa()!r})"
        return f"Node({self.level}, {len(self.children)} children, {self.to_ipa()!r})"


@dataclass(frozen=True)
class _FormConstants:
    tier_names: tuple[str, ...]
    levels: tuple[str, ...]
    edge_level: str
    boundary_marks: Mapping[str, Mapping[str, str]]
    zeros: Mapping[str, Mapping[str, str]]


def _derive_form_constants(features: IPAFeatures) -> _FormConstants:
    """Derive immutable vocabulary shared by every parse of an inventory."""
    declared_tier = features.features.get("tier")
    level_order = features.features["level"].values
    spelled = {
        level
        for sep in features.separators.values()
        if (level := (sep.features or {}).get("level")) in level_order
    }
    edge = (
        max(spelled, key=level_order.index)
        if spelled
        else level_order[-1]  # pragma: no cover - no separator declares a level
    )
    structural = {
        name
        for name in features.features_by_mode.get("structural", ())
        if name != "tie" and features.features[name].centre is None
    }
    marks: dict[str, Mapping[str, str]] = {}
    for symbol, declared in features.diacritics.items():
        bundle = getattr(declared, "features", None) or {}
        if any(key in structural for key in bundle):
            marks[symbol] = MappingProxyType(
                {key: value for key, value in bundle.items() if key not in _METADATA}
            )
    nulls = {
        symbol: MappingProxyType(dict(declared.features or {}))
        for symbol, declared in features.zeros.items()
    }
    return _FormConstants(
        tuple(declared_tier.values) if declared_tier is not None else (),
        tuple(reversed(level_order)),
        edge,
        MappingProxyType(marks),
        MappingProxyType(nulls),
    )


def tier_names(features: IPAFeatures | None = None) -> tuple[str, ...]:
    """The tiers an :class:`Interval` may be declared on, read off the data.

    ``<feature name="tier">`` is nominal and ``mode="structural"``, and it
    is a different thing from the ordinal ``level`` three lines above it in
    ``ipa.xml``: ``level=syllable`` is how strong a boundary is,
    ``tier=syllable`` is which tier a span sits on. They are read by
    separate functions for that reason, and neither is written out here, so
    a language declaring a further tier gets it without a change to this
    module.
    """
    features = _default(features)
    return features._form_constants.tier_names


@dataclass(frozen=True)
class Interval:
    """A span on a declared tier, over :attr:`Form.units`.

    Half-open -- ``[start, end)``, the convention :class:`rules.Site`
    already uses -- and indexing the *unit* sequence rather than the
    segmental projection, because a tier may need to span a boundary and a
    boundary is a unit.

    An interval makes **no claim to nest**. That is the whole of what it
    buys over :meth:`Form.tree`, which splits on the strongest boundary
    first and so cannot state a syllable that crosses a word: in
    ``pə.ti.t‿a.mi`` the syllable ``t‿a`` is contained by neither word, and
    two intervals may overlap with neither containing the other. Nothing
    here orders two tiers, and nothing should -- ``tier`` is nominal
    precisely so a mora cannot be ranked against a morph.

    An interval is not spelled, so it does not survive
    :meth:`Form.to_ipa`; and it is not derived from the units, so nothing
    invents one. A form with no dots has no syllable intervals rather than
    one, for the reason the rest of this module gives about unspecified
    structure.

    ``features`` names the inventory the tier is checked against and is not
    stored: two intervals with the same tier and span are the same
    interval, whichever inventory declared the name.
    """

    tier: str
    start: int
    end: int
    features: dataclasses.InitVar[IPAFeatures | None] = None
    timing: Timing | None = None

    def __post_init__(self, features: IPAFeatures | None) -> None:
        declared = tier_names(features)
        if self.tier not in declared:
            raise ValueError(
                f"{self.tier!r} is not a declared tier; "
                f"declared: {', '.join(declared) or '(none)'}"
            )
        if self.start < 0:
            raise ValueError(f"interval starts before the form: {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"interval ends before it starts: [{self.start}, {self.end})"
            )

    def __len__(self) -> int:
        return self.end - self.start

    def __repr__(self) -> str:
        held = f", timing={self.timing!r}" if self.timing is not None else ""
        return f"Interval({self.tier!r}, {self.start}, {self.end}{held})"


def levels(features: IPAFeatures | None = None) -> tuple[str, ...]:
    """The boundary levels, outermost first, read off the declaration.

    ``ipa.xml`` declares ``<feature name="level">`` with its values in
    order -- ``syllable``, ``word``, ``phrase``, ``utterance`` -- and each
    separator or break mark declares which one it terminates. So the
    nesting is data, not a constant here: declaring a further value
    extends the tree without a change to this module.
    """
    features = _default(features)
    return features._form_constants.levels


def edge_level(features: IPAFeatures | None = None) -> str:
    """The level the form's own edges delimit, read off the declaration.

    A form with no ``#`` in it still has one word, because running off
    the end of a form is a word edge -- the same reading the rule engine
    uses when ``_ #`` matches without a ``#`` having been typed. That is
    not "the outermost level": ``|`` and ``‖`` declare levels *above*
    ``word``, and a form with no break mark in it is not thereby one
    phrase. So the level is the strongest one a **separator** spells,
    which is what a form edge is an unwritten instance of.

    Read from ``<separators>`` rather than stated here, so declaring a
    stronger separator moves the edge with it. ``rules.py`` asks this
    function rather than answering it again: its ``_edge_level`` used to
    read the top of the whole ``level`` ladder, which is ``utterance``
    while this is ``word``, since ``|`` and ``‖`` declare levels above
    ``word`` without being separators. The two are one read now, so they
    cannot drift apart when a separator above ``word`` is declared.

    Called ``edge_tier`` until ``tier`` became a declared feature of its
    own. A function named for one declared feature and answering with a
    value of another is exactly the confusion this increment exists to
    prevent, so nothing named ``tier`` in this module answers with a
    ``level`` and nothing named ``level`` answers with a ``tier``.
    """
    features = _default(features)
    return features._form_constants.edge_level


def boundary_marks(features: IPAFeatures) -> Mapping[str, Mapping[str, str]]:
    """Declared marks that stand *between* units rather than modify one.

    The prosodic break ``|``, the major break ``‖`` and the linking mark
    ``‿``. They are declared suprasegmentals, ``is_valid_ipa`` accepts
    them, and ``segments()`` discards them without even the warning it
    gives a stray stress mark -- so a form carrying one did not spell
    back out. Read from ``<modes>``: the ``structural`` features, less
    ``tie``, because a tie *joins* two units rather than standing between
    them.
    """
    return features._form_constants.boundary_marks


def zeros(features: IPAFeatures) -> Mapping[str, Mapping[str, str]]:
    """Declared symbols that hold a position open without filling it.

    Today ``∅``. A zero carries no phonetic features at all, which is
    what keeps it out of the metric by construction rather than by an
    exclusion someone has to maintain, and it is not ``␣``: silence is a
    registered phone with ``manner="silence"``, a segment with duration.
    A zero is the absence of one.

    The bundle view of :attr:`~ipakit.IPAFeatures.zeros`, which the
    loader fills like any other element class. It used to open
    ``ipa.xml`` a second time, because ``_load_element`` routed four
    classes and dropped the rest; two readers of one file is the shape
    this repo treats as a defect waiting to happen, and it is now one.
    """
    return features._form_constants.zeros


def _segmental(bundle: dict[str, str], features: IPAFeatures) -> dict[str, str]:
    """A feature bundle with the prosodic keys removed.

    ``seg.scalar()`` reports ``length='normal'`` for a long vowel, because
    prosody lives on the unit and not in the bag (docs/ties.md). Carrying
    that key here left ``Unit.features`` and ``Unit.prosody`` disagreeing
    about the same feature, so a caller could read either and get a
    different answer. Prosody now has exactly one home.
    """
    prosodic = set(features.features_by_mode.get("prosodic", ()))
    return {k: v for k, v in bundle.items() if k not in prosodic}


def declared_prosody(glyph: str, features: IPAFeatures) -> Mapping[str, str]:
    """What one mark says about prosody: ``ˈ`` is ``{'stress': 'primary'}``.

    The single read of a mark's prosodic declaration. Everything that
    needs it -- resolving a unit's prosody, deciding whether a character
    in a rule's notation is prosody at all, and respelling prosody after
    a rule writes it -- goes through here, so no two of them can end up
    with different ideas of what ``ː`` means.

    Filtered to ``mode="prosodic"`` keys, which is what makes the read
    usable as a *test*: ``ʰ`` declares a release phase and comes back
    empty, so a caller can ask "is this glyph prosody" without a list of
    glyphs. No shipped mark mixes the two modes, so the filter costs
    nothing on the resolving path.
    """
    return features._prosody_declarations.get(glyph, _EMPTY_MAPPING)


def _derive_prosody_declarations(
    features: IPAFeatures,
) -> Mapping[str, Mapping[str, str]]:
    """Build the immutable mark-to-prosody table for one inventory."""
    prosodic = features.features_by_mode.get("prosodic", ())
    return MappingProxyType(
        {
            glyph: MappingProxyType(
                {
                    key: value
                    for key, value in (declared.features or {}).items()
                    if key not in _METADATA and key in prosodic
                }
            )
            for glyph, declared in features.diacritics.items()
        }
    )


def _asserted_prosody(seg: Segment, features: IPAFeatures) -> dict[str, str]:
    """What a segment's prosody glyphs, together, assert.

    ``ˈ`` declares ``stress="primary"`` and ``ː`` declares
    ``length="long"`` in ``ipa.xml``; this reads those declarations
    rather than restating which glyph means what.

    A run of marks stating a **sequence-valued** feature *concatenates*:
    ``a˩˥`` is ``tone="bottom>top"`` and ``a˧˩˧`` is
    ``tone="mid>bottom>mid"``, because a contour is the whole run and not
    its last letter. A run stating a single-valued feature twice is a
    contradiction rather than a stack -- two lengths on one unit -- so the
    first stands and the collision is **reported**. Neither case may drop
    a mark in silence: a merge that let the last writer win recorded a
    rise and a fall as opposite level tones, with no diagnostic at all.

    Both branches are :func:`~ipakit.segment.state_mark_value`, which is
    also how the segmental read folds a modifier stack. Written out here
    once, the segmental read had neither branch: ``compose("a˧˦")``
    answered ``tone="mid"`` where this answered ``tone="mid>high"``, and
    ``compose("ɛ̥̤")`` answered a phonation off the order the marks
    happened to be written in.
    """
    out: dict[str, str] = {}
    stated: dict[str, str] = {}
    for glyph in seg.prosody:
        for key, value in declared_prosody(glyph, features).items():
            state_mark_value(
                features,
                out,
                stated,
                key,
                value,
                overriding=True,
                where=repr(seg.to_ipa()),
            )
    return out


def _derived_contour(
    stated: dict[str, str], features: IPAFeatures
) -> dict[str, str] | None:
    """The shape a stated level sequence has, or ``None`` where it states
    no sequence to have one.

    A contour **is** the sequence: one step per adjacent pair of levels,
    each step the value whose declared ``move`` matches the direction that
    pair goes on the level scale. So ``a˩˥`` derives ``contour="rising"``
    and ``a˧˩˧`` derives ``contour="falling>rising"``, and the diacritic
    and tone-letter spellings of one contour answer alike.

    Which feature is derived from which is read off the data: the derived
    feature is the one declaring ``over``. Nothing here knows the word
    "tone" or the word "rising".
    """
    for name, feature in features.features.items():
        if feature.over is None:
            continue
        scale = features.features.get(feature.over)
        if scale is None or feature.over not in stated:
            continue
        levels = scale.steps(stated[feature.over])
        moves = [
            feature.move(scale, a, b) for a, b in zip(levels, levels[1:], strict=False)
        ]
        if moves and all(m is not None for m in moves):
            return {name: feature.sequenced([m for m in moves if m is not None])}
    return None


def _prosodic_features(seg: Segment, features: IPAFeatures) -> dict[str, str]:
    """A segment's prosody: what its marks assert, plus what that entails.

    The read half of the unit's prosody. Everything the glyphs say comes
    through :func:`_asserted_prosody`; on top of that, a stated level
    sequence *has* a shape, and that shape is derived here rather than
    demanded of the writer. The consequence is the one the chart claims:
    ``ǎ`` and ``a˩˥`` agree on the contour, and ``a᷄`` and ``a˧˦`` agree
    on everything.

    A derived value never overwrites an asserted one. Where they disagree
    -- a fall written over a rising level sequence -- the assertion stands
    and the contradiction is reported, because only the writer knows which
    of the two they meant.
    """
    out = _asserted_prosody(seg, features)
    for key, value in (_derived_contour(out, features) or {}).items():
        if key not in out:
            out[key] = value
        elif out[key] != value:
            warnings.warn(
                f"{seg.to_ipa()!r}: a mark states {key}={out[key]!r}, but the "
                f"levels written on it are {value!r}; the mark stands",
                stacklevel=2,
            )
    return out


def split_prosody(text: str, features: IPAFeatures) -> tuple[str, tuple[str, ...]]:
    """Separate a written unit into its phone and the prosody it wears.

    ``aː`` is ``('a', ('ː',))``, ``ˈa`` is ``('a', ('ˈ',))``, ``a`` is
    ``('a', ())``. The counterpart of :attr:`Unit.core`, for text that has
    not been parsed yet -- which is what a rule's notation is, and why a
    literal naming prosody could not be matched before: it was compared
    whole against ``core``, from which the prosody glyphs have already
    been removed.

    The text is canonicalized first, because ``á`` is a single character
    until it is decomposed and the tone mark is not there to be seen
    before that. :meth:`~ipakit.IPAFeatures.canonicalize_unicode` is the
    right decomposition rather than raw NFD: it puts back the few
    registered precomposed symbols, so ``ç`` stays one phone instead of
    becoming a ``c`` wearing a cedilla.

    Prosody is recognized anywhere in the string, not only at the edges.
    A mark's *written* position is a spelling convention -- stress goes
    before its domain, length after -- and ``Segment.to_ipa`` is what
    knows that; a splitter that hardcoded it would be a second opinion.
    """
    core: list[str] = []
    prosody: list[str] = []
    for char in features.canonicalize_unicode(text):
        (prosody if declared_prosody(char, features) else core).append(char)
    return "".join(core), tuple(prosody)


def with_prosody(
    seg: Segment, changes: Mapping[str, str | None], features: IPAFeatures
) -> Segment | None:
    """``seg`` with its prosody rewritten: values assigned, changed, cleared.

    The write half of :func:`_prosodic_features`, and the reason prosody
    is expressible on the right of a rewrite arrow at all. It has to be
    separate from the segmental composer because the two do not share a
    mechanism: :meth:`~ipakit.IPAFeatures.compose_unit` verifies a
    composition by reading the feature bag back, and the bag *by design*
    excludes prosody (docs/ties.md), so it answers ``None`` for every
    prosodic request -- correctly, since prosody is not part of what it
    spells. Writing prosody means changing :attr:`Segment.prosody`.

    The change is stated in **feature space**, and a value of ``None``
    clears the feature. A value that no mark declares but which the
    feature takes when unmarked is also a clear: nothing declares
    ``length=normal`` because a bare vowel already says it, so shortening
    and clearing are one operation rather than two spellings of it.

    Glyphs are then re-derived only where they no longer say what is
    wanted. That matters for fidelity in both directions. A mark whose
    whole declaration still holds is kept *as written*, so changing the
    length of ``á`` does not silently respell its tone as ``a˦``; and a
    mark that is dropped because one of its features changed does not
    take the others down with it -- changing the length of ``ˈa`` leaves
    the stress behind, because the features are what was written and the
    glyphs are downstream of them.

    The write is stated in what the marks **assert**, never in what the
    marks entail: a level sequence has a contour, and no mark for it is
    added, because that would be a second claim about a shape the levels
    already fix. A mark that was *written* for it stays written, agreeing
    or not -- dropping an assertion because a derivation would reach the
    same tier is how a caron over a falling sequence came back as a fall.
    A run stating a sequence is kept by walking it -- ``a˩˥`` keeps both
    letters against ``tone="bottom>top"``, and a sequence no single mark
    spells is spelled one level at a time.

    Returns ``None`` where the inventory cannot spell the result, where
    the result does not read back as what was asked, or where what was
    asked cannot be spelled at all: clearing a tier that the retained
    tiers *entail* is impossible, since a tone reading ``bottom>top``
    rises whether or not a mark says so, and clearing the tone as well
    would answer a different request from the one made.

    That check is a measurement rather than a formality: the marks were
    picked from the declaration, but whether they re-emit themselves and
    still say the requested values is exactly the kind of thing this repo
    has been wrong about while looking right.
    """
    wanted = _asserted_prosody(seg, features)
    #: Tiers the caller asked to be **absent**. Held separately because a
    #: hole in ``wanted`` is not a negative constraint: a derivable tier
    #: fills its own hole back in on the read, and only a request that
    #: says "gone" can tell that apart from one that was never made.
    cleared: set[str] = set()
    for key, value in changes.items():
        feature = features.features.get(key)
        if feature is None:
            raise ValueError(f"unknown feature {key!r}")
        if value is None or (
            value == feature.default and features.declaring_mark(key, value) is None
        ):
            wanted.pop(key, None)
            cleared.add(key)
        else:
            wanted[key] = value

    # The read the result must produce, fixed here -- before one glyph is
    # chosen -- so the check at the bottom is a measurement and not a
    # restatement of whatever the speller decided. Computing it from the
    # marks that got picked is what let an asserted contour be dropped and
    # its opposite derived back, with the check agreeing by construction.
    target: dict[str, str | None] = {
        **(_derived_contour(wanted, features) or {}),
        **wanted,
    }
    for key in cleared:
        target[key] = None

    # How far through each wanted sequence the kept marks have got, so a
    # run of level marks is matched as the run it is rather than each
    # letter against the whole.
    reached = {k: 0 for k, v in wanted.items() if features.features[k].sequence}
    kept: list[str] = []
    covered: set[str] = set()
    for glyph in seg.prosody:
        says = declared_prosody(glyph, features)
        advanced: dict[str, int] = {}
        holds = True
        for key, value in says.items():
            feature = features.features.get(key)
            if feature is not None and key in reached:
                piece = feature.steps(value)
                at = reached[key]
                if feature.steps(wanted[key])[at : at + len(piece)] != piece:
                    holds = False
                else:
                    advanced[key] = at + len(piece)
            elif wanted.get(key) != value:
                holds = False
        if holds:
            kept.append(glyph)
            covered.update(k for k in says if k not in reached)
            reached.update(advanced)
    order = list(features.features)
    for key in sorted(set(wanted) - covered, key=order.index):
        feature = features.features[key]
        rest = feature.steps(wanted[key])[reached.get(key, 0) :]
        if not rest:
            continue
        # One mark for the whole remainder if one declares it (``᷄`` is
        # mid-then-high), else level by level.
        found = features.declaring_mark(key, feature.sequenced(rest))
        spellings = (
            [found] if found else [features.declaring_mark(key, s) for s in rest]
        )
        if not all(spellings):
            return None
        kept.extend(found[1] for found in spellings if found)

    out = dataclasses.replace(seg, prosody=tuple(kept))
    spelled = out.to_ipa()
    items = units(spelled, features)
    if len(items) != 1 or items[0].text != spelled:
        return None
    got = items[0].prosody
    # Three claims, because one dict comparison cannot make them all. The
    # marks say what was wanted and no more, so nothing entailed got
    # written as a second claim; every tier asked to be gone is gone; and
    # what remains reads as the target -- which includes the tiers the
    # levels entail, so a request to drop one fails here rather than being
    # reported as done.
    if _asserted_prosody(out, features) != wanted:
        return None
    if any(key in got for key, value in target.items() if value is None):
        return None
    if got != {key: value for key, value in target.items() if value is not None}:
        return None
    return out


def _resolve_unit_views(
    seg: Segment, features: IPAFeatures
) -> tuple[Mapping[str, str], Mapping[str, str], tuple[tuple[str, str, str], ...]]:
    """Resolve all occurrence views together for one memoized first access."""
    provenance: list[tuple[str, str, str]] = [
        (glyph, key, value)
        for glyph in seg.prosody
        for key, value in declared_prosody(glyph, features).items()
    ]
    return (
        MappingProxyType(_segmental(seg.scalar(), features)),
        MappingProxyType(_prosodic_features(seg, features)),
        tuple(provenance),
    )


def _unit_for(seg: Segment, features: IPAFeatures) -> Unit:
    # Keep the declaring inventory with the structured value. The resolved
    # occurrence views are computed together on their first access.
    return Unit(
        text=seg.to_ipa(),
        segment=seg,
        _inventory=features,
    )


def units(
    form: str, features: IPAFeatures | None = None, strict: bool = False
) -> list[Unit]:
    """Split a transcription into positions, keeping boundaries.

    The unprojected read. :class:`Form` is the object around it; this is
    here for callers that want the sequence alone.
    """
    return list(_default(features).read(form, strict=strict).units)


def spell(items: Sequence[Unit]) -> str:
    """Join units back into one IPA string."""
    return "".join(u.spelling if u.spelling is not None else u.text for u in items)


class _CompatibilityProjection:
    """Map the graph's input-owned positions to the frozen public coordinates."""

    def __init__(
        self,
        graph: Any,
        inventory: IPAFeatures | None = None,
    ) -> None:
        from ._tiergraph_builder import LegacyCoordinates, LegacyOccurrence
        from ._tiergraph_identity import DurableEventIdentity

        self.graph = graph
        self.identity = DurableEventIdentity.build(graph)
        self._inventory = inventory
        indexed: list[tuple[int, Unit, Any]] = []
        for node in graph.clock:
            for group in node.groups:
                for event in group.events:
                    unit = event.features.get("compatibility-unit")
                    index = event.features.get("compatibility-index")
                    if isinstance(unit, Unit) and isinstance(index, int):
                        indexed.append((index, unit, event))
        indexed.sort(key=lambda item: item[0])
        if [index for index, _, _ in indexed] != list(range(len(indexed))):
            raise FormProjectionError(
                "graph compatibility unit order is not contiguous"
            )
        self._indexed = tuple(indexed)
        self._units: tuple[Unit, ...] | None = None
        self._intervals: tuple[Interval, ...] | None = None
        self.coordinates = LegacyCoordinates(
            tuple(
                LegacyOccurrence(
                    consumes_span=not unit.is_boundary,
                    refines_tick=unit.is_boundary,
                )
                for _, unit, _ in indexed
            )
        )
        # The adapter is required to be bidirectional.  Check every position,
        # not merely interval endpoints that happen to exist on this form.
        for index in range(len(indexed) + 1):
            if self.coordinates.to_legacy(self.coordinates.to_graph(index)) != index:
                raise FormProjectionError(
                    "graph compatibility coordinates are not lossless"
                )

    @property
    def units(self) -> tuple[Unit, ...]:
        if self._units is not None:
            return self._units
        from ._containment_projection import _event_payload, _unit_from_attributes

        if self._inventory is None:
            raise FormProjectionError("compatibility unit inventory is not available")
        # Reconstruct each Unit from its lowered attribute payload — the same
        # encoding that is stored on the authoritative graph — without
        # materializing that graph, so reads stay off the build path.
        out = []
        for _index, _stored, event in self._indexed:
            attributes = {
                name: lexical for name, _type, lexical in _event_payload(event)
            }
            out.append(_unit_from_attributes(attributes, self._inventory))
        self._units = tuple(out)
        return self._units

    @property
    def intervals(self) -> tuple[Interval, ...]:
        if self._intervals is not None:
            return self._intervals
        from ._containment_projection import _event_payload

        # Adjacent ticks share their boundary position, so a legacy coordinate
        # is the intra-tick gap plus the running gap total of every earlier
        # tick — the same mapping the builder's to_legacy computed.
        gap_prefix = [0]
        for node in self.graph.clock:
            gap_prefix.append(gap_prefix[-1] + node.gap_count)

        def coordinate(pointer: str) -> int:
            parts = pointer.split("/")
            tick = int(parts[2])
            gap = int(parts[4]) if len(parts) == 5 else 0
            return gap + gap_prefix[tick]

        indexed = []
        for tick, node in enumerate(self.graph.clock):
            for group in node.groups:
                for event in group.events:
                    index = event.features.get("compatibility-interval")
                    if not isinstance(index, int):
                        continue
                    attributes = {
                        name: lexical for name, _type, lexical in _event_payload(event)
                    }
                    timing = (
                        Timing(
                            float(attributes["timing-start"]),
                            float(attributes["timing-duration"]),
                        )
                        if "timing-start" in attributes
                        else None
                    )
                    if "span-start" in attributes:
                        start = coordinate(attributes["span-start"])
                        end = coordinate(attributes["span-end"])
                    elif "structural-duration" in attributes:
                        start = gap_prefix[tick]
                        end = gap_prefix[tick + int(attributes["structural-duration"])]
                    else:
                        raise FormProjectionError(
                            "compatibility interval has no exact span"
                        )
                    interval = Interval.__new__(Interval)
                    object.__setattr__(interval, "tier", group.tier)
                    object.__setattr__(interval, "start", start)
                    object.__setattr__(interval, "end", end)
                    object.__setattr__(interval, "timing", timing)
                    indexed.append((index, interval))
        indexed.sort(key=lambda item: item[0])
        if [index for index, _ in indexed] != list(range(len(indexed))):
            raise FormProjectionError(
                "graph compatibility interval order is not contiguous"
            )
        self._intervals = tuple(interval for _, interval in indexed)
        return self._intervals


def _clock_bounds(position_values: Sequence[Any]) -> tuple[int, tuple[int, ...]]:
    """Decode clock cardinality and refined-gap bounds from graph positions."""
    encoded_gaps: dict[int, int] = {}
    for position in position_values:
        attributes = {
            attribute.name.local_name: int(attribute.lexical)
            for attribute in position.attributes
        }
        tick = attributes["tick"]
        encoded_gaps[tick] = max(encoded_gaps.get(tick, 0), attributes["gap"])
    tick_count = max(encoded_gaps, default=-1) + 1
    return tick_count, tuple(encoded_gaps[tick] for tick in range(tick_count))


@dataclass(frozen=True)
class _ClockPathProfile:
    """Bind ipakit clock spellings to authoritative tiergraph references."""

    text: str

    def bind(self, path: Any, graph: Any) -> Any:
        from tiergraph.path import PathOffender, PathRefusal, PathRefusalCode

        from tiergraph import DurableItemRef, ItemBinding, PositionBinding, PositionRef

        segments = path.segments

        def refuse(code: Any) -> None:
            raise PathRefusal(code, PathOffender(text=self.text, path=path))

        if len(segments) < 2 or segments[0] != "clock" or not segments[1].isdigit():
            refuse(PathRefusalCode.MALFORMED_POINTER)
        tick = int(segments[1])
        tick_count, gap_counts = _clock_bounds(graph.position_values)
        clock_positions = tuple(
            position
            for position in graph.position_values
            if any(
                attribute.name.local_name == "tick" for attribute in position.attributes
            )
        )
        clock_tier = next(
            tier for tier in graph.tiers if tier.declaration.name.local_name == "clock"
        )
        if tick >= tick_count:
            return PositionBinding(
                PositionRef(
                    clock_tier.declaration.name,
                    len(clock_tier.items) + 1,
                )
            )
        if len(segments) == 2:
            gap = 0
        elif len(segments) == 4 and segments[2] == "gaps" and segments[3].isdigit():
            gap = int(segments[3])
            if gap >= gap_counts[tick]:
                refuse(PathRefusalCode.POSITION_NOT_IN_PARENT)
        elif len(segments) == 4 and segments[3].isdigit():
            return ItemBinding(DurableItemRef(self.text))
        else:
            refuse(PathRefusalCode.MALFORMED_POINTER)
        for position in clock_positions:
            attributes = {
                attribute.name.local_name: int(attribute.lexical)
                for attribute in position.attributes
            }
            if attributes == {"gap": gap, "tick": tick}:
                return PositionBinding(position.reference)
        refuse(PathRefusalCode.OUT_OF_RANGE)

    def spell(self, binding: Any, graph: Any) -> Any:
        """Refuse reverse projection, which Form.at never requests."""
        from tiergraph.path import PathOffender, PathRefusal, PathRefusalCode

        del binding, graph
        raise PathRefusal(PathRefusalCode.UNSPELLABLE, PathOffender(text=self.text))

    def alternatives(self, owner: Any, relation: Any, graph: Any) -> tuple[Any, ...]:
        """Return no alternatives; this profile never binds that path kind."""
        del owner, relation, graph
        return ()


_AT_REFUSAL_PHRASES = {
    "malformed_pointer": "malformed JSON Pointer reference",
    "out_of_range": "dangling JSON Pointer reference",
    "unknown_form": "dangling JSON Pointer reference",
    "unknown_tier": "dangling JSON Pointer reference",
    "unknown_durable_item": "dangling JSON Pointer reference",
    "unknown_durable_anchor": "dangling JSON Pointer reference",
    "position_not_in_parent": "gap does not belong to named tick",
}


@dataclass(frozen=True)
class _FormGraphIndex:
    """Non-authoritative spelling and public-object index for one tg.Graph."""

    containment_input: Any
    inventory: IPAFeatures

    @classmethod
    def build(cls, scaffold: Any, inventory: IPAFeatures) -> _FormGraphIndex:
        from ._containment_projection import ContainmentProjectionInput

        return cls(ContainmentProjectionInput.capture(scaffold), inventory)

    def _memo(self, name: str, build: Callable[[], _T]) -> _T:
        cached = self.__dict__.get(name, _VIEW_ABSENT)
        if cached is _VIEW_ABSENT:
            cached = build()
            object.__setattr__(self, name, cached)
        return cast(_T, cached)

    @property
    def roots(self) -> tuple[str, ...]:
        return self._memo("_roots", lambda: tuple(self.containment_input.roots))

    @property
    def clock(self) -> tuple[Any, ...]:
        return self._memo("_clock", lambda: tuple(self.containment_input.clock))

    @property
    def events(self) -> Mapping[str, tuple[None, Any]]:
        def build() -> Mapping[str, tuple[None, Any]]:
            events = {
                path: (None, event)
                for path, event in self.containment_input.events.items()
            }
            return MappingProxyType(events)

        return self._memo("_events", build)

    @property
    def compatibility(self) -> _CompatibilityProjection:
        return self._memo(
            "_compatibility",
            lambda: _CompatibilityProjection(self.containment_input, self.inventory),
        )

    @property
    def units(self) -> tuple[Unit, ...]:
        return self._memo("_units", lambda: self.compatibility.units)

    @property
    def intervals(self) -> tuple[Interval, ...]:
        return self._memo("_intervals", lambda: self.compatibility.intervals)

    @property
    def dot(self) -> str:
        from .tiergraph_dot import dumps

        return self._memo("_dot", lambda: dumps(self.containment_input))

    @property
    def dot_with_empty_tiers(self) -> str:
        from .tiergraph_dot import dumps

        return self._memo(
            "_dot_with_empty_tiers",
            lambda: dumps(self.containment_input, include_empty_tiers=True),
        )

    def at(self, containment: Any, graph: Any, path: str) -> Any:
        """Parse ipakit spelling, but resolve event identity in ``graph``."""
        from tiergraph.path import PathRefusal

        from tiergraph import ResolvedItem, ResolvedPosition, resolve_path

        from ._tiergraph import GraphValidationError

        try:
            resolved = resolve_path(graph, _ClockPathProfile(path), path)
        except PathRefusal as exc:
            phrase = _AT_REFUSAL_PHRASES.get(exc.code.value)
            if phrase is None:
                raise
            raise GraphValidationError(f"{exc.offender.text!r}: {phrase}") from exc
        if isinstance(resolved, ResolvedItem):
            old = containment.new_to_old[resolved.current]
            return self.containment_input.events[old]
        assert isinstance(resolved, ResolvedPosition)
        attributes = {
            attribute.name.local_name: int(attribute.lexical)
            for position in graph.position_values
            if graph.resolve_position(position.reference) == resolved.current
            for attribute in position.attributes
        }
        return self.containment_input.clock[attributes["tick"]]

    def event_items(self, containment: Any, graph: Any) -> tuple[tuple[str, Any], ...]:
        """Return public event values after authoritative identity resolution."""
        from tiergraph import DurableItemRef

        out = []
        for path, (_, event) in self.events.items():
            expected = containment.old_to_new[path]
            if graph.resolve_item(DurableItemRef(path)) != expected:
                raise ValueError("authoritative durable identity changed coordinate")
            out.append((path, event))
        return tuple(out)


def _graph_from_compatibility(
    units: Sequence[Unit], intervals: Sequence[Interval]
) -> Any:
    """Build constructed/edited forms from units once, without lexical scanning."""
    from ._ipa_graph import BOUNDARY_TIER, SEGMENT_TIER, ZERO_TIER, declarations
    from ._tiergraph import Declarations, TierDeclaration
    from ._tiergraph import Timing as GraphTiming
    from ._tiergraph_builder import GraphBuilder

    inventory = _default(None)
    declared = declarations(inventory)
    known = {tier.name for tier in declared.tiers}
    extras = tuple(
        dict.fromkeys(span.tier for span in intervals if span.tier not in known)
    )
    if extras:
        permitted = frozenset(
            {"compatibility-interval", "compatibility-unit", "compatibility-index"}
        )
        declared = Declarations(
            tuple(TierDeclaration(name, permitted) for name in extras) + declared.tiers,
            declared.features,
            declared.relations,
            declared.closed,
        )
    builder = GraphBuilder(declared)
    allowed = {tier.name: tier.features for tier in declared.tiers}
    for index, unit in enumerate(units):
        base = {
            "spelling": unit.text,
            "input": True,
            # Keep the caller's frozen Unit as the compatibility projection.
            # Timing also lives structurally on the event, and the projection
            # only replaces this object when that structural value differs.
            "compatibility-unit": unit,
            "compatibility-index": index,
        }
        timing = (
            GraphTiming(unit.timing.start, unit.timing.duration)
            if unit.timing is not None
            else None
        )
        if unit.segment is not None:
            tier = SEGMENT_TIER
            facts = {
                **base,
                "value": unit.segment,
                "provenance": unit.provenance,
                **dict(unit.features),
                **dict(unit.prosody),
            }
            builder.append_input_atom(
                tier,
                cast(
                    Any,
                    {
                        key: value
                        for key, value in facts.items()
                        if key in allowed[tier]
                    },
                ),
                timing=timing,
            )
        elif unit.is_zero:
            tier = ZERO_TIER
            facts = {**base, "symbol": unit.text, **dict(unit.features)}
            builder.append_input_atom(
                tier,
                cast(
                    Any,
                    {
                        key: value
                        for key, value in facts.items()
                        if key in allowed[tier]
                    },
                ),
                timing=timing,
            )
        else:
            tier = BOUNDARY_TIER
            facts = {**base, "symbol": unit.text, **dict(unit.features)}
            builder.append_input_occurrence(
                tier,
                cast(
                    Any,
                    {
                        key: value
                        for key, value in facts.items()
                        if key in allowed[tier]
                    },
                ),
                refines_tick=True,
                timing=timing,
            )
    coordinates = builder.compatibility_coordinates()
    for index, span in enumerate(intervals):
        timing = (
            GraphTiming(span.timing.start, span.timing.duration)
            if span.timing is not None
            else None
        )
        builder.add_span(
            span.tier,
            coordinates.to_graph(span.start),
            coordinates.to_graph(span.end),
            {"compatibility-interval": index},
            timing=timing,
        )
    return builder.build()


@dataclass(frozen=True, eq=False)
class Form:
    """A transcription carrying everything it was written with.

    Immutable. :attr:`units` is the one sequence, and :attr:`segments`,
    :attr:`phones`, :attr:`attributes`, :attr:`boundaries` and
    :meth:`tree` are projections of it, each named for what it drops, none
    of them happening on the way in.

    :attr:`intervals` is the exception, and it is the only one. A span on a
    declared tier is **not derivable from the unit sequence** -- a mora, a
    gesture, or a syllable crossing a word boundary is delimited by no
    glyph -- so it is carried rather than computed. Two consequences, both
    of them the point rather than a wart:

    * :meth:`to_ipa` round-trips the **spelling**, and an interval is not
      spelled. ``Form.parse(f.to_ipa())`` gives back the units and no
      intervals, whatever ``f`` carried.
    * Nothing synthesizes one. A form with no dots has no syllable
      intervals rather than one, the same policy :meth:`tree` follows about
      an unspecified tier.
    """

    units: tuple[Unit, ...]
    #: Spans on declared tiers. Carried, never derived, never spelled.
    intervals: tuple[Interval, ...] = ()
    #: Exact source where unit-local spellings cannot reproduce its order.
    #: Constructed/edited forms leave this unset, preventing stale source.
    spelling: str | None = None

    def __post_init__(self) -> None:
        held_units = object.__getattribute__(self, "units")
        held_intervals = object.__getattribute__(self, "intervals")
        for span in held_intervals:
            if span.end > len(held_units):
                raise ValueError(
                    f"{span!r} runs past the {len(held_units)} units of the form"
                )
        object.__setattr__(self, "_compatibility_units", held_units)
        object.__setattr__(self, "_compatibility_intervals", held_intervals)
        self._install_scaffold(_graph_from_compatibility(held_units, held_intervals))
        # These names stay dataclass fields so the constructor,
        # dataclasses.fields/replace, equality, and hash behavior retain their
        # public coordinates.  The instance values are deliberately removed:
        # __getattribute__ below projects them from the graph store.
        object.__delattr__(self, "units")
        object.__delattr__(self, "intervals")

    def __getattribute__(self, name: str) -> Any:
        if name in {"units", "intervals"}:
            namespace = object.__getattribute__(self, "__dict__")
            index = namespace["_tiergraph_index"]
            return index.units if name == "units" else index.intervals
        return object.__getattribute__(self, name)

    def _identity(self) -> tuple[Any, ...]:
        namespace = object.__getattribute__(self, "__dict__")
        held_units = namespace.get("_compatibility_units")
        held_intervals = namespace.get("_compatibility_intervals")
        return (
            held_units if held_units is not None else self.units,
            held_intervals if held_intervals is not None else self.intervals,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Form):
            return NotImplemented
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

    @property
    def _graph(self) -> Any:
        """The one validated authoritative tiergraph graph."""
        namespace = object.__getattribute__(self, "__dict__")
        graph = namespace.get("_tiergraph_graph")
        if graph is None:
            from ._containment_projection import ContainmentProjection

            index = namespace["_tiergraph_index"]
            containment = ContainmentProjection.build_captured(index.containment_input)
            graph = containment.graph
            object.__setattr__(self, "_tiergraph_containment", containment)
            object.__setattr__(self, "_tiergraph_graph", graph)
        return graph

    def _install_scaffold(self, scaffold: Any) -> None:
        """Promote a build-only ipakit graph and immediately drop it."""
        inventory = next(
            (
                unit.__dict__["_inventory"]
                for node in scaffold.clock
                for group in node.groups
                for event in group.events
                if isinstance((unit := event.features.get("compatibility-unit")), Unit)
                and unit.segment is not None
                and unit.__dict__.get("_inventory") is not None
            ),
            _default(None),
        )
        index = _FormGraphIndex.build(scaffold, inventory)
        object.__setattr__(self, "_tiergraph_index", index)

    @classmethod
    def _from_graph(cls, graph: Any, spelling: str | None = None) -> Form:
        """Adopt a validated parser graph without rebuilding or rescanning it."""
        form = cls.__new__(cls)
        object.__setattr__(form, "spelling", spelling)
        form._install_scaffold(graph)
        return form

    @property
    def roots(self) -> tuple[str, ...]:
        """Canonical paths of the graph's declared traversal roots."""
        from tiergraph import DurableItemRef

        graph = self._graph
        containment = self._containment
        instances = tuple(
            relation
            for relation in graph.polyadic_relations
            if relation.declaration == containment.roots_name
        )
        if len(instances) != 1:
            raise ValueError(
                "authoritative graph must store exactly one roots instance"
            )
        roots = tuple(containment.new_to_old[target] for target in instances[0].targets)
        for path in roots:
            expected = containment.old_to_new[path]
            if graph.resolve_item(DurableItemRef(path)) != expected:
                raise ValueError(
                    "authoritative durable identity changed root coordinate"
                )
        return roots

    @property
    def _containment(self) -> ContainmentProjection:
        """The cached read-only tiergraph containment projection."""
        _ = self._graph
        return cast("ContainmentProjection", self.__dict__["_tiergraph_containment"])

    def direct_children(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        """Return the declared ordered children of ``parent``."""
        return self._containment.direct_children(parent, tier)

    def descendants(self, parent: str, tier: str | None = None) -> tuple[str, ...]:
        """Walk containment routes once each, optionally filtering by tier."""
        return self._containment.descendants(parent, tier)

    def leaves(self, parent: str) -> tuple[str, ...]:
        """Return expanded containment leaves in declared order."""
        return self._containment.leaves(parent)

    def parents(self, child: str) -> tuple[str, ...]:
        """Return every direct containment parent of ``child``."""
        return self._containment.parents(child)

    def ancestors(self, child: str) -> tuple[str, ...]:
        """Return every reachable containment ancestor once."""
        return self._containment.ancestors(child)

    def at(self, path: str) -> Any:
        """Return the graph element named by a canonical match path."""
        return self.__dict__["_tiergraph_index"].at(
            self._containment, self._graph, path
        )

    @classmethod
    def from_parsed(
        cls,
        source: str,
        parsed: Sequence[tuple[str, list[str]]],
        features: IPAFeatures,
        strict: bool = False,
    ) -> Form:
        """Build from the inventory's single canonical token scan.

        Strict construction resolves segment views eagerly, so resolution
        diagnostics fire here. Lax construction leaves them until first view
        access; spelling-only operations do not trigger them.

        The unit tiers built by this string-reading path contain only units on
        which a unit feature was asserted. In particular, the ``word`` tier is
        not an inventory of the words in the transcription: today it contains
        only words carrying asserted prominence.
        """
        from ._ipa_graph import (
            BOUNDARY_TIER,
            CLOCK_TREATMENTS,
            SEGMENT_TIER,
            ZERO_TIER,
            OccurrenceKind,
            declarations,
        )
        from ._tiergraph_builder import GraphBuilder

        out: list[Unit] = []
        graph_declarations = declarations(features)
        builder = GraphBuilder(graph_declarations)
        graph_features = graph_declarations._tier_by_name
        marks = boundary_marks(features)
        nulls = features.zeros
        edge = edge_level(features)
        aligned = features._raised_units_from_parsed(parsed, strict)
        word_parts: list[tuple[Any, str, int]] = []
        words: list[tuple[int, int, list[Any], str, str | None]] = []
        word_prominence: str | None = None

        def finish_word() -> None:
            nonlocal word_parts, word_prominence
            if not word_parts:
                return
            handles = [handle for handle, _, _ in word_parts]
            spelling = "".join(text for _, text, _ in word_parts)
            start = word_parts[0][2]
            end = word_parts[-1][2] + 1
            words.append((start, end, handles, spelling, word_prominence))
            word_parts = []
            word_prominence = None

        for token, segment, raised in aligned:
            if segment is not None:
                if not word_parts:
                    word_prominence = raised.get("prominence")
                segment_tick = builder.current_tick
                unit = _unit_for(segment, features)
                if strict:
                    _ = unit.prosody
                out.append(unit)
                segment_features = {
                    "value": segment,
                    "spelling": token,
                    "input": True,
                    "compatibility-unit": unit,
                    "compatibility-index": len(out) - 1,
                }
                handle = builder.append_input_atom(
                    SEGMENT_TIER,
                    cast(
                        Any,
                        {
                            key: value
                            for key, value in segment_features.items()
                            if key in graph_features[SEGMENT_TIER].features
                        },
                    ),
                )
                word_parts.append((handle, token, segment_tick))
            elif token and all(ch in features.stress_markers for ch in token):
                # Prefix attributes occupy no independent structural slot;
                # their spelling remains in ``spelling`` and their semantic
                # value rides on the segment they resolved to.
                continue
            elif token and all(ch in features.prominence_markers for ch in token):
                continue
            elif token in nulls:
                out.append(Unit(text=token, features=dict(nulls[token].features or {})))
                builder.append_input_atom(
                    ZERO_TIER,
                    {
                        "symbol": token,
                        "spelling": token,
                        "input": True,
                        "compatibility-unit": dataclasses.replace(out[-1], timing=None),
                        "compatibility-index": len(out) - 1,
                    },
                )
            elif token in features.separators:
                declared = features.separators[token]
                out.append(Unit(text=token, features=dict(declared.features or {})))
                treatment = CLOCK_TREATMENTS[OccurrenceKind.BOUNDARY]
                boundary_features = {
                    "symbol": token,
                    "spelling": token,
                    "input": True,
                    "compatibility-unit": dataclasses.replace(out[-1], timing=None),
                    "compatibility-index": len(out) - 1,
                    **dict(declared.features or {}),
                }
                builder.append_input_occurrence(
                    BOUNDARY_TIER,
                    cast(
                        Any,
                        {
                            key: value
                            for key, value in boundary_features.items()
                            if key in graph_features[BOUNDARY_TIER].features
                        },
                    ),
                    refines_tick=treatment.refines_tick,
                )
                level = (declared.features or {}).get("level")
                if level in features.features["level"].values:
                    if features.features["level"].values.index(
                        level
                    ) >= features.features["level"].values.index("word"):
                        finish_word()
            elif token in marks:
                out.append(Unit(text=token, features=dict(marks[token])))
                treatment = CLOCK_TREATMENTS[OccurrenceKind.BOUNDARY]
                boundary_features = {
                    "symbol": token,
                    "spelling": token,
                    "input": True,
                    "compatibility-unit": dataclasses.replace(out[-1], timing=None),
                    "compatibility-index": len(out) - 1,
                    **dict(marks[token]),
                }
                builder.append_input_occurrence(
                    BOUNDARY_TIER,
                    cast(
                        Any,
                        {
                            key: value
                            for key, value in boundary_features.items()
                            if key in graph_features[BOUNDARY_TIER].features
                        },
                    ),
                    refines_tick=treatment.refines_tick,
                )
                level = marks[token].get("level")
                if level in features.features["level"].values:
                    if features.features["level"].values.index(
                        level
                    ) >= features.features["level"].values.index("word"):
                        finish_word()
            elif token.isspace():
                finish_word()
                declared = features.separators["#"]
                out.append(
                    Unit(
                        text="#",
                        spelling=token,
                        features=dict(declared.features or {}),
                    )
                )
                treatment = CLOCK_TREATMENTS[OccurrenceKind.BOUNDARY]
                builder.append_input_occurrence(
                    BOUNDARY_TIER,
                    {
                        "symbol": "#",
                        "spelling": token,
                        "input": True,
                        "level": edge,
                        "compatibility-unit": dataclasses.replace(out[-1], timing=None),
                        "compatibility-index": len(out) - 1,
                    },
                    refines_tick=treatment.refines_tick,
                )

        finish_word()
        for start, end, children, spelling, prominence in words:
            if prominence is None:
                continue
            facts: dict[str, Any] = {"spelling": spelling}
            if prominence is not None:
                facts["prominence"] = prominence
            word = builder.add_event("word", start, facts, duration=end - start)
            builder.contain(word, children)

        local = spell(out)
        scanned = "".join(base + "".join(diacritics) for base, diacritics in parsed)
        return cls._from_graph(
            builder.build(), spelling=scanned if scanned != local else None
        )

    @classmethod
    def parse(
        cls,
        text: str,
        features: IPAFeatures | None = None,
        strict: bool = False,
        *,
        segmented: bool = False,
        wild: bool = False,
    ) -> Form:
        """Read a transcription without projecting anything away.

        ``strict=True`` resolves every segment view eagerly, so resolution
        diagnostics fire during parsing. Lax parsing defers them until the
        first view access; :meth:`to_ipa` alone does not trigger them.

        No interval is derived from the separators. The dot is optional
        notation, so reading one as a syllable interval would state a claim
        the transcription never made -- and a transcription that *does*
        state its tiers hands them in with :meth:`of`.
        """
        return _default(features).read(
            text, strict=strict, segmented=segmented, wild=wild
        )

    @classmethod
    def of(cls, items: Sequence[Unit], intervals: Sequence[Interval] = ()) -> Form:
        """Wrap a unit sequence that has already been read."""
        return cls(units=tuple(items), intervals=tuple(intervals))

    # -- the faithful read ------------------------------------------------

    def to_ipa(self, mode: str = "exact") -> str:
        """Every position, spelled back. Round-trips what was *spelled*.

        Not every position the form carries: an interval is not spelled, so
        it does not come back through a round-trip through the string. That
        is a fact about the notation rather than a loss here -- there is no
        agreed way to write a mora interval into a transcription, and
        inventing one would put a claim in the string that nothing reads.
        """
        if mode == "exact":
            return self.spelling if self.spelling is not None else spell(self.units)
        if mode == "canonical":
            from ._codecs import ipa_profile, render_graph

            return render_graph(self, ipa_profile(exact=False))
        raise ValueError("IPA spelling mode must be 'exact' or 'canonical'")

    def to_dict(self, self_contained: bool = False) -> dict[str, Any]:
        """Serialize the versioned representation.

        The default is lean: structured segments carry no redundant resolved
        views. ``self_contained=True`` embeds those views for readers without
        the declaring inventory. Boundaries and zeros always carry their
        declared features because they have no segment to derive them from.
        """

        _ = self._graph

        def encode_unit(unit: Unit) -> dict[str, Any]:
            encoded: dict[str, Any] = {
                "text": unit.text,
                "segment": (
                    unit.segment.to_dict() if unit.segment is not None else None
                ),
                "timing": (
                    {"start": unit.timing.start, "duration": unit.timing.duration}
                    if unit.timing is not None
                    else None
                ),
            }
            if unit.spelling is not None:
                encoded["spelling"] = unit.spelling
            if unit.segment is None or self_contained:
                encoded.update(
                    {
                        "features": dict(unit.features),
                        "prosody": dict(unit.prosody),
                        "provenance": [list(item) for item in unit.provenance],
                    }
                )
            return encoded

        return {
            "type": _JSON_TYPE,
            "v": _JSON_VERSION,
            "units": [encode_unit(unit) for unit in self.units],
            "intervals": [
                {
                    "tier": span.tier,
                    "start": span.start,
                    "end": span.end,
                    "timing": (
                        {
                            "start": span.timing.start,
                            "duration": span.timing.duration,
                        }
                        if span.timing is not None
                        else None
                    ),
                }
                for span in self.intervals
            ],
            "spelling": self.spelling,
        }

    def to_json(self, self_contained: bool = False) -> str:
        """Return the complete, versioned representation as JSON."""
        return json.dumps(
            self.to_dict(self_contained=self_contained), ensure_ascii=False
        )

    def to_dot(self, *, include_empty_tiers: bool = False) -> str:
        """Render the used tiers as deterministic Graphviz DOT.

        By default, rows answer which tiers this form uses. Set
        ``include_empty_tiers`` to show every tier its model permits.
        """
        from .tiergraph_dot import to_dot

        _ = self._graph
        return to_dot(self, include_empty_tiers=include_empty_tiers)

    @classmethod
    def from_dict(
        cls, obj: Mapping[str, Any], features: IPAFeatures | None = None
    ) -> Form:
        """Restore a form without reparsing its IPA surface spelling.

        A lean document derives all its views coherently from this restoring
        inventory. Use the self-contained mode to pin views across inventories.
        """
        if obj.get("type") != _JSON_TYPE:
            raise ValueError(f"unsupported representation type: {obj.get('type')!r}")
        if obj.get("v") != _JSON_VERSION:
            raise ValueError(f"unsupported Form JSON version: {obj.get('v')!r}")
        inventory = _default(features)
        from .segment import Segment

        restored: list[Unit] = []
        for raw in obj.get("units", ()):
            segment_data = raw.get("segment")
            timing_data = raw.get("timing")
            segment = (
                Segment.from_dict(segment_data, inventory)
                if segment_data is not None
                else None
            )
            has_views = any(key in raw for key in ("features", "prosody", "provenance"))
            supplied = (
                dict(raw.get("features", {})),
                dict(raw.get("prosody", {})),
                tuple(tuple(item) for item in raw.get("provenance", ())),
            )
            view_arguments: dict[str, Any] = (
                {
                    "features": supplied[0],
                    "prosody": supplied[1],
                    "provenance": supplied[2],
                }
                if segment is None or has_views
                else {}
            )
            unit = Unit(
                text=raw["text"],
                spelling=raw.get("spelling"),
                segment=segment,
                timing=(
                    Timing(timing_data["start"], timing_data["duration"])
                    if timing_data is not None
                    else None
                ),
                _inventory=inventory if segment is not None else None,
                **view_arguments,
            )
            restored.append(unit)
        intervals = tuple(
            Interval(
                raw["tier"],
                raw["start"],
                raw["end"],
                inventory,
                (
                    Timing(raw["timing"]["start"], raw["timing"]["duration"])
                    if raw.get("timing") is not None
                    else None
                ),
            )
            for raw in obj.get("intervals", ())
        )
        spelling = obj.get("spelling")
        if spelling is not None and not isinstance(spelling, str):
            raise ValueError("Form spelling must be a string or null")
        return cls(tuple(restored), intervals, spelling)

    @classmethod
    def from_json(cls, data: str, features: IPAFeatures | None = None) -> Form:
        """Restore :meth:`to_json` output without a lossy IPA round trip.

        A lean document derives all its views coherently from this restoring
        inventory. Self-contained JSON pins those views across inventories.
        """
        return cls.from_dict(json.loads(data), features)

    # -- projections, each named for what it drops -------------------------

    @property
    def segments(self) -> tuple[Segment, ...]:
        """Sounds only; boundaries dropped.

        What :func:`ipakit.segments` returns, except that here the
        dropping is the caller's choice and :attr:`boundaries` still
        holds what went.
        """
        return tuple(u.segment for u in self.units if u.segment is not None)

    @property
    def phones(self) -> tuple[str, ...]:
        """Phone identity names; boundaries and prosody dropped.

        ``ˈa`` and ``aː`` both read as ``a``, because prosody is not
        part of a phone's identity.

        Filtered on carrying a segment rather than on not being a
        boundary, so a structural zero drops out here too: it is a
        position, not a sound, and there is no phone name to give it.
        """
        return tuple(u.core for u in self.units if u.segment is not None)

    @property
    def attributes(self) -> tuple[Attribute, ...]:
        """What :attr:`phones` drops: the values attached to segments.

        The counterpart of :attr:`boundaries`. :attr:`segments` keeps
        these -- prosody rides on the ``Segment`` -- so this is the
        record of what the *identity* projection lets go.
        """
        out: list[Attribute] = []
        index = 0
        for unit in self.units:
            # ``at`` indexes :attr:`segments`, so only a position that
            # contributes one may advance it: a zero carries no segment
            # and would walk every later attribute one place right.
            if unit.segment is None:
                continue
            for glyph, feature, value in unit.provenance:
                out.append(
                    Attribute(feature=feature, value=value, at=index, glyph=glyph)
                )
            index += 1
        return tuple(out)

    def tree(self, features: IPAFeatures | None = None) -> Node:
        """The transcription as a tree, nested by declared boundary level.

        The flat string is a projection of this: ``#`` and ``.`` are
        nesting depth written on one line. The levels come from
        :func:`levels`, so the shape is generated from ``ipa.xml`` rather
        than stated here. They are levels and not :func:`tier_names`:
        this tree nests, and a tier does not.

        Each node records which delimiter supplied each end of its span
        (:attr:`Node.opened_by`, :attr:`Node.closed_by`), ``None`` being
        the form edge. That is provenance, not shape -- the endpoints are
        the same either way.
        """
        order = levels(features)
        edge = edge_level(features)
        # Paired with the one read of where the boundaries sat, rather
        # than a second walk computing 'at' again: the two are in the
        # same order by construction, so they cannot disagree.
        found = iter(self.boundaries)
        tagged = [(u, next(found) if u.is_boundary else None) for u in self.units]

        def build(
            items: Sequence[tuple[Unit, Boundary | None]],
            depth: int,
            opened: Boundary | None,
            closed: Boundary | None,
        ) -> tuple[Node, ...]:
            if depth == len(order):
                return tuple(
                    Node(level="segment", unit=u) for u, _ in items if not u.is_boundary
                )
            level = order[depth]
            # A level exists only where a boundary asserts it. With the
            # dot optional, a word written without one has *unspecified*
            # syllabification, not one syllable, and inventing a node
            # here would state a claim the transcription never made. The
            # level the form's edges delimit is the exception, and it is
            # the one a separator spells (:func:`edge_level`) rather than
            # whichever happens to be outermost: declaring a level above
            # 'word' must not stop '#'-less input from having a word.
            if level != edge and not any(
                u.is_boundary and u.level == level for u, _ in items
            ):
                return build(items, depth + 1, opened, closed)
            groups: list[list[tuple[Unit, Boundary | None]]] = [[]]
            # A skipped level hands its brackets down, and a split hands
            # the splitting boundary to both sides: an inner node's edges
            # are its parent's until something is written between them.
            opens: list[Boundary | None] = [opened]
            closes: list[Boundary | None] = []
            for unit, boundary in items:
                if unit.is_boundary and unit.level == level:
                    closes.append(boundary)
                    opens.append(boundary)
                    groups.append([])
                else:
                    groups[-1].append((unit, boundary))
            closes.append(closed)
            return tuple(
                Node(
                    level=level,
                    children=build(group, depth + 1, opener, closer),
                    opened_by=opener,
                    closed_by=closer,
                )
                # strict: one opener and one closer per group by
                # construction, and a mismatch would silently mis-bracket.
                for group, opener, closer in zip(groups, opens, closes, strict=True)
                if any(not u.is_boundary for u, _ in group)
            )

        return Node(level="form", children=build(tagged, 0, None, None))

    @property
    def boundaries(self) -> tuple[Boundary, ...]:
        """What the projections drop, and where it sat."""
        out: list[Boundary] = []
        seen = 0
        for unit in self.units:
            if unit.is_boundary:
                out.append(
                    Boundary(
                        text=unit.spelling if unit.spelling is not None else unit.text,
                        level=unit.level or "word",
                        at=seen,
                        features=dict(unit.features),
                    )
                )
            elif unit.segment is not None:
                # ``at`` indexes :attr:`segments`, the same rule
                # :attr:`attributes` counts by: a structural zero is a
                # position in the form and none in the projection, so
                # letting it advance the count put every later boundary
                # one place right and ``rebuild`` spelled it there.
                seen += 1
        return tuple(out)

    # -- putting a projection back together --------------------------------

    @classmethod
    def rebuild(
        cls,
        segments: Sequence[Segment],
        boundaries: Sequence[Boundary],
        intervals: Sequence[Interval] = (),
        features: IPAFeatures | None = None,
    ) -> Form:
        """Reassemble a form from a segmental projection and its boundaries.

        The inverse of taking :attr:`segments` and :attr:`boundaries`
        apart, so collapsing a form is recoverable rather than final.

        The inverse of *those two projections*, which is not the inverse
        of the form. A structural zero is neither a sound nor a relation,
        so neither projection carries it and a form holding one comes back
        without it. What does survive is where everything sat:
        :attr:`Boundary.at` counts the segments before the mark, the same
        sequence it is used to index, so a zero does not walk a later
        boundary along it.

        ``intervals`` is the third **data** argument and it sits beside
        that asymmetry rather than repairing it. An interval is not
        derivable from a sound or a relation, so it has to be handed in;
        and it indexes the unit sequence of the form being built, which is
        the caller's to get right. Where the sequence handed in differs
        from the one the intervals were taken off -- a dropped zero, a
        collapsed boundary -- the endpoints are stale, and a stale endpoint
        past the end is refused here rather than carried. Rebasing an
        interval under an edit is not this: it is a separate operation over
        what the edit says moved.

        The boundary unit is put back from everything the boundary
        carries, which is why :attr:`Boundary.features` exists. Rebuilding
        it from :attr:`Boundary.level` alone spelled the mark right and
        described it wrong: ``|`` came back declaring a bare level and no
        ``break=minor``, and ``‿`` came back as a plain word boundary with
        its ``linking=+`` gone -- the same spelling, a different unit. A
        level is used only where the boundary was hand-made and states
        nothing else.
        """
        features = _default(features)
        placed: dict[int, list[Boundary]] = {}
        for boundary in boundaries:
            placed.setdefault(boundary.at, []).append(boundary)

        out: list[Unit] = []
        for index in range(len(segments) + 1):
            for boundary in placed.get(index, ()):
                declared = dict(boundary.features) or {"level": boundary.level}
                out.append(
                    Unit(
                        text="#" if boundary.text.isspace() else boundary.text,
                        spelling=boundary.text if boundary.text.isspace() else None,
                        features=declared,
                    )
                )
            if index < len(segments):
                out.append(_unit_for(segments[index], features))
        return cls(units=tuple(out), intervals=tuple(intervals))

    def without_boundaries(self) -> Form:
        """This form with its boundary positions removed.

        Named so the collapse is visible at the call site.

        Refused where the form carries an interval, because removing a
        position moves every index after it and an interval indexes
        positions. Returning the intervals unchanged would spell the same
        sounds and describe a different span -- the silent wrong answer
        this module is built to avoid -- and shifting them is rebasing,
        which belongs to whatever knows what moved.
        """
        if self.intervals:
            raise ValueError(
                "removing boundaries moves the positions "
                f"{len(self.intervals)} interval(s) index; rebase them first"
            )
        return Form(units=tuple(u for u in self.units if not u.is_boundary))

    # -- sequence behavior ------------------------------------------------

    def __iter__(self) -> Iterator[Unit]:
        return iter(self.units)

    def __len__(self) -> int:
        return len(self.units)

    def __getitem__(self, index: int) -> Unit:
        return self.units[index]

    def __str__(self) -> str:
        return self.to_ipa()

    def __repr__(self) -> str:
        held = f"{len(self.units)} units"
        if self.intervals:
            held += f", {len(self.intervals)} intervals"
        return f"Form({self.to_ipa()!r}, {held})"
