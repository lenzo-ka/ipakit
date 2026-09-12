"""Constructive finite transforms and actual shared-fold binary consumers."""

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest
from ipakit.binary_cost import binary_pack
from ipakit.bridges.costmodel import (
    CostPolicy,
    Normalization,
    Segmentation,
    normalized,
    pack_from_declaration,
    semiring_alignment,
)
from ipakit.distance import price
from ipakit.feature_transform import (
    BinaryEncoding,
    FeatureMap,
    FiniteTransform,
    InvalidTransform,
    MissingFeature,
    OutsideImage,
    ScalarCase,
    ternary_to_binary,
)
from ipakit.finite_declaration import read_ternary_declaration
from ipakit.finite_model import (
    FeatureBundle,
    FeatureSchema,
    FiniteModel,
    InvalidFeature,
    MissingToken,
    ModelMismatch,
)
from tiergraph.semiring import TROPICAL

DECLARATION = Path(__file__).parent / "panphon" / "panphon.xml"


def scalar_model() -> FiniteModel:
    return FiniteModel(
        "opaque",
        FeatureSchema({"f": (-1, 0, 1)}),
        {"NEG": (-1,), "ZERO": (0,), "POS": (1,)},
    )


def binary(
    source: FiniteModel, encoding: BinaryEncoding = BinaryEncoding.TWO_PREDICATE
) -> FiniteTransform:
    return ternary_to_binary(source, encoding, missing="require-complete")


def test_nine_scalar_pairs_and_all_codes() -> None:
    source = scalar_model()
    transform = binary(source)
    assert transform.injective
    assert transform.collisions() == ()
    pack = binary_pack(transform, gap=1)
    for left, right in product(source.rows, repeat=2):
        a, b = source.read(left).values[0], source.read(right).values[0]
        assert pack.sub_cost(left, right) == abs(a - b) / 2
    for token, code in {"NEG": (0, 1), "ZERO": (0, 0), "POS": (1, 0)}.items():
        result = transform.apply(source.read(token))
        assert result.target.values == code
        assert result.operation_id == transform.identity
        preimage = transform.decode(result.target)
        assert preimage.count == 1
        assert preimage.inventory_candidates == (token,)
    with pytest.raises(OutsideImage):
        transform.decode(FeatureBundle(transform.target.identity, (1, 1)))


def test_lossy_projection_reports_domain_and_inventory_ambiguity() -> None:
    source = scalar_model()
    transform = binary(source, BinaryEncoding.POSITIVE_ONLY)
    assert not transform.injective
    preimage = transform.decode(transform.target.read("ZERO"))
    assert preimage.choices == (("f", (-1, 0)),)
    assert preimage.count == 2
    assert preimage.inventory_candidates == ("NEG", "ZERO")
    assert transform.collisions()[0].tokens == ("NEG", "ZERO")
    assert binary_pack(transform, gap=1).sub_cost("NEG", "ZERO") == 0
    sparse = FiniteModel("sparse", source.schema, {"ZERO": (0,), "ALIAS": (0,)})
    sparse_transform = binary(sparse, BinaryEncoding.POSITIVE_ONLY)
    assert not sparse_transform.injective
    assert sparse_transform.collisions() == ()  # Aliases are not lost distinctions.
    assert sparse_transform.decode(sparse_transform.target.read("ZERO")).count == 2


def test_general_typed_nonternary_map_and_defensive_copy() -> None:
    source = FiniteModel(
        "typed", FeatureSchema({"flag": (False, 0)}), {"BOOL": (False,), "INT": (0,)}
    )
    cases = [ScalarCase(False, ("off",)), ScalarCase(0, ("zero",))]
    transform = FiniteTransform(
        "labels",
        source,
        FeatureSchema({"label": ("off", "zero")}),
        (FeatureMap("flag", ("label",), cases),),
        "require-complete",
    )
    cases.clear()
    assert transform.injective
    assert transform.target.read("BOOL").values == ("off",)
    assert transform.target.read("INT").values == ("zero",)
    assert len({ScalarCase(False, (0,)), ScalarCase(0, (0,))}) == 2
    with pytest.raises(ValueError, match="integer bit"):
        binary_pack(transform, gap=1)


@pytest.mark.parametrize(
    "cases",
    [
        (ScalarCase(-1, (0,)),),
        (ScalarCase(-1, (0,)), ScalarCase(0, (0,)), ScalarCase(0, (1,))),
        (ScalarCase(-1, (0,)), ScalarCase(0, (0,)), ScalarCase(True, (1,))),
    ],
)
def test_refuse_incomplete_duplicate_and_wrong_typed_cases(cases: tuple) -> None:
    with pytest.raises(InvalidTransform, match="domain cases"):
        FiniteTransform(
            "bad",
            scalar_model(),
            FeatureSchema({"bit": (0, 1)}),
            (FeatureMap("f", ("bit",), cases),),
            "require-complete",
        )


def test_output_and_source_contract_refusals() -> None:
    source = scalar_model()
    with pytest.raises(InvalidFeature):
        FiniteTransform(
            "bad",
            source,
            FeatureSchema({"bit": (0, 1)}),
            (
                FeatureMap(
                    "f", ("bit",), tuple(ScalarCase(v, (False,)) for v in (-1, 0, 1))
                ),
            ),
            "require-complete",
        )
    transform = binary(source)
    other = FiniteModel(source.name, source.schema, {"NEG": (0,)})
    with pytest.raises(ModelMismatch):
        transform.apply(other.read("NEG"))
    with pytest.raises(InvalidFeature):
        transform.apply(FeatureBundle(source.identity, (2,)))
    with pytest.raises(MissingFeature):
        transform.apply(FeatureBundle(source.identity, (None,)))
    with pytest.raises(MissingFeature):
        binary(FiniteModel("absent", source.schema, {"ABSENT": (None,)}))
    with pytest.raises(InvalidTransform):
        ternary_to_binary(source, "two-predicate", missing="require-complete")
    with pytest.raises(InvalidTransform):
        ternary_to_binary(source, BinaryEncoding.TWO_PREDICATE, missing="zero")
    with pytest.raises(InvalidFeature):
        transform.decode(FeatureBundle(transform.target.identity, (False, 0)))


def test_field_coverage_width_and_explicit_dropped_feature() -> None:
    source = FiniteModel(
        "drop",
        FeatureSchema({"keep": (0, 1), "drop": (0, 1)}),
        {"FIRST": (0, 0), "SECOND": (0, 1)},
    )
    keep = FeatureMap("keep", ("bit",), (ScalarCase(0, (0,)), ScalarCase(1, (1,))))
    drop = FeatureMap("drop", (), (ScalarCase(0, ()), ScalarCase(1, ())))
    schema = FeatureSchema({"bit": (0, 1)})
    transform = FiniteTransform(
        "drop", source, schema, (keep, drop), "require-complete"
    )
    assert not transform.injective
    assert transform.decode(transform.target.read("FIRST")).count == 2
    assert transform.collisions()[0].tokens == ("FIRST", "SECOND")
    for maps in (
        (keep,),
        (keep, keep),
        (keep, FeatureMap("drop", ("bit",), drop.cases)),
    ):
        with pytest.raises(InvalidTransform, match="cover every"):
            FiniteTransform("bad", source, schema, maps, "require-complete")
    bad_width = FeatureMap("keep", ("bit",), (ScalarCase(0, ()), ScalarCase(1, (1,))))
    with pytest.raises(InvalidTransform, match="width"):
        FiniteTransform("bad", source, schema, (bad_width, drop), "require-complete")


@pytest.mark.parametrize("gap", [-1, 0, True, float("inf"), float("nan")])
def test_gap_policy_is_validated(gap: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        binary_pack(binary(scalar_model()), gap=gap)


def test_weight_policy_identity_and_invalid_inputs() -> None:
    transform = binary(scalar_model())
    for weights in (
        {},
        {"unknown": 1},
        {"f:positive": True, "f:negative": 1},
        {"f:positive": -1, "f:negative": 1},
        {"f:positive": 0, "f:negative": 0},
    ):
        with pytest.raises(ValueError):
            binary_pack(transform, gap=1, weights=weights)
    plain = binary_pack(transform, gap=1)
    weighted = binary_pack(transform, gap=1, weights={"f:positive": 0, "f:negative": 1})
    assert weighted.sub_cost("POS", "ZERO") == 0
    assert weighted.name != plain.name
    assert binary_pack(transform, gap=2).name != plain.name
    with pytest.raises(ValueError, match="positive effective"):
        binary_pack(transform, gap=1, policy=CostPolicy(indel_weight=0))


def test_binary_policy_weights_gaps_normalization_and_validation() -> None:
    transform = binary(scalar_model())
    policy = CostPolicy(
        substitution_scale=2, indel_weight=3, normalization=Normalization.DIV_MAXLEN
    )
    pack = binary_pack(
        transform, gap=0.25, weights={"f:positive": 3, "f:negative": 1}, policy=policy
    )
    assert pack.sub_cost("POS", "ZERO") == 1.5
    assert pack.sub_cost("NEG", "ZERO") == 0.5
    assert price(pack.insert_cost, "POS") == 0.75
    left, right = Segmentation(("POS", "NEG")), Segmentation(("ZERO", "ZERO"))
    result = semiring_alignment(pack, left, right, TROPICAL, encode=float)
    assert result == 2
    assert normalized(pack, left, right, result) == 1
    assert pack.tokenize("POS").tokens == ("POS",)
    assert pack.tokenize("").tokens == ()
    for bad in ("POSNEG", "p", "UNKNOWN"):
        with pytest.raises(MissingToken):
            pack.tokenize(bad)
        with pytest.raises(MissingToken):
            pack.sub_cost(bad, bad)
        with pytest.raises(MissingToken):
            price(pack.insert_cost, bad)
        for left, right in (
            (Segmentation((bad,)), Segmentation(())),
            (Segmentation(()), Segmentation((bad,))),
            (Segmentation((bad,)), Segmentation((bad,))),
        ):
            with pytest.raises(MissingToken):
                semiring_alignment(pack, left, right, TROPICAL, encode=float)


def test_frozen_rows_roundtrip_loss_and_separate_gap_counterexample() -> None:
    source = read_ternary_declaration(DECLARATION).model
    exact = binary(source)
    lossy = binary(source, BinaryEncoding.POSITIVE_ONLY)
    assert exact.injective
    assert exact.collisions() == ()
    assert len(lossy.collisions()) == 214
    assert exact.target.source == source.source
    for token in source.rows:
        original = source.read(token)
        output = exact.apply(original)
        decoded = exact.decode(output.target)
        assert tuple(choices[0] for _, choices in decoded.choices) == original.values
        assert token in decoded.inventory_candidates
        assert output.source.model_id == source.identity
        assert decoded.operation_id == exact.identity
    native = pack_from_declaration(DECLARATION)
    pack = binary_pack(exact, gap=1)
    for left, right in product(("p", "b", "a", "i", "s"), repeat=2):
        assert pack.sub_cost(left, right) == native.sub_cost(left, right)
    vowel = exact.target.read("a").values
    naive_zero_gap = sum(vowel) / len(vowel)
    assert naive_zero_gap == 20 / 48
    assert price(native.insert_cost, "a") == 44 / 48
    assert price(pack.insert_cost, "a") == 1
    assert price(native.insert_cost, "a") != naive_zero_gap
