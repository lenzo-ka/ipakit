"""English's generated declaration and the curation loop behind it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ipakit

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "data" / "english-syllable-curation-2026-08-11.json"


def test_strictness_exposes_the_curated_schm_onset() -> None:
    strict = ipakit.syllabifier("english", strictness="strict")("ʃmˈɑlts")
    permissive = ipakit.syllabifier("english", strictness="permissive")("ʃmˈɑlts")
    assert strict.spelled() == ("mˈɑlts",)
    assert strict.unsyllabified == ((0, 1),)
    assert permissive.spelled() == ("ʃmˈɑlts",)
    assert permissive.unsyllabified == ()


def test_stress_is_a_nucleus_and_an_unknown_margin_is_not_absorbed() -> None:
    result = ipakit.syllabifier("english", strictness="strict")("ŋtˈɑ")
    assert result.spelled() == ("tˈɑ",)
    assert result.unsyllabified == ((0, 1),)


def test_leading_and_house_stress_find_the_same_nucleus() -> None:
    built = ipakit.syllabifier("english", strictness="strict")
    leading = built("ˈbaʊt")
    house = built("bˈaʊt")
    assert leading.spelled() == house.spelled() == ("bˈa", "ʊt")
    leading_nucleus = next(u for u in leading.form.units if "stress" in u.prosody)
    house_nucleus = next(u for u in house.form.units if "stress" in u.prosody)
    assert leading_nucleus.text.encode() == house_nucleus.text.encode() == "ˈa".encode()


def test_every_harvested_cluster_retains_evidence_and_a_decision() -> None:
    declaration = ipakit.language("english")
    harvested = [onset for onset in declaration.onsets if onset.harvested_count]
    assert harvested
    assert all(onset.exemplar and onset.decision for onset in harvested)
    schm = next(onset for onset in harvested if onset.source == "ʃ m")
    assert (schm.stratum, schm.harvested_count) == ("borrowing", 66)


def test_report_totals_and_iterations_are_self_consistent() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    grid = report["grid"]
    assert grid == {
        "constraint_illegal_attested": 61,
        "constraint_legal_attested": 89,
        "constraint_legal_unattested": 1,
    }
    queue = report["curation_queue"]
    assert queue["size"] == sum(queue["resolution_by_stratum"].values()) + len(
        queue["refusals"]
    )
    assert [row["iteration"] for row in report["iterations"]] == [0, 1, 2, 3]
    assert report["cross_check"]["shared_words"] == (
        report["cross_check"]["agreements"] + report["cross_check"]["disagreements"]
    )
    cross_check = report["cross_check"]
    assert (
        cross_check["normalizations"]["stress_to_nucleus"]["applied_to_forms"] == 128670
    )
    assert (
        cross_check["normalizations"]["registered_diphthong_tying"]["applied_to_forms"]
        == 0
    )
    assert {
        name: bucket["count"]
        for name, bucket in cross_check["disagreement_buckets"].items()
    } == {
        "stress_seat": 0,
        "untied_diphthong_nucleation": 18966,
        "genuine_boundary_difference": 1511,
        "other": 69473,
    }


def test_fixture_regeneration_is_attributed_and_records_refusals(
    tmp_path: Path,
) -> None:
    declaration = tmp_path / "english.xml"
    report = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "syllable_curation.py"),
            "--cmudict",
            str(ROOT / "tests" / "fixtures" / "cmudict_excerpt.dict"),
            "--date",
            "2026-08-11",
            "--declaration",
            str(declaration),
            "--report",
            str(report),
        ],
        check=True,
    )
    generated = json.loads(report.read_text(encoding="utf-8"))
    assert generated["corpus"] == {"forms": 101, "ingest_refusals": 1}
    assert generated["curation_queue"]["refusals"][0]["word"] == "unmappable"
    assert "do not edit by hand" in declaration.read_text(encoding="utf-8")
