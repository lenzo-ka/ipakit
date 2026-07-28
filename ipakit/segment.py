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
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .constants import METADATA_ATTRS, SEQ_TIE, TIE_BAR

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures

_JSON_VERSION = 1

# Feature keys that assign a diacritic its contribution mode (docs/ties.md,
# design spec section 8). Order matters: the first matching bucket wins.
_STRUCTURAL_KEYS = frozenset({"tie", "linking", "break"})
_PROSODIC_KEYS = frozenset({"stress", "length", "tone", "contour", "global", "step"})
_SECONDARY_KEYS = frozenset(
    {"palatalized", "labialized", "velarized", "pharyngealized", "labio-palatized"}
)
_OVERRIDING_KEYS = frozenset({"voiced", "place", "manner", "syllabic"})
# Symbols whose feature keys would misclassify them: pre-glottalization
# carries a glottal phase (manner/place) and the schwa release carries vowel
# qualities, but both are release/phase marks, not overrides of their base.
_MODE_EXCEPTIONS = {"ˀ": "release", "ᵊ": "release"}

_ORAL_OBSTRUENT = frozenset({"plosive", "fricative", "affricate"})


class Sense(StrEnum):
    """Juncture sense: what a tie asserts about timing."""

    FUSE = "fuse"  # over-tie U+0361: one timing slot
    SEQ = "seq"  # under-tie U+035C: several slots bound into one unit

    @property
    def glyph(self) -> str:
        return TIE_BAR if self is Sense.FUSE else SEQ_TIE


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


def modifier_mode(features: IPAFeatures, symbol: str) -> str:
    """Contribution mode of a diacritic/suprasegmental symbol.

    One of ``structural``, ``prosodic``, ``release``, ``secondary``,
    ``overriding``, ``additive``. Derived from the mark's feature keys,
    with the documented exceptions.
    """
    if symbol in _MODE_EXCEPTIONS:
        return _MODE_EXCEPTIONS[symbol]
    mark = features.diacritics.get(symbol)
    keys = set(mark.features) - METADATA_ATTRS - {"class"} if mark else set()
    if keys & _STRUCTURAL_KEYS:
        return "structural"
    if keys & _PROSODIC_KEYS:
        return "prosodic"
    if "release" in keys:
        return "release"
    if keys & _SECONDARY_KEYS:
        return "secondary"
    if keys & _OVERRIDING_KEYS:
        return "overriding"
    return "additive"


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
    """
    if _is_non_speech(features, feats):
        return feats
    for name, feat in features.features.items():
        if name not in feats and feat.default is not None:
            feats[name] = feat.default
    return feats


@dataclass(frozen=True)
class Constituent:
    """A base phone plus its ordered modifier stack."""

    base: str
    modifiers: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.base + "".join(self.modifiers)

    def bundle(
        self, features: IPAFeatures, with_defaults: bool = True
    ) -> dict[str, str]:
        """Phonetic feature bundle, assembled in the contracted order.

        (1) the base's explicit features; (2) modifier contributions per
        mode — overriding replaces, everything else adds only keys not yet
        present; (3) defaults fill keys still missing. Defaults never apply
        to modifier projections, so a sparse modifier stays sparse.
        """
        base_phone = features.get_phone(self.base)
        feats: dict[str, str] = {}
        if base_phone is not None:
            feats = {
                k: v for k, v in base_phone.features.items() if k not in METADATA_ATTRS
            }
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
        blocks = self._phase_blocks()
        manners = [self._manner(self.constituents[s]) for s, _ in blocks]
        if any(self._airstream(c) == "velaric" for c in self.constituents):
            return Kind.CLICK_ACCOMPANIMENT
        if len(blocks) == 1:
            return Kind.DOUBLE_ARTICULATION
        first, second = manners[0], manners[1]
        if first == "plosive" and second == "fricative":
            return Kind.AFFRICATE
        if first == "nasal" and second in _ORAL_OBSTRUENT:
            return Kind.PRENASALIZED
        if first in _ORAL_OBSTRUENT and second == "nasal":
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
        """Flat backward-compatible projection (design spec section 6).

        Delegates to the same rules the string entry points use --
        registered lookup or tie composition for the chain, then the
        same mode-governed modifier overlay :meth:`Constituent.bundle`
        applies -- so this and ``get_features`` are one read, not two,
        and for an atomic unit this agrees with the bundle on every
        phonetic key.

        ``scalar() == compose(s)[0]`` for string-expressible units with
        one exception: a prosodic mark belongs to the unit rather than to
        its feature bag, so ``compose("eː")`` reports ``length=long``
        where this reports the ``length`` of ``e`` and carries the mark in
        :attr:`prosody`.
        """
        features = self._require_features()
        chain = "".join(
            c.base if i == 0 else self.junctures[i - 1].glyph + c.base
            for i, c in enumerate(self.constituents)
        )
        # Read the chain undefaulted: a mark that adds what the base
        # leaves unstated has to land before the defaults do.
        feats = features.get_features(chain, with_defaults=False)
        if not feats:
            return {}
        # The last constituent carries the written trailing marks.
        apply_modifiers(features, feats, self.constituents[-1].modifiers)
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
        stress: list[str] = []
        trailing: list[str] = []
        for mark in self.prosody:
            bucket = None
            if features is not None:
                entry = features.diacritics.get(mark)
                if entry is not None and "stress" in entry.features:
                    bucket = stress
            (bucket if bucket is not None else trailing).append(mark)
        body = "".join(
            str(c) if i == 0 else self.junctures[i - 1].glyph + str(c)
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
            for mark in prosody:
                if modifier_mode(features, mark) == "structural":
                    raise ValueError(
                        f"structural mark {mark!r} is not prosody; "
                        "ties are junctures, breaks live between units"
                    )
        return cls(
            constituents=tuple(
                Constituent(base=c["base"], modifiers=tuple(c.get("modifiers", ())))
                for c in obj["constituents"]
            ),
            junctures=tuple(Sense(j) for j in obj.get("junctures", ())),
            prosody=prosody,
            _features=features,
        )
