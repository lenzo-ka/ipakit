"""The optional, language-scoped ipa-dict input door."""

from pathlib import Path

import pytest
from ipakit.bridges.ipa_dict import IPADictReader

FIXTURE = Path(__file__).parent / "fixtures" / "ipa_dict_en_US.txt"


def test_fixture_echoes_complete_lines_and_collects_refusals() -> None:
    report = IPADictReader(FIXTURE, language="en_US").read()
    assert [entry.word for entry in report.entries] == ["hello", "good", "keyboard"]
    assert [IPADictReader(FIXTURE).emit_line(entry) for entry in report.entries] == [
        "hello\t/həˈloʊ/, /hɛˈloʊ/",
        "good\t/ɡʊd/",
        "keyboard\t/'ki:bɔrd/",
    ]
    keyboard = report.entries[2].pronunciations[0]
    assert keyboard.written == "'ki:bɔrd"
    assert keyboard.form.to_ipa() == "ˈkiːbɔrd"
    assert [(item.line_number, item.word) for item in report.refusals] == [
        (6, "half-read"),
        (7, "not-delimited"),
    ]
    assert "variant 2 'Q'" in report.refusals[0].reason
    assert "slash-delimited" in report.refusals[1].reason


def test_provenance_is_language_scoped_and_falls_back_to_file_identity() -> None:
    provenance = IPADictReader(FIXTURE, language="en_US").read().provenance
    assert provenance.language == "en_US"
    assert provenance.file.endswith("ipa_dict_en_US.txt")
    assert provenance.version


def test_unconfigured_environment_is_a_clean_absence() -> None:
    assert IPADictReader.from_environment("en_US", environ={}) is None


def test_environment_accepts_checkout_shape_and_missing_file_is_loud(
    tmp_path: Path,
) -> None:
    reader = IPADictReader.from_environment(
        "en_US", environ={"IPAKIT_IPA_DICT": str(tmp_path)}
    )
    assert reader is not None
    with pytest.raises(ValueError, match="is not a file"):
        reader.read()


def test_leading_bom_is_stripped_not_absorbed(tmp_path: Path) -> None:
    target = tmp_path / "xx.txt"
    target.write_text("﻿hello\t/həˈloʊ/\n", encoding="utf-8")
    report = IPADictReader(target).read()
    assert [entry.word for entry in report.entries] == ["hello"]
    assert report.refusals == ()


def test_whitespace_only_variants_are_refused_like_empty_ones(
    tmp_path: Path,
) -> None:
    target = tmp_path / "xx.txt"
    target.write_text("a\t/ /\nb\t/ /\nc\t//\n", encoding="utf-8")
    report = IPADictReader(target).read()
    assert report.entries == ()
    assert [refusal.line_number for refusal in report.refusals] == [1, 2, 3]
    assert all("is empty" in refusal.reason for refusal in report.refusals)
