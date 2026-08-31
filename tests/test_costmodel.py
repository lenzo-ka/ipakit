"""Regression tests for the shared cost-model parameter surface."""

from __future__ import annotations

import inspect
import math
import warnings
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Any

import ipakit
import pytest
from ipakit.bridges.costmodel import (
    CHEAP_INDEL,
    FAITHFUL,
    PANPHON_CONSERVING,
    AbsentCell,
    CostPack,
    CostPolicy,
    DeclaredCostFamily,
    Normalization,
    Segmentation,
    WinningPayloadSemiring,
    align_under,
    compare,
    house_pack,
    model_pack,
    pack_from_declaration,
    semiring_alignment,
)
from ipakit.distance_model import DistanceModel
from ipakit.features import IPAFeatures
from tiergraph.semiring import TROPICAL

CORPUS = Path(__file__).parent / "panphon" / "shared-corpus.txt"
DECLARATION = Path(__file__).parent / "panphon" / "panphon.xml"

ROUND_TRIP = """  <round-trip>
    <external-to-house fidelity="lossless"/>
    <house-to-external fidelity="lossless"/>
  </round-trip>
"""


def _words() -> list[str]:
    return CORPUS.read_text(encoding="utf-8").splitlines()


def test_default_policy_is_faithful_and_identity_names_every_field() -> None:
    assert FAITHFUL.is_faithful
    assert FAITHFUL.identity == ("costmodel/1.0 sub_scale=1.0 indel=1.0 norm=raw")
    assert not CHEAP_INDEL.is_faithful


def test_negative_or_nonfinite_policy_values_are_refused_at_construction() -> None:
    for value in (-1.0, math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError, match="substitution_scale"):
            CostPolicy(substitution_scale=value)
        with pytest.raises(ValueError, match="indel_weight"):
            CostPolicy(indel_weight=value)


def test_a_bad_policy_is_refused_before_the_fold_prices_a_phone() -> None:
    with pytest.raises(ValueError, match="indel_weight") as error:
        CostPolicy(indel_weight=-1.0)
    assert "phone" not in str(error.value)


def test_house_pack_reproduces_word_distance_exactly_over_the_shared_corpus() -> None:
    ipa = IPAFeatures()
    for source, target in combinations_with_replacement(_words(), 2):
        actual = compare(ipa, house_pack(ipa), source, target).edit_cost
        assert actual == ipa.word_distance(source, target).edit_cost


def test_indel_weight_scales_indels_and_never_the_substitution() -> None:
    ipa = IPAFeatures()
    pack = house_pack(ipa, CHEAP_INDEL)
    assert compare(ipa, pack, "kat", "kot").edit_cost == 0.32352092352092354
    assert compare(ipa, pack, "mbanda", "banda").edit_cost == 0.25


def test_the_house_arm_never_drops_and_raises_on_unconvertible_input() -> None:
    ipa = IPAFeatures()
    tokenize = house_pack(ipa).tokenize
    for word in _words():
        assert tokenize(word).dropped == ()
    with pytest.raises(ValueError):
        tokenize("☃")


def test_div_null_alignment_reproduces_word_distance_similarity() -> None:
    ipa = IPAFeatures()
    policy = CostPolicy(normalization=Normalization.DIV_NULL_ALIGNMENT)
    for source, target in combinations_with_replacement(_words(), 2):
        row = compare(ipa, house_pack(ipa, policy), source, target)
        result = ipa.word_distance(source, target)
        assert 1.0 - row.normalized == result.similarity


def test_align_under_is_the_only_foreign_call_site_of_the_fold() -> None:
    root = Path(__file__).parents[1] / "ipakit"
    calls: list[str] = []
    for path in root.rglob("*.py"):
        calls.extend(
            str(path.relative_to(root))
            for _ in range(path.read_text().count("._align("))
        )
    assert sorted(calls) == [
        "bridges/costmodel.py",
        "distance.py",
        "distance_model.py",
        "distance_model.py",
    ]


def test_align_under_refuses_bare_token_lists() -> None:
    ipa = IPAFeatures()
    pack = house_pack(ipa)
    with pytest.raises(AttributeError):
        align_under(ipa, pack, ["k", "a"], ["k", "o"])  # type: ignore[arg-type]
    assert (
        align_under(ipa, pack, Segmentation(("k", "a")), Segmentation(("k", "o")))[0]
        >= 0.0
    )


def test_declared_families_reproduce_the_captured_values_exactly() -> None:
    ipa = IPAFeatures()
    unweighted = pack_from_declaration(DECLARATION)
    assert compare(ipa, unweighted, "kat", "kot").edit_cost == 0.08333333333333333
    assert compare(ipa, unweighted, "kʰat", "kat").edit_cost == 0.041666666666666664
    assert compare(ipa, unweighted, "", "a").edit_cost == 0.9166666666666666


def test_winner_semiring_keeps_the_count_belonging_to_the_winning_move() -> None:
    winner = WinningPayloadSemiring(TROPICAL, 0, 0, lambda left, right: left + right)
    moves = [(3.0, 5), (2.0, 9), (4.0, 1)]
    result = winner.zero
    for move in moves:
        result = winner.add(result, move)
    assert result == (2.0, 9)


class _SymbolicSemiring:
    """A carrier with no numeric escape hatch for the fold-purity pin."""

    zero: tuple[Any, ...] = ("zero",)
    one: tuple[Any, ...] = ("one",)

    def add(self, left: tuple[Any, ...], right: tuple[Any, ...]) -> tuple[Any, ...]:
        return ("add", left, right)

    def multiply(
        self, left: tuple[Any, ...], right: tuple[Any, ...]
    ) -> tuple[Any, ...]:
        return ("multiply", left, right)


def test_alignment_fold_uses_only_the_four_semiring_operations() -> None:
    pack = CostPack(
        "symbolic",
        "test",
        lambda left, right: 0.0 if left == right else 1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        lambda word: Segmentation(tuple(word)),
        FAITHFUL,
    )
    result = semiring_alignment(
        pack,
        Segmentation(("a",)),
        Segmentation(("b",)),
        _SymbolicSemiring(),
        encode=lambda value: ("term", value),
    )
    assert result[0] == "add"


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_semiring_alignment_refuses_invalid_indel_prices(bad: float) -> None:
    pack = CostPack(
        "bad-price",
        "test",
        lambda left, right: 0.0,
        bad,
        bad,
        1.0,
        1.0,
        lambda word: Segmentation(tuple(word)),
        FAITHFUL,
    )
    with pytest.raises(ValueError, match="non-negative finite price"):
        semiring_alignment(
            pack,
            Segmentation(("a",)),
            Segmentation(("b",)),
            TROPICAL,
            encode=float,
        )


def test_absence_is_a_declared_term_in_one_product_fold(tmp_path: Path) -> None:
    declaration = tmp_path / "absent.xml"
    declaration.write_text(
        f"""<feature-table name="absent">
{ROUND_TRIP}  <features><feature name="f"/><feature name="g"/></features>
  <segments>
    <segment name="a" f="+"/>
    <segment name="b" f="-" g="+"/>
  </segments>
</feature-table>
""",
        encoding="utf-8",
    )
    ipa = IPAFeatures()
    skip = pack_from_declaration(declaration, absent=AbsentCell.SKIP)
    zero = pack_from_declaration(declaration, absent=AbsentCell.ZERO_COUNTED)
    half = pack_from_declaration(declaration, absent=AbsentCell.HALF_COUNTED)
    assert compare(ipa, skip, "a", "b").edit_cost == 1.0
    assert compare(ipa, zero, "a", "b").edit_cost == 0.5
    assert compare(ipa, half, "a", "b").edit_cost == 0.75

    with pytest.raises(ValueError, match="supports only absent='skip'"):
        pack_from_declaration(
            declaration,
            family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
            absent=AbsentCell.ZERO_COUNTED,
        )


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "not-a-number"])
def test_weighted_declaration_refuses_an_invalid_named_weight(
    tmp_path: Path, value: str
) -> None:
    declaration = tmp_path / "weights.xml"
    declaration.write_text(
        f"""<feature-table name="weights">
{ROUND_TRIP}\
  <features><feature name="f"/></features>
  <weights><weight name="f" value="{value}"/></weights>
  <segments><segment name="a" f="+"/></segments>
</feature-table>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="feature 'f'"):
        pack_from_declaration(
            declaration,
            family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
            absent=AbsentCell.SKIP,
        )


def test_weighted_declaration_requires_one_weight_per_feature(tmp_path: Path) -> None:
    declaration = tmp_path / "short-weights.xml"
    declaration.write_text(
        f"""<feature-table name="weights">
{ROUND_TRIP}\
  <features><feature name="f"/><feature name="g"/></features>
  <weights><weight name="f" value="1"/></weights>
  <segments><segment name="a" f="+" g="-"/></segments>
</feature-table>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="feature 'g'"):
        pack_from_declaration(
            declaration,
            family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
            absent=AbsentCell.SKIP,
        )


def test_comparison_machinery_cannot_branch_on_a_pack_identity(tmp_path: Path) -> None:
    source = (
        Path(__file__).parents[1] / "ipakit" / "bridges" / "costmodel.py"
    ).read_text()
    assert "if pack.name" not in source
    assert "isinstance(pack" not in source
    declaration = tmp_path / "complete-weights.xml"
    declaration.write_text(
        f"""<feature-table name="complete">
{ROUND_TRIP}\
  <features><feature name="f"/></features>
  <weights><weight name="f" value="1"/></weights>
  <segments><segment name="a" f="+"/><segment name="b" f="-"/></segments>
</feature-table>
""",
        encoding="utf-8",
    )
    packs = (
        pack_from_declaration(declaration),
        pack_from_declaration(
            declaration,
            family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
            absent=AbsentCell.SKIP,
        ),
    )
    for pack in packs:
        for cost in (pack.sub_cost, pack.insert_cost, pack.delete_cost):
            assert callable(cost)
            assert "family" not in inspect.getclosurevars(cost).nonlocals


class TestDoublingSubstitutionIsNotARescale:
    """The one-line repair, asked of a corpus rather than argued.

    panphon's substitution ceiling is 1.0 against an indel pair of 2.0, so
    the recurrence can never prefer two indels to a substitution however
    unlike the phones are. Doubling the substitution scale is the repair,
    and `PANPHON_CONSERVING` is it as a setting.

    What makes it a measurement rather than a change of units is that it
    does not move every pair by the same factor. A pure substitution
    doubles. A pure indel does not move at all. A mixed pair moves by
    something in between, because the doubling changes *which alignment
    wins* -- and that is the whole content of the question, since a
    uniform rescale would leave every ordering intact and be worth
    nothing.

    Pinned over both arms, because a claim about the repair that held for
    one geometry and not the other would be a claim about that geometry.
    """

    def _arms(self, ipa: IPAFeatures, policy: CostPolicy) -> dict[str, CostPack]:
        return {
            "house": house_pack(ipa, policy),
            "declared": pack_from_declaration(DECLARATION, policy),
        }

    def _ratio(self, ipa: IPAFeatures, arm: str, source: str, target: str) -> float:
        faithful = compare(ipa, self._arms(ipa, FAITHFUL)[arm], source, target)
        doubled = compare(ipa, self._arms(ipa, PANPHON_CONSERVING)[arm], source, target)
        return doubled.edit_cost / faithful.edit_cost

    def test_a_pure_substitution_doubles(self) -> None:
        ipa = IPAFeatures()
        for arm in ("house", "declared"):
            assert self._ratio(ipa, arm, "kat", "kot") == pytest.approx(2.0), arm

    def test_a_pure_indel_does_not_move(self) -> None:
        """The scale prices substitutions and nothing else, so a pair the
        aligner answers entirely with indels is untouched."""
        ipa = IPAFeatures()
        for arm in ("house", "declared"):
            assert self._ratio(ipa, arm, "mbanda", "banda") == pytest.approx(1.0), arm

    def test_a_mixed_pair_moves_by_neither_factor(self) -> None:
        """Between the two, because the doubling re-decides the alignment.
        A rescale could not do this, and a rescale would be worthless."""
        ipa = IPAFeatures()
        for arm in ("house", "declared"):
            ratio = self._ratio(ipa, arm, "a", "ndʒulu")
            assert 1.0 < ratio < 2.0, (arm, ratio)


class TestAnInventoryRelativePackIsNotAPortableOne:
    """Two kinds of cost model, and the difference has to stay visible.

    `house_pack` and `pack_from_declaration` price a pair from the two
    segments' declarations alone. Nothing about the rest of the inventory
    enters, so the number is portable and comparable across studies -- and
    compressed, because spreading a scale requires knowing what else
    exists.

    `model_pack` wraps a `DistanceModel`, which ranks a raw score within a
    reference distribution and bends the rank by gamma. That buys legible
    magnitudes and costs portability: the same pair against a different
    reference is a different number, and nothing in the number says which
    reference produced it. So the pack carries one and the row reports it.

    The machinery is adopted rather than rebuilt. `DistanceModel` already
    persists a matrix with a `metric_fingerprint` over the phones it
    holds, already refuses a reader whose feature space does not match,
    and already re-slices to a phoneset. A second redistribution here
    would have been a second place for the same number to live.
    """

    def test_a_portable_pack_names_no_reference(self) -> None:
        ipa = IPAFeatures()
        for pack in (house_pack(ipa), pack_from_declaration(DECLARATION)):
            assert pack.reference is None
            assert compare(ipa, pack, "kat", "kot").reference is None

    def test_an_inventory_relative_row_names_its_reference_and_gamma(self) -> None:
        ipa = IPAFeatures()
        model = DistanceModel.global_(ipa, gamma=2.0)
        row = compare(ipa, model_pack(ipa, model), "kat", "kot")
        assert row.reference is not None
        assert "gamma=2.0" in row.reference

    def test_gamma_raises_realized_cost_toward_the_budget(self) -> None:
        """The direction matters and is easy to get backwards. A
        `DistanceModel` ranks *confusability*, so a larger gamma pushes
        realized substitution costs UP toward the indel budget -- which is
        the whole reason the parameter exists, since a budget-correct
        ceiling nothing reaches leaves the aligner preferring
        substitution."""
        ipa = IPAFeatures()
        costs = [
            compare(
                ipa, model_pack(ipa, DistanceModel.global_(ipa, gamma=g)), "kat", "kot"
            ).edit_cost
            for g in (0.5, 1.0, 2.0)
        ]
        assert costs[0] < costs[1] < costs[2], costs

    def test_two_inventories_rank_one_contrast_differently(self) -> None:
        """The asymmetric case. One geometry, two references, two answers,
        and neither is wrong -- which is exactly why a bare figure needs
        its reference named beside it."""
        ipa = IPAFeatures()
        sparse = ipakit.Phoneset.from_list(list("ptkbdɡmnfsxlraeiou"), name="sparse")
        dense = ipakit.Phoneset.from_list(
            list("ptkbdɡmnŋfvszʃʒhlrjwæɛɪiuʊ"), name="dense"
        )
        scores = {}
        for name, phoneset in (("sparse", sparse), ("dense", dense)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = DistanceModel.for_phoneset(ipa, phoneset, gamma=1.0)
            scores[name] = model_pack(ipa, model).sub_cost("i", "ɪ")
        assert scores["sparse"] != scores["dense"], scores
