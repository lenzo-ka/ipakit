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
    assert result.spelled() == ("ˈa", "bˈa")
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
