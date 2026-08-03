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
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .constants import METADATA_ATTRS

if TYPE_CHECKING:  # pragma: no cover
    from ._base import IPAFeaturesBase
    from .features import IPAFeatures

_JSON_VERSION = 2

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


#: The mode a feature declares when it is a property of the phase a
#: segment is *entered* on. Named here because the two placements a mark
#: can be written in are a fact about the notation and the mode is the
#: data's name for one of them; which features are in it, and which marks
#: therefore stand before a base, stays derived from the declarations.
APPROACH_MODE = "approach"


def phase_keys(features: IPAFeaturesBase, symbol: str, approach: bool) -> set[str]:
    """The keys a mark contributes in one of the two placements.

    A mark written before a base states how the segment is approached and
    a mark written after it states how the segment is released, and the
    four marks that can do both (``ⁿ ˀ ʰ ʱ``) declare a key for each. So
    the placement selects the keys, and a mark never says both ends at
    once: ``dⁿ`` is nasally released, ``ⁿd`` is pre-nasalized, and neither
    is both.

    Membership comes from ``<modes>`` through
    :attr:`~ipakit.IPAFeatures.features_by_mode`; nothing here knows which
    glyph or which feature name is which.
    """
    mark = features.diacritics.get(symbol)
    if mark is None:
        return set()
    stated = set(mark.features) - METADATA_ATTRS - {"class"}
    at_approach = features.features_by_mode.get(APPROACH_MODE, frozenset())
    return {key for key in stated if (key in at_approach) is approach}


def modifier_mode(
    features: IPAFeaturesBase, symbol: str, approach: bool = False
) -> str:
    """Contribution mode of a diacritic/suprasegmental symbol.

    One of the modes the data declares (``structural``, ``prosodic``,
    ``release``, ``approach``, ``secondary``, ``overriding``,
    ``additive``), read off the mark's own feature keys: a mark is a
    release phase because it says ``release=...`` and a secondary
    articulation because it says ``velarized=...``. Declaration order in
    ``<modes>`` is precedence, so the first mode any of the mark's keys
    claims wins. No symbol is classified by name, and no table here
    restates which key means what.

    ``approach=True`` asks the same question of the *other* placement,
    over the keys :func:`phase_keys` leaves the mark there. The default is
    the trailing placement because that is where every other caller means:
    a modifier run, a mark stack's order, the prosody check.

    Takes the mixin base rather than ``IPAFeatures``: it reads only the
    diacritic table, so the mixins can call it on ``self``.
    """
    keys = phase_keys(features, symbol, approach)
    by_mode = features.features_by_mode
    for mode in features.modes:
        if keys & by_mode.get(mode, frozenset()):
            return mode
    return features.default_mode


def approach_run(features: IPAFeaturesBase, text: str, start: int) -> list[str]:
    """The run of marks at ``text[start]`` that a following base carries.

    The mirror of ``IPAFeatures._modifier_run``, and the one place a read
    of a transcription looks *forward*: a mark declaring an approach-phase
    feature states a phase of the base written after it, so ``ⁿd`` is one
    unit the way ``dⁿ`` is. Membership is
    :attr:`~ipakit.IPAFeatures.approach_marks`, read off the declarations.
    The run is only meaningful where a base actually follows it, which is
    each caller's own check, because a mark with nothing after it binds
    nothing and is reported rather than read.

    This never takes a mark away from a base on its *left*. Every caller
    reaches here having already taken the modifier run of the unit before,
    so in ``dⁿd`` the ``ⁿ`` is the release of the first ``d`` and not the
    approach of the second: a mark binds backward wherever it can, and
    forward only where it cannot.

    A module function rather than a parser method because the parser and
    :meth:`~ipakit.IPAFeatures.validate_ipa` both have to agree about
    where a unit starts, and two reads of that question is how the two
    came to disagree about ``ⁿd`` in the first place.
    """
    run: list[str] = []
    j = start
    while j < len(text) and text[j] in features.approach_marks:
        run.append(text[j])
        j += 1
    return run


def check_prosody(features: IPAFeaturesBase, prosody: Iterable[str]) -> None:
    """Validate a unit's prosody: what may stand in it, and how much.

    Two rules, one place, so every construction path states them the
    same way. Prosody carries prosodic marks and nothing else, and
    stress is one feature of one syllable: a unit states at most one
    level of it, because two marks on one unit is a contradiction rather
    than a stack.

    Asked as ``mode == "prosodic"`` rather than as a list of the modes
    to turn away, because the mark decides its own mode by what it
    declares and a list here would have to be revised every time
    ``<modes>`` gains a row. Structural marks keep their own message:
    a tie is a juncture and a break lives between units, so neither is a
    property of one unit, and saying that is more use than saying the
    mode is wrong.

    The looser test this replaces refused only structural marks, which
    let a *segmental* diacritic be stored here. It changed nothing where
    it sat -- prosody is not read for features -- and then ``to_ipa``
    wrote it where the parser reads it as a constituent modifier, so a
    voiced ``d`` with a ring parked in its prosody came back devoiced.
    An accepted segment must not become a different segment by being
    written out and read back.
    """
    seen_stress: list[str] = []
    for mark in prosody:
        mode = modifier_mode(features, mark)
        if mode == "structural":
            raise ValueError(
                f"structural mark {mark!r} is not prosody; "
                "ties are junctures, breaks live between units"
            )
        if mode != "prosodic":
            raise ValueError(
                f"{mark!r} states {mode}, so it belongs on a constituent "
                "rather than in prosody; written out it would be read back "
                "as a modifier and change the segment"
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


def state_mark_value(
    features: IPAFeaturesBase,
    feats: dict[str, str],
    stated: dict[str, str],
    key: str,
    value: str,
    overriding: bool,
    where: str,
) -> None:
    """Fold one mark's statement of one feature into a bundle being read.

    The single answer to "what do two marks stating one feature mean",
    and the read counterpart of what ``compose_unit`` and
    :func:`~ipakit.form.with_prosody` already do when they *write* one.
    Both branches of it are declared in ``ipa.xml``:

    A feature declared ``sequence="+"`` states a trajectory, so a run of
    marks stating it **concatenates**: ``a˧˦`` is ``tone="mid>high"``,
    which is what ``᷄`` declares in one glyph, and ``a˧˩˧`` is
    ``tone="mid>bottom>mid"``. The writer emits exactly such a run --
    ``[tone=top>bottom]`` spells ``˥˩`` -- so refusing it on the way back
    in would be the library declining to read what it writes.

    Every other feature is single-valued, so a second mark stating it is a
    **contradiction rather than a stack**: ``ɛ̥̤`` cannot be both devoiced
    and breathy. The first statement stands and the second is reported,
    naming what contradicts what. Which of the two stands is a tie broken
    for consistency and not for meaning -- a mark stack carries no order
    the writer chose, since ``compose_unit`` re-emits the whole stack in
    mode order and Unicode reorders combining marks by combining class --
    so the report is the load-bearing half, not the choice. What must not
    happen is the silent answer: reading ``ɛ̥̤`` as breathy and ``ɛ̤̥`` as
    devoiced assigns a phonation off an order that means nothing, and
    ``compose_unit`` will not spell either.

    ``stated`` is what the marks of *this* stack have said so far, kept
    apart from ``feats`` because the base's own value is not a competing
    mark: a mark overriding what the phone declares is the ordinary case,
    and only a second *mark* contradicts. ``feats`` is updated in place,
    following ``overriding`` on a key no mark has claimed yet.
    """
    feature = features.features.get(key)
    if key not in stated:
        stated[key] = value
        if overriding or key not in feats:
            feats[key] = value
        return
    incumbent = stated[key]
    if feature is not None and feature.sequence:
        merged = feature.sequenced(feature.steps(incumbent) + feature.steps(value))
        stated[key] = merged
        # Only where the first statement is the one standing: a mark that
        # gave way to the base's value has no run for a later one to join.
        if feats.get(key) == incumbent:
            feats[key] = merged
    elif incumbent != value:
        warnings.warn(
            f"{where}: two marks state {key!r} ({incumbent!r} then {value!r}); "
            f"{key!r} is single-valued, so {value!r} is a contradiction and "
            "is not recorded",
            stacklevel=3,
        )


def apply_modifiers(
    features: IPAFeatures,
    feats: dict[str, str],
    modifiers: Iterable[str],
    prosody: bool = False,
    approach: bool = False,
    where: str | None = None,
) -> dict[str, str]:
    """Overlay a modifier stack onto a base bundle, per mark, by mode.

    The single implementation of what a diacritic contributes, so the
    flat projection and the structured bundle cannot disagree about one
    mark. Overriding marks replace their base's value (the devoicing
    ring makes ``d̥`` voiceless, never both-voiced); additive, secondary,
    release and approach marks add only keys the base leaves unstated --
    a phase mark describes a phase, not the whole segment, so the glottal
    phase of ``tˀ`` never makes the ``t`` glottal. Structural and prosodic
    marks contribute nothing to a feature bag: ties are junctures and
    prosody lives on the unit.

    ``approach=True`` is the stack written *before* the base, and what it
    changes is which of each mark's keys is read: :func:`phase_keys`
    hands over the approach-mode ones there and the rest here, so ``ⁿd``
    states ``approach="nasal"`` and ``dⁿ`` states ``release="nasal"``
    from one declaration, and neither states both.

    ``prosody=True`` is for the one read that has no unit level to put a
    prosodic mark on -- :meth:`IPAFeatures.compose_segments` returns one
    flat bundle per token, so ``eː`` has nowhere but the bundle to carry
    its length. That is the documented divergence between ``compose()``
    and ``scalar()``, and it stays exactly that one thing.

    Metadata (``name``/``class``/``href``/``xsampa``) never crosses.
    Those attributes name a *symbol*, and the symbol a unit's metadata
    describes is its base, not the mark riding on it -- the article for
    ``tʰ`` is the one for ``t``, not the one for aspiration.

    What two marks of one stack stating one feature mean is
    :func:`state_mark_value`, which is also what the unit's prosody is
    read with -- so the segmental read and the prosodic one cannot come
    to different ideas of ``a˧˦``. ``where`` names the unit in the report
    that read makes, and defaults to the stack itself.

    Mutates and returns ``feats``. Defaults must not be filled before
    this runs: a mark adding a feature the base leaves unstated
    (nasalization on a vowel) would otherwise find the default already
    sitting in the slot.
    """
    modifiers = list(modifiers)
    if where is None:
        where = repr("".join(modifiers))
    stated: dict[str, str] = {}
    for mod in modifiers:
        mark = features.diacritics.get(mod)
        if mark is None:
            continue
        keys = phase_keys(features, mod, approach)
        if not keys:
            continue
        mode = modifier_mode(features, mod, approach)
        if mode == "structural" or (mode == "prosodic" and not prosody):
            continue
        # Iterated in the mark's own declaration order, not over ``keys``:
        # a set's iteration order moves with PYTHONHASHSEED, and the order
        # keys land in is the order the assembled bundle is written in.
        for key, value in mark.features.items():
            if key not in keys:
                continue
            state_mark_value(
                features,
                feats,
                stated,
                key,
                value,
                overriding=mode == "overriding",
                where=where,
            )
    return feats


def fill_defaults(features: IPAFeatures, feats: dict[str, str]) -> dict[str, str]:
    """Fill each still-unset feature with its declared default.

    Skipped entirely for a bundle :func:`takes_defaults` refuses, which is
    the same question this used to answer for itself off a narrower test:
    silence answered no to both, but a position that is not a segment at
    all -- a declared zero, whose ``class`` is dropped from a feature bag,
    leaving nothing to constrict with -- answered no there and was filled
    here anyway, so a structural zero acquired an airstream and a channel.
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
    if not takes_defaults(features, feats):
        return feats
    for name, feat in features.features.items():
        if name not in feats and feat.default is not None:
            feats[name] = feat.default
    return feats


def phase_blocks(bundles: Sequence[Mapping[str, str]]) -> list[tuple[int, int]]:
    """Maximal same-manner runs of constituents, as ``(start, end)`` slices.

    A unit's phase structure, read once: :func:`classify` asks it and so
    does :attr:`Segment.children`, so the grouping a caller walks and the
    classification it is given cannot disagree about where a phase ends.
    """
    blocks: list[tuple[int, int]] = []
    start = 0
    for i in range(1, len(bundles)):
        if bundles[i].get("manner") != bundles[start].get("manner"):
            blocks.append((start, i))
            start = i
    blocks.append((start, len(bundles)))
    return blocks


def phase_ordered(
    bundles: Sequence[Mapping[str, str]], junctures: Sequence[Sense]
) -> bool:
    """Whether a unit's constituents stand in an order that carries
    meaning, from its phase structure and its junctures.

    What a tie's order means, asked once. A sequential tie orders its
    constituents in time. A simultaneous tie orders nothing by itself:
    it asserts one timing slot, and the only order inside one is the
    order of the phases -- the closure before the release, the nasal
    before the stop. So a fusion whose constituents share a phase has no
    order at all, and writing them the other way round is the same unit.

    :attr:`Segment.phased` is this over a parsed unit and
    :func:`flat_projection` is this over the bundles it merges, so the
    metric's alignment mode and the projection's merge cannot come to
    different ideas about whether ``u͡i`` and ``i͡u`` are one sound. They
    did: the metric called them identical while the projection read the
    last constituent's backness and rounding, so one sound had two
    descriptions and no distance between them.
    """
    return Sense.SEQ in junctures or len(phase_blocks(bundles)) > 1


def simultaneous_merge(
    features: IPAFeatures, bundles: Sequence[Mapping[str, str]]
) -> dict[str, str]:
    """Merge constituent bundles that stand in no order.

    Position cannot break a tie here, so nothing about which constituent
    was written first may reach the result. What breaks it instead is
    what the feature declares itself to be:

    * One constituent states the key -- that value. A mark on either
      constituent still reaches the projection where the other states
      nothing, so ``kʷ͡p`` keeps ``labialized='+'`` and ``p͡kʷ`` agrees.
    * Both state it, on a feature whose values are **positions** -- the
      combining spelling of the two, which :meth:`Feature.combine` orders
      by scale position and which is therefore the same string either way
      round. ``k͡p`` is ``bilabial^velar`` written from either end, which
      is the rule :func:`combining_place` already applied to place alone;
      ``u͡i`` is ``front^back``, and ``s͡ɬ`` is ``lateral^grooved``.
    * Both state it, on a **binary** feature -- the declared default,
      which for a binary type is the negative: its two values are the
      presence and the absence of one articulation, so constituents that
      disagree do not give the unit one to assert. ``ɡ͡b̥`` is voiceless
      written either way round, where before it was voiceless one way and
      voiced the other.

    The disagreement itself is not thrown away by any of these:
    :meth:`Segment.disagreements` reads it off the union bag, which is
    where composition reports rather than referees.

    A key naming no declared feature is metadata rather than an
    articulation; there is nothing to combine, and ``href`` is dropped by
    the projection in any case.
    """
    stated: dict[str, list[str]] = {}
    for bundle in bundles:
        for key, value in bundle.items():
            values = stated.setdefault(key, [])
            if value not in values:
                values.append(value)
    merged: dict[str, str] = {}
    for key, values in stated.items():
        feature = features.features.get(key)
        if feature is None or len(values) == 1:
            merged[key] = values[0]
        elif feature.is_binary and feature.default is not None:
            merged[key] = feature.default
        else:
            merged[key] = feature.combine(tuple(values))
    return merged


def combining_place(
    features: IPAFeatures, bundles: Sequence[Mapping[str, str]]
) -> str | None:
    """The place a simultaneous fusion is spelled with when its
    constituents constrict in more than one, and ``None`` when there is
    nothing to combine.

    One timing slot at one manner, articulated in two places, is a double
    articulation, and its place is the canonical combining spelling --
    components ordered by scale position, any pair and not just the
    pre-named ones. This is the whole of that test: :func:`classify` calls
    a fusion a double articulation exactly where this returns a value, and
    :func:`flat_projection` writes exactly the value it returns, so the
    name and the spelling are one decision. ``t͡d`` acquiring the name
    without the spelling is what it looks like when they are two.

    ``None`` for a phased unit, whose place is the phase the merge ends on
    (``t̪͡s`` is alveolar, not dental^alveolar).
    """
    if len(phase_blocks(bundles)) > 1:
        return None
    places = [bundle["place"] for bundle in bundles if "place" in bundle]
    if len(set(places)) < 2:
        return None
    place_feature = features.features.get("place")
    if place_feature is None:
        return None
    return str(place_feature.combine(tuple(places)))


def classify(
    features: IPAFeatures,
    bundles: Sequence[Mapping[str, str]],
    junctures: Sequence[Sense],
) -> Kind:
    """What one unit is, from its constituents' bundles and its junctures.

    The single read of that question. :attr:`Segment.kind` is this over a
    parsed unit's constituents, and :func:`flat_projection` is this over
    the very bundles it merges, so the structured classification and the
    flat projection cannot call one unit two things. They did: a
    prenasalized stop was projected with ``manner="affricate"`` while
    ``kind`` called it prenasalized, and ``t͡d`` was classified a double
    articulation while the projection beside it read one alveolar place.
    Both were two answers to this question, kept in step by vigilance.

    Read off the bundles rather than off the base phones, because a mark
    is part of the constituent it is written on: the mark that overrides a
    place is what decides whether two constituents constrict in two
    places, and the mark that overrides an airstream is what decides
    whether a constituent is still a click.

    The order of the tests is the classification's own precedence: a
    sequence before a fusion, an airstream before a manner, and a
    single-block fusion -- one timing slot, no phase to order -- before
    the phased readings.
    """
    if len(bundles) == 1:
        return Kind.ATOMIC
    if Sense.SEQ in junctures:
        if all(bundle.get("manner") == "vowel" for bundle in bundles):
            return Kind.DIPHTHONG
        return Kind.CHAIN
    if any(bundle.get("airstream") == "velaric" for bundle in bundles):
        return Kind.CLICK_ACCOMPANIMENT
    blocks = phase_blocks(bundles)
    if len(blocks) == 1:
        # One manner, so the only thing that can make this two
        # articulations is two places to articulate at -- and that is the
        # question :func:`combining_place` answers for the projection. With
        # one effective place there is nothing to combine and nothing
        # double about it: the constituents are laid over each other.
        if combining_place(features, bundles) is not None:
            return Kind.DOUBLE_ARTICULATION
        return Kind.OVERLAY
    manner_feature = features.features.get("manner")
    obstruent = (
        manner_feature.value_classes.get(_OBSTRUENT, frozenset())
        if manner_feature is not None
        else frozenset()
    )
    first = bundles[blocks[0][0]].get("manner")
    second = bundles[blocks[1][0]].get("manner")
    if first == "plosive" and second == "fricative":
        return Kind.AFFRICATE
    if first == "nasal" and second in obstruent:
        return Kind.PRENASALIZED
    if first in obstruent and second == "nasal":
        return Kind.PRE_STOPPED
    if first == "plosive" and second == "approximant":
        start, end = blocks[1]
        if any(bundle.get("channel") == "lateral" for bundle in bundles[start:end]):
            return Kind.LATERAL_RELEASE
    return Kind.OVERLAY


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

    How the block then merges is asked of :func:`phase_ordered`, the one
    read of what the constituents' order means. Where they stand in
    phases the order is meaning, and the merge runs left to right, last
    constituent wins: an affricate takes the place of its release
    (``t͡ʃ`` is postalveolar, from ``ʃ``), and a mark on an earlier
    constituent survives only where the later ones state nothing -- which
    is why ``t̪͡s`` is alveolar, not dental. Where they share one phase
    there is no order to read, and :func:`simultaneous_merge` takes the
    tie off what the features declare instead of off the writing: ``kʷ͡p``
    still keeps ``labialized='+'``, and ``u͡i`` and ``i͡u`` project one
    bundle, as the metric already scores them one sound.

    The merge stands except where the unit's own reading names a declared
    value for the whole of it, and there are exactly two such names: an
    affricate *is* the manner ``affricate`` (``q͡χ`` is a uvular
    affricate), and a simultaneous fusion in two places *is* the combining
    place they spell. Both are asked here of the same functions that name
    the unit -- :func:`classify` and :func:`combining_place` -- so a unit
    cannot be called one thing and projected as another.

    Every other reading -- a prenasalized stop, a pre-stopped nasal, a
    lateral release -- names a phase rather than a value, so the merge
    reports what the constituents state and :attr:`Segment.kind` is where
    the phase is read. Collapsing every differing manner to ``affricate``
    is what once made ``describe("n͡d")`` and ``describe("d͡n")`` the same
    sentence, and made the metric compare a prenasalized stop as an
    affricate.

    ``href`` is dropped from any composed unit: it names a specific
    Wikipedia article for a symbol, and an ad hoc compound has none.

    Returns a fresh dict; the inputs are not mutated.
    """
    composed = bool(junctures)
    if Sense.SEQ in junctures:
        cut = list(junctures).index(Sense.SEQ) + 1
        bundles, junctures = list(bundles)[:cut], list(junctures)[: cut - 1]
    feats: dict[str, str] = {}
    if phase_ordered(bundles, junctures):
        for bundle in bundles:
            feats.update(bundle)
    else:
        feats = simultaneous_merge(features, bundles)
    if composed:
        feats.pop("href", None)
    if classify(features, bundles, junctures) is Kind.AFFRICATE:
        feats["manner"] = "affricate"
    place = combining_place(features, bundles)
    if place is not None:
        feats["place"] = place
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
    """A base phone with the marks written on either side of it.

    ``modifiers`` is the stack written after the base and ``approach``
    the stack written before it. One constituent either way: a
    pre-articulation is a phase of *this* segment, so ``ⁿd`` is one base
    wearing one mark, exactly as ``dⁿ`` is, and not a second constituent
    to be tied on (docs/ties.md).
    """

    base: str
    modifiers: tuple[str, ...] = ()
    approach: tuple[str, ...] = ()

    def __str__(self) -> str:
        return "".join(self.approach) + self.base + "".join(self.modifiers)

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

        The marks written before the base contribute at step (2) as well,
        and contribute their *approach*-phase keys where the trailing
        stack contributes the rest. The base is applied before either, so
        a phone that states a phase of its own is not overwritten by a
        mark that only adds.

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
        where = repr(str(self))
        apply_modifiers(features, feats, self.approach, approach=True, where=where)
        apply_modifiers(features, feats, self.modifiers, where=where)
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

    def _part_bundles(self) -> list[dict[str, str]]:
        """Each constituent's own explicit bundle -- what the projection
        merges, and what the classification is read off."""
        features = self._require_features()
        return [part_bundle(features, c) for c in self.constituents]

    def _phase_blocks(self) -> list[tuple[int, int]]:
        """Maximal same-manner runs of constituents, as (start, end) slices."""
        return phase_blocks(self._part_bundles())

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
        """Total classification (design spec section 5).

        :func:`classify` over this unit's own bundles -- the same read the
        flat projection is named by, not a second one beside it.
        """
        return classify(self._require_features(), self._part_bundles(), self.junctures)

    @property
    def phased(self) -> bool:
        """Whether the unit's parts stand in phase or sequence, so their
        order is meaning rather than notation.

        What the metric aligns on (docs/distance.md): a sequential chain
        and a fusion of more than one phase block are read in order; a
        single-block fusion and an atomic unit are not, because one timing
        slot at one manner has no phase to put first. :func:`phase_ordered`
        over this unit's own bundles: asked of the structure rather than
        of a list of :class:`Kind` names, so that naming a fusion
        differently cannot silently change how it aligns, and the same
        read :func:`flat_projection` merges by, so the alignment mode and
        the projection cannot disagree about what the order means.
        """
        return phase_ordered(self._part_bundles(), self.junctures)

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
        if not any(c.modifiers or c.approach for c in self.constituents):
            return features.get_features(self.spelling, with_defaults=with_defaults)
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

    @property
    def spelling(self) -> str:
        """The unit as written, without its prosody: constituents joined
        by the glyphs their junctures are spelled with.

        The segmental half of :meth:`to_ipa`, and the half a converter
        looks a unit up by -- a phone-set table (``cmu.xml``) is keyed on
        segments and holds no stress, length or tone. Split out rather
        than rebuilt beside it so the chain join is written once: this,
        :meth:`to_ipa` and :meth:`scalar` all read it.
        """
        return "".join(
            str(c) if i == 0 else self.junctures[i - 1].glyph(self._features) + str(c)
            for i, c in enumerate(self.constituents)
        )

    def unmarked(self) -> Segment:
        """This unit with the marks written on its constituents taken off:
        bases and junctures only, and no prosody.

        What a target alphabet that cannot spell a diacritic falls back
        to, so that the fallback is still *this* unit rather than a
        second reading of the string.
        """
        return Segment(
            constituents=tuple(Constituent(base=c.base) for c in self.constituents),
            junctures=self.junctures,
            _features=self._features,
        )

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
        return "".join(stress) + self.spelling + "".join(trailing)

    def to_json(self) -> str:
        return json.dumps(
            {
                "v": _JSON_VERSION,
                "constituents": [
                    {
                        "base": c.base,
                        "modifiers": list(c.modifiers),
                        "approach": list(c.approach),
                    }
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
                Constituent(
                    base=c["base"],
                    modifiers=tuple(c.get("modifiers", ())),
                    approach=tuple(c.get("approach", ())),
                )
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
