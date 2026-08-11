"""The shared syllabification mechanism, before any worked language."""

from pathlib import Path

import pytest
from ipakit import Form, Language, syllabifier
from ipakit.syllable import read_language


def _declared(tmp_path: Path, body: str):
    path = tmp_path / "test.xml"
    path.write_text(body, encoding="utf-8")
    return read_language(path)


def test_span_agreement_validates_the_whole_candidate(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" />
  <onset span="[obstruent voiced=α] [obstruent voiced=α]" />
  <onset span="[-vowel]" />
</syllabification>""",
    )
    built = syllabifier(declaration)
    assert built("abda").spelled() == ("a", "bda")
    assert built("abta").spelled() == ("ab", "ta")


def test_stated_marks_are_honored_and_conflicts_reported() -> None:
    declaration = Language("test", "constraints", "test", nuclei=(), onsets=())
    # Stress is independently sufficient to establish each nucleus.
    result = syllabifier(declaration)("ˈa.bˈa")
    assert result.spelled() == ("ˈa", "ˈa")
    assert result.unsyllabified == ((2, 3),)
    assert len(result.conflicts) == 1
    assert result.form.to_ipa() == "ˈa.bˈa"


def test_word_edges_hold_and_linking_edges_are_crossable(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[-vowel]" />
</syllabification>""",
    )
    built = syllabifier(declaration)
    assert built("at#a").spelled() == ("at", "a")
    assert built("at‿a").spelled() == ("a", "t‿a")


def test_declared_codas_validate_the_word_final_margin(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[-vowel]" />
  <coda span="[-vowel]" />
</syllabification>""",
    )
    result = syllabifier(declaration)("ants")
    assert result.spelled() == ("an",)
    assert result.unsyllabified == ((2, 3), (3, 4))


def test_a_richer_boundary_carrier_round_trips(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[-vowel]" />
</syllabification>""",
    )
    result = syllabifier(declaration)(Form.parse("a.|ta"))
    assert result.form.to_ipa() == "a.|ta"
    assert result.marks() == "a.|ta"


def test_a_lone_agreement_variable_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="once"):
        _declared(
            tmp_path,
            """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[voiced=α]" />
</syllabification>""",
        )


def test_onset_metadata_is_preserved_and_strictness_filters_it(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" />
  <onset span="[-vowel]" />
  <onset span="ʃ m" stratum="borrowing" harvested-count="3"
    exemplar="schmaltz" decision="retain loan stratum"
    curation-provenance="fixture harvest iteration 2" />
</syllabification>""",
    )
    curated = declaration.onsets[1]
    assert (
        curated.stratum,
        curated.harvested_count,
        curated.exemplar,
        curated.decision,
        curated.curation_provenance,
    ) == (
        "borrowing",
        3,
        "schmaltz",
        "retain loan stratum",
        "fixture harvest iteration 2",
    )
    assert syllabifier(declaration, strictness="strict")("ʃmɑlʦ").unsyllabified == (
        (0, 1),
    )
    assert (
        syllabifier(declaration, strictness="permissive")("ʃmɑlʦ").unsyllabified == ()
    )


def test_unlabeled_declarations_are_admitted_at_every_strictness(
    tmp_path: Path,
) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="s t" />
</syllabification>""",
    )
    assert syllabifier(declaration, strictness="strict")("sta").spelled() == ("sta",)
    assert syllabifier(declaration, strictness="permissive")("sta").spelled() == (
        "sta",
    )


def test_unknown_strictness_is_refused() -> None:
    with pytest.raises(ValueError, match="strictness"):
        syllabifier("spanish", strictness="unknown")
