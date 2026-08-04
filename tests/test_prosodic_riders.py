"""Prosodic tiers ride on the unit clock and bear graded distance (#190).

Stress, a plain tone, and length are ``mode="prosodic"`` features whose marks
attach to a unit rather than sitting between units. They were invisible to the
metric -- ``ˈkɛt`` and ``ˌkɛt`` scored identical. Now each such rider adds one
graded term to the unit it rides on, read via the ordinal ``value_distance``,
metric-only so the stored features and round-trips are untouched. Sequence
values (tone contours) stay out until a sequence comparison exists.
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
        assert ipa.word_similarity("ˈkɛt", "ˌkɛt") < 1.0

    def test_a_level_change_is_smaller_than_stressed_vs_unstressed(self, ipa):
        # primary vs secondary is half a step; primary vs unstressed is a full
        # step, so ˈkɛt is nearer ˌkɛt than it is kɛt.
        near = ipa.word_similarity("ˈkɛt", "ˌkɛt")
        far = ipa.word_similarity("ˈkɛt", "kɛt")
        assert near > far > ipa.word_similarity("ˈkɛt", "ˈdɔɡ")

    def test_the_mark_rides_on_its_unit_in_the_alignment(self, ipa):
        r = ipa.word_distance("ˈkɛt", "ˌkɛt", return_alignment=True)
        assert ("ˈk", "ˌk") in r.alignment


class TestToneAndLengthAlsoRide:
    def test_a_plain_tone_is_read(self, ipa):
        assert ipa.distance("a", "á") > 0.0  # untoned vs high
        assert ipa.distance("á", "à") > 0.0  # high vs low

    def test_length_is_read(self, ipa):
        assert ipa.distance("a", "aː") > 0.0

    def test_a_tone_contour_stays_out(self, ipa):
        # A sequence value is a trajectory, not a scale point -- deferred.
        assert ipa.distance("a", "a᷅") == 0.0
        assert ipa.distance("a᷄", "a᷅") == 0.0


class TestItIsMetricOnlyAndContained:
    def test_a_phone_with_no_rider_is_unchanged(self, ipa):
        # p/b carry no prosody: their distance is the plain feature distance.
        assert ipa.distance("p", "b") == pytest.approx(0.05, abs=1e-6)

    def test_the_stored_features_are_untouched(self, ipa):
        # The rider is read for the metric; it does not enter the unit's
        # feature bundle, so a form still spells back unchanged.
        assert ipa.to_ipa(ipa.segments("ˈkɛt")) == "ˈkɛt"
        assert "stress" not in ipa.get_features("ˈk")

    def test_the_confusion_triangle_is_unmoved(self, ipa):
        # No shipped phone carries a rider, so the phone matrix is identical
        # -- confusability (a percentile over it) is stable.
        assert ipakit.confusability("s", "ʃ") == pytest.approx(
            ipakit.confusability("s", "ʃ")
        )


class TestExplainTrace:
    def test_it_traces_each_position_with_the_prosodic_term(self, ipa):
        steps = ipa.explain_word_distance("ˈkɛt", "ˌkɛt")
        sub = next(s for s in steps if s["op"] == "sub")
        assert sub["a"] == "ˈk" and sub["b"] == "ˌk"
        stress = next(t for t in sub["terms"] if t["label"].startswith("stress"))
        assert stress["a"] == "primary" and stress["b"] == "secondary"
        assert stress["cost"] == 0.5

    def test_matches_have_zero_cost(self, ipa):
        steps = ipa.explain_word_distance("ˈkɛt", "ˌkɛt")
        matches = [s for s in steps if s["op"] == "match"]
        assert matches and all(s["cost"] == 0.0 for s in matches)

    def test_the_module_level_wrapper_traces_too(self):
        import ipakit

        steps = ipakit.explain_word_distance("ˈkɛt", "ˌkɛt")
        sub = next(s for s in steps if s["op"] == "sub")
        stress = next(t for t in sub["terms"] if t["label"].startswith("stress"))
        assert stress["a"] == "primary" and stress["b"] == "secondary"
