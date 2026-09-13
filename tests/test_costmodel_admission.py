"""Declared costs admit exact model tokens before alignment shortcuts."""

from dataclasses import replace

import pytest
from ipakit.bridges.costmodel import (
    AbsentCell,
    DeclaredCostFamily,
    Segmentation,
    compare_tokens,
    pack_from_ternary_declaration,
)
from ipakit.feature_models import read
from ipakit.features import IPAFeatures
from ipakit.finite_model import MissingToken


@pytest.fixture(scope="module")
def declaration():
    supplied = read("panphon")
    names = supplied.model.schema.features
    assert len(names) == 24
    # This custom policy supplies all weights. The shipped weight metadata
    # intentionally lacks two entries and cannot construct weighted costs.
    return replace(supplied, weight_names=names, weights=(1.0,) * len(names))


@pytest.fixture(scope="module")
def ipa():
    return IPAFeatures()


@pytest.mark.parametrize("family", list(DeclaredCostFamily))
@pytest.mark.parametrize(
    "left,right",
    [
        (("not-a-declared-token",), ()),
        ((), ("not-a-declared-token",)),
        (("not-a-declared-token",), ("not-a-declared-token",)),
    ],
)
def test_declared_admission_precedes_empty_and_identity_paths(
    declaration, ipa, family, left, right
):
    pack = pack_from_ternary_declaration(
        declaration, family=family, absent=AbsentCell.SKIP
    )
    with pytest.raises(MissingToken):
        compare_tokens(ipa, pack, Segmentation(left), Segmentation(right))


@pytest.mark.parametrize("family", list(DeclaredCostFamily))
def test_declared_admission_preserves_valid_identity_and_empty_costs(
    declaration, ipa, family
):
    pack = pack_from_ternary_declaration(
        declaration, family=family, absent=AbsentCell.SKIP
    )
    token = Segmentation(("p",))
    empty = Segmentation(())
    assert compare_tokens(ipa, pack, token, token).edit_cost == 0.0
    assert compare_tokens(ipa, pack, empty, empty).edit_cost == 0.0
    expected = (
        24.0
        if family is DeclaredCostFamily.WEIGHTED_DIFFERENCE
        else sum(0.5 if value == 0 else 1.0 for value in declaration.vectors["p"]) / 24
    )
    assert compare_tokens(ipa, pack, token, empty).edit_cost == expected
    assert compare_tokens(ipa, pack, empty, token).edit_cost == expected
