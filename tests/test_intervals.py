"""What an ``Interval`` on a ``Form`` must satisfy.

``Form`` had exactly one field, and ``segments``, ``phones``,
``attributes``, ``boundaries`` and ``tree()`` were all reads of it. An
interval is the first thing on a form that is **not** derivable from the
unit sequence, so the invariants that rested on "one sequence with
projections" have to be restated rather than assumed to carry over. Three
of them are tested here:

* ``to_ipa()`` round-trips the **spelling**, and an interval is not
  spelled, so a round-trip through the string does not carry one back;
* ``rebuild`` is handed its intervals, because nothing derives them, and
  a stale endpoint is refused rather than carried; and
* nothing is invented -- a form with no dots has no syllable intervals,
  and a form with dots has none either, because the dot asserts a
  *boundary* and an interval is a different claim.

The fourth is the reason the field exists at all, and it is the one worth
reading: an interval can state enchaînement and ``tree()`` cannot.
"""

from __future__ import annotations

import dataclasses

import ipakit
import pytest
from ipakit.form import Form, Interval, Node, tier_names

FEATURES = ipakit.load_ipa_features()

#: French *petite amie*, resyllabified. The `‿` is a declared **word**
#: boundary, and the syllable `ta` needs the `t` on its left and the `a`
#: on its right -- one syllable spanning it.
LIAISON = "pə.ti.t‿a.mi"


def _spans(form: Form, spans: list[Interval]) -> Form:
    return Form.of(form.units, spans)


def _syllables_of_liaison() -> list[Interval]:
    """`pə` `ti` `t‿a` `mi`, over the units of :data:`LIAISON`.

    Indices into ``Form.units``, which counts the separators: ``p ə . t i
    . t ‿ a . m i``.
    """
    return [
        Interval("syllable", 0, 2),
        Interval("syllable", 3, 5),
        Interval("syllable", 6, 9),
        Interval("syllable", 10, 12),
    ]


class TestATierNameIsDeclaredAndAnUndeclaredOneIsRefused:
    def test_the_vocabulary_is_read_from_the_data(self, ipa) -> None:
        """Not written out here, so a language declaring one gets it."""
        assert tier_names(ipa) == tuple(ipa.features["tier"].values)
        assert set(tier_names(ipa)) >= {"syllable", "mora", "morph"}

    def test_an_undeclared_tier_is_refused_loudly(self) -> None:
        """The same default the rule parser keeps for an unknown bare word.

        A typo that produced an interval on a tier nothing declares would
        be carried, compared against nothing, and read as an assertion
        about a tier that does not exist.
        """
        with pytest.raises(ValueError) as caught:
            Interval("gesture", 0, 2, FEATURES)
        message = str(caught.value)
        assert "gesture" in message
        assert "syllable" in message, "the refusal does not say what is declared"

    def test_every_declared_tier_is_accepted(self, ipa) -> None:
        checked = 0
        for name in tier_names(ipa):
            assert Interval(name, 0, 1, ipa).tier == name
            checked += 1
        assert checked >= 3, f"{checked} tiers swept"

    def test_a_span_that_runs_backwards_is_refused(self) -> None:
        with pytest.raises(ValueError):
            Interval("syllable", 3, 1, FEATURES)
        with pytest.raises(ValueError):
            Interval("syllable", -1, 2, FEATURES)

    def test_an_empty_span_is_allowed_because_a_site_has_one(self) -> None:
        """Half-open, the convention ``rules.Site`` already uses.

        ``start == end`` is a position rather than a span there, and an
        interval is not the place to decide that a tier may not have one.
        """
        assert len(Interval("mora", 2, 2, FEATURES)) == 0
        assert len(Interval("mora", 2, 5, FEATURES)) == 3

    def test_the_inventory_is_not_stored_on_the_interval(self) -> None:
        """Two intervals with the same tier and span are one interval.

        The inventory names what the tier is checked against; it is not
        part of what the interval says.
        """
        assert Interval("mora", 0, 2, FEATURES) == Interval("mora", 0, 2)
        assert dataclasses.replace(Interval("mora", 0, 2), end=3) == Interval(
            "mora", 0, 3
        )


class TestNothingIsInvented:
    """The policy ``docs/form.md`` already states, applied to intervals.

    A form with no dots has unspecified syllabification, not one syllable.
    Deriving intervals from the separators would make the same claim from
    the other end -- and would make it about *every* transcription in the
    repository, none of which asserted a tier.
    """

    def test_parsing_derives_no_intervals_from_the_separators(self) -> None:
        for text in ("kæt", "kæt.dɒɡ", "#kæt.dɒɡ#", LIAISON):
            assert Form.parse(text, FEATURES).intervals == (), text

    def test_a_form_with_no_dots_has_no_syllable_intervals(self) -> None:
        """Not one. The distinction the tree already makes, kept here."""
        form = Form.parse("kæt", FEATURES)
        assert form.intervals == ()
        assert [n.to_ipa() for n in form.tree(FEATURES).at("syllable")] == []

    def test_an_interval_is_carried_only_where_one_was_handed_in(self) -> None:
        form = Form.parse(LIAISON, FEATURES)
        held = _spans(form, _syllables_of_liaison())
        assert len(held.intervals) == 4
        assert Form.parse(held.to_ipa(), FEATURES).intervals == ()


class TestTheRoundTripCoversTheSpellingAndNotTheWholeForm:
    """Restated, because ``Form`` is no longer one sequence.

    ``to_ipa()`` round-tripping "everything the transcription had" was true
    while every field was a read of the units. An interval is not spelled,
    so the claim now covers the *units* exactly, and says nothing about a
    field the notation has no way to write.
    """

    def test_intervals_do_not_change_what_a_form_spells(self) -> None:
        checked = 0
        for text in ("kæt", "kæt.dɒɡ", "#kæt.dɒɡ#", LIAISON, "kˌæn.tˈiːn"):
            bare = Form.parse(text, FEATURES)
            held = _spans(bare, [Interval("morph", 0, len(bare.units), FEATURES)])
            assert held.to_ipa() == bare.to_ipa() == text, text
            checked += 1
        assert checked == 5, f"{checked} forms swept, not 5"

    def test_the_units_round_trip_and_the_intervals_do_not(self) -> None:
        form = _spans(Form.parse(LIAISON, FEATURES), _syllables_of_liaison())
        back = Form.parse(form.to_ipa(), FEATURES)
        assert back.units == form.units
        assert back.intervals == ()
        assert form.intervals != ()

    def test_an_interval_past_the_end_of_the_form_is_refused(self) -> None:
        """A stale endpoint is a well-formed wrong answer if it is kept."""
        form = Form.parse("kæt", FEATURES)
        with pytest.raises(ValueError) as caught:
            Form.of(form.units, [Interval("syllable", 0, 9, FEATURES)])
        assert "runs past" in str(caught.value)

    def test_collapsing_boundaries_under_an_interval_is_refused(self) -> None:
        """Removing a position moves every index after it.

        ``without_boundaries`` would spell the same sounds and describe a
        different span, which is the silent wrong answer this module is
        built against. Shifting them is rebasing, and rebasing needs to
        know what moved.
        """
        form = _spans(Form.parse(LIAISON, FEATURES), _syllables_of_liaison())
        with pytest.raises(ValueError) as caught:
            form.without_boundaries()
        assert "rebase" in str(caught.value)
        assert Form.parse(LIAISON, FEATURES).without_boundaries().to_ipa() == (
            "pətitami"
        )


class TestRebuildCarriesIntervalsItIsHanded:
    """Beside the asymmetry it does not repair.

    ``rebuild`` is the inverse of the two projections it is given, and
    neither carries a structural zero. Intervals are a third data argument
    of the same kind: nothing derives them, so they are handed in, and the
    endpoints are the caller's because only the caller knows whether the
    sequence being rebuilt is the one they were taken off.
    """

    def test_rebuild_takes_intervals_as_a_data_argument(self) -> None:
        form = Form.parse("kˌæn.tˈiːn", FEATURES)
        spans = [Interval("morph", 0, 4, FEATURES)]
        back = Form.rebuild(form.segments, form.boundaries, spans, FEATURES)
        assert back.to_ipa() == "kˌæn.tˈiːn"
        assert back.intervals == tuple(spans)

    def test_rebuild_without_intervals_is_unchanged(self) -> None:
        form = Form.parse("lez‿a.mi", FEATURES)
        back = Form.rebuild(form.segments, form.boundaries, features=FEATURES)
        assert back.to_ipa() == "lez‿a.mi"
        assert back.intervals == ()

    def test_a_stale_endpoint_is_refused_rather_than_carried(self) -> None:
        """The zero asymmetry, seen from the intervals.

        A form holding a zero rebuilds without it, so the rebuilt sequence
        is shorter than the one the intervals indexed. An interval reaching
        the old end is stale, and it is refused here rather than silently
        naming a shorter span.
        """
        form = Form.parse("le∅ʃjɛ̃", FEATURES)
        assert any(u.is_zero for u in form.units), "no zero in the fixture"
        whole = Interval("morph", 0, len(form.units), FEATURES)
        with pytest.raises(ValueError) as caught:
            Form.rebuild(form.segments, form.boundaries, [whole], FEATURES)
        assert "runs past" in str(caught.value)


class TestAnIntervalStatesEnchainementAndTheTreeCannot:
    """The capability the field buys, and the reason for the whole piece.

    ``docs/form.md`` records that ``tree()`` cannot represent a constituent
    crossing a stronger boundary: it splits on ``word`` first, because
    ``word`` is above ``syllable`` on the ordinal ladder, so a syllable
    spanning ``‿`` is cut in two before the syllable tier is reached. An
    interval has no such problem, because it makes no claim to nest.
    """

    def test_the_linking_mark_is_a_word_boundary(self, ipa) -> None:
        """Which is why a syllable crossing it is the hard case.

        ``‿`` is declared ``level="word"`` on purpose -- it is the absence
        of a *pause*, not of a boundary -- and that declaration is what
        makes the tree split there.
        """
        form = Form.parse(LIAISON, FEATURES)
        linking = [u for u in form.units if u.text == "‿"]
        assert len(linking) == 1
        assert linking[0].level == "word"
        assert linking[0].features.get("linking") == "+"

    def test_the_nested_reading_cuts_the_crossing_syllable_in_two(self) -> None:
        form = Form.parse(LIAISON, FEATURES)
        assert [n.to_ipa() for n in form.tree(FEATURES).at("syllable")] == [
            "pə",
            "ti",
            "t",
            "a",
            "mi",
        ]
        assert [n.to_ipa() for n in form.tree(FEATURES).at("word")] == [
            "pətit",
            "ami",
        ]

    def test_the_interval_reading_states_the_four_syllables(self) -> None:
        form = _spans(Form.parse(LIAISON, FEATURES), _syllables_of_liaison())
        spelled = [
            "".join(u.text for u in form.units[s.start : s.end] if not u.is_boundary)
            for s in form.intervals
        ]
        assert spelled == ["pə", "ti", "ta", "mi"]

    def test_no_node_of_the_tree_spans_what_the_interval_spans(self) -> None:
        """The demonstration, stated over the whole tree rather than a tier.

        Not "the syllable tier disagrees" -- *no* node anywhere, at any
        depth, covers exactly the units ``t‿a`` covers. A nested reading
        cannot express the span, because the span is contained by neither
        word and containment is all a tree has.
        """
        form = Form.parse(LIAISON, FEATURES)
        crossing = Interval("syllable", 6, 9, FEATURES)
        wanted = tuple(
            u for u in form.units[crossing.start : crossing.end] if not u.is_boundary
        )
        assert "".join(u.text for u in wanted) == "ta"

        nodes = _every_node(form.tree(FEATURES))
        assert len(nodes) > 10, f"the tree did not build: {len(nodes)}"
        assert not any(n.units == wanted for n in nodes), (
            "a node covers the crossing span, so the tree can state it "
            "after all and the motivation for Interval is wrong"
        )

    def test_and_the_two_halves_land_in_different_words(self) -> None:
        """Why no node covers it: the tree splits on ``word`` first.

        The ``t`` belongs to *petite* and the ``a`` to *amie*, so the only
        node containing both is their parent, which contains the whole
        form as well.
        """
        form = Form.parse(LIAISON, FEATURES)
        words = form.tree(FEATURES).at("word")
        left, right = form.units[6], form.units[8]
        holding = [[w.to_ipa() for w in words if u in w.units] for u in (left, right)]
        assert holding == [["pətit"], ["ami"]], holding

    def test_two_intervals_may_overlap_with_neither_containing_the_other(
        self,
    ) -> None:
        """What a tree cannot hold, said directly.

        A morph interval over *petite* and the syllable interval over
        ``t‿a`` share the ``t`` and neither contains the other. A Dyck
        bracketing is strictly nested by definition, so this is not a
        notation that could be added to the tree -- it is a different
        shape.
        """
        form = Form.parse(LIAISON, FEATURES)
        syllable = Interval("syllable", 6, 9, FEATURES)
        morph = Interval("morph", 0, 7, FEATURES)
        held = _spans(form, [syllable, morph])
        assert len(held.intervals) == 2
        assert _overlaps(syllable, morph)
        assert not _contains(morph, syllable)
        assert not _contains(syllable, morph)


def _every_node(node: Node) -> list[Node]:
    return [node, *(n for child in node for n in _every_node(child))]


def _overlaps(a: Interval, b: Interval) -> bool:
    return a.start < b.end and b.start < a.end


def _contains(outer: Interval, inner: Interval) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end
