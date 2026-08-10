"""CMUdict corpus ingestion pins."""

from __future__ import annotations

from pathlib import Path

import ipakit
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "cmudict_excerpt.dict"


@pytest.fixture
def ingested(tmp_path: Path):
    corpus = ipakit.corpus.create(tmp_path / "cmudict")
    report = ipakit.corpus.ingest_cmudict(corpus, FIXTURE)
    return corpus, report


def test_fileids_variant_metadata_stress_and_round_trip(ingested):
    corpus, report = ingested
    assert report.added == 101
    assert "tomato" in corpus.ids()
    assert "tomato.2" in corpus.ids()

    first = corpus.read("tomato")
    second = corpus.read("tomato.2")
    assert first.meta == {"text": "tomato", "word": "tomato", "variant": 1}
    assert second.meta["word"] == "tomato"
    assert second.meta["variant"] == 2
    assert first.forms["cited"].to_ipa() == "təmˈe͜ɪtˌo͜ʊ"
    assert corpus.read("tomato").forms["cited"] == first.forms["cited"]


def test_refusals_accumulate_with_source_identity(ingested):
    corpus, report = ingested
    assert len(report.refusals) == 1
    refusal = report.refusals[0]
    assert refusal.line_number == 106
    assert refusal.word == "unmappable"
    assert refusal.line.startswith("unmappable ")
    assert "ZZZ" in refusal.reason
    assert "unmappable" not in corpus.ids()


def test_final_nasal_query_runs_on_cited_forms(ingested):
    corpus, _ = ingested
    matches = list(ipakit.corpus.query(corpus, "[+nasal] / _ #", role="cited"))
    assert any(match.fileid == "tom" and match.text == "m" for match in matches)


def test_apostrophe_is_a_literal_fileid(ingested):
    corpus, _ = ingested
    assert corpus.read("tom's").meta["word"] == "tom's"


def test_missing_source_is_loud(tmp_path: Path):
    corpus = ipakit.corpus.create(tmp_path / "cmudict")
    with pytest.raises(ipakit.corpus.CorpusError, match="is not a file"):
        ipakit.corpus.ingest_cmudict(corpus, tmp_path / "missing.dict")
