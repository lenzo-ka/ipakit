"""Prosodic tiers ride on the unit clock and bear graded distance (#190).

Stress, tone, and length are ``mode="prosodic"`` features whose marks
attach to a unit rather than sitting between units. They were invisible to the
metric -- ``ˈkɛt`` and ``ˌkɛt`` scored identical. Now each such rider adds one
graded term to the unit it rides on, read via the ordinal ``value_distance``,
metric-only so the stored features and round-trips are untouched. Sequence
values use ordered, graded edit distance over their declared steps.
"""

import ipakit
import pytest


@pytest.fixture(scope="module")
def ipa() -> ipakit.IPAFeatures:
    return ipakit.IPAFeatures()


class TestTheStressFeatureIsAGradedOrdinal:
    def test_three_levels_in_prominence_order(self, ipa):
        assert ipa.features["stress"].values == ["none", "secondary", "primary"]

    def test_primary_and_secondary_are_a_half_step(self, ipa):
        f = ipa.features["stress"]
        assert f.value_distance("primary", "secondary") == 0.5
        assert f.value_distance("primary", "none") == 1.0
        assert f.value_distance("secondary", "none") == 0.5


class TestStressIsRead:
    def test_the_reported_bug_is_fixed(self, ipa):
        # #190: these were 1.0 (identical) before.
        assert ipa.transcription_similarity("ˈkɛt", "ˌkɛt") < 1.0

    def test_a_level_change_is_smaller_than_stressed_vs_unstressed(self, ipa):
        # primary vs secondary is half a step; primary vs unstressed is a full
        # step, so ˈkɛt is nearer ˌkɛt than it is kɛt.
        near = ipa.transcription_similarity("ˈkɛt", "ˌkɛt")
        far = ipa.transcription_similarity("ˈkɛt", "kɛt")
        assert near > far > ipa.transcription_similarity("ˈkɛt", "ˈdɔɡ")

    def test_the_mark_rides_on_its_unit_in_the_alignment(self, ipa):
        r = ipa.transcription_distance("ˈkɛt", "ˌkɛt", return_alignment=True)
        assert ("ˈɛ", "ˌɛ") in r.alignment


class TestToneAndLengthAlsoRide:
    def test_a_plain_tone_is_read(self, ipa):
        assert ipa.distance("a", "á") > 0.0  # untoned vs high
        assert ipa.distance("á", "à") > 0.0  # high vs low

    def test_length_is_read(self, ipa):
        assert ipa.distance("a", "aː") > 0.0

    def test_a_tone_contour_is_read(self, ipa):
        assert ipa.distance("a", "a᷅") > 0.0
        assert ipa.distance("a᷄", "a᷅") > 0.0

    def test_contour_sequences_price_without_a_tone_term(self, ipa):
        terms = ipa.explain_transcription_distance("ǎ̂", "â̌")[0]["terms"]
        contour = [term for term in terms if term["label"] == "contour (prosodic)"]
        assert contour and contour[0]["cost"] > 0.0
        assert not [term for term in terms if term["label"] == "tone (prosodic)"]


class TestSequenceValuedProsody:
    @staticmethod
    def word_distance(ipa, left, right):
        return ipa.transcription_distance(left, right).edit_cost

    def test_different_levels_are_not_identical(self, ipa):
        assert self.word_distance(ipa, "ma˧˥", "ma˧˩") > 0.0

    def test_order_alone_is_not_normalized_away(self, ipa):
        assert self.word_distance(ipa, "ma˥˩", "ma˩˥") > 0.0

    def test_level_differences_are_graded(self, ipa):
        assert ipa.distance("a˧˥", "a˧˦") < ipa.distance("a˧˥", "a˧˩")
        assert ipa.distance("a˩˨", "a˩˧") < ipa.distance("a˩˨", "a˩˥")

    def test_unequal_lengths_compare(self, ipa):
        assert ipa.distance("a˧˥", "a˧˥˧") > 0.0

    def test_identity_is_exactly_zero(self, ipa):
        assert ipa.distance("a˧˥˧", "a˧˥˧") == 0.0

    def test_single_level_cost_is_unchanged(self, ipa):
        terms = ipa.explain_transcription_distance("a˥", "a˧")[0]["terms"]
        tone = next(term for term in terms if term["label"] == "tone (prosodic)")
        assert (tone["a"], tone["b"], tone["cost"]) == ("top", "mid", 0.5)


class TestItIsMetricOnlyAndContained:
    def test_a_phone_with_no_rider_is_unchanged(self, ipa):
        # p/b carry no prosody: their distance is the plain feature distance.
        assert ipa.distance("p", "b") == pytest.approx(1 / 21, abs=1e-6)

    def test_the_stored_features_are_untouched(self, ipa):
        # The rider is read for the metric; it does not enter the unit's
        # feature bundle, so a form still spells back unchanged.
        assert ipa.read("ˈkɛt").to_ipa() == "ˈkɛt"
        with pytest.warns(ipakit.FeatureNarrowingWarning):
            assert "stress" not in ipa.get_features("ˈɛ")

    def test_the_prosodic_feature_adds_no_phone_term(self, ipa):
        # No shipped phone carries a rider. The exact position is repinned
        # when another segmental declaration moves the reference matrix.
        assert ipakit.similarity_position("s", "ʃ") == 0.9984361968306923


class TestExplainTrace:
    def test_it_traces_each_position_with_the_prosodic_term(self, ipa):
        steps = ipa.explain_transcription_distance("ˈkɛt", "ˌkɛt")
        sub = next(s for s in steps if s["op"] == "sub")
        assert sub["a"] == "ˈɛ" and sub["b"] == "ˌɛ"
        stress = next(t for t in sub["terms"] if t["label"].startswith("stress"))
        assert stress["a"] == "primary" and stress["b"] == "secondary"
        assert stress["cost"] == 0.5

    def test_matches_have_zero_cost(self, ipa):
        steps = ipa.explain_transcription_distance("ˈkɛt", "ˌkɛt")
        matches = [s for s in steps if s["op"] == "match"]
        assert matches and all(s["cost"] == 0.0 for s in matches)

    def test_the_module_level_wrapper_traces_too(self):
        import ipakit

        steps = ipakit.explain_transcription_distance("ˈkɛt", "ˌkɛt")
        sub = next(s for s in steps if s["op"] == "sub")
        stress = next(t for t in sub["terms"] if t["label"].startswith("stress"))
        assert stress["a"] == "primary" and stress["b"] == "secondary"
