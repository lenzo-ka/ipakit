"""Contracts the public API must not silently break.

Each test here pins a case where a caller could previously get a wrong
answer rather than an error.
"""

import dataclasses

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.form import Form
from ipakit.models import Phone


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestDistanceRefusesWords:
    """distance() compares single units. It used to parse multi-unit input,
    fail internally, and return the maximal-difference sentinel -- so two
    identical words reported as maximally different, with no error."""

    def test_identical_words_do_not_report_maximal_difference(self) -> None:
        with pytest.raises(ValueError, match="single units"):
            ipakit.distance("kat", "kat")

    def test_error_names_the_right_tool(self) -> None:
        with pytest.raises(ValueError, match="word_distance"):
            ipakit.distance("kæt", "dɒɡ")

    def test_single_units_still_work(self) -> None:
        assert 0.0 < ipakit.distance("p", "b") < 1.0
        assert ipakit.distance("t͡s", "t͡s") == 0.0
        assert ipakit.distance("t͡s͜a", "t͡s͜a") == 0.0  # one unit, several parts

    def test_word_level_tools_are_exported(self) -> None:
        for name in ("word_distance", "segment_distance", "pairwise_distances"):
            assert name in ipakit.__all__, name

    def test_segment_distance_accepts_multiple_units(self) -> None:
        assert ipakit.segment_distance("kat", "kat") == 0.0
        assert ipakit.segment_distance("kat", "kad") > 0.0


class TestQueriesRefuseToMatchEverything:
    """A query term that names nothing must be an error, alone or beside
    a term that resolves: dropped, it leaves either a vacuous all() over
    the entire inventory or a query answering for a wider class than the
    caller asked for."""

    def test_all_invalid_query_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="resolves to no feature term"):
            ipa.phones_matching(["zzz", "qqq"])

    def test_one_invalid_term_beside_a_valid_one_raises(self, ipa: IPAFeatures) -> None:
        # ['plosive', 'zzz'] must not answer as ['plosive'].
        with pytest.raises(ValueError, match="'zzz' resolves to no feature term"):
            ipa.phones_matching(["plosive", "zzz"])

    def test_valid_query_still_filters(self, ipa: IPAFeatures) -> None:
        bilabials = ipa.phones_matching({"place": "bilabial"})
        assert "p" in bilabials and "t" not in bilabials
        assert len(bilabials) < len(ipa.phones)


class TestMeasurementRejectsUnconvertibleInput:
    """Conversion may be lossy; measurement may not. word_distance used to
    drop unknown symbols and return a plausible number from what was left
    -- comparing 'kæt' against 'kt'."""

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown symbol"):
            ipakit.word_distance("kæt", "k4t")
        with pytest.raises(ValueError, match="unknown symbol"):
            ipakit.word_similarity("kæt", "k4t")

    def test_lossy_measurement_is_opt_in(self) -> None:
        assert ipakit.word_distance("kæt", "k4t", strict=False).edit_cost >= 0.0

    def test_clean_input_unaffected(self) -> None:
        assert ipakit.word_similarity("kæt", "kæd") > 0.9


class TestInventoryIsImmutable:
    """The module API is backed by one cached instance; a write to a phone
    bundle used to corrupt what every later call read."""

    def test_phone_features_are_read_only(self, ipa: IPAFeatures) -> None:
        with pytest.raises(TypeError):
            ipa.get_phone("p").features["voiced"] = "+"  # type: ignore[index]

    def test_features_still_returns_a_mutable_copy(self, ipa: IPAFeatures) -> None:
        feats = ipa.get_features("p")
        feats["voiced"] = "+"  # caller's copy, must not write through
        assert ipa.get_features("p")["voiced"] == "-"

    def test_a_corrupted_phone_must_be_constructed(self, ipa: IPAFeatures) -> None:
        # The supported way to build a variant: make a new Phone.
        variant = Phone(symbol="p", features={**ipa.get_phone("p").features})
        assert variant.features["place"] == "bilabial"


class TestAFormIsImmutable:
    """`Unit`, `Boundary` and `Form` are frozen dataclasses, which stops a
    *field* being rebound and says nothing about the mapping a field points
    at. A write to a unit's prosody was accepted and left the form spelling
    one thing and reading another -- the same shape as the write to a phone
    bundle above, on the other half of the API.
    """

    def test_a_units_prosody_cannot_be_written_through(self) -> None:
        form = Form.parse("a\u02e9")
        with pytest.raises(TypeError):
            form.units[0].prosody["tone"] = "top"  # type: ignore[index]
        assert form.units[0].prosody == {"tone": "bottom"}
        assert form.to_ipa() == "a\u02e9"

    def test_a_units_features_cannot_be_written_through(self) -> None:
        form = Form.parse("a")
        with pytest.raises(TypeError):
            form.units[0].features["manner"] = "plosive"  # type: ignore[index]
        assert form.units[0].features["manner"] == "vowel"

    def test_a_boundarys_features_cannot_be_written_through(self) -> None:
        (boundary,) = Form.parse("a.b").boundaries
        with pytest.raises(TypeError):
            boundary.features["level"] = "word"  # type: ignore[index]
        assert boundary.features["level"] == "syllable"

    def test_a_variant_unit_must_be_constructed(self) -> None:
        # The supported way to write one: build a new Unit. The copy handed
        # to `replace` is the caller's, and writing it after the fact must
        # not reach the unit either.
        unit = Form.parse("a")[0]
        mine = {**unit.prosody, "stress": "primary"}
        variant = dataclasses.replace(unit, prosody=mine)
        mine["stress"] = "secondary"
        assert variant.prosody == {"stress": "primary"}
        assert unit.prosody == {}
