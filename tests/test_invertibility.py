"""Inventory-relative invertibility reports and the corpus regime split."""

import ipakit
from ipakit import _corpus_query as Q
from ipakit import rules
from ipakit.models import Phoneset

FEATURES = ipakit.load_ipa_features()


def inventory(*phones: str) -> Phoneset:
    return Phoneset.from_list(list(phones), "test")


def test_polarity_flip_passes_both_clauses():
    found = rules.parse("[voiced=α] -> [voiced=-α]", FEATURES).invertibility(
        inventory("t", "d"), FEATURES
    )
    assert found.invertible
    assert "clause 1" in found.reason and "clause 2" in found.reason


def test_final_devoicing_names_the_confusable_segment():
    found = rules.parse("d -> t / _ #", FEATURES).invertibility(
        inventory("d", "t"), FEATURES
    )
    assert not found.invertible
    assert found.clause == 2
    assert found.culprit == "t"
    assert "underlying 't'" in found.reason


def test_velar_nasal_verdict_is_relative_to_the_inventory():
    rule = rules.parse("n -> ŋ / _ k", FEATURES)
    assert rule.invertibility(inventory("n", "k"), FEATURES).invertible
    found = rule.invertibility(inventory("n", "ŋ", "k"), FEATURES)
    assert not found.invertible and found.culprit == "ŋ"


def test_deletion_fails_length_preservation():
    found = rules.parse("n -> ∅", FEATURES).invertibility(inventory("n"), FEATURES)
    assert not found.invertible and found.clause == 1


def test_invertible_corpus_check_takes_no_capped_enumeration(monkeypatch):
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
