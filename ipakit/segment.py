"""Structured segment representation: constituents bound by typed junctures.

A parsed unit is stored as its flat chain — constituents (base phone +
modifier stack) joined by typed junctures (``Sense.FUSE`` for the over-tie,
``Sense.SEQ`` for the under-tie) — plus unit-level prosody. Everything else
is a derived read: the grouping (``children``), the classification
(``kind``), the union feature bag (``bag``), the flat scalar projection
(``scalar``), and the emitted string (``to_ipa``). Nothing is decided at
merge time. See docs/ties.md for the tie conventions.

Serialization: ``to_json``/``from_json`` carry the junctures explicitly and
are the round-trip-guaranteed form. ``to_ipa`` emits sense-correct glyphs
and is lossy exactly on the legacy alias collisions (an intentional
simultaneous ``a+ɪ`` emits ``a͡ɪ``, which re-ingests as the registered
sequential diphthong).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .constants import METADATA_ATTRS

if TYPE_CHECKING:  # pragma: no cover
    from ._base import IPAFeaturesBase
    from .features import IPAFeatures

_JSON_VERSION = 1

# The natural class a phased unit's classification asks about, declared over
# the manner values in the data (nasals are sonorants, so "obstruent" is
# already the oral one).
_OBSTRUENT = "obstruent"


class Sense(StrEnum):
    """Juncture sense: what a tie asserts about timing."""

    FUSE = "fuse"  # one timing slot
    SEQ = "seq"  # several slots bound into one unit

    def glyph(self, features: IPAFeaturesBase | None = None) -> str:
        """The character spelling this sense, asked of the declaration.

        A sense is this library's own classification; which glyph writes
        it is ipa.xml's, so the pairing is read from the inventory rather
        than pasted here. ``features`` is optional because a ``Segment``
        may be rebuilt from JSON without one, and a unit with no
        inventory has only the bundled one to be spelled in.
        """
        if features is None:
            from ._convert import ipa_features

            features = ipa_features()
        return features.tie_bar if self is Sense.FUSE else features.seq_tie


class Kind(StrEnum):
    """Derived classification of a unit (design spec section 5)."""

    ATOMIC = "atomic"
    AFFRICATE = "affricate"
    PRENASALIZED = "prenasalized"
    PRE_STOPPED = "pre-stopped"
    LATERAL_RELEASE = "lateral-release"
    CLICK_ACCOMPANIMENT = "click-accompaniment"
    DOUBLE_ARTICULATION = "double-articulation"
    OVERLAY = "overlay"
    DIPHTHONG = "diphthong"
    CHAIN = "chain"


def modifier_mode(features: IPAFeaturesBase, symbol: str) -> str:
    """Contribution mode of a diacritic/suprasegmental symbol.

    One of the modes the data declares (``structural``, ``prosodic``,
    ``release``, ``secondary``, ``overriding``, ``additive``), read off
    the mark's own feature keys: a mark is a release phase because it says
    ``release=...`` and a secondary articulation because it says
    ``velarized=...``. Declaration order in ``<modes>`` is precedence, so
    the first mode any of the mark's keys claims wins. No symbol is
    classified by name, and no table here restates which key means what.

    Takes the mixin base rather than ``IPAFeatures``: it reads only the
    diacritic table, so the mixins can call it on ``self``.
    """
    mark = features.diacritics.get(symbol)
    keys = set(mark.features) - METADATA_ATTRS - {"class"} if mark else set()
    by_mode = features.features_by_mode
    for mode in features.modes:
        if keys & by_mode.get(mode, frozenset()):
            return mode
    return features.default_mode


def check_prosody(features: IPAFeaturesBase, prosody: Iterable[str]) -> None:
    """Validate a unit's prosody: what may stand in it, and how much.

    Two rules, one place, so every construction path states them the
    same way. Structural marks are not prosody -- a tie is a juncture
    and a break lives between units, neither of them a property of one.
    And stress is one feature of one syllable: a unit states at most one
    level of it, because two marks on one unit is a contradiction rather
    than a stack.
    """
    seen_stress: list[str] = []
    for mark in prosody:
        if modifier_mode(features, mark) == "structural":
            raise ValueError(
                f"structural mark {mark!r} is not prosody; "
                "ties are junctures, breaks live between units"
            )
        if mark in features.stress_markers:
            seen_stress.append(mark)
    if len(seen_stress) > 1:
        raise ValueError(
            f"a unit bears one stress level, got {seen_stress!r}: "
            "stress is single-valued, so these contradict rather than stack"
        )


def _is_non_speech(features: IPAFeatures, feats: dict[str, str]) -> bool:
    """True for a bundle whose manner holds no position on the
    constriction axis (silence): not a speech sound, so the articulatory
    defaults do not apply to it. Filling them would make silence *match*
    every phone on every unremarkable binary and dilute the one real
    difference; leaving them out keeps silence maximally distant, so
    substituting it for a phone costs what deleting the phone costs.
    """
    manner_feature = features.features.get("manner")
    manner = feats.get("manner")
    return bool(
        manner_feature is not None
        and manner is not None
        and manner in manner_feature.offscale
    )


def takes_defaults(features: IPAFeatures, feats: Mapping[str, str]) -> bool:
    """Whether a bundle is a speech segment, and so takes declared defaults.

    :func:`fill_defaults` asks this of a feature bag and
    :meth:`~ipakit.IPAFeatures._prosody_asked` asks it of the same bag
    before filling the *prosody* beside it, so a bundle cannot be
    articulatorily bare and prosodically furnished. Silence answers no
    here, and so does a position that is not a segment at all -- a
    declared zero carries a ``class`` and nothing to constrict with.
    """
    return feats.get("manner") is not None and not _is_non_speech(features, dict(feats))


def apply_modifiers(
    features: IPAFeatures,
    feats: dict[str, str],
    modifiers: Iterable[str],
    prosody: bool = False,
) -> dict[str, str]:
    """Overlay a modifier stack onto a base bundle, per mark, by mode.

    The single implementation of what a diacritic contributes, so the
    flat projection and the structured bundle cannot disagree about one
    mark. Overriding marks replace their base's value (the devoicing
    ring makes ``d̥`` voiceless, never both-voiced); additive, secondary
    and release marks add only keys the base leaves unstated -- a
    release-phase mark describes a phase, not the whole segment, so the
    glottal phase of ``tˀ`` never makes the ``t`` glottal. Structural
    and prosodic marks contribute nothing to a feature bag: ties are
    junctures and prosody lives on the unit.

    ``prosody=True`` is for the one read that has no unit level to put a
    prosodic mark on -- :meth:`IPAFeatures.compose_segments` returns one
    flat bundle per token, so ``eː`` has nowhere but the bundle to carry
    its length. That is the documented divergence between ``compose()``
    and ``scalar()``, and it stays exactly that one thing.

    Metadata (``name``/``class``/``href``/``xsampa``) never crosses.
    Those attributes name a *symbol*, and the symbol a unit's metadata
    describes is its base, not the mark riding on it -- the article for
    ``tʰ`` is the one for ``t``, not the one for aspiration.

    Mutates and returns ``feats``. Defaults must not be filled before
    this runs: a mark adding a feature the base leaves unstated
    (nasalization on a vowel) would otherwise find the default already
    sitting in the slot.
    """
    for mod in modifiers:
        mark = features.diacritics.get(mod)
        if mark is None:
            continue
        mode = modifier_mode(features, mod)
        if mode == "structural" or (mode == "prosodic" and not prosody):
            continue
        for key, value in mark.features.items():
            if key in METADATA_ATTRS:
                continue
            if mode == "overriding":
                feats[key] = value
            else:
                feats.setdefault(key, value)
    return feats


def fill_defaults(features: IPAFeatures, feats: dict[str, str]) -> dict[str, str]:
    """Fill each still-unset feature with its declared default.

    Skipped entirely for a non-speech bundle (see :func:`_is_non_speech`).
    Mutates and returns ``feats``.

    A ``mode="prosodic"`` default lands here too, and it is the one kind
    that does not belong: prosody is not in this bag by design, so a
    ``length`` sitting in it can only ever say ``normal``, which is right
    for ``a`` and wrong for ``aː``. :func:`~ipakit.form._segmental` takes
    those keys back out of ``Unit.features`` for that reason, and no query
    reads them here -- a prosodic term is put to the unit's prosody, where
    :meth:`~ipakit.IPAFeatures._prosody_asked` fills the same declared
    default. What they are still doing is sitting in the metric's
    comparison bundle, where an always-agreeing key is a term in the
    denominator of every distance: taking them out moves 9413 pairs of
    9591, which is a change to the metric and not to a query, and is not
    made here.
    """
    if _is_non_speech(features, feats):
        return feats
    for name, feat in features.features.items():
        if name not in feats and feat.default is not None:
            feats[name] = feat.default
    return feats


def flat_projection(
    features: IPAFeatures,
    bundles: Sequence[dict[str, str]],
    junctures: Sequence[Sense],
) -> dict[str, str]:
    """The flat projection of one unit, from its constituents' bundles.

    The single implementation of what a composed unit looks like when it
    is read as one bundle: :meth:`Segment.scalar` calls it over parsed
    constituents and :meth:`IPAFeatures._compose_tie_bar_features` over
    the parts of a tie-chain string, so the flat entry points and the
    structured ones cannot answer differently about one unit.

    Each bundle is a constituent's *own* explicit features -- base plus
    the marks written on that constituent, per :func:`part_bundle` --
    never defaulted, because a default sitting in a slot would beat a
    later constituent's silence there.

    Two rules, in this order:

    A sequential (under-tie) chain projects its **first block**: the run
    up to the first ``SEQ`` juncture. That is the encoding the registered
    diphthongs use; the chain's other constituents stay recoverable from
    the token, not from this flat projection. So a mark written on a
    later block does not reach the projection at all -- ``a͜ɪ̃`` projects
    ``a``, and ``t͡s͜ã`` projects the affricate.

    The block then merges left to right, last constituent wins. An
    affricate takes the place of its release (``t͡ʃ`` is postalveolar,
    from ``ʃ``), and a mark on an earlier constituent survives only where
    the later ones state nothing -- which is exactly why ``kʷ͡p`` keeps
    ``labialized='+'`` while ``t̪͡s`` is alveolar, not dental. A differing
    manner across the block collapses to "affricate"; same-manner parts
    with different places are a double articulation, spelled with the
    canonical combining value.

    ``href`` is dropped from any composed unit: it names a specific
    Wikipedia article for a symbol, and an ad hoc compound has none.

    Returns a fresh dict; the inputs are not mutated.
    """
    composed = bool(junctures)
    if Sense.SEQ in junctures:
        bundles = list(bundles)[: list(junctures).index(Sense.SEQ) + 1]
    feats: dict[str, str] = {}
    manners: set[str | None] = set()
    places: list[str] = []
    for bundle in bundles:
        manners.add(bundle.get("manner"))
        if "place" in bundle:
            places.append(bundle["place"])
        feats.update(bundle)
    if composed:
        feats.pop("href", None)
    if len(manners) > 1:
        feats["manner"] = "affricate"
    elif len(set(places)) > 1:
        # A same-manner multi-place fusion is a double articulation; its
        # place is the canonical combining spelling (components ordered
        # by scale position): any pair, not just the pre-named ones.
        place_feature = features.features.get("place")
        if place_feature is not None:
            feats["place"] = place_feature.combine(tuple(places))
    return feats


def part_bundle(features: IPAFeatures, constituent: Constituent) -> dict[str, str]:
    """One constituent's own explicit bundle, undefaulted, with the base's
    metadata kept.

    The input to :func:`flat_projection`, and the reason a mark reaches
    the merge as part of its own constituent rather than as an overlay
    applied after it.

    Metadata rides along here where :meth:`Constituent.bundle` drops it,
    because the flat read of a marked unit *is* its base's entry: the
    article for ``tʰ`` is the one for ``t``. A feature bag has no use for
    it, so ``bag()`` and the metric keep taking the stripped bundle.
    """
    return constituent.bundle(features, with_defaults=False, metadata=True)


@dataclass(frozen=True)
class Constituent:
    """A base phone plus its ordered modifier stack."""

    base: str
    modifiers: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.base + "".join(self.modifiers)

    def bundle(
        self,
        features: IPAFeatures,
        with_defaults: bool = True,
        metadata: bool = False,
    ) -> dict[str, str]:
        """Phonetic feature bundle, assembled in the contracted order.

        (1) the base's explicit features; (2) modifier contributions per
        mode — overriding replaces, everything else adds only keys not yet
        present; (3) defaults fill keys still missing. Defaults never apply
        to modifier projections, so a sparse modifier stays sparse.

        ``metadata=True`` keeps the base's ``class``/``href``/``xsampa``
        instead of dropping them; only the flat projection asks for that
        (see :func:`part_bundle`). A mark never contributes metadata
        either way.
        """
        base_phone = features.get_phone(self.base)
        feats: dict[str, str] = {}
        if base_phone is not None:
            drop = frozenset() if metadata else METADATA_ATTRS
            feats = {k: v for k, v in base_phone.features.items() if k not in drop}
        apply_modifiers(features, feats, self.modifiers)
        if with_defaults:
            fill_defaults(features, feats)
        return feats


@dataclass(frozen=True)
class Segment:
    """One unit: constituents joined by typed junctures, plus prosody.

    Structural equality covers ``constituents``, ``junctures``, and
    ``prosody``; ``to_ipa()`` output is deliberately not an equality proxy
    (two structurally different intents can share a spelling).
    """

    constituents: tuple[Constituent, ...]
    junctures: tuple[Sense, ...] = ()
    prosody: tuple[str, ...] = ()
    _features: IPAFeatures | None = field(
        default=None, compare=False, repr=False, hash=False
    )

    def __post_init__(self) -> None:
        if not self.constituents:
            raise ValueError("a Segment needs at least one constituent")
        if len(self.junctures) != len(self.constituents) - 1:
            raise ValueError(
                f"{len(self.constituents)} constituents need "
                f"{len(self.constituents) - 1} junctures, "
                f"got {len(self.junctures)}"
            )

    # -- derived reads --------------------------------------------------------

    @property
    def sense(self) -> Sense | None:
        """The loosest juncture in the unit (None for an atomic unit)."""
        if not self.junctures:
            return None
        return Sense.SEQ if Sense.SEQ in self.junctures else Sense.FUSE

    def _require_features(self) -> IPAFeatures:
        if self._features is None:
            raise ValueError(
                "this Segment is not bound to an IPAFeatures instance; "
                "construct it via IPAFeatures.segment()/build_segment()"
            )
        return self._features

    def _manner(self, constituent: Constituent) -> str | None:
        phone = self._require_features().get_phone(constituent.base)
        return phone.features.get("manner") if phone else None

    def _vocalic(self, constituent: Constituent) -> bool:
        return self._manner(constituent) == "vowel"

    def _airstream(self, constituent: Constituent) -> str | None:
        phone = self._require_features().get_phone(constituent.base)
        return phone.features.get("airstream") if phone else None

    def _phase_blocks(self) -> list[tuple[int, int]]:
        """Maximal same-manner runs of constituents, as (start, end) slices."""
        blocks: list[tuple[int, int]] = []
        start = 0
        for i in range(1, len(self.constituents)):
            if self._manner(self.constituents[i]) != self._manner(
                self.constituents[start]
            ):
                blocks.append((start, i))
                start = i
        blocks.append((start, len(self.constituents)))
        return blocks

    def _sub(self, start: int, end: int) -> Segment:
        return Segment(
            constituents=self.constituents[start:end],
            junctures=self.junctures[start : end - 1],
            _features=self._features,
        )

    @property
    def children(self) -> tuple[Segment, ...]:
        """Top-level operands of the derived grouping.

        SEQ-containing unit: its maximal FUSE runs (and lone constituents).
        Pure-FUSE unit with two or more phase blocks: those blocks. Pure-FUSE
        unit with one block (e.g. k͡p): its atomic constituents directly —
        the degenerate block layer is skipped, so traversal terminates.
        Atomic unit: ().
        """
        if len(self.constituents) == 1:
            return ()
        if Sense.SEQ in self.junctures:
            runs: list[Segment] = []
            start = 0
            for i, j in enumerate(self.junctures):
                if j is Sense.SEQ:
                    runs.append(self._sub(start, i + 1))
                    start = i + 1
            runs.append(self._sub(start, len(self.constituents)))
            return tuple(runs)
        blocks = self._phase_blocks()
        if len(blocks) >= 2:
            return tuple(self._sub(s, e) for s, e in blocks)
        return tuple(self._sub(i, i + 1) for i in range(len(self.constituents)))

    @property
    def left(self) -> Segment:
        children = self.children
        return children[0] if children else self

    @property
    def right(self) -> Segment:
        children = self.children
        return children[-1] if children else self

    def __getitem__(self, index: int) -> Segment:
        children = self.children
        if not children:
            if index in (0, -1):
                return self
            raise IndexError(index)
        return children[index]

    def left_features(self, with_defaults: bool = True) -> dict[str, str]:
        """Flat features of the left edge: the leftmost top-level child.

        For ``t͡s͜a`` this is the affricate's feature read; for an atomic
        unit it is the unit's own features. The edge reads are how
        computation approaches a composed unit from one side instead of
        through the whole-unit projection.
        """
        return self.left.scalar(with_defaults=with_defaults)

    def right_features(self, with_defaults: bool = True) -> dict[str, str]:
        """Flat features of the right edge: the rightmost top-level child."""
        return self.right.scalar(with_defaults=with_defaults)

    def disagreements(self) -> dict[str, tuple[str, ...]]:
        """Features whose values differ across this unit's constituents.

        A diagnostic *read* over the union bag -- composition never
        referees agreement (a voicing-disagreeing tie like ``t͡ɮ`` is
        reported, not rejected), and structural multi-valuedness is
        included (a double articulation naturally "disagrees" in place).
        Empty for an atomic unit.
        """
        return {k: v for k, v in self.bag().items() if len(v) > 1}

    def distance(self, other: Segment) -> float:
        """Structural distance to another Segment, in [0, 1] (the metric
        of design spec section 7; see ipakit.metric)."""
        from .metric import segment_metric

        return segment_metric(self._require_features(), self, other)

    def features_at(self, index: int, with_defaults: bool = True) -> dict[str, str]:
        """Flat features of the index-th top-level child (edge reads
        generalized to any position in an n-ary unit)."""
        return self[index].scalar(with_defaults=with_defaults)

    @property
    def kind(self) -> Kind:
        """Total classification (design spec section 5)."""
        if len(self.constituents) == 1:
            return Kind.ATOMIC
        if Sense.SEQ in self.junctures:
            if all(self._vocalic(c) for c in self.constituents):
                return Kind.DIPHTHONG
            return Kind.CHAIN
        features = self._require_features()
        manner_feature = features.features.get("manner")
        obstruent = (
            manner_feature.value_classes.get(_OBSTRUENT, frozenset())
            if manner_feature is not None
            else frozenset()
        )
        blocks = self._phase_blocks()
        manners = [self._manner(self.constituents[s]) for s, _ in blocks]
        if any(self._airstream(c) == "velaric" for c in self.constituents):
            return Kind.CLICK_ACCOMPANIMENT
        if len(blocks) == 1:
            return Kind.DOUBLE_ARTICULATION
        first, second = manners[0], manners[1]
        if first == "plosive" and second == "fricative":
            return Kind.AFFRICATE
        if first == "nasal" and second in obstruent:
            return Kind.PRENASALIZED
        if first in obstruent and second == "nasal":
            return Kind.PRE_STOPPED
        if first == "plosive" and second == "approximant":
            block_start, block_end = blocks[1]
            if any(
                (p := self._require_features().get_phone(c.base))
                and p.features.get("channel") == "lateral"
                for c in self.constituents[block_start:block_end]
            ):
                return Kind.LATERAL_RELEASE
        return Kind.OVERLAY

    def bag(self) -> dict[str, tuple[str, ...]]:
        """Union feature bag: per-feature value tuples in constituent order,
        deduplicated. Bases are default-filled per constituent before the
        union (so ``u͜i`` carries rounded=(+, −)); modifier projections stay
        sparse."""
        features = self._require_features()
        out: dict[str, list[str]] = {}
        for constituent in self.constituents:
            for k, v in constituent.bundle(features, with_defaults=True).items():
                values = out.setdefault(k, [])
                if v not in values:
                    values.append(v)
        return {k: tuple(v) for k, v in out.items()}

    def scalar(self, with_defaults: bool = True) -> dict[str, str]:
        """Flat projection: one value per key (design spec section 6).

        :func:`flat_projection` over this unit's constituents -- the same
        function the string entry points compose a tie chain with -- so
        this and ``get_features`` are one computation, not two that have
        to be kept in step. A mark reaches the merge as part of its own
        constituent's bundle, so it wins the keys its constituent states
        and loses the keys a later constituent states: ``t̪͡s`` is
        alveolar (the affricate takes the place of its release) and
        ``kʷ͡p`` keeps ``labialized='+'`` (``p`` states no labialization).

        An unmarked unit is read through :meth:`IPAFeatures.get_features`
        on its chain, so a registered entry still wins over the merge of
        its parts -- that is where ``t͡s`` gets its ``href`` and ``ʦ``
        resolves at all.

        ``scalar() == compose(s)[0]`` for string-expressible units with
        one exception: a prosodic mark belongs to the unit rather than to
        its feature bag, so ``compose("eː")`` reports ``length=long``
        where this reports the ``length`` of ``e`` and carries the mark in
        :attr:`prosody`.
        """
        features = self._require_features()
        if not any(c.modifiers for c in self.constituents):
            chain = "".join(
                c.base if i == 0 else self.junctures[i - 1].glyph(features) + c.base
                for i, c in enumerate(self.constituents)
            )
            return features.get_features(chain, with_defaults=with_defaults)
        feats = flat_projection(
            features,
            [part_bundle(features, c) for c in self.constituents],
            self.junctures,
        )
        if not feats:
            return {}
        if with_defaults:
            fill_defaults(features, feats)
        return feats

    # -- construction and serialization ---------------------------------------

    def to_ipa(self) -> str:
        """Emit the unit with sense-correct tie glyphs and prosody marks.

        Lossy exactly on the legacy alias collisions (see docs/ties.md):
        the emitted string always re-ingests to a valid unit, but for
        collision spellings the registered sense wins over the emitted
        glyph, so ``parse(to_ipa(x))`` may differ structurally from ``x``.
        """
        features = self._features
        # Stress is written before its domain, every other prosodic mark
        # after its own; `stress_markers` is the one derived read of
        # which marks those are, shared with the parse side.
        markers = features.stress_markers if features is not None else {}
        stress = [m for m in self.prosody if m in markers]
        trailing = [m for m in self.prosody if m not in markers]
        body = "".join(
            str(c) if i == 0 else self.junctures[i - 1].glyph(features) + str(c)
            for i, c in enumerate(self.constituents)
        )
        return "".join(stress) + body + "".join(trailing)

    def to_json(self) -> str:
        return json.dumps(
            {
                "v": _JSON_VERSION,
                "constituents": [
                    {"base": c.base, "modifiers": list(c.modifiers)}
                    for c in self.constituents
                ],
                "junctures": [j.value for j in self.junctures],
                "prosody": list(self.prosody),
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, data: str, features: IPAFeatures | None = None) -> Segment:
        obj: dict[str, Any] = json.loads(data)
        version = obj.get("v")
        if version != _JSON_VERSION:
            raise ValueError(f"unsupported Segment JSON version: {version!r}")
        prosody = tuple(obj.get("prosody", ()))
        if features is not None:
            check_prosody(features, prosody)
        return cls(
            constituents=tuple(
                Constituent(base=c["base"], modifiers=tuple(c.get("modifiers", ())))
                for c in obj["constituents"]
            ),
            junctures=tuple(Sense(j) for j in obj.get("junctures", ())),
            prosody=prosody,
            _features=features,
        )

    # -- notebook display -----------------------------------------------------

    def _repr_svg_(self) -> str:
        """The mid-sagittal tract figure, drawn when a notebook shows this.

        A segment is one unit, so it is one posture, so it has one figure:
        that is the whole reason this hook is here and not on ``Form`` or
        ``Derivation``, each of which is a sequence of postures and would
        have to choose one or invent a strip. See docs/tract-figures.md.

        Drawn against this segment's own inventory when it has one, so a
        caller using their own ``ipa.xml`` gets a picture of their data
        rather than of the shipped default.

        The import is deferred: the renderer reads the model, ``ipakit
        .metric`` reads the model, and nothing that computes a distance
        should be able to reach a stylesheet.
        """
        from .tract_svg import figure

        return figure(self.to_ipa(), features=self._features)
