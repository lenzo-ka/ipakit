"""What a Form must satisfy: carry everything, drop only when asked.

Two failures would be silent, so both are swept rather than sampled:

* a projection that drops something it did not name -- the reason
  ``segments()`` alone was not enough; and
* a tier invented where the transcription asserted none. With the dot
  optional, a word written without one has *unspecified* syllabification,
  and a tree that answers "one syllable" has made a claim nobody wrote.

Two claims the tree makes about itself are tested rather than assumed,
because both would fail quietly. That a node's brackets *are* its span
endpoints is swept over the inventory, since provenance is only worth
having if it names positions that were already there. And that declaring
a further ``level`` extends the tree with no code change is tested against
an inventory built with one more level in it, which is the only way to
find out -- the promise held for a value below ``word`` and would have
broken for one above it.
"""

from __future__ import annotations

import ipakit
import ipakit.rules as R
import pytest
from ipakit.features import IPAFeatures
from ipakit.form import (
    Attribute,
    Form,
    Node,
    boundary_marks,
    edge_tier,
    spell,
    tiers,
    units,
)

from tests.corpus import assert_swept, self_spelling_phones

FEATURES = ipakit.load_ipa_features()


def _phones() -> list[str]:
    """The shared enumeration; see tests/corpus.py for why it is shared."""
    return self_spelling_phones()


class TestAFormCarriesEverythingItWasWrittenWith:
    def test_it_round_trips_every_phone(self):
        phones = _phones()
        assert_swept(len(phones), phones)
        bad = [p for p in phones if Form.parse(p, FEATURES).to_ipa() != p]
        assert bad == [], f"{len(bad)} lost their spelling: {bad[:5]}"

    @pytest.mark.parametrize("shape", ["#{0}#", "{0}.{0}", "{0} {0}", "#{0}.{0}#"])
    def test_it_round_trips_with_boundaries(self, shape):
        checked = 0
        for phone in _phones():
            form = shape.format(phone)
            assert Form.parse(form, FEATURES).to_ipa() == form, form
            checked += 1
        assert_swept(checked, _phones())

    def test_segments_is_the_projection_that_loses_them(self):
        """Pins why this exists, so the reason cannot go stale."""
        text = "#kæt.dɒɡ#"
        assert ipakit.to_ipa(ipakit.segments(text)) != text
        assert Form.parse(text, FEATURES).to_ipa() == text


class TestEachProjectionDropsExactlyWhatItNames:
    FORM = "#kˌæn.tˈiːn dɒɡ#"

    def test_to_ipa_drops_nothing(self):
        assert Form.parse(self.FORM, FEATURES).to_ipa() == self.FORM

    def test_segments_drops_boundaries_and_keeps_attributes(self):
        form = Form.parse(self.FORM, FEATURES)
        assert [s.to_ipa() for s in form.segments] == list("k") + [
            "ˌæ",
            "n",
            "t",
            "ˈiː",
            "n",
            "d",
            "ɒ",
            "ɡ",
        ]
        assert any(s.prosody for s in form.segments), "attributes were dropped too"

    def test_phones_drops_attributes_as_well(self):
        form = Form.parse(self.FORM, FEATURES)
        assert form.phones == ("k", "æ", "n", "t", "i", "n", "d", "ɒ", "ɡ")

    def test_identity_is_the_same_phone_under_any_attribute(self):
        for text in ("a", "ˈa", "aː", "ˈaː"):
            assert Form.parse(text, FEATURES).phones == ("a",)

    def test_without_boundaries_says_so_at_the_call_site(self):
        form = Form.parse(self.FORM, FEATURES)
        assert form.without_boundaries().boundaries == ()
        assert len(form.without_boundaries().segments) == len(form.segments)


class TestWhatIsDroppedIsStillRecorded:
    def test_boundaries_record_where_they_sat(self):
        form = Form.parse("#kæt.dɒɡ#", FEATURES)
        # Compared whole, not by a few fields: Boundary now carries
        # everything the separator declared so rebuild reproduces the unit.
        assert [(b.text, b.level, b.at) for b in form.boundaries] == [
            ("#", "word", 0),
            (".", "syllable", 3),
            ("#", "word", 6),
        ]
        assert all(b.features.get("level") == b.level for b in form.boundaries)
        assert form.boundaries[0].features.get("class") == "separator"

    def test_attributes_record_which_glyph_declared_them(self):
        """'ˈiː' carries a stress from 'ˈ' and a length from 'ː'."""
        got = Form.parse("tˈiːn", FEATURES).attributes
        assert Attribute("stress", "primary", 1, "ˈ") in got
        assert Attribute("length", "long", 1, "ː") in got

    def test_rebuild_is_the_inverse_of_taking_it_apart(self):
        checked = 0
        for phone in _phones():
            text = f"#{phone}.{phone}#"
            form = Form.parse(text, FEATURES)
            back = Form.rebuild(form.segments, form.boundaries, FEATURES)
            assert back.to_ipa() == text, text
            checked += 1
        assert_swept(checked, _phones())

    def test_a_collapsed_form_can_be_put_back(self):
        form = Form.parse("kˌæn.tˈiːn", FEATURES)
        flat = form.without_boundaries()
        assert flat.to_ipa() == "kˌæntˈiːn"
        assert Form.rebuild(flat.segments, form.boundaries, FEATURES).to_ipa() == (
            "kˌæn.tˈiːn"
        )

    def test_rebuild_reproduces_the_boundary_unit_not_just_its_spelling(self):
        """The spelling round-tripped while the description did not.

        Rebuilding a boundary from ``Boundary.level`` alone put ``|`` back
        with a bare level and no ``break=minor``, and ``‿`` -- which
        declared no level then, so ``level`` fell back to ``word`` -- back
        as a plain *word boundary* with its ``linking=+`` gone. Every
        declared separating mark, not just the one that broke.
        """
        checked = 0
        marks = [".", "#", " ", *boundary_marks(FEATURES)]
        for glyph in marks:
            text = f"a{glyph}b"
            form = Form.parse(text, FEATURES)
            back = Form.rebuild(form.segments, form.boundaries, FEATURES)
            assert back.to_ipa() == text, text
            assert [(u.text, u.features) for u in back.units] == [
                (u.text, u.features) for u in form.units
            ], text
            checked += 1
        assert checked == 6, f"{checked} marks swept, not 6"

    def test_every_boundary_reports_the_level_it_declares(self):
        """``Boundary.level`` and the declaration agree, on every mark.

        They disagreed while ``|``, ``‖`` and ``‿`` declared no level:
        ``Form.boundaries`` reported ``word`` for all three from the
        fallback, while ``Unit.level`` reported ``None``, so one form gave
        two answers about the same position.
        """
        checked = 0
        for glyph in (".", "#", " ", *boundary_marks(FEATURES)):
            (boundary,) = Form.parse(f"a{glyph}b", FEATURES).boundaries
            unit = Form.parse(f"a{glyph}b", FEATURES).units[1]
            assert boundary.level == unit.level, glyph
            if glyph != " ":
                assert boundary.level == boundary.features["level"], glyph
            checked += 1
        assert checked == 6, f"{checked} marks swept, not 6"


class TestTheTreeIsGeneratedFromTheDeclarations:
    def test_tiers_come_from_the_level_feature(self):
        """Outermost first, read off ipa.xml rather than stated in code."""
        assert tiers(FEATURES) == tuple(reversed(FEATURES.features["level"].values))
        assert tiers(FEATURES) == ("utterance", "phrase", "word", "syllable")

    def test_a_separator_declares_which_tier_it_terminates(self):
        for glyph, level in ((".", "syllable"), ("#", "word")):
            assert FEATURES.separators[glyph].features["level"] == level

    def test_a_break_mark_declares_its_tier_too(self):
        """The glyph-to-tier map is in ipa.xml, not in Python."""
        for glyph, level in (("|", "phrase"), ("‖", "utterance")):
            assert FEATURES.diacritics[glyph].features["level"] == level
            assert boundary_marks(FEATURES)[glyph]["level"] == level

    def test_the_level_feature_is_declared_structural(self):
        """A boundary level belongs to no segment's feature bag.

        It fell to the additive default while only separators declared a
        level. Once a diacritic declares one, additive would offer a mark
        that adds an ordinal ``level`` to a base, and an ordinal in a
        phone's bundle is a term in the metric.
        """
        assert FEATURES.features["level"].mode == "structural"
        carriers = [
            unit
            for unit in self_spelling_phones()
            for key in FEATURES.get_features(unit)
            if key == "level"
        ]
        assert carriers == [], f"{len(carriers)} phones carry a level"

    def test_the_edge_tier_is_the_strongest_a_separator_spells(self):
        """Not "the outermost tier": there are now tiers above ``word``."""
        assert edge_tier(FEATURES) == "word"
        assert edge_tier(FEATURES) != tiers(FEATURES)[0]
        strongest = max(
            (
                level
                for sep in FEATURES.separators.values()
                if (level := (sep.features or {}).get("level"))
            ),
            key=FEATURES.features["level"].values.index,
        )
        assert edge_tier(FEATURES) == strongest

    def test_the_tree_nests_by_declared_tier(self):
        tree = Form.parse("#kˌæn.tˈiːn dɒɡ#", FEATURES).tree(FEATURES)
        assert [w.to_ipa() for w in tree.at("word")] == ["kˌæntˈiːn", "dɒɡ"]
        assert [s.to_ipa() for s in tree.at("syllable")] == ["kˌæn", "tˈiːn"]

    def test_every_segment_survives_the_tree(self):
        checked = 0
        for phone in _phones():
            text = f"#{phone}.{phone}#"
            form = Form.parse(text, FEATURES)
            assert form.tree(FEATURES).units == tuple(
                u for u in form.units if not u.is_boundary
            )
            checked += 1
        assert_swept(checked, _phones())


class TestAnUnspecifiedTierIsNotInvented:
    """The dot is optional, so its absence is not a claim of one syllable."""

    def test_a_word_without_dots_has_no_syllable_tier(self):
        tree = Form.parse("kˌæntˈiːn", FEATURES).tree(FEATURES)
        assert tree.at("syllable") == ()
        (word,) = tree.at("word")
        assert [n.level for n in word.children] == ["segment"] * 6

    def test_a_word_with_dots_has_one(self):
        tree = Form.parse("kˌæn.tˈiːn", FEATURES).tree(FEATURES)
        assert [s.to_ipa() for s in tree.at("syllable")] == ["kˌæn", "tˈiːn"]

    def test_specification_is_per_node_not_per_form(self):
        """One word may state its syllables while another does not."""
        tree = Form.parse("kæt dɒ.ɡi", FEATURES).tree(FEATURES)
        first, second = tree.at("word")
        assert first.at("syllable") == ()
        assert [s.to_ipa() for s in second.at("syllable")] == ["dɒ", "ɡi"]

    def test_the_outermost_tier_is_delimited_by_the_edges(self):
        """Consistent with '_ #' matching the end of a form in a rule."""
        assert len(Form.parse("kæt", FEATURES).tree(FEATURES).at("word")) == 1
        assert len(Form.parse("kæt dɒɡ", FEATURES).tree(FEATURES).at("word")) == 2

    def test_a_form_with_no_break_mark_has_no_phrase_or_utterance_tier(self):
        """The tiers above ``word`` are not invented either.

        This is what makes :func:`edge_tier` a different question from
        "the outermost tier": a bare word is one word, not one utterance.
        """
        tree = Form.parse("kˌæn.tˈiːn", FEATURES).tree(FEATURES)
        assert tree.at("phrase") == ()
        assert tree.at("utterance") == ()
        assert len(tree.at("word")) == 1

    def test_a_form_edge_asserts_only_the_tier_a_separator_spells(self):
        """Swept, because a floor here would pass on an empty tree."""
        checked = 0
        for phone in _phones():
            tree = Form.parse(phone, FEATURES).tree(FEATURES)
            present = [t for t in tiers(FEATURES) if tree.at(t)]
            assert present == [edge_tier(FEATURES)], (phone, present)
            checked += 1
        assert_swept(checked, _phones())


class TestABreakMarkSplitsTheTierItDeclares:
    """``|`` and ``‖`` used to split nothing: ``'a|b'`` was one word ``ab``."""

    def test_a_minor_break_splits_the_phrase_tier(self):
        tree = Form.parse("a|b", FEATURES).tree(FEATURES)
        assert [n.to_ipa() for n in tree.at("phrase")] == ["a", "b"]
        assert [n.to_ipa() for n in tree.at("word")] == ["a", "b"]

    def test_a_major_break_splits_the_tier_above_it(self):
        tree = Form.parse("a|b‖c", FEATURES).tree(FEATURES)
        assert [n.to_ipa() for n in tree.at("utterance")] == ["ab", "c"]
        # 'c' has no phrase node: no '|' was written inside that
        # utterance, and an unstated tier is not invented.
        assert [n.to_ipa() for n in tree.at("phrase")] == ["a", "b"]
        assert [n.to_ipa() for n in tree.at("word")] == ["a", "b", "c"]

    def test_a_break_does_not_disturb_the_tiers_below_it(self):
        tree = Form.parse("a.b|c.d", FEATURES).tree(FEATURES)
        assert [n.to_ipa() for n in tree.at("syllable")] == ["a", "b", "c", "d"]

    def test_the_linking_mark_divides_words_while_linking_them(self):
        """``‿`` is the absence of a *pause*, not of a boundary.

        ``lez‿ami`` is two words run together, so it declares
        ``level=word`` as ``#`` does and ``linking=+`` for the part that
        differs. With no level it sat on no tier, ``#`` did not reach it,
        and only ``%`` did -- together with the syllable dot, so a
        word-final rule written with ``%`` fired at an interior dot too.
        """
        assert boundary_marks(FEATURES)["‿"] == {"linking": "+", "level": "word"}
        form = Form.parse("lez‿ami", FEATURES)
        assert form.units[3].level == "word"
        assert form.units[3].transparent is False
        tree = form.tree(FEATURES)
        assert [n.to_ipa() for n in tree.at("word")] == ["lez", "ami"]
        assert tree.at("phrase") == () and tree.at("utterance") == ()

    def test_every_declared_boundary_mark_now_states_its_tier(self):
        """The predicate, not the two glyphs that used to fail it.

        ``Boundary.level`` is typed ``str`` and falls back to ``word``
        where a mark declares none. Nothing shipped reaches that fallback
        any more; if a mark is added without a level, this fails and the
        fallback is a silent wrong answer again rather than dead code.
        """
        declared = {
            glyph: bundle.get("level")
            for glyph, bundle in boundary_marks(FEATURES).items()
        }
        declared.update(
            {
                glyph: (sep.features or {}).get("level")
                for glyph, sep in FEATURES.separators.items()
            }
        )
        assert len(declared) == 5, f"{len(declared)} boundary glyphs, not 5"
        missing = [g for g, level in declared.items() if level is None]
        assert missing == [], f"{missing} declare no level"
        assert set(declared.values()) <= set(FEATURES.features["level"].values)

    def test_a_break_mark_still_round_trips(self):
        checked = 0
        for phone in _phones():
            for text in (f"{phone}|{phone}", f"{phone}‖{phone}", f"{phone}‿{phone}"):
                assert Form.parse(text, FEATURES).to_ipa() == text, text
                checked += 1
        assert_swept(checked, _phones())


def _shape(node: Node) -> list:
    """Levels and spellings, with no provenance in it.

    The claim provenance makes is that it adds *no shape*, so the
    comparison has to be of something that cannot see it.
    """
    return [node.level, node.to_ipa(), [_shape(c) for c in node.children]]


def _check_spans(node: Node, start: int) -> int:
    """Assert every bracket sits at the span endpoint it records, and
    return one past the node's last segment."""
    if node.is_leaf:
        return start + 1
    end = start
    for child in node.children:
        end = _check_spans(child, end)
    if node.opened_by is not None:
        assert node.opened_by.at == start, (node, node.opened_by, start)
    if node.closed_by is not None:
        assert node.closed_by.at == end, (node, node.closed_by, end)
    return end


class TestANodeSaysWhichDelimiterSuppliedEachEnd:
    """``#kæt#`` and ``kæt`` are the same word, written two ways."""

    def test_written_brackets_do_not_change_the_shape(self):
        bare = Form.parse("kæt.dɒɡ", FEATURES).tree(FEATURES)
        bracketed = Form.parse("#kæt.dɒɡ#", FEATURES).tree(FEATURES)
        assert _shape(bare) == _shape(bracketed)

    def test_written_brackets_are_what_asserted_reports(self):
        bare = Form.parse("kæt", FEATURES).tree(FEATURES)
        bracketed = Form.parse("#kæt#", FEATURES).tree(FEATURES)
        (one,) = bare.at("word")
        (two,) = bracketed.at("word")
        assert (one.opened_by, one.closed_by) == (None, None)
        assert one.asserted is False
        assert (two.opened_by.text, two.closed_by.text) == ("#", "#")
        assert two.asserted is True

    def test_one_written_end_is_not_two(self):
        """A space asserts the inner edge of each word and neither outer one."""
        first, second = Form.parse("kæt dɒɡ", FEATURES).tree(FEATURES).at("word")
        assert (first.opened_by, first.closed_by.text) == (None, " ")
        assert (second.opened_by.text, second.closed_by) == (" ", None)
        assert [n.asserted for n in (first, second)] == [False, False]

    def test_an_inner_node_inherits_the_ends_nothing_was_written_between(self):
        """A syllable at the edge of its word is bracketed by the word's mark."""
        (word,) = Form.parse("#kæt.dɒɡ#", FEATURES).tree(FEATURES).at("word")
        first, second = word.at("syllable")
        assert (first.opened_by.text, first.closed_by.text) == ("#", ".")
        assert (second.opened_by.text, second.closed_by.text) == (".", "#")

    def test_a_leaf_and_the_root_have_no_delimiters(self):
        tree = Form.parse("#kæt#", FEATURES).tree(FEATURES)
        assert (tree.opened_by, tree.closed_by, tree.asserted) == (None, None, False)
        leaves = tree.at("segment")
        assert len(leaves) == 3
        assert all(n.opened_by is None and n.closed_by is None for n in leaves)
        assert not any(n.asserted for n in leaves)

    @pytest.mark.parametrize(
        "shape", ["{0}", "#{0}#", "{0}.{0}", "#{0}.{0}#", "{0}|{0}", "#{0}# {0}"]
    )
    def test_a_bracket_is_the_span_endpoint_it_records(self, shape):
        """The property the whole design rests on, swept over the inventory.

        A node's brackets are not extra information: they *are* its span
        in the segmental sequence, and what provenance adds is only which
        delimiter supplied each one. So every non-None bracket must sit
        exactly at the node's own endpoint, counted in segments -- which is
        the same count ``Boundary.at`` uses and ``rebuild`` reads.
        """
        checked = 0
        for phone in _phones():
            form = Form.parse(shape.format(phone), FEATURES)
            total = len([u for u in form.units if not u.is_boundary])
            assert _check_spans(form.tree(FEATURES), 0) == total
            checked += 1
        assert_swept(checked, _phones())

    def test_the_brackets_are_the_boundaries_the_form_reports(self):
        """Provenance names existing boundaries; it does not mint new ones."""
        checked = 0
        for text in ("#kæt.dɒɡ#", "a|b‖c", "kæt dɒ.ɡi", "#a.b# #c#"):
            form = Form.parse(text, FEATURES)
            declared = [(b.text, b.at) for b in form.boundaries]
            tree = form.tree(FEATURES)
            used = [
                (b.text, b.at)
                for level in tiers(FEATURES)
                for node in tree.at(level)
                for b in (node.opened_by, node.closed_by)
                if b is not None
            ]
            assert used, text
            assert set(used) <= set(declared), (text, used, declared)
            checked += 1
        assert checked == 4, "sweep did not run"

    def test_no_bracket_enters_the_unit_sequence(self):
        """``Form.units`` stays the faithful read of what was spelled.

        Putting bracket units in would renumber ``Site.start``/``end``,
        which are documented public indices into this sequence.
        """
        checked = 0
        for phone in _phones():
            text = f"#{phone}.{phone}#"
            form = Form.parse(text, FEATURES)
            form.tree(FEATURES)
            assert spell(form.units) == text
            assert [u.text for u in form.units] == [
                u.text for u in units(text, FEATURES)
            ]
            checked += 1
        assert_swept(checked, _phones())


class TestDeclaringAFurtherLevelExtendsTheTreeWithNoCodeChange:
    """The promise ``form.py``'s docstring makes, tested rather than assumed.

    ``tiers()`` and ``rules._reaches()`` read one ordinal declaration and
    neither restates it, so a value added to ``<feature name="level">``
    should reach the tree and the rule engine on its own. That is only
    true if nothing in Python enumerates the tiers, which is exactly the
    sort of claim this repo has been wrong about while looking right --
    ``tree()`` did hardcode "depth 0 is delimited by the form edges",
    which a level above ``word`` would have broken.
    """

    LEVEL = "discourse"
    GLYPH = "¶"

    @pytest.fixture
    def extended(self, tmp_path):
        """The shipped inventory plus one declared level and one mark for it."""
        source = FEATURES.xml_path.read_text(encoding="utf-8")
        value = '<value name="utterance" short="utt" href="Utterance_(linguistics)"/>'
        mark = '<suprasegmental name="‖" break="major" level="utterance"'
        assert source.count(value) == 1 and source.count(mark) == 1
        patched = source.replace(
            value, f'{value}\n      <value name="{self.LEVEL}" short="dsc"/>'
        ).replace(
            mark,
            f'<suprasegmental name="{self.GLYPH}" break="major"'
            f' level="{self.LEVEL}"/>\n    {mark}',
        )
        path = tmp_path / "ipa.xml"
        path.write_text(patched, encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_the_ladder_grows_at_the_top(self, extended):
        assert tiers(extended)[0] == self.LEVEL
        assert tiers(extended) == (self.LEVEL, *tiers(FEATURES))

    def test_the_tree_splits_on_the_new_tier(self, extended):
        tree = Form.parse(f"a{self.GLYPH}b", extended).tree(extended)
        assert [n.to_ipa() for n in tree.at(self.LEVEL)] == ["a", "b"]

    def test_the_new_tier_brackets_what_it_splits(self, extended):
        first, second = (
            Form.parse(f"a{self.GLYPH}b", extended).tree(extended).at(self.LEVEL)
        )
        assert (first.opened_by, first.closed_by.text) == (None, self.GLYPH)
        assert (second.opened_by.text, second.closed_by) == (self.GLYPH, None)

    def test_the_edge_tier_does_not_move_with_it(self, extended):
        """A form with no ``¶`` in it is not thereby one discourse."""
        assert edge_tier(extended) == "word"
        tree = Form.parse("kæt", extended).tree(extended)
        assert tree.at(self.LEVEL) == ()
        assert len(tree.at("word")) == 1

    def test_a_space_keeps_asserting_whatever_a_form_edge_asserts(self, extended):
        """The two must not come apart when the ladder grows.

        Whitespace is undeclared, so ``units()`` has to say what level it
        asserts; if it said the literal ``word`` while the form's own end
        rose to the strongest declared level, a context matching the end of
        a form would stop matching a trailing space, and the two readings
        of "an edge" would disagree.
        """
        for inventory in (FEATURES, extended):
            (space,) = [u for u in units("a b", inventory) if u.text == " "]
            assert space.level == edge_tier(inventory)

    def test_the_rule_engine_ranks_it_from_the_same_declaration(self, extended):
        """``_reaches`` is the other reader of the ladder, and it is not mine.

        Imported here rather than restated: if the two ever stop reading
        one declaration, this is what says so.
        """
        from ipakit.rules import _reaches

        for weaker in tiers(FEATURES):
            assert _reaches(self.LEVEL, weaker, extended)
            assert not _reaches(weaker, self.LEVEL, extended)


class TestABoundaryPatternMatchesItsLevelOrStronger:
    """The consequence of the new levels for ``rules.py``, which this lane
    does not own. Measured here so the change cannot be silent."""

    def test_a_word_pattern_now_matches_a_phrase_break(self):
        """A phrase boundary *is* a word boundary, so it should."""
        assert ipakit.rewrite("a|b", "a -> o / _ #") == "o|b"
        assert ipakit.rewrite("a‖b", "a -> o / _ #") == "o‖b"

    def test_a_syllable_pattern_does_too(self):
        assert ipakit.rewrite("a|b", "a -> o / _ .") == "o|b"

    def test_the_reverse_still_does_not_hold(self):
        """``#`` is not matched by a mere syllable break, and ``|`` is not
        matched by a word mark."""
        assert ipakit.rewrite("a.b", "a -> o / _ #") == "a.b"
        assert ipakit.rewrite("a#b", "a -> o / _ |") == "a#b"

    def test_a_word_pattern_reaches_the_linking_mark(self):
        """The point of giving ``‿`` a level: ``#`` must reach it.

        Before, only ``%`` did, and ``%`` also catches the syllable dot --
        so a word-final rule written with ``%`` fired at an interior dot
        and the optional dot changed which rules fired after all.
        """
        assert ipakit.rewrite("lez‿ami", "z -> ∅ / _ #") == "le‿ami"
        assert ipakit.rewrite("a‿b", "a -> o / _ .") == "o‿b"
        assert ipakit.rewrite("a‿b", "a -> o / _ ‿") == "o‿b"

    def test_naming_a_word_edge_no_longer_needs_two_patterns(self):
        """``%`` and ``#`` used to differ on ``‿`` and agree on nothing
        useful; now ``#`` alone covers every word edge, and ``%`` is the
        only one that also catches a syllable dot."""
        spec = "z -> ∅ / _ #"
        assert ipakit.rewrite("lez‿ami", spec) == "le‿ami"
        assert ipakit.rewrite("lez ami", spec) == "le ami"
        assert ipakit.rewrite("lez#ami", spec) == "le#ami"
        assert ipakit.rewrite("lez", spec) == "le"
        # A syllable dot is not a word edge, and this is what says so.
        assert ipakit.rewrite("lez.ami", spec) == "lez.ami"

    def test_a_form_edge_is_still_only_a_word_edge(self):
        """``_ #`` fires at the end of a form; ``_ |`` must not, because a
        phrase break is written or it is not there."""
        assert ipakit.rewrite("ab", "b -> o / _ #") == "ao"
        assert ipakit.rewrite("ab", "b -> o / _ |") == "ab"

    def test_naming_a_level_in_a_query_is_refused(self):
        """The tiers add no notation, and the query says so out loud.

        A bracketed query is compared against a *segment's* bundle, and a
        boundary has none, so ``[level=phrase]`` cannot hold. ``#``, ``.``
        and ``%`` are the level notations, and ``|``/``‖`` are matched as
        the literal marks they are.

        Refused rather than answered "no site". A term over a feature no
        unit can carry is not a narrow term: on the negative side of the
        same coin, ``[-word]`` was satisfied by the absence of the key and
        so matched every segment there is.
        """
        for spec in ("a -> o / _ [level=phrase]", "a -> o / _ [-word]"):
            with pytest.raises(R.RuleError, match="is structural"):
                ipakit.rewrite("a|b", spec)
