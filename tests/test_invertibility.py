"""Inventory-relative invertibility reports and the corpus regime split."""

import ipakit
from ipakit import _corpus_query as Q
from ipakit import rules
from ipakit.models import Phoneset

FEATURES = ipakit.load_ipa_features()


def inventory(*phones: str) -> Phoneset:
    return Phoneset.from_list(list(phones), "test")


def test_pin_exchange_has_no_absorption_fixed_point():
    found = rules.parse("[voiced=α] -> [voiced=-α]", FEATURES).invertibility(
        inventory("t", "d"), FEATURES
    )
    assert found.invertible
    assert "clause 1" in found.reason and "clause 2" in found.reason
    assert "no escape or absorption collision" in found.reason


def test_pin_clause_2_escape_names_the_confusable_segment():
    found = rules.parse("d -> t / _ #", FEATURES).invertibility(
        inventory("d", "t"), FEATURES
    )
    assert not found.invertible
    assert found.clause == 2
    assert found.culprit == "t"
    assert "(escape)" in found.reason
    assert "underlying 't'" in found.reason and "moved 'd'" in found.reason


def test_pin_shipped_final_devoicing_is_absorption():
    german = rules.shipped("german-final-devoicing", FEATURES)
    found = german.invertibility(inventory("d", "t"), FEATURES)
    assert not found.invertible and found.lost_at == 1
    assert found.rules[0].culprit == "t"
    assert "(absorption)" in found.rules[0].reason
    assert (
        "fixed point" in found.rules[0].reason and "moved 'd'" in found.rules[0].reason
    )
    assert str(found) == (
        "german-final-devoicing: 1 rule(s)\n"
        "  1  not invertible: clause 2 fails (absorption): underlying 't' is an "
        "absorption fixed point in this environment and collides with moved 'd'\n"
        "set: invertibility is lost at rule 1, because clause 2 fails "
        "(absorption): underlying 't' is an absorption fixed point in this "
        "environment and collides with moved 'd'; regime: capped candidate enumeration"
    )


def test_pin_velar_nasal_verdict_is_relative_to_the_inventory():
    rule = rules.parse("n -> ŋ / _ k", FEATURES)
    assert rule.invertibility(inventory("n", "k"), FEATURES).invertible
    found = rule.invertibility(inventory("n", "ŋ", "k"), FEATURES)
    assert not found.invertible and found.culprit == "ŋ"


def test_pin_deletion_fails_length_preservation():
    found = rules.parse("n -> ∅", FEATURES).invertibility(inventory("n"), FEATURES)
    assert not found.invertible and found.clause == 1


def test_fixture_invertible_corpus_check_takes_no_capped_enumeration(monkeypatch):
    grammar = rules.RuleSet.parse("[voiced=α] -> [voiced=-α]", FEATURES)

    def forbidden(*args, **kwargs):
        raise AssertionError("the deterministic regime called variants()")

    monkeypatch.setattr(rules.RuleSet, "variants", forbidden)
    answer = Q.derives(
        grammar, "d", "t", features=FEATURES, phoneset=inventory("d", "t")
    )
    assert isinstance(answer, rules.Derivation)
    assert answer.result == "t"


def test_report_names_the_first_loss_and_regime():
    grammar = rules.RuleSet.parse(
        "[voiced=α] -> [voiced=-α]\nd -> t / _ #", FEATURES, name="lesson"
    )
    report = grammar.invertibility(inventory("d", "t"), FEATURES)
    assert report.lost_at == 2
    assert report.regime == "capped candidate enumeration"
    assert "invertibility is lost at rule 2" in str(report)
