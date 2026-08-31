"""One parameter surface for cost models over one alignment fold.

Packs are always made by factories that take their geometry as an argument;
no pack constructor hardwires a geometry.  This keeps cost model and geometry
as separate, explicitly identified parts of every comparison cell.
"""

from __future__ import annotations

import math
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from typing import Protocol

from tiergraph.semiring import TROPICAL, ProductSemiring

from ..distance import Alignment, PhoneCost, _prices, _substitution_cost, price
from ..distance_model import DistanceModel
from ..features import IPAFeatures
from ..metric import GAP_COST
from .base import Bridge, Fidelity, RoundTripLeg, RoundTripReport

COSTMODEL_VERSION = "1.0"


class Normalization(StrEnum):
    """What an alignment cost is divided by before it is reported."""

    RAW = "raw"
    DIV_MAXLEN = "div-maxlen"
    DIV_NULL_ALIGNMENT = "div-null-alignment"


class DeclaredCostFamily(StrEnum):
    """Which generic arithmetic family a ternary declaration supplies.

    These names describe formulas rather than the foreign system whose table
    first motivated them.  Keeping the family independent of the declaration
    is what lets an experiment vary geometry and cost functions separately.
    """

    SYMMETRIC_DIFFERENCE = "symmetric-difference"
    WEIGHTED_DIFFERENCE = "weighted-difference"


class AbsentCell(StrEnum):
    """What an explicitly absent declaration cell contributes to one fold.

    Absence changes the index set, not the policy scalar.  Each member is the
    same product-semiring fold with a different declared term, which makes an
    absence treatment substitutable without changing the program around it.
    """

    SKIP = "skip"
    ZERO_COUNTED = "zero-counted"
    HALF_COUNTED = "half-counted"


@dataclass(frozen=True)
class CostPolicy:
    """What a comparison charges, stated once for both cost models."""

    substitution_scale: float = 1.0
    indel_weight: float = 1.0
    normalization: Normalization = Normalization.RAW

    def __post_init__(self) -> None:
        for field in ("substitution_scale", "indel_weight"):
            value = getattr(self, field)
            number = float(value)
            if not math.isfinite(number) or number < 0.0:
                raise ValueError(
                    f"{field} must be a non-negative finite number; got {value!r}"
                )
            object.__setattr__(self, field, number)

    @property
    def is_faithful(self) -> bool:
        """True when each arm reproduces its own system unmodified."""
        return (
            self.substitution_scale == 1.0
            and self.indel_weight == 1.0
            and self.normalization is Normalization.RAW
        )

    @property
    def identity(self) -> str:
        """One line naming this policy, version and all."""
        return (
            f"costmodel/{COSTMODEL_VERSION} "
            f"sub_scale={self.substitution_scale!r} "
            f"indel={self.indel_weight!r} norm={self.normalization.value}"
        )


PANPHON_CONSERVING = CostPolicy(substitution_scale=2.0)
CHEAP_INDEL = CostPolicy(indel_weight=0.25)
FAITHFUL = CostPolicy()


@dataclass(frozen=True)
class Segmentation:
    """A word as one cost model reads it, and what that reading threw away."""

    tokens: tuple[str, ...]
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True)
class CostPack:
    """Three callables and their ceilings: one cost model and one policy."""

    name: str
    geometry: str
    sub_cost: Callable[[str, str], float]
    insert_cost: PhoneCost
    delete_cost: PhoneCost
    substitution_ceiling: float
    indel_ceiling: float
    tokenize: Callable[[str], Segmentation]
    policy: CostPolicy
    #: The reference distribution a percentile was taken against, where the
    #: pack is inventory-relative. None for the portable packs.
    reference: str | None = None
    bridge: Bridge | None = None

    @property
    def budget_ratio(self) -> float:
        """Return ``substitution_ceiling / indel_ceiling``."""
        return self.substitution_ceiling / self.indel_ceiling


class DroppedMaterial(ValueError):
    """A cost model discarded input, and the caller asked to be told."""


@dataclass(frozen=True)
class ComparisonRow:
    """One number, and everything needed to say what it is a number of."""

    policy: str
    pack: str
    geometry: str
    budget_ratio: float
    edit_cost: float
    normalized: float
    dropped: tuple[str, ...]
    alignment: Alignment | None = None
    geometry_mapping: str | None = None
    #: The reference distribution behind an inventory-relative figure.
    #: Two numbers ranked over different inventories are not comparable
    #: and nothing in the numbers says so, which is why this travels.
    reference: str | None = None


def align_under(
    ipa: IPAFeatures,
    pack: CostPack,
    source: Segmentation,
    target: Segmentation,
    *,
    return_alignment: bool = False,
) -> tuple[float, Alignment | None]:
    """Run one cost pack through ipakit's existing tropical alignment fold.

    The production comparison takes both cost and optional witness from this
    single DP. ``semiring_alignment`` remains the experimental route for
    substituting another algebra; running both would charge every comparison
    for two full grids merely to discard one result.
    """
    return ipa._align(
        list(source.tokens),
        list(target.tokens),
        pack.sub_cost,
        pack.insert_cost,
        pack.delete_cost,
        return_alignment,
    )


class FoldSemiring[Carrier](Protocol):
    """The four operations the alignment fold is permitted to know about."""

    zero: Carrier
    one: Carrier

    def add(self, left: Carrier, right: Carrier, /) -> Carrier:
        """Combine alternative paths."""

    def multiply(self, left: Carrier, right: Carrier, /) -> Carrier:
        """Extend one path by one move."""


@dataclass(frozen=True)
class WinningPayloadSemiring[Carrier, Payload]:
    """Carry the payload belonging to the move selected by a semiring.

    ``ProductSemiring`` is wrong for this job because it selects each field
    independently.  This adapter asks the supplied selective semiring which
    whole operand won and returns that operand's payload; multiplication uses
    a caller-supplied payload fold.  It is used on scaled tropical integers,
    where float addition is exact, because tiergraph correctly refuses to
    label its general float tropical multiplication exact enough for
    ``LexicographicSemiring``.  Decimal is not substituted: ``k/2n`` repeats
    there too, while the scaled integers are exact in ordinary floats.
    """

    values: FoldSemiring[Carrier]
    payload_zero: Payload
    payload_one: Payload
    payload_multiply: Callable[[Payload, Payload], Payload]

    @property
    def zero(self) -> tuple[Carrier, Payload]:
        """Return the paired additive identity."""
        return (self.values.zero, self.payload_zero)

    @property
    def one(self) -> tuple[Carrier, Payload]:
        """Return the paired multiplicative identity."""
        return (self.values.one, self.payload_one)

    def add(
        self,
        left: tuple[Carrier, Payload],
        right: tuple[Carrier, Payload],
        /,
    ) -> tuple[Carrier, Payload]:
        """Return the complete operand whose value the semiring selects."""
        preferred = self.values.add(left[0], right[0])
        return left if preferred == left[0] else right

    def multiply(
        self,
        left: tuple[Carrier, Payload],
        right: tuple[Carrier, Payload],
        /,
    ) -> tuple[Carrier, Payload]:
        """Extend both the value and its attached payload."""
        return (
            self.values.multiply(left[0], right[0]),
            self.payload_multiply(left[1], right[1]),
        )


def semiring_alignment[Carrier](
    pack: CostPack,
    source: Segmentation,
    target: Segmentation,
    semiring: FoldSemiring[Carrier],
    *,
    encode: Callable[[float], Carrier],
) -> Carrier:
    """Fold an alignment grid using only ``add``, ``multiply``, zero and one.

    The fold cannot name tropical arithmetic, compare carrier values, or
    branch on a pack.  Consequently COUNTING and PATH exercise the identical
    recurrence rather than a similar-looking implementation.  PATH callers
    must impose and report a visible cap before materializing its result; this
    low-level fold does not silently truncate a carrier.
    """
    left, right = source.tokens, target.tokens
    deletes = tuple(
        encode(value) for value in _prices(pack.delete_cost, list(left), "delete_cost")
    )
    inserts = tuple(
        encode(value) for value in _prices(pack.insert_cost, list(right), "insert_cost")
    )
    dp = [[semiring.zero for _ in range(len(right) + 1)] for _ in range(len(left) + 1)]
    dp[0][0] = semiring.one
    for i, deletion in enumerate(deletes, 1):
        dp[i][0] = semiring.multiply(dp[i - 1][0], deletion)
    for j, insertion in enumerate(inserts, 1):
        dp[0][j] = semiring.multiply(dp[0][j - 1], insertion)
    for i, left_token in enumerate(left, 1):
        for j, right_token in enumerate(right, 1):
            delete = semiring.multiply(dp[i - 1][j], deletes[i - 1])
            insert = semiring.multiply(dp[i][j - 1], inserts[j - 1])
            substitute = semiring.multiply(
                dp[i - 1][j - 1], encode(pack.sub_cost(left_token, right_token))
            )
            dp[i][j] = semiring.add(semiring.add(delete, insert), substitute)
    return dp[-1][-1]


def compare(
    ipa: IPAFeatures,
    pack: CostPack,
    source: str,
    target: str,
    *,
    strict: bool = False,
    return_alignment: bool = False,
) -> ComparisonRow:
    """Score one word pair under one cost pack, drops and all."""
    left, right = pack.tokenize(source), pack.tokenize(target)
    dropped = left.dropped + right.dropped
    if dropped and strict:
        raise DroppedMaterial(
            f"{pack.name} discarded {''.join(dropped)!r} reading "
            f"{source!r} and {target!r}; the score would be computed from "
            "truncated input"
        )
    cost, alignment = align_under(
        ipa, pack, left, right, return_alignment=return_alignment
    )
    return ComparisonRow(
        policy=pack.policy.identity,
        pack=pack.name,
        geometry=pack.geometry,
        budget_ratio=pack.budget_ratio,
        edit_cost=cost,
        normalized=normalized(pack, left, right, cost),
        dropped=dropped,
        alignment=alignment,
        reference=pack.reference,
    )


def house_pack(ipa: IPAFeatures, policy: CostPolicy = FAITHFUL) -> CostPack:
    """Build ipakit's cost model against the supplied ipakit geometry."""
    indel = GAP_COST * policy.indel_weight
    cache: dict[tuple[str, str], float] = {}

    def sub(t1: str, t2: str) -> float:
        if t1 == t2:
            return 0.0
        key = (t1, t2)
        hit = cache.get(key)
        if hit is None:
            raw = _substitution_cost(ipa.segment_distance(t1, t2), GAP_COST, GAP_COST)
            hit = raw * policy.substitution_scale
            cache[key] = hit
        return hit

    return CostPack(
        name="ipakit/house",
        geometry="ipakit",
        sub_cost=sub,
        insert_cost=indel,
        delete_cost=indel,
        substitution_ceiling=2.0 * policy.substitution_scale,
        indel_ceiling=2.0 * policy.indel_weight,
        tokenize=_house_segmentation(ipa),
        policy=policy,
    )


def model_pack(
    ipa: IPAFeatures,
    model: DistanceModel,
    policy: CostPolicy = FAITHFUL,
) -> CostPack:
    """A cost model over an inventory-relative :class:`DistanceModel`.

    The other two packs are inventory-INDEPENDENT: `house_pack` and
    `pack_from_declaration` price a pair from the two segments'
    declarations alone, so the number does not move when the inventory
    does. That portability is bought with compression -- a raw structural
    score occupies about a third of its nominal range -- and it is the
    right default, because a figure that changes when a phone is added is
    not comparable across studies.

    Sometimes the inventory is the question. A `DistanceModel` ranks a
    raw cost within a reference distribution and bends the rank by
    `gamma`, which is what raises realized costs toward the indel budget
    and makes magnitudes legible. Crucially the reference can be a
    specific inventory rather than everything: `DistanceModel.for_phoneset`
    re-slices the percentile to one phoneset, so the same geometry answers
    "how unusual is this contrast" relative to whichever inventory is
    doing the hearing.

    That is the asymmetric case, and it is where this earns its keep: a
    learner's L1 inventory and the L2 they are learning rank the same
    contrast differently -- the same geometry, two distributions, and
    neither answer wrong. `i`/`ɪ` against a sparse reference and against
    a dense one is the worked pair, pinned in
    `TestAnInventoryRelativePackIsNotAPortableOne` rather than quoted
    here: a figure in prose goes stale in silence, and no gate reads a
    docstring.

    **What that number is, and what it is not.** It says how unusual the
    contrast is against that inventory's own spread. A sparser inventory
    has fewer close pairs, so a small raw difference ranks high in it; a
    denser one has many, so the same difference ranks low. That is a fact
    about the inventory, NOT a claim about a listener: reading "unusual
    against this inventory" as "hard for a speaker of it to hear" is a
    hypothesis about perception, and it needs perceptual data to become a
    finding. The quantity here is distinctiveness relative to a reference,
    which is worth having on its own terms and is not a difficulty score.

    Computed once and reused: `DistanceModel.save` writes the matrix with
    a `metric_fingerprint` over the phones it holds, and
    `from_matrix_file` refuses a reader whose feature space does not match
    it -- so a saved model cannot quietly be read against an inventory it
    was not built for. Nothing here recomputes a distribution that has
    already been computed.

    The row this pack produces carries the model's reference and gamma,
    because a percentile is meaningless without the distribution it was
    taken against, and two figures ranked over different inventories are
    not comparable while looking exactly as though they were.
    """

    def _weighted(cost: PhoneCost) -> PhoneCost:
        # The model's own indel prices, kept per-phone and kept apart.
        # Insertion and deletion are different questions -- a learner who
        # epenthesizes supplies material cheaply while losing it is dear --
        # so this scales each without collapsing them into one gap price.
        if callable(cost):
            return lambda token: float(cost(token)) * policy.indel_weight
        return float(cost) * policy.indel_weight

    def sub(t1: str, t2: str) -> float:
        if t1 == t2:
            return 0.0
        return model.sub_cost(t1, t2) * policy.substitution_scale

    named = model.reference_name or f"{len(model.reference_phones)} phones"
    reference = f"{named} gamma={model.gamma!r}"
    return CostPack(
        name="ipakit/model",
        geometry="ipakit/inventory-relative",
        sub_cost=sub,
        insert_cost=_weighted(model.insert_cost),
        delete_cost=_weighted(model.delete_cost),
        substitution_ceiling=2.0 * policy.substitution_scale,
        indel_ceiling=2.0 * policy.indel_weight,
        tokenize=_house_segmentation(ipa),
        policy=policy,
        reference=reference,
    )


def pack_from_declaration(
    path: str | PathLike[str],
    policy: CostPolicy = FAITHFUL,
    *,
    family: DeclaredCostFamily = DeclaredCostFamily.SYMMETRIC_DIFFERENCE,
    absent: AbsentCell = AbsentCell.HALF_COUNTED,
) -> CostPack:
    """Build a declared cost family from a ternary declaration.

    The family, not one system's instance of it. A declaration states some
    features and gives every segment a value in ``{-, 0, +}`` for each; this
    reads that and returns the pack a comparison drives. ``family`` picks the
    arithmetic: the default symmetric difference, normalized into [0, 1], or
    ``WEIGHTED_DIFFERENCE``, an unnormalized weighted sum whose ceiling is
    twice the declared weight mass. Its round-trip declaration becomes the
    pack's ``Bridge``: crossing a feature-system boundary has a stated
    fidelity rather than an inferred losslessness.
    Nothing here knows which feature system it was handed, and that is what
    lets one cost model meet a foreign geometry: swapping the declaration
    swaps the geometry.

    **Why symmetric difference.** Recast a ternary cell privatively -- each
    feature becomes two unary predicates, ``(f, +)`` and ``(f, -)``, and ``0``
    becomes absence. Under that reading the substitution cost below is exactly
    the symmetric-difference measure of the two segments' predicate sets,
    ``|A xor B| / 2n``. That is not an approximation of the usual formulation;
    it is the same number, and it is why the segment distance satisfies the
    triangle inequality: symmetric difference over a measure space is a metric
    by construction.

    **What the arithmetic really is, under symmetric difference.** A ternary
    cell makes ``|a - b|`` one of 0, 1 or 2; halving gives 0, 0.5 or 1 per
    feature; the sum over ``n`` features is a multiple of one half; dividing
    by ``n`` leaves an integer over ``2n``. Every cost that family returns is
    therefore ``k / 2n`` for some integer ``k`` -- a point on a fixed rational
    grid rather than an arbitrary real. With the 24-feature declarations in
    circulation that grid is ``k / 48``, and since ``48 = 2^4 * 3`` most of
    its points are exact in neither binary nor decimal floating point. That is
    a reason to scale by ``2n`` where exactness matters, not a reason to reach
    for a wider numeric type: the values are integers wearing a denominator.

    **``0`` is a value here, not an absence.** It participates: under
    symmetric difference ``0`` against ``+`` costs half a step, and ``0``
    against ``0`` costs nothing, so two segments are recorded as agreeing
    about a feature neither of them may have. That is faithful to the
    fixed-width reading a ternary declaration encodes, and it is deliberately
    not repaired here -- a declaration that wishes to distinguish inapplicable
    from underspecified has to say so, and a cost family cannot invent the
    distinction on its behalf.

    **The tokenizer reports what it could not read.** Longest-match over the
    declared segments, and every character it cannot place is carried out in
    ``Segmentation.dropped`` rather than discarded. A model that silently
    drops input and still returns a number is the failure this obstructs:
    ``compare`` is the only public route to a score, and it cannot lose the
    report on the way.
    """
    root = ET.parse(path).getroot()
    round_trip = root.find("round-trip")
    if round_trip is None:
        raise ValueError("a feature declaration requires a round-trip classification")
    external = round_trip.find("external-to-house")
    house = round_trip.find("house-to-external")
    if external is None or house is None:
        raise ValueError("a feature declaration must classify both directions")

    def leg(element: ET.Element, direction: str) -> RoundTripLeg:
        try:
            fidelity = Fidelity(element.attrib["fidelity"])
        except KeyError as error:
            raise ValueError(f"{direction} requires a fidelity") from error
        return RoundTripLeg(
            direction,
            fidelity,
            tuple(item.attrib["name"] for item in element.findall("drop")),
            tuple(item.attrib["name"] for item in element.findall("trick")),
        )

    identity = root.get("name", "declared")
    version = root.get("version", "")
    bridge = Bridge(
        identity,
        version,
        root.get("provenance", ""),
        RoundTripReport(
            leg(external, "external-to-house"),
            leg(house, "house-to-external"),
        ),
    )
    feature_block = root.find("features")
    segment_block = root.find("segments")
    if feature_block is None or segment_block is None:
        raise ValueError("a feature declaration requires features and segments blocks")
    features = tuple(
        name
        for item in feature_block.findall("feature")
        if (name := item.get("name")) is not None
    )
    if not features:
        raise ValueError("a feature declaration must declare at least one feature")

    vectors: dict[str, tuple[int | None, ...]] = {}
    for item in segment_block:
        name = item.get("name")
        if name is None:
            raise ValueError("every declared segment requires a name")
        normalized = unicodedata.normalize("NFD", name)
        if normalized != name:
            raise ValueError(f"segment key is not NFD: {name!r}")
        if normalized in vectors:
            raise ValueError(f"duplicate segment key: {normalized!r}")
        values: list[int | None] = []
        for feature in features:
            raw = item.get(feature)
            if raw not in {None, "-", "0", "+"}:
                raise ValueError(
                    f"segment {name!r} feature {feature!r} is not ternary: {raw!r}"
                )
            values.append(None if raw is None else {"-": -1, "0": 0, "+": 1}[raw])
        vectors[normalized] = tuple(values)

    ordered = sorted(vectors, key=len, reverse=True)
    weights_block = root.find("weights")
    weight_items = tuple(weights_block) if weights_block is not None else ()
    declared_weights: list[float] = []
    for index, item in enumerate(weight_items):
        feature = item.get("name") or (
            features[index] if index < len(features) else f"weight[{index}]"
        )
        raw_weight = item.get("value")
        try:
            weight = float(raw_weight) if raw_weight is not None else math.nan
        except ValueError as error:
            raise ValueError(
                f"weight for feature {feature!r} is not numeric: {raw_weight!r}"
            ) from error
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError(
                f"weight for feature {feature!r} must be non-negative and finite; "
                f"got {raw_weight!r}"
            )
        declared_weights.append(weight)

    weighted = family is DeclaredCostFamily.WEIGHTED_DIFFERENCE
    if weighted:
        if absent is not AbsentCell.SKIP:
            raise ValueError(
                "weighted difference supports only absent='skip'; its unnormalized "
                "sum has no denominator in which a counted zero or half can differ"
            )
        if len(weight_items) != len(features):
            offending = (
                features[len(weight_items)]
                if len(weight_items) < len(features)
                else weight_items[len(features)].get("name", f"weight[{len(features)}]")
            )
            raise ValueError(
                "weighted difference requires one weight per feature; "
                f"feature {offending!r} breaks that correspondence"
            )
    weights = tuple(declared_weights) if declared_weights else (1.0,) * len(features)
    inner = ProductSemiring(TROPICAL, TROPICAL)
    # Bound once and annotated because the pre-commit hook type-checks this file
    # alone, where the product's payload widens to Any without the package in
    # view; CI checks the package and infers it. Naming the type satisfies both.
    inner_one: tuple[float, float] = inner.one

    def absent_term() -> tuple[float, float]:
        # All absence treatments are one fold; only this declared term moves.
        if absent is AbsentCell.SKIP:
            return inner_one
        if absent is AbsentCell.ZERO_COUNTED:
            return (0.0, 1.0)
        return (0.5, 1.0)

    def vector_fold(
        left: tuple[int | None, ...], right: tuple[int | None, ...]
    ) -> tuple[float, float]:
        total: tuple[float, float] = inner_one
        for a, b in zip(left, right, strict=True):
            term = absent_term() if a is None or b is None else (abs(a - b) / 2.0, 1.0)
            total = inner.multiply(total, term)
        return total

    if weighted:

        def raw_sub(left: str, right: str) -> float:
            return sum(
                abs(a - b) * weight
                for a, b, weight in zip(
                    vectors[left], vectors[right], weights, strict=True
                )
                if a is not None and b is not None
            )

        weight_total = sum(weights)

        def raw_indel(token: str) -> float:
            # Deliberately constant: this family defines an indel as the full
            # feature-weight mass, rather than inspecting the segment's cells.
            return weight_total

        substitution_ceiling = 2.0 * weight_total
        indel_ceiling = weight_total
    else:

        def raw_sub(left: str, right: str) -> float:
            cost, count = vector_fold(vectors[left], vectors[right])
            return cost / count if count else 0.0

        def raw_indel(token: str) -> float:
            vector = vectors[token]
            terms = [
                absent_term() if value is None else (0.5 if value == 0 else 1.0, 1.0)
                for value in vector
            ]
            total = inner.one
            for term in terms:
                total = inner.multiply(total, term)
            return total[0] / total[1] if total[1] else 0.0

        substitution_ceiling = 1.0
        indel_ceiling = 1.0

    cache: dict[tuple[str, str], float] = {}

    def sub(left: str, right: str) -> float:
        if left == right:
            return 0.0
        key = (left, right)
        hit = cache.get(key)
        if hit is None:
            hit = raw_sub(left, right) * policy.substitution_scale
            cache[key] = hit
        return hit

    def indel(token: str) -> float:
        return raw_indel(token) * policy.indel_weight

    def tokenize(word: str) -> Segmentation:
        remaining = unicodedata.normalize("NFD", word)
        tokens: list[str] = []
        dropped: list[str] = []
        while remaining:
            token = next((item for item in ordered if remaining.startswith(item)), None)
            if token is None:
                dropped.append(remaining[0])
                remaining = remaining[1:]
            else:
                tokens.append(token)
                remaining = remaining[len(token) :]
        return Segmentation(tuple(tokens), tuple(dropped))

    geometry = f"{identity}/{version}" if version else identity
    return CostPack(
        name=f"declared/{identity}/{family.value}",
        geometry=geometry,
        sub_cost=sub,
        insert_cost=indel,
        delete_cost=indel,
        substitution_ceiling=substitution_ceiling * policy.substitution_scale,
        indel_ceiling=indel_ceiling * policy.indel_weight,
        tokenize=tokenize,
        policy=policy,
        bridge=bridge,
    )


def _house_segmentation(ipa: IPAFeatures) -> Callable[[str], Segmentation]:
    """Return the strict house tokenizer as a ``Segmentation`` source."""

    def read(word: str) -> Segmentation:
        ipa._reject_unconvertible(word)
        return Segmentation(tuple(ipa._word_units(word)), ())

    return read


def normalized(
    pack: CostPack, source: Segmentation, target: Segmentation, raw: float
) -> float:
    """PROVISIONAL: apply the concrete readout these cost families require.

    A ratio is not a semiring operation. Both of its cardinalities can be
    folded inside the algebra, but the division that turns them into a score
    sits above the signature, so it happens here rather than in the fold.

    What is provisional is the DECLARATION rather than the arithmetic. The
    substrate is expected to grow a way for a final division to be recorded as
    part of what a profile states, so that a pipeline stays self-describing --
    otherwise an undeclared post-pass computes the real answer and "load an
    algebra and the same expression decides, counts or scores" stops being
    true. When that lands, this computation most likely stays and gains a
    place to be declared; do not assume it will be replaced by a different one.
    """
    normalization = pack.policy.normalization
    if normalization is Normalization.RAW:
        return raw
    denominator: float
    if normalization is Normalization.DIV_MAXLEN:
        denominator = max(len(source.tokens), len(target.tokens))
    else:
        denominator = sum(price(pack.delete_cost, token) for token in source.tokens)
        denominator += sum(price(pack.insert_cost, token) for token in target.tokens)
    return raw / denominator if denominator else 0.0
