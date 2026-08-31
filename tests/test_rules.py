"""Rewrite rules: what a rule must satisfy, swept rather than sampled.

The properties here are the ones a green suite would otherwise let slide.
Two matter most, because both are silent when wrong:

* a form that no rule reaches must spell back out **byte-identical**,
  including its boundaries -- ``segments()`` drops them, which is why
  :func:`ipakit.rules.units` exists at all; and
* optional notation must not change which rules fire, or the same word
  gets two answers depending on whether someone typed the dots.
"""

from __future__ import annotations

import contextlib
import dataclasses
import itertools
import warnings

import ipakit
import pytest
from ipakit import rules as R
from ipakit.form import declared_prosody, split_prosody, with_prosody

from tests.corpus import assert_swept, prosody_bearing_units, self_spelling_phones

FEATURES = ipakit.load_ipa_features()

FLAPPING = "t -> [manner=tap voiced=+] / [vowel stress=primary] _ [vowel] ; flapping"
VOICING = "[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing"
GLOTTALLING = "t -> ʔ / _ # ; glottalling"

#: Every declared separator, read from ``<separators>`` rather than
#: written out, so declaring a tier above ``word`` puts its mark into
#: these sweeps without this file being edited.
SEPARATORS = tuple(FEATURES.separators)

#: What can stand at a form edge. Whitespace is the one mark that is NOT
#: declared: ``form.units()`` treats it as an edge of the strongest
#: declared level, which is a code-side convention rather than something
#: ``ipa.xml`` says. Named here so it is visible instead of smuggled.
UNDECLARED_EDGE_MARK = " "
EDGE_MARKS = (*SEPARATORS, UNDECLARED_EDGE_MARK)

#: Every mark that reads as a boundary unit: the declared separators plus
#: the declared break and linking marks. Off the declaration rather than
#: listed, so a newly declared mark is swept without this file changing.
BOUNDARY_MARKS = (*SEPARATORS, *R.boundary_marks(FEATURES))


def _optional_everywhere(mark: str) -> bool:
    """Whether a mark is notation a rule steps over, or a real edge.

    Read off ``Unit.transparent``, which reads the declared ``level``, so
    "the dot is optional and the word mark is not" is not restated here.
    """
    return R.units(mark, FEATURES)[0].transparent


def _phones() -> list[str]:
    """The shared enumeration; see tests/corpus.py for why it is shared."""
    return self_spelling_phones()


@contextlib.contextmanager
def _quiet():  # type: ignore[no-untyped-def]
    """Silence the read's own warnings, which a sweep over lossy input
    would otherwise drown in. What the read discarded is pinned separately,
    so the warning is not being taken on trust here."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield


class TestAFormNoRuleReachesSpellsBackOutUnchanged:
    """The round trip ``segments()`` cannot make."""

    def test_every_registered_phone_round_trips(self):
        phones = _phones()
        assert_swept(len(phones), phones)
        bad = [p for p in phones if R.spell(R.units(p, FEATURES)) != p]
        assert bad == [], f"{len(bad)} phones lost their spelling: {bad[:5]}"

    @pytest.mark.parametrize("decoration", ["#{}#", "{}.{}", "{} {}", "#{}.{}#", "{}"])
    def test_boundaries_survive(self, decoration):
        """The property that motivated a separate unit layer."""
        checked = 0
        for phone in _phones():
            form = decoration.format(phone, phone)
            assert R.spell(R.units(form, FEATURES)) == form, form
            checked += 1
        assert_swept(checked, _phones())

    def test_segments_is_the_one_that_loses_them(self):
        """Pins *why* this layer exists, so the reason cannot go stale."""
        form = "#kæt.dɒɡ#"
        assert ipakit.to_ipa(ipakit.segments(form)) != form
        assert R.spell(R.units(form, FEATURES)) == form

    def test_an_empty_rule_set_changes_nothing(self):
        empty = R.RuleSet(rules=())
        checked = 0
        for phone in _phones():
            form = f"#{phone}.{phone}#"
            assert empty.apply(form, FEATURES) == form
            checked += 1
        assert_swept(checked, _phones())


class TestStressIsNotPartOfAPhonesIdentity:
    """``ˈa`` is the phone ``a``, wearing stress."""

    def test_a_literal_matches_its_stressed_spelling(self):
        checked = 0
        for phone in _phones():
            marked = f"ˈ{phone}"
            items = R.units(marked, FEATURES)
            if len(items) != 1 or not items[0].segment:
                continue
            if items[0].prosody.get("stress") != "primary":
                continue  # the mark did not land on this unit
            assert R._pattern(phone, FEATURES).matches(items[0], FEATURES), marked
            checked += 1
        # A leading mark binds only a nucleus, so the sweep covers exactly the
        # syllabic inventory; a count drift means the binding rule changed.
        assert checked == 39, f"sweep covered {checked} nuclei, expected 39"

    def test_prosody_is_still_askable(self):
        stressed = R.units("kˈæt", FEATURES)[1]
        plain = R.units("kæt", FEATURES)[1]
        asks = R._pattern("[vowel stress=primary]", FEATURES)
        assert asks.matches(stressed, FEATURES)
        assert not asks.matches(plain, FEATURES)

    def test_a_feature_change_keeps_the_prosody(self):
        """Rewriting the segment must not strip the stress it wore.

        Uses a change the inventory can actually spell: an earlier
        version asked for ``backness=back`` on ``æ``, which respells to
        nothing, so the rule fired no edits and the assertions held of
        the unmodified input while pinning nothing.
        """
        assert FEATURES.respell("a", backness="back") == "ɑ", "premise moved"
        spec = "[vowel] -> [backness=back] / _ [manner=plosive]"
        assert ipakit.derive("kˈat", spec).fired, "rule did not fire; test is vacuous"
        assert ipakit.rewrite("kˈat", spec) == "kˈɑt"
        assert ipakit.rewrite("kˈaːt", spec) == "kˈɑːt"
        assert ipakit.rewrite("kat", spec) == "kɑt"

    def test_the_prosodic_namespace_is_read_from_the_declaration(self):
        """No list of prosodic feature names is restated in the module."""
        declared = {
            n
            for n, f in FEATURES.features.items()
            if getattr(f, "mode", None) == "prosodic"
        }
        assert "stress" in declared and "length" in declared
        for name in declared:
            assert R._is_prosodic(name, FEATURES)
        assert not R._is_prosodic("manner", FEATURES)


class TestOptionalNotationDoesNotChangeWhatFires:
    """The dot is spelling, not structure."""

    @pytest.mark.parametrize(
        "without,with_dot",
        [("bˈʌtɚ", "bˈʌ.tɚ"), ("ata", "a.ta"), ("atapa", "a.ta.pa")],
    )
    def test_dots_are_transparent_to_context(self, without, with_dot):
        for spec in (FLAPPING, VOICING):
            a = ipakit.rewrite(without, spec)
            b = ipakit.rewrite(with_dot, spec)
            assert a == b.replace(".", ""), f"{spec}: {a!r} vs {b!r}"

    def test_a_rule_may_still_name_the_boundary(self):
        """Transparent by default is not the same as unreachable."""
        rule = R.parse("t -> ʔ / _ . ; before a break", FEATURES)
        assert ipakit.rewrite("at.a", rule) == "aʔ.a"
        assert ipakit.rewrite("ata", rule) == "ata"

    def test_a_word_edge_is_opaque(self):
        """Context does not step over ``#`` the way it steps over ``.``."""
        rule = R.parse(VOICING, FEATURES)
        assert ipakit.rewrite("ata", rule) == "ada"
        assert ipakit.rewrite("at#a", rule) == "at#a"

    def test_the_end_of_a_form_is_a_word_edge(self):
        """``_ #`` fires without a ``#`` having been typed."""
        assert ipakit.rewrite("kæt", GLOTTALLING) == "kæʔ"
        assert ipakit.rewrite("kæt#", GLOTTALLING) == "kæʔ#"
        assert ipakit.rewrite("kætə", GLOTTALLING) == "kætə"


class TestRecognitionAndActionSeparate:
    """The two halves are usable apart, and agree when composed."""

    def test_a_query_answers_without_any_rewrite(self):
        rule = R.parse(VOICING, FEATURES)
        sites = rule.query.sites(R.units("atapa", FEATURES), FEATURES)
        assert [(s.start, s.end) for s in sites] == [(1, 2), (3, 4)]

    def test_edits_land_on_the_sites_recognition_found(self):
        rule = R.parse(VOICING, FEATURES)
        for form in ("atapa", "a.ta.pa", "ata#apa"):
            items = R.units(form, FEATURES)
            recognized = {(s.start, s.end) for s in rule.recognize(items, FEATURES)}
            edited = {(e.start, e.end) for e in rule.edits(items, FEATURES)}
            # A subset claim is satisfied by the empty set, so the floor
            # is what stops this passing when no edit is produced at all.
            assert edited, f"no edits for {form!r}; the subset claim is vacuous"
            assert edited <= recognized, form

    def test_a_site_records_which_neighbors_licensed_it(self):
        rule = R.parse(VOICING, FEATURES)
        (site,) = rule.recognize("ata", FEATURES)
        assert site.left == (0,) and site.right == (2,)

    def test_an_action_that_cannot_be_spelled_does_not_fire(self):
        """The inventory decides; a rule never invents a symbol."""
        assert FEATURES.respell("t", manner="tap") is None
        assert ipakit.rewrite("ata", "t -> [manner=tap] / [vowel] _ [vowel]") == "ata"

    def test_recognition_does_not_mutate_the_form(self):
        items = R.units("atapa", FEATURES)
        before = R.spell(items)
        R.parse(VOICING, FEATURES).recognize(items, FEATURES)
        assert R.spell(items) == before


class TestARuleMatchesASnapshotOfItsInput:
    """A rule cannot read its own output, so a pass terminates."""

    def test_a_rule_does_not_feed_itself(self):
        """Were sites found live, this would spread down the whole word."""
        rule = R.parse("a -> e / e _ ; raising", FEATURES)
        assert ipakit.rewrite("eaaa", rule) == "eeaa"

    def test_all_sites_are_found_before_any_is_rewritten(self):
        rule = R.parse(VOICING, FEATURES)
        out = ipakit.rewrite("atapaka", rule)
        assert out == "adabaɡa"  # IPA U+0261, not ASCII 'g'

    def test_ordering_is_where_feeding_lives(self):
        """The two orders must differ, or the test shows nothing.

        An earlier version asserted both orders equal on a form where
        flapping could not fire at all, so it demonstrated that ordering
        made no difference -- the opposite of its name.
        """
        raising = "a -> i / _ t ; raising"
        glottal = "t -> ʔ / i _ ; glottalling"
        fed = ipakit.ruleset(f"{raising}\n{glottal}").apply("at", FEATURES)
        starved = ipakit.ruleset(f"{glottal}\n{raising}").apply("at", FEATURES)
        # Ordered first, raising creates the environment glottalling needs.
        assert fed == "iʔ"
        # Ordered second, it arrives too late: the rule has already looked.
        assert starved == "it"
        assert fed != starved


class TestInsertionAndDeletion:
    def test_epenthesis_inserts_between_the_named_context(self):
        assert (
            ipakit.rewrite("ktm", "∅ -> ə / [manner=plosive] _ [manner=plosive]")
            == "kətm"
        )

    def test_elision_removes_the_target(self):
        assert ipakit.rewrite("atəm", "ə -> ∅ / [vowel] [manner=plosive] _") == "atm"

    def test_null_spellings_are_interchangeable(self):
        for null in ("∅", "0", "Ø"):
            assert (
                ipakit.rewrite("atəm", f"ə -> {null} / [vowel] [manner=plosive] _")
                == "atm"
            )

    def test_an_insertion_reports_as_one(self):
        (edit,) = R.parse(
            "∅ -> ə / [manner=plosive] _ [manner=plosive]", FEATURES
        ).edits("ktm", FEATURES)
        assert edit.is_insertion and edit.before == "" and edit.after == "ə"

    def test_a_deletion_reports_as_one(self):
        (edit,) = R.parse("ə -> ∅ / [vowel] [manner=plosive] _", FEATURES).edits(
            "atəm", FEATURES
        )
        assert edit.is_deletion and edit.after == ""


class TestTheTraceSaysWhatHappened:
    def test_a_derivation_records_every_rule_whether_or_not_it_fired(self):
        derivation = ipakit.derive("kˈæt", f"{VOICING}\n{GLOTTALLING}")
        assert len(derivation.steps) == 2
        assert [s.fired for s in derivation.steps] == [False, True]
        assert len(derivation.fired) == 1

    def test_an_edit_names_its_rule_and_position(self):
        (edit,) = ipakit.derive("kæt", GLOTTALLING).edits
        assert edit.rule == "glottalling"
        assert (edit.before, edit.after, edit.start) == ("t", "ʔ", 2)

    def test_the_trace_is_readable(self):
        text = ipakit.derive("kæt", GLOTTALLING).trace()
        assert "glottalling" in text and "kæʔ" in text

    def test_a_derivation_that_fires_nothing_says_so(self):
        derivation = ipakit.derive("sis", GLOTTALLING)
        assert derivation.result == "sis"
        assert derivation.fired == ()
        assert "no rule fired" in derivation.trace()


class TestTheTraceListsItsRulesInOneColumn:
    """Every rule name starts at the same column, in either mode.

    Under ``all_steps`` the marker for a rule that did nothing used to be
    a *prefix*, so a name sat at column 2 or at column 15 depending on
    whether its rule had fired -- and the column a reader scans down to
    find a rule by name was the one that moved. The marker follows the
    name now, which is also what leaves the default output
    byte-identical: every step that mode shows has fired, so no marker is
    written at all.

    Stated over the derivation's own step names rather than over a pinned
    listing, so it holds for any rule set rather than for this one.
    """

    #: A cascade with one rule that fires on this form and one that does not.
    CASCADE = R.RuleSet.parse(f"{FLAPPING}\n{GLOTTALLING}", FEATURES)
    FORM = "bˈʌtɚ"

    def _heads(self, all_steps):
        derivation = self.CASCADE.derive(self.FORM, FEATURES)
        shown = derivation.steps if all_steps else derivation.fired
        lines = derivation.trace(all_steps=all_steps).splitlines()
        # The first line is the form as the rules read it; each step
        # contributes exactly three.
        assert lines[0] == derivation.start
        assert len(lines) == 1 + 3 * len(shown), lines
        return shown, [lines[1 + 3 * i] for i in range(len(shown))]

    def test_the_listing_has_both_kinds_of_step(self):
        shown, _ = self._heads(all_steps=True)
        assert {s.fired for s in shown} == {True, False}

    @pytest.mark.parametrize("all_steps", [False, True])
    def test_every_name_starts_at_column_two(self, all_steps):
        shown, heads = self._heads(all_steps)
        for step, head in zip(shown, heads, strict=True):
            assert head.startswith("  " + step.rule), head

    def test_the_marker_follows_the_name_and_only_where_nothing_changed(self):
        shown, heads = self._heads(all_steps=True)
        for step, head in zip(shown, heads, strict=True):
            assert ("no change" in head) is not step.fired, head
            assert head.startswith("  " + step.rule), head

    def test_the_default_listing_is_the_all_listing_minus_what_did_nothing(self):
        """Byte-identical, which is the point of marking after the name."""
        quiet = self.CASCADE.derive(self.FORM, FEATURES).trace().splitlines()
        loud = self.CASCADE.derive(self.FORM, FEATURES).trace(all_steps=True)
        kept = [line for line in loud.splitlines() if "(no change)" not in line]
        assert kept[: len(quiet)] == quiet


class TestTheNotation:
    @pytest.mark.parametrize("arrow", R.ARROWS)
    def test_every_declared_arrow_parses(self, arrow):
        rule = R.parse(f"t {arrow} ʔ / _ #", FEATURES)
        assert rule.becomes == "ʔ"

    def test_a_rule_may_be_named(self):
        assert R.parse("t -> ʔ / _ # ; glottalling", FEATURES).name == "glottalling"

    def test_an_unnamed_rule_is_named_by_its_source(self):
        assert R.parse("t -> ʔ / _ #", FEATURES).name == "t -> ʔ / _ #"

    def test_bare_and_keyed_terms_may_be_mixed(self):
        pattern = R._pattern("[vowel stress=primary]", FEATURES)
        assert pattern.seg_required.get("manner") == "vowel"
        assert pattern.pro_required.get("stress") == "primary"

    def test_a_rule_set_skips_blanks_and_comments(self):
        parsed = ipakit.ruleset(f"# a comment\n\n{GLOTTALLING}\n")
        assert len(parsed) == 1

    @pytest.mark.parametrize(
        "bad,because",
        [
            ("t ʔ / _ #", "no rewrite arrow"),
            ("-> ʔ / _ #", "nothing on the left"),
            ("t -> / _ #", "nothing on the right"),
            ("t -> ʔ / #", "no '_'"),
            ("∅ -> ∅ / _ #", "nothing as nothing"),
            ("t -> [nonsense=1] / _ #", "undeclared"),
            ("t -> [vowel] / _ #", "every term must be"),
            ("t -> ʔ / [ _ #", "unbalanced"),
        ],
    )
    def test_a_malformed_rule_says_what_is_wrong(self, bad, because):
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert because in str(caught.value), str(caught.value)

    def test_a_query_that_would_match_everything_is_refused(self):
        """An unresolved class is a typo, not a wildcard."""
        with pytest.raises(R.RuleError):
            R._pattern("[definitely-not-a-feature]", FEATURES)

    def test_a_separators_notation_and_level_are_both_read_from_the_data(self):
        """Not ``if text == "#": boundary = "word"``.

        ``<separator name="#" level="word"/>`` says both the notation and
        the level, so a newly declared tier gets notation that parses
        instead of a mark nothing understands. Swept over the declaration
        rather than spot-checked, so a tier cannot be added past it.
        """
        assert len(SEPARATORS) >= 2, f"only {len(SEPARATORS)} separators declared"
        for mark in SEPARATORS:
            declared = (FEATURES.separators[mark].features or {}).get("level")
            assert declared, f"{mark!r} declares no level"
            assert R._pattern(mark, FEATURES).boundary == declared, mark

    def test_the_form_edge_is_the_tier_a_separator_spells(self):
        """One read, not two that agree by habit -- and they did not.

        The engine used to answer this itself, as the top of the ordinal
        ``level`` ladder, while ``form.edge_level()`` answered "the
        strongest level a **separator** spells". Those are different
        questions and already gave different answers -- ``utterance``
        against ``word`` -- because ``|`` and ``‖`` declare levels above
        ``word`` and no separator spells one. It was harmless only
        because a level pattern is built for a separator, so the virtual
        edge was never tested above ``word``; declaring a separator above
        it would have made the disagreement real, and the comment
        promising the two would be reconciled was in the function that
        would not have noticed.
        """
        strongest = R.edge_level(FEATURES)
        assert R._edge_level(FEATURES) == strongest
        assert strongest != FEATURES.features["level"].values[-1], "the two differ"
        for mark in SEPARATORS:
            level = (FEATURES.separators[mark].features or {}).get("level")
            assert R._reaches(strongest, level, FEATURES), level
            # An untyped edge matches every separator's own notation.
            assert ipakit.rewrite("kæt", f"t -> ʔ / _ {mark}") == "kæʔ", mark


class TestTheFlatAPI:
    def test_rewrite_accepts_notation_a_rule_or_a_set(self):
        rule = ipakit.rule(GLOTTALLING)
        assert ipakit.rewrite("kæt", GLOTTALLING) == "kæʔ"
        assert ipakit.rewrite("kæt", rule) == "kæʔ"
        assert ipakit.rewrite("kæt", ipakit.ruleset(GLOTTALLING)) == "kæʔ"

    def test_the_default_inventory_is_used_when_none_is_named(self):
        assert ipakit.rule(GLOTTALLING).recognize("kæt")
        assert R.units("kæt")

    def test_units_is_the_boundary_keeping_split(self):
        assert [u.text for u in ipakit.units("#kæt#")] == list("#kæt#")


class TestWhatMutationTestingFoundUnguarded:
    """Behaviors that survived a deliberate break in the source.

    Each test here exists because the property it names was true but
    unpinned: mutating the source to violate it left the suite green.
    """

    def test_the_splice_order_survives_more_than_one_site(self):
        """Every earlier insertion/deletion case had exactly one site.

        With one site, splicing left-to-right and rightmost-first agree,
        so ``_apply_edits``' claim that it works rightmost-first "so
        indices hold" was unobservable.
        """
        assert (
            ipakit.rewrite("atəmatəm", "ə -> ∅ / [vowel] [manner=plosive] _")
            == "atmatm"
        )
        assert (
            ipakit.rewrite("ktkt", "∅ -> ə / [manner=plosive] _ [manner=plosive]")
            == "kətəkət"
        )
        assert (
            ipakit.rewrite("ktmktm", "∅ -> ə / [manner=plosive] _ [manner=nasal]")
            == "ktəmktəm"
        )

    def test_the_start_of_a_form_is_a_word_edge_too(self):
        """Only the right edge was tested, so ``# _`` could have died silently."""
        assert ipakit.rewrite("tæt", "t -> ʔ / # _") == "ʔæt"
        assert ipakit.rewrite("ætæ", "t -> ʔ / # _") == "ætæ"

    @pytest.mark.parametrize("side", ["% _", "_ %"])
    def test_the_any_boundary_pattern_matches_an_implicit_edge(self, side):
        """``%`` had no test at all; its branch never executed."""
        rule = R.parse(f"t -> ʔ / {side}", FEATURES)
        assert ipakit.rewrite("tæt", rule) != "tæt"

    def test_a_space_is_opaque_like_a_word_mark(self):
        """``transparent``'s docstring names whitespace; only ``#`` was tested."""
        assert ipakit.rewrite("at a", VOICING) == "at a"
        assert ipakit.rewrite("ata", VOICING) == "ada"

    def test_an_insertion_does_not_double_across_a_dot(self):
        """The transparency sweep covered only substitutions.

        A gap-anchored rule sees two gaps around a transparent boundary,
        both scanning to the same neighbors, so an unguarded scan
        inserted twice where the undotted spelling inserted once.
        """
        spec = "∅ -> ə / [vowel] _ [vowel]"
        for plain, dotted in (("aa", "a.a"), ("aia", "a.i.a")):
            got_plain = ipakit.rewrite(plain, spec)
            got_dotted = ipakit.rewrite(dotted, spec).replace(".", "")
            assert got_plain == got_dotted, f"{got_plain!r} vs {got_dotted!r}"

    def test_transparency_holds_for_every_kind_of_rule(self):
        """Swept over all four rule kinds, not just substitution."""
        specs = [
            VOICING,
            "t -> ʔ / [vowel] _ [vowel]",
            "∅ -> ə / [vowel] _ [vowel]",
            "t -> ∅ / [vowel] _ [vowel]",
        ]
        checked = 0
        for spec in specs:
            for plain, dotted in (("ata", "a.ta"), ("atata", "a.ta.ta"), ("aa", "a.a")):
                a = ipakit.rewrite(plain, spec)
                b = ipakit.rewrite(dotted, spec).replace(".", "")
                assert a == b, f"{spec}: {plain!r}->{a!r} vs {dotted!r}->{b!r}"
                checked += 1
        assert checked == 12, "sweep did not run"


class TestARuleThatCannotWorkIsRefused:
    """Escapes that used to parse and then quietly do nothing."""

    @pytest.mark.parametrize(
        "bad,because",
        [
            (". -> ʔ / _", "a relation cannot become a segment"),
            ("t -> . / _", "nor a segment a relation"),
            ("t -> .a", "nor half of one"),
            (". -> [level=word]", "a boundary has no feature bundle to change"),
            (". -> %", "'%' is a wildcard, so it names nothing to write"),
        ],
    )
    def test_a_boundary_and_a_segment_are_not_exchangeable(self, bad, because):
        """What is left of the boundary refusal once both ends of it agree.

        A boundary may be written, unwritten and restated at another level
        -- ``TestABoundaryIsWrittenAndUnwrittenAlike`` below. What it may
        not do is change places with a segment, because the invariant that
        makes a boundary rewrite a *boundary* rewrite is that the segmental
        string does not move.
        """
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert "boundary" in str(caught.value), because

    @pytest.mark.parametrize(
        "bad", ["[mannr=plosive]", "[nonsense=1]", "[manner!=vowel]"]
    )
    def test_an_undeclared_feature_key_is_refused_on_the_left(self, bad):
        """It used to build a constraint no phone could satisfy, silently."""
        with pytest.raises(R.RuleError) as caught:
            R._pattern(bad, FEATURES)
        assert "undeclared" in str(caught.value)

    def test_the_left_and_right_of_the_arrow_are_equally_strict(self):
        """The right side already refused this; the left did not."""
        for side in ("[mannr=plosive] -> [voiced=+] / _ #", "t -> [mannr=x] / _ #"):
            with pytest.raises(R.RuleError):
                R.parse(side, FEATURES)

    @pytest.mark.parametrize(
        "bad,because",
        [
            ("Q -> ʔ", "an unread target matched nothing, silently"),
            ("t -> ʔ / _ Q", "and so did an unread context item"),
            ("t -> ʔ / _ zzz", "a literal naming three units cannot hold either"),
            ("t -> Q", "and this one DELETED rather than not firing"),
            ("∅ -> Q / a _ a", "an insertion of nothing is not an insertion"),
        ],
    )
    def test_an_unregistered_literal_is_refused_on_both_sides(self, bad, because):
        """The third member of the family, and the only one still open.

        ``[mannr=plosive]`` (undeclared key) and ``[manner=obstruent]``
        (undeclared value) both built constraints nothing could satisfy
        and are refused above. A bare glyph the inventory does not
        register is the same mistake spelled a third way, and the read's
        own "dropped 1 unregistered symbol" reports the symbol without
        reporting what it did to the rule.
        """
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert "registers" in str(caught.value) or "units" in str(caught.value), because

    def test_an_unread_right_hand_side_was_a_deletion_and_not_a_no_op(self):
        """The serious one, pinned as the wrong answer it gave.

        ``t -> Q`` read as zero units, so the replacement was empty and
        the rule did what ``t -> ∅`` does: not a rule that failed to fire
        but a rule that changed operation. Deletion has a spelling, and
        this was not it.
        """
        with pytest.raises(R.RuleError):
            R.parse("t -> Q", FEATURES)
        assert ipakit.rewrite("kæt", "t -> ∅") == "kæ", "which is how it is written"

    def test_the_old_name_separator_is_caught_by_the_same_guard(self):
        """A migration hazard, and why the refusal names the separator.

        ``|`` was the name separator until it turned out to be a declared
        prosodic break -- ``t -> ʔ / _ |`` was swallowed as a name and the
        rule became unconditional. The fix made ``;`` the separator, and
        left the opposite failure behind: a rule still written the old way
        parses its own name as context items and matches nothing. The name
        is an unregistered literal, so it is caught for free -- but
        "unregistered literal 'flapping'" is a puzzling error for someone
        whose mistake was the separator, so the message says both.
        """
        with pytest.raises(R.RuleError) as caught:
            R.parse("t -> ʔ / _ # | flapping", FEATURES)
        assert "';'" in str(caught.value), "the message has to name the separator"
        assert R.parse("t -> ʔ / _ # ; flapping", FEATURES).name == "flapping"

    def test_the_guard_refuses_nothing_the_inventory_can_spell(self):
        """A refusal that is too wide is the same class of defect.

        Swept over the inventory on both sides of the arrow rather than
        spot-checked, because what would make this guard wrong is one
        registered spelling it happens to read as two units.
        """
        checked = identity = 0
        bad: list[str] = []
        for phone in _phones():
            for spec in (f"{phone} -> ʔ", f"t -> {phone}", f"t -> ʔ / {phone} _"):
                checked += 1
                left, _, right = spec.partition(" -> ")
                if left == right.partition(" / ")[0]:
                    # 'ʔ -> ʔ' and 't -> t' fall out of this enumeration and
                    # are refused by a different guard for a different
                    # reason: they write back what they matched, so they can
                    # never edit. See TestARuleMustBeAbleToEdit.
                    identity += 1
                    continue
                try:
                    R.parse(spec, FEATURES)
                except R.RuleError as refused:
                    bad.append(f"{spec}: {refused}")
        assert identity == 2, "the two identity rules this enumeration makes"
        assert_swept(checked, _phones())
        assert bad == [], f"{len(bad)} of {checked} refused, first: {bad[:3]}"


#: Every shape a bracketed right-hand side takes, one line each: a
#: segmental bundle, both spellings of the empty left-hand side, an
#: assigned prosody, a cleared one, a second prosodic feature, and a
#: change naming an agreement variable the context really does bind.
INSERTED_CHANGES = [
    ("∅ -> [manner=plosive] / a _ t", "a segmental bundle"),
    ("∅ -> [voiced=+]", "one with no context to hide behind"),
    ("0 -> [manner=plosive] / a _ t", "the ASCII spelling of the same rule"),
    ("∅ -> [stress=primary] / # _", "assigning prosody"),
    ("∅ -> [stress=∅] / # _", "clearing it"),
    ("∅ -> [length=long] / a _ t", "and the other prosodic feature"),
    ("∅ -> [place=α] / [place=α] _ a", "an agreement the context does bind"),
]


class TestAnInsertionHasNoUnitToModify:
    """``∅ -> [...]``, pinned as the answer it used to give.

    ``rewrite("ata", "∅ -> [manner=plosive] / a _ t")`` answered
    ``'ata'``: the rule parsed, recognized its site, declined to build an
    edit, and reported nothing. A bracketed right-hand side *modifies*
    the unit the rule matched, and an insertion matches none -- so the
    modification had no referent, and a rule that could never fire said
    so at no point.
    """

    @pytest.mark.parametrize("bad,shape", INSERTED_CHANGES)
    def test_an_inserted_feature_change_was_a_rule_that_fired_and_did_nothing(
        self, bad, shape
    ):
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        message = str(caught.value)
        assert "insert" in message, shape
        assert "∅ -> t" in message, "the message has to name a spelling that works"

    def test_the_spelling_the_message_recommends_actually_inserts(self):
        """Otherwise the refusal sends its reader to a second dead end.

        The two the message offers: a bare literal, and a literal naming
        prosody -- which is what someone reaching for ``[stress=primary]``
        on an insertion wanted.
        """
        assert ipakit.rewrite("ata", "∅ -> t / a _ t") == "atta"
        assert ipakit.rewrite("at", "∅ -> ˈa / # _") == "ˈaat"

    @pytest.mark.parametrize(
        "form,spec,want",
        [
            ("aʃa", "ʃ -> [voiced=+]", "aʒa"),
            ("aʈa", "ʈ -> [voiced=+]", "aɖa"),
            ("kˈat", "[vowel] -> [stress=∅]", "kat"),
        ],
    )
    def test_a_substitution_still_modifies_the_unit_it_matched(self, form, spec, want):
        """The half that works, and why the refusal has to be narrow.

        A refusal satisfied by refusing everything would pass the tests
        above and take the notation's one capture with it: ``ʒ`` keeps
        grooved, postalveolar and fricative from the ``ʃ`` that stood
        there, and ``ɖ`` keeps retroflex.
        """
        assert ipakit.rewrite(form, spec) == want

    def test_the_refusal_reaches_no_substitution_the_engine_can_spell(self):
        """Swept over the inventory: a guard too wide is the same defect."""
        checked = 0
        bad: list[str] = []
        for phone in _phones():
            for spec in (
                f"{phone} -> [voiced=+]",
                f"[vowel] -> [voiced=+] / {phone} _",
            ):
                try:
                    R.parse(spec, FEATURES)
                except R.RuleError as refused:
                    bad.append(f"{spec}: {refused}")
                checked += 1
        assert_swept(checked, _phones())
        assert bad == [], f"{len(bad)} of {checked} refused, first: {bad[:3]}"

    def test_a_bundle_describes_a_class_and_so_cannot_name_what_to_insert(self):
        """Why refuse, rather than resolve the bundle to a segment.

        The reading that would make ``∅ -> [manner=plosive]`` work is
        "insert the segment this bundle names", and a bundle does not name
        one at any degree of specification. Narrowed to a manner, a place
        and a voicing it still holds several phones; and a phone's own
        complete declared bundle need not pick that phone out again, since
        a tied diphthong states its first element's features. An engine
        resolving a bundle to a segment would be choosing, not reading.
        """
        narrow = FEATURES.phones_matching(
            {"manner": "plosive", "place": "alveolar", "voiced": "-"}
        )
        assert len(narrow) > 1, f"a narrowed query picked out {narrow}"
        shared = []
        for phone in _phones():
            bundle = {
                key: value
                for key, value in FEATURES.get_features(phone).items()
                if key in FEATURES.features
                and FEATURES.features[key].mode != "prosodic"
            }
            if len(FEATURES.phones_matching(bundle)) > 1:
                shared.append(phone)
        assert shared, "no complete bundle is shared; the docstring needs re-reading"

    def test_no_insertion_parses_into_a_rule_that_recognizes_and_never_edits(self):
        """The sweep, rather than the one input the defect was found on.

        Every left-hand side the notation distinguishes against every
        right-hand side, over forms carrying prosody, a zero, a dot and a
        break mark. What is asserted is the shape: no *insertion* survives
        parsing as a rule that finds sites and produces no edit.

        The family that does survive is named rather than left implied,
        because it is a different one -- a substitution whose change is
        already true (``t -> t``), or whose result the inventory cannot
        spell (``[vowel] -> [manner=plosive]``). Both are per-site and
        per-result decisions docs/rules.md documents, and such a rule goes
        on firing wherever its change does land, which is why they cannot
        be refused at parse the way this one can.
        """
        lhs = (
            "∅",
            "0",
            "t",
            "a",
            "aː",
            "ˈa",
            "[vowel]",
            "[manner=plosive]",
            "[-vowel]",
            "[zero]",
            ".",
            "#",
            "%",
            "|",
        )
        rhs = (
            "t",
            "ə",
            "ˈa",
            "aː",
            "ts",
            "∅",
            "[zero]",
            "[voiced=+]",
            "[manner=plosive]",
            "[stress=primary]",
            "[stress=∅]",
            "[length=long]",
            ".",
            "#",
        )
        contexts = ("", " / a _ t", " / _ #", " / # _", " / [vowel] _ [vowel]")
        probes = ("ata", "aːtːa", "le∅ʃ", "a.ta", "a|ta", "kˈat", "at")
        checked = 0
        silent: list[str] = []
        for left in lhs:
            for right in rhs:
                for context in contexts:
                    spec = f"{left} -> {right}{context}"
                    checked += 1
                    try:
                        rule = R.parse(spec, FEATURES)
                    except R.RuleError:
                        continue
                    with _quiet():
                        sites = sum(len(rule.recognize(p)) for p in probes)
                        edits = sum(len(rule.edits(p)) for p in probes)
                    if sites and not edits:
                        silent.append(spec)
        assert checked == len(lhs) * len(rhs) * len(contexts) > 500, "sweep did not run"
        inserting = [s for s in silent if s.split(" ->")[0] in ("∅", "0")]
        assert inserting == [], f"{len(inserting)} silent insertions: {inserting[:3]}"
        assert (
            silent
        ), "the surviving family is stated as present; if it is gone, say so"

    def test_every_shipped_rule_still_parses(self):
        """A refusal that unloads a shipped set is a finding about the set."""
        checked = 0
        for name in R.available():
            rules = R.shipped(name, FEATURES).rules
            assert rules, f"{name} loaded no rules"
            checked += len(rules)
        assert checked >= 80, f"only {checked} shipped rules parsed"


class TestWhatTheReviewFound:
    """Regressions for defects found by review, each swept where it can be.

    All three were silent: well-formed output, green suite, wrong answer.
    """

    @pytest.mark.parametrize("mark,name", [("ː", "length"), ("˥", "tone")])
    def test_a_literal_rewrite_carries_the_targets_prosody(self, mark, name):
        """The feature-change branch preserved prosody; the literal one did not.

        ``t -> ʔ`` is this module's own headline example, and it silently
        shortened every long segment it rewrote.
        """
        out = ipakit.rewrite(f"kæt{mark}", "t -> ʔ / _ #")
        assert out == f"kæʔ{mark}", f"{name} lost: {out!r}"

    def test_every_prosody_bearing_unit_keeps_it_through_a_literal_rewrite(self):
        checked = lost = 0
        # The written form of the target, so 'ʔ -> ʔ' is not asked. It
        # writes back what it matched and is refused where it is read;
        # what this sweep is about is a rewrite that changes the segment
        # and must leave the prosody where it was.
        rewritten = "ʔ"
        for phone in _phones():
            if phone == rewritten:
                continue
            for mark in ("ː", "˥"):
                unit = f"{phone}{mark}"
                if FEATURES.segment(unit).to_ipa() != unit:
                    continue
                got = ipakit.rewrite(unit, f"{phone} -> {rewritten}")
                checked += 1
                if got and mark not in got:
                    lost += 1
        assert_swept(checked, _phones())
        assert lost == 0, f"{lost} of {checked} units lost their prosody"

    @pytest.mark.parametrize("form", ["kæt", "kæt.", "kæt..", "kæt.#"])
    def test_a_dot_beside_a_word_edge_does_not_block_it(self, form):
        """Naming '#' used to stop the skip, so an adjacent dot hid the edge."""
        assert ipakit.rewrite(form, "t -> ʔ / _ #") == form.replace("t", "ʔ")

    def test_the_virtual_edge_is_reported_as_none_not_a_valid_index(self):
        """-1 is a valid index: a consumer got the form's last unit."""
        (site,) = ipakit.rule("t -> ʔ / _ #").recognize("kæt")
        assert site.right == (None,)
        assert -1 not in site.right, "a sentinel that indexes is not a sentinel"

    def test_optional_notation_never_changes_the_result_anywhere(self):
        """The sweep the earlier transparency test should have been.

        Every rule kind, every form, and a mark inserted at every position
        the mark is *optional notation* -- the earlier version was three
        forms, two rules and the dot alone.

        Which positions those are differs by mark, and that is the point
        rather than an evasion. A dot is optional everywhere: ``bʌtɚ`` and
        ``bʌ.tɚ`` are the same word. A word mark is optional only at an
        **end**, because the form's own edge already is a word boundary --
        typing ``#`` there states what was true anyway. In the middle it
        is information, not notation: ``at#a`` is two words and blocks a
        context that ``ata`` licenses, which is the whole difference
        between a transparent boundary and an opaque one.
        """
        specs = [
            VOICING,
            "t -> ʔ / [vowel] _ [vowel]",
            "t -> ʔ / _ #",
            "t -> ʔ / # _",
            "∅ -> ə / [vowel] _ [vowel]",
            "∅ -> ə / [manner=plosive] _ #",
            "∅ -> ə / # _ [manner=plosive]",
            # The two the edge-redundancy defect lived in: an insertion
            # whose context names a boundary and nothing else. Without
            # them the sweep had no rule that could see the virtual edge
            # and a written mark as two anchors.
            "∅ -> ə / _ #",
            "∅ -> ə / # _",
            "t -> ∅ / [vowel] _ [vowel]",
            # The fourth rule kind, since a boundary may be the target:
            # a rule that unwrites one. It writes no mark of its own, so
            # stripping the written mark from the output compares exactly
            # what such a rule leaves behind, which is the segments.
            ". -> ∅ / [vowel] _ [vowel]",
        ]
        forms = ["ata", "atata", "aa", "kt", "kta", "tat", "ktm", "atapaka"]
        # Shape first: a sweep that lost the transparent mark, or lost
        # every opaque one, would still clear any floor.
        transparent = [m for m in EDGE_MARKS if _optional_everywhere(m)]
        opaque = [m for m in EDGE_MARKS if not _optional_everywhere(m)]
        assert transparent and len(opaque) >= 2, f"{transparent} / {opaque}"

        checked = 0
        per_mark: dict[str, int] = {}
        bad: list[str] = []
        for mark in EDGE_MARKS:
            for spec in specs:
                for form in forms:
                    base = ipakit.rewrite(form, spec)
                    optional = (
                        range(len(form) + 1)
                        if _optional_everywhere(mark)
                        else (0, len(form))
                    )
                    for cut in optional:
                        written = form[:cut] + mark + form[cut:]
                        got = ipakit.rewrite(written, spec).replace(mark, "")
                        checked += 1
                        per_mark[mark] = per_mark.get(mark, 0) + 1
                        if got != base:
                            bad.append(f"{spec}: {form}->{base} vs {written!r}->{got}")
        # Exact, not a floor: 11 rules x 36 positions for each mark that is
        # optional everywhere, and 11 rules x 8 forms x 2 ends for each mark
        # that is only optional at one. A floor cannot tell that a whole
        # rule kind -- or a whole mark -- dropped out, so the per-mark
        # breakdown is asserted too. The literal moves if a tier is
        # declared; the derived total is what states the shape.
        anywhere = len(specs) * sum(len(f) + 1 for f in forms)
        ends = len(specs) * len(forms) * 2
        assert per_mark == {
            **{m: anywhere for m in transparent},
            **{m: ends for m in opaque},
        }, f"sweep skewed: {per_mark}"
        expected = len(transparent) * anywhere + len(opaque) * ends
        assert checked == expected == 748, f"sweep covered {checked}, not {expected}"
        assert bad == [], f"{len(bad)} violations, first: {bad[:3]}"


class TestABoundaryRunIsOneBoundary:
    """**Edge redundancy.** For any rule ``r`` and form ``f`` whose ends
    carry no boundary run::

        r(f) == strip(r("#" + f)) == strip(r(f + "#")) == strip(r("#" + f + "#"))

    A form's end *is* a word boundary whether or not a ``#`` is typed, so
    typing one adds no information and must not change the derivation --
    and neither must doubling it. This is the invariant already fixed for
    the syllable dot, never generalized to ``#``, and it failed for every
    insertion whose context named a boundary: the written mark and the
    virtual edge past it were two anchors, so one phonological position
    yielded two insertions and ``∅ -> ə / # _`` took ``#tæt#`` to
    ``ə#ətæt#ə``.

    Silent, as ever: well-formed output, green suite, wrong answer.
    """

    #: Every rule kind, against every boundary a context can name. The
    #: per-separator contexts are built from the declaration, so a newly
    #: declared tier is swept on both sides and as a run of two; the rest
    #: are the shapes that mix a boundary with a feature query.
    #:
    #: The last two shapes put an item **past** the boundary, which is the
    #: shape every other context here misses: each of the others ends at
    #: the edge, and matching the virtual edge disqualified whatever came
    #: next without asking whether it was optional. So the sweep agreed
    #: with itself while ``t -> d / _ # (z)`` fired on ``at#`` and not on
    #: ``at``. An optional item is the only item that can stand there and
    #: still hold of a form with nothing written at its end, which is why
    #: it is the one that shows this.
    HEADS = ("∅ -> ə", "t -> ʔ", "t -> ∅")
    CONTEXTS = tuple(
        context
        for mark in SEPARATORS
        for context in (
            f"_ {mark}",
            f"{mark} _",
            f"{mark} _ {mark}",
            f"_ {mark} {mark}",
            f"_ {mark} (z)",
            f"(z) {mark} _",
        )
    ) + (
        "_ %",
        "% _",
        "[vowel] _ [vowel]",
        "[manner=plosive] _ #",
        "# _ [manner=plosive]",
    )
    FORMS = ("ata", "atata", "aa", "kt", "kta", "tat", "ktm", "atapaka")
    #: A run of one and of two, for every mark that can carry a form edge.
    RUNS = tuple(mark * n for mark in EDGE_MARKS for n in (1, 2))

    @pytest.mark.slow
    def test_the_invariant_over_every_rule_kind_and_every_boundary(self):
        """The sweep. ``strip`` removes the run that was written and no
        more, which is what makes this sharp: an insertion that lands
        *outside* the mark fails on the prefix check rather than being
        stripped away with it.
        """
        checked = 0
        bad: list[str] = []
        for head in self.HEADS:
            for context in self.CONTEXTS:
                spec = f"{head} / {context}"
                for form in self.FORMS:
                    base = ipakit.rewrite(form, spec)
                    for run in self.RUNS:
                        for pre, post in ((run, ""), ("", run), (run, run)):
                            written = pre + form + post
                            out = ipakit.rewrite(written, spec)
                            checked += 1
                            if not (out.startswith(pre) and out.endswith(post)):
                                bad.append(f"{spec}: {written!r} -> {out!r} escaped")
                                continue
                            inner = out[len(pre) : len(out) - len(post) or None]
                            if inner != base:
                                bad.append(
                                    f"{spec}: {form}->{base} vs {written!r}->{out!r}"
                                )
        # Shape, then the count: every declared separator has to reach the
        # corpus on both sides, or a sweep that quietly dropped a tier
        # would still clear a floor.
        for mark in SEPARATORS:
            assert f"_ {mark}" in self.CONTEXTS and f"{mark} _" in self.CONTEXTS
            assert mark * 2 in self.RUNS
            # And one shape per mark with an item past the edge, on each
            # side, or the sweep goes back to testing only contexts that
            # stop at the boundary.
            assert f"_ {mark} (z)" in self.CONTEXTS
            assert f"(z) {mark} _" in self.CONTEXTS
        # Exact, not a floor: 51 rules x 8 forms x 18 decorations. A floor
        # cannot tell that a rule kind or a mark left the sweep. The
        # literal moves if a tier is declared; the derived total is the
        # claim, and the literal is what says it has not moved yet.
        expected = (
            len(self.HEADS) * len(self.CONTEXTS) * len(self.FORMS) * len(self.RUNS) * 3
        )
        assert checked == expected == 7344, f"sweep covered {checked}, not {expected}"
        assert bad == [], f"{len(bad)} violations, first: {bad[:3]}"

    def test_the_corpus_the_review_measured(self):
        """The reproduction, kept at the size it was reported at.

        Two heads by three boundary contexts by ten forms by three
        decorations is 180 comparisons, of which 90 failed -- every one an
        insertion, and substitutions and deletions clean. Pinned as the
        exact corpus so the before number stays checkable.
        """
        specs = [
            f"{h} / {c}" for h in ("∅ -> ə", "t -> ʔ") for c in ("# _", "_ #", "# _ #")
        ]
        forms = [
            "ata",
            "atata",
            "aa",
            "kt",
            "kta",
            "tat",
            "ktm",
            "atapaka",
            "tæt",
            "kæt",
        ]
        kinds = {s: ipakit.rule(s).inserts for s in specs}
        assert sum(kinds.values()) == 3, "the corpus lost its insertion rules"
        checked = 0
        bad: list[str] = []
        for spec in specs:
            for form in forms:
                base = ipakit.rewrite(form, spec)
                for decoration in ("#{}", "{}#", "#{}#"):
                    written = decoration.format(form)
                    got = ipakit.rewrite(written, spec).replace("#", "")
                    checked += 1
                    if got != base.replace("#", ""):
                        bad.append(f"{spec}: {form}->{base} vs {written}->{got}")
        assert checked == len(specs) * len(forms) * 3 == 180
        assert bad == [], f"{len(bad)} of {checked} violations, first: {bad[:3]}"

    def test_a_written_mark_takes_the_insertion_inside_the_word(self):
        """Which gap the run offers is a choice, and this is it.

        The run's **inner** gap: there is nothing outside the form to
        insert into, and prothesis makes the schwa part of the word.
        Anchoring the outer gap would spell ``ə#tæt#`` -- two words, one of
        them a bare schwa -- rather than ``#ətæt#``.
        """
        assert ipakit.rewrite("#tæt#", "∅ -> ə / # _") == "#ətæt#"
        assert ipakit.rewrite("#tæt#", "∅ -> ə / _ #") == "#tætə#"
        assert ipakit.rewrite("##tæt##", "∅ -> ə / # _") == "##ətæt##"
        assert ipakit.rewrite("##tæt##", "∅ -> ə / _ #") == "##tætə##"

    def test_two_boundary_patterns_in_a_row_never_both_hold(self):
        """A run is one boundary, so a context cannot name two of it.

        ``docs/rules.md`` has always said ``_ # #`` does not match, and it
        was true of ``kæt`` and false of ``kæt#``: the written mark and the
        virtual edge past it counted twice, so typing a redundant final
        ``#`` switched a rule on. The review reported substitution
        violations as zero; this context is where they were not.
        """
        checked = 0
        for form in ("kæt", "kæt#", "kæt##", "kæt.", "#kæt#", "kæt "):
            for spec in ("t -> ʔ / _ # #", "t -> ʔ / # # _", "∅ -> ə / _ # #"):
                assert ipakit.rewrite(form, spec) == form, f"{spec} on {form!r}"
                checked += 1
        assert checked == 18, f"sweep covered {checked}"
        # A non-boundary pattern may still follow one, or this would have
        # been fixed by refusing everything after a boundary.
        assert ipakit.rewrite("kæt#at", "t -> ʔ / _ # [vowel]") == "kæʔ#at"

    def test_an_optional_item_may_stand_past_the_virtual_edge(self):
        """The parity, at the size the report gave it.

        A written mark and the form's own edge are the same boundary, so
        the same rule has to fire against both. It fired against the
        written one and not the virtual one, because matching the edge
        disqualified the next context item before anything asked whether
        the item was optional -- and an optional item that finds nothing
        records ``None`` and the match goes on, which is what the
        :class:`~ipakit.rules.Site` contract already says.
        """
        assert ipakit.rewrite("at", "t -> d / _ #") == "ad"
        assert ipakit.rewrite("at", "t -> d / _ # (z)") == "ad"
        assert ipakit.rewrite("at#", "t -> d / _ # (z)") == "ad#"
        # The mirror: the optional item outside a leading edge.
        assert ipakit.rewrite("ta", "t -> d / (z) # _") == "da"
        assert ipakit.rewrite("#ta", "t -> d / (z) # _") == "#da"
        # One entry per context item, with None where nothing licensed it,
        # so the record stays alignable with the notation.
        (site,) = ipakit.rule("t -> d / _ # (z)").recognize("at")
        assert site.right == (None, None)
        # The run rule is not what was relaxed: an item past the edge that
        # is *not* optional still fails, and a second boundary past it
        # fails whether or not the mark was typed.
        assert ipakit.rewrite("at", "t -> d / _ # [vowel]") == "at"
        for form in ("at", "at#"):
            assert ipakit.rewrite(form, "t -> d / _ # (z) #") == form

    def test_paragoge_still_fires_beside_a_form_final_mark(self):
        """The hazard this fix has twice been broken by.

        Anchoring only the run's first gap loses the gap ``. _`` needs at a
        form-final dot; discarding every gap but the first loses paragoge.
        Both directions are pinned, and each is checked to fire rather than
        merely to agree.
        """
        for form in ("kæt", "kæt.", "kæt..", "kæt#", "kæt "):
            got = ipakit.rewrite(form, "∅ -> ə / _ #")
            assert got != form, f"paragoge did not fire on {form!r}"
            assert got.replace(".", "").replace("#", "").strip() == "kætə", got

    def test_naming_a_margin_keeps_the_gap_after_it(self):
        """The other direction, and the precise question the guard asks.

        ``[vowel] _ [vowel]`` steps over the dot in ``a.a`` and sees the
        same two vowels from either gap, so those are one position and one
        insertion. ``. _`` *names* the margin, and then "after the margin"
        is a position of its own -- an interior margin a rule may condition
        on, which is why the dot is information there and not notation.
        """
        assert ipakit.rewrite("a.a", "∅ -> ə / [vowel] _ [vowel]") == "aə.a"
        assert ipakit.rewrite("a.a", "∅ -> ə / . _") == "əa.əa"
        assert ipakit.rewrite("aa", "∅ -> ə / . _") == "əaa"
        # A run of two is still one margin, so doubling the dot does not
        # double the insertion.
        assert ipakit.rewrite("a..a", "∅ -> ə / . _") == "əa..əa"
        assert ipakit.rewrite("a..a", "∅ -> ə / [vowel] _ [vowel]") == "aə..a"

    def test_the_shipped_set_holds_the_invariant_too(self):
        """Calibration, stated as the property rather than as glyphs.

        The fix reaches exactly two things: the anchor set of an insertion,
        and a context naming two boundaries in a row. **No shipped rule is
        either**, which is why every shipped derivation is byte-identical
        across it -- asserted here rather than assumed, since a set that
        grew an insertion would silently leave this calibration behind.
        The invariant itself is then swept over the shipped cascade, which
        is the one rule set a caller actually runs.
        """
        shipped = R.shipped("american-english", FEATURES)
        assert not any(r.inserts for r in shipped), "a shipped rule now inserts"
        adjacent = [
            r.name
            for r in shipped
            for side in (r.query.left, r.query.right)
            for a, b in zip(side, side[1:], strict=False)
            if a.names_boundary and b.names_boundary
        ]
        assert adjacent == [], f"shipped rules name adjacent boundaries: {adjacent}"

        words = [
            "pˈɪn",
            "spˈɪn",
            "bˈʌtɚ",
            "kˈæt",
            "klˈin",
            "fˈʊl",
            "ˈbʌ.tn",
            "pə.tˈe͜ɪ.to͜ʊ",
            "bˈɑ.tl",
            "hˈæn.dbˌæɡ",
        ]
        checked = 0
        bad: list[str] = []
        for word in words:
            base = shipped.apply(word, FEATURES)
            assert base != word, f"{word!r} exercises no shipped rule"
            for run in self.RUNS:
                for pre, post in ((run, ""), ("", run), (run, run)):
                    out = shipped.apply(pre + word + post, FEATURES)
                    checked += 1
                    if out != pre + base + post:
                        bad.append(f"{pre + word + post!r} -> {out!r}, not {base!r}")
        assert checked == len(words) * len(self.RUNS) * 3 == 180
        assert bad == [], f"{len(bad)} of {checked}, first: {bad[:3]}"


class TestTheTraceStartsFromWhatTheRulesSaw:
    """``Derivation.start`` is ``steps[0].before``, by construction.

    Reading a form can drop what the inventory does not register -- with a
    warning -- and ``start`` used to be the string handed in rather than
    the form the rules were given. So ``derive("KÆT", ...)`` reported
    ``start='KÆT'`` beside ``steps[0].before=''``: the trace printed the
    input, then ``(no rule fired)``, and yet the result was not the input.
    A trace whose first line is not what the first rule saw accounts for a
    derivation that did not happen.
    """

    #: Forms that survive the read, and forms that lose something to it:
    #: an unregistered symbol, an unbound stress mark, an unbound tie.
    FORMS = (
        "kæt",
        "kæt|dɒɡ",
        "kæt‖dɒɡ",
        "kæt‿dɒɡ",
        "#kæt#",
        "kæt.",
        "kæt ",
        "KÆT",
        "kætˈ",
        "kæt͡",
        "kæ$t",
    )

    def test_the_first_line_is_what_the_first_rule_was_given(self):
        checked = 0
        for form in self.FORMS:
            with _quiet():
                derivation = ipakit.derive(form, f"{VOICING}\n{GLOTTALLING}")
            assert derivation.start == derivation.steps[0].before, form
            assert derivation.trace().startswith(derivation.start), form
            checked += 1
        assert checked == len(self.FORMS) == 11, f"sweep covered {checked}"

    def test_a_derivation_that_fires_nothing_ends_where_it_started(self):
        """The consequence that made the disagreement a wrong answer: the
        trace said ``(no rule fired)`` while the output differed from what
        it printed as the input."""
        checked = 0
        for form in self.FORMS:
            for spec in (GLOTTALLING, VOICING, "∅ -> ə / # _", "t -> ∅ / _ #"):
                with _quiet():
                    derivation = ipakit.derive(form, spec)
                if not derivation.fired:
                    assert derivation.result == derivation.start, f"{spec} {form!r}"
                    assert "no rule fired" in derivation.trace()
                checked += 1
        assert checked == 44, f"sweep covered {checked}"

    def test_the_dropped_input_is_still_reported_by_the_read(self):
        """Pinned so the limit stays known: ``start`` is the read form, and
        what the read discarded is said by a warning rather than by the
        derivation. If reading stops warning, this fails."""
        with pytest.warns(UserWarning, match="unregistered symbol"):
            derivation = ipakit.derive("KÆT", GLOTTALLING)
        assert derivation.start == derivation.result == ""
        assert derivation.fired == ()


class TestProsodyIsWritableAndNotOnlyAskable:
    """Assign, change, clear -- and a literal that names prosody on the left.

    Every one of these parsed and then did nothing, in three unrelated
    ways: a literal was compared against the prosody-stripped ``core``, a
    prosodic change reached ``respell``, which does not spell prosody, and
    a bare suprasegmental on the right parsed to no units at all so
    ``before == after``. The gap stayed invisible because *lengthening*
    worked (``a -> aː``) -- one direction of one feature out of six -- and
    because the parser validated prosodic feature names, which advertises
    that they are writable.
    """

    @pytest.mark.parametrize(
        "form,spec,want",
        [
            ("ka", "[vowel] -> [length=long] / _ #", "kaː"),
            ("kaː", "[vowel] -> [length=normal] / _ #", "ka"),
            ("at", "[vowel] -> [stress=primary] / # _", "ˈat"),
            ("kaː", "aː -> a / _ #", "ka"),
            ("kˈat", "ˈa -> e", "ket"),
            ("kˌat", "[vowel] -> [stress=primary]", "kˈat"),
            ("kˈat", "[vowel] -> [stress=∅]", "kat"),
            ("ka", "[vowel] -> [tone=high] / _ #", "ka˦"),
            ("kaː", "[vowel] -> [length=half-long]", "kaˑ"),
        ],
    )
    def test_it_fires_and_says_what_was_asked(self, form, spec, want):
        """``fired`` first: a no-op rule would satisfy an equality against
        input that happens to look right."""
        assert ipakit.derive(form, spec).fired, f"{spec} did not fire; nothing tested"
        assert ipakit.rewrite(form, spec) == want

    def test_lengthening_and_shortening_are_the_same_shape(self):
        """The asymmetry that hid all of this: one direction already worked."""
        assert ipakit.rewrite("ka", "a -> aː / _ #") == "kaː"
        assert ipakit.rewrite("kaː", "aː -> a / _ #") == "ka"

    def test_clearing_a_value_and_naming_its_unmarked_one_agree(self):
        """``length`` declares a default of ``normal`` and no mark declares
        that value, because a bare vowel already says it. So shortening and
        clearing are one operation and ``[length=∅]`` is not a second
        spelling of it -- which is why the removal notation is needed only
        where a feature has no unmarked value to name."""
        assert FEATURES.features["length"].default == "normal", "premise moved"
        assert FEATURES.declaring_mark("length", "normal") is None
        for spec in ("[vowel] -> [length=normal]", "[vowel] -> [length=∅]"):
            assert ipakit.rewrite("kaː", spec) == "ka", spec

    def test_stress_has_no_unmarked_value_to_name(self):
        """Which is the whole reason removal needed notation: ``stress``
        declares no default, so there is nothing to write for "unstressed"
        and ``∅`` is the only way to say it."""
        assert FEATURES.features["stress"].default is None, "premise moved"
        assert ipakit.rewrite("kˈat", "[vowel] -> [stress=∅]") == "kat"

    def test_a_change_may_name_both_namespaces_at_once(self):
        """One bracket, split by declared mode, each half realized where it
        can be. Neither half alone can do it: ``respell`` refuses a
        prosodic key outright, since prosody is not in the bag it
        respells from, and ``compose_unit`` verifies *through* the bag and
        so answers ``None`` for every prosodic request."""
        with pytest.raises(ValueError, match="respell cannot write"):
            FEATURES.respell("a", length="normal")
        assert FEATURES.compose_unit("a", length="long") is None, "premise moved"
        assert ipakit.rewrite("kaː", "[vowel] -> [backness=back]") == "kɑː"
        assert ipakit.rewrite("kaː", "[vowel] -> [backness=back length=normal]") == "kɑ"


class TestOnlyTheProsodyARuleNamedIsRewritten:
    """A literal on the right spells a whole unit, so its *silence* about
    prosody has to be given a meaning rather than left to fall out.

    It means "carry it across": ``t -> ʔ`` must not shorten ``tː``, since
    length and tone are phonemic in plenty of inventories. The exception
    is a feature one of the two sides named, which is what lets ``aː -> a``
    shorten instead of doing nothing.
    """

    def test_a_literal_rewrite_still_carries_prosody_it_did_not_name(self):
        assert ipakit.rewrite("kætː", "t -> ʔ / _ #") == "kæʔː"
        assert ipakit.rewrite("kæt˥", "t -> ʔ / _ #") == "kæʔ˥"

    def test_naming_it_on_the_left_and_not_the_right_removes_it(self):
        assert ipakit.rewrite("kaː", "aː -> a") == "ka"
        assert ipakit.rewrite("kˈaː", "ˈaː -> a") == "ka"

    def test_it_removes_only_the_feature_that_was_named(self):
        """Two marks on one unit, one rule naming one of them."""
        assert ipakit.rewrite("kˈaː", "aː -> a") == "kˈa"
        assert ipakit.rewrite("kˈaː", "ˈa -> e") == "keː"

    def test_a_query_naming_prosody_names_it_the_same_way(self):
        """The pattern language is one language: ``[vowel length=long]``
        says what ``aː`` says, so it has to mean the same on the left."""
        assert ipakit.rewrite("kaː", "[vowel length=long] -> a") == "ka"

    def test_an_action_used_alone_carries_everything(self):
        """``Action.edit`` has no left half to consult -- the halves are
        separable, and a site may have been found some other way -- so it
        keeps prosody, which is the safe reading when nothing said
        otherwise. It can still be told to clear a value outright."""
        items = R.units("kaː", FEATURES)
        carried = R.Action(becomes="e").edit(R.Site(1, 2), items, FEATURES)
        assert carried is not None and carried.after == "eː"
        cleared = R.Action(becomes={"length": None}).edit(R.Site(1, 2), items, FEATURES)
        assert cleared is not None and cleared.after == "a"


class TestAMultiUnitReplacementInheritsTheProsodyBySide:
    """Which of several new units wears the mark the old one wore.

    "Carry the prosody across" answers a one-unit right-hand side and
    says nothing about a longer one, so ``rewrite("katː", "t -> ts")``
    gave ``kats`` -- the geminate's length on the floor, silently, while
    ``t -> ʔ`` on the same input kept it. The three candidate answers are
    the FIRST of the new units, the LAST, and ALL of them; they disagree
    for stress against length, so no single position is right, and a
    table saying "stress here, length there" would be exactly the
    hardcoded phonetics ``test_declared_not_hardcoded.py`` rejects.

    The answer is read off **where the mark is written**: before its unit
    (``ˈa``) or after it (``aː``). A mark written before the target goes
    on the first of the units replacing it, one written after goes on the
    last -- the mark stays on the side of the span it was written on,
    which is the claim ``_anchors`` already makes about a boundary run,
    applied to the marks that ride a span rather than divide it. That one
    rule gives ``katsː`` (length at the end of the coda, which is the
    LAST answer) and ``ˈai`` (stress on the nucleus, which is the FIRST
    answer) without choosing either, and it rules ALL out: ``tːsː``
    states the length twice.

    Which side a mark is written on is ``IPAFeatures.stress_markers``,
    the read ``Segment.to_ipa`` uses to place the glyph -- so where a
    mark lands and where it is spelled cannot come apart.
    """

    #: Every declared prosodic mark, read rather than listed.
    MARKS = tuple(g for g in FEATURES.diacritics if declared_prosody(g, FEATURES))

    @staticmethod
    def _worn(phone: str, mark: str) -> str:
        return dataclasses.replace(FEATURES.segment(phone), prosody=(mark,)).to_ipa()

    @classmethod
    def _bears(cls, phone: str, mark: str) -> str | None:
        """``phone`` wearing ``mark``, or None if that is not what it spells.

        ``t`` plus the rising contour spells ``ť``, a *registered phone*
        the recomposition owns -- one unit whose core is ``ť``, not a
        ``t`` wearing anything -- so no rule about ``t`` reaches it. Asked
        of the read rather than listed, so the next precomposed symbol
        drops out of the sweep instead of failing it.
        """
        worn = cls._worn(phone, mark)
        read = R.units(worn, FEATURES)
        return worn if len(read) == 1 and read[0].core == phone else None

    def test_the_headline(self):
        assert ipakit.rewrite("katː", "t -> ts") == "katsː"

    def test_the_sweep_sees_every_declared_prosodic_feature(self):
        """Shape as well as a floor: all six prosodic features present."""
        named = {key for m in self.MARKS for key in declared_prosody(m, FEATURES)}
        assert named == set(FEATURES.features_by_mode["prosodic"])
        assert len(self.MARKS) >= 21

    def test_no_declared_mark_is_dropped_by_a_multi_unit_replacement(self):
        """The defect itself, over every mark and three replacement lengths."""
        lost = []
        checked = 0
        for mark in self.MARKS:
            worn = self._bears("t", mark)
            if worn is None:
                continue
            for rhs in ("ts", "tsk", "s"):
                got = ipakit.rewrite("ka" + worn + "i", f"t -> {rhs}")
                checked += 1
                if mark not in got:
                    lost.append((mark, rhs, got))
        assert checked >= 60, "sweep did not run"
        assert not lost, f"{len(lost)} of {checked} replacements lost the mark"

    def test_a_mark_written_after_its_unit_lands_on_the_last(self):
        trailing = [m for m in self.MARKS if m not in FEATURES.stress_markers]
        assert len(trailing) >= 19
        checked = 0
        for mark in trailing:
            worn = self._bears("t", mark)
            if worn is None:
                continue
            out = ipakit.rewrite("ka" + worn + "i", "t -> ts")
            assert out == "kats" + mark + "i", f"{mark!r} not last: {out!r}"
            checked += 1
        assert checked >= 18, "sweep did not run"

    def test_a_mark_written_before_its_unit_lands_on_the_first(self):
        leading = [m for m in self.MARKS if m in FEATURES.stress_markers]
        assert leading, "no mark is written before its unit; the partition is gone"
        for mark in leading:
            out = ipakit.rewrite(f"k{mark}ai", "a -> ai")
            assert out == f"k{mark}aii", f"{mark!r} not first: {out!r}"

    def test_the_side_is_the_side_the_speller_writes_it_on(self):
        """The structural claim, so the two reads cannot drift apart.

        If a mark ever spells leading while landing trailing, this fails
        rather than the answer quietly moving.
        """
        for mark in self.MARKS:
            spelled = self._worn("a", mark)
            assert spelled.startswith(mark) == (mark in FEATURES.stress_markers), mark

    def test_it_is_never_stated_twice(self):
        """ALL is the third candidate, and this is what rules it out."""
        for rhs in ("ts", "tsk"):
            assert ipakit.rewrite("katː", f"t -> {rhs}").count("ː") == 1
        assert ipakit.rewrite("kˈai", "a -> ai").count("ˈ") == 1

    def test_the_single_unit_case_is_untouched(self):
        """First and last are the same unit, so this is not a branch."""
        assert ipakit.rewrite("kætː", "t -> ʔ / _ #") == "kæʔː"
        assert ipakit.rewrite("kæt˥", "t -> ʔ / _ #") == "kæʔ˥"

    def test_a_named_feature_is_still_not_carried(self):
        """The exception that makes ``aː -> a`` shorten reaches here too,
        from either side of the arrow."""
        assert ipakit.rewrite("katː", "tː -> ts") == "kats"
        assert ipakit.rewrite("katː", "t -> tsː") == "katsː"
        assert ipakit.rewrite("kˈai", "ˈa -> ai") == "kaii"

    def test_nothing_that_cannot_wear_a_mark_is_given_one(self):
        assert ipakit.rewrite("katː", "t -> ∅") == "ka"


class TestTheGlyphsAreDownstreamOfTheFeatures:
    """Prosody is written in feature space and spelled afterwards, so a
    rule about one feature does not disturb the others.

    Two consequences, and both are silent when wrong.
    """

    def test_a_mark_that_still_says_what_is_wanted_is_kept_as_written(self):
        """Changing the length of ``á`` must not respell its tone as
        ``a˦``: the tone mark still says exactly what is wanted, so it
        survives verbatim rather than being re-derived."""
        # Written decomposed: the engine canonicalizes, so the tone mark
        # comes back out as a combining acute rather than precomposed.
        assert ipakit.rewrite("ka\u0301ː", "[vowel] -> [length=normal]") == "ka\u0301"

    def test_clearing_one_feature_leaves_the_marks_that_state_the_others(self):
        """Dropping a mark because *its* feature changed must not take a
        neighboring mark's feature down with it."""
        assert ipakit.rewrite("kˈa᷄", "[vowel] -> [tone=∅]") == "kˈa"
        assert ipakit.rewrite("kˈa᷄", "[vowel] -> [stress=∅]") == "ka᷄"

    def test_clearing_a_contour_clears_the_whole_run_that_spelled_it(self):
        """A contour is a sequence of levels, so it goes as one thing.

        ``᷄`` states ``tone="mid>high"`` and nothing else, and so does the
        two-letter run spelling the same contour. Clearing the tone of
        either leaves no half of it standing -- a mark for the *direction*
        would be a claim the caller did not make, and one the levels just
        removed were the only evidence for.
        """
        assert declared_prosody("᷄", FEATURES) == {"tone": "mid>high"}, "premise moved"
        assert ipakit.rewrite("ka᷄", "[vowel] -> [tone=∅]") == "ka"
        assert ipakit.rewrite("ka˧˦", "[vowel] -> [tone=∅]") == "ka"

    def test_a_run_that_still_says_what_is_wanted_is_kept_whole(self):
        """The sequence counterpart of the test above: every letter of a
        tone-letter run survives a change to another feature, rather than
        the run being re-derived into the mark that abbreviates it, or each
        letter being matched against the whole sequence and dropped."""
        assert ipakit.rewrite("ka˧˩˧", "[vowel] -> [stress=primary]") == "kˈa˧˩˧"

    def test_assigning_a_level_of_stress_replaces_the_other(self):
        """Not a stack: a unit bears one stress level, so ``ˌ`` has to go
        rather than stand beside ``ˈ``."""
        assert ipakit.rewrite("kˌat", "[vowel] -> [stress=primary]") == "kˈat"


class TestNamingProsodyOnALiteralDoesNotJoinIdentity:
    """The constraint that made this delicate: ``a`` must go on matching
    ``ˈa``.

    Prosody on a literal is an *additional* constraint layered over the
    identity match, not part of the identity. Folding it in would have
    made ``aː -> a`` work and broken the library's stated position.
    """

    def test_a_plain_literal_stays_loose_and_a_marked_one_is_strict(self):
        plain, marked = R.units("a", FEATURES)[0], R.units("aː", FEATURES)[0]
        loose, tight = R._pattern("a", FEATURES), R._pattern("aː", FEATURES)
        assert loose.matches(plain, FEATURES) and loose.matches(marked, FEATURES)
        assert tight.matches(marked, FEATURES)
        assert not tight.matches(plain, FEATURES)

    def test_the_layer_is_a_constraint_and_not_a_name(self):
        pattern = R._pattern("aː", FEATURES)
        assert pattern.literal == "a"
        assert pattern.pro_required == {"length": "long"}
        assert pattern.prosodic_keys == frozenset({"length"})

    def test_the_bundles_are_still_one(self):
        """If this ever fails, the fix went the wrong way round."""
        assert ipakit.features("a") == ipakit.features("ˈa") == ipakit.features("aː")

    def test_the_split_reads_the_declaration_not_a_glyph_table(self):
        assert split_prosody("aː", FEATURES) == ("a", ("ː",))
        assert split_prosody("ˈa", FEATURES) == ("a", ("ˈ",))
        # Canonicalized first: 'á' is one character until it is decomposed,
        # and the tone mark is not there to be seen before that.
        assert split_prosody("á", FEATURES) == ("a", ("́",))
        # ...but not decomposed away: 'ç' is a registered phone, not a 'c'
        # wearing a cedilla.
        assert split_prosody("ç", FEATURES) == ("ç", ())


class TestProsodyThatCannotBeWrittenIsRefusedOrDeclined:
    """Refused at parse where the notation cannot mean anything; declined
    at apply where the inventory cannot spell it. Neither is silent."""

    @pytest.mark.parametrize(
        "bad", ["∅ -> ˈ / # _", "∅ -> ː / [vowel] _ #", "ˈ -> ∅", "t -> ʔ / ˈ _"]
    )
    def test_a_bare_suprasegmental_is_not_a_position(self, bad):
        """A prosodic mark is a property of a unit, not one of its own, so
        there is nothing for an insertion to insert and nothing for a
        context to stand at. Each of these used to parse and never fire."""
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert "prosody with no phone under it" in str(caught.value)

    def test_only_prosody_can_be_cleared(self):
        """Every phone has some voicing, so ``[voiced=∅]`` names nothing."""
        with pytest.raises(R.RuleError) as caught:
            R.parse("t -> [voiced=∅]", FEATURES)
        assert "only prosody can be absent" in str(caught.value)

    @pytest.mark.parametrize("bad", ["[length=looong]", "[stress=third]"])
    def test_an_undeclared_prosodic_value_is_refused(self, bad):
        """The prosodic path does not go through ``respell``, which is where
        a misspelled segmental value fails loudly. Without this check it
        would be the one place a typo stayed quiet."""
        with pytest.raises(R.RuleError, match="not a declared value"):
            R.parse(f"a -> {bad}", FEATURES)

    def test_a_composition_colliding_with_a_registered_phone_declines(self):
        """The one escape the sweep below finds, pinned so it stays known.

        ``t`` plus the rising-contour caron recomposes to the registered
        ``ť``, which does not read back as a ``t`` bearing a contour.
        ``with_prosody`` *measures* that instead of trusting the marks it
        picked, so the rule declines rather than handing back a different
        phone. If this starts working, the sweep's declined count drops and
        that test fails too.
        """
        assert (
            with_prosody(FEATURES.segment("t"), {"contour": "rising"}, FEATURES) is None
        )
        assert ipakit.rewrite("t", "t -> [contour=rising]") == "t"


class TestAssigningThenClearingProsodyReturnsTheSpelling:
    """The sweep. Named cases test the features somebody thought of.

    Every registered phone that spells itself back, against every
    prosodic value some mark declares, in both directions: write it, then
    clear it, and the spelling must be the one it started with. That is
    the property "prosody is writable" reduces to, and it is the one a
    green suite would otherwise let slide -- a writer that assigned but
    could not clear would pass every assignment test in this file.
    """

    def test_every_phone_and_every_declared_prosodic_value(self):
        prosodic = {
            name
            for name, feature in FEATURES.features.items()
            if getattr(feature, "mode", None) == "prosodic"
        }
        pairs = [
            (name, value)
            for name in prosodic
            for value in FEATURES.features[name].values
            if FEATURES.declaring_mark(name, value) is not None
        ]
        # Shape, not only a count: all six prosodic features must
        # contribute a value, or a sweep that quietly lost tone entirely
        # would still clear any floor. 'length=normal' contributes none,
        # which is the point of the test above.
        assert (
            {name for name, _ in pairs}
            == prosodic
            == {
                "stress",
                "length",
                "tone",
                "contour",
                "step",
                "global",
            }
        )
        assert len(pairs) >= 15, f"only {len(pairs)} declared prosodic values"

        phones = _phones()
        assert_swept(len(phones), phones)
        checked = 0
        declined: list[str] = []
        bad: list[str] = []
        for phone in phones:
            for name, value in pairs:
                marked = ipakit.rewrite(phone, f"{phone} -> [{name}={value}]")
                if marked == phone:
                    # The inventory cannot spell it, so the rule declined.
                    # Counted rather than skipped: a writer that declined
                    # everything would otherwise sweep nothing.
                    declined.append(f"{phone} {name}={value}")
                    continue
                back = ipakit.rewrite(marked, f"{phone} -> [{name}=∅]")
                checked += 1
                if back != phone:
                    bad.append(f"{phone} {name}={value}: {marked!r} -> {back!r}")
        assert checked + len(declined) == len(phones) * len(pairs)
        assert checked > 2000, f"sweep covered only {checked}"
        assert bad == [], f"{len(bad)} of {checked} did not round trip: {bad[:3]}"
        # Stress can be written only on nuclei; every non-nucleus therefore
        # declines both levels, in addition to the established contour miss.
        non_nuclei = {
            phone
            for phone in phones
            if not FEATURES.is_nucleus(FEATURES.get_features(phone))
        }
        expected_declined = {"t contour=rising"} | {
            f"{phone} stress={level}"
            for phone in non_nuclei
            for level in ("primary", "secondary")
        }
        assert set(declined) == expected_declined, f"declined set moved: {declined}"


def _prosody_of(form: str) -> dict[str, str]:
    """What one written unit's prosody reads as."""
    with _quiet():
        return dict(R.units(form, FEATURES)[0].prosody)


def _states(seg, key: str) -> bool:  # type: ignore[no-untyped-def]
    """Whether a mark on ``seg`` *asserts* ``key``, rather than the read
    deriving it from the levels beside it."""
    return any(key in declared_prosody(glyph, FEATURES) for glyph in seg.prosody)


#: A rise asserted by a caron over a run of levels that falls. Escaped, so
#: the literal is the run of marks it names -- ``a``, U+030C COMBINING
#: CARON, then the two tone letters -- and not the single codepoint an
#: editor may normalize the first two into.
CARON_OVER_A_FALL = "a\u030c\u02e5\u02e9"

#: The same assertion with no levels under it to agree or disagree with.
BARE_CARON = "a\u030c"


class TestWritingProsodyDoesNotRewriteWhatItWasNotAsked:
    """A no-change write handed back a different transcription.

    ``ǎ˥˩`` states a rise with its caron and a fall with its levels. The
    read reports the contradiction and lets the assertion stand, because
    only the writer knows which of the two they meant. The write dropped
    the caron on the way past -- for no reason but that ``contour`` is a
    tier something else could derive -- and the result read as a *fall*,
    the opposite of what was asserted, out of a call that changed nothing.
    The read-back check agreed with it, because it recomputed what to
    expect from the same shortened target it had just written from.
    """

    def test_a_no_change_write_keeps_a_contour_its_levels_contradict(self):
        written = with_prosody(FEATURES.segment(CARON_OVER_A_FALL), {}, FEATURES)
        assert written is not None
        assert written.to_ipa() == CARON_OVER_A_FALL
        assert _prosody_of(written.to_ipa())["contour"] == "rising"

    def test_an_unrelated_change_leaves_that_contour_alone(self):
        written = with_prosody(
            FEATURES.segment(CARON_OVER_A_FALL), {"length": "long"}, FEATURES
        )
        assert written is not None
        assert _prosody_of(written.to_ipa()) == {
            "contour": "rising",
            "tone": "top>bottom",
            "length": "long",
        }

    def test_every_prosody_bearing_unit_rereads_as_itself(self):
        """The sweep. One mark cannot contradict itself, so this is the
        property a corpus of *single*-marked units cannot state -- and the
        reason a named case for the caron would not have been enough."""
        corpus = prosody_bearing_units()
        checked = 0
        bad: list[str] = []
        for unit in corpus:
            checked += 1
            written = with_prosody(FEATURES.segment(unit), {}, FEATURES)
            if written is None:
                bad.append(f"{unit!r}: declined")
                continue
            if _prosody_of(written.to_ipa()) != _prosody_of(unit):
                bad.append(f"{unit!r} -> {written.to_ipa()!r}")
        assert checked > 5000, f"sweep covered only {checked} units"
        assert bad == [], f"{len(bad)} of {checked} were rewritten: {bad[:3]}"

    def test_the_sweep_reaches_a_contour_asserted_over_its_own_levels(self):
        """Shape, not size. A corpus of singly marked units would clear any
        floor above and still be unable to fail the property, because one
        mark has nothing to contradict. What makes it able to fail is a unit
        that *asserts* a contour and states levels too, so this asserts that
        class is in the sweep rather than trusting the count."""
        corpus = prosody_bearing_units()
        contradictable = [
            unit
            for unit in corpus
            if {"contour", "tone"} <= set(_prosody_of(unit))
            and any("contour" in declared_prosody(c, FEATURES) for c in unit)
        ]
        assert (
            len(contradictable) > 500
        ), f"only {len(contradictable)} units assert a contour over their levels"


class TestClearingProsodyReportsWhatItActuallyDid:
    """A non-``None`` answer said the request was honored when it was not.

    ``with_prosody(seg("a˩˥"), {"contour": None})`` returned ``a˩˥``, whose
    contour is still ``rising``. Nothing recorded that the caller had asked
    for a tier to be *gone*, so the read-back check re-derived the very
    value it was asked to remove and then accepted it.

    A tone that reads ``bottom>top`` rises whether or not a mark says so,
    so a form with those levels and no contour does not exist. That request
    is impossible, and ``None`` is how this function says so. Clearing the
    tone as well would answer a different question from the one asked.
    """

    def test_clearing_a_contour_the_levels_entail_is_refused(self):
        assert (
            with_prosody(FEATURES.segment("a˩˥"), {"contour": None}, FEATURES) is None
        )

    def test_clearing_a_contour_only_a_mark_states_still_works(self):
        written = with_prosody(
            FEATURES.segment(BARE_CARON), {"contour": None}, FEATURES
        )
        assert written is not None
        assert written.to_ipa() == "a"
        assert _prosody_of(written.to_ipa()) == {}

    def test_clearing_the_levels_takes_the_contour_they_entailed(self):
        written = with_prosody(FEATURES.segment("a˩˥"), {"tone": None}, FEATURES)
        assert written is not None
        assert _prosody_of(written.to_ipa()) == {}

    @pytest.mark.slow
    def test_every_answered_clear_actually_cleared(self):
        """The sweep, over every tier every unit in the corpus reads.

        The property is not "clearing works" -- some clears are impossible
        and must be refused. It is that an answer other than ``None`` means
        the tier is gone, which is what the caller is entitled to conclude.
        """
        corpus = prosody_bearing_units()
        refused = honored = 0
        refused_derived = 0
        bad: list[str] = []
        for unit in corpus:
            seg = FEATURES.segment(unit)
            for key in _prosody_of(unit):
                written = with_prosody(seg, {key: None}, FEATURES)
                if written is None:
                    refused += 1
                    refused_derived += not _states(seg, key)
                    continue
                honored += 1
                if key in _prosody_of(written.to_ipa()):
                    bad.append(f"{unit!r} {key}=None -> {written.to_ipa()!r}")
        assert honored > 5000, f"sweep honored only {honored} clears"
        assert bad == [], f"{len(bad)} of {honored} were not cleared: {bad[:3]}"
        # Both branches must occur, or the property is satisfiable by a
        # writer that refuses everything -- and the derived branch is the
        # one the defect lived in, so a sweep that never reaches it says
        # nothing about the case it was written for.
        assert refused_derived > 0, f"{refused} refusals, none of a derived tier"


def _segmental(form: str) -> tuple[str, ...]:
    """The segments of a form, with the boundaries dropped and nothing else.

    Read through ``rules.units`` rather than ``ipakit.segments`` so this
    is the faithful spelling minus the relations: it is the projection a
    boundary rewrite must leave byte-identical, and the property that
    says which rewrites are boundary rewrites at all.
    """
    with _quiet():
        return tuple(u.text for u in R.units(form, FEATURES) if not u.is_boundary)


def _ends_stripped(form: str) -> str:
    """``form`` with the boundary runs at its two ends removed.

    ``TestABoundaryRunIsOneBoundary`` strips the run it wrote by
    position, which a rule that *deletes* boundaries has already taken
    away -- so the same claim has to be asked of both sides normalized
    rather than of one side sliced.
    """
    with _quiet():
        items = R.units(form, FEATURES)
    lo, hi = 0, len(items)
    while lo < hi and items[lo].is_boundary:
        lo += 1
    while hi > lo and items[hi - 1].is_boundary:
        hi -= 1
    return R.spell(items[lo:hi])


class TestABoundaryIsWrittenAndUnwrittenAlike:
    """The asymmetry this class exists for, measured before the change::

        '∅ -> . / [manner=plosive] _ [vowel]'  parses and FIRES: 'ata' -> 'at.a'
        '. -> ∅ / _'                           REFUSED: "a boundary is a relation
                                               between segments, not a segment"

    The engine would *assert* a relation and refuse to *retract* one. The
    refusal was the deliberate half -- a boundary named as a target used
    to parse and then silently never fire, because site scanning skipped
    boundary units -- and the insertion was the half nobody had examined.
    Both ends agree now: a boundary may be written, unwritten, or restated
    at another level, and what says that this is one kind of rewrite and
    not license to treat a relation as a segment is that **the segmental
    string does not move**.
    """

    #: Every shape a boundary rewrite takes -- write, unwrite, restate,
    #: and the wildcard -- with and without a context.
    SPECS = (
        "∅ -> . / [manner=plosive] _ [vowel]",
        "∅ -> . / [vowel] _ [vowel]",
        "∅ -> ‿ / [vowel] _ z [vowel]",
        ". -> ∅",
        ". -> ∅ / [vowel] _ [vowel]",
        ". -> ∅ / _ #",
        "% -> ∅",
        "‿ -> ∅",
        ". -> #",
        "‿ -> .",
    )
    FORMS = (
        "ata",
        "a.ta",
        "a.t.a",
        "ata.",
        ".ata",
        "a#ta",
        "a‿ta",
        "a a",
        "lez‿ami",
        "lez‿.ami",
        "a.b‿c|d",
        "kæt",
        "kæt..",
        "ˈbʌ.tn",
        "pə.tˈe͜ɪ.to͜ʊ",
    )
    #: Rules that only ever take a boundary away, for the edge-redundancy
    #: sweep: those are the ones the positional strip cannot check.
    UNWRITING = (". -> ∅", "% -> ∅", ". -> ∅ / _ #", ". -> #")
    #: Forms whose ends carry no boundary run, which is the invariant's
    #: precondition.
    PLAIN = ("ata", "a.ta", "kæt", "a‿ta", "lez‿ami", "atapaka")

    def test_both_ends_of_the_arrow_agree(self):
        """The report, as a test: one fired, and now the other does too."""
        assert ipakit.rewrite("ata", "∅ -> . / [manner=plosive] _ [vowel]") == "at.a"
        assert ipakit.rewrite("at.a", ". -> ∅") == "ata"

    def test_a_dot_can_be_moved_which_is_what_resyllabification_is(self):
        """Why this went the permissive way rather than refusing both.

        Moving a boundary is a real process, and it is exactly an unwrite
        followed by a write -- two rules, since a rule sees a snapshot of
        its input. The segmental string is byte-identical across it, which
        is the whole content of "only the relations moved".
        """
        spec = ". -> ∅\n∅ -> . / [vowel] _ [manner=plosive] [vowel]"
        assert ipakit.rewrite("at.a", spec) == "a.ta"
        assert _segmental("a.ta") == _segmental("at.a") == ("a", "t", "a")

    def test_a_boundary_rewrite_leaves_the_segmental_string_alone(self):
        """The invariant, swept over every shape and every form.

        This is the class rule the parser enforces from the other side by
        refusing ``t -> .`` and ``. -> t``: if a rewrite can name only
        boundaries, the segments it stands between cannot move.
        """
        checked = 0
        bad: list[str] = []
        for spec in self.SPECS:
            for form in self.FORMS:
                with _quiet():
                    got = ipakit.rewrite(form, spec)
                checked += 1
                if _segmental(got) != _segmental(form):
                    bad.append(f"{spec}: {form!r} -> {got!r}")
        # Exact, not a floor: every shape against every form. A floor
        # cannot tell that the writing rules, or the unwriting ones, fell
        # out of the sweep, so the kinds are counted too.
        kinds = [ipakit.rule(s) for s in self.SPECS]
        assert sum(r.inserts for r in kinds) == 3, "the sweep lost its writers"
        assert sum(r.deletes for r in kinds) == 5, "the sweep lost its unwriters"
        assert checked == len(self.SPECS) * len(self.FORMS) == 150
        assert bad == [], f"{len(bad)} of {checked}, first: {bad[:3]}"

    def test_writing_then_unwriting_a_boundary_returns_the_spelling(self):
        """The two halves undo each other, swept over the inventory.

        Syllabify and then de-syllabify, and the form that comes back is
        the one that went in -- which is only checkable now that both
        directions exist.
        """
        spec = "∅ -> . / [manner=plosive] _ [vowel]\n. -> ∅"
        checked = 0
        bad: list[str] = []
        for phone in _phones():
            for form in (phone, f"a{phone}a", f"{phone}a{phone}"):
                with _quiet():
                    got = ipakit.rewrite(form, spec)
                checked += 1
                if got != form:
                    bad.append(f"{form!r} -> {got!r}")
        assert_swept(checked, _phones())
        assert bad == [], f"{len(bad)} of {checked} did not return: {bad[:3]}"

    def test_a_boundary_target_is_a_class_exactly_as_a_context_pattern_is(self):
        """``.`` is "syllable or stronger" in a target as in a context.

        A word boundary *is* a syllable boundary (docs/rules.md), so
        ``. -> ∅`` deletes a written ``#`` too, and with it the word
        division the dot never named -- exactly as ``[vowel] -> ∅``
        deletes a stress it never named. Surprising enough to pin in both
        directions: naming the mark itself is how a rule is exact about
        which boundary it means.
        """
        assert ipakit.rewrite("a#b", ". -> ∅") == "ab"
        assert ipakit.rewrite("a‿b", ". -> ∅") == "ab"
        assert ipakit.rewrite("kˈat", "[vowel] -> ∅") == "kt", "the same rule"
        # A named mark is exact, and the ladder does not run downhill.
        assert ipakit.rewrite("a.b", "‿ -> ∅") == "a.b"
        assert ipakit.rewrite("a‿b", "‿ -> ∅") == "ab"
        hashed = R.parse("# -> ∅", FEATURES)
        assert R.spell(hashed.apply("a.b", FEATURES)[0]) == "a.b"
        assert R.spell(hashed.apply("a#b", FEATURES)[0]) == "ab"

    def test_unwriting_a_boundary_holds_edge_redundancy(self):
        """The invariant survives the new rule kind, in its stated form.

        ``r(f) == strip(r("#" + f))`` and so on: the virtual edge past the
        end of a form is not a unit, so there is nothing there for a
        deletion to take, and a written mark still adds no information.
        What cannot be reused is the *positional* strip -- these rules
        remove the mark that strip expects to find -- so both sides have
        their end runs taken off instead.
        """
        runs = ("#", "##", ".", "..", "‿", " ")
        checked = 0
        bad: list[str] = []
        for spec in self.UNWRITING:
            for form in self.PLAIN:
                base = _ends_stripped(ipakit.rewrite(form, spec))
                for run in runs:
                    for pre, post in ((run, ""), ("", run), (run, run)):
                        written = pre + form + post
                        with _quiet():
                            got = _ends_stripped(ipakit.rewrite(written, spec))
                        checked += 1
                        if got != base:
                            bad.append(f"{spec}: {form}->{base} vs {written}->{got}")
        assert checked == len(self.UNWRITING) * len(self.PLAIN) * len(runs) * 3 == 432
        assert bad == [], f"{len(bad)} of {checked}, first: {bad[:3]}"

    def test_a_word_boundary_target_can_be_written_in_a_set(self):
        """The word mark is a target in a file, like every other boundary.

        A line opening with ``#`` is a comment, because ``#`` is also the
        word boundary and a set has to carry prose. That was read as a
        prefix, which decided the collision against the rule: ``# -> ∅``
        was prose, so the *one* boundary a file could not name was the
        word mark -- while ``. -> ∅``, the class pattern that matches a
        syllable break and everything stronger, deleted that same mark. The
        general pattern was strictly stronger than the specific one, which
        inverts what naming a mark is for.

        The engine was never the problem, and that is worth pinning: the
        rule found its site and made its edit all along. What lost the
        answer was the line reader, so the whole set was empty and the
        form came back unchanged.
        """
        assert len(R.RuleSet.parse("# -> ∅", FEATURES)) == 1
        assert len(R.RuleSet.parse("∅ -> # / a _ a", FEATURES)) == 1
        # The half that always worked, kept as the witness that the fix is
        # in the reader and not in what a rule does with a boundary.
        assert R.spell(R.parse("# -> ∅", FEATURES).apply("a#b", FEATURES)[0]) == "ab"
        assert ipakit.rewrite("a#b", "# -> ∅") == "ab"
        assert ipakit.rewrite("a#b", "% -> ∅") == "ab"

    @pytest.mark.parametrize(
        "line,rules,because",
        [
            ("# -> ∅", 1, "the mark alone, then the arrow"),
            ("#->∅", 1, "the arrow need not be spaced"),
            ("# ~> ∅", 1, "and it may be the optional arrow"),
            ("# → ‿ / a _ b", 1, "any arrow spelling, with a context"),
            ("# a comment", 0, "prose"),
            ("#", 0, "a bare rule of hashes"),
            ("#  ʁaːd  Rad  -> [ʁaːt]", 0, "prose that carries an arrow"),
            ("# THE CONDITION IS A CODA -> NOT A WORD EDGE", 0, "and shouts one"),
        ],
    )
    def test_the_comment_glyph_and_the_word_mark_are_told_apart_by_position(
        self, line, rules, because
    ):
        """A target is the whole of what stands left of the arrow.

        So the mark is a target exactly when it is the whole of it. Prose
        opening with the mark has words before its arrow if it carries one
        at all, which is what makes the two separable at all.
        """
        assert len(R.RuleSet.parse(line, FEATURES)) == rules, because

    def test_no_shipped_comment_line_is_read_as_a_rule(self):
        """The measurement the separation rests on, swept not sampled.

        The comment blocks in ``ipakit/data/rules`` are full of arrows --
        they tabulate derivations -- which is why "a comment does not
        rewrite" cannot be the rule. This asserts the rule that IS used
        holds of every one of them, so a comment written in a new file
        cannot quietly become a rule.
        """
        comments = 0
        read_as_rules: list[str] = []
        for name in R.available():
            path = R.RULES_DIR / f"{name}.rules"
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith("#"):
                    continue
                comments += 1
                if not R._is_comment(stripped, FEATURES):
                    read_as_rules.append(f"{name}: {stripped}")
        assert comments > 1000, f"only {comments} comment lines swept"
        assert read_as_rules == [], f"{len(read_as_rules)}: {read_as_rules[:3]}"

    def test_every_shipped_set_holds_exactly_the_lines_it_declares(self):
        """The other side of the same measurement, and the durable form.

        A count per set would be a table to keep in step by hand. What the
        reader must satisfy is that a set holds one rule per line that is
        neither blank nor prose -- so the file and the set are counted the
        same way, and a comment read as a rule shows up as a set that grew
        or as a file that stopped loading.
        """
        for name in R.available():
            text = (R.RULES_DIR / f"{name}.rules").read_text(encoding="utf-8")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            written = [ln for ln in lines if not R._is_comment(ln, FEATURES)]
            assert written, f"{name} declares no rules"
            assert len(R.shipped(name, FEATURES)) == len(written), name


class TestARunUsedAsATargetIsOneBoundary:
    """The third place the run rule has to hold, and the last one to.

    ``_anchors`` coalesces a run for an insertion and ``_side`` coalesces
    one in a context; a run used as the **target** was left as one site
    per written mark, so ``. -> #`` took ``a..b`` to ``a##b`` -- one
    boundary in, two out.

    ``a##b`` is the visible half. The quiet half is the trace: a rule
    that deletes every mark of a run spells the right surface and still
    reports two changes where the contract says there is one, which is
    the shape of defect this suite exists to catch. So the assertions
    here are on :meth:`Query.sites` and on the edits, and the spelling is
    checked as well rather than instead.

    The site is the run ``[lo, hi)``, and that is **not** the wider span
    that was refused: a target whose width the *rule* states -- ``ab ->
    ba``, n patterns and n terms with a permutation on the right. What
    that one costs is the reason it was refused. ``aa`` on ``aaa`` finds
    overlapping sites, so ``Query.sites``'s promise of non-overlapping
    positions stops being an accident of a one-wide scan;
    ``_carry_prosody`` has to say which of several new units inherits a
    mark; ``_check_no_exchange`` has to run per term. None of that is
    reached here. The rule states one pattern and matches one boundary,
    and the extra width is a fact about how the form was spelled, so the
    sites are disjoint by construction, the right of the arrow keeps its
    one implicit term, and a boundary has no prosody to inherit.
    """

    #: Every mark that reads as a boundary unit, off the declaration.
    MARKS = BOUNDARY_MARKS
    #: Runs of one, two and three, over every mark and every mixture. A
    #: run of one is in the corpus because the coalesced answer has to
    #: agree with the uncoalesced one where there is nothing to coalesce.
    RUNS = tuple(
        "".join(combination)
        for length in (1, 2, 3)
        for combination in itertools.product(BOUNDARY_MARKS, repeat=length)
    )
    #: Where the run sits: interior, initial, final.
    PLACES = (("a", "b"), ("", "ab"), ("ab", ""))
    #: One class target that reaches every mark, and one that restates
    #: the boundary at another level -- the rule the symptom was reported
    #: against.
    SPECS = ("% -> ∅", ". -> #")

    def test_a_run_is_one_site_however_long_and_however_spelled(self):
        """The sweep, on recognition rather than on the spelling."""
        checked = 0
        bad: list[str] = []
        for run in self.RUNS:
            for pre, post in self.PLACES:
                form = pre + run + post
                with _quiet():
                    items = R.units(form, FEATURES)
                start = len(pre)
                # A run that did not read as one unit per mark would make
                # the rest of this sweep agree about the wrong thing.
                assert [u.is_boundary for u in items].count(True) == len(run), form
                for spec in self.SPECS:
                    sites = R.parse(spec, FEATURES).query.sites(items, FEATURES)
                    checked += 1
                    got = [(s.start, s.end) for s in sites]
                    if got != [(start, start + len(run))]:
                        bad.append(f"{spec}: {form!r} -> {got}")
        # Exact, not a floor: every run against every placement and both
        # class targets. A floor cannot tell that the runs of three, or
        # one of the marks, left the sweep.
        expected = len(self.RUNS) * len(self.PLACES) * len(self.SPECS)
        assert len(self.RUNS) == sum(len(self.MARKS) ** n for n in (1, 2, 3))
        assert checked == expected == 930, f"sweep covered {checked}, not {expected}"
        assert bad == [], f"{len(bad)} of {checked}, first: {bad[:3]}"

    def test_the_derivation_reports_one_change_and_not_one_per_mark(self):
        """The quiet half: right surface, wrong number of changes.

        A deletion of every mark in a run comes out spelled correctly
        whether the run was one site or several, so the spelling cannot
        tell the two apart and the trace can.
        """
        checked = 0
        for run in ("..", "...", ".#", "#.", ".‿", "|‖", "..#"):
            form = f"a{run}b"
            with _quiet():
                assert ipakit.rewrite(form, "% -> ∅") == "ab", form
                derivation = ipakit.derive(form, "% -> ∅")
            (edit,) = derivation.edits
            assert (edit.start, edit.end) == (1, 1 + len(run)), form
            # The run as written is what the trace reports it read.
            assert edit.before == run and edit.after == "", form
            assert edit.is_deletion, form
            checked += 1
        assert checked == 7, f"sweep covered {checked}"

    def test_restating_a_run_at_another_level_writes_one_mark(self):
        """The visible symptom, and the length it is invariant over."""
        for run in (".", "..", "...", "...."):
            assert ipakit.rewrite(f"a{run}b", ". -> #") == "a#b", run

    def test_a_named_mark_takes_only_its_own_mark_out_of_a_run(self):
        """Which is what makes this a coalesced *match* and not a span.

        The run is walked as far as the pattern matches, so a rule that
        names one mark is exact about which boundary it means -- the same
        claim ``. -> ∅`` deleting a written ``#`` makes from the other
        side. Walking the whole run regardless would take marks the rule
        never named.
        """
        assert ipakit.rewrite("a.‿b", "‿ -> ∅") == "a.b"
        assert ipakit.rewrite("a‿.b", "‿ -> ∅") == "a.b"
        assert ipakit.rewrite("a.‿.b", "‿ -> ∅") == "a..b"
        assert ipakit.rewrite("a.‿b", ". -> ∅") == "ab", "the class takes the run"

    def test_context_reads_outward_from_the_whole_run(self):
        """A site's neighbors are the run's neighbors, not the mark's.

        And the run is not its own left context: ``% _`` looks for a
        boundary beside the target, and inside a run there is none,
        because the run *is* the boundary. Before this it found the mark
        next to it and fired.
        """
        assert ipakit.rewrite("a..b", ". -> # / a _ b") == "a#b"
        assert ipakit.rewrite("a..b", ". -> # / _ b") == "a#b"
        assert ipakit.rewrite("a..b", ". -> # / a _") == "a#b"
        assert ipakit.rewrite("a..b", ". -> # / % _") == "a..b"
        assert ipakit.rewrite("a..b", ". -> # / _ %") == "a..b"

    def test_the_sites_of_a_form_stay_disjoint_and_ordered(self):
        """``Query.sites`` promises non-overlapping positions.

        A wider site is where that promise would go quietly: two runs are
        maximal stretches and cannot overlap, and the scan resumes past
        the run rather than inside it, so the property is checked here
        rather than assumed from the shape of the loop.
        """
        forms = ("a..b..c", "..a..b..", "a.#.b", "a‿|‖b.c", "abc", "a.b.c")
        checked = 0
        for form in forms:
            with _quiet():
                items = R.units(form, FEATURES)
            for spec in (*self.SPECS, "% -> ∅ / a _"):
                sites = R.parse(spec, FEATURES).query.sites(items, FEATURES)
                spans = [(s.start, s.end) for s in sites]
                assert spans == sorted(spans), f"{spec}: {form!r} {spans}"
                for first, second in zip(spans, spans[1:], strict=False):
                    assert first[1] <= second[0], f"{spec}: {form!r} {spans}"
                checked += 1
        assert checked == len(forms) * 3 == 18, f"sweep covered {checked}"


class TestEnchainementIsNotExpressible:
    """A named limit, pinned rather than fixed.

    Enchaînement is what motivated moving boundaries at all: a French
    word-final consonant that is *always* pronounced becomes the onset of
    a following vowel-initial word, ``petite amie`` -> ``pə.ti.ta.mi``.
    The segmental string is **byte-identical** before and after -- only
    the dots move -- so it is a boundary rewrite in the exact sense this
    module now supports, and it is still not expressible. It needs two
    things, and the second is out of scope and staying out:

    1. moving boundaries, which is now available; and
    2. a syllable that **crosses a word boundary**, which no reading of a
       form can produce: ``Form.tree()`` splits on word before syllable,
       so a dot beside a word mark yields two syllables and never one
       spanning it.

    The second is not a gap waiting for a bracketing notation. A design
    review concluded that a Dyck/balanced-bracket model *entrenches*
    strict layering rather than relaxing it -- a balanced bracketing is
    strictly nested by definition -- and that the honest model for tier
    independence is autosegmental multi-tier intervals, which is a
    different representation and not a notation change. Recorded here so
    it is not rediscovered as a bug.
    """

    #: 'petite amie' with the liaison /t/ still in the first word, and the
    #: same phrase with the /t/ syllabified into the second, which is what
    #: enchaînement claims.
    BEFORE = "pə.tit‿a.mi"
    AFTER = "pə.ti.t‿a.mi"

    def test_the_boundary_half_is_expressible(self):
        """The dot moves, and the segments do not."""
        moved = ipakit.rewrite(self.BEFORE, "∅ -> . / [vowel] _ [manner=plosive] ‿")
        assert moved == self.AFTER
        assert _segmental(moved) == _segmental(self.BEFORE)
        assert "".join(_segmental(moved)) == "pətitami"

    def test_but_a_syllable_never_crosses_a_word_boundary(self):
        """The half that is out of scope, measured rather than asserted.

        The dots are written where enchaînement wants them and the
        reading still does not deliver ``ta``: the ``t`` comes back as a
        syllable of its own, because ``tree()`` splits on word first. The
        only string that *does* read as ``ta`` is the one with no word
        division left in it -- a different claim about the phrase.
        """
        split = ["pə", "ti", "t", "a", "mi"]
        tree = ipakit.Form.parse(self.AFTER, FEATURES).tree()
        assert [n.to_ipa() for n in tree.at("syllable")] == split
        assert [n.to_ipa() for n in tree.at("word")] == ["pətit", "ami"]
        # The same with '#' written instead of the linking mark, so this
        # is the tier relation and not something about '‿'.
        hashed = ipakit.Form.parse("pə.ti.t#a.mi", FEATURES).tree()
        assert [n.to_ipa() for n in hashed.at("syllable")] == split
        # What enchaînement wants to be able to say, and the only spelling
        # that says it: one word, which is not what the phrase is.
        joined = ipakit.Form.parse("pə.ti.ta.mi", FEATURES).tree()
        assert [n.to_ipa() for n in joined.at("syllable")] == ["pə", "ti", "ta", "mi"]
        assert [n.to_ipa() for n in joined.at("word")] == ["pətitami"]

    def test_and_a_rule_cannot_reach_that_spelling_either(self):
        """Erasing the division is the only way there, and it is a lie.

        ``. -> ∅`` is "a boundary at syllable level or stronger", so it
        takes the word division with it -- the class rule again. The
        result reads as one word: the phrase has been turned into
        something it is not, which is precisely why enchaînement is a
        limit and not a rule that has yet to be written.
        """
        flattened = ipakit.rewrite(self.AFTER, ". -> ∅")
        assert flattened == "pətitami"
        assert _segmental(flattened) == _segmental(self.AFTER)
        tree = ipakit.Form.parse(flattened, FEATURES).tree()
        assert [n.to_ipa() for n in tree.at("word")] == ["pətitami"], "one word now"


# --------------------------------------------------------------------------
# A rule that parses and finds a site must be able to change something
# --------------------------------------------------------------------------


#: Targets to build rules from: literal phones, a bundle, the declared
#: boundary marks, and the wildcard. Read off the declaration where it can
#: be, so a newly declared mark joins these sweeps without an edit here.
SWEEP_TARGETS = (
    "t",
    "d",
    "a",
    "aː",
    "ˈa",
    "[voiced=+]",
    "[manner=plosive]",
    "[vowel stress=primary]",
    "[voiced=α]",
    R.ANY_BOUNDARY,
    *BOUNDARY_MARKS,
)

#: What those targets may become: a phone, a bundle, a boundary, a run of
#: two boundaries, deletion, and the same spellings the targets use -- so
#: the identity rules are generated rather than avoided.
SWEEP_BECOMES = (
    "t",
    "d",
    "a",
    "aː",
    "ˈa",
    "ʔ",
    "[voiced=+]",
    "[voiced=-]",
    "[manner=plosive]",
    "[stress=primary]",
    "[voiced=α]",
    "[voiced=-α]",
    "∅",
    *BOUNDARY_MARKS,
)

#: Forms to run them against: segments, prosody, every boundary mark, a
#: two-mark run, a form-final mark and a bare space.
#:
#: More than one vowel and more than one stressed vowel, deliberately. A
#: corpus holding only ``ˈa`` makes ``[vowel stress=primary] -> ˈa`` look
#: like a rule that can never fire, when what it cannot do is fire on
#: *that* form -- and a sweep whose thinness reads as a defect teaches
#: the wrong thing about the rules it clears.
SWEEP_FORMS = (
    "ata",
    "ada",
    "ˈata",
    "aːta",
    "kæt",
    "tʰa",
    "a.a",
    "a#a",
    "a‿a",
    "a|a",
    "a‖a",
    "a b",
    "a.#a",
    "a..a",
    "at#a",
    "at.",
    "at#",
    ".at",
    "iti",
    "ˈiti",
    "ˈuku",
    "apa",
    "saɡa",
    "ˈaːta",
)


class TestARuleMustBeAbleToEdit:
    """``[voiced=+] -> [voiced=+]`` parsed, recognized, and never fired.

    The right of the arrow asked for exactly what the target had to have
    to match, so :meth:`Action.edit` found ``before == after`` at every
    site and answered ``None``. The rule was well formed, found its
    positions, reported no change, and said nothing about why -- which is
    the shape ``_check_inserted_change`` was written to refuse for an
    insertion and the shape this suite exists to catch.
    """

    @pytest.mark.parametrize(
        "bad,shape",
        [
            ("[voiced=+] -> [voiced=+]", "a value restated"),
            ("[manner=plosive] -> [manner=plosive]", "and another"),
            ("[voiced=α] -> [voiced=α]", "a variable bound and written back"),
            ("[vowel stress=primary] -> [stress=primary]", "prosody restated"),
            ("[manner=plosive voiced=+] -> [voiced=+]", "part of the target"),
            ("d -> d", "a literal that writes itself"),
            ("aː -> aː", "prosody and all"),
            ("ˈa -> ˈa", "the other prosody"),
            ("‿ -> ‿", "a mark names one glyph, so this is one too"),
            ("| -> |", "and so is this"),
        ],
    )
    def test_a_rule_that_can_never_edit_is_refused_where_it_is_read(self, bad, shape):
        """Refused at parse, for ``_check_inserted_change``'s reason.

        Nothing about it depends on the form, so a set holding one fails
        to load rather than loading and deriving a quietly unchanged
        answer one word at a time.
        """
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert "silently" in str(caught.value), shape

    @pytest.mark.parametrize(
        "good,form,expected,shape",
        [
            ("[voiced=α manner=plosive] -> [voiced=-α]", "ada", "ata", "a flip"),
            ("[voiced=α manner=plosive] -> [voiced=-α]", "ata", "ada", "either way"),
            ("n -> [place=α] / _ [place=α]", "anpa", "ampa", "the canonical one"),
            ("ˈa -> a", "ˈata", "ata", "prosody named on one side only"),
            ("aː -> a", "aːta", "ata", "and the other prosody"),
            ("[vowel stress=primary] -> [stress=secondary]", "ˈata", "ˌata", "a move"),
        ],
    )
    def test_the_refusal_is_not_wider_than_that(self, good, form, expected, shape):
        """Each of these differs from its target somewhere, and edits."""
        assert ipakit.rewrite(form, good) == expected, shape

    @pytest.mark.parametrize("spec", ["# -> #", ". -> ."])
    def test_identity_across_a_level_pattern_is_a_real_rewrite(self, spec):
        """The interesting half, and why the guard is not simply textual.

        A boundary pattern is a *class*: ``#`` matches a word boundary or
        anything stronger, so ``# -> #`` writing ``#`` where a ``‖`` stood
        is a downgrade rather than a no-op. Identity on the two sides of a
        class says something; identity on the two sides of a mark, which
        names one glyph, cannot.
        """
        mark = spec[0]
        stronger = [
            m
            for m in BOUNDARY_MARKS
            if m != mark
            and R.spell(R.parse(spec, FEATURES).apply(f"a{m}b")[0]) != f"a{m}b"
        ]
        assert stronger, f"{spec} rewrites no other mark, so it IS a no-op"
        for other in stronger:
            assert (
                R.spell(R.parse(spec, FEATURES).apply(f"a{other}b")[0]) == f"a{mark}b"
            )

    def test_the_guard_states_what_it_cannot_see(self):
        """A pinned escape, with the measurement that draws the line.

        ``d -> [voiced=+]`` cannot edit either -- ``d`` is voiced already
        -- but the guard does not reach it, and deliberately. It reads
        only what the *rule states*, never what the inventory says of a
        phone the rule names, because a literal's bundle is the flat
        projection and a tied unit projects its FIRST element's features:
        ``a͜ɪ`` reads ``manner=vowel`` while ``a͜ɪ -> [manner=vowel]``
        answers ``a``, collapsing the tie. So the bundle is not a
        guarantee, and a guard that read one off it would refuse rules
        that do edit.

        The count below is that measurement, so this escape closes only
        deliberately. If it reaches zero, the bundle has become a
        guarantee and the guard could be widened.
        """
        R.parse("d -> [voiced=+]", FEATURES)
        assert ipakit.rewrite("ada", "d -> [voiced=+]") == "ada", "still a no-op"

        checked = movers = 0
        for phone in _phones():
            read = R._reads_as(phone, FEATURES)
            if len(read) != 1 or read[0].segment is None:
                continue
            for key, value in read[0].features.items():
                if key not in FEATURES.features:
                    continue
                try:
                    rule = R.parse(f"{phone} -> [{key}={value}]", FEATURES)
                except R.RuleError:
                    continue
                checked += 1
                if R.spell(rule.apply(phone, FEATURES)[0]) != phone:
                    movers += 1
        assert checked > 2000, f"only {checked} literal/bundle pairs swept"
        assert movers > 0, "the flat bundle has become a guarantee; widen the guard"

    def test_no_generated_rule_finds_sites_and_edits_none_of_them(self):
        """The general shape, swept rather than named.

        A rule that recognizes a position and then declines every one of
        them, on every form, is a rule that cannot work. That covers the
        restated bundle above and the word mark a file could not name
        alike, and it is the property worth holding rather than either
        case on its own.

        Where it stops is a **spelled** right-hand side. A rule that says
        what to write is refused at parse if it writes what it matched, so
        no spelled rule survives to be idle. A bracketed one can, and for
        two reasons the rule itself does not state: the unit already had
        the value asked for (``t -> [voiced=-]``), or the inventory can
        spell the result neither as a registered phone nor as a composed
        one and the rule declines rather than inventing a symbol. Both are
        facts about the data, so the idle set is asserted to be exactly
        the bracketed ones and asserted to be non-empty -- if it empties,
        one of those two has stopped being reachable and this pin should
        say so rather than pass quietly.
        """
        rules = built = recognized = 0
        idle: list[str] = []
        spelled_idle: list[str] = []
        for target, becomes in itertools.product(SWEEP_TARGETS, SWEEP_BECOMES):
            spec = f"{target} -> {becomes}"
            rules += 1
            try:
                rule = R.parse(spec, FEATURES)
            except R.RuleError:
                continue
            built += 1
            sites = edits = 0
            for form in SWEEP_FORMS:
                items = R.units(form, FEATURES)
                sites += len(rule.recognize(items, FEATURES))
                edits += len(rule.edits(items, FEATURES))
            if not sites:
                continue
            recognized += 1
            if edits:
                continue
            idle.append(f"{spec}: {sites} sites, no edit on any form")
            if not isinstance(rule.becomes, dict):
                spelled_idle.append(spec)
        assert rules == len(SWEEP_TARGETS) * len(SWEEP_BECOMES)
        assert built > 100, f"only {built} of {rules} rules parsed"
        assert recognized > 100, f"only {recognized} rules found a site"
        assert spelled_idle == [], f"{len(spelled_idle)}: {spelled_idle[:3]}"
        assert idle, "the escape has closed; widen the guard or drop this pin"

    def test_the_same_sweep_run_through_a_set_agrees(self):
        """Through ``rewrite``, which is where the word mark was lost.

        The engine found the site and made the edit all along; the line
        reader dropped the rule, so nothing downstream of it could tell.
        A sweep that only asks ``Rule`` cannot see that, and this is the
        same corpus asked at the entry point a caller uses.
        """
        checked = 0
        silent: list[str] = []
        for target, becomes in itertools.product(SWEEP_TARGETS, SWEEP_BECOMES):
            spec = f"{target} -> {becomes}"
            try:
                rule = R.parse(spec, FEATURES)
            except R.RuleError:
                continue
            for form in SWEEP_FORMS:
                items = R.units(form, FEATURES)
                if not rule.edits(items, FEATURES):
                    continue
                checked += 1
                with _quiet():
                    if ipakit.rewrite(form, spec) == form:
                        silent.append(f"{spec} on {form!r}")
        assert checked > 500, f"only {checked} firing rule/form pairs swept"
        assert silent == [], f"{len(silent)} of {checked}, first: {silent[:3]}"


class TestNamingAMarkIsAtLeastAsStrongAsAClass:
    """``# -> ∅`` left ``a#a`` alone while ``. -> ∅`` took the mark out.

    Naming the mark is how a rule says *which* boundary it means, so a
    rule that names one must reach it wherever a pattern that merely
    covers it reaches it. It was the other way round for the word mark,
    and silently: the line reader read ``# -> ∅`` as prose, the set held
    no rule, and the form came back unchanged.
    """

    #: Every pattern that covers a boundary without naming one: the
    #: declared separators, which match their level or stronger, and the
    #: wildcard, which matches every boundary there is.
    GENERAL = (*SEPARATORS, R.ANY_BOUNDARY)

    #: Where the mark can stand: between segments, at each end, and twice.
    SHAPES = ("a{m}b", "{m}ab", "ab{m}", "a{m}b{m}c")

    def test_a_rule_naming_a_mark_deletes_it_wherever_a_class_does(self):
        """The specificity relation, over every declared mark and shape.

        Asked of the deletion because that is the one operation every
        boundary admits, and asked through ``rewrite`` because the entry
        point is where the answer was lost.
        """
        checked = reached = 0
        weaker: list[str] = []
        for mark in BOUNDARY_MARKS:
            for shape in self.SHAPES:
                form = shape.format(m=mark)
                named = ipakit.rewrite(form, f"{mark} -> ∅")
                for general in self.GENERAL:
                    if general == mark:
                        continue
                    checked += 1
                    covered = ipakit.rewrite(form, f"{general} -> ∅")
                    if mark in covered:
                        continue
                    reached += 1
                    if mark in named:
                        weaker.append(
                            f"{general!r} clears {mark!r} from {form!r} "
                            f"and {mark!r} leaves {named!r}"
                        )
        expected = len(BOUNDARY_MARKS) * len(self.SHAPES) * len(self.GENERAL)
        assert checked == expected - len(SEPARATORS) * len(self.SHAPES)
        assert checked > 40, f"only {checked} mark/class pairs swept"
        assert reached > 30, f"only {reached} pairs where the class acts at all"
        assert weaker == [], f"{len(weaker)} of {reached}: {weaker[:3]}"

    def test_a_mark_names_only_itself_and_a_class_takes_the_run(self):
        """The other direction, which is the run rule and not a defect.

        ``. -> ∅`` is "syllable or stronger" and takes the whole of a run;
        ``‿ -> ∅`` names one mark and leaves the rest where it was
        written. Specificity means the named rule is not WEAKER, not that
        the two are the same rule.
        """
        assert ipakit.rewrite("a.‿b", ". -> ∅") == "ab"
        assert ipakit.rewrite("a.‿b", "‿ -> ∅") == "a.b"
        assert ipakit.rewrite("a.#b", "# -> ∅") == "a.b"
        assert ipakit.rewrite("a.#b", ". -> ∅") == "ab"

    def test_writing_a_mark_target_in_a_set_holds_the_edge_invariant(self):
        """The invariant PR #86 strengthened, over the newly reachable rules.

        A form's end is a word boundary whether or not ``#`` is typed, so
        ``r(f) == strip(r('#' + f)) == strip(r(f + '#'))``. The rules that
        name a mark as their target are the ones a file could not hold
        until now, so they are the ones this had never been asked of.
        """
        checked = 0
        bad: list[str] = []
        for mark in BOUNDARY_MARKS:
            for becomes in ("∅", R.ANY_BOUNDARY, *BOUNDARY_MARKS):
                spec = f"{mark} -> {becomes}"
                try:
                    R.parse(spec, FEATURES)
                except R.RuleError:
                    continue
                for form in ("kæt", "kæ.t", "kæt.a", "a‿b"):
                    with _quiet():
                        base = _ends_stripped(ipakit.rewrite(form, spec))
                        for written in (f"#{form}", f"{form}#", f"#{form}#"):
                            got = _ends_stripped(ipakit.rewrite(written, spec))
                            checked += 1
                            if got != base:
                                bad.append(
                                    f"{spec}: {form}->{base} vs {written}->{got}"
                                )
        assert checked > 200, f"only {checked} edge triples swept"
        assert bad == [], f"{len(bad)} of {checked}, first: {bad[:3]}"


class TestABundleIsReadAsWhatWasWritten:
    """``[stress=not_declared stress=primary]`` parsed and wrote ``ˈa``.

    ``dict(...)`` keeps the last of a repeated key, so the undeclared
    value was erased before the value arm looked at it: the check that
    exists to catch a misspelled value was blind to any value a second
    term stood in front of. The same construction was on both sides of
    the arrow, so ``[voiced=not_declared voiced=+]`` did it on the left.
    """

    @pytest.mark.parametrize(
        "bad,shape",
        [
            ("a -> [stress=not_declared stress=primary]", "on the right"),
            ("[voiced=not_declared voiced=+] -> a", "on the left"),
            ("a -> [stress=primary stress=not_declared]", "either order"),
            ("[voiced=+ voiced=-] -> a", "a contradiction no unit satisfies"),
            ("a -> [stress=primary stress=primary]", "even where they agree"),
            ("t -> ʔ / _ [voiced=+ voiced=-]", "in a context item too"),
        ],
    )
    def test_a_repeated_key_is_refused_on_both_sides(self, bad, shape):
        with pytest.raises(R.RuleError) as caught:
            R.parse(bad, FEATURES)
        assert "more than once" in str(caught.value), shape

    def test_every_written_term_is_validated_and_not_only_the_survivor(self):
        """Over the token sequence, since a mapping cannot see the loss.

        A test on the resulting mapping is exactly what could not have
        caught this: by the time the mapping exists the discarded term is
        gone. So the sweep pairs a bad term with a good one on the same
        key and asserts the rule is refused whichever position it takes.
        """
        good = {"stress": "primary", "voiced": "+", "manner": "plosive"}
        checked = 0
        passed: list[str] = []
        for key, value in good.items():
            for bad in ("not_declared", "0", "obstruent"):
                for terms in (
                    (f"{key}={bad}", f"{key}={value}"),
                    (f"{key}={value}", f"{key}={bad}"),
                ):
                    spec = f"a -> [{' '.join(terms)}]"
                    checked += 1
                    try:
                        R.parse(spec, FEATURES)
                    except R.RuleError:
                        continue
                    passed.append(spec)
        assert checked == len(good) * 3 * 2 == 18
        assert passed == [], f"{len(passed)} of {checked} parsed: {passed[:3]}"

    def test_a_bundle_with_no_repeat_is_read_as_the_mapping_it_builds(self):
        """The equality the refusal buys, asserted rather than assumed.

        With no key written twice the term sequence and the mapping have
        the same length, so validating the mapping IS validating what was
        written -- which is what makes the check above unnecessary a
        second time rather than merely passing today.
        """
        checked = 0
        for source in (
            "[voiced=+ manner=plosive]",
            "[stress=primary length=long]",
            "[manner=plosive]",
            "[voiced=α place=labial]",
        ):
            terms = [t for t in source[1:-1].split() if t]
            written = R._keyed(source, terms)
            assert len(written) == len(dict(written)) == len(terms), source
            checked += 1
        assert checked == 4


class TestARunIsABoundaryOnTheRightOfTheArrowToo:
    """``. -> .#`` was refused as "not a boundary", and it is one.

    The exchange guard asked exact membership of the whole spelling in
    the declared marks, so a right-hand side made *entirely* of boundary
    marks failed a test named for whether it was a boundary at all. Under
    this module's own run rule a run of marks is one boundary, which is
    the reading every other position already took: ``∅ -> .# / a _ b``
    was accepted and wrote that very run, so the same string was legal on
    the right of an insertion and refused on the right of a rewrite.
    """

    def test_a_rewrite_may_write_a_run_as_an_insertion_may(self):
        """The two positions agree, which is what was wrong."""
        assert ipakit.rewrite("ab", "∅ -> .# / a _ b") == "a.#b"
        assert ipakit.rewrite("a.b", ". -> .#") == "a.#b"
        assert ipakit.rewrite("a.b", ". -> #.") == "a#.b"

    @pytest.mark.parametrize("stray", ["a", "∅", R.ANY_BOUNDARY])
    def test_a_run_carrying_anything_else_is_still_refused(self, stray):
        """The guard is per glyph, so one segment among the marks fails.

        ``%`` is deliberately among these: it is a wildcard over the
        declared marks and names no particular one, so it can be
        recognized and never written.
        """
        with pytest.raises(R.RuleError):
            R.parse(f". -> .{stray}", FEATURES)

    def test_a_run_a_rule_wrote_is_a_run_every_context_can_read(self):
        """The measurement the acceptance rests on.

        What would make this wrong is a rule writing a boundary no rule
        can then match. Every pattern that reaches the run reaches it, the
        class takes the whole of it and the named mark takes its own.
        """
        written = ipakit.rewrite("a.b", ". -> .#")
        assert written == "a.#b"
        for general in (*SEPARATORS, R.ANY_BOUNDARY):
            assert ipakit.rewrite(written, f"b -> x / {general} _") == "a.#x"
        assert ipakit.rewrite(written, ". -> ∅") == "ab"
        assert ipakit.rewrite(written, "# -> ∅") == "a.b"
        assert ipakit.rewrite(written, "∅ -> e / . _ b") == "a.#eb"

    def test_a_context_naming_two_boundaries_is_still_refused(self):
        """A different proposition, and it did not move.

        There the *rule* states two patterns and a run is one boundary, so
        the second can never hold. Here the rule states one boundary and
        spells it with the marks it was written with.
        """
        assert ipakit.rewrite("a.#b", "b -> x / . # _") == "a.#b"
        assert ipakit.rewrite("a.#b", "b -> x / . _") == "a.#x"

    def test_every_run_of_declared_marks_is_writable(self):
        """Swept over the declaration rather than the pair that was found."""
        checked = 0
        refused: list[str] = []
        for first, second in itertools.product(BOUNDARY_MARKS, repeat=2):
            spec = f". -> {first}{second}"
            checked += 1
            try:
                rule = R.parse(spec, FEATURES)
            except R.RuleError as caught:
                refused.append(f"{spec}: {caught}")
                continue
            got = R.spell(rule.apply("a.b", FEATURES)[0])
            assert got == f"a{first}{second}b", spec
        assert checked == len(BOUNDARY_MARKS) ** 2
        assert checked > 20, f"only {checked} runs swept"
        assert refused == [], f"{len(refused)} of {checked}: {refused[:3]}"
