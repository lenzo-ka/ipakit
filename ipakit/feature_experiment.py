"""Repeatable finite re-encoding experiments over the shared corpus engine."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from ._identity import identity_fingerprint
from .binary_cost import binary_pack
from .bridges.costmodel import (
    CostPack,
    CostPolicy,
    compare_token_corpus,
    house_pack,
    pack_from_ternary_declaration,
)
from .feature_transform import BinaryEncoding, ternary_to_binary
from .features import IPAFeatures
from .finite_declaration import TernaryDeclaration, validate_ternary_declaration


def compare_declaration_encodings(
    ipa: IPAFeatures,
    declaration: TernaryDeclaration,
    corpus: list[list[str]],
    *,
    encodings: Sequence[BinaryEncoding],
    binary_gap: float,
    policies: Sequence[CostPolicy],
    all_pairs: bool = False,
    include_house: bool = False,
) -> dict[str, Any]:
    """Compare original ternary costs and explicitly selected binary encodings.

    No acquisition, file reading, tokenization, or house pivot is performed.
    All arms consume one immutable declaration and one explicit token corpus.
    Binary bits have unit weights; the source's weight metadata is not applied.
    """
    validate_ternary_declaration(declaration)
    encodings, policies = tuple(encodings), tuple(policies)
    if not encodings or any(
        not isinstance(value, BinaryEncoding) for value in encodings
    ):
        raise ValueError("select explicit BinaryEncoding values")
    if len(set(encodings)) != len(encodings):
        raise ValueError("duplicate encoding selections")
    if not policies or any(not isinstance(policy, CostPolicy) for policy in policies):
        raise ValueError("select explicit CostPolicy values")
    if len({policy.identity for policy in policies}) != len(policies):
        raise ValueError("duplicate policy selections")
    model = declaration.model
    transforms = [
        ternary_to_binary(model, encoding, missing="require-complete")
        for encoding in encodings
    ]
    receipt: dict[str, Any] = {
        "model": model.identity,
        "features": list(model.schema.features),
        "feature_count": len(model.schema.features),
        "source": model.source.to_dict() if model.source else None,
        "weight_names": list(declaration.weight_names),
        "declared_weights": list(declaration.weights),
        "weights_applied": False,
        "bridge_metadata": asdict(declaration.bridge),
    }
    receipt["identity"] = identity_fingerprint(receipt)
    packs = []
    arms = []
    for policy in policies:
        original = pack_from_ternary_declaration(declaration, policy)
        selected: list[tuple[CostPack, dict[str, Any]]] = [
            (
                original,
                {
                    "kind": "original-ternary",
                    "model": model.identity,
                    "substitution": "sum(abs(a-b))/(2*feature-count)",
                    "weights": "equal-features",
                    "gap": {
                        "kind": "source-dependent",
                        "formula": "mean(0.5 if cell==0 else 1)*indel_weight",
                    },
                },
            )
        ]
        for encoding, operation in zip(encodings, transforms, strict=True):
            pack = binary_pack(operation, gap=binary_gap, policy=policy)
            selected.append(
                (
                    pack,
                    {
                        "kind": "binary",
                        "encoding": encoding.value,
                        "source_model": model.identity,
                        "target_model": operation.target.identity,
                        "operation": operation.identity,
                        "missing": operation.missing,
                        "bit_names": list(operation.target.schema.features),
                        "bit_count": len(operation.target.schema.features),
                        "weights": [1.0] * len(operation.target.schema.features),
                        "substitution": "weighted-hamming/weight-mass",
                        "gap": {
                            "kind": "constant",
                            "requested": binary_gap,
                            "effective": binary_gap * policy.indel_weight,
                        },
                        "loss": {
                            "domain_injective": operation.injective,
                            "observed_collision_groups": len(operation.collisions()),
                            "aliases_are_collisions": False,
                        },
                    },
                )
            )
        if include_house:
            selected.append(
                (
                    house_pack(ipa, policy),
                    {"kind": "house", "gap": {"kind": "house-adapter"}},
                )
            )
        for pack, metadata in selected:
            arm = {
                **metadata,
                "pack": pack.name,
                "geometry": pack.geometry,
                "policy": policy.identity,
                "cost_policy": {
                    "substitution_scale": policy.substitution_scale,
                    "indel_weight": policy.indel_weight,
                    "normalization": policy.normalization.value,
                },
            }
            arm["identity"] = identity_fingerprint(arm)
            packs.append(pack)
            arms.append(arm)
    report = compare_token_corpus(ipa, packs, corpus, all_pairs=all_pairs)
    experiment = {
        "schema": "ipakit-declared-encoding-experiment",
        "version": 1,
        "declaration": receipt,
        "arms": arms,
    }
    experiment["identity"] = identity_fingerprint(experiment)
    return {**report, "experiment": experiment}
