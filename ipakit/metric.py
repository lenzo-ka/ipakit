"""Structural distance over Segments (design spec section 7).

Distance is computed over the derived grouping, never the flat feature
bag: constituents compare as whole bundles, alignment mode follows the
unit's phase structure (ordered where order is meaning, unordered where
it is notation), junctures carry the binding-sense term, and secondary
articulations enter as weighted place components. All values lie in
[0, 1].

Key properties, pinned by tests:

- ``D(ɡ, ɡ͡b) = A + d_b(ɡ, b) / 2`` — adding an articulator costs
  one derived arity term ``A`` while the sharing term remains graded.
- ``D(u͡i, u͜i) = 1/3`` — same constituents, different timing claim: one
  juncture-sense mismatch over three terms.
- ``place(t, tʲ) = δ/3 < place(tʲ, c) = 2δ/3 < place(t, c) = δ`` — a
  secondary articulation moves a segment toward its secondary place,
  strictly between the plain segments.
- ``D(u͡i, i͡u) = 0`` but ``D(a͡t, t͡a) > 0`` — a single-block fusion is
  unordered notation; phased units are ordered.
"""

from __future__ import annotations

import functools
import hashlib
import warnings
from typing import TYPE_CHECKING

from .constants import METADATA_ATTRS
from .models import Feature
from .segment import Constituent, Segment, Sense
from .tract import constrictions, tract_point

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable, Iterator

    from .features import IPAFeatures

# Word-alignment gap cost (design spec section 11). Segment composition does
# not use a flat gap: ``MATERIAL_BUDGET`` declares its derived comparison.
GAP_COST = 1.0
# Secondary-articulation place weight.
SECONDARY_WEIGHT = 0.5

#: The mass budget for material in one segment. These are policies, not fitted
#: weights: every graded price is derived from the feature/value declarations
#: through ``segment_metric``. The tuple is also fingerprinted, so a saved
#: matrix names the convention under which its numbers were derived.
MATERIAL_BUDGET = (
    ("atomic feature", "one value-distance term", "graded"),
    ("fusion arity", "one atomic-term mass per added constituent", "derived"),
    ("unmatched constituent", "nearest-part distance plus one mass term", "graded"),
    ("juncture", "one binding-sense term", "categorical"),
    ("secondary articulation", "shared at SECONDARY_WEIGHT", "graded"),
    ("prosodic rider", "one value-distance term per tier", "graded"),
)

# The secondary articulations, and the place each constricts at, come from
# the data (IPAFeatures.secondary_places): a feature declares
# mode="secondary" place="velar" once, and the mode partition and the place
# table are then the same statement rather than two lists that agree by
# habit. Combining place values (bilabial^palatal) carry their expansion in
# the name; Feature.expand supplies the components.

# Which pairs align ordered is asked of the unit's phase structure --
# Segment.phased -- and not of a list of Kind names beside it. The list was
# the kinds that happen to be phased, which held only while every
# single-block fusion was called a double articulation; a fusion renamed
# for having one place would have fallen off it and started aligning as a
# sequence, with nothing to say so.

PlaceComponents = tuple[tuple[str, float], ...]

# Sagittal bridges: shared tract coordinates (see ipakit.tract) make
# cross-class spatial proximity (j~i, w~u, k~u) visible.


@functools.cache
def excluded_keys(features: IPAFeatures) -> frozenset[str]:
    """Feature keys the ordinary per-key comparison must not count,
    because something else in the metric already carries their content.

    ``place`` and the secondary articulations are carried by the weighted
    place components: counting both would double-charge a secondary and
    push ``tʲ`` away from ``c`` instead of toward it, and dropping the key
    without adding the component subtracts the articulation outright
    (``ɫ`` would read as plain ``l``).

    A feature every one of whose informative values is claimed by a bridge
    is carried by that bridge, and counting it too would cancel the bridge
    out again (``ã`` would sit no nearer a nasal than plain ``a`` does).
    ``nasalized`` is such a feature; ``channel`` and ``release`` are not,
    because each also holds values no bridge claims. Derived rather than
    listed, so a bridge added to the data cannot leave a stale exclusion
    behind it. Memoized per inventory: this sits in the innermost loop of
    every distance, and the answer is a property of the data.

    A feature that *borrows* an excluded feature's vocabulary is excluded
    with it. ``constriction-location`` declares ``vocabulary="place"``,
    so its values are ``place``'s values; comparing them as an ordinary
    key would put back exactly the nominal place comparison the line
    above takes out, in a spelling the weighted components cannot see.
    The reason it matters here rather than in principle is that no vowel
    is obliged to state one, and a key present on one side and absent on
    the other scores the maximal difference, so counting it would say
    that schwa is further from ``i`` than ``i`` is from ``p``. What a
    stated location contributes is its ``arc``, and that reaches every
    distance through :func:`_tract_x`.
    """
    bridged: set[str] = set()
    for spellings in features.bridges.values():
        for name, _ in spellings:
            bridged.add(name)
    carried = set()
    for name in bridged:
        feat = features.features.get(name)
        if feat is None:
            continue
        claimed = {v for s in features.bridges.values() for f, v in s if f == name}
        informative = set(feat.values) - ({feat.default} if feat.default else set())
        if informative and informative <= claimed:
            carried.add(name)
    excluded = (
        set(METADATA_ATTRS) | {"place"} | set(features.secondary_places) | carried
    )
    borrowers = {
        name
        for name, feat in features.features.items()
        if feat.vocabulary is not None and feat.vocabulary in excluded
    }
    return frozenset(excluded | borrowers)


def _metric_bundle(
    features: IPAFeatures, constituent: Constituent
) -> tuple[dict[str, str], PlaceComponents]:
    """A constituent's comparable form: ordinary features (with the derived
    bridge features), plus place as weighted components."""
    bundle = constituent.bundle(features, with_defaults=True)
    excluded = excluded_keys(features)
    feats = {k: v for k, v in bundle.items() if k not in excluded}

    place_feature = features.features.get("place")

    def expand(value: str) -> tuple[str, ...]:
        return place_feature.expand(value) if place_feature is not None else (value,)

    components: list[tuple[str, float]] = []
    place = bundle.get("place")
    if place is not None:
        components.extend((comp, 1.0) for comp in expand(place))
    for key, secondary in features.secondary_places.items():
        if bundle.get(key) == "+":
            components.extend((comp, SECONDARY_WEIGHT) for comp in expand(secondary))

    # Bridge features (metric-only): the same phonetic dimension spelled
    # as manner, property, or release compares as one derived binary. The
    # spellings are declared in the data (<bridges>); what is derived here
    # is the comparison, not the phonetic equivalence. Not for non-speech
    # (silence has no nasality or laterality either - granting it the
    # negative would match every phone and dilute the difference right
    # back).
    manner_feature = features.features.get("manner")
    if manner_feature is not None and bundle.get("manner") in manner_feature.offscale:
        return feats, tuple(components)
    # The active articulator: place names the constriction target, this
    # names the organ that gets there. Resolved (a phone's own value, else
    # its place's default) so that same-place different-organ pairs -- a
    # linguolabial against a bilabial, apical against laminal -- are
    # visible to the metric at all.
    resolved = tract_point(features, bundle).articulator
    if resolved is not None:
        feats["articulator"] = resolved
    for bridge, spellings in features.bridges.items():
        feats[bridge] = "+" if any(bundle.get(f) == v for f, v in spellings) else "-"
    return feats, tuple(components)


def _sagittal(
    features: IPAFeatures, bundle: dict[str, str]
) -> tuple[float | None, float | None]:
    """A bundle's position in normalized tract space (arc, offset).

    The reference frame's axes are each stored twice, in features that
    never co-occur -- x as place (consonants) and backness (vowels),
    y as manner-constriction and height -- so cross-class spatial
    proximity is invisible to per-feature comparison. The tract
    coordinates (ipakit.tract) are the shared reading: real anchor
    positions along the midline, not scale-index proxies, so the arc
    spacing follows anatomy rather than assuming equal steps.
    """
    point = tract_point(features, bundle)
    return point.arc, point.offset


class _Unlocalized:
    """A tract-x reading with no single point: the segment constricts, but at
    no location the evidence localizes (a rhotic)."""

    __slots__ = ()

    def __repr__(self) -> str:  # lands in the fingerprint, so it is fixed text
        return "unlocalized"


_UNLOCALIZED = _Unlocalized()


def _tract_x(
    features: IPAFeatures, bundle: dict[str, str]
) -> tuple[tuple[float, float], ...] | _Unlocalized | None:
    """The tract-x reading: ``(arc, weight)`` for every constriction.

    A sorted tuple of every constriction's arc, so a double articulation is
    two positions rather than the average of two -- ``w`` closes at the lips
    AND the velum, not between them, and a click at its named place AND the
    velum. ``None`` where the segment holds no arc at all, exactly as the
    single-point reading did. ``_UNLOCALIZED`` where a stated feature
    declares its constriction has no single location: a rhotacized nucleus
    constricts, but the evidence gives no arc to place it at, so the metric
    withholds the whole term rather than inventing a position, including
    any localized secondary articulation the same segment states.

    Primary components and click closures weigh 1.0; secondary articulations
    weigh ``SECONDARY_WEIGHT``. A single-constriction segment yields one
    ``(arc, 1.0)`` entry and keeps the same distance and fingerprint text.
    """
    for name, feat in features.features.items():
        if feat.constriction == "unlocalized":
            value = bundle.get(name)
            if value is not None and value != feat.default:
                return _UNLOCALIZED
    arcs = tuple(
        sorted(
            (p.arc, SECONDARY_WEIGHT if p.kind == "secondary" else 1.0)
            for p in constrictions(features, bundle)
            if p.arc is not None
        )
    )
    return arcs or None


def _arc_distance(
    a: tuple[tuple[float, float], ...], b: tuple[tuple[float, float], ...]
) -> float:
    """Directional best-match between two sets of arcs, in [0, 1].

    ``max`` of the two directional means, the shape
    :func:`_weighted_place_distance` uses for place components. Over two
    weight-1.0 singletons it is ``|a - b|``, so a single-constriction pair
    scores exactly as the single-point subtraction did. The tuples are sorted,
    so the mean sums them in a fixed order and the matrix stays reproducible.
    """

    def direction(
        src: tuple[tuple[float, float], ...],
        dst: tuple[tuple[float, float], ...],
    ) -> float:
        total_weight = sum(weight for _, weight in src)
        return (
            sum(
                weight * min(abs(arc - target) for target, _ in dst)
                for arc, weight in src
            )
            / total_weight
        )

    return max(direction(a, b), direction(b, a))


def _tract_terms_text(features: IPAFeatures, bundle: dict[str, str]) -> list[str]:
    """The sagittal terms as fingerprint text: the arc(s), then the offset.

    A single-constriction bundle yields the two reprs the single point
    yielded; a double articulation yields one repr per constriction, and a
    rhotic the fixed ``unlocalized`` in the arc slot.
    """
    x = _tract_x(features, bundle)
    offset = _sagittal(features, bundle)[1]
    if isinstance(x, _Unlocalized):
        arcs = [repr(x)]
    elif x is None:
        arcs = [repr(None)]
    else:
        arcs = [
            repr(arc) if weight == 1.0 else repr((arc, weight)) for arc, weight in x
        ]
    return arcs + [repr(offset)]


def _weighted_place_distance(
    features: IPAFeatures, c1: PlaceComponents, c2: PlaceComponents
) -> float:
    """Weighted directional best-match over place components, max of the
    two directions. ``place(t, tʲ) = δσ/(1+σ)``; ``place(tʲ, c) = δ/(1+σ)``."""
    if not c1 and not c2:
        return 0.0
    if not c1 or not c2:
        return 1.0
    place_feature = features.features.get("place")

    def component_distance(a: str, b: str) -> float:
        if place_feature is not None:
            return place_feature.value_distance(a, b)
        return 0.0 if a == b else 1.0

    def direction(src: PlaceComponents, dst: PlaceComponents) -> float:
        total = sum(w * min(component_distance(v, v2) for v2, _ in dst) for v, w in src)
        weight = sum(w for _, w in src)
        return total / weight if weight else 0.0

    return max(direction(c1, c2), direction(c2, c1))


def _bundle_terms(
    features: IPAFeatures, a: Constituent, b: Constituent
) -> tuple[float, int]:
    """The summed term cost and term count for two constituents' bundles.
    :func:`bundle_distance` is their ratio; exposing them lets a caller fold
    in further terms (prosodic riders) at the same weight before dividing."""
    f1, p1 = _metric_bundle(features, a)
    f2, p2 = _metric_bundle(features, b)
    # Sorted, not set order: the loop below sums floats, and addition is
    # not associative, so iterating a set of strings makes the result
    # depend on Python's per-process hash randomization. The shipped
    # confusion matrix is a derived artifact checked in CI, so it has to
    # be reproducible bit for bit rather than only within a tolerance.
    keys = sorted(set(f1) | set(f2))
    include_place = bool(p1 or p2)
    total = 0.0
    for key in keys:
        feat = features.features.get(key)
        v1, v2 = f1.get(key), f2.get(key)
        if feat is not None:
            total += feat.value_distance(v1, v2)
        else:
            total += 0.0 if v1 == v2 else 1.0
    if include_place:
        total += _weighted_place_distance(features, p1, p2)
    count = len(keys) + (1 if include_place else 0)
    # Sagittal bridge terms: shared x (tract position) and y (aperture)
    # scalars make cross-class spatial proximity visible (j~i, w~u, k~u).
    b1 = a.bundle(features, with_defaults=True)
    b2 = b.bundle(features, with_defaults=True)
    # x (tract position) first, then y (aperture), in that order: the sum is
    # not associative and the shipped matrix is bit-reproducible, so the term
    # order the single-point reading used is kept.
    x1, x2 = _tract_x(features, b1), _tract_x(features, b2)
    if not (isinstance(x1, _Unlocalized) or isinstance(x2, _Unlocalized)):
        # A rhotic states no locatable x: the term is withheld, scored
        # neither 0 (identical) nor 1 (maximal). Otherwise several
        # constrictions compare by best-match, one absent against a present
        # one is maximal, and two absences are no difference -- as the single
        # point was.
        if x1 is not None or x2 is not None:
            total += (
                _arc_distance(x1, x2) if (x1 is not None and x2 is not None) else 1.0
            )
            count += 1
    y1, y2 = _sagittal(features, b1)[1], _sagittal(features, b2)[1]
    if y1 is not None or y2 is not None:
        total += abs(y1 - y2) if (y1 is not None and y2 is not None) else 1.0
        count += 1
    # No terms means no key on either side, no place on either side and no
    # tract coordinate on either side -- the two comparable forms are equal,
    # so the answer is 0, not the maximal difference this used to assert.
    # A constituent the metric cannot read is not this case: its keys are
    # present on one side only, each scores 1, and the mean is 1.0 anyway.
    return total, count


def bundle_distance(features: IPAFeatures, a: Constituent, b: Constituent) -> float:
    """Distance between two constituents' bundles, in [0, 1]."""
    total, count = _bundle_terms(features, a, b)
    return total / count if count else 0.0


@functools.cache
def _prosodic_anchor(features: IPAFeatures, feature: str) -> str | None:
    """The unmarked value of a prosodic feature -- the declared value no
    diacritic spells (stress's ``none``). A unit with no mark on this tier
    reads as this anchor, so an unstressed unit is a graded step from a
    stressed one rather than a categorical mismatch. ``None`` when every
    value is spelled (tone), where present-vs-absent is a full step."""
    feat = features.features.get(feature)
    if feat is None:
        return None
    spelled = {
        v
        for d in features.diacritics.values()
        for k, v in d.features.items()
        if k == feature
    }
    unspelled = [v for v in feat.values if v not in spelled]
    return unspelled[0] if len(unspelled) == 1 else None


def _segment_prosodic(features: IPAFeatures, segment: Segment) -> dict[str, str]:
    """The prosodic-tier values riding on a unit: its prosody marks mapped to
    the ``mode="prosodic"`` features they declare (stress, tone, length, ...).
    Read for the metric only -- the unit's stored features are untouched, so
    round-trips are unaffected. Empty when the unit carries no prosodic mark,
    which is every shipped phone."""
    out: dict[str, str] = {}
    spelled_twice: set[str] = set()
    prosodic = features.features_by_mode.get("prosodic", frozenset())
    for mark in getattr(segment, "prosody", ()) or ():
        decl = features.diacritics.get(mark)
        if decl is None:
            continue
        for feat, val in decl.features.items():
            # A sequence value is a trajectory (a tone contour, ``mid>high``),
            # not a point on the scale, so ``value_distance`` has no honest
            # answer for it; those stay out of the metric until a sequence
            # comparison exists. Single-level riders (stress, a plain tone,
            # length) ride here.
            if feat not in prosodic or Feature.SEQUENCER in val:
                continue
            # The same trajectory can be spelled across several marks
            # instead of inside one: ``a˩˥`` is two Chao letters, each
            # declaring a level of the one contour. Assigning here would
            # keep whichever came last, so ``a˩˥`` and ``a˧˥`` would ride
            # as ``top`` alike and score 0 against each other -- a
            # silently truncated contour, where the packed spelling
            # ``a᷅`` withholds honestly. A feature claimed by more than
            # one mark is therefore a sequence too, and is withheld the
            # same way, so the two spellings of one contour agree.
            if feat in out and out[feat] != val:
                spelled_twice.add(feat)
            out[feat] = val
    for feat in spelled_twice:
        del out[feat]
    return out


def _prosodic_terms(
    features: IPAFeatures, x: dict[str, str], y: dict[str, str]
) -> tuple[float, int]:
    """Summed cost and count of the prosodic-rider terms between two units.
    A term is added only when at least one unit carries that rider, so a pair
    with no prosody adds nothing and is scored exactly as before. Where both
    carry it, the ordinal ``value_distance`` grades them (primary vs secondary
    stress is half a step); where one is unmarked, it reads as the tier's
    anchor if one is declared, else a full step."""
    total = 0.0
    count = 0
    for key in sorted(set(x) | set(y)):
        feat = features.features.get(key)
        v1, v2 = x.get(key), y.get(key)
        if v1 is not None and v2 is not None:
            total += feat.value_distance(v1, v2) if feat else (0.0 if v1 == v2 else 1.0)
        else:
            present = v1 if v1 is not None else v2
            anchor = _prosodic_anchor(features, key)
            if anchor is not None and feat is not None:
                total += feat.value_distance(present, anchor)
            else:
                total += 1.0
        count += 1
    return total, count


def _parts(segment: Segment) -> tuple[Segment, ...]:
    children = segment.children
    return children if children else (segment,)


def _part_junctures(segment: Segment) -> tuple[Sense, ...]:
    parts = _parts(segment)
    if len(parts) == 1:
        return ()
    sense = Sense.SEQ if Sense.SEQ in segment.junctures else Sense.FUSE
    return tuple([sense] * (len(parts) - 1))


def _monotone_matchings(n: int, m: int) -> list[tuple[tuple[int, int], ...]]:
    """All order-preserving matchings between range(n) and range(m), as
    tuples of (i, j) pairs. Sizes here are tiny (parts of one unit)."""
    results: list[tuple[tuple[int, int], ...]] = []

    def extend(i: int, j: int, acc: tuple[tuple[int, int], ...]) -> None:
        if i == n or j == m:
            results.append(acc)
            return
        extend(i + 1, j + 1, acc + ((i, j),))  # match i with j
        extend(i + 1, j, acc)  # gap on the left side
        extend(i, j + 1, acc)  # gap on the right side

    extend(0, 0, ())
    return results


def _fold_prosody(seg_d: float, weight: int, pt: float, pc: int) -> float:
    """Fold prosodic-rider terms into a multi-constituent unit's distance,
    weighting the segmental result as ``weight`` equal terms so a rider sits at
    one-term weight beside them. A no-rider pair (``pc == 0``) is unchanged."""
    if not pc:
        return seg_d
    return (seg_d * weight + pt) / (weight + pc)


def _nearest_part_cost(
    features: IPAFeatures, part: Segment, present: tuple[Segment, ...]
) -> float:
    """Charge material by its nearest real comparison on the other side.

    This is the one extra-material convention for both composition paths:
    ordered alignment calls it for a part left unmatched by a candidate
    matching, while unordered reduction charges every source part the same
    way through :func:`_nearest_part`, which also reports which opposite
    part was selected. ``present`` is nonempty because every segment has a
    part.
    """
    return min(segment_metric(features, part, other) for other in present)


def _nearest_part(
    features: IPAFeatures, part: Segment, present: tuple[Segment, ...]
) -> tuple[int, float]:
    """The selected opposite part and its cost, with metric tie-breaking."""
    choices = tuple(segment_metric(features, part, other) for other in present)
    cost = min(choices)
    return choices.index(cost), cost


@functools.cache
def _arity_base(features: IPAFeatures) -> float:
    """The normalized mass of one added constituent in an unordered fusion.

    Arity is one categorical structural fact, so it carries the mass of one
    ordinary atomic comparison term. The base is ``1 / min(term counts)`` over
    the inventory's one-constituent atoms after off-scale non-speech atoms are
    excluded. That filter is load-bearing: silence has one term, so retaining
    it would set the base to ``1 / 1`` instead of the shipped speech minimum
    ``1 / 20``. Marked speech atoms remain in the population; their optional
    terms give them 21 or more terms, so they do not attain the minimum. The
    base changes if the declared atomic feature budget or off-scale boundary
    changes.

    This derivation deliberately reads neither ``release`` nor the cost of any
    release-marked pair. The ordering between an added articulator and a
    release phase is consequently a falsifiable result, not a restatement of
    the arity definition.
    """
    manner = features.features.get("manner")
    counts = []
    for symbol in features.phones:
        segment = features.segment(symbol)
        if len(segment.constituents) != 1:
            continue
        bundle = segment.constituents[0].bundle(features, with_defaults=True)
        if manner is not None and bundle.get("manner") in manner.offscale:
            continue
        counts.append(
            _bundle_terms(features, segment.constituents[0], segment.constituents[0])[1]
        )
    if not counts:  # pragma: no cover - a valid IPA inventory has speech atoms
        raise ValueError("fusion arity needs at least one declared atomic speech unit")
    return 1.0 / min(counts)


def segment_metric(
    features: IPAFeatures,
    x: Segment,
    y: Segment,
    *,
    _rows: list[tuple[str, str | None, str | None, float]] | None = None,
) -> float:
    """The structural distance ``D`` (design spec section 7), plus the unit's
    prosodic riders. In [0, 1] and symmetric.

    Prosodic-tier marks -- stress, tone, length -- ride on the unit clock: each
    tier the two units differ on adds one graded term, at the same weight as a
    segmental feature, read via the ordinal ``value_distance`` (primary vs
    secondary stress is half a step). A pair where neither unit carries a rider
    adds nothing, so every shipped phone -- which carries none -- is scored
    exactly as before, and the prosody a unit stores stays untouched, so
    round-trips are unaffected."""
    pt, pc = _prosodic_terms(
        features, _segment_prosodic(features, x), _segment_prosodic(features, y)
    )
    x_silence = any(
        part.bundle(features, with_defaults=True).get("manner") == "silence"
        for part in x.constituents
    )
    y_silence = any(
        part.bundle(features, with_defaults=True).get("manner") == "silence"
        for part in y.constituents
    )
    if x_silence != y_silence:
        if _rows is not None:
            _rows.append(("silence", x.to_ipa(), y.to_ipa(), 1.0))
        return 1.0
    if len(x.constituents) == 1 and len(y.constituents) == 1:
        bt, bc = _bundle_terms(features, x.constituents[0], y.constituents[0])
        if _rows is not None:
            _rows.extend(_atomic_rows(features, x, y))
            _rows.extend(_prosodic_rows(features, x, y))
        return (bt + pt) / (bc + pc) if (bc + pc) else 0.0

    ordered = x.phased or y.phased
    px, py = _parts(x), _parts(y)

    if not ordered:

        def direction(
            src: tuple[Segment, ...], dst: tuple[Segment, ...]
        ) -> tuple[float, list[tuple[int, int, float]]]:
            selected = [
                (i, *_nearest_part(features, part, dst)) for i, part in enumerate(src)
            ]
            return sum(cost for _, _, cost in selected) / len(src), selected

        dx, x_selected = direction(px, py)
        dy, y_selected = direction(py, px)
        arity = abs(len(px) - len(py))
        arity_cost = arity * _arity_base(features)
        selected_costs = x_selected if dx >= dy else y_selected
        # Sum in the same form the trace exposes. Besides keeping exact
        # reconstruction, this states the additive law directly: every row's
        # graded share remains, and their common arity share adds ``A`` after
        # the mean rather than replacing or flooring it.
        seg_d = min(
            1.0,
            sum(cost + arity_cost for _, _, cost in selected_costs)
            / len(selected_costs),
        )
        if _rows is not None:
            src, dst, selected, side = (
                (px, py, x_selected, "a") if dx >= dy else (py, px, y_selected, "b")
            )
            for i, j, cost in selected:
                _rows.append(
                    (
                        f"part {side}[{i}] nearest opposite[{j}]"
                        + (" + arity share" if arity else ""),
                        src[i].to_ipa(),
                        dst[j].to_ipa(),
                        min(1.0, cost + arity_cost),
                    )
                )
            _rows.extend(_prosodic_rows(features, x, y))
        return _fold_prosody(seg_d, max(len(px), len(py)), pt, pc)

    jx, jy = _part_junctures(x), _part_junctures(y)
    best = 1.0
    best_rows: list[tuple[str, str | None, str | None, float]] = []
    for matching in _monotone_matchings(len(px), len(py)):
        if len(matching) != min(len(px), len(py)):
            # Every part on the shorter side makes a real pair. Once gaps are
            # graded, dropping material on both sides would manufacture an
            # indirect shortcut (including between two equal-arity units).
            continue
        matched = dict(matching)
        pair_cost = sum(segment_metric(features, px[i], py[j]) for i, j in matching)
        unmatched_cost = sum(
            _nearest_part_cost(features, px[i], py)
            for i in range(len(px))
            if i not in matched
        ) + sum(
            _nearest_part_cost(features, py[j], px)
            for j in range(len(py))
            if j not in matched.values()
        )
        gaps = (len(px) - len(matching)) + (len(py) - len(matching))
        juncture_terms = 0
        juncture_cost = 0.0
        aligned_j = {
            (i, matched[i])
            for i in matched
            if i + 1 in matched and matched[i + 1] == matched[i] + 1
        }
        for i, j in aligned_j:
            juncture_terms += 1
            if jx[i] is not jy[j]:
                juncture_cost += 1.0
        unaligned = (len(jx) - len(aligned_j)) + (len(jy) - len(aligned_j))
        juncture_terms += unaligned
        juncture_cost += unaligned
        # A real pair is one comparison term. A gap carries that comparison
        # plus the unmatched part's own material term: the declared budget
        # distinguishes an orphan's mass from the value used to price it.
        denom = len(matching) + 2 * gaps + juncture_terms
        if denom == 0:
            continue
        value = (pair_cost + unmatched_cost + juncture_cost) / denom
        chosen = value < best
        if chosen:
            best = value
        if _rows is not None and (chosen or not best_rows):
            candidate: list[tuple[str, str | None, str | None, float]] = []
            for i, j in matching:
                nested = (
                    " (nested composite)"
                    if len(px[i].constituents) > 1 or len(py[j].constituents) > 1
                    else ""
                )
                candidate.append(
                    (
                        f"matched part a[{i}]~b[{j}]{nested}",
                        px[i].to_ipa(),
                        py[j].to_ipa(),
                        segment_metric(features, px[i], py[j]),
                    )
                )
            for side, parts, opposite, used in (
                ("a", px, py, set(matched)),
                ("b", py, px, set(matched.values())),
            ):
                for i, part in enumerate(parts):
                    if i in used:
                        continue
                    j, cost = _nearest_part(features, part, opposite)
                    candidate.append(
                        (
                            f"unmatched part {side}[{i}] nearest opposite[{j}]",
                            part.to_ipa(),
                            opposite[j].to_ipa(),
                            cost,
                        )
                    )
                    candidate.append(
                        (
                            f"unmatched part {side}[{i}] material",
                            part.to_ipa(),
                            None,
                            0.0,
                        )
                    )
            for i, j in sorted(aligned_j):
                candidate.append(
                    (
                        f"juncture a[{i}]~b[{j}]",
                        jx[i].value,
                        jy[j].value,
                        0.0 if jx[i] is jy[j] else 1.0,
                    )
                )
            aligned_x = {i for i, _ in aligned_j}
            aligned_y = {j for _, j in aligned_j}
            for side, junctures, aligned_set in (
                ("a", jx, aligned_x),
                ("b", jy, aligned_y),
            ):
                for i, sense in enumerate(junctures):
                    if i not in aligned_set:
                        candidate.append(
                            (f"unaligned juncture {side}[{i}]", sense.value, None, 1.0)
                        )
            best_rows = candidate
    if _rows is not None:
        _rows.extend(best_rows)
        _rows.extend(_prosodic_rows(features, x, y))
    return _fold_prosody(best, max(len(px), len(py)), pt, pc)


def _atomic_rows(
    features: IPAFeatures, x: Segment, y: Segment
) -> list[tuple[str, str | None, str | None, float]]:
    """Named rows for the atomic bundle path."""
    rows: list[tuple[str, str | None, str | None, float]] = []
    f1, p1 = _metric_bundle(features, x.constituents[0])
    f2, p2 = _metric_bundle(features, y.constituents[0])
    for key in sorted(set(f1) | set(f2)):
        feat = features.features.get(key)
        v1, v2 = f1.get(key), f2.get(key)
        cost = (
            feat.value_distance(v1, v2)
            if feat is not None
            else (0.0 if v1 == v2 else 1.0)
        )
        rows.append((key, v1, v2, cost))
    if p1 or p2:
        rows.append(("place", None, None, _weighted_place_distance(features, p1, p2)))
    b1 = x.constituents[0].bundle(features, with_defaults=True)
    b2 = y.constituents[0].bundle(features, with_defaults=True)
    x1, x2 = _tract_x(features, b1), _tract_x(features, b2)
    if not (isinstance(x1, _Unlocalized) or isinstance(x2, _Unlocalized)) and (
        x1 is not None or x2 is not None
    ):
        rows.append(
            (
                "tract-x",
                None,
                None,
                _arc_distance(x1, x2) if (x1 is not None and x2 is not None) else 1.0,
            )
        )
    y1, y2 = _sagittal(features, b1)[1], _sagittal(features, b2)[1]
    if y1 is not None or y2 is not None:
        rows.append(
            (
                "tract-y",
                None,
                None,
                abs(y1 - y2) if (y1 is not None and y2 is not None) else 1.0,
            )
        )
    return rows


def _prosodic_rows(
    features: IPAFeatures, x: Segment, y: Segment
) -> list[tuple[str, str | None, str | None, float]]:
    rows: list[tuple[str, str | None, str | None, float]] = []
    # prosodic riders
    xp, yp = _segment_prosodic(features, x), _segment_prosodic(features, y)
    for key in sorted(set(xp) | set(yp)):
        feat = features.features.get(key)
        v1, v2 = xp.get(key), yp.get(key)
        if v1 is not None and v2 is not None:
            cost = feat.value_distance(v1, v2) if feat else (0.0 if v1 == v2 else 1.0)
        else:
            present = v1 if v1 is not None else v2
            anchor_v = _prosodic_anchor(features, key)
            cost = (
                feat.value_distance(present, anchor_v)
                if (anchor_v is not None and feat is not None)
                else 1.0
            )
            v1, v2 = v1 or anchor_v, v2 or anchor_v
        rows.append((f"{key} (prosodic)", v1, v2, cost))
    return rows


def segment_terms(
    features: IPAFeatures, x: Segment, y: Segment
) -> list[tuple[str, str | None, str | None, float]]:
    """The flat, non-overlapping term breakdown behind ``segment_metric``.

    Atomic pairs expose their named bundle terms. Composite pairs expose the
    selected outer comparisons, unmatched-material charges, and junctures;
    matched parts remain one row because the metric weights their own distance
    as one outer term. Consequently ``sum(cost) / len(rows)`` reconstructs the
    metric without counting a parent aggregate beside children.
    """
    rows: list[tuple[str, str | None, str | None, float]] = []
    distance = segment_metric(features, x, y, _rows=rows)
    if rows and sum(row[3] for row in rows) / len(rows) != distance:
        # The metric deliberately groups its three ordered subtotals before
        # adding them. Preserve that last-bit result in a flat report: absorb
        # only the binary-addition residue into the first non-categorical row.
        # (Rendered costs round to four decimals, so this is never a phonetic
        # charge; it is solely what makes the public reconstruction exact.)
        index = next((i for i, row in enumerate(rows) if "juncture" not in row[0]), 0)
        others = sum(row[3] for i, row in enumerate(rows) if i != index)
        label, a, b, _ = rows[index]
        rows[index] = (label, a, b, distance * len(rows) - others)
    return rows


#: Bytes of digest a fingerprint carries. Sixty-four bits, because the
#: question it answers is "is this the same space", not "who wrote this":
#: two feature spaces colliding by accident is not a failure mode, and a
#: short digest stays readable in a diff of a derived file.
FINGERPRINT_BYTES = 8


def _fingerprint_lines(features: IPAFeatures, phones: tuple[str, ...]) -> Iterator[str]:
    """Everything a distance between two of ``phones`` can depend on, as text."""
    for material, mass, shape in MATERIAL_BUDGET:
        yield f"mass-budget\t{material}\t{mass}\t{shape}"
    yield f"SECONDARY_WEIGHT\t{SECONDARY_WEIGHT!r}"
    for phone in phones:
        with warnings.catch_warnings():
            # A phone this inventory cannot read is a difference, not an
            # incident: it lands in the digest as one and the caller hears
            # about it as a refusal, not as a warning about a phone list.
            warnings.simplefilter("ignore")
            try:
                constituents = features.segment(phone).constituents
            except ValueError:
                yield "unreadable"
                continue
        for constituent in constituents:
            feats, components = _metric_bundle(features, constituent)
            bundle = constituent.bundle(features, with_defaults=True)
            yield "\t".join(
                [f"{key}={value}" for key, value in sorted(feats.items())]
                + [f"{place}*{weight!r}" for place, weight in components]
                + _tract_terms_text(features, bundle)
            )
    # Every declared feature EXCEPT the structural ones, and the exception
    # is what makes this agree with the metric rather than merely track it.
    # A structural feature is excluded from every phone bundle by
    # construction -- the mode gate drops it before a bundle is built -- so
    # it cannot reach a distance through a phone or through a mark, which
    # is the route `phonation` takes and the reason this half is not
    # restricted to the features the listed phones spell.
    #
    # Including them made the digest stricter than the metric, and the gap
    # had a cost: declaring `tier` moves 0 of 9591 distances and still
    # invalidated every saved matrix, so a language declaring a tier of its
    # own was refused a matrix that was provably still correct for it.
    # Tiers and their inventories are language-relative and the feature
    # space is not, so declaring one must leave a saved matrix standing.
    #
    # Omitting them outright rather than digesting a reduced line is
    # deliberate: it means declaring one changes nothing, which is the
    # property wanted. A mode change is still caught in both directions,
    # because it moves the feature into or out of this loop and so adds or
    # removes a line. And two inventories differing only in a structural
    # feature agree here, which is correct -- their matrices are
    # interchangeable.
    structural = features.features_by_mode.get("structural", frozenset())
    for name in sorted(features.features):
        if name in structural:
            continue
        feature = features.features[name]
        values = list(feature.values)
        yield "\t".join(
            [name, feature.type, str(feature.default), *values]
            + [repr(feature.value_distance(a, b)) for a in values for b in values]
        )


def metric_fingerprint(features: IPAFeatures, phones: Iterable[str]) -> str:
    """Digest of the feature space distances over ``phones`` are computed in.

    A saved matrix is a set of numbers whose meaning is the space they
    were derived in, and a reader had no way to ask which space that was.
    ``phones`` does not answer it: it detects membership drift, and a
    bridge -- a whole extra term in the denominator of every distance --
    changes no membership at all. This is what the reader compares.

    Two halves, both asked of the metric rather than listed here, so
    neither can go stale against a change to what the metric reads:

    - **What the metric reads off each phone**: the comparison bundle and
      the weighted place components :func:`_metric_bundle` derives, and
      the two tract coordinates :func:`bundle_distance` sums beside them.
    - **How any two values of a declared feature compare**: the ordered
      value list, the declared type and default, and the full
      ``value_distance`` table. Every declared feature, not only the ones
      the listed phones happen to spell -- ``phonation`` reaches the
      metric through marks and through nothing in the phone table, so a
      digest of the bundles alone is still for a change that reprices
      every devoiced segment in the inventory.

    Taking the first half over a **caller-supplied** phone list is what
    makes it membership-independent, and membership-independence is what
    makes it usable: a supplement adds phones and declares nothing, so an
    inventory built with one must agree with a matrix derived before it.
    Reading the list the matrix file itself carries gives exactly that,
    and leaves membership to ``phones``, which is already the check for
    it. The second half needs no such care -- a supplement may not
    declare a feature, a type or a bridge.

    Order-fixed throughout: the phone list is read in order, feature names
    are sorted, bundle keys are sorted, and floats are written as
    ``repr``. Nothing iterates a set, so the digest does not move with
    ``PYTHONHASHSEED``.

    Memoized per (inventory, phone list), the way :func:`excluded_keys` is
    memoized per inventory: it is read on the path every default model is
    built on, and the answer is a property of the data. The phone list is
    part of the key because it is part of the question -- the same
    inventory over a wider list is a different fingerprint, and a cache
    that answered one for the other would be worse than no check at all.
    Keys compare by value, so hash randomization moves where an entry
    sits and never what it says.
    """
    return _fingerprint(features, tuple(phones))


@functools.cache
def _fingerprint(features: IPAFeatures, phones: tuple[str, ...]) -> str:
    digest = hashlib.blake2b(digest_size=FINGERPRINT_BYTES)
    for line in _fingerprint_lines(features, phones):
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
