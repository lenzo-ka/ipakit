"""The shared syllabification mechanism, before any worked language."""

import re
from dataclasses import replace
from pathlib import Path

import pytest
from ipakit import Form, Language, language, languages, syllabifier
from ipakit.rules import RuleSet, parse
from ipakit.syllable import (
    MODES,
    SYLLABLES_DIR,
    admitted_strata,
    declared_strata,
    read_language,
)


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


class TestTheAdmittedStrata:
    """A stratum is a curation decision recorded in the data.

    It was four copies of three words -- twice inside one dict literal in
    ``syllable.py``, once in the grammar, once in the curation script -- and
    the filter kept an onset only if its stratum was in the copy it could see.
    A stratum that reached the data and not that literal was therefore
    discarded exactly as though the curator had asked for it to be, with no
    error, at the most permissive setting there is: 39 of English's 125
    declared onsets, under a green suite. These are the predicates that make
    the copies unable to disagree and the discard unable to be silent.
    """

    def test_the_admitted_vocabulary_is_what_the_declarations_name(self) -> None:
        """Measured against the documents, by a different read of them."""
        supplied = {
            match
            for name in languages()
            for match in re.findall(
                r'stratum="([^"]*)"',
                (SYLLABLES_DIR / f"{name}.xml").read_text(encoding="utf-8"),
            )
        }
        assert len(supplied) >= 2, f"only {supplied} found; the sweep is vacuous"
        assert declared_strata() == supplied

    def test_the_default_and_permissive_are_one_admission(self) -> None:
        """The same object, so no edit can make them differ while reading alike."""
        assert admitted_strata(None) is admitted_strata("permissive")

    def test_strict_admits_a_subset_of_permissive(self) -> None:
        assert admitted_strata("strict") < admitted_strata("permissive")
        assert admitted_strata("strict") <= declared_strata()

    def test_permissive_drops_no_declared_onset(self) -> None:
        """The property the silent filter broke, asked of every shipped language."""
        for name in languages():
            declared = language(name)
            for strictness in (None, "permissive"):
                built = syllabifier(declared, strictness=strictness)
                assert len(built.language.onsets) == len(declared.onsets), (
                    f"{name} at strictness {strictness!r} kept "
                    f"{len(built.language.onsets)} of {len(declared.onsets)} "
                    f"declared onsets"
                )

    def test_an_undeclared_stratum_is_refused_and_named(self) -> None:
        """The witness. Renaming a stratum used to lose the onsets carrying it."""
        declared = language("english")
        renamed = replace(
            declared,
            onsets=tuple(
                (
                    replace(onset, stratum="areal")
                    if onset.stratum == "marginal"
                    else onset
                )
                for onset in declared.onsets
            ),
        )
        with pytest.raises(ValueError, match="areal"):
            syllabifier(renamed, strictness="permissive")

    def test_only_a_labeled_onset_is_checked(self) -> None:
        """An unlabeled onset is core, and no vocabulary applies to it."""
        declared = language("english")
        unlabeled = replace(
            declared,
            onsets=tuple(replace(onset, stratum=None) for onset in declared.onsets),
        )
        built = syllabifier(unlabeled, strictness="strict")
        assert len(built.language.onsets) == len(declared.onsets)


class TestTheDeclaredModes:
    """``mode`` names a derivation this module implements, so the code owns it.

    That makes it the one vocabulary here the data does not declare, and the
    grammar enumerating it was a copy of the branch names -- one that could
    only ever refuse a declaration read off disk, never one built in memory.
    """

    def test_every_shipped_declaration_uses_a_declared_mode(self) -> None:
        used = {language(name).mode for name in languages()}
        assert used == MODES, f"shipped modes {sorted(used)} against {sorted(MODES)}"

    def test_an_unknown_mode_is_refused_and_named(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="quantal"):
            _declared(
                tmp_path,
                """
<syllabification language="test" version="1" mode="quantal" provenance="test">
  <nucleus span="[vowel]" /><onset span="s t" />
</syllabification>""",
            )


def test_a_rule_reads_the_syllable_tier_the_producer_wrote(tmp_path: Path) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[-vowel]" />
</syllabification>""",
    )
    stated = syllabifier(declaration)("ata")

    short = parse("t -> tʰ / <syllable _").rewrite(stated.form)[0]
    long = parse("t -> tʰ / . _").rewrite(Form.parse(stated.marks()))[0]

    assert stated.form.to_ipa() == "ata"
    assert stated.marks() == "a.ta"
    assert short.to_ipa() == "atʰa"
    assert long.to_ipa() == "a.tʰa"
    assert long.without_boundaries().to_ipa() == short.to_ipa()


def test_an_internal_expansion_carries_the_margin_to_the_next_rule(
    tmp_path: Path,
) -> None:
    declaration = _declared(
        tmp_path,
        """
<syllabification language="test" version="1" mode="constraints" provenance="test">
  <nucleus span="[vowel]" /><onset span="[-vowel]" />
</syllabification>""",
    )
    stated = syllabifier(declaration)("ata").form

    derived = RuleSet.parse("a -> ai / # _\nt -> tʰ / <syllable _").derive(stated)

    assert derived.result == "aitʰa"
    assert [(span.start, span.end) for span in derived.intervals] == [(0, 2), (2, 4)]
