"""The quotation check: what it must catch, and what it must not call a fault.

``scripts/docquotes.py`` reads the sentences one document quotes out of
another and asserts they are still there. It is a guard, so what is
tested here is the *shape* of the mistake it exists to catch and the
shape of the ordinary practice it must let through -- not the quotations
that happen to be in the tree today. A list of those would document the
present and catch nothing.

Two of these matter more than the rest. A guard that silently matches
nothing passes every document, which is the failure ``docs/reviewing.md``
names first, so one test perturbs a real quotation and requires a report,
and another points the check at a tree with nothing in it and requires a
complaint rather than a pass.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# scripts/ is not a package -- the same reach tests/test_notebook.py makes.
sys.path.insert(0, str(ROOT / "scripts"))

import docquotes  # noqa: E402


def write(root: Path, **pages: str) -> Path:
    """A little tree of documents, named by keyword."""
    for stem, body in pages.items():
        (root / f"{stem}.md").write_text(body, encoding="utf-8")
    return root


def cited(root: Path, page: str = "quoting") -> list[tuple[int, str, Path]]:
    tree = docquotes.documents(root)
    found, _ = docquotes.citations(root / f"{page}.md", root, tree)
    return found


def verdict(root: Path, page: str = "quoting") -> list[bool]:
    """For each quotation on the page, whether the source still has it."""
    return [
        docquotes.appears(
            docquotes.normalize(quote),
            docquotes.normalize(target.read_text(encoding="utf-8")),
        )
        for _, quote, target in cited(root, page)
    ]


# --------------------------------------------------------------------------
# The mistake it exists to catch


def test_a_reworded_source_fails_the_quotation(tmp_path: Path) -> None:
    write(
        tmp_path,
        source="The rule fires at the left edge and nowhere else.\n",
        quoting='[source](source.md) says *"the rule fires at the right edge"*.\n',
    )
    assert verdict(tmp_path) == [False]


def test_the_same_quotation_passes_when_the_source_still_says_it(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        source="The rule fires at the left edge and nowhere else.\n",
        quoting='[source](source.md) says *"the rule fires at the left edge"*.\n',
    )
    assert verdict(tmp_path) == [True]


def test_one_changed_word_is_a_finding(tmp_path: Path) -> None:
    """Not a similarity score. A different word is a different sentence."""
    write(
        tmp_path,
        source="A boundary carries no prosody for anything to inherit.\n",
        quoting=(
            "[source](source.md): "
            '*"a boundary carries no prosody for anyone to inherit"*.\n'
        ),
    )
    assert verdict(tmp_path) == [False]


# --------------------------------------------------------------------------
# The copy-editing a citation is allowed


def test_a_sentence_initial_capital_may_be_lowered(tmp_path: Path) -> None:
    """The correction that made this check worth writing carefully.

    ``A target is one Pattern`` opens a sentence in the source and is
    quoted mid-sentence, so it is lowercased to fit. That is ordinary
    practice, not a misquotation.
    """
    write(
        tmp_path,
        source="A target is one `Pattern`, so `ab -> ba` is refused.\n",
        quoting='the sentence in [source](source.md) — "a target is one '
        '`Pattern`" — understates it.\n',
    )
    assert verdict(tmp_path) == [True]


def test_a_lowercase_word_may_be_raised_to_open_a_sentence(tmp_path: Path) -> None:
    write(
        tmp_path,
        source="so only a hand-made boundary reaches the fallback.\n",
        quoting='[source](source.md) is plain: *"Only a hand-made boundary '
        'reaches the fallback"*.\n',
    )
    assert verdict(tmp_path) == [True]


def test_case_folding_reaches_the_first_character_and_no_further(
    tmp_path: Path,
) -> None:
    """Blanket case-insensitivity would let a real misquotation through."""
    write(
        tmp_path,
        source="A target is one Pattern, so the scan advances by one.\n",
        quoting='[source](source.md) says "a target is one pattern".\n',
    )
    assert verdict(tmp_path) == [False]


def test_a_quotation_cut_at_a_clause_may_close_with_a_period(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        source="A margin-conditioned rule does not fire there: it guesses nothing.\n",
        quoting='[source](source.md) states the policy: *"a margin-conditioned '
        'rule does not fire there."*\n',
    )
    assert verdict(tmp_path) == [True]


def test_a_nested_quotation_may_be_retypographed(tmp_path: Path) -> None:
    """``"`` inside ``"`` does not nest, so a citation restyles it."""
    write(
        tmp_path,
        source='A variable over a "whole segment" is not a term.\n',
        quoting="[source](source.md) says: *\"a variable over a 'whole segment' "
        'is not a term"*.\n',
    )
    assert verdict(tmp_path) == [True]


def test_emphasis_and_code_spans_are_not_part_of_the_sentence(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        source="It is a variable over a *segment*, and there is no such `term`.\n",
        quoting='[source](source.md): *"it is a variable over a segment, and '
        'there is no such term"*.\n',
    )
    assert verdict(tmp_path) == [True]


def test_an_ellipsis_elides_what_the_citation_skipped(tmp_path: Path) -> None:
    write(
        tmp_path,
        source="The scan resumes past each site, which costs nothing, and a "
        "target is one term.\n",
        quoting='[source](source.md): *"the scan resumes past each site… and a '
        'target is one term"*.\n',
    )
    assert verdict(tmp_path) == [True]


def test_a_hard_wrapped_quotation_still_reads_as_one_sentence(
    tmp_path: Path,
) -> None:
    """``README.md`` and ``docs/releasing.md`` are wrapped; the design docs are not."""
    write(
        tmp_path,
        source="The scan resumes past each site and a target is one term.\n",
        quoting='[source](source.md) says *"the scan resumes past each\nsite '
        'and a target is one term"*.\n',
    )
    assert verdict(tmp_path) == [True]


# --------------------------------------------------------------------------
# Who a quotation is attributed to


def test_a_quotation_binds_to_the_nearest_document_named_before_it(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        one="Alpha holds at the left edge.\n",
        two="Beta holds at the right edge.\n",
        quoting="[one](one.md), and then [two](two.md), say "
        '*"beta holds at the right edge"*.\n',
    )
    ((_, _, target),) = cited(tmp_path)
    assert target.name == "two.md"


def test_an_attribution_does_not_reach_back_past_its_own_sentence(
    tmp_path: Path,
) -> None:
    """The paragraph is the wrong window.

    A page names a sibling, finishes that thought, and then quotes a
    handout or a docstring in the next sentence. Binding by paragraph
    hands the second quotation to the first sentence's source and reports
    a misquotation that nobody made.
    """
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting="The sentence in [source](source.md) understates it. The "
        "promise is a docstring's: *\"every non-overlapping position where "
        'this environment holds."*\n',
    )
    assert cited(tmp_path) == []


def test_a_document_named_in_prose_attributes_as_a_link_does(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        source="A margin-conditioned rule does not fire there.\n",
        quoting='`source.md` states the policy it fails on: *"a '
        'margin-conditioned rule does not fire there"*.\n',
    )
    ((_, _, target),) = cited(tmp_path)
    assert target.name == "source.md"


def test_a_quotation_attributed_to_nothing_is_left_alone(tmp_path: Path) -> None:
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting='Hayes writes *"braces express disjunctions of a kind"*.\n',
    )
    assert cited(tmp_path) == []


def test_a_quotation_attributed_outside_the_tree_is_left_alone(
    tmp_path: Path,
) -> None:
    """*SPE* and a lecture handout cannot be read, and this does not pretend to."""
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting="The [2020 handout](https://example.invalid/notes.md) corrects "
        'it: *"rules from the same schema apply conjunctively"*.\n',
    )
    assert cited(tmp_path) == []


def test_an_ambiguous_name_is_not_guessed_at(tmp_path: Path) -> None:
    """Two documents of one name, named by that name and no path."""
    for stem in ("one", "two"):
        (tmp_path / stem).mkdir()
        (tmp_path / stem / "notes.md").write_text(
            f"{stem.title()} holds at its own edge.\n", encoding="utf-8"
        )
    (tmp_path / "quoting.md").write_text(
        '`notes.md` says *"one holds at its own edge"*.\n', encoding="utf-8"
    )
    assert cited(tmp_path) == []


def test_a_bibliographic_citation_outranks_a_document_named_alongside(
    tmp_path: Path,
) -> None:
    """A page reporting the literature is not quoting its sibling.

    ``source.md`` is named in the sentence, but the quotation carries its
    own attribution -- an author, a year, a page -- and the words are
    Janda's, who is not a document in this tree.
    """
    write(
        tmp_path,
        source="Alpha holds at the left edge.\n",
        quoting="The same source `source.md` quotes reports the objection: "
        '*"a Pandora\'s box of implausible-seeming processes"* '
        "(Janda 1984: 92, quoted by Hume).\n",
    )
    assert cited(tmp_path) == []


def test_the_same_sentence_without_a_citation_is_still_checked(
    tmp_path: Path,
) -> None:
    """The release is the citation's doing and nothing else's.

    Word for word the sentence above, with the parenthetical dropped. If
    this ever passes, the rule stopped being about attribution.
    """
    write(
        tmp_path,
        source="Alpha holds at the left edge.\n",
        quoting="The same source `source.md` quotes reports the objection: "
        '*"a Pandora\'s box of implausible-seeming processes"*.\n',
    )
    assert verdict(tmp_path) == [False]


def test_a_citation_inside_the_quoted_words_attributes_nothing(
    tmp_path: Path,
) -> None:
    """The source citing its own sources is not this page's attribution."""
    write(
        tmp_path,
        source="Webb (1974) claims metathesis is not synchronic.\n",
        quoting='`source.md` says *"Webb (1974) claims metathesis is not '
        'diachronic"*.\n',
    )
    assert verdict(tmp_path) == [False]


def test_a_citation_does_not_release_the_next_sentence(tmp_path: Path) -> None:
    """A citation reaches its own sentence, the same window a link gets."""
    write(
        tmp_path,
        source="Alpha holds at the left edge.\n",
        quoting="Hume records the objection (Janda 1984: 92). But "
        '`source.md` says *"alpha holds at the right edge"*.\n',
    )
    assert verdict(tmp_path) == [False]


def test_a_phrase_in_italics_is_not_read_as_a_quotation(tmp_path: Path) -> None:
    """Quotation marks mean the source's words, and nothing else does.

    A contrast frame built from the author's own coined phrases wears
    italics, so neither phrase claims to be the sibling's wording.
    """
    write(
        tmp_path,
        source="The rules are waiting on a notation.\n",
        quoting="It turns [source](source.md)'s twelve rules from *waiting on "
        "structure nobody can supply* into *waiting on a rule set the caller "
        "may compose in*.\n",
    )
    assert cited(tmp_path) == []


def test_a_list_item_does_not_claim_the_next_one(tmp_path: Path) -> None:
    """One line per paragraph *or bullet*; a list runs with no blank lines."""
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting="- [source](source.md) is the reference.\n"
        '- A variable is not `"a copy of whatever consonant stood there"`.\n'
        '- And *"a copy of whatever consonant stood there"* is not a term.\n',
    )
    assert cited(tmp_path) == []


def test_a_fenced_block_is_code_and_not_prose(tmp_path: Path) -> None:
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting="[source](source.md) is the reference.\n\n"
        '```python\nsegment("a")  # "beta holds and nothing else"\n```\n',
    )
    assert cited(tmp_path) == []


def test_a_short_run_in_quotes_is_a_mention_not_a_citation(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        source="Alpha holds.\n",
        quoting='[source](source.md) makes "non-overlapping" a property.\n',
    )
    assert cited(tmp_path) == []


# --------------------------------------------------------------------------
# The sweep cannot go vacuous


def test_the_tree_is_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert docquotes.main([str(ROOT)]) == 0
    assert "every quotation is in the document it cites" in capsys.readouterr().out


def test_perturbing_a_real_quotation_is_reported(tmp_path: Path) -> None:
    """The check run against the real documents, with one word moved.

    A guard is only worth its exit status if it fails when it should, on
    the corpus it actually guards.
    """
    copy = tmp_path / "docs"
    shutil.copytree(ROOT / "docs", copy)
    tree = docquotes.documents(tmp_path)
    moved = 0
    for path in tree:
        found, _ = docquotes.citations(path, tmp_path, tree)
        for _, quote, target in found:
            body = target.read_text(encoding="utf-8")
            words = quote.split()
            hinge = words[len(words) // 2]
            target.write_text(body.replace(hinge, hinge + "x"), encoding="utf-8")
            moved += 1
            break
        if moved:
            break
    assert moved, "no quotation in docs/ to perturb; the sweep found nothing"
    assert docquotes.main([str(tmp_path), "--floor", "0", "--cited-floor", "0"]) == 1


def test_a_tree_with_no_quotations_complains_rather_than_passes(
    tmp_path: Path,
) -> None:
    (tmp_path / "quiet.md").write_text("Nothing is quoted here.\n", encoding="utf-8")
    assert docquotes.main([str(tmp_path)]) == 1


def test_the_floors_are_below_what_the_tree_holds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A floor above the corpus fails every run; one at zero guards nothing."""
    assert docquotes.main([str(ROOT)]) == 0
    lines = capsys.readouterr().out.splitlines()
    checked = int(next(line for line in lines if "checked against" in line).split()[0])
    read = checked + int(
        next(line for line in lines if "attributed to something" in line).split()[0]
    )
    assert 0 < docquotes.CITED_FLOOR <= checked
    assert 0 < docquotes.FLOOR <= read
