"""Executable exit gates for the corpus query language."""

from pathlib import Path

import ipakit
import pytest
from ipakit import corpus


@pytest.mark.parametrize(
    "source,text,wanted",
    [
        ("[+nasal] / [vowel] _ [vowel]", "ana", ["n"]),
        ("t / _ #", "at", ["t"]),
        ("[vowel, height=close]", "ita", ["i"]),
        ("a / * _ #", "na", ["a"]),
        ("a{stress=primary}", "aˈã", ["ˈã"]),
        ("a{+nasalized}", "aã", ["ã"]),
        ("t{release=no-audible}", "tt̚", ["t̚"]),
        ("n{place=α}", "nm", ["n"]),
    ],
)
def test_every_documented_dsl_example_parses_and_matches(source, text, wanted):
    parsed = corpus.parse_query(source)
    assert parsed.target is not None
    assert [match.text for match in corpus.find(text, parsed)] == wanted


@pytest.mark.parametrize(
    "source,position,fragment",
    [
        ("*", 0, "bare '*'"),
        ("a{}", 0, "empty brace"),
        ("a{vowel}", 0, "non-feature"),
        ("V", 0, "spells nothing"),
        ("ab", 0, "names 2 units"),
    ],
)
def test_malformed_queries_report_the_offending_position(source, position, fragment):
    with pytest.raises(corpus.QueryParseError) as caught:
        corpus.parse_query(source)
    assert caught.value.position == position
    assert str(caught.value).count(f"position {position}") == 1
    assert fragment in str(caught.value)


def test_removed_vocabulary_aliases_point_at_declared_spellings():
    with pytest.raises(corpus.QueryParseError) as caught:
        corpus.parse_query("[+high]")
    assert "height=close" in str(caught.value)
    with pytest.raises(corpus.QueryParseError) as caught:
        corpus.parse_query("V")
    assert "feature query for a class" in str(caught.value)


def test_braces_are_a_conjunction_and_a_literal_is_exact():
    assert [m.text for m in corpus.find("ˈã", "a{stress=primary}")] == ["ˈã"]
    assert list(corpus.find("ˈã", "ˈa")) == []
    assert corpus.parse_query("a{stress=primary}").target.brace_base is True
    assert corpus.parse_query("ˈa").target.brace_base is False


def test_wild_normalization_skips_feature_bundles():
    wild = corpus.parse_query("[channel=grooved]", wild=True)
    exact = corpus.parse_query("[channel=grooved]")
    assert wild == exact
    assert [match.text for match in corpus.find("sa", wild)] == ["s"]


def test_wild_normalization_changes_literals_but_not_brace_constraints():
    assert corpus.parse_query("g", wild=True) == corpus.parse_query("ɡ")
    assert corpus.parse_query("g{+voiced}", wild=True) == corpus.parse_query(
        "ɡ{+voiced}"
    )


def test_bindings_paths_and_offsets_are_complete():
    bound = next(corpus.find("n", "n{place=α}"))
    assert bound.bindings == (("α", "alveolar"),)
    run = next(corpus.find("a#.b", "."))
    assert run.text == "#."
    assert len(run.paths) == 2
    assert all(path.startswith("/clock/") for path in run.paths)
    assert run.offset == str(ipakit.read("a#.b")).index(run.text)


def test_form_and_corpus_doors_return_the_same_match(tmp_path: Path):
    form = ipakit.read("an")
    direct = list(corpus.find(form, "[nasal]"))
    stored = corpus.create(tmp_path / "speech")
    stored.add("one", {}, {"broad": form})
    collected = list(corpus.query(stored, "[nasal]", role="broad"))
    assert [item.match for item in collected] == direct
    assert [(item.fileid, item.role) for item in collected] == [("one", "broad")]


def test_query_rule_is_the_rule_notation_constructor():
    assert corpus.query_rule("n / _ p", "m") == ipakit.rules.parse("n -> m / _ p")


def test_corpus_document_is_checked_by_the_handwritten_example_harness():
    root = Path(__file__).resolve().parent.parent
    harness = (root / "scripts" / "docexamples.py").read_text(encoding="utf-8")
    document = (root / "docs" / "corpus.md").read_text(encoding="utf-8")
    assert 'rglob("*.md")' in harness
    assert '[(m.fileid, m.text) for m in matches]  # [("one", "n")]' in document
