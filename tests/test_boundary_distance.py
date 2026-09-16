"""Boundary claims participate in transcription distance.

The phone matrix remains a phone-only artifact. Boundary comparison lives at
the transcription layer, where positions are segment-clock margins and types
are values on the declared ``level`` hierarchy.
"""

import ipakit
import pytest


@pytest.fixture(scope="module")
def ipa() -> ipakit.IPAFeatures:
    return ipakit.IPAFeatures()


class TestBoundaryClaimsAreNotFree:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("ka.tə", "kat.ə"),  # same type, different position
            ("a.a", "a#a"),  # same position, different type
            ("a|a", "a‖a"),  # phrase versus utterance
            ("ka.tə", "katə"),  # claim versus unclaimed margin
            ("a|a", "aa"),
        ],
    )
    def test_each_declared_witness_has_positive_cost(self, ipa, left, right):
        assert ipa.transcription_distance(left, right).edit_cost > 0.0

    def test_position_and_type_are_independent_witnesses(self, ipa):
        moved = ipa.transcription_distance("ka.tə", "kat.ə").edit_cost
        retyped = ipa.transcription_distance("a.a", "a#a").edit_cost
        assert moved > 0.0
        assert retyped > 0.0


class TestBoundaryTypesUseTheDeclaredHierarchy:
    def test_syllable_to_word_is_nearer_than_syllable_to_utterance(self, ipa):
        near = ipa.transcription_distance("a.a", "a#a").edit_cost
        far = ipa.transcription_distance("a.a", "a‖a").edit_cost
        assert 0.0 < near < far

    def test_word_to_phrase_is_nearer_than_word_to_utterance(self, ipa):
        near = ipa.transcription_distance("a#a", "a|a").edit_cost
        far = ipa.transcription_distance("a#a", "a‖a").edit_cost
        assert 0.0 < near < far


class TestClaimIdentity:
    @pytest.mark.parametrize("text", ["ka.tə", "a#a", "a|a", "a‖a"])
    def test_identical_claims_cost_exactly_zero(self, ipa, text):
        assert ipa.transcription_distance(text, text).edit_cost == 0.0

    def test_two_notations_for_the_same_word_boundary_compare_equal(self, ipa):
        assert ipa.transcription_distance("a#a", "a a").edit_cost == 0.0

    def test_prominence_cost_is_unchanged(self, ipa):
        assert ipa.transcription_distance("ˈba", "ba").edit_cost == pytest.approx(
            0.08695652173913043
        )


class TestBoundaryExplanation:
    def test_type_change_names_the_declared_level_term_and_margin(self, ipa):
        boundary = ipa.explain_transcription_distance("a.a", "a#a")[-1]
        assert boundary["op"] == "sub"
        assert boundary["at"] == 1
        assert boundary["terms"] == [
            {
                "label": "level (boundary)",
                "a": "syllable",
                "b": "word",
                "cost": 0.3333,
            }
        ]

    def test_claim_against_unclaimed_is_not_an_absence_assertion(self, ipa):
        boundary = ipa.explain_transcription_distance("a|a", "aa")[-1]
        assert boundary["op"] == "delete"
        assert boundary["a"] == "phrase"
        assert boundary["b"] is None


def test_inventory_model_also_prices_boundary_claims(ipa):
    model = ipakit.distance_model()
    assert model.transcription_distance("a|a", "aa").edit_cost > 0.0
    assert model.transcription_distance("a#a", "a a").edit_cost == 0.0
