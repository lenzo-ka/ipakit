"""A mark the parser cannot place is reported, never dropped.

``segments`` read a token that carried no unit and moved on. Every
registered mark written *before* its base is such a token -- ``ⁿd`` is
``ⁿ`` then ``d`` -- so the mark left no trace in the units, in the
bundle, or in the distance: ``segments("ⁿd", strict=True)`` was one
segment spelling ``d``, ``features("ⁿd")`` was ``{}``, and
``distance("ⁿd", "d")`` was ``0.0``. Swept over the table, **64 of 68
marks** vanished that way with nothing said, and two more (the ties)
were reported by ``parse`` before they got here.

``validate_ipa`` had reported the same string as ``orphan_diacritic``
since long before. Two reads of "is this well formed" disagreed about
one string, and the quiet one was the one the metric goes through.

The corpus is deliberately not the canonical one. ``scripts/sweep.py``
enumerates units that spell themselves back; what is under test here is
exactly the strings that do *not*, so it enumerates every registered
mark in both placements and asks a weaker question of each: was it kept,
or was it refused by name.
"""

from __future__ import annotations

import unicodedata
import warnings

import pytest
from ipakit import IPAFeatures
from ipakit.constants import METADATA_ATTRS
from ipakit.segment import modifier_mode

#: Modes whose marks describe something other than the segment's own
#: value for a key -- a phase of it, a constriction added beside the
#: primary, a property of the unit rather than of its feature bag. Read
#: off ``<modes>`` by name because the mode names are declared there;
#: what is *in* each mode is derived from the features every time.
_NOT_THE_SEGMENTS_OWN = ("structural", "prosodic", "release", "secondary")


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def _substantive(ipa: IPAFeatures, text: str) -> list[str]:
    """The characters of ``text`` a unit can carry, as a multiset.

    Structural marks are excluded on both sides of every comparison
    below: a break and the linking tie are relations *between* units,
    belong to no unit at either side, and ``Form`` is the layer that
    keeps them. A unit emits its marks in its own order, so what is
    compared is that nothing was lost, not that nothing moved.
    """
    return sorted(ch for ch in text if not ipa.is_structural_token(ch))


def placements(ipa: IPAFeatures) -> list[str]:
    """Every registered mark on every registered phone, both sides.

    The two placements are the two the data allows anything to be
    written in. One of them is canonical and one of them is what every
    external inventory ships, which is the whole point: PHOIBLE and BIPA
    write the pre-modifier, and until a mark written there was refused,
    a source that used it lost it.
    """
    return [
        unicodedata.normalize("NFC", text)
        for phone in ipa.phones
        for mark in ipa.diacritics
        for text in (phone + mark, mark + phone)
    ]


def sweep(ipa: IPAFeatures) -> dict[str, str]:
    """Each placement, as "kept" or "refused" -- or "dropped", which is
    the verdict this whole module exists to see none of."""
    out: dict[str, str] = {}
    for text in placements(ipa):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            units = ipa.segments(text)
        emitted = "".join(unit.to_ipa() for unit in units)
        # An alias is a second spelling of a declared mark, so the
        # emission is compared against what the alias resolves to.
        wanted = ipa.expand_ligatures(text)
        if _substantive(ipa, emitted) == _substantive(ipa, wanted):
            out[text] = "kept"
        elif caught:
            out[text] = "refused"
        else:
            out[text] = "dropped"
    return out


@pytest.fixture(scope="module")
def verdicts(ipa: IPAFeatures) -> dict[str, str]:
    return sweep(ipa)


class TestNoPlacementOfAMarkIsSilentlyLost:
    """The predicate, over the shape rather than over the 64."""

    def test_the_sweep_is_wide(
        self, ipa: IPAFeatures, verdicts: dict[str, str]
    ) -> None:
        # Two placements of every mark on every phone, less the strings
        # two placements spell the same way.
        assert len(verdicts) > 15000, "sweep did not run"
        assert len(ipa.diacritics) > 60, "the mark table went missing"
        assert len(ipa.phones) > 130, "the phone inventory went missing"

    def test_the_sweep_reaches_both_answers(self, verdicts: dict[str, str]) -> None:
        # A predicate that only ever sees one answer is not being tested.
        # Both counts are in the thousands: a mark on its base is kept, a
        # mark before it is refused, and that is most of the corpus each.
        counted = {verdict: 0 for verdict in ("kept", "refused", "dropped")}
        for verdict in verdicts.values():
            counted[verdict] += 1
        assert counted["kept"] > 5000, counted
        assert counted["refused"] > 5000, counted

    def test_no_placement_is_dropped(self, verdicts: dict[str, str]) -> None:
        dropped = sorted(
            text for text, verdict in verdicts.items() if verdict == "dropped"
        )
        assert dropped == [], f"{len(dropped)} placements lost a mark in silence"

    def test_what_warns_by_default_raises_under_strict(
        self, ipa: IPAFeatures, verdicts: dict[str, str]
    ) -> None:
        # ``strict=True`` is what a caller passes because they want to be
        # told, so nothing may reach a warning without reaching this too.
        refused = [text for text, verdict in verdicts.items() if verdict == "refused"]
        assert len(refused) > 5000, "nothing was refused"
        for text in refused:
            with pytest.raises(ValueError):
                ipa.segments(text, strict=True)

    def test_the_sweep_sees_the_silence_when_it_is_put_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-vacuity, by perturbing what is under test rather than by
        trusting a count. Suppress the one report and the same sweep must
        find thousands of placements dropped without a word."""
        report = IPAFeatures._report_unplaced
        monkeypatch.setattr(
            IPAFeatures,
            "_report_unplaced",
            lambda self, superseded, unbound, unplaced, strict: report(
                self, superseded, unbound, [], strict
            ),
        )
        dropped = sum(1 for v in sweep(IPAFeatures()).values() if v == "dropped")
        assert dropped > 5000, "the guard is not looking at the report"


class TestTheReportedCases:
    """The five strings the defect was reported as."""

    def test_a_pre_modifier_that_states_no_phase_raises_under_strict(
        self, ipa: IPAFeatures
    ) -> None:
        # ``ʷ`` shares the position and is a secondary articulation, which
        # spans the segment rather than naming a phase of it, so it binds
        # the unit before it and there is none.
        with pytest.raises(ValueError, match="unplaced"):
            ipa.segments("ʷk", strict=True)

    def test_a_pre_modifier_that_states_no_phase_warns_by_default(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.warns(UserWarning, match="unplaced"):
            ipa.segments("ʷk")
        with pytest.warns(UserWarning, match="unplaced"):
            ipa.get_features("ʷk")

    def test_the_above_the_symbol_spellings_are_registered(
        self, ipa: IPAFeatures
    ) -> None:
        # U+030A and U+030D were unregistered characters, so a segment
        # spelled with either came back a mark short and voiceless ŋ read
        # as ŋ. They are the chart's own spelling for a base whose
        # descender leaves no room below it.
        assert ipa.tokenize("ŋ̊") == ["ŋ̥"]
        assert ipa.tokenize("ŋ̍") == ["ŋ̩"]
        assert ipa.get_features("ŋ̊")["voiced"] == "-"
        assert ipa.get_features("ŋ̍")["syllabic"] == "+"
        assert ipa.validate_ipa("ŋ̊") == []

    def test_an_ejective_click_keeps_its_ejection(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("ǂʼ")["airstream"] == "ejective"
        assert ipa.distance("ǂʼ", "ǂ") > 0

    def test_a_structural_mark_is_not_an_unplaced_one(self, ipa: IPAFeatures) -> None:
        # A break and the linking tie belong to no unit at either side,
        # by declaration rather than by exemption, so they carry no unit
        # and say nothing about it. ``Form`` is where they survive.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert len(ipa.segments("a|b")) == 2
            assert len(ipa.segments("a‿b")) == 2


class TestNoMarkIsOverruledByItsBase:
    """The other half of the same silence: a mark that parses, is placed,
    and then states nothing the unit reads back.

    ``ǂʼ`` spelled itself, parsed to one unit and carried the mark -- and
    read as ``ǂ`` anyway, because ``airstream`` sat in the additive
    default and the click declares its own. Nothing was dropped and the
    answer was still wrong by exactly one feature.
    """

    def test_every_mark_that_states_the_segments_own_value_lands(
        self, ipa: IPAFeatures
    ) -> None:
        overruled: list[tuple[str, str, str, str]] = []
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for phone in ipa.phones:
                for mark, declared in ipa.diacritics.items():
                    if modifier_mode(ipa, mark) in _NOT_THE_SEGMENTS_OWN:
                        continue
                    unit = unicodedata.normalize("NFC", phone + mark)
                    try:
                        parsed = ipa.segment(unit)
                    except ValueError:
                        continue
                    # One constituent wearing this one mark: anything else
                    # and the flat read is answering about a chain, which
                    # is a different question.
                    if len(parsed.constituents) != 1:
                        continue
                    if parsed.constituents[0].modifiers != (mark,):
                        continue
                    if parsed.to_ipa() != unit:
                        continue
                    checked += 1
                    read = parsed.scalar(with_defaults=False)
                    for key, value in declared.features.items():
                        if key in METADATA_ATTRS:
                            continue
                        if read.get(key) != value:
                            overruled.append((unit, key, value, read.get(key, "")))
        assert checked > 2000, "sweep did not run"
        assert overruled == [], (
            f"{len(overruled)} units read back a value their own mark "
            f"contradicts, e.g. {overruled[:3]}"
        )


class TestAPreArticulationIsRead:
    """``ⁿd``, ``ˀb``, ``ʰk`` are how every outside source spells a
    pre-articulation, and they are one unit each.

    The two halves of this are easy to confuse and are kept apart here.
    The *sound* was in the model all along -- ``n͡d`` is a tied unit that
    classifies as prenasalized -- and what was missing was the superscript
    notation. So the notation reads as a phase of one segment and not as
    the tied chain: a mark states an ``approach`` where the same mark
    after the base states a ``release``. ``docs/ties.md`` carries the
    argument and ``scripts/interop.py premarks`` the demand.
    """

    def test_a_prenasalized_stop_is_a_unit_the_library_already_reads(
        self, ipa: IPAFeatures
    ) -> None:
        for spelling in ("n͡d", "m͡b", "ŋ͡ɡ"):
            unit = ipa.segment(spelling, strict=True)
            assert unit.kind.value == "prenasalized", spelling
            assert unit.to_ipa() == spelling

    def test_the_superscript_spelling_is_one_constituent(
        self, ipa: IPAFeatures
    ) -> None:
        unit = ipa.segment("ⁿd", strict=True)
        assert unit.to_ipa() == "ⁿd"
        assert len(unit.constituents) == 1
        assert unit.constituents[0].base == "d"
        assert unit.constituents[0].approach == ("ⁿ",)
        assert ipa.get_features("ⁿd")["approach"] == "nasal"
        assert ipa.describe("ⁿd") == "voiced pre-nasalized alveolar plosive"

    def test_the_two_spellings_are_not_the_same_claim(self, ipa: IPAFeatures) -> None:
        """Why the chain is not the answer to the notation question, and
        why the notation did not become one.

        A tied unit is two constituents with a juncture; a mark is one
        constituent with a phase on it. The metric is structural, so the
        two sit at very different distances from the same base -- reading
        ``ⁿd`` as ``n͡d`` would move a prenasalized stop most of the way
        from ``d`` to something else, where the phase-mark spelling stays
        near it, exactly as the release-mark spelling of the mirror-image
        sound does. The superscript reads as the near one, and the two
        stay distinct units rather than one being rewritten to the other.
        """
        assert ipa.segment_distance("n͡d", "d") > 5 * ipa.segment_distance("dⁿ", "d")
        assert ipa.segment_distance("n͡d", "d") > 5 * ipa.segment_distance("ⁿd", "d")
        assert ipa.segment("ⁿd") != ipa.segment("n͡d")

    def test_the_phase_a_mark_states_is_the_end_it_is_written_at(
        self, ipa: IPAFeatures
    ) -> None:
        """One declaration, two placements, and never both at once."""
        for mark, value in (("ⁿ", "nasal"), ("ˀ", "glottal"), ("ʰ", "aspirated")):
            before = ipa.get_features(mark + "t", with_defaults=False)
            after = ipa.get_features("t" + mark, with_defaults=False)
            assert before.get("approach") == value and "release" not in before, mark
            assert after.get("release") == value and "approach" not in after, mark

    def test_the_marks_written_before_a_base_are_the_release_marks(
        self, ipa: IPAFeatures
    ) -> None:
        """The measurement's finding, as a claim about the inventory.

        Over BIPA, CLTS's whole grapheme table and PHOIBLE, the marks
        outside sources write before a base are the four declaring
        ``release`` -- so the counterpart feature needed no vocabulary of
        its own, only the other phase. This asserts that those four, and
        only those four, are what the parser now admits there, and that
        each states one phase at each end; the counts live in the script,
        which is where something re-runs them.
        """
        pre_articulations = ("ⁿ", "ˀ", "ʰ", "ʱ")
        assert ipa.approach_marks == frozenset(pre_articulations)
        for mark in pre_articulations:
            assert modifier_mode(ipa, mark) == "release", mark
            assert modifier_mode(ipa, mark, approach=True) == "approach", mark
            stated = set(ipa.diacritics[mark].features) - METADATA_ATTRS
            assert stated == {"release", "approach"}, mark
        # And the one that shares the position without being a phase.
        assert modifier_mode(ipa, "ʷ") == "secondary"
        assert "ʷ" not in ipa.approach_marks
