from __future__ import annotations

import json
from pathlib import Path

import ipakit
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _corpus(tmp_path: Path):
    corpus = ipakit.corpus.create(tmp_path / "corpus")
    pairs = {
        "yes": ("anp", "amp"),
        "no": ("ant", "amp"),
        "missing": ("anp", None),
    }
    for entry_id, (source, target) in pairs.items():
        forms = {"broad": ipakit.read(source)}
        if target is not None:
            forms["narrow"] = ipakit.read(target)
        corpus.add(entry_id, {}, forms)
    corpus.put_split("held-out", ["yes", "no", "missing"])
    return corpus


def test_experiment_classifies_serializes_and_compares(tmp_path: Path):
    corpus = _corpus(tmp_path)
    grammar = ipakit.RuleSet.parse("n -> m / _ [place=bilabial]", name="assimilation")
    report = ipakit.Experiment(
        grammar, corpus, "broad", "narrow", split="held-out"
    ).run()

    assert report.coverage == {"derived": 1, "total": 3, "ratio": 1 / 3}
    assert report.counts == {
        "derivable": 1,
        "provably_underivable": 1,
        "cap_truncated": 0,
        "ill_formed_input": 1,
    }
    document = json.loads(report.to_json())
    assert document["provenance"]["rule_set"]["name"] == "assimilation"
    assert document["provenance"]["corpus"].startswith("sha256:")
    assert document["entries"][1]["source"] == "ant"
    assert ipakit.ExperimentReport.from_json(report.to_json()) == report

    identity = ipakit.RuleSet.parse("", name="identity")
    other = ipakit.Experiment(
        identity, corpus, "broad", "narrow", split="held-out"
    ).run()
    assert [
        (move.entry_id, move.before, move.after) for move in report.compare(other)
    ] == [("yes", "derivable", "provably_underivable")]


def test_experiment_refuses_a_stale_split(tmp_path: Path):
    corpus = _corpus(tmp_path)
    corpus.remove("yes")
    with pytest.raises(ipakit.corpus.CorpusError, match="missing entries"):
        ipakit.Experiment(
            ipakit.RuleSet(()), corpus, "broad", "narrow", split="held-out"
        ).run()


def test_cmudict_slice_executed_demonstration(tmp_path: Path):
    """The documented corpus experiment numbers are executed, not copied."""
    corpus = ipakit.corpus.create(tmp_path / "cmu")
    ingested = ipakit.corpus.ingest_cmudict(
        corpus,
        ROOT / "tests" / "fixtures" / "cmudict_excerpt.dict",
        mapper=ipakit.CMUMapper(),
    )
    assert ingested.added == 101
    grammar = ipakit.shipped("experiment-demo")
    chosen = tuple(list(corpus.ids())[:25])
    for entry_id in chosen:
        source = corpus.read(entry_id).forms["cited"]
        corpus.put_form(entry_id, "observed", ipakit.read(grammar.apply(source)))
    first = chosen[0]
    corpus.put_form(first, "observed", ipakit.read("ʒ"))
    corpus.put_split("demo", chosen)

    report = ipakit.Experiment(grammar, corpus, "cited", "observed", split="demo").run()
    assert report.coverage == {"derived": 24, "total": 25, "ratio": 0.96}
    assert report.counts == {
        "derivable": 24,
        "provably_underivable": 1,
        "cap_truncated": 0,
        "ill_formed_input": 0,
    }
