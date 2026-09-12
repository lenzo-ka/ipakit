"""Explicit binary feature costs consumed by the existing alignment folds."""

from __future__ import annotations

import math
from collections.abc import Mapping

from ._identity import identity_fingerprint
from .bridges.costmodel import FAITHFUL, CostPack, CostPolicy, Segmentation
from .feature_transform import FiniteTransform


def binary_pack(
    transform: FiniteTransform,
    *,
    gap: float,
    weights: Mapping[str, float] | None = None,
    policy: CostPolicy = FAITHFUL,
) -> CostPack:
    """Normalized weighted Hamming, with a separately declared constant gap.

    Gap is not Hamming-to-zero and does not inherit the source model's indels.
    Text input is exactly one opaque token (or empty); use Segmentation for
    explicit multi-token sequences. No concatenated-string parser is implied.
    """
    model = transform.target
    for name, domain in model.schema.domains.items():
        if any(type(value) is not int for value in domain) or set(domain) != {0, 1}:
            raise ValueError(f"binary costs require integer bit domains: {name!r}")
    if type(gap) not in (int, float) or not math.isfinite(gap) or gap <= 0:
        raise ValueError("gap must be an explicit positive finite price")
    if policy.indel_weight <= 0:
        raise ValueError("binary comparison requires positive effective gap pricing")
    effective_gap = gap * policy.indel_weight
    if not math.isfinite(effective_gap) or effective_gap <= 0:
        raise ValueError("effective gap price must be positive and finite")
    supplied = (
        dict(weights)
        if weights is not None
        else dict.fromkeys(model.schema.features, 1.0)
    )
    if set(supplied) != set(model.schema.features):
        raise ValueError("weights must name every binary feature exactly once")
    ordered = tuple(supplied[name] for name in model.schema.features)
    if any(
        type(value) not in (int, float) or not math.isfinite(value) or value < 0
        for value in ordered
    ):
        raise ValueError("weights must be non-negative finite numbers")
    mass = sum(ordered)
    if not math.isfinite(mass) or mass <= 0:
        raise ValueError("binary weights require positive finite total mass")

    def sub(left: str, right: str) -> float:
        a, b = model.read(left), model.read(right)
        return (
            sum(
                weight
                for x, y, weight in zip(a.values, b.values, ordered, strict=True)
                if x != y
            )
            / mass
            * policy.substitution_scale
        )

    def indel(token: str) -> float:
        model.read(token)
        return effective_gap

    def tokenize(text: str) -> Segmentation:
        if not text:
            return Segmentation(())
        model.read(text)
        return Segmentation((text,))

    identity = identity_fingerprint(
        {
            "format": "binary-cost/1",
            "operation": transform.identity,
            "target": model.identity,
            "weights": ordered,
            "gap": gap,
            "policy": policy.identity,
            "substitution": "weighted-hamming/weight-mass",
            "tokenization": "one-exact-token-or-empty",
        }
    )
    return CostPack(
        name=f"binary/{transform.identity}/{identity}",
        geometry=model.identity,
        sub_cost=sub,
        insert_cost=indel,
        delete_cost=indel,
        substitution_ceiling=policy.substitution_scale,
        indel_ceiling=effective_gap,
        tokenize=tokenize,
        policy=policy,
    )
