from __future__ import annotations

from pathlib import Path

import ipakit
import pytest
from ipakit import _corpus, rules
from ipakit import _corpus_query as Q
from ipakit._rewrite_graph import japanese_moraic_fixtures
from ipakit.form import Form

FEATURES = ipakit.load_ipa_features()


class TestContextCompilerVariables:
    def test_lone_environment_variable_binds_like_the_shipped_rule(self):
        grammar = rules.shipped("american-english", FEATURES)
        assimilation = next(
            rule for rule in grammar.rules if rule.name == "nasal assimilation"
        )
        form = ipakit.read("ˈɪnpʊt")

        compiled = Q.context("n / _ [place=α]", FEATURES)
        found = tuple(compiled.sites(form.units, FEATURES, form.intervals))
        recognized = tuple(assimilation.recognize(form, FEATURES))

        assert found == recognized
        assert found[0].bindings == (("α", "bilabial"),)

    def test_lone_target_variable_is_also_a_bind_only_query(self):
        form = ipakit.read("pa")
        query = Q.context("[place=α]", FEATURES)

        sites = tuple(query.sites(form.units, FEATURES, form.intervals))

        assert [site.bindings for site in sites] == [(("α", "bilabial"),)]

    def test_two_occurrences_still_require_agreement(self):
        query = Q.context("a / [place=α] _ [place=α]", FEATURES)
        agreeing = ipakit.read("pap")
        disagreeing = ipakit.read("pat")

        assert len(tuple(query.sites(agreeing.units, FEATURES))) == 1
        assert tuple(query.sites(disagreeing.units, FEATURES)) == ()

    def test_one_variable_still_cannot_name_two_features(self):
        with pytest.raises(rules.RuleError, match="on two features"):
            Q.context("a / [place=α] _ [voiced=α]", FEATURES)


@pytest.mark.parametrize("target", ["∅", "[zero]", "0", "Ø"])
def test_context_refuses_null_and_zero_targets_loudly(target: str):
    with pytest.raises(
        rules.RuleError, match="insertion sites are not recognizable patterns"
    ):
        Q.context(f"{target} / _ [manner=nasal]", FEATURES)


def test_feature_context_returns_exact_resolvable_graph_paths(tmp_path: Path):
    corpus = _corpus.create(tmp_path / "c")
    corpus.add("cat", {}, {"broad": ipakit.read("kæt")})
    corpus.add("dog", {}, {"broad": ipakit.read("dɒɡ")})
    corpus.add("tin", {}, {"broad": ipakit.read("tɪn")})

    found = list(Q.query(corpus, "[vowel] / _ [nasal]", role="broad"))

    assert [entry_id for entry_id, _ in found] == ["tin"]
    restored = corpus.read("tin").forms["broad"]
    assert len(found[0][1]) == 1
    assert restored._graph.resolve(found[0][1][0]).event is not None


def test_empty_query_does_not_restore_an_unqueried_role(tmp_path: Path, monkeypatch):
    corpus = _corpus.create(tmp_path / "c")
    corpus.add("one", {}, {"broad": ipakit.read("a"), "secret": ipakit.read("z")})
    original = Form.from_dict.__func__

    def observe(cls, wire):
        restored = original(cls, wire)
        assert restored.to_ipa() != "z"
        return restored

    monkeypatch.setattr(Form, "from_dict", classmethod(observe))
    assert list(Q.query(corpus, "[nasal]", role="broad")) == []


def test_all_attested_japanese_pairs_have_deterministic_witnesses():
    grammar = rules.shipped("japanese-moraic", FEATURES)
    for fixture in japanese_moraic_fixtures().values():
        answer = Q.derives(grammar, fixture.source, fixture.output, features=FEATURES)
        assert isinstance(answer, rules.Derivation)
    wrong = Q.derives(grammar, "pɛn", "wrong", features=FEATURES)
    assert isinstance(wrong, Q.ExhaustiveRefusal)


def test_optional_witness_and_truncated_unknown():
    grammar = rules.RuleSet.parse("t ~> ʔ / _ #", FEATURES)
    answer = Q.derives(grammar, "kæt", "kæʔ", features=FEATURES)
    assert isinstance(answer, rules.Derivation)
    assert answer.fired

    many = rules.RuleSet.parse("ə ~> ∅", FEATURES)
    unknown = Q.derives(many, "əəə", "xxx", features=FEATURES, limit=1)
    assert isinstance(unknown, Q.BudgetRefusal)
    assert unknown.unexplored == 7


def test_corpus_derivation_door_streams_pairs(tmp_path: Path):
    corpus = _corpus.create(tmp_path / "c")
    corpus.add("one", {}, {"source": ipakit.read("kæt"), "target": ipakit.read("kæʔ")})
    grammar = rules.RuleSet.parse("t ~> ʔ / _ #", FEATURES)
    first = next(
        Q.query_derivations(
            corpus,
            grammar,
            source_role="source",
            target_role="target",
            features=FEATURES,
        )
    )
    assert first[0] == "one"
    assert isinstance(first[1], rules.Derivation)


def test_thousand_entry_query_yields_before_restoring_the_tail(
    tmp_path: Path, monkeypatch
):
    corpus = _corpus.create(tmp_path / "c")
    for index in range(1000):
        corpus.add(f"e{index:04}", {}, {"broad": ipakit.read("a")})
    restored = 0
    original = Form.from_dict.__func__

    def count(cls, wire):
        nonlocal restored
        restored += 1
        return original(cls, wire)

    monkeypatch.setattr(Form, "from_dict", classmethod(count))
    stream = Q.query(corpus, "[vowel]", role="broad")
    assert next(stream)[0] == "e0000"
    assert restored == 1
