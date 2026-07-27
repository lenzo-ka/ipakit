"""Structural distance over Segments (design spec section 7).

Distance is computed over the derived grouping, never the flat feature
bag: constituents compare as whole bundles, alignment mode follows the
unit kinds (ordered where order is meaning, unordered where it is
notation), junctures carry the binding-sense term, and secondary
articulations enter as weighted place components. All values lie in
[0, 1].

Key properties, pinned by tests:

- ``D(ɡ, ɡ͡b) = d_b(ɡ, b) / 2`` — sharing one articulation is half the
  distance of the unshared one (unordered best-match with a lifted
  singleton).
- ``D(u͡i, u͜i) = 1/3`` — same constituents, different timing claim: one
  juncture-sense mismatch over three terms.
- ``place(t, tʲ) = δ/3 < place(tʲ, c) = 2δ/3 < place(t, c) = δ`` — a
  secondary articulation moves a segment toward its secondary place,
  strictly between the plain segments.
- ``D(u͡i, i͡u) = 0`` but ``D(a͡t, t͡a) > 0`` — double articulation is
  unordered notation; phased units are ordered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import METADATA_ATTRS
from .segment import Constituent, Kind, Segment, Sense, modifier_mode

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures

# Ordered-alignment gap cost (design spec section 11).
GAP_COST = 1.0
# Secondary-articulation place weight.
SECONDARY_WEIGHT = 0.5

# Secondary-articulation modifiers -> the place component they contribute.
SECONDARY_PLACE = {
    "ʲ": "palatal",
    "ʷ": "bilabial",
    "ˠ": "velar",
    "ˤ": "pharyngeal",
}

# Combining place values (bilabial+velar) carry their expansion in the
# name; Feature.expand supplies the components.

# Kinds whose part order is meaning (phased units and sequences); pairs
# involving any of these align ordered. Single-block fusions and atomic
# units are unordered notation.
ORDERED_KINDS = frozenset(
    {
        Kind.AFFRICATE,
        Kind.PRENASALIZED,
        Kind.PRE_STOPPED,
        Kind.LATERAL_RELEASE,
        Kind.CLICK_ACCOMPANIMENT,
        Kind.OVERLAY,
        Kind.DIPHTHONG,
        Kind.CHAIN,
    }
)

# Secondary-articulation property keys stay in the scalar projection for
# compatibility, but in the metric their content is carried entirely by
# the weighted place components -- counting both would double-charge a
# secondary articulation and push tʲ away from c instead of toward it.
_SECONDARY_KEYS = frozenset(
    {"palatalized", "labialized", "velarized", "pharyngealized", "labio-palatized"}
)
# nasalized's content is carried by the nasality bridge feature the same
# way; counting both would cancel the bridge (ã would sit no nearer to a
# nasal than plain a does).
_EXCLUDED_KEYS = METADATA_ATTRS | {"class", "place", "nasalized"} | _SECONDARY_KEYS

PlaceComponents = tuple[tuple[str, float], ...]

# Sagittal bridges: the reference frame's axes are each stored twice --
# x as place (consonants) and backness (vowels), y as manner-constriction
# and height -- in features that never co-occur, so cross-class spatial
# proximity (j~i, w~u, k~u) is invisible to per-feature comparison. The
# bridges project both classes onto shared scalars.
# Vowel space occupies the open half of the aperture axis; consonantal
# constriction stacks above it, approximants adjacent to close vowels.
_VOWEL_APERTURE_TOP = 0.5


def _metric_bundle(
    features: IPAFeatures, constituent: Constituent
) -> tuple[dict[str, str], PlaceComponents]:
    """A constituent's comparable form: ordinary features (with the derived
    bridge features), plus place as weighted components."""
    bundle = constituent.bundle(features, with_defaults=True)
    feats = {k: v for k, v in bundle.items() if k not in _EXCLUDED_KEYS}

    components: list[tuple[str, float]] = []
    place = bundle.get("place")
    if place is not None:
        place_feature = features.features.get("place")
        comps = place_feature.expand(place) if place_feature else (place,)
        for comp in comps:
            components.append((comp, 1.0))
    for mod in constituent.modifiers:
        if modifier_mode(features, mod) == "secondary" and mod in SECONDARY_PLACE:
            components.append((SECONDARY_PLACE[mod], SECONDARY_WEIGHT))

    # Bridge features (metric-only, design spec section 8): the same
    # phonetic dimension spelled as manner, property, or release compares
    # as one derived binary.
    feats["nasality"] = (
        "+"
        if (
            bundle.get("manner") == "nasal"
            or bundle.get("nasalized") == "+"
            or bundle.get("release") == "nasal"
        )
        else "-"
    )
    feats["laterality"] = (
        "+"
        if (bundle.get("lateral") == "+" or bundle.get("release") == "lateral")
        else "-"
    )
    return feats, tuple(components)


def _sagittal(
    features: IPAFeatures, bundle: dict[str, str], place_components: PlaceComponents
) -> tuple[float | None, float | None]:
    """(x, y) tract position in [0, 1]: x lips->glottis, y aperture
    (0 open .. 1 closed). Consonants take x from their most posterior
    lingual place component and y from constriction; vowels take x from
    backness mapped into the palatal..uvular span (the classic
    correspondence) and y from height within the open half."""
    place_feature = features.features.get("place")
    manner = bundle.get("manner")
    x: float | None = None
    y: float | None = None
    if place_feature is not None:
        idx = place_feature._value_index
        span = len(idx) - 1
        if manner == "vowel":
            backness_feature = features.features.get("backness")
            backness = bundle.get("backness")
            if backness_feature is not None and backness is not None:
                b_idx = backness_feature._value_index.get(backness)
                b_span = len(backness_feature._value_index) - 1
                lo, hi = idx.get("palatal"), idx.get("uvular")
                if b_idx is not None and lo is not None and hi is not None:
                    x = (lo + (hi - lo) * (b_idx / b_span)) / span
        elif place_components:
            # Primary components only: a secondary articulation shades the
            # place term but does not relocate the tongue body.
            pos = [idx.get(comp) for comp, w in place_components if w >= 1.0]
            known = [i for i in pos if i is not None]
            if known:
                x = max(known) / span
    manner_feature = features.features.get("manner")
    if manner_feature is not None and manner is not None:
        if manner == "vowel":
            height_feature = features.features.get("height")
            height = bundle.get("height")
            if height_feature is not None and height is not None:
                h_idx = height_feature._value_index.get(height)
                h_span = len(height_feature._value_index) - 1
                if h_idx is not None:
                    y = _VOWEL_APERTURE_TOP * (h_idx / h_span)
        else:
            m_idx = manner_feature._value_index.get(manner)
            v_idx = manner_feature._value_index.get("vowel")
            m_span = len(manner_feature._value_index) - 1
            if m_idx is not None and v_idx is not None and m_idx > v_idx:
                rel = (m_idx - v_idx) / (m_span - v_idx)
                y = _VOWEL_APERTURE_TOP + rel * (1.0 - _VOWEL_APERTURE_TOP)
    return x, y


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


def bundle_distance(features: IPAFeatures, a: Constituent, b: Constituent) -> float:
    """Distance between two constituents' bundles, in [0, 1]."""
    f1, p1 = _metric_bundle(features, a)
    f2, p2 = _metric_bundle(features, b)
    keys = set(f1) | set(f2)
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
    for s1, s2 in zip(
        _sagittal(features, b1, p1), _sagittal(features, b2, p2), strict=True
    ):
        if s1 is None and s2 is None:
            continue
        total += abs(s1 - s2) if (s1 is not None and s2 is not None) else 1.0
        count += 1
    return total / count if count else 1.0


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


def segment_metric(features: IPAFeatures, x: Segment, y: Segment) -> float:
    """The structural distance ``D`` (design spec section 7). Prosody is
    excluded; the result is in [0, 1] and symmetric."""
    if len(x.constituents) == 1 and len(y.constituents) == 1:
        return bundle_distance(features, x.constituents[0], y.constituents[0])

    ordered = x.kind in ORDERED_KINDS or y.kind in ORDERED_KINDS
    px, py = _parts(x), _parts(y)

    if not ordered:

        def direction(src: tuple[Segment, ...], dst: tuple[Segment, ...]) -> float:
            return sum(
                min(segment_metric(features, s, d) for d in dst) for s in src
            ) / len(src)

        return max(direction(px, py), direction(py, px))

    jx, jy = _part_junctures(x), _part_junctures(y)
    best = 1.0
    for matching in _monotone_matchings(len(px), len(py)):
        matched = dict(matching)
        pair_cost = sum(segment_metric(features, px[i], py[j]) for i, j in matching)
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
        denom = len(matching) + gaps + juncture_terms
        if denom == 0:
            continue
        value = (pair_cost + GAP_COST * gaps + juncture_cost) / denom
        best = min(best, value)
    return best
