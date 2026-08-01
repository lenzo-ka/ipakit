"""The calculus over the string set: ``A ~> B`` and what it derives.

``docs/calculus.md`` states the algebra. This file is the measurement
behind every number on that page, in the shape ``docs/reviewing.md``
asks for: sweeps over generated input with the corpus size asserted, and
the escapes pinned so a limit changes deliberately rather than quietly.

Four claims carry the rest, and each has a class of its own.

**The two entry points cannot drift apart.** ``variants(f)[0].form`` is
``apply(f)`` by construction -- the empty subset is enumerated first --
so the additive feature cannot silently change the answer the existing
one gives. Swept over every shipped set and every corpus word.

**Composition is concatenation, and it is associative.** Applying B to
A's output set equals applying ``A ++ B``. Proved by the fold argument
and measured anyway, because the argument has a gap: the internal fold
carries ``Unit`` sequences while the external composition carries
strings that are read back, and only a sweep can say those agree.

**The set is finite, insertion included.** A rule is matched against a
snapshot, so it cannot feed itself and each step is finite. Insertion
lengthens what the *next* rule scans, which is what makes the bound
doubly exponential rather than exponential -- measured on an adversarial
set rather than argued.

**The cap is the one place the algebra stops.** A bounded enumeration
cannot be a homomorphism, and the counterexample is pinned here rather
than left as a caveat. Everything else on the page holds of a complete
answer and none of it holds of a truncated one, which is why
``VariantSet.complete`` exists -- and the implication that makes it worth
asking, that a complete answer holds every form the uncapped one does, is
swept here rather than left to the construction that gives it.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
import warnings
from pathlib import Path

import ipakit
import pytest
from ipakit import rules as R
from ipakit.form import spell, units

FEATURES = ipakit.load_ipa_features()
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _quiet():  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield


def _set(text: str) -> R.RuleSet:
    return R.RuleSet.parse(text, FEATURES)


def _cat(*sets: R.RuleSet) -> R.RuleSet:
    """Concatenation, which is the composition of the maps they induce."""
    return R.RuleSet(rules=tuple(rule for one in sets for rule in one.rules))


def _forms(alphabet: str, lengths: tuple[int, ...]) -> list[str]:
    """Every form over ``alphabet`` that spells itself back.

    The sweep corpus for this file. Generated rather than named, on
    tests/corpus.py's predicate (a form belongs if it re-spells), but
    over rule-sized strings rather than single units -- the question here
    is about cascades, and a one-unit corpus cannot ask it.
    """
    out = []
    for size in lengths:
        for combo in itertools.product(alphabet, repeat=size):
            form = "".join(combo)
            if spell(list(units(form, FEATURES))) == form:
                out.append(form)
    return sorted(set(out))


def _exhaust(cascade: R.RuleSet, form: str) -> dict[str, int]:
    """Every form the cascade derives, and the fewest choices reaching it.

    The oracle the cost claims are measured against, written the long
    way round: no cap, no dedupe between steps, every subset of every
    rule's edits from every state it is handed, and the minimum taken
    only at the end. It shares nothing with the engine but the matcher,
    so agreement is evidence rather than a tautology -- in particular it
    knows nothing about the order the engine enumerates in, which is
    what both cost claims are about.

    Exponential in the sites, deliberately. Small cascades and short
    forms only, and the sweeps that use it say how many they ran.
    """
    states = [(list(units(form, FEATURES)), 0)]
    for rule in cascade.rules:
        onward = []
        for items, cost in states:
            found = rule.edits(items, FEATURES)
            if not rule.optional:
                onward.append((R._apply_edits(list(items), found), cost))
                continue
            for size in range(len(found) + 1):
                for subset in itertools.combinations(range(len(found)), size):
                    picked = [found[i] for i in subset]
                    onward.append((R._apply_edits(list(items), picked), cost + size))
        states = onward
    cheapest: dict[str, int] = {}
    for items, cost in states:
        for rule in R.surface(FEATURES):
            items = R._apply_edits(list(items), rule.edits(items, FEATURES))
        spelled = spell(items)
        cheapest[spelled] = min(cheapest.get(spelled, cost), cost)
    return cheapest


#: The rules the composition sweeps draw from. Deliberately mixed:
#: substitution, insertion, deletion, a feature change, a prosodic
#: change, a boundary write, and both arrows -- the composition claim is
#: about every rule kind, and a pool of substitutions would prove it of
#: the easiest one.
POOL = (
    "a ~> e / _ t ; raise",
    "t ~> ʔ / _ # ; glottal",
    "∅ ~> ə / t _ t ; epenthesis",
    "t -> ɾ / [vowel] _ [vowel] ; tapping",
    "ə ~> ∅ / [vowel] [-vowel] _ [-vowel] [vowel] ; caduc",
    "[vowel] ~> [length=long] / _ # ; lengthening",
    "∅ ~> t / [-vowel] _ ; growth",
    "e -> a ; lowering",
    "t ~> ∅ / a _ ; loss",
    "∅ ~> . / [vowel] _ [-vowel] ; syllabification",
)

RULES = tuple(R.parse(text, FEATURES) for text in POOL)

#: A second pool, for the claims about cost. Every rule here can be
#: reached another way round -- a is raised to e directly and also
#: through schwa, a t is glottalled by two rules with different
#: environments -- so a form is routinely derived twice at two different
#: prices. A pool of rules that never converge cannot ask which of two
#: derivations a member reports, because there is never more than one.
CONVERGENT = (
    "a ~> e ; straight",
    "a ~> ə ; halfway",
    "ə ~> e ; onward",
    "t ~> ʔ ; stop",
    "t ~> ʔ / _ # ; final stop",
    "∅ ~> t / [-vowel] _ ; growth",
    "t ~> ∅ ; loss",
    "e ~> a ; back",
)

#: The shipped set that carries the optional half.
FRENCH = R.shipped("french-liaison", FEATURES)

#: Big enough that a cap cannot fire on the sweeps, so they measure the
#: algebra and not the bound. Where the bound is the subject, it is named
#: in the test.
UNBOUNDED = 10**9


# --------------------------------------------------------------------------
# The notation
# --------------------------------------------------------------------------


class TestTheOptionalArrow:
    @pytest.mark.parametrize("arrow", R.ARROWS)
    def test_a_plain_arrow_is_obligatory(self, arrow: str) -> None:
        assert R.parse(f"a {arrow} e", FEATURES).optional is False

    @pytest.mark.parametrize("arrow", R.OPTIONAL_ARROWS)
    def test_every_optional_spelling_parses_as_optional(self, arrow: str) -> None:
        """Including the three that contain a plain arrow.

        '~=>' contains '=>' and '~->' contains '->', so a parser that
        asks the plain arrows first reads every one of these as an
        obligatory rule with a stray '~' on the left.
        """
        rule = R.parse(f"a {arrow} e", FEATURES)
        assert rule.optional is True
        assert R.RuleSet(rules=(rule,)).variants("at", FEATURES).forms == ("at", "et")

    def test_the_optional_spellings_are_derived_from_the_plain_ones(self) -> None:
        """Not a second list beside the first: '~' prefixed to each, plus
        the ASCII shorthand. A fourth arrow gets its optional counterpart
        without an edit, so the two cannot disagree about how many
        arrows there are."""
        assert set(R.OPTIONAL_ARROWS) == {
            R.OPTIONAL_MARK + arrow for arrow in R.ARROWS
        } | {R.OPTIONAL_MARK + ">"}

    def test_the_optional_mark_spells_nothing_the_inventory_declares(self) -> None:
        """The collision check, as a predicate over the declaration.

        A notation character has to spell nothing writable, or a rule
        naming it would mean two things. Asked of the data rather than
        against the list of characters that were notation when this was
        written.
        """
        mark = R.OPTIONAL_MARK
        assert mark not in FEATURES.phones
        assert not [p for p in FEATURES.phones if mark in p]
        assert mark not in FEATURES.diacritics
        assert mark not in FEATURES.separators
        assert mark not in FEATURES.zeros
        assert mark not in R._boundary_spellings(FEATURES)
        assert mark != R.ANY_BOUNDARY and mark != R.NAME_SEP
        assert mark not in R.NULL
        # And it does not survive a read, so it cannot reach a form either.
        assert [u.text for u in units(f"a{mark}b", FEATURES)] == ["a", "b"]
        assert mark not in (ROOT / "ipakit" / "data" / "ipa.xml").read_text(
            encoding="utf-8"
        )

    def test_the_mark_alone_is_not_an_arrow_and_says_so(self) -> None:
        with pytest.raises(R.RuleError, match="marks an arrow optional"):
            R.parse("a ~ e", FEATURES)

    def test_a_rule_name_may_contain_the_mark(self) -> None:
        """The name is partitioned off before the arrow is looked for, so
        a '~' past the ';' never reaches this decision."""
        rule = R.parse("a -> e ; raising ~ lowering", FEATURES)
        assert rule.optional is False
        assert rule.name == "raising ~ lowering"


# --------------------------------------------------------------------------
# Per site, not per rule
# --------------------------------------------------------------------------


class TestOptionalityIsPerSite:
    """The decision the whole feature turns on.

    Rule-level optionality bounds the answer at 2**rules and is cheap;
    site-level bounds it at 2**sites and is the one French needs. A
    regression to rule-level would give two variants here, not four, and
    would still look like a working feature.
    """

    def test_two_sites_give_four_variants(self) -> None:
        got = _set("t ~> ʔ").variants("tat", FEATURES)
        assert got.forms == ("tat", "ʔat", "taʔ", "ʔaʔ")

    @pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6])
    def test_n_sites_give_two_to_the_n(self, count: int) -> None:
        got = _set("[vowel] ~> [length=long]").variants("a" * count, FEATURES)
        assert len(got) == 2**count
        assert got.complete

    def test_the_shipped_french_set_needs_it(self) -> None:
        """'devenir' is the classical demonstration: three of the four
        combinations are French and the fourth is not."""
        assert FRENCH.variants("dəvəniʁ", FEATURES).forms == (
            "dəvəniʁ",
            "dəvniʁ",
            "dvəniʁ",
        )


# --------------------------------------------------------------------------
# The obligatory half is untouched
# --------------------------------------------------------------------------


class TestTheFormToFormEntryPointsAreUnchanged:
    """The additive claim, made checkable rather than asserted."""

    @pytest.mark.parametrize("name", R.available())
    def test_the_first_variant_is_what_apply_answers(self, name: str) -> None:
        """Not agreement between two implementations -- construction. The
        empty subset is the first thing enumerated at every optional
        rule, so the citation form is the first branch by definition."""
        from tests.test_rule_sets import CORPUS

        rule_set = R.shipped(name, FEATURES)
        words = CORPUS[name]
        assert len(words) >= 15, f"corpus for {name} is only {len(words)} words"
        for word in words:
            got = rule_set.variants(word, FEATURES)
            assert got.forms[0] == rule_set.apply(word, FEATURES), word
            assert got.variants[0].choices == 0, word

    def test_an_optional_rule_does_not_fire_under_rewrite(self) -> None:
        assert ipakit.rewrite("kæt", "t ~> ʔ / _ #") == "kæt"
        assert ipakit.rewrite("kæt", "t -> ʔ / _ #") == "kæʔ"

    def test_a_declined_choice_is_not_a_failed_environment(self) -> None:
        """A trace that spelled the two alike would be the first silent
        wrong answer this feature could tell: 'no change' says the rule
        looked and found nothing."""
        taken = ipakit.derive("kæt", "t ~> ʔ / _ #")
        assert "(not taken)" in taken.trace(all_steps=True)
        missed = ipakit.derive("kæd", "t ~> ʔ / _ #")
        assert "(not taken)" in missed.trace(all_steps=True)
        plain = ipakit.derive("kæd", "t -> ʔ / _ #")
        assert "(no change)" in plain.trace(all_steps=True)
        assert [step.optional for step in taken.steps] == [True]
        assert [step.optional for step in plain.steps] == [False]

    def test_rule_apply_is_the_mechanism_and_ignores_optionality(self) -> None:
        """The pinned escape. ``Rule.apply`` is "apply this rule once" and
        goes on applying every edit; optionality is a fact about a
        derivation, and RuleSet is where derivations live. Everything
        public reaches a rule through a RuleSet, which is why this is a
        limit rather than a defect -- but it is a limit, so it is pinned
        and stays known rather than assumed shut.
        """
        rule = R.parse("t ~> ʔ / _ #", FEATURES)
        items, edits = rule.apply("kæt", FEATURES)
        assert spell(items) == "kæʔ"
        assert len(edits) == 1
        # The public spellings all take the choice, and take it the same way.
        assert ipakit.rewrite("kæt", rule) == "kæt"
        assert ipakit.derive("kæt", rule).result == "kæt"
        assert ipakit.variants("kæt", rule).forms == ("kæt", "kæʔ")

    def test_a_set_with_no_optional_rule_has_exactly_one_variant(self) -> None:
        from tests.test_rule_sets import CORPUS

        checked = 0
        for name in R.available():
            rule_set = R.shipped(name, FEATURES)
            if rule_set.optional:
                continue
            for word in CORPUS[name]:
                got = rule_set.variants(word, FEATURES)
                assert got.forms == (rule_set.apply(word, FEATURES),), word
                checked += 1
        assert checked > 100, "sweep did not run"


# --------------------------------------------------------------------------
# Closure, identity, composition, associativity
# --------------------------------------------------------------------------


def _externally(form: str, first: R.RuleSet, second: R.RuleSet) -> tuple[str, ...]:
    """``second`` applied to ``first``'s answer, deduped in order.

    The composition a *caller* writes, as opposed to the one the fold
    performs. That the two agree is the claim.
    """
    seen: dict[str, None] = {}
    for variant in first.variants(form, FEATURES, limit=UNBOUNDED):
        for onward in second.variants(variant.form, FEATURES, limit=UNBOUNDED):
            seen.setdefault(onward.form, None)
    return tuple(seen)


class TestTheEmptyRuleSetIsTheIdentity:
    def test_it_maps_every_form_to_itself(self) -> None:
        empty = _set("")
        assert len(empty) == 0
        corpus = _forms("ate", (1, 2, 3))
        assert len(corpus) > 30, "sweep did not run"
        for form in corpus:
            # Identity up to the read, which is Derivation.start's caveat
            # and not a new one.
            assert empty.variants(form, FEATURES).forms == (
                spell(list(units(form, FEATURES))),
            )

    def test_it_is_a_two_sided_identity_for_concatenation(self) -> None:
        empty = _set("")
        corpus = _forms("ate", (2, 3, 4))
        assert len(corpus) > 100, "sweep did not run"
        checked = 0
        for rule in RULES:
            one = R.RuleSet(rules=(rule,))
            for form in corpus:
                want = one.variants(form, FEATURES, limit=UNBOUNDED).forms
                assert (
                    _cat(empty, one).variants(form, FEATURES, UNBOUNDED).forms == want
                )
                assert (
                    _cat(one, empty).variants(form, FEATURES, UNBOUNDED).forms == want
                )
                checked += 1
        assert checked > 1000, "sweep did not run"


class TestApplyingToAnOutputSetIsConcatenation:
    """The claim a caller leans on, swept over every pair of the pool.

    Stronger than the algebra needs: the two agree in *order*, not only
    as sets, so a caller who splits a cascade gets an empty diff rather
    than an equivalent answer.
    """

    def test_the_sweep(self) -> None:
        corpus = _forms("atəe", (1, 2, 3, 4))
        pairs = list(itertools.combinations_with_replacement(range(len(RULES)), 2))
        assert len(corpus) > 200, "sweep did not run"
        assert len(pairs) > 40, "sweep did not run"
        checked = 0
        set_equal = order_equal = 0
        disagreed: list[tuple[str, str, str]] = []
        for i, j in pairs:
            first = R.RuleSet(rules=(RULES[i],))
            second = R.RuleSet(rules=(RULES[j],))
            joined = _cat(first, second)
            for form in corpus:
                fold = joined.variants(form, FEATURES, limit=UNBOUNDED)
                assert fold.complete, "the bound fired; this sweep measures the algebra"
                split = _externally(form, first, second)
                checked += 1
                if set(fold.forms) == set(split):
                    set_equal += 1
                else:
                    disagreed.append((POOL[i], POOL[j], form))
                if fold.forms == split:
                    order_equal += 1
        assert checked > 5000, f"sweep did not run: {checked}"
        assert set_equal == checked, disagreed[:5]
        assert order_equal == checked, "the orders diverged"


class TestConcatenationIsAssociative:
    def test_three_rule_sets_agree_however_they_are_bracketed(self) -> None:
        corpus = _forms("ate", (2, 3))[:40]
        assert len(corpus) >= 30, "sweep did not run"
        pool = RULES[:6]
        checked = 0
        for i, j, k in itertools.product(range(len(pool)), repeat=3):
            a, b, c = (R.RuleSet(rules=(pool[x],)) for x in (i, j, k))
            for form in corpus:
                left = _externally(form, _cat(a, b), c)
                right = _externally(form, a, _cat(b, c))
                fold = _cat(a, b, c).variants(form, FEATURES, limit=UNBOUNDED).forms
                assert left == right == fold, (POOL[i], POOL[j], POOL[k], form)
                checked += 1
        assert checked > 5000, f"sweep did not run: {checked}"


class TestTheCapIsWhereTheAlgebraStops:
    """The counterexample, pinned rather than left as a caveat.

    ``limit`` is a bound per *call*, so splitting a cascade into two
    calls doubles the budget. A bounded enumeration cannot be a
    homomorphism, and this is what that costs -- which is the whole
    reason ``complete`` is on the answer and not in a log line.
    """

    LONG = "[vowel] ~> [length=long] ; long"
    GLOT = "t ~> ʔ ; glottal"

    def test_uncapped_the_two_agree(self) -> None:
        first, second = _set(self.LONG), _set(self.GLOT)
        joined = _cat(first, second).variants("atatata", FEATURES, limit=UNBOUNDED)
        assert joined.complete
        assert len(joined) == 128
        assert joined.forms == _externally("atatata", first, second)

    def test_capped_they_do_not_and_the_answer_says_so(self) -> None:
        first, second = _set(self.LONG), _set(self.GLOT)
        joined = _cat(first, second).variants("atatata", FEATURES, limit=8)
        split = {
            onward.form
            for variant in first.variants("atatata", FEATURES, limit=8)
            for onward in second.variants(variant.form, FEATURES, limit=8)
        }
        assert len(joined) == 8
        assert len(split) == 64
        assert set(joined.forms) != split
        # And the caller can tell, without comparing anything.
        assert joined.complete is False
        assert joined.truncated is True
        assert joined.unexplored > 0


# --------------------------------------------------------------------------
# Finiteness
# --------------------------------------------------------------------------


class TestTheSetIsAlwaysFinite:
    """Insertion is the case worth checking, and it is the adversarial one.

    A rule cannot feed itself, so a pass terminates; but an insertion
    lengthens the form the *next* rule scans, so the bound compounds.
    Measured rather than argued, because "it terminates" and "it
    terminates before the heat death" are different claims.
    """

    #: Each rule inserts a consonant after every consonant, so the next
    #: rule finds twice as many sites. The worst shape the notation can
    #: express with a bounded number of rules.
    ADVERSARIAL = "∅ ~> t / [-vowel] _ ; epenthesis {}"

    @pytest.mark.parametrize(
        "rules,variants,longest", [(1, 4, 4), (2, 16, 8), (3, 64, 16)]
    )
    def test_insertion_plus_optionality_is_finite_and_doubly_exponential(
        self, rules: int, variants: int, longest: int
    ) -> None:
        cascade = _set(
            "\n".join(self.ADVERSARIAL.format(i) for i in range(1, rules + 1))
        )
        got = cascade.variants("pk", FEATURES, limit=UNBOUNDED)
        assert got.complete
        assert len(got) == variants, "4 ** k, so the growth claim moved"
        assert max(len(form) for form in got.forms) == longest, "2 ** (k+1)"

    def test_an_insertion_rule_still_cannot_feed_itself(self) -> None:
        """The property finiteness rests on, restated for the optional
        path: one rule, one pass, against a snapshot."""
        got = _set(self.ADVERSARIAL.format(1)).variants("p", FEATURES)
        assert got.forms == ("p", "pt")

    def test_a_deleting_optional_rule_terminates_too(self) -> None:
        got = _set("[-vowel] ~> ∅").variants("ptk", FEATURES)
        assert got.complete and len(got) == 8
        assert "" in got.forms, "deleting every site is a member like any other"


# --------------------------------------------------------------------------
# The cap, and how a caller sees it
# --------------------------------------------------------------------------


class TestTheCapIsReportedAndNotLogged:
    def test_a_complete_answer_says_so_and_carries_no_truncation(self) -> None:
        got = _set("[vowel] ~> [length=long]").variants("aaa", FEATURES)
        assert got.complete and not got.truncated
        assert got.truncations == ()
        assert got.unexplored == 0
        assert got.limit == R.DEFAULT_LIMIT

    def test_a_cut_answer_names_the_rule_and_counts_what_it_missed(self) -> None:
        got = _set("[vowel] ~> [length=long] ; lengthening").variants(
            "aaaa", FEATURES, limit=4
        )
        assert len(got) == 4
        assert got.complete is False
        assert len(got.truncations) == 1
        cut = got.truncations[0]
        assert cut.step == 0
        assert cut.rule == "lengthening"
        assert cut.kept == 4
        # Exact, not estimated: one branch offering 2**4 subsets, of which
        # 4 were enumerated.
        assert cut.unexplored == 2**4 - 4 == 12
        assert got.unexplored == 12

    def test_a_cut_keeps_the_members_that_depart_least(self) -> None:
        """Grading the subsets by size is half of what makes this true.
        Counting in binary would enumerate every subset of a PREFIX of
        the sites and none of the rest, so the last site would never be
        seen to vary -- a biased sample dressed as a set.

        One rule over one branch is the half this case can see. The
        other half is that the grading has to run across branches too,
        and that is TestTheCutFallsOnTheDearestChoicesAnywhere.
        """
        got = _set("[vowel] ~> [length=long]").variants("aaaa", FEATURES, limit=5)
        assert got.forms == ("aaaa", "aːaaa", "aaːaa", "aaaːa", "aaaaː")
        assert [v.choices for v in got] == [0, 1, 1, 1, 1]

    def test_an_obligatory_rule_never_truncates(self) -> None:
        """It is a function, so it maps each branch to one child and can
        only ever carry forward what it was handed. Truncating one would
        drop a form that was already in the set."""
        cascade = _set("[vowel] ~> [length=long] ; long\nt -> ʔ ; glottal")
        got = cascade.variants("atatat", FEATURES, limit=6)
        assert [cut.rule for cut in got.truncations] == ["long"]

    def test_the_limit_must_admit_at_least_one_answer(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            _set("a ~> e").variants("a", FEATURES, limit=0)

    def test_a_limit_of_one_keeps_the_citation_form(self) -> None:
        got = _set("a ~> e").variants("aaa", FEATURES, limit=1)
        assert got.forms == ("aaa",)
        assert got.complete is False


class TestUnexploredCountsChoicesAndNotForms:
    """What the number is, pinned in both directions it is not.

    ``unexplored`` is the children the cut step declined to build. It is
    exact for that step and it is a floor under the cascade, and the
    reading it invites -- "this many forms are missing" -- is wrong
    either way round. A single-rule cascade cannot show that, because
    with one rule the step IS the cascade and the two numbers agree;
    that agreement is what let the upper-bound claim stand.
    """

    #: Two rules that each insert a consonant after every consonant, so
    #: the second finds twice the sites of the first. The same shape as
    #: the finiteness sweep, which is where the growth is measured.
    INSERT = "∅ ~> t / [-vowel] _ ; one\n∅ ~> t / [-vowel] _ ; two"

    def _missing(self, cascade: R.RuleSet, form: str, limit: int) -> int:
        cut = cascade.variants(form, FEATURES, limit=limit)
        whole = cascade.variants(form, FEATURES, limit=UNBOUNDED)
        assert whole.complete, "the oracle has to be the complete answer"
        return len(set(whole.forms) - set(cut.forms))

    def test_one_rule_is_the_case_where_the_two_numbers_agree(self) -> None:
        cascade = _set("[vowel] ~> [length=long]")
        got = cascade.variants("aaaa", FEATURES, limit=4)
        assert got.unexplored == 12
        assert self._missing(cascade, "aaaa", 4) == 12

    @pytest.mark.parametrize(
        "rules,form,limit,unexplored,missing",
        [
            ("a ~> b\nc ~> d", "aac", 1, 4, 7),
            ("a ~> b\nc ~> d", "aac", 2, 4, 6),
            ("a ~> b\nb ~> c\nc ~> d", "abc", 2, 8, 22),
            ("[vowel] ~> [length=long]\nt ~> ʔ", "atat", 3, 10, 13),
        ],
    )
    def test_a_cut_early_in_a_cascade_under_reports(
        self, rules: str, form: str, limit: int, unexplored: int, missing: int
    ) -> None:
        """Every branch the cut declined would have had children under
        every later rule, and none of those are counted. So the number
        is not an upper bound on the forms missing, and each of these
        cases is one where reading it as one would mislead by name."""
        cascade = _set(rules)
        got = cascade.variants(form, FEATURES, limit=limit)
        assert got.unexplored == unexplored
        assert self._missing(cascade, form, limit) == missing
        assert got.unexplored < missing

    def test_a_cut_over_convergent_choices_over_reports(self) -> None:
        """And it is not a lower bound on the forms missing either.
        Distinct choices spell one form, so a step can decline more
        combinations than there are forms left to lose."""
        cascade = _set(self.INSERT)
        got = cascade.variants("pk", FEATURES, limit=4)
        assert got.unexplored == 30
        assert self._missing(cascade, "pk", 4) == 12
        assert got.unexplored > 12

    def test_the_two_directions_are_the_same_cascade_at_two_depths(self) -> None:
        """Not two contrived rule sets: one cascade, cut at four, over
        and under reporting as it grows a rule."""
        rule = "∅ ~> t / [-vowel] _ ; epenthesis {}"
        seen = []
        for length in (2, 3, 4):
            cascade = _set("\n".join(rule.format(i) for i in range(1, length + 1)))
            got = cascade.variants("pk", FEATURES, limit=4)
            seen.append((got.unexplored, self._missing(cascade, "pk", 4)))
        assert seen == [(30, 12), (60, 60), (90, 252)]

    def test_swept_it_fails_in_both_directions(self) -> None:
        """A predicate over the pool rather than four chosen cases: for
        a truncated answer the count is positive, and it is sometimes
        above and sometimes below the number of forms lost. If either
        tally ever comes back zero this file is asserting a bound the
        library does not have."""
        corpus = _forms("ate", (2, 3))
        assert len(corpus) > 20, "sweep did not run"
        checked = over = under = 0
        for pair in itertools.combinations(range(len(POOL)), 2):
            cascade = _cat(*(_set(POOL[i]) for i in pair))
            for form in corpus:
                for limit in (1, 2, 3, 4):
                    got = cascade.variants(form, FEATURES, limit=limit)
                    if got.complete:
                        continue
                    checked += 1
                    assert got.unexplored > 0, "a cut that counts nothing"
                    missing = self._missing(cascade, form, limit)
                    over += got.unexplored > missing
                    under += got.unexplored < missing
        assert checked > 500, f"sweep did not run: {checked}"
        assert over > 0 and under > 0, (over, under)


class TestACompleteAnswerHoldsEveryForm:
    """The implication the whole page rests on, swept rather than argued.

    ``complete is True`` has to mean the answer is every form the same
    call answers uncapped -- otherwise every algebraic claim above is
    being checked against a sample of the set it names. It is true by
    construction, since a step that declines nothing carries forward
    what it was handed, and construction is exactly what the rest of
    this file has caught being wrong. So it is measured: capped against
    uncapped over cascades of one, two and three rules from the pool,
    every form of a generated corpus, at six limits.

    The converse is not asserted and must not be. ``complete is False``
    says a step declined a child, not that a form is missing, and the
    two part company because distinct derivations spell one
    pronunciation. That direction is pinned below on a named case, so
    that trading this safe imprecision for an unsafe precision fails
    here.
    """

    #: Small enough that a cut is common and large enough that a
    #: complete answer at the same limit is not rare.
    LIMITS = (1, 2, 3, 4, 6, 8)

    #: Two rules that spell one form from ``ab``, the second from the
    #: branch that declined the first.
    CONVERGE = "a ~> b ; one\na ~> b / _ b ; two"

    def _cascades(self) -> list[tuple[int, ...]]:
        """Every rule of the pool, every ordered pair, every triple.

        Ordered pairs rather than unordered, because feeding and
        bleeding live in the order and a cut interacts with both.
        Unordered triples, because there are already a hundred and
        twenty of them and the pairs have made the point about order.
        """
        return [
            tuple(combo)
            for combo in itertools.chain(
                itertools.permutations(range(len(POOL)), 1),
                itertools.permutations(range(len(POOL)), 2),
                itertools.combinations(range(len(POOL)), 3),
            )
        ]

    def test_swept_a_complete_answer_is_missing_nothing(self) -> None:
        """Three tallies, and each of them has to be non-trivial.

        ``checked`` is the sweep's size. ``brim`` counts the complete
        answers that filled their budget exactly -- the edge cases,
        where a cap that dropped a branch without recording it would
        show -- because a sweep at limits nothing reaches would satisfy
        the implication by never testing it. ``conservative`` counts the
        other side, and is asserted only to be non-zero: it says the cut
        answers in this sweep are not all of them missing something, so
        the implication being swept is the one direction and not both.
        """
        corpus = _forms("ate", (2, 3))[:12]
        cascades = self._cascades()
        assert len(corpus) == 12, "sweep did not run"
        assert len(cascades) > 200, f"sweep did not run: {len(cascades)}"
        checked = brim = conservative = 0
        broken: list[tuple[tuple[str, ...], str, int, list[str]]] = []
        for combo in cascades:
            cascade = _cat(*(R.RuleSet(rules=(RULES[i],)) for i in combo))
            for form in corpus:
                whole = cascade.variants(form, FEATURES, limit=UNBOUNDED)
                assert whole.complete, "the oracle has to be the complete answer"
                entire = set(whole.forms)
                for limit in self.LIMITS:
                    cut = cascade.variants(form, FEATURES, limit=limit)
                    checked += 1
                    missing = entire - set(cut.forms)
                    if not cut.complete:
                        conservative += not missing
                        continue
                    if missing:
                        rules = tuple(POOL[i] for i in combo)
                        broken.append((rules, form, limit, sorted(missing)))
                    brim += len(cut) >= limit
        assert not broken, broken[:5]
        assert checked > 10000, f"sweep did not run: {checked}"
        assert brim > 1000, f"no complete answer was near its limit: {brim}"
        assert conservative > 0, "every cut answer lost a form; see the pin below"

    def test_a_false_is_allowed_to_be_conservative(self) -> None:
        """The named case, small enough to follow all the way down.

        Over ``ab`` the first rule offers ``bb``, and the second offers
        ``bb`` again from the branch that declined the first. At a limit
        of two the budget is spent before that second child is built, so
        the step records a declined combination -- and what it declined
        was already a member. The answer reports itself cut and holds
        every form the uncapped call holds, in the same order.

        This failing means ``complete`` has been made exact, and making
        it exact means building the declined children, which is the work
        the cap exists to avoid. The repair is not to relax the sweep
        above: that direction is the one a caller is entitled to.
        """
        cascade = _set(self.CONVERGE)
        cut = cascade.variants("ab", FEATURES, limit=2)
        whole = cascade.variants("ab", FEATURES, limit=UNBOUNDED)
        assert cut.complete is False
        assert cut.truncations[0].step == 1
        assert cut.truncations[0].rule == "two"
        assert cut.unexplored == 1
        assert whole.complete is True
        assert cut.forms == whole.forms == ("ab", "bb")


class TestTheCheapestDerivationIsTheOneReported:
    """``choices`` is a fact about the form, not about rule order.

    Two branches that spell the same thing are one member, and the one
    to keep is the cheapest -- the member stands where the first of them
    arrived, and reports what the cheapest cost. Keeping the first
    instead makes ``choices`` and ``derivation`` answer for whichever
    route the enumeration happened to walk first, which is not a fact
    about the pronunciation at all.
    """

    #: c is one optional edit from a by the first rule and two by the
    #: other two. The branches are ordered a(0), b(1), c(1) when the
    #: third rule runs, and expanding b offers c at 2 where c already
    #: stands at 1.
    DETOUR = "a ~> c\na ~> b\nb ~> c"

    def test_a_convergent_member_reports_the_shorter_route(self) -> None:
        got = _set(self.DETOUR).variants("a", FEATURES)
        assert got.complete, "nothing here is cut; the set is all three"
        assert got.forms == ("a", "b", "c")
        assert [v.choices for v in got] == [0, 1, 1]
        cheap = got[2]
        assert [step.rule for step in cheap.derivation.fired] == ["a ~> c"]
        assert cheap.derivation.result == "c"

    def test_the_member_still_stands_where_it_first_arrived(self) -> None:
        """Cost decides the derivation, never the position. The order is
        the one a cascade split in two reproduces, and re-sorting the
        answer by cost would break the composition claim above."""
        got = _set(self.DETOUR).variants("a", FEATURES)
        assert got.forms.index("c") == 2

    def test_swept_against_the_exhaustive_oracle(self) -> None:
        """Every member of a complete answer reports the cheapest
        derivation the cascade has for it, measured against an
        enumeration that does no deduping at all."""
        corpus = ["at", "ta", "tat", "ata", "att", "aat", "ət", "tət", "tt", "ea"]
        checked = 0
        for size in (2, 3):
            for order in itertools.permutations(range(len(CONVERGENT)), size):
                cascade = _set("\n".join(CONVERGENT[i] for i in order))
                for form in corpus:
                    got = cascade.variants(form, FEATURES, limit=UNBOUNDED)
                    assert got.complete
                    want = _exhaust(cascade, form)
                    assert set(got.forms) == set(want), (order, form)
                    assert {v.form: v.choices for v in got} == want, (order, form)
                    checked += 1
        assert checked > 3000, f"sweep did not run: {checked}"


class TestTheCutFallsOnTheDearestChoicesAnywhere:
    """The cap is a cost order over the whole step, not over one branch.

    A rule is handed a set of branches, and grading its subsets by size
    orders the children of each branch on its own. Spending the budget
    branch by branch therefore keeps a first branch's dearest children
    over a second branch's free one, which is the same bias grading was
    introduced to remove, one level up.
    """

    def test_the_cut_looks_across_branches_and_not_down_one(self) -> None:
        got = _set("a ~> x\nb ~> y").variants("abbb", FEATURES, limit=5)
        assert got.forms == ("abbb", "aybb", "abyb", "abby", "xbbb")
        assert [v.choices for v in got] == [0, 1, 1, 1, 1]
        # xbbb takes one optional edit and ayyb takes two, and a cut
        # that exhausted the first branch first would keep ayyb.
        assert "ayyb" not in got.forms

    def test_a_capped_answer_is_a_subsequence_of_the_complete_one(self) -> None:
        """Cheapest first is what is KEPT; the order is still the order
        the cascade produced. So the two answers can be diffed without
        sorting either of them."""
        cascade = _set("a ~> x\nb ~> y")
        whole = list(cascade.variants("abbb", FEATURES, limit=UNBOUNDED).forms)
        for limit in range(1, len(whole) + 1):
            cut = cascade.variants("abbb", FEATURES, limit=limit).forms
            onward = iter(whole)
            assert all(any(form == other for other in onward) for form in cut), limit

    def test_no_kept_member_is_dearer_than_one_left_out(self) -> None:
        """The predicate, ranked globally by total choices against the
        exhaustive oracle.

        Confined to cascades whose one cut falls on the LAST rule, and
        that is not a convenience: the cap is a bound per step, so once
        a step has dropped a branch the steps after it are working from
        a set that is already short, and a form the whole cascade would
        have derived cheaply may have no cheap ancestor left to derive
        it from. What holds at every step is that the step kept the
        cheapest children it was offered, and the last step is where
        that is observable in the answer.
        """
        corpus = ["ab", "abb", "abbb", "bab", "bba", "abab"]
        checked = cut_seen = 0
        for pair in itertools.permutations(("a ~> x", "b ~> y", "a ~> e"), 2):
            cascade = _set("\n".join(pair))
            for form in corpus:
                costs = _exhaust(cascade, form)
                for limit in (1, 2, 3, 5, 8):
                    got = cascade.variants(form, FEATURES, limit=limit)
                    checked += 1
                    if len(got.truncations) != 1:
                        continue
                    if got.truncations[0].step != len(cascade) - 1:
                        continue
                    kept = set(got.forms)
                    lost = [cost for f, cost in costs.items() if f not in kept]
                    if not lost:
                        continue
                    cut_seen += 1
                    assert max(v.choices for v in got) <= min(lost), (pair, form, limit)
        assert checked > 100, f"sweep did not run: {checked}"
        assert cut_seen > 20, f"nothing was actually cut: {cut_seen}"

    def test_a_cut_step_reports_what_it_declined(self) -> None:
        """The count follows the cut. Two branches of four sites each,
        cut at five: the step builds five children and declines the
        rest of both branches' subsets."""
        got = _set("a ~> x\nb ~> y").variants("abbb", FEATURES, limit=5)
        assert got.truncations[0].step == 1
        assert got.truncations[0].kept == 5
        assert got.unexplored == (2**3 - 4) + (2**3 - 1) == 11


# --------------------------------------------------------------------------
# Order and determinism
# --------------------------------------------------------------------------


class TestTheOrderIsDeterministic:
    def test_repeated_calls_agree(self) -> None:
        cascade = _set("a ~> e ; raise\nt ~> ʔ ; glottal")
        first = cascade.variants("atata", FEATURES, limit=UNBOUNDED).forms
        for _ in range(3):
            assert cascade.variants("atata", FEATURES, limit=UNBOUNDED).forms == first

    def test_the_order_does_not_depend_on_the_hash_seed(self) -> None:
        """Nothing in the enumeration iterates a set or a hash, so this
        should hold -- and a regression to a set-keyed dedupe would be
        invisible under the pinned seed the suite runs with."""
        script = (
            "import ipakit;"
            "print(ipakit.variants('atata',"
            "'a ~> e ; raise\\nt ~> ʔ ; glottal').forms)"
        )
        answers = set()
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT))
            done = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                cwd=ROOT,
                env=env,
            )
            assert done.returncode == 0, done.stderr
            answers.add(done.stdout.strip())
        assert len(answers) == 1, answers

    def test_the_first_member_takes_no_optional_choice(self) -> None:
        corpus = _forms("ate", (2, 3))
        assert len(corpus) > 20, "sweep did not run"
        cascade = _set("a ~> e ; raise\nt ~> ʔ ; glottal\n∅ ~> ə / t _ t ; epenthesis")
        for form in corpus:
            got = cascade.variants(form, FEATURES, limit=UNBOUNDED)
            assert got.variants[0].choices == 0, form
            assert got.forms[0] == cascade.apply(form, FEATURES), form

    def test_within_one_rule_the_members_are_graded_by_choices_taken(self) -> None:
        got = _set("[vowel] ~> [length=long]").variants("aaa", FEATURES)
        taken = [variant.choices for variant in got]
        assert taken == sorted(taken)
        assert taken == [0, 1, 1, 1, 2, 2, 2, 3]

    def test_convergent_branches_are_one_member_keeping_the_first(self) -> None:
        """Two distinct choices spelling the same form are one variant,
        and the derivation kept is the cheaper one."""
        got = _set("t ~> ∅").variants("att", FEATURES)
        assert got.forms == ("att", "at", "a")
        assert [variant.choices for variant in got] == [0, 1, 2]


# --------------------------------------------------------------------------
# The answer's shape
# --------------------------------------------------------------------------


class TestTheVariantSetAnswersForItself:
    def test_the_container_protocol(self) -> None:
        got = _set("t ~> ʔ / _ #").variants("kæt", FEATURES)
        assert len(got) == 2
        assert [variant.form for variant in got] == list(got.forms)
        assert "kæʔ" in got and "kæd" not in got
        assert got[0] in got
        assert got.start == "kæt"
        assert str(got) == "kæt ~ kæʔ"

    def test_complete_and_truncated_are_one_fact(self) -> None:
        for limit in (1, 2, 4, R.DEFAULT_LIMIT):
            got = _set("[vowel] ~> [length=long]").variants("aa", FEATURES, limit=limit)
            assert got.complete is not got.truncated
            assert got.complete == (got.unexplored == 0)

    def test_every_member_carries_a_derivation_that_reaches_it(self) -> None:
        cascade = R.shipped("french-liaison", FEATURES)
        checked = 0
        for word in ("pətit", "dəvəniʁ", "lez‿ami", "samədi"):
            got = cascade.variants(word, FEATURES)
            for variant in got:
                derivation = variant.derivation
                assert derivation.result == variant.form
                assert derivation.start == got.start
                assert len(derivation.steps) == len(cascade)
                # choices is what the derivation says it is, not a
                # counter kept beside it.
                assert variant.choices == sum(
                    len(step.edits) for step in derivation.steps if step.optional
                )
                checked += 1
        assert checked >= 8, "sweep did not run"


# --------------------------------------------------------------------------
# The shipped set
# --------------------------------------------------------------------------


class TestTheFrenchSetShipsTheOptionalHalf:
    """e caduc: the phenomenon the arrow exists for, and the linguistics.

    Every expected value here is a fact about French rather than about
    the engine, so a change to the engine that moves one of them is a
    change to what the set claims about the language.
    """

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("pətit", ("pəti", "pti"), "petit"),
            ("pətitə", ("pətit", "ptit"), "petite"),
            ("ʃəval", ("ʃəval", "ʃval"), "cheval"),
            ("dəmɛ̃", ("dəmɛ̃", "dmɛ̃"), "demain"),
            ("samədi", ("samədi", "samdi"), "samedi"),
            ("dəvəniʁ", ("dəvəniʁ", "dəvniʁ", "dvəniʁ"), "devenir: not *[dvniʁ]"),
            ("vɑ̃dʁədi", ("vɑ̃dʁədi",), "vendredi: the loi des trois consonnes"),
            ("pʁəmjeʁ", ("pʁəmjeʁ",), "premier: /pʁm/ would be three"),
            ("lə", ("lə",), "le: the schwa is the only vowel it has"),
            ("ʒə", ("ʒə",), "je"),
            ("ynə", ("yn",), "une: the final schwa goes, obligatorily"),
            ("katʁə", ("katʁ",), "quatre"),
            ("pətit‿ami", ("pəti‿tami", "pti‿tami"), "petit ami, after liaison"),
        ],
    )
    def test_variants(self, source: str, expected: tuple[str, ...], gloss: str) -> None:
        assert FRENCH.variants(source, FEATURES).forms == expected, gloss

    def test_the_three_consonant_law_is_stated_by_ordering(self) -> None:
        """The finding this set records, measured both ways.

        Within one rule the sites branch independently against a
        snapshot, so no site can see what another chose and an output
        constraint is lost. Splitting the choices over ordered rules is
        where the information comes back: the second rule asks its
        question of a form in which the first choice is already made.

        Written up as a technique in docs/calculus.md, under "Splitting
        the choices over ordered rules"; the three tests below are the
        rest of that write-up, including the word it gets wrong.
        """
        one_rule = _set("ə ~> ∅ / [-vowel] _ [-vowel] [vowel] ; both at once")
        assert one_rule.variants("dəvəniʁ", FEATURES).forms == (
            "dəvəniʁ",
            "dvəniʁ",
            "dəvniʁ",
            "dvniʁ",
        ), "one rule over-generates, which is the point"
        assert "dvniʁ" not in FRENCH.variants("dəvəniʁ", FEATURES).forms

    def test_the_mechanism_is_bleeding_branch_by_branch(self) -> None:
        """Not a filter afterwards: the illegal form is never derived.

        In the branch where the first schwa dropped, the interior rule's
        left context -- a consonant preceded by a VOWEL -- no longer
        holds, because the /v/ now stands behind a /d/. So the second
        choice is not offered at that branch at all, and each surviving
        member names the one rule that made it.
        """
        assert [
            (v.form, [s.rule for s in v.derivation.fired])
            for v in FRENCH.variants("dəvəniʁ", FEATURES)
        ] == [
            ("dəvəniʁ", []),
            ("dəvniʁ", ["e caduc (interior)"]),
            ("dvəniʁ", ["e caduc (first syllable)"]),
        ]

    def test_the_split_is_not_a_preference_for_one_schwa(self) -> None:
        """Measured rather than assumed, because ordering imposes an
        asymmetry that the constraint does not have.

        Here it happens not to matter: the bleeding runs both ways, so
        the two orders give the same set. That is a fact about this pair
        and not a property of the technique, which is why it is a
        measurement and not a claim.
        """
        first = "ə ~> ∅ / # [-vowel] _ [-vowel] [vowel] ; first"
        interior = "ə ~> ∅ / [vowel] [-vowel] _ [-vowel] [vowel] ; interior"
        forward = _set(f"{first}\n{interior}").variants("dəvəniʁ", FEATURES).forms
        backward = _set(f"{interior}\n{first}").variants("dəvəniʁ", FEATURES).forms
        assert set(forward) == set(backward) == {"dəvəniʁ", "dəvniʁ", "dvəniʁ"}

    def test_the_technique_is_narrower_than_the_constraint_it_stands_in_for(
        self,
    ) -> None:
        """The word it gets wrong, and this set over-generates on it today.

        Ordering separates choices it can put in DIFFERENT rules. Two
        sites that fall to the SAME rule still branch independently
        against the snapshot -- that is what the limit says, and no
        ordering reaches inside one rule. 'redevenir' /ʁədəvəniʁ/ has
        three droppable schwas whose second and third are both interior,
        so they are one rule's two sites, and *[ʁədvniʁ] comes out with
        /d v n/ in it.

        Pinned as a KNOWN over-generation. If it ever stops being
        derived, the write-up in docs/calculus.md needs updating, which
        is the point of pinning an escape rather than assuming it shut.
        """
        forms = FRENCH.variants("ʁədəvəniʁ", FEATURES).forms
        assert forms == (
            "ʁədəvəniʁ",
            "ʁədvəniʁ",
            "ʁədəvniʁ",
            "ʁədvniʁ",
            "ʁdəvəniʁ",
            "ʁdəvniʁ",
        )
        assert "ʁədvniʁ" in forms, "the documented limit has moved"
        # and both of the offending choices came from the one rule
        illegal = next(
            v for v in FRENCH.variants("ʁədəvəniʁ", FEATURES) if v.form == "ʁədvniʁ"
        )
        assert [s.rule for s in illegal.derivation.fired] == ["e caduc (interior)"]
        assert illegal.choices == 2

    def test_the_optional_rules_are_the_e_caduc_pair_and_nothing_else(
        self,
    ) -> None:
        """A predicate over the file: liaison and the deletions are
        obligatory, and marking any of them optional would derive
        [le‿ami], which is a speech error rather than a variant."""
        assert [rule.name for rule in FRENCH if rule.optional] == [
            "e caduc (first syllable)",
            "e caduc (interior)",
        ]
        assert FRENCH.optional is True

    def test_the_obligatory_derivations_are_untouched(self) -> None:
        """The set gained two rules and no existing answer moved. Swept
        over the set's own corpus rather than spot-checked."""
        from tests.test_rule_sets import CORPUS
        from tests.test_rule_sets import FRENCH as FRENCH_NAME

        words = CORPUS[FRENCH_NAME]
        assert len(words) >= 15, "sweep did not run"
        for word in words:
            assert (
                FRENCH.apply(word, FEATURES) == FRENCH.variants(word, FEATURES).forms[0]
            ), word

    def test_no_other_shipped_set_has_become_optional(self) -> None:
        """Marking a rule optional changes what a set claims, so it may
        not happen by accident in a set nobody meant to touch."""
        optional = {
            name for name in R.available() if R.shipped(name, FEATURES).optional
        }
        assert optional == {"french-liaison"}


# --------------------------------------------------------------------------
# The CLI says the same thing the API says
# --------------------------------------------------------------------------


def _cli(monkeypatch, capsys, *argv: str) -> tuple[int, str, str]:
    """Invoke the CLI in process; return (rc, stdout, stderr).

    The same shape ``tests/test_cli.py`` uses. Written here rather than
    imported so this lane's CLI tests live beside the API claims they
    check against, and a divergence between the two surfaces fails in the
    file that documents why they must agree.
    """
    import ipakit.cli

    monkeypatch.setattr(sys, "argv", ["ipakit", *argv])
    rc = ipakit.cli.main()
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


class TestTheCommandLineIsInSyncWithTheLibrary:
    """Whatever the API gained, the CLI gained. Checked by comparing the
    two answers rather than by reading both, because a CLI that computes
    the right thing and prints a stale shape is the same silent wrong
    answer as any other."""

    def test_variants_prints_the_forms_the_api_returns(
        self, monkeypatch, capsys
    ) -> None:
        rc, out, err = _cli(
            monkeypatch, capsys, "rules", "variants", "-s", "french-liaison", "dəvəniʁ"
        )
        assert rc == 0, err
        lines = out.strip().split("\n")
        assert lines[0] == "dəvəniʁ: 3 variants"
        assert (
            tuple(line.strip() for line in lines[1:])
            == FRENCH.variants("dəvəniʁ", FEATURES).forms
        )

    def test_the_json_row_carries_the_completeness_of_the_answer(
        self, monkeypatch, capsys
    ) -> None:
        import json

        rc, out, err = _cli(
            monkeypatch,
            capsys,
            "rules",
            "variants",
            "-r",
            "[vowel] ~> [length=long]",
            "aaaa",
            "--limit",
            "4",
            "-j",
        )
        assert rc == 0, err
        row = json.loads(out)[0]
        want = ipakit.variants("aaaa", "[vowel] ~> [length=long]", limit=4)
        assert row["complete"] is False
        assert row["limit"] == 4
        assert [v["form"] for v in row["variants"]] == list(want.forms)
        assert [v["choices"] for v in row["variants"]] == [v.choices for v in want]
        assert row["truncations"][0]["unexplored"] == want.truncations[0].unexplored

    def test_a_complete_answer_carries_the_same_keys(self, monkeypatch, capsys) -> None:
        """The shape does not change with the answer, so an absent key
        can never be mistaken for a complete one."""
        import json

        rc, out, _ = _cli(
            monkeypatch, capsys, "rules", "variants", "-r", "t ~> ʔ / _ #", "kæt", "-j"
        )
        assert rc == 0
        row = json.loads(out)[0]
        assert row["complete"] is True
        assert row["truncations"] == []
        assert set(row) == {
            "form",
            "start",
            "limit",
            "complete",
            "truncations",
            "variants",
        }

    def test_the_count_line_says_when_the_answer_is_cut(
        self, monkeypatch, capsys
    ) -> None:
        """Reported in the answer, not in a log: a truncated set of
        pronunciations reads exactly like an exhaustive one."""
        rc, out, _ = _cli(
            monkeypatch,
            capsys,
            "rules",
            "variants",
            "-r",
            "[vowel] ~> [length=long] ; lengthening",
            "aaaa",
            "--limit",
            "4",
        )
        assert rc == 0
        assert "INCOMPLETE" in out.split("\n")[0]
        assert "lengthening" in out.split("\n")[0]
        # "at least", because the count is exact for the step it names
        # and silent about the rules after it. A bare number here reads
        # as the size of what is missing, which it is not.
        assert "at least 12 choice combination(s) unexplored" in out

    def test_the_count_line_reports_a_cut_and_not_a_loss(
        self, monkeypatch, capsys
    ) -> None:
        """INCOMPLETE says the enumeration was cut. On the conservative
        case it prints beside every form the uncapped call gives, which
        is what the word has to be able to mean."""
        cascade = _set(TestACompleteAnswerHoldsEveryForm.CONVERGE)
        whole = cascade.variants("ab", FEATURES, limit=UNBOUNDED)
        rc, out, _ = _cli(
            monkeypatch,
            capsys,
            "rules",
            "variants",
            "-r",
            "a ~> b ; one",
            "-r",
            "a ~> b / _ b ; two",
            "ab",
            "--limit",
            "2",
        )
        assert rc == 0
        lines = out.strip().split("\n")
        assert "INCOMPLETE" in lines[0]
        assert tuple(line.strip() for line in lines[1:]) == whole.forms

    def test_apply_prints_the_first_variant(self, monkeypatch, capsys) -> None:
        rc, out, _ = _cli(
            monkeypatch, capsys, "rules", "apply", "-s", "french-liaison", "pətit"
        )
        assert rc == 0
        assert out.strip() == FRENCH.variants("pətit", FEATURES).forms[0]

    def test_trace_marks_a_choice_not_taken(self, monkeypatch, capsys) -> None:
        rc, out, _ = _cli(
            monkeypatch,
            capsys,
            "rules",
            "trace",
            "-r",
            "t ~> ʔ / _ # ; glottalling",
            "kæt",
            "--all",
        )
        assert rc == 0
        # The marker follows the name, so every name starts at column two --
        # see ``Derivation.trace``. A choice declined reads differently from a
        # rule that fired and changed nothing.
        assert "glottalling  (not taken)" in out

    def test_list_reports_which_rules_are_optional(self, monkeypatch, capsys) -> None:
        import json

        rc, out, _ = _cli(monkeypatch, capsys, "rules", "list", "french-liaison", "-j")
        assert rc == 0
        rows = json.loads(out)["rules"]
        assert [row["name"] for row in rows if row["optional"]] == [
            rule.name for rule in FRENCH if rule.optional
        ]

    def test_a_limit_below_one_is_an_error_and_not_a_traceback(
        self, monkeypatch, capsys
    ) -> None:
        rc, _, err = _cli(
            monkeypatch,
            capsys,
            "rules",
            "variants",
            "-r",
            "a ~> e",
            "a",
            "--limit",
            "0",
        )
        assert rc == 1
        assert "at least 1" in err

    def test_a_set_with_no_optional_rule_reports_one_variant(
        self, monkeypatch, capsys
    ) -> None:
        rc, out, _ = _cli(
            monkeypatch, capsys, "rules", "variants", "-s", "american-english", "pˈɪn"
        )
        assert rc == 0
        assert out.strip().split("\n") == ["pˈɪn: 1 variant", "  pʰˈɪ̃n"]
