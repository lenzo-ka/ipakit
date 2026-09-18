"""Boundary claims participate in transcription distance.

The phone matrix remains a phone-only artifact. Boundary comparison lives at
the transcription layer, where positions are segment-clock margins and types
are values on the declared ``level`` hierarchy.
"""

import ipakit
import pytest
from ipakit.metric import _arity_base


@pytest.fixture(scope="module")
def ipa() -> ipakit.IPAFeatures:
    return ipakit.IPAFeatures()


class TestBoundaryClaimsAreNotFree:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("ka.tə", "kat.ə"),
            ("a.a", "a#a"),
            ("a|a", "a‖a"),
            ("ka.tə", "katə"),
            ("a|a", "aa"),
        ],
    )
    def test_each_declared_witness_has_positive_cost(self, ipa, left, right):
        assert ipa.transcription_distance(left, right).edit_cost > 0.0

    def test_moving_a_claim_costs_two_one_sided_claims(self, ipa):
        moved = ipa.transcription_distance("ka.tə", "kat.ə").edit_cost
        one_sided = ipa.transcription_distance("ka.tə", "katə").edit_cost
        assert moved == 2 * one_sided


class TestBoundaryTypesUseTheDeclaredHierarchy:
    def test_syllable_to_word_is_nearer_than_syllable_to_utterance(self, ipa):
        near = ipa.transcription_distance("a.a", "a#a").edit_cost
        far = ipa.transcription_distance("a.a", "a‖a").edit_cost
        assert 0.0 < near < far

    def test_word_to_phrase_is_nearer_than_word_to_utterance(self, ipa):
        near = ipa.transcription_distance("a#a", "a|a").edit_cost
        far = ipa.transcription_distance("a#a", "a‖a").edit_cost
        assert 0.0 < near < far

    @pytest.mark.parametrize("other", ["word", "utterance"])
    def test_type_cost_is_the_exact_declared_value_distance(self, ipa, other):
        glyph = {"word": "#", "utterance": "‖"}[other]
        actual = ipa.transcription_distance("a.a", f"a{glyph}a").edit_cost
        level = ipa.features["level"]
        assert actual == 2 * _arity_base(ipa, False) * level.value_distance(
            "syllable", other
        )


class TestBoundaryNormalization:
    def test_one_sided_claim_uses_the_phone_null_scale(self, ipa):
        mass = _arity_base(ipa, False)
        result = ipa.transcription_distance("a.a", "aa")
        assert result.edit_cost == mass
        assert 1.0 - result.similarity == pytest.approx(mass / 4)

    def test_two_sided_claims_do_not_enlarge_the_scale(self, ipa):
        result = ipa.transcription_distance("a.a", "a#a")
        assert 1.0 - result.similarity == pytest.approx(result.edit_cost / 4)

    def test_boundary_only_forms_use_a_fixed_scale(self, ipa):
        mass = _arity_base(ipa, False)
        assert 1.0 - ipa.transcription_distance(".", "").similarity == 0.5
        assert 1.0 - ipa.transcription_distance(".", "‖").similarity == pytest.approx(
            2 * mass / (2 * mass)
        )


class TestClaimIdentity:
    @pytest.mark.parametrize("text", ["ka.tə", "a#a", "a|a", "a‖a"])
    def test_identical_claims_cost_exactly_zero(self, ipa, text):
        assert ipa.transcription_distance(text, text).edit_cost == 0.0

    def test_two_notations_for_the_same_word_boundary_compare_equal(self, ipa):
        assert ipa.transcription_distance("a#a", "a a").edit_cost == 0.0

    @pytest.mark.parametrize(
        ("run", "single"),
        [
            ("a.#a", "a#a"),
            ("a#.a", "a#a"),
            ("a.|a", "a|a"),
            ("a|.a", "a|a"),
        ],
    )
    def test_boundary_run_uses_its_strongest_claim_in_either_order(
        self, ipa, run, single
    ):
        assert ipa.transcription_distance(run, single).edit_cost == 0.0

    def test_prominence_cost_is_unchanged(self, ipa):
        assert ipa.transcription_distance("ˈba", "ba").edit_cost == pytest.approx(
            0.08695652173913043
        )


class TestBoundaryExplanation:
    def test_type_change_names_the_declared_level_term_and_margin(self, ipa):
        boundary = ipa.explain_transcription_distance("a.a", "a#a")[-1]
        assert boundary["op"] == "sub"
        assert boundary["at"] == 1
        assert boundary["cost"] == ipa.features["level"].value_distance(
            "syllable", "word"
        )
        assert boundary["terms"] == [
            {
                "label": "level (boundary)",
                "a": "syllable",
                "b": "word",
                "cost": ipa.features["level"].value_distance("syllable", "word"),
                "weight": 1.0,
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


class TestLiaisonSuppressesOnlyItsDistanceClaim:
    def test_u203f_deletes_the_word_boundary_claim(self, ipa):
        assert ipa.transcription_distance("lez‿ami", "lezami").edit_cost == 0.0
        assert ipa.transcription_distance("lez#ami", "lez‿ami").edit_cost > 0.0

    @pytest.mark.parametrize("mixed", ["a#‿a", "a‿#a"])
    def test_liaison_suppresses_only_its_own_claim(self, ipa, mixed):
        mass = _arity_base(ipa, False)
        assert ipa.transcription_distance(mixed, "a#a").edit_cost == 0.0
        assert ipa.transcription_distance(mixed, "aa").edit_cost == mass

    def test_the_two_ipakit_tie_senses_are_unchanged(self, ipa):
        assert ipa.transcription_distance("t͡s", "t͜s").edit_cost == pytest.approx(
            0.6666666666666666
        )


class TestLocalBoundaryPolicy:
    def fit(self, ipa, observed):
        return ipa.rank_pronunciations(observed, ["bc"], mode="local")[0].result

    def test_claim_outside_the_fitted_span_is_free_context(self, ipa):
        assert self.fit(ipa, "a|xbc").edit_cost == 0.0

    def test_claim_at_the_fitted_span_edge_counts(self, ipa):
        assert self.fit(ipa, "a|bc").edit_cost == _arity_base(ipa, False)

    def test_claim_inside_the_fitted_span_counts(self, ipa):
        assert self.fit(ipa, "b|c").edit_cost == _arity_base(ipa, False)

    def test_free_context_cannot_lower_an_available_fit(self, ipa):
        target = ".abc"
        fitted = ipa.rank_pronunciations(".abc.", [target], mode="local")[0].result
        extended = ipa.rank_pronunciations("abcx.abc.", [target], mode="local")[
            0
        ].result
        assert extended.similarity >= fitted.similarity


def test_boundary_claim_edit_cost_is_a_metric_on_a_small_exhaustive_corpus(ipa):
    marks = ("", ".", "#", "|", "‖")
    forms = sorted(
        {"aa"[:margin] + mark + "aa"[margin:] for margin in range(3) for mark in marks}
    )
    distances = {
        (left, right): ipa.transcription_distance(left, right).edit_cost
        for left in forms
        for right in forms
    }
    normalized = {
        (left, right): 1.0 - ipa.transcription_distance(left, right).similarity
        for left in forms
        for right in forms
    }
    for left in forms:
        for right in forms:
            assert distances[left, right] == distances[right, left]
            assert normalized[left, right] == normalized[right, left]
            for middle in forms:
                assert distances[left, right] <= (
                    distances[left, middle] + distances[middle, right]
                )
                assert normalized[left, right] <= (
                    normalized[left, middle] + normalized[middle, right]
                )
