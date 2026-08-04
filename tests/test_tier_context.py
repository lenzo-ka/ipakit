"""A rule may **read** a tier in its context, and may not rewrite one.

Piece 3 of the tier increment. ``tests/test_tiers.py`` tests the declared
vocabulary and ``tests/test_intervals.py`` the span on a ``Form``; this
file tests the notation that names one from a rule, and the restriction
that keeps it out of what a rule rewrites.

Three properties get more than a named case each, because each is the
shape of a mistake rather than a single value:

* **Read-only by construction.** A tier term in a rule's center is
  refused at parse time. Swept over *every declared tier* and both
  spellings of the term, and every refusal is paired with a **control**
  that parses the same rule with the term moved into the context -- a
  refusal that would also fire on a well-formed rule is not evidence of
  anything. The vocabulary size is asserted, so an empty ``tier``
  declaration cannot make the sweep vacuous.
* **Declared, not hardcoded.** The gate is
  ``tests/test_declared_not_hardcoded.py``; what is added here is the
  stronger statement it cannot make: an inventory declaring a *fourth*
  tier gets the notation for it with no edit to ``rules.py``, measured by
  declaring one and parsing a rule that names it.
* **A position is not a unit.** A tier term consumes nothing and claims
  the gap the cursor sits at. That is what lets a rule say "a ``t`` that
  begins a syllable" while the center stays closed to tier terms, and it
  is what keeps a tier edge a different claim from a boundary glyph.

The case the notation is *for* is enchaînement, which is why the fixtures
below are French: in ``pə.ti.t‿a.mi`` the syllable ``t‿a`` starts inside
a word and no glyph delimits it, so no boundary pattern can name the
position and ``<syllable`` can.
"""

from __future__ import annotations

import ast
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit import rules as R
from ipakit.form import Form, Interval, tier_names
from ipakit.rules import TIER_CLOSE, TIER_OPEN, Pattern, RuleError

FEATURES = ipakit.load_ipa_features()

_RULES_PY = Path(ipakit.rules.__file__)

#: ``pə.ti.t‿a.mi`` as units, and its four syllables as spans. The third
#: is the one the tree cannot state (tests/test_intervals.py measures
#: that): it starts at the ``t`` of *petite* and runs across the linking
#: mark into *amie*.
LIAISON = "pətit‿ami"
SYLLABLES = ((0, 2), (2, 4), (4, 7), (7, 9))


def _liaison(features: IPAFeatures = FEATURES) -> Form:
    form = Form.parse(LIAISON, features)
    spans = [Interval("syllable", a, b, features) for a, b in SYLLABLES]
    return Form.of(form.units, spans)


def _terms(tier: str) -> tuple[str, str]:
    """Both spellings of a term on one tier, opening and closing."""
    return f"{TIER_OPEN}{tier}", f"{tier}{TIER_CLOSE}"


class TestTheVocabularyIsWideEnoughToSweep:
    """Every sweep below loops over the declared tiers. If that vocabulary
    were empty or one member long, the loops would pass while testing
    nothing, which is the failure ``docs/reviewing.md`` names first."""

    def test_there_are_several_declared_tiers(self) -> None:
        assert len(tier_names(FEATURES)) >= 3, tier_names(FEATURES)

    def test_and_the_terms_they_spell_are_all_distinct(self) -> None:
        spelled = [t for tier in tier_names(FEATURES) for t in _terms(tier)]
        assert len(set(spelled)) == len(spelled) == 2 * len(tier_names(FEATURES))


class TestATierTermIsRefusedInTheCenter:
    """The read-only restriction, by construction and at parse time.

    Kaplan & Kay's restriction is on a rule's **center** and not on its
    contexts (docs/calculus.md), and what leaves the finite-state
    tradition is rewriting a tier rather than reading one
    (docs/design/tiers.md §2). So the center is closed to a tier term and
    the context is open to it, and both halves are asserted here.
    """

    @pytest.mark.parametrize("tier", tier_names(FEATURES))
    def test_a_tier_term_may_not_be_the_target(self, tier: str) -> None:
        for term in _terms(tier):
            with pytest.raises(RuleError, match="may READ a tier"):
                R.parse(f"{term} -> d", FEATURES)

    @pytest.mark.parametrize("tier", tier_names(FEATURES))
    def test_a_tier_term_may_not_be_the_right_hand_side(self, tier: str) -> None:
        for term in _terms(tier):
            with pytest.raises(RuleError, match="may READ a tier"):
                R.parse(f"t -> {term}", FEATURES)

    @pytest.mark.parametrize("tier", tier_names(FEATURES))
    def test_but_the_same_rule_parses_with_the_term_in_the_context(
        self, tier: str
    ) -> None:
        """The control. Without it the refusals above are consistent with a
        parser that refuses every rule mentioning the term at all."""
        for term in _terms(tier):
            left = R.parse(f"t -> d / {term} _", FEATURES)
            right = R.parse(f"t -> d / _ {term}", FEATURES)
            assert [p.tier for p in left.query.left] == [tier]
            assert [p.tier for p in right.query.right] == [tier]
            assert left.query.target is not None
            assert left.query.target.tier is None

    def test_the_refusal_names_what_it_saw(self) -> None:
        with pytest.raises(RuleError) as caught:
            R.parse(f"{TIER_OPEN}mora -> d", FEATURES)
        assert "'mora'" in str(caught.value)
        assert f"{TIER_OPEN}mora _" in str(caught.value), "no repair is offered"


class TestAStructuralFeatureCannotBeWritten:
    """The leak this piece found, and it was live.

    The query side already refuses a structural term -- a bundle cannot
    carry one, so the term is satisfied by its absence and true of every
    segment. The **change** side did not: ``t -> [tier=mora]`` parsed,
    wrote ``tier`` into a bundle no unit has, fired at every ``t``, and
    changed nothing. A well-formed statement with no effect and no
    complaint is the shape of every defect this library has had.
    """

    @pytest.mark.parametrize("name", sorted(FEATURES.features_by_mode["structural"]))
    def test_no_structural_feature_may_be_rewritten(self, name: str) -> None:
        value = FEATURES.features[name].values[0]
        with pytest.raises(RuleError, match="structural"):
            R.parse(f"t -> [{name}={value}]", FEATURES)

    @pytest.mark.parametrize("name", sorted(FEATURES.features_by_mode["structural"]))
    def test_and_it_was_already_refused_on_the_query_side(self, name: str) -> None:
        """The two sides say the same thing now. Only one of them did."""
        value = FEATURES.features[name].values[0]
        with pytest.raises(RuleError, match="structural"):
            R.parse(f"t -> d / [{name}={value}] _", FEATURES)

    def test_the_control_is_that_a_writable_feature_still_writes(self) -> None:
        """A non-structural change must be unaffected, or the refusal above
        is a parser that has stopped accepting bracketed changes."""
        assert ipakit.rewrite("kæt", "t -> [voiced=+]") == "kæd"
        assert R.parse("t -> [stress=primary]", FEATURES).becomes == {
            "stress": "primary"
        }


class TestNothingOrdersTwoTiers:
    """``tier`` is nominal. No spelling here may imply containment."""

    def test_two_tier_terms_at_one_position_are_a_conjunction(self) -> None:
        form = Form.parse("ata", FEATURES)
        spans = [
            Interval("syllable", 1, 3, FEATURES),
            Interval("mora", 0, 1, FEATURES),
        ]
        held = Form.of(form.units, spans)
        rule = R.parse(f"t -> d / mora{TIER_CLOSE} {TIER_OPEN}syllable _", FEATURES)
        assert R.spell(rule.apply(held, FEATURES)[0]) == "ada"

    def test_and_the_order_they_are_written_in_does_not_matter(self) -> None:
        """Two claims about one position. If one contained the other, the
        order would have to mean something, and it must not."""
        form = Form.parse("ata", FEATURES)
        spans = [
            Interval("syllable", 1, 3, FEATURES),
            Interval("mora", 0, 1, FEATURES),
        ]
        held = Form.of(form.units, spans)
        one = R.parse(f"t -> d / mora{TIER_CLOSE} {TIER_OPEN}syllable _", FEATURES)
        other = R.parse(f"t -> d / {TIER_OPEN}syllable mora{TIER_CLOSE} _", FEATURES)
        assert one.recognize(held, FEATURES) == other.recognize(held, FEATURES)
        assert one.recognize(held, FEATURES) != []

    def test_a_term_on_one_tier_does_not_answer_for_another(self) -> None:
        form = Form.parse("ata", FEATURES)
        held = Form.of(form.units, [Interval("mora", 1, 3, FEATURES)])
        assert (
            R.parse(f"t -> d / mora{TIER_CLOSE} _", FEATURES).recognize(held, FEATURES)
            == []
        )
        assert (
            R.parse(f"t -> d / {TIER_OPEN}mora _", FEATURES).recognize(held, FEATURES)
            != []
        )
        assert (
            R.parse(f"t -> d / {TIER_OPEN}syllable _", FEATURES).recognize(
                held, FEATURES
            )
            == []
        )


class TestATierTermClaimsAPositionAndNotAUnit:
    """The choice that makes read-only livable, asserted as behavior.

    A per-unit tier term could only ever describe a *neighbor*, because
    the center is closed to it -- so "aspirate a ``t`` that begins a
    syllable" would be unwritable. A position term states exactly that,
    and it is a context term because a position is where the target sits.
    """

    def test_matching_a_tier_term_against_a_unit_is_refused(self) -> None:
        """Not answered False. A pattern that quietly answered False would
        make every tier term a rule that never fires."""
        pattern = R._pattern(f"{TIER_OPEN}mora", FEATURES)
        with pytest.raises(RuleError, match="position"):
            pattern.matches(Form.parse("a", FEATURES).units[0], FEATURES)

    def test_and_a_non_tier_pattern_has_no_position_to_hold_at(self) -> None:
        """The pin in the other direction, so neither read can drift into
        answering for the other."""
        with pytest.raises(RuleError, match="not a tier term"):
            R._pattern("[vowel]", FEATURES).holds_at(0, ())

    def test_it_consumes_no_unit_so_the_target_keeps_its_neighbor(self) -> None:
        """``<syllable [vowel] _`` is a vowel before the target *and* an
        interval starting at the target, not two units."""
        form = Form.parse("ata", FEATURES)
        held = Form.of(form.units, [Interval("syllable", 1, 3, FEATURES)])
        rule = R.parse(f"t -> d / [vowel] {TIER_OPEN}syllable _", FEATURES)
        assert R.spell(rule.apply(held, FEATURES)[0]) == "ada"

    def test_the_site_records_no_unit_for_it(self) -> None:
        """One entry per context item, ``None`` where nothing licensed it --
        the same record the virtual edge and an absent optional item make."""
        held = _liaison()
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        sites = rule.recognize(held, FEATURES)
        assert sites and all(site.left == (None,) for site in sites)

    def test_holds_at_reads_the_half_open_span(self) -> None:
        spans = (Interval("mora", 2, 5, FEATURES),)
        opens = R._pattern(f"{TIER_OPEN}mora", FEATURES)
        closes = R._pattern(f"mora{TIER_CLOSE}", FEATURES)
        assert [g for g in range(7) if opens.holds_at(g, spans)] == [2]
        assert [g for g in range(7) if closes.holds_at(g, spans)] == [5]


class TestATierEdgeIsADifferentClaimFromABoundaryGlyph:
    """The asymmetry piece 2 exists for, from the rule side.

    ``docs/form.md`` records that ``tree()`` cannot state enchaînement,
    because a syllable crossing ``‿`` is a subtree of neither word. The
    same failure reaches the rule engine: no boundary pattern can name the
    position where that syllable starts, because no glyph is written
    there.
    """

    def test_a_syllable_may_start_where_no_glyph_is_written(self) -> None:
        held = _liaison()
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        # Units 2 and 4 are the two /t/s; unit 4 opens 't‿a'.
        assert [s.start for s in rule.recognize(held, FEATURES)] == [2, 4]
        assert R.spell(rule.apply(held, FEATURES)[0]) == "pətʰitʰ‿ami"

    def test_and_the_boundary_notation_cannot_reach_that_position(self) -> None:
        """The measurement that says the tier term buys something. Every
        boundary spelling is tried, including the wildcard."""
        held = _liaison()
        spellings = [".", "#", R.ANY_BOUNDARY, "‿"]
        for glyph in spellings:
            rule = R.parse(f"t -> tʰ / {glyph} _", FEATURES)
            assert 4 not in [s.start for s in rule.recognize(held, FEATURES)], glyph

    def test_a_glyph_does_not_assert_an_interval_either(self) -> None:
        """The other direction: a dot is a boundary and not a span, so a
        dotted form with no intervals holds no tier term."""
        dotted = Form.parse("pə.ti.t‿a.mi", FEATURES)
        assert dotted.intervals == ()
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        assert rule.recognize(dotted, FEATURES) == []
        assert R.parse("t -> tʰ / . _", FEATURES).recognize(dotted, FEATURES) != []


class TestAnUnspecifiedTierIsNotInvented:
    """``docs/form.md``'s policy, read from the rule side.

    A form that asserts no interval is not given one, so a rule
    conditioned on a tier does not fire there -- the same answer a
    margin-conditioned rule already gives on an undotted word.
    """

    def test_a_tier_rule_finds_nothing_on_a_bare_string(self) -> None:
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        assert rule.recognize(LIAISON, FEATURES) == []
        assert R.spell(rule.apply(LIAISON, FEATURES)[0]) == LIAISON

    def test_nor_on_a_unit_sequence(self) -> None:
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        assert rule.recognize(list(R.units(LIAISON, FEATURES)), FEATURES) == []

    def test_but_the_control_is_that_the_same_rule_fires_on_a_form(self) -> None:
        rule = R.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        assert rule.recognize(_liaison(), FEATURES) != []


class TestARuleNamingNoTierIsUnchanged:
    """The signature grew a third accepted form. Nothing else may move."""

    def test_every_shipped_rule_answers_alike_however_the_form_arrives(self) -> None:
        held = _liaison()
        bare = list(held.units)
        checked = 0
        for name in R.available():
            for rule in R.shipped(name, FEATURES).rules:
                assert rule.recognize(bare, FEATURES) == rule.recognize(held, FEATURES)
                assert rule.edits(bare, FEATURES) == rule.edits(held, FEATURES)
                checked += 1
        assert checked > 80, f"sweep did not run: {checked}"

    def test_no_shipped_rule_names_a_tier(self) -> None:
        """The premise of the 0-derivations measurement, kept where it can
        fail rather than only in a commit message."""
        named = [
            (name, rule.source)
            for name in R.available()
            for rule in R.shipped(name, FEATURES).rules
            for pattern in (rule.query.target, *rule.query.left, *rule.query.right)
            if pattern is not None and pattern.names_tier
        ]
        assert named == []

    def test_the_common_call_site_is_still_one_argument(self) -> None:
        assert ipakit.rewrite("kæt", "t -> ʔ / _ #") == "kæʔ"


class TestWhatARuleCarriesOut:
    """Both of these were pinned as *limits* while rebasing did not exist.
    Rebasing exists (``tests/test_tier_rebase.py``), so what they pin now
    is the shape rather than the absence, and this file is not left
    asserting a limit that has been lifted."""

    def test_apply_returns_units_and_rewrite_returns_a_form(self) -> None:
        """A unit sequence carries no tier, so asking for units is asking
        for the units. ``rewrite`` is the same operation answering with a
        form, spans rebased onto it."""
        held = _liaison()
        rule = R.parse("t -> ∅ / _ i", FEATURES)
        out, edits = rule.apply(held, FEATURES)
        assert isinstance(out, list) and all(isinstance(u, R.Unit) for u in out)
        assert edits and len(out) < len(held.units)
        after, again = rule.rewrite(held, FEATURES)
        assert tuple(out) == after.units and edits == again and after.intervals

    def test_a_cascade_carries_a_tier_and_a_string_still_carries_none(self) -> None:
        """``RuleSet.derive`` takes a form now, so a tier-conditioned rule
        fires at step ten as it does at step one. A string still carries no
        tier, because nothing derives one from the dots."""
        rules = R.RuleSet.parse(f"t -> tʰ / {TIER_OPEN}syllable _", FEATURES)
        assert rules.apply(LIAISON, FEATURES) == LIAISON
        assert rules.apply(_liaison(), FEATURES) == "pətʰitʰ‿ami"


class TestTheNotationRefusesWhatItDoesNotOffer:
    def test_an_undeclared_tier_is_refused_and_the_message_declares(self) -> None:
        with pytest.raises(RuleError) as caught:
            R.parse(f"t -> d / {TIER_OPEN}gesture _", FEATURES)
        assert "'gesture'" in str(caught.value)
        for tier in tier_names(FEATURES):
            assert tier in str(caught.value)

    def test_membership_is_refused_rather_than_read_as_an_edge(self) -> None:
        """The pinned limit. ``<mora>`` could be made to mean "inside a
        mora" later; it must not silently mean one of the two edges now."""
        with pytest.raises(RuleError, match="membership"):
            R.parse(f"t -> d / {TIER_OPEN}mora{TIER_CLOSE} _", FEATURES)

    def test_a_tier_term_may_not_be_marked_optional(self) -> None:
        """``(∅)`` is for a declared zero, and a position is not a zero."""
        with pytest.raises(RuleError, match="only a declared zero"):
            R.parse(f"t -> d / ({TIER_OPEN}mora) _", FEATURES)

    def test_a_bare_angle_bracket_is_still_an_unregistered_symbol(self) -> None:
        for text in (TIER_OPEN, TIER_CLOSE):
            with pytest.raises(RuleError):
                R.parse(f"t -> d / {text} _", FEATURES)


class TestTheTierNamesAreDeclaredAndNotWrittenInPython:
    """``tests/test_declared_not_hardcoded.py`` is the gate. This is the
    statement it cannot make: a *fourth* declared tier works with no edit
    to ``rules.py``."""

    TIER = "gesture"

    @pytest.fixture
    def extended(self, tmp_path) -> IPAFeatures:
        source = FEATURES.xml_path.read_text(encoding="utf-8")
        anchor = '<value name="morph" short="mph" href="Morpheme"/>'
        assert source.count(anchor) == 1
        patched = source.replace(
            anchor, f'{anchor}\n      <value name="{self.TIER}" short="gst"/>'
        )
        path = tmp_path / "ipa.xml"
        path.write_text(patched, encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_the_new_tier_joins_the_vocabulary(self, extended: IPAFeatures) -> None:
        assert self.TIER in tier_names(extended)
        assert self.TIER not in tier_names(FEATURES)

    def test_and_a_rule_can_name_it_with_no_code_change(
        self, extended: IPAFeatures
    ) -> None:
        for term in _terms(self.TIER):
            rule = R.parse(f"t -> d / {term} _", extended)
            assert [p.tier for p in rule.query.left] == [self.TIER]

    def test_and_it_fires(self, extended: IPAFeatures) -> None:
        form = Form.parse("ata", extended)
        held = Form.of(form.units, [Interval(self.TIER, 1, 3, extended)])
        rule = R.parse(f"t -> d / {TIER_OPEN}{self.TIER} _", extended)
        assert R.spell(rule.apply(held, extended)[0]) == "ada"

    def test_and_it_is_refused_in_the_center_like_every_other(
        self, extended: IPAFeatures
    ) -> None:
        with pytest.raises(RuleError, match="may READ a tier"):
            R.parse(f"{TIER_OPEN}{self.TIER} -> d", extended)

    def test_no_declared_tier_name_is_a_string_literal_in_the_rule_engine(
        self,
    ) -> None:
        """The predicate, over the source rather than over today's names: a
        tier name pasted into ``rules.py`` is the mistake, whichever one it
        is. ``docs/design/tiers.md`` records the precedent -- ``'#'`` was
        pasted as ``word`` once, and a newly declared separator had notation
        nothing would parse."""
        tree = ast.parse(_RULES_PY.read_text(encoding="utf-8"))
        declared = set(tier_names(FEATURES))
        found = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in declared
        ]
        assert found == [], found

    def test_and_the_guard_can_see_one(self) -> None:
        """A guard that has quietly stopped covering a shape is worse than
        none, so it is fed a source that does carry the shape."""
        tier = sorted(tier_names(FEATURES))[0]
        tree = ast.parse(f"def f():\n    return {tier!r}\n")
        found = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and node.value in set(tier_names(FEATURES))
        ]
        assert found == [tier]


class TestNothingNamedTierAnswersWithALevel:
    """The collision this increment had to resolve, held by construction.

    ``edge_tier()`` returned a value of the ordinal ``level`` feature and
    ``tiers()`` returned the whole ``level`` ladder, both named for the
    other declared feature. They are ``edge_level()`` and ``levels()``
    now, and this is the predicate rather than the two spot checks: a
    public read named for one declared feature must answer with a value
    of that feature.
    """

    def test_every_level_named_read_answers_with_a_declared_level(self) -> None:
        declared = set(FEATURES.features["level"].values)
        assert set(ipakit.levels(FEATURES)) <= declared
        assert R.units("a b", FEATURES)[1].level in declared

    def test_every_tier_named_read_answers_with_a_declared_tier(self) -> None:
        declared = set(FEATURES.features["tier"].values)
        assert set(tier_names(FEATURES)) == declared
        assert not declared & set(FEATURES.features["level"].values) - {"syllable"}

    def test_and_the_two_vocabularies_are_not_the_same_vocabulary(self) -> None:
        """``syllable`` is in both and means two different things: how
        strong a boundary is, and which tier a span sits on. That overlap
        is why a function may not be named for one and answer with the
        other."""
        assert set(tier_names(FEATURES)) != set(FEATURES.features["level"].values)
        assert "syllable" in set(tier_names(FEATURES)) & set(
            FEATURES.features["level"].values
        )

    def test_no_public_form_read_is_named_for_the_wrong_feature(self) -> None:
        exported = {name for name in ipakit.__all__ if not name[0].isupper()}
        assert "levels" in exported and "tier_names" in exported
        assert "tiers" not in exported and "edge_tier" not in dir(ipakit.form)


class TestPatternRepr:
    def test_a_tier_pattern_prints_the_notation_it_was_written_as(self) -> None:
        assert str(R._pattern(f"{TIER_OPEN}mora", FEATURES)) == f"{TIER_OPEN}mora"
        assert str(R._pattern(f"mora{TIER_CLOSE}", FEATURES)) == f"mora{TIER_CLOSE}"

    def test_a_tier_pattern_is_not_a_boundary_pattern(self) -> None:
        """``names_boundary`` and ``names_tier`` are different questions,
        and the boundary-run rule reads the first."""
        pattern: Pattern = R._pattern(f"{TIER_OPEN}mora", FEATURES)
        assert pattern.names_tier and not pattern.names_boundary
        assert R._pattern("#", FEATURES).names_boundary
        assert not R._pattern("#", FEATURES).names_tier
