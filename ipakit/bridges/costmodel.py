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

from ..distance import Alignment, PhoneCost, _substitution_cost, price
from ..features import IPAFeatures
from ..metric import GAP_COST

COSTMODEL_VERSION = "1.0"


class Normalization(StrEnum):
    """What an alignment cost is divided by before it is reported."""

    RAW = "raw"
    DIV_MAXLEN = "div-maxlen"
    DIV_NULL_ALIGNMENT = "div-null-alignment"


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


def align_under(
    ipa: IPAFeatures,
    pack: CostPack,
    source: Segmentation,
    target: Segmentation,
    *,
    return_alignment: bool = False,
) -> tuple[float, Alignment | None]:
    """Run one cost pack through ipakit's existing alignment fold."""
    return ipa._align(
        list(source.tokens),
        list(target.tokens),
        pack.sub_cost,
        pack.insert_cost,
        pack.delete_cost,
        return_alignment,
    )


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


def pack_from_declaration(
    path: str | PathLike[str], policy: CostPolicy = FAITHFUL
) -> CostPack:
    """Build the symmetric-difference cost family from a ternary declaration."""
    root = ET.parse(path).getroot()
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

    vectors: dict[str, tuple[int, ...]] = {}
    for item in segment_block:
        name = item.get("name")
        if name is None:
            raise ValueError("every declared segment requires a name")
        normalized = unicodedata.normalize("NFD", name)
        if normalized != name:
            raise ValueError(f"segment key is not NFD: {name!r}")
        if normalized in vectors:
            raise ValueError(f"duplicate segment key: {normalized!r}")
        values: list[int] = []
        for feature in features:
            raw = item.get(feature)
            if raw not in {"-", "0", "+"}:
                raise ValueError(
                    f"segment {name!r} feature {feature!r} is not ternary: {raw!r}"
                )
            values.append({"-": -1, "0": 0, "+": 1}[raw])
        vectors[normalized] = tuple(values)

    ordered = sorted(vectors, key=len, reverse=True)
    width = float(len(features))
    cache: dict[tuple[str, str], float] = {}

    def sub(left: str, right: str) -> float:
        if left == right:
            return 0.0
        key = (left, right)
        hit = cache.get(key)
        if hit is None:
            hit = (
                sum(
                    abs(a - b) / 2.0
                    for a, b in zip(vectors[left], vectors[right], strict=True)
                )
                / width
                * policy.substitution_scale
            )
            cache[key] = hit
        return hit

    def indel(token: str) -> float:
        vector = vectors[token]
        raw = sum(0.5 if value == 0 else 1.0 for value in vector) / width
        return raw * policy.indel_weight

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

    identity = root.get("name", "declared")
    version = root.get("version")
    geometry = f"{identity}/{version}" if version else identity
    return CostPack(
        name=f"declared/{identity}",
        geometry=geometry,
        sub_cost=sub,
        insert_cost=indel,
        delete_cost=indel,
        substitution_ceiling=1.0 * policy.substitution_scale,
        indel_ceiling=1.0 * policy.indel_weight,
        tokenize=tokenize,
        policy=policy,
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
    """Divide a raw alignment cost as ``pack.policy.normalization`` says."""
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
