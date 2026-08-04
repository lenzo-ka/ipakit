"""A scoring configuration is one named, versioned, by-value object.

#169: a word-distance number depends on ``gamma`` and the two indel costs,
which lived in separate arguments in separate places, so "the score" was not
a nameable thing. ``ScoringParameters`` makes it one, sitting beside
``metric_fingerprint`` the way the fingerprint sits beside the matrix.
"""

import dataclasses

import ipakit
import pytest
from ipakit.distance import SCORING_VERSION, ScoringParameters, cost_name


def test_of_reads_flat_costs_by_value():
    sp = ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    assert sp.gamma == 1.0
    assert sp.insert == "1.0"
    assert sp.delete == "1.0"
    assert sp.version == SCORING_VERSION


def test_a_named_schedule_is_captured_by_its_name():
    drop = ipakit.CostSchedule("example/schwa-drops", {"ə": 0.25}, 1.0)
    sp = ScoringParameters.of(gamma=1.0, insert_cost=drop, delete_cost=1.0)
    assert sp.insert == "example/schwa-drops"
    assert sp.insert == cost_name(drop)


def test_an_unnamed_lambda_admits_it_named_nothing():
    sp = ScoringParameters.of(gamma=1.0, insert_cost=lambda p: 1.0, delete_cost=1.0)
    # cost_name reports the qualified name, so a lambda ends in "<lambda>":
    # the honest admission that it named nothing a reader could pin.
    assert sp.insert.endswith("<lambda>")


def test_it_is_frozen():
    sp = ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sp.gamma = 2.0  # type: ignore[misc]


def test_equal_configurations_compare_and_hash_equal():
    a = ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    b = ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_the_control_a_gamma_difference_is_a_difference_here():
    # The instrument must be able to see a non-zero: a changed gamma, or a
    # changed cost, is not the same configuration.
    base = ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    assert ScoringParameters.of(gamma=2.0, insert_cost=1.0, delete_cost=1.0) != base
    assert ScoringParameters.of(gamma=1.0, insert_cost=0.5, delete_cost=1.0) != base
    assert ScoringParameters.of(gamma=1.0, insert_cost=1.0, delete_cost=0.5) != base


def test_identity_names_version_gamma_and_both_costs():
    sp = ScoringParameters.of(gamma=1.5, insert_cost=1.0, delete_cost=2.0)
    assert sp.identity == f"scoring/{SCORING_VERSION} gamma=1.5 insert=1.0 delete=2.0"


def test_a_model_reports_the_configuration_it_was_built_with():
    model = ipakit.distance_model(gamma=1.0, insert_cost=1.0, delete_cost=1.0)
    assert model.scoring == ScoringParameters.of(
        gamma=1.0, insert_cost=1.0, delete_cost=1.0
    )


def test_two_models_differing_only_in_gamma_report_different_configurations():
    a = ipakit.distance_model(gamma=1.0)
    b = ipakit.distance_model(gamma=2.0)
    assert a.scoring != b.scoring
    assert a.scoring.gamma == 1.0 and b.scoring.gamma == 2.0


def test_threshold_and_length_ratio_are_not_part_of_the_configuration():
    # They gate a verdict without changing the score, so two models that
    # differ only in them report the same scoring configuration.
    a = ipakit.distance_model(threshold=0.5, max_length_ratio=2.0)
    b = ipakit.distance_model(threshold=0.9, max_length_ratio=None)
    assert a.scoring == b.scoring


def test_it_is_exported_from_the_package():
    assert ipakit.ScoringParameters is ScoringParameters
