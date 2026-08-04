"""An interval is rebased under an edit, and refused where it has no image.

Piece 4 of the tier increment, and the last. ``tests/test_tiers.py`` tests
the declared vocabulary, ``tests/test_intervals.py`` the span on a
``Form``, ``tests/test_tier_context.py`` the rule term that reads one;
this file tests what happens to a span when the rule underneath it
rewrites the sequence it indexes.

The declared policy, and every case below is an instance of it: **an
interval may lose material to an edit and may never gain material from
outside itself.** So

* an edit wholly outside a span moves it or does not, and its material
  never joins the span -- which decides the insertion sitting exactly on
  an endpoint, the one case of the three that is live on shipped data;
* an edit wholly inside a span changes what the span holds, and the span
  stretches or shrinks with it, including where the two are coextensive;
* an edit that rewrote **across** an endpoint leaves that endpoint with no
  image, and rebasing is refused rather than answered.

Three things are asserted about the refusal rather than assumed: that the
case is reachable at all, that no shipped rule reaches it, and that
``apply`` still answers where ``rewrite`` refuses -- the units were never
in doubt.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit import rules as R
from ipakit.form import Form, Interval, units
from ipakit.rules import TIER_OPEN, Edit, RebaseError, Site

from tests.test_rule_sets import CORPUS

FEATURES = ipakit.load_ipa_features()

#: The enchaînement form piece 3 works on, and its four syllables. The
#: third crosses the linking mark, which is what no tree can state.
LIAISON = "pətit‿ami"
SYLLABLES = ((0, 2), (2, 4), (4, 7), (7, 9))


def _form(text: str, spans: tuple[tuple[str, int, int], ...]) -> Form:
    read = Form.parse(text, FEATURES)
    return Form.of(read.units, [Interval(t, a, b, FEATURES) for t, a, b in spans])


def _liaison() -> Form:
    return _form(LIAISON, tuple(("syllable", a, b) for a, b in SYLLABLES))


def _edit(start: int, end: int, replacement: str, rule: str = "made up") -> Edit:
    """One edit, built by hand, so a case need not wait on a rule to spell it."""
    return Edit(
        rule=rule,
        start=start,
        end=end,
        replacement=tuple(units(replacement, FEATURES)),
        before="",
        after=replacement,
        site=Site(start=start, end=end),
    )


def _spans(form: Form) -> tuple[tuple[int, int], ...]:
    return tuple((s.start, s.end) for s in form.intervals)


def _corpus() -> list[tuple[str, str]]:
    """Every shipped set's own words, and each with one dot written into it.

    The same construction piece 3 swept, and the dot matters here for the
    same reason it mattered there: it is the only tier a transcription can
    spell, so it is what a caller syllabifying a form would hand in.
    """
    out: list[tuple[str, str]] = []
    for name, words in CORPUS.items():
        for word in words:
            out.append((name, word))
            read = list(units(word, FEATURES))
            for cut in range(1, len(read)):
                if read[cut - 1].is_boundary or read[cut].is_boundary:
                    continue
                out.append(
                    (
                        name,
                        "".join(u.text for u in read[:cut])
                        + "."
                        + "".join(u.text for u in read[cut:]),
                    )
                )
    return out


CORPUS_FORMS = _corpus()


# ----------------------------------------------------------------------
# The three endpoint positions
# ----------------------------------------------------------------------


class TestTheThreeEndpointPositions:
    """``p <= start``, ``p >= end``, and ``start < p < end``.

    Each is exercised at each of the three deltas an edit can carry, so a
    case is not passing because the delta happened to be zero.
    """

    @pytest.mark.parametrize("replacement,delta", [("", -1), ("s", 0), ("st", 1)])
    def test_an_edit_wholly_after_the_span_moves_nothing(
        self, replacement: str, delta: int
    ) -> None:
        span = Interval("mora", 0, 2, FEATURES)
        assert _spans(
            Form.of(
                units("abcde", FEATURES),
                R.rebase([span], [_edit(3, 4, replacement)], FEATURES),
            )
        ) == ((0, 2),)

    @pytest.mark.parametrize("replacement,delta", [("", -1), ("s", 0), ("st", 1)])
    def test_an_edit_wholly_before_the_span_shifts_both_ends(
        self, replacement: str, delta: int
    ) -> None:
        span = Interval("mora", 3, 5, FEATURES)
        moved = R.rebase([span], [_edit(0, 1, replacement)], FEATURES)
        assert (moved[0].start, moved[0].end) == (3 + delta, 5 + delta)

    @pytest.mark.parametrize("replacement", ["", "s", "st"])
    def test_an_endpoint_inside_a_rewritten_span_is_refused(
        self, replacement: str
    ) -> None:
        """The one case with no arithmetic answer: the edit says nothing
        about where inside its replacement a position it swallowed went."""
        span = Interval("mora", 0, 2, FEATURES)
        with pytest.raises(RebaseError) as caught:
            R.rebase([span], [_edit(1, 3, replacement, rule="wide")], FEATURES)
        message = str(caught.value)
        assert "ends at 2" in message and "[1, 3)" in message
        assert "wide" in message, "the refusal must name the rule that made the edit"

    def test_and_it_is_refused_at_the_start_endpoint_too(self) -> None:
        span = Interval("mora", 2, 4, FEATURES)
        with pytest.raises(RebaseError) as caught:
            R.rebase([span], [_edit(1, 3, "s")], FEATURES)
        assert "starts at 2" in str(caught.value)

    def test_the_control_is_that_the_same_span_rebases_off_by_one(self) -> None:
        """Move the span one place and the refusal goes away, so the
        refusal is the position and not the shape of the case."""
        span = Interval("mora", 0, 1, FEATURES)
        assert _spans(
            Form.of(
                units("abcde", FEATURES),
                R.rebase([span], [_edit(1, 3, "s")], FEATURES),
            )
        ) == ((0, 1),)


class TestTheRefusedCaseIsReachableAndNoShippedRuleReachesIt:
    """Pinned in both directions, because a refusal nothing can trigger is
    not a policy and a refusal every rule triggers is not shippable."""

    def test_a_rule_can_produce_a_target_wider_than_one_unit(self) -> None:
        """``_target_end`` extends a boundary target over the whole run it
        opens, so a two-glyph boundary run is one two-unit target."""
        found = R.parse(". -> #", FEATURES).edits("a..b", FEATURES)
        assert [(e.start, e.end, len(e.replacement)) for e in found] == [(1, 3, 1)]

    def test_and_that_rule_refuses_a_span_ending_inside_the_run(self) -> None:
        held = _form("a..b", (("mora", 0, 2),))
        with pytest.raises(RebaseError):
            R.parse(". -> #", FEATURES).rewrite(held, FEATURES)

    def test_no_shipped_rule_makes_an_edit_wider_than_one_unit(self) -> None:
        """So the refusal above is a stated limit rather than a live cost.

        If this ever fails, a shipped set has grown a boundary-run target
        and the policy needs re-arguing against it -- which is the point of
        asserting it rather than believing it.
        """
        widths: set[int] = set()
        checked = 0
        for name, word in CORPUS_FORMS:
            for step in R.shipped(name, FEATURES).derive(word, FEATURES).steps:
                for edit in step.edits:
                    widths.add(edit.end - edit.start)
                    checked += 1
        assert checked > 500, "sweep did not run"
        assert max(widths) == 1, f"a shipped rule targets {max(widths)} units"
        assert widths == {0, 1}, "insertions and single-unit targets, and nothing else"


# ----------------------------------------------------------------------
# The seam: an insertion exactly on an endpoint
# ----------------------------------------------------------------------


class TestAnInsertionOnAnEndpointLandsOutsideTheSpan:
    """The live case, and the one the policy is really about.

    ``docs/form.md``'s rule is that an unspecified tier is not invented.
    Nothing says which mora an epenthetic vowel joins, intervals do not
    tile, and a unit on no tier is an ordinary state of a form -- so the
    new material joins no span rather than the span it abuts.
    """

    def test_an_insertion_at_the_start_pushes_the_span_right(self) -> None:
        span = Interval("mora", 2, 4, FEATURES)
        moved = R.rebase([span], [_edit(2, 2, "s")], FEATURES)
        assert (moved[0].start, moved[0].end) == (3, 5)

    def test_an_insertion_at_the_end_leaves_the_span_alone(self) -> None:
        span = Interval("mora", 2, 4, FEATURES)
        moved = R.rebase([span], [_edit(4, 4, "s")], FEATURES)
        assert (moved[0].start, moved[0].end) == (2, 4)

    def test_so_the_inserted_unit_is_on_no_tier_at_all(self) -> None:
        """Stated as the property rather than as two endpoint values: the
        position the new unit occupies is covered by neither neighbor."""
        held = _form("abcd", (("mora", 0, 2), ("mora", 2, 4)))
        after, found = R.parse("∅ -> s / b _ c", FEATURES).rewrite(held, FEATURES)
        assert after.to_ipa() == "abscd"
        assert _spans(after) == ((0, 2), (3, 5))
        new = [i for i in range(len(after.units)) if after.units[i].text == "s"]
        assert new == [2]
        assert not [
            span for span in after.intervals if span.start <= 2 < span.end
        ], "the epenthetic unit joined a mora nothing put it in"

    def test_the_control_is_that_an_insertion_strictly_inside_does_grow_it(
        self,
    ) -> None:
        """Not a contradiction of the policy but the other half of it: a
        unit inserted between two units the span holds has nowhere else to
        be, so including it adds no claim."""
        held = _form("abcd", (("mora", 0, 4),))
        after, _ = R.parse("∅ -> s / b _ c", FEATURES).rewrite(held, FEATURES)
        assert after.to_ipa() == "abscd" and _spans(after) == ((0, 5),)

    def test_an_empty_span_with_an_insertion_on_it_is_refused(self) -> None:
        """The one place the two clauses disagree: a span with no inside
        has no outside for the new material to be on."""
        span = Interval("mora", 2, 2, FEATURES)
        with pytest.raises(RebaseError) as caught:
            R.rebase([span], [_edit(2, 2, "s")], FEATURES)
        assert "empty" in str(caught.value)


# ----------------------------------------------------------------------
# The split
# ----------------------------------------------------------------------


class TestALengthChangingRewriteStretchesTheSpanItIsInside:
    """``a͜ɪ -> ai`` and the five other shipped splits.

    Both endpoints have a unique image here, so this is determined and not
    a policy choice. What *is* a choice is declining to say the result is
    two morae: that is a well-formedness statement about a language's tier,
    it is structure creation, and a rule may not write a tier.
    """

    def test_a_split_coextensive_with_a_span_stretches_it(self) -> None:
        held = _form("ka͜ɪ", (("mora", 1, 2),))
        after, _ = R.parse("a͜ɪ -> ai", FEATURES).rewrite(held, FEATURES)
        assert after.to_ipa() == "kai" and _spans(after) == ((1, 3),)

    def test_the_same_edit_inside_a_wider_span_grows_it_by_the_same_delta(
        self,
    ) -> None:
        """Which is the argument against refusing the coextensive case. The
        edit is the same edit; refusing it only where a span happens to end
        exactly on it would make the policy depend on nothing phonological.
        """
        held = _form("ka͜ɪt", (("mora", 0, 3),))
        after, _ = R.parse("a͜ɪ -> ai", FEATURES).rewrite(held, FEATURES)
        assert after.to_ipa() == "kait" and _spans(after) == ((0, 4),)

    def test_a_deletion_inside_a_span_shrinks_it(self) -> None:
        held = _form("kans", (("mora", 0, 3),))
        after, _ = R.parse("n -> ∅ / _ s", FEATURES).rewrite(held, FEATURES)
        assert after.to_ipa() == "kas" and _spans(after) == ((0, 2),)

    def test_a_substitution_inside_a_span_moves_nothing(self) -> None:
        held = _liaison()
        after, found = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES).rewrite(
            held, FEATURES
        )
        assert after.to_ipa() == "pətʰitʰ‿ami"
        assert found and _spans(after) == SYLLABLES


class TestSeveralEditsAtOnce:
    """A rule finds every site against one snapshot, so its edits are
    disjoint and all indexed against the sequence before any of them ran.
    That is what lets the deltas be summed rather than applied in order."""

    def test_the_deltas_sum(self) -> None:
        span = Interval("mora", 4, 6, FEATURES)
        moved = R.rebase([span], [_edit(0, 1, ""), _edit(2, 3, "st")], FEATURES)
        assert (moved[0].start, moved[0].end) == (4, 6)

    def test_and_the_order_they_are_given_in_does_not_matter(self) -> None:
        span = Interval("mora", 4, 6, FEATURES)
        forward = R.rebase([span], [_edit(0, 1, "st"), _edit(2, 3, "st")], FEATURES)
        backward = R.rebase([span], [_edit(2, 3, "st"), _edit(0, 1, "st")], FEATURES)
        assert forward == backward
        assert (forward[0].start, forward[0].end) == (6, 8)

    def test_a_span_is_rebased_independently_of_its_neighbors(self) -> None:
        held = _form("abcd", (("mora", 0, 2), ("syllable", 1, 4)))
        after, _ = R.parse("a -> ∅", FEATURES).rewrite(held, FEATURES)
        assert _spans(after) == ((0, 1), (0, 3))


# ----------------------------------------------------------------------
# The pins piece 3 left, replaced
# ----------------------------------------------------------------------


class TestApplyAndRewriteAreOneOperation:
    """``Rule.apply`` still answers with units, and that is now a
    projection of ``Rule.rewrite`` rather than a gap where rebasing should
    have been. Piece 3 pinned the drop; what is pinned here is that the
    drop loses only the tier."""

    def test_apply_returns_units_and_no_intervals(self) -> None:
        held = _liaison()
        out, found = R.parse("t -> ∅ / _ i", FEATURES).apply(held, FEATURES)
        assert isinstance(out, list) and all(isinstance(u, R.Unit) for u in out)
        assert found and len(out) < len(held.units)

    def test_and_rewrite_answers_with_the_same_units_and_the_spans(self) -> None:
        held = _liaison()
        rule = R.parse("t -> ∅ / _ i", FEATURES)
        out, found = rule.apply(held, FEATURES)
        after, again = rule.rewrite(held, FEATURES)
        assert tuple(out) == after.units and found == again
        assert after.intervals and after.intervals != held.intervals

    def test_the_two_agree_on_every_form_in_the_corpus(self) -> None:
        """Swept rather than sampled, because "one implementation" is a
        property and a named case only shows it held once."""
        checked = 0
        for name, word in CORPUS_FORMS:
            for rule in R.shipped(name, FEATURES).rules:
                out, found = rule.apply(word, FEATURES)
                after, again = rule.rewrite(word, FEATURES)
                assert tuple(out) == after.units
                assert found == again
                checked += 1
        assert checked > 500, "sweep did not run"

    def test_apply_answers_where_rewrite_refuses(self) -> None:
        """The units were never in doubt. A caller who is not carrying the
        span that has no image is not blocked by it."""
        held = _form("a..b", (("mora", 0, 2),))
        rule = R.parse(". -> #", FEATURES)
        with pytest.raises(RebaseError):
            rule.rewrite(held, FEATURES)
        out, found = rule.apply(held, FEATURES)
        assert found and "".join(u.text for u in out) == "a#b"


class TestACascadeCarriesATier:
    """Piece 3 pinned that ``RuleSet.derive`` took a string, so a cascade
    carried no tier at all. It takes a form now, and the replacement is
    stronger than the pin: what is asserted is that a tier-conditioned rule
    fires *after* a length-changing one, which is the wrong answer the pin
    was standing in front of."""

    RULES = "p -> ∅ / # _\nt -> tʰ / <syllable _"

    def test_a_tier_rule_fires_after_a_length_changing_rule(self) -> None:
        derived = R.RuleSet.parse(self.RULES, FEATURES).derive(_liaison(), FEATURES)
        assert derived.result == "ətʰitʰ‿ami"
        assert _spans(Form.of(units(derived.result, FEATURES), derived.intervals)) == (
            (0, 1),
            (1, 3),
            (3, 6),
            (6, 8),
        )

    def test_and_with_the_spans_left_stale_it_fires_somewhere_else(self) -> None:
        """The control, and it is what the silence would have looked like.
        Run the first rule, keep the spans it was handed, and the tier rule
        aspirates a different set of positions."""
        held = _liaison()
        after, _ = R.parse("p -> ∅ / # _", FEATURES).apply(held, FEATURES)
        stale = Form.of(after, [s for s in held.intervals if s.end <= len(after)])
        moved, _ = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES).rewrite(
            stale, FEATURES
        )
        assert moved.to_ipa() != "ətʰitʰ‿ami"

    def test_a_cascade_over_a_string_still_carries_no_tier(self) -> None:
        """Nothing is derived from the dots. The spans come from the caller
        or there are none, which is ``docs/form.md``'s policy read from the
        cascade."""
        derived = R.RuleSet.parse(self.RULES, FEATURES).derive("pə.tit‿ami", FEATURES)
        assert derived.intervals == ()
        assert "tʰ" not in derived.result

    def test_the_intervals_index_the_units_of_the_result(self) -> None:
        checked = 0
        for name, word in CORPUS_FORMS[:80]:
            read = Form.parse(word, FEATURES)
            if len(read.units) < 3:
                continue
            held = Form.of(read.units, [Interval("syllable", 0, 2, FEATURES)])
            derived = R.shipped(name, FEATURES).derive(held, FEATURES)
            # Form refuses a span past its end, so this is the assertion.
            Form.of(units(derived.result, FEATURES), derived.intervals)
            checked += 1
        assert checked > 50, "sweep did not run"

    def test_the_shipped_sets_derive_the_same_string_either_way(self) -> None:
        """A form carrying a tier must not change what the segmental rules
        do. No shipped rule names a tier, so the spelling is the spelling."""
        checked = 0
        for name, word in CORPUS_FORMS:
            rules = R.shipped(name, FEATURES)
            read = Form.parse(word, FEATURES)
            plain = rules.apply(word, FEATURES)
            held = Form.of(
                read.units, [Interval("morph", 0, len(read.units), FEATURES)]
            )
            assert rules.apply(held, FEATURES) == plain
            checked += 1
        assert checked > 500, "sweep did not run"


class TestVariantsRefusesATierRatherThanDroppingOne:
    """Scoped out on purpose, and pinned so the limit stays known. A
    variant is keyed by its spelling, and two branches spelling alike with
    different spans are two structures and one key."""

    OPTIONAL = "t ~> ʔ / _ #"

    def test_a_form_carrying_an_interval_is_refused(self) -> None:
        with pytest.raises(R.RuleError) as caught:
            R.RuleSet.parse(self.OPTIONAL, FEATURES).variants(_liaison(), FEATURES)
        assert "derive()" in str(caught.value)

    def test_but_the_same_form_without_one_is_accepted(self) -> None:
        held = Form.parse(LIAISON, FEATURES)
        got = R.RuleSet.parse(self.OPTIONAL, FEATURES).variants(held, FEATURES)
        assert [v.form for v in got] == [LIAISON, "pətiʔ‿ami"]


class TestTheTierNamesStayDeclared:
    """``rebase`` constructs intervals, and constructing one re-checks the
    tier against a declared vocabulary. It has to be the *caller's*
    vocabulary, or a language declaring a fourth tier would have its spans
    refused by the arithmetic that is supposed to move them."""

    TIER = "gesture"

    @pytest.fixture
    def extended(self, tmp_path) -> IPAFeatures:  # type: ignore[no-untyped-def]
        source = FEATURES.xml_path.read_text(encoding="utf-8")
        anchor = '<value name="morph" short="mph" href="Morpheme"/>'
        assert source.count(anchor) == 1
        path = tmp_path / "ipa.xml"
        path.write_text(
            source.replace(
                anchor, f'{anchor}\n      <value name="{self.TIER}" short="gst"/>'
            ),
            encoding="utf-8",
        )
        return IPAFeatures(xml_path=path)

    def test_a_span_on_a_fourth_declared_tier_rebases(
        self, extended: IPAFeatures
    ) -> None:
        span = Interval(self.TIER, 3, 5, extended)
        moved = R.rebase([span], [_edit(0, 1, "")], extended)
        assert (moved[0].tier, moved[0].start, moved[0].end) == (self.TIER, 2, 4)

    def test_and_the_control_is_that_the_shipped_inventory_refuses_it(self) -> None:
        """So the test above is not passing on a name everything accepts."""
        assert self.TIER not in ipakit.tier_names(FEATURES)
        with pytest.raises(ValueError, match="not a declared tier"):
            Interval(self.TIER, 3, 5, FEATURES)

    def test_a_cascade_carries_a_fourth_tier_too(self, extended: IPAFeatures) -> None:
        read = Form.parse("apata", extended)
        held = Form.of(read.units, [Interval(self.TIER, 3, 5, extended)])
        derived = R.RuleSet.parse(
            f"a -> ∅ / # _\nt -> d / {TIER_OPEN}{self.TIER} _", extended
        ).derive(held, extended)
        assert derived.result == "pada"
        assert [(s.tier, s.start, s.end) for s in derived.intervals] == [
            (self.TIER, 2, 4)
        ]
