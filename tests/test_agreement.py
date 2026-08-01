"""Agreement variables: SPE's ``α``, and what it is allowed to mean.

The feature exists because the shipped English set was working around
its absence by *enumeration* -- one nasal-assimilation rule per place --
and the file said so in a comment. Two rules sufficed only because
English needs two places; the general process needs eleven or more, and
a student who has read Kenstowicz writes the variable and expects it to
work. The collapse of those two rules into one is the demonstration, and
the sweep below is what makes it a claim rather than a hope.

Three things are measured here rather than argued, because each is a
place where a looser reading would be a well-formed wrong answer:

* the notation cannot collide with a phone and cannot reach a form;
* every refusal is a refusal, not a rule that parses and quietly matches
  nothing -- a variable that fell through to "no site" would be the
  fourth silent-drop defect in this query language's history;
* the collapsed rule agrees with the enumeration exactly where the
  enumeration spoke, and the places where it does *not* agree are
  enumerated one by one.
"""

from __future__ import annotations

import warnings

import pytest
from ipakit import rules as R
from ipakit.features import IPAFeatures
from ipakit.form import units

FEATURES = IPAFeatures()


def _set(text: str) -> R.RuleSet:
    return R.RuleSet.parse(text, FEATURES)


def _apply(spec: str, form: str) -> str:
    return _set(spec).apply(form, FEATURES)


# --------------------------------------------------------------------------
# The notation, and the collision it had to answer
# --------------------------------------------------------------------------


class TestTheSeriesIsAskedOfTheDeclaration:
    """The collision check, as a predicate rather than a hand-checked list.

    The traditional series is ``α β γ``, and its second member is a
    registered phone. Which letters are free is therefore a question
    about *this* inventory, and the answer has to be computed from it --
    the same standard ``OPTIONAL_MARK`` is held to in test_calculus.py.
    """

    def test_the_series_is_the_alphabet_and_nothing_else(self) -> None:
        """Membership, not size.

        A floor on the length passed while the series held a member
        nobody had looked at, because no rule string anywhere in this
        suite spells one. The alphabet is written out so that a filter
        which swaps one letter for another fails here rather than in a
        rule somebody writes.
        """
        assert "".join(R.SERIES) == "αβγδεζηθικλμνξοπρστυφχψω"
        assert R.SERIES[0] == "α" and R.SERIES[-1] == "ω"
        assert len(R.SERIES) == len(set(R.SERIES))
        assert all(len(letter) == 1 for letter in R.SERIES)

    def test_no_two_members_are_one_letter_drawn_two_ways(self) -> None:
        """The safety property the bound exists for, as a predicate.

        'ά' is alpha with a tonos and sits outside the endpoints; 'ς' is
        sigma in final position and sits inside them. Both are a member
        that differs from another only in how it is drawn, which is the
        typo the endpoints were chosen to keep out -- so the endpoints
        cannot be the whole of the answer, and this is the part that
        does not depend on where the range happens to stop.
        """
        assert len(R.SERIES) == len({letter.upper() for letter in R.SERIES})
        assert "ά" not in R.SERIES
        assert "σ" in R.SERIES and "ς" not in R.SERIES

    def test_final_sigma_is_not_a_second_sigma(self) -> None:
        """What the letter not being in the series means for a rule.

        A variable spelled with it is a value the feature does not
        declare, refused where every other misspelled value is.
        """
        assert _apply("n -> [place=σ] / _ [place=σ]", "anpa") == "ampa"
        with pytest.raises(R.RuleError, match="is not a value of feature"):
            R.parse("n -> [place=ς] / _ [place=ς]", FEATURES)

    def test_a_free_letter_spells_nothing_and_reaches_no_form(self) -> None:
        """The property that makes a variable safe, over every free letter.

        Not "α is free": *every* letter this inventory leaves free must
        be unable to reach a form, or a leak would spell a phone.
        """
        free = R._free_variables(FEATURES)
        assert free, "no variable letter is available at all"
        checked = 0
        for letter in free:
            assert letter not in FEATURES.phones
            assert not [p for p in FEATURES.phones if letter in p]
            assert letter not in FEATURES.diacritics
            assert letter not in FEATURES.separators
            assert letter not in FEATURES.zeros
            assert letter not in R._boundary_spellings(FEATURES)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                assert [u.text for u in units(f"a{letter}b", FEATURES)] == ["a", "b"]
            checked += 1
        assert checked >= 20, "sweep did not run"

    def test_a_taken_letter_is_refused_by_name_and_with_the_reason(self) -> None:
        """The half that must be loud.

        Skipping ``β`` in silence is the shape of surprise this
        repository keeps paying for. A phonologist who writes the second
        member of the traditional series gets told which phone it is.
        """
        taken = [
            letter for letter in R.SERIES if letter not in R._free_variables(FEATURES)
        ]
        assert "β" in taken, "the collision this notation had to answer is gone"
        for letter in taken:
            with pytest.raises(R.RuleError, match="this inventory registers"):
                R.parse(f"n -> [place={letter}] / _ [place={letter}]", FEATURES)

    def test_the_free_letters_all_work_as_variables(self) -> None:
        """Not only α: the series is a supply, and a rule may need three."""
        for letter in R._free_variables(FEATURES)[:5]:
            spec = f"n -> [place={letter}] / _ [place={letter}]"
            assert _apply(spec, "anka") == "aŋka", letter

    def test_a_letter_the_inventory_claims_stops_being_notation(self) -> None:
        """The declaration wins, always.

        Pinned as a *predicate over both directions*: a letter is a
        variable exactly when the inventory does not read it. If the two
        ever came apart -- a letter both readable and usable as a
        variable -- a variable could reach a form.
        """
        for letter in R.SERIES:
            readable = bool(R._reads_as(letter, FEATURES))
            usable = letter in R._free_variables(FEATURES)
            assert readable != usable, letter


# --------------------------------------------------------------------------
# What a variable means
# --------------------------------------------------------------------------


class TestRecognitionBindsAndTheActionRefers:
    def test_the_canonical_rule(self) -> None:
        spec = "n -> [place=α] / _ [place=α]"
        assert _apply(spec, "anpa") == "ampa"
        assert _apply(spec, "anka") == "aŋka"
        assert _apply(spec, "anfa") == "aɱfa"

    def test_a_place_that_is_not_there_does_not_bind(self) -> None:
        """No vowel declares a place, so /n/ before a vowel is left alone.

        The ordinary reading of a query term, not a rule about variables:
        ``[place=alveolar]`` does not match a vowel either.
        """
        assert _apply("n -> [place=α] / _ [place=α]", "ana") == "ana"

    def test_the_site_records_what_it_bound(self) -> None:
        rule = R.parse("n -> [place=α] / _ [place=α]", FEATURES)
        (site,) = rule.recognize("anka", FEATURES)
        assert site.bindings == (("α", "velar"),)

    def test_a_binding_does_not_outlive_its_site(self) -> None:
        """Two sites in one form bind independently.

        A binding carried between candidate positions would make the
        first consonant in a word decide what every later one has to
        agree with.
        """
        assert _apply("n -> [place=α] / _ [place=α]", "anpanka") == "ampaŋka"

    def test_the_target_may_bind_and_the_context_check(self) -> None:
        """Either side may be where a variable first takes a value.

        The direction is not part of the semantics: the site holds where
        the occurrences agree, so writing it the other way round is the
        same rule.
        """
        spec = "[place=α] -> [voiced=+] / _ [place=α]"
        assert _apply(spec, "atta") == "adta"
        assert _apply(spec, "atka") == "atka"

    def test_two_independent_variables_in_one_rule(self) -> None:
        spec = "[manner=plosive] -> [place=α voiced=γ] / _ [place=α] [voiced=γ]"
        assert _apply(spec, "atkza") == "aɡdza"

    def test_a_variable_may_range_over_prosody(self) -> None:
        """Routed by declared mode, exactly as a plain term is.

        Written with explicit combining marks: a precomposed 'á' and a
        decomposed one are the same word and different strings, and the
        library answers in the decomposed spelling.
        """
        spread = "[vowel] -> [tone=α] / [tone=α] [-vowel] _"
        assert _apply(spread, "ma\u0301ta\u0300") == "ma\u0301ta\u02e6"
        assert _apply(spread, "ma\u0300ta\u0301") == "ma\u0300ta\u02e8"

    def test_a_rule_may_be_optional_and_use_a_variable(self) -> None:
        """The two features are orthogonal, and each site still branches."""
        found = _set("n ~> [place=α] / _ [place=α]").variants("anpanka", FEATURES)
        assert found.forms == ("anpanka", "ampanka", "anpaŋka", "ampaŋka")
        assert found.complete


class TestDisagreement:
    """``-α``: legal where an opposite exists, refused where it does not."""

    def test_the_opposite_of_a_binary_value(self) -> None:
        spec = "[manner=plosive] -> [voiced=-α] / [voiced=α] _"
        assert _apply(spec, "asta") == "asda"
        assert _apply(spec, "azta") == "azta"

    def test_an_n_ary_feature_has_no_opposite_and_says_so(self) -> None:
        with pytest.raises(R.RuleError, match="well defined only"):
            R.parse("n -> [place=-α] / _ [place=α]", FEATURES)

    def test_the_opposite_is_read_from_the_declaration(self) -> None:
        """Not assumed to be '+'/'-': the other declared value, whatever
        the declaration calls it."""
        for name, feature in FEATURES.features.items():
            if feature.type == "binary" and len(feature.values) == 2:
                first, second = feature.values
                assert R._opposite(name, first, FEATURES) == second
                assert R._opposite(name, second, FEATURES) == first


# --------------------------------------------------------------------------
# Every refusal is loud
# --------------------------------------------------------------------------


class TestAVariableThatCannotMeanAnythingIsRefused:
    """Each of these would otherwise be a *site-dependent* silence.

    The live lesson: a mixed query that drops an unresolvable term still
    parses and derives a wrong answer. None of these is allowed to
    become a second instance of that shape.
    """

    def test_one_feature_per_variable(self) -> None:
        with pytest.raises(R.RuleError, match="on two features"):
            R.parse("n -> [place=α] / [voiced=α] _ [place=α]", FEATURES)

    def test_a_variable_the_left_never_binds(self) -> None:
        with pytest.raises(R.RuleError, match="nothing on the left binds"):
            R.parse("n -> [place=α] / _ [place=γ]", FEATURES)

    def test_a_variable_with_no_context_at_all(self) -> None:
        with pytest.raises(R.RuleError, match="nothing on the left binds"):
            R.parse("n -> [place=α]", FEATURES)

    def test_a_variable_used_once_says_nothing(self) -> None:
        with pytest.raises(R.RuleError, match="once"):
            R.parse("n -> t / _ [place=α]", FEATURES)

    def test_a_bare_variable_has_no_feature_to_be_a_value_of(self) -> None:
        with pytest.raises(R.RuleError, match="on its own"):
            R.parse("n -> t / _ [α]", FEATURES)

    def test_a_multi_letter_name_is_not_a_variable(self) -> None:
        """It falls through to the value arm and is refused as a value,
        which is the right answer: the series supplies single letters."""
        with pytest.raises(R.RuleError, match="is not a value of feature"):
            R.parse("n -> [place=αγ] / _ [place=αγ]", FEATURES)

    def test_a_pattern_matched_with_no_environment_refuses(self) -> None:
        """The last place a variable could be dropped in silence.

        ``Pattern.matches`` is reachable on its own, and a pattern that
        ignored its variable would match wherever the rest of it held --
        assimilation to *every* following consonant.
        """
        rule = R.parse("n -> [place=α] / _ [place=α]", FEATURES)
        (context,) = rule.query.right
        unit = list(units("k", FEATURES))[0]
        with pytest.raises(R.RuleError, match="no environment"):
            context.matches(unit, FEATURES)

    def test_an_action_asked_for_an_unbound_variable_refuses(self) -> None:
        """``parse`` makes this unreachable from the notation, so it is
        pinned by constructing the state directly. It raises rather than
        writing the rest of the change and reporting an edit."""
        action = R.Action(becomes={"place": R.Agreement("α")})
        items = list(units("nk", FEATURES))
        with pytest.raises(R.RuleError, match="never bound"):
            action.edit(R.Site(0, 1), items, FEATURES, rule="probe")


class TestTheVariableNeverReachesTheQueryResolver:
    """Where this feature and the unresolvable-term guard meet.

    A variable is *not* a query term that fails to resolve and has to be
    tolerated -- it is peeled off in the notation layer and never handed
    to ``_resolve_query`` at all. So whatever that resolver does with a
    term it cannot place, drop it or raise, it never sees one of these,
    and the two designs cannot collide.
    """

    def test_no_variable_is_ever_passed_to_the_resolver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[object] = []
        original = IPAFeatures._resolve_query

        def spy(self, query):  # type: ignore[no-untyped-def]
            seen.append(query)
            return original(self, query)

        monkeypatch.setattr(IPAFeatures, "_resolve_query", spy)
        specs = [
            "n -> [place=α] / _ [place=α]",
            "n -> [place=α] / [vowel] _ [place=α -nasal]",
            "[manner=plosive] -> [voiced=-α] / [voiced=α] _",
            "[manner=plosive] -> [place=α voiced=γ] / _ [place=α] [voiced=γ]",
        ]
        for spec in specs:
            R.parse(spec, FEATURES)
        assert seen, "the resolver was not exercised at all"
        letters = set(R.SERIES)
        for query in seen:
            terms = query.values() if isinstance(query, dict) else query
            for term in terms:
                assert not (letters & set(str(term))), (term, query)

    def test_a_variable_leaves_no_trace_in_the_resolved_constraints(self) -> None:
        pattern = R._pattern("[place=α -nasal]", FEATURES)
        assert pattern.seg_agreements == {"place": R.Agreement("α")}
        assert "place" not in pattern.seg_required
        assert not (set(R.SERIES) & set("".join(pattern.seg_required.values())))


# --------------------------------------------------------------------------
# The collapse, swept
# --------------------------------------------------------------------------

#: The enumeration the shipped rule replaced, kept here so the comparison
#: is against what actually shipped rather than against a paraphrase.
ENUMERATED = (
    "n -> [place=bilabial] / _ [place=bilabial] ; nasal assimilation (labial)\n"
    "n -> [place=velar] / _ [place=velar] ; nasal assimilation (velar)"
)
COLLAPSED = "n -> [place=α] / _ [place=α] ; nasal assimilation"


class TestTheCollapsedNasalRule:
    """One rule where there were two, and exactly what that changed.

    The honest claim is *not* "the derivations are unchanged". A single
    rule over a variable cannot be restricted to two of the fourteen
    declared places -- a bracketed query is a conjunction, so there is no
    way to write "bilabial or velar" once -- so collapsing necessarily
    widens. What is measured here is the shape of the widening: identical
    where the enumeration spoke, and the general process everywhere else.
    """

    @pytest.fixture(scope="class")
    def source(self) -> str:
        path = R.RULES_DIR / "american-english.rules"
        return path.read_text(encoding="utf-8")

    def test_the_shipped_set_states_it_once(self, source: str) -> None:
        assert COLLAPSED in source
        assert ENUMERATED not in source
        names = [r.name for r in R.shipped("american-english", FEATURES)]
        assert names.count("nasal assimilation") == 1
        assert not [n for n in names if n.startswith("nasal assimilation (")]

    def test_it_agrees_with_the_enumeration_where_the_enumeration_spoke(
        self, source: str
    ) -> None:
        """The regression half, swept rather than sampled.

        'n' before every phone that spells itself back, in three frames.
        At bilabial and velar -- the two the old rules named -- and at
        alveolar, where the change is a no-op, the two spellings must
        give the same form for every phone.
        """
        collapsed = R.RuleSet.parse(source, FEATURES)
        enumerated = R.RuleSet.parse(source.replace(COLLAPSED, ENUMERATED), FEATURES)
        assert len(enumerated) == len(collapsed) + 1

        named = {"bilabial", "velar", "alveolar"}
        checked = 0
        for phone in (p for p in FEATURES.phones if FEATURES.segment(p).to_ipa() == p):
            place = FEATURES.get_features(phone).get("place")
            for frame in ("ˈan{}a", "an{}#", "ˈɪn{}ət"):
                form = frame.format(phone)
                got = collapsed.apply(form, FEATURES)
                was = enumerated.apply(form, FEATURES)
                checked += 1
                if place in named or place is None:
                    assert got == was, (form, phone, place)
        assert checked > 300, "sweep did not run"

    def test_every_difference_is_a_place_the_enumeration_never_named(
        self, source: str
    ) -> None:
        """The other half: account for every mover.

        Each differing form must be one where the collapsed rule wrote
        the *following consonant's own place* onto the /n/, at a place
        outside the two the old rules enumerated. Nothing else may move.
        """
        collapsed = R.RuleSet.parse(source, FEATURES)
        enumerated = R.RuleSet.parse(source.replace(COLLAPSED, ENUMERATED), FEATURES)
        one = R.parse(COLLAPSED, FEATURES)

        moved: dict[str, int] = {}
        checked = 0
        for phone in (p for p in FEATURES.phones if FEATURES.segment(p).to_ipa() == p):
            place = FEATURES.get_features(phone).get("place")
            for frame in ("ˈan{}a", "an{}#", "ˈɪn{}ət"):
                form = frame.format(phone)
                checked += 1
                if collapsed.apply(form, FEATURES) == enumerated.apply(form, FEATURES):
                    continue
                assert place not in {"bilabial", "velar", "alveolar", None}
                # and the mover is the assimilation itself, binding to
                # the neighbor's own place
                (site,) = one.recognize(form, FEATURES)
                assert site.bindings == (("α", place),)
                moved[place] = moved.get(place, 0) + 1
        assert checked > 300, "sweep did not run"
        assert set(moved) == {
            "labiodental",
            "dental",
            "palatal",
            "uvular",
            "bilabial^velar",
        }, moved

    def test_the_two_words_the_widening_is_worth(self) -> None:
        english = R.shipped("american-english", FEATURES)
        assert english.apply("ˈɪnfənt", FEATURES) == "ˈɪ̃ɱfə̃nt̚"
        assert english.apply("tˈɛnθ", FEATURES) == "tʰˈɛ̃n̪θ"


# --------------------------------------------------------------------------
# What agreement variables do NOT bring
# --------------------------------------------------------------------------


class TestMetathesisDoesNotFallOut:
    """Recorded because it was *expected* to, and it does not.

    The two rhyme -- both want the right of the arrow to refer to
    material the left matched -- and they are different mechanisms. An
    agreement variable copies a feature VALUE between positions the rule
    already matched one at a time; metathesis REORDERS the positions
    themselves. A ``Pattern`` constrains one unit and a ``Site`` spans
    one, so there is nothing for a permutation to permute, and no
    variable changes that. docs/calculus.md keeps metathesis on the list
    of what the calculus cannot express, and this is the pin that says
    the list is still right.
    """

    def test_a_two_unit_target_is_still_refused(self) -> None:
        with pytest.raises(R.RuleError, match="constrains a\n?\\s*single unit"):
            R.parse("ab -> ba", FEATURES)

    def test_a_variable_does_not_buy_a_two_unit_target(self) -> None:
        with pytest.raises(R.RuleError, match="single unit"):
            R.parse("ab -> [place=α] / _ [place=α]", FEATURES)

    def test_copying_a_whole_segment_still_needs_it_named(self) -> None:
        """The French liaison shape: a rule that inserts a copy of the
        consonant has to name the consonant. A variable over *values* of
        one feature cannot stand for a segment, so the four liaison rules
        stay four."""
        liaison = R.shipped("french-liaison", FEATURES)
        copies = [r for r in liaison if r.name.startswith("liaison")]
        assert len(copies) == 4
