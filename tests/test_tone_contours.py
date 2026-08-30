"""A contour is a sequence of tone levels, and a compound mark declares its own.

`᷅` U+1DC5 COMBINING GRAVE-MACRON declared `contour="falling"`. Grave is
low and macron is mid -- `ipa.xml` says so itself, on the simplex marks --
and low then mid is a **rise**.

The wrong value was invisible to everything that measures. `tone` and
`contour` are `mode="prosodic"`, so they live on the unit and never enter
the feature bag (docs/ties.md): `features("a")` and `features("a᷅")` are
equal and `distance("a", "a᷅")` is 0.0. It surfaced at exactly one read --
`units("a᷅")[0].prosody` -- which is why no sweep over features or
distances could have found it and why the guard below is over the
*declaration* rather than over any computed value.

The same read had a larger defect under it: a run of prosodic marks
merged last-writer-wins, so **only the final tone letter survived**.
`a˩˥` came back as `tone=top` and `a˥˩` as `tone=bottom` -- a rise and a
fall recorded as opposite *level* tones, silently. A unit's tone is now
its levels in time order, which is what the run spells and what a compound
diacritic abbreviates, so the two spellings agree and nothing is dropped
(docs/tone.md).

That makes the guard derived twice over. Unicode's names for these
ligatures spell their components in time order, and `ipa.xml` already
declares what each component's pitch is, so a compound's whole `tone`
value is a consequence of two things the file states rather than a third
fact to maintain beside them. `scripts/invariants.py:check_contour_marks`
is the predicate; this file pins it, pins the premises it rests on, and
pins which marks are declared.
"""

from __future__ import annotations

import sys
import unicodedata
import warnings
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.form import declared_prosody, units

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import check_contour_marks, pitch_marks  # noqa: E402

FEATURES = IPAFeatures()

#: The six compound tone diacritics Unicode encodes for this series, read
#: off their character names: grave low, macron mid, acute high, left to
#: right in time order. Not a table of phonetic facts the library reads --
#: nothing imports this -- but the external measurement the check is
#: answerable to, written down so the derivation can be compared against a
#: source outside the library. L2/25-250 reads the first four as higher
#: rising, lower rising, lower falling, higher falling, which agrees.
UNICODE_SERIES = {
    "᷄": ("mid>high", "rising"),  # MACRON-ACUTE
    "᷅": ("low>mid", "rising"),  # GRAVE-MACRON
    "᷆": ("mid>low", "falling"),  # MACRON-GRAVE
    "᷇": ("high>mid", "falling"),  # ACUTE-MACRON
    "᷈": ("low>high>low", "rising>falling"),  # GRAVE-ACUTE-GRAVE
    "᷉": ("high>low>high", "falling>rising"),  # ACUTE-GRAVE-ACUTE
}

#: The two marks that name a direction and no levels. They are the whole
#: of the abbreviating half of the notation.
ABBREVIATIONS = {"̌": "rising", "̂": "falling"}


class TestTheLevelsAgreeWithTheParts:
    """The defect, and the predicate that would have caught it."""

    def test_the_shipped_inventory_passes_the_invariant(self) -> None:
        assert check_contour_marks(FEATURES)

    def test_the_mark_that_was_wrong(self) -> None:
        assert unicodedata.name("᷅") == "COMBINING GRAVE-MACRON"
        assert declared_prosody("᷅", FEATURES) == {"tone": "low>mid"}
        assert units("a᷅", FEATURES)[0].prosody == {
            "tone": "low>mid",
            "contour": "rising",
        }

    def test_its_neighbor_was_right_and_still_rises(self) -> None:
        assert declared_prosody("᷄", FEATURES) == {"tone": "mid>high"}
        assert units("a᷄", FEATURES)[0].prosody["contour"] == "rising"

    def test_both_registers_of_one_contour_are_distinguishable(self) -> None:
        # The point of the pair: two rises differing in register, and the
        # level sequence is what carries the register. If a future change
        # collapses them, this says so.
        low, high = (units(f"a{m}", FEATURES)[0].prosody for m in ("᷅", "᷄"))
        assert low["contour"] == high["contour"] == "rising"
        assert low["tone"] != high["tone"]

    @pytest.mark.parametrize(("mark", "want"), sorted(UNICODE_SERIES.items()))
    def test_the_declaration_agrees_with_unicode(
        self, mark: str, want: tuple[str, str]
    ) -> None:
        levels, shape = want
        assert declared_prosody(mark, FEATURES) == {"tone": levels}
        assert units(f"a{mark}", FEATURES)[0].prosody["contour"] == shape

    def test_the_premises_the_derivation_rests_on(self) -> None:
        # Both halves are read from ipa.xml, so if either moves the
        # derivation moves with it -- and this fails, which is the point.
        assert pitch_marks(FEATURES) == {
            "ACUTE": "high",
            "MACRON": "mid",
            "GRAVE": "low",
        }
        assert FEATURES.features["tone"].values == [
            "bottom",
            "low",
            "mid",
            "high",
            "top",
        ]

    def test_a_compound_declaring_the_wrong_way_round_is_caught(self) -> None:
        """The guard against the guard: it must fail on the old data.

        Written as a mutation of the loaded inventory rather than as a
        second copy of ipa.xml, so it exercises the same objects the
        shipped check runs over.
        """
        import dataclasses

        broken = IPAFeatures()
        mark = broken.diacritics["᷅"]
        broken.diacritics["᷅"] = dataclasses.replace(
            mark, features={**mark.features, "tone": "mid>low"}
        )
        assert not check_contour_marks(broken)

    def test_a_compound_restating_its_shape_is_caught(self) -> None:
        """The shape follows from the levels, so declaring it beside them
        is a second claim that can come to disagree with the first -- the
        exact shape of the original defect."""
        import dataclasses

        broken = IPAFeatures()
        mark = broken.diacritics["᷅"]
        broken.diacritics["᷅"] = dataclasses.replace(
            mark, features={**mark.features, "contour": "rising"}
        )
        assert not check_contour_marks(broken)

    def test_the_check_cannot_go_vacuous(self) -> None:
        """A simplex mark states no sequence, so it is invisible to the
        derivation. If the compound marks were ever removed the check
        would pass over nothing, and it reports that as a failure."""
        empty = IPAFeatures()
        empty.diacritics = {
            s: d
            for s, d in empty.diacritics.items()
            if "-" not in (unicodedata.name(s, "") if len(s) == 1 else "")
        }
        assert not check_contour_marks(empty)


class TestTheRunIsTheContour:
    """A tone-letter run and the diacritic abbreviating it are one thing.

    The defect this replaces was a silent wrong answer of the worst
    available shape: no error, a well-formed result, and a rise stored as
    the opposite level tone of a fall.
    """

    @pytest.mark.parametrize(
        ("form", "levels", "shape"),
        [
            ("a˩˥", "bottom>top", "rising"),
            ("a˥˩", "top>bottom", "falling"),
            ("a˧˩˧", "mid>bottom>mid", "falling>rising"),
            ("a˩˥˩", "bottom>top>bottom", "rising>falling"),
            ("a˥˦˧˨˩", "top>high>mid>low>bottom", "falling>falling>falling>falling"),
        ],
    )
    def test_no_letter_of_a_run_is_dropped(
        self, form: str, levels: str, shape: str
    ) -> None:
        assert units(form, FEATURES)[0].prosody == {"tone": levels, "contour": shape}

    def test_a_lone_level_has_no_shape(self) -> None:
        """One level is not a move, so there is no step to name."""
        assert units("a˥", FEATURES)[0].prosody == {"tone": "top"}

    def test_an_equal_pair_is_a_step_that_goes_nowhere(self) -> None:
        assert units("a˧˧", FEATURES)[0].prosody == {
            "tone": "mid>mid",
            "contour": "steady",
        }

    @pytest.mark.parametrize(("mark", "run"), [("᷄", "˧˦"), ("᷅", "˨˧"), ("᷈", "˨˦˨")])
    def test_the_two_spellings_of_one_contour_read_alike(
        self, mark: str, run: str
    ) -> None:
        """The equivalence the IPA chart claims, holding where it is true."""
        by_mark = units(f"a{mark}", FEATURES)[0].prosody
        by_letters = units(f"a{run}", FEATURES)[0].prosody
        assert by_mark == by_letters

    @pytest.mark.parametrize("form", ["a˩˥", "a˧˩˧", "ˈa᷈ː", "a᷉"])
    def test_a_run_survives_a_round_trip_through_the_string(self, form: str) -> None:
        assert ipakit.to_ipa(ipakit.segments(form)) == form


class TestAnAbbreviationStatesNoLevels:
    """The underspecification thesis, applied to the level tier.

    A caron says the pitch rises and does not say between which levels.
    Giving it a sequence would state a claim about the language's register
    that the transcriber never made -- the same error as reading an
    undotted word as one syllable (docs/form.md).
    """

    @pytest.mark.parametrize(("mark", "shape"), sorted(ABBREVIATIONS.items()))
    def test_it_declares_a_direction_and_nothing_else(
        self, mark: str, shape: str
    ) -> None:
        assert declared_prosody(mark, FEATURES) == {"contour": shape}
        assert units(f"a{mark}", FEATURES)[0].prosody == {"contour": shape}

    def test_the_abbreviations_are_exactly_these_two(self) -> None:
        """Every other prosodic mark names what it is rather than what it
        does. If a third abbreviating mark is ever declared, this fails
        and the reasoning above has to be re-read for it."""
        naming_a_shape = {
            symbol
            for symbol in FEATURES.diacritics
            if "contour" in declared_prosody(symbol, FEATURES)
        }
        assert naming_a_shape == set(ABBREVIATIONS)

    def test_compatible_with_a_full_spelling_but_not_identical(self) -> None:
        """The honest relation between `ǎ` and `a˩˥`.

        They agree on everything either states, and one states more. That
        is compatibility; equality would mean inventing levels for the
        caron or discarding the ones the letters wrote.
        """
        bare = units("ǎ", FEATURES)[0].prosody
        spelled = units("a˩˥", FEATURES)[0].prosody
        assert bare != spelled
        assert all(spelled[k] == v for k, v in bare.items())
        assert set(spelled) - set(bare) == {"tone"}


class TestADirectionIsStillAskable:
    """`contour=rising` is what a rule is written with, and it reaches
    both spellings now that the shape is derived rather than declared."""

    def test_a_rule_about_a_direction_matches_either_spelling(self) -> None:
        # The levels ride across because the rule spoke about the shape and
        # not about them; the caron goes because it *was* the shape.
        assert ipakit.rewrite("kǎ", "[contour=rising] -> e") == "ke"
        assert ipakit.rewrite("ka˩˥", "[contour=rising] -> e") == "ke˩˥"
        assert ipakit.rewrite("ka᷅", "[contour=rising] -> e") == "ke᷅"

    def test_a_rule_about_a_direction_does_not_match_the_other_one(self) -> None:
        # Written decomposed: the engine canonicalizes, so a combining
        # circumflex comes back out as one rather than precomposed.
        assert ipakit.rewrite("ka\u0302", "[contour=rising] -> e") == "ka\u0302"
        assert ipakit.rewrite("ka˥˩", "[contour=rising] -> e") == "ka˥˩"

    def test_a_turning_contour_is_neither_a_rise_nor_a_fall(self) -> None:
        for rule in ("[contour=rising] -> e", "[contour=falling] -> e"):
            assert ipakit.rewrite("ka᷈", rule) == "ka᷈"
        assert ipakit.rewrite("ka᷈", "[contour=rising>falling] -> e") == "ke᷈"

    def test_a_sequence_is_writable_and_finds_the_mark_that_spells_it(self) -> None:
        assert ipakit.rewrite("ka", "[vowel] -> [tone=low>high>low]") == "ka᷈"
        assert ipakit.rewrite("ka", "[vowel] -> [tone=bottom>top]") == "ka˩˥"

    def test_an_undeclared_level_in_a_sequence_still_raises(self) -> None:
        from ipakit.rules import RuleError

        with pytest.raises(RuleError, match="not a declared value"):
            ipakit.rewrite("ka", "[vowel] -> [tone=nonsense>high]")


class TestWhatIsReportedInsteadOfDropped:
    """The truncation must not survive in any form."""

    def test_a_second_mark_for_a_single_valued_feature_warns(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            got = units("aːˑ", FEATURES)[0].prosody
        assert got == {"length": "long"}
        messages = [str(w.message) for w in caught if "single-valued" in str(w.message)]
        assert len(messages) == 1
        assert "'long'" in messages[0] and "'half-long'" in messages[0]

    def test_a_written_shape_contradicting_the_written_levels_warns(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            got = units("â˩˥", FEATURES)[0].prosody
        assert got["contour"] == "falling", "the assertion stands"
        assert got["tone"] == "bottom>top"
        messages = [
            str(w.message) for w in caught if "levels written on it" in str(w.message)
        ]
        assert len(messages) == 1

    def test_a_sequence_never_warns_because_nothing_is_dropped(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            units("a˥˦˧˨˩", FEATURES)
        assert [str(w.message) for w in caught] == []


class TestTheWrongValueCouldNotReachTheMetric:
    """Why no sweep found this, pinned as the reason.

    Prosody sits on the unit rather than in the feature bag, so a wrong
    contour is invisible to `features`, to `distance` and to the shipped
    matrix. It is also why fixing it moves none of them.
    """

    def test_tone_and_contour_are_prosodic(self) -> None:
        assert {"tone", "contour"} <= set(FEATURES.features_by_mode["prosodic"])

    @pytest.mark.parametrize("mark", sorted(set(UNICODE_SERIES) | set(ABBREVIATIONS)))
    def test_the_feature_bag_never_carries_it(self, mark: str) -> None:
        assert ipakit.features("a") == ipakit.features(f"a{mark}")
        assert "contour" not in ipakit.features(f"a{mark}")
        assert "tone" not in ipakit.features(f"a{mark}")

    def test_the_distance_is_zero_either_way(self) -> None:
        assert ipakit.distance("a", "a᷅") == 0.0
        assert ipakit.distance("a᷄", "a᷅") == 0.0
        assert ipakit.distance("a᷈", "a᷉") == 0.0

    def test_the_description_never_said_it(self) -> None:
        # `contour` declares no labels, so no description reads it out.
        assert not FEATURES.features["contour"].labels
        assert ipakit.describe("a᷅") == ipakit.describe("a")


class TestWhichMarksAreDeclared:
    """Coverage, pinned so it stays known rather than assumed shut."""

    def test_all_eight_tone_diacritics_are_declared(self) -> None:
        wanted = set(UNICODE_SERIES) | set(ABBREVIATIONS)
        assert {m for m in wanted if m in FEATURES.diacritics} == wanted

    def test_the_shape_scale_names_the_three_things_a_step_can_do(self) -> None:
        assert FEATURES.features["contour"].values == ["falling", "steady", "rising"]
        assert FEATURES.features["contour"].over == "tone"

    def test_the_level_tier_is_the_gap_that_remains(self) -> None:
        """The chart's extra-high `̋` U+030B and extra-low `̏` U+030F are
        not declared, so `top` and `bottom` are reachable only through the
        tone letters. Separate from contours, and pinned here because this
        is where a reader looks for it."""
        for mark in ("̋", "̏"):
            assert mark not in FEATURES.diacritics
            codes = {i["code"] for i in FEATURES.validate_ipa(f"a{mark}")}
            assert "unknown_symbol" in codes, mark
        for level, letter in (("top", "˥"), ("bottom", "˩")):
            found = FEATURES.declaring_mark("tone", level)
            assert found is not None and found[1] == letter


class TestAContourSpelledAcrossMarksIsWithheldNotTruncated:
    """One contour has two spellings, and they used to disagree.

    ``a᷅`` packs the trajectory into one mark declaring ``tone="low>mid"``,
    and the metric withholds it: a sequence is a trajectory rather than a
    point, so ``value_distance`` has no honest answer and the rider is
    excluded by construction. That is stated in ``metric.py`` and it is
    right.

    ``a˩˥`` spells the same contour as two Chao letters, each declaring
    one level. The rider map is keyed by feature, so the second mark
    overwrote the first and the unit rode as its FINAL level alone. The
    consequence was a silent wrong answer rather than a withheld one:
    ``a˩˥`` and ``a˧˥`` are different tones and scored 0 against each
    other, while ``a˩˥`` against ``a˩˧`` scored, because there only the
    endpoint differed. Which pairs the truncation happened to separate
    was an accident of where the contours ended.

    A feature claimed by more than one mark is a sequence spelled the long
    way, so it is withheld the same way. The two spellings now agree, and
    the honest limitation replaces the quiet one.
    """

    def test_two_contours_sharing_an_endpoint_are_not_called_identical(self):
        """The case that was wrong: these differ, and the truncation could
        not see it because it kept only the last level."""
        assert ipakit.distance("a˩˥", "a˧˥") == 0.0
        assert ipakit.distance("a˩˥", "a˩˧") == 0.0
        assert ipakit.distance("a˩˥", "a˥˩") == 0.0

    def test_it_withholds_rather_than_scoring_from_a_fragment(self):
        """Withheld, not scored: a contour contributes no tone term at
        all, the same as the packed spelling. Both are 0 against a bare
        vowel because neither rides."""
        assert ipakit.distance("a", "a˩˥") == 0.0
        assert ipakit.distance("a", "a᷅") == 0.0

    def test_a_single_level_still_rides(self):
        """The narrowing is only for sequences. One mark declaring one
        level is a point on the scale and still scores, so this does not
        quietly switch tone off."""
        assert ipakit.distance("a", "a˥") > 0.0
        assert ipakit.distance("a˥", "a˩") > ipakit.distance("a˥", "a˧")

    def test_no_registered_phone_can_reach_this_path(self):
        """Why the shipped matrix is untouched, stated as the reason
        rather than as the outcome.

        The rider path only narrows where one unit carries two marks
        declaring the same prosodic feature. No phone in the inventory
        carries a prosodic mark at all, so nothing in `confusion.json`
        can reach it -- which is what makes this change safe for a
        shipped artifact, and is checkable here rather than only in the
        derived-artifact guard.
        """
        for phone in FEATURES.phones:
            segment = ipakit.segments(phone, strict=True)[0]
            assert not segment.prosody, (phone, segment.prosody)
