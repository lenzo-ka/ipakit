"""Contracts the public API must not silently break.

Each test here pins a case where a caller could previously get a wrong
answer rather than an error.
"""

import ipakit
import pytest
from ipakit import IPAFeatures
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
    """An unresolved query used to drop every term, leaving a vacuous
    all() that matched the entire inventory."""

    def test_all_invalid_query_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="entire inventory"):
            ipa.phones_matching(["zzz", "qqq"])

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
        assert ipakit.word_distance("kæt", "k4t", strict=False).distance >= 0.0

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
