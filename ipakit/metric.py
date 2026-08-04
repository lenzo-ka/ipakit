"""Structural distance over Segments (design spec section 7).

Distance is computed over the derived grouping, never the flat feature
bag: constituents compare as whole bundles, alignment mode follows the
unit's phase structure (ordered where order is meaning, unordered where
it is notation), junctures carry the binding-sense term, and secondary
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
- ``D(u͡i, i͡u) = 0`` but ``D(a͡t, t͡a) > 0`` — a single-block fusion is
  unordered notation; phased units are ordered.
"""

from __future__ import annotations

import functools
import hashlib
import warnings
from typing import TYPE_CHECKING

from .constants import METADATA_ATTRS
from .segment import Constituent, Segment, Sense
from .tract import tract_point

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable, Iterator

    from .features import IPAFeatures

# Ordered-alignment gap cost (design spec section 11).
GAP_COST = 1.0
# Secondary-articulation place weight.
SECONDARY_WEIGHT = 0.5

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
    is obliged to state one: 16 do and 23 do not, and a key present on
    one side and absent on the other scores the maximal difference, so
    counting it would say that schwa is further from ``i`` than ``i`` is
    from ``p``. What a stated location contributes is its ``arc``, and
    that reaches every distance through :func:`_sagittal`.
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
    for s1, s2 in zip(_sagittal(features, b1), _sagittal(features, b2), strict=True):
        if s1 is None and s2 is None:
            continue
        total += abs(s1 - s2) if (s1 is not None and s2 is not None) else 1.0
        count += 1
    # No terms means no key on either side, no place on either side and no
    # tract coordinate on either side -- the two comparable forms are equal,
    # so the answer is 0, not the maximal difference this used to assert.
    # A constituent the metric cannot read is not this case: its keys are
    # present on one side only, each scores 1, and the mean is 1.0 anyway.
    return total / count if count else 0.0


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

    ordered = x.phased or y.phased
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


#: Bytes of digest a fingerprint carries. Sixty-four bits, because the
#: question it answers is "is this the same space", not "who wrote this":
#: two feature spaces colliding by accident is not a failure mode, and a
#: short digest stays readable in a diff of a derived file.
FINGERPRINT_BYTES = 8


def _fingerprint_lines(features: IPAFeatures, phones: tuple[str, ...]) -> Iterator[str]:
    """Everything a distance between two of ``phones`` can depend on, as text."""
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
                + [repr(coordinate) for coordinate in _sagittal(features, bundle)]
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
    # docs/design/tiers.md §7 promises that does not happen.
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
