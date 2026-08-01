"""A boundary run that asserts a constituent nobody keeps.

``'kæt..dɒɡ'`` was accepted in silence by every layer that read it, and
the layers did not agree about what it meant. The rule engine's insertion
scan treats the gap between the two dots as a real syllable and gives it
an epenthetic vowel of its own; ``Form.tree()`` discards the empty group
and reports two syllables, the same tree ``'kæt.dɒɡ'`` gets. Neither said
a word, so a caller could not find out which reading they had.

``validate_ipa`` now says it, as a **warning**: the license is
docs/ties.md's "unknown characters are dropped audibly, never silently",
not a claim that the input is malformed. The reasoning is argued in
``validate_ipa``'s docstring; these tests pin the two measurements the
argument rests on, and the exact set of inputs it reaches.
"""

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.form import Form, units
from ipakit.models import Phone


def codes(ipa: IPAFeatures, text: str) -> list[str]:
    return [issue["code"] for issue in ipa.validate_ipa(text)]


#: One corpus for both directions of the claim -- everything degenerate
#: and everything that merely looks it. Kept together so a change to the
#: check has to restate the whole partition rather than add a case.
FORMS = (
    "kæt",
    "kæt.",
    "kæt..",
    "kæt...",
    "kæt.#",
    "#kæt#",
    "##kæt",
    "kæt##",
    "kæt.dɒɡ",
    "kæt..dɒɡ",
    "kæt#dɒɡ",
    "kæt dɒɡ",
    "kæt  dɒɡ",
    "kæt. .dɒɡ",
    "#.kæt",
    "hɛ.loʊ",
    "kæt.ˈ.dɒɡ",
    "kæt.|.dɒɡ",
    "#kæt# #dɒɡ#",
)

#: The members of FORMS that assert a constituent no reader keeps.
EMPTY = frozenset(
    {
        "kæt..",
        "kæt...",
        "##kæt",
        "kæt##",
        "kæt..dɒɡ",
        "kæt  dɒɡ",
        "kæt.ˈ.dɒɡ",
        "kæt.|.dɒɡ",
        "#kæt# #dɒɡ#",
    }
)


class TestTheTwoLayersReallyDoDisagree:
    """The argument for warning is a measurement, not a preference, so it
    is worth a test of its own: if either layer changes its reading the
    docstring's reasoning has moved and must be rewritten."""

    def test_the_rule_engine_gives_the_empty_syllable_its_own_vowel(self) -> None:
        # Three insertion sites in 'kæt..dɒɡ' against two in 'kæt.dɒɡ':
        # the extra one is the empty syllable, a real constituent here.
        assert ipakit.rewrite("kæt.dɒɡ", "∅ -> ə / . _") == "əkæt.ədɒɡ"
        assert ipakit.rewrite("kæt..dɒɡ", "∅ -> ə / . _") == "əkæt..ədɒɡ"

    def test_the_tree_discards_it_without_a_word(self) -> None:
        doubled = Form.parse("kæt..dɒɡ").tree()
        single = Form.parse("kæt.dɒɡ").tree()
        assert [n.to_ipa() for n in doubled.at("syllable")] == ["kæt", "dɒɡ"]
        assert [n.to_ipa() for n in doubled.at("syllable")] == [
            n.to_ipa() for n in single.at("syllable")
        ]

    def test_the_word_mark_run_loses_a_word_the_same_way(self) -> None:
        assert [n.to_ipa() for n in Form.parse("##kæt").tree().at("word")] == ["kæt"]


class TestTheWarningNamesTheDiscardedConstituent:
    def test_a_doubled_break_is_reported(self, ipa: IPAFeatures) -> None:
        assert "empty_constituent" in codes(ipa, "kæt..dɒɡ")

    def test_it_is_a_warning_and_never_an_error(self, ipa: IPAFeatures) -> None:
        # The whole point of the license argument: the input is
        # interpretable, so it is reported, not rejected.
        for issue in ipa.validate_ipa("kæt..dɒɡ"):
            assert issue["type"] == "warning", issue

    def test_the_form_stays_valid(self, ipa: IPAFeatures) -> None:
        assert ipa.is_valid_ipa("kæt..dɒɡ") is True

    def test_the_message_names_the_tier_and_both_marks(self, ipa: IPAFeatures) -> None:
        (issue,) = [
            i for i in ipa.validate_ipa("kæt..dɒɡ") if i["code"] == "empty_constituent"
        ]
        assert "syllable" in issue["message"]
        assert issue["position"] == "4"
        assert issue["symbol"] == "."

    def test_a_word_level_run_names_the_word_tier(self, ipa: IPAFeatures) -> None:
        (issue,) = [
            i for i in ipa.validate_ipa("##kæt") if i["code"] == "empty_constituent"
        ]
        assert "word" in issue["message"]

    def test_one_report_per_discarded_constituent(self, ipa: IPAFeatures) -> None:
        # Three dots delimit two empty syllables, not one run.
        assert codes(ipa, "kæt...dɒɡ").count("empty_constituent") == 2

    def test_nothing_is_repaired(self, ipa: IPAFeatures) -> None:
        # A repair would be a normalization on the ingest path, and the
        # byte-faithful round trip is what Form exists for. Reporting must
        # leave every flagged form spelling itself back out.
        checked = 0
        for text in sorted(EMPTY - {"kæt.ˈ.dɒɡ"}):  # see the next class
            ipa.validate_ipa(text)
            assert Form.parse(text).to_ipa() == text, text
            checked += 1
        assert checked >= 8, "the round-trip sweep did not run"


class TestAStressMarkBeforeASeparatorIsADifferentDisagreementAgain:
    """Found while pinning the round trip, pre-existing at c8d742e, and not
    fixed here: ``form.py`` belongs to another lane.

    ``validate_ipa`` and ``segments`` both read the stress mark in
    ``'kæt.ˈ.dɒɡ'`` as binding ``d`` -- separators are transparent to
    stress binding -- and ``segments`` puts it in ``d``'s prosody.
    ``Form.parse`` flushes its buffer at the separator, so it hands
    ``segments`` the bare mark, calls it unbound, warns, and **drops it**.
    The form then does not spell itself back out, which is the one thing
    ``Form`` advertises. Same defect class as this file's subject: two
    layers, two readings, and the loud one is the one that is wrong.
    """

    def test_the_segmental_layer_binds_it(self, ipa: IPAFeatures) -> None:
        stressed = [s for s in ipa.segments("kæt.ˈ.dɒɡ") if s.prosody]
        assert [(s.constituents[0].base, s.prosody) for s in stressed] == [
            ("d", ("ˈ",))
        ]

    def test_the_validator_agrees_it_binds(self, ipa: IPAFeatures) -> None:
        assert "unbound_stress" not in codes(ipa, "kæt.ˈ.dɒɡ")

    @pytest.mark.parametrize("form", ["kæt.ˈ.dɒɡ", "kæt.ˈ dɒɡ", "kæt.ˈ#dɒɡ"])
    def test_the_form_layer_still_drops_it(self, form: str) -> None:
        # When form.py stops disagreeing, this fails -- and the exclusion
        # in test_nothing_is_repaired above can come out.
        with pytest.warns(UserWarning, match="unbound stress mark"):
            assert Form.parse(form).to_ipa() != form


class TestTheFlaggedSetIsExactlyThis:
    """A count would pass while the check quietly stopped covering a
    shape. The set is the assertion."""

    def test_the_partition(self, ipa: IPAFeatures) -> None:
        flagged = {f for f in FORMS if "empty_constituent" in codes(ipa, f)}
        assert flagged == set(EMPTY)

    def test_the_corpus_covers_both_sides(self) -> None:
        # A guard over a corpus that drifted to one side of the line
        # tests nothing. Both halves must stay populated.
        assert len(EMPTY) >= 5
        assert len(set(FORMS) - EMPTY) >= 5


class TestTheBoundaryVocabularyComesFromTheData:
    """Phonetic facts live in ipa.xml, not in Python constants
    (tests/test_declared_not_hardcoded.py). Which characters delimit a
    constituent, and at which tier, is such a fact.

    A test that only listed today's separators would document the present.
    These declare a *new* separator at a *new* tier on a private inventory
    and assert the check picks it up with no change to the code -- which is
    what says the vocabulary is derived rather than enumerated, and what
    says a lane adding a tier above ``word`` will not break it.
    """

    @staticmethod
    def _with_a_third_tier() -> IPAFeatures:
        # A private instance: the session fixture is shared and read-only.
        features = IPAFeatures()
        features.separators["%"] = Phone(
            symbol="%", features={"level": "phrase", "class": "separator"}
        )
        return features

    def test_a_newly_declared_separator_is_seen(self) -> None:
        features = self._with_a_third_tier()
        (issue,) = [
            i
            for i in features.validate_ipa("kæt%%dɒɡ")
            if i["code"] == "empty_constituent"
        ]
        # The declared level names the tier, so the message does too.
        assert "phrase" in issue["message"]

    def test_the_new_tier_is_compared_by_declaration_not_by_rank(self) -> None:
        # Nothing here counts the tiers or orders them: two boundaries are
        # same-level when their declared levels are equal. So a third tier
        # neither flags against the other two nor breaks them.
        features = self._with_a_third_tier()
        for form in ("kæt%.dɒɡ", "kæt%#dɒɡ", "kæt%dɒɡ", "kæt.%dɒɡ"):
            assert codes(features, form) == [], form
        assert "empty_constituent" in codes(features, "kæt..dɒɡ")

    def test_every_declared_separator_participates(self, ipa: IPAFeatures) -> None:
        # A predicate over the whole declared set rather than a spot check
        # on '.' and '#': doubling any declared separator is degenerate.
        checked = 0
        for symbol in ipa.separators:
            assert "empty_constituent" in codes(ipa, f"kæt{symbol}{symbol}dɒɡ"), symbol
            checked += 1
        assert checked == len(ipa.separators) >= 2, "the sweep did not run"

    def test_whitespace_is_the_declared_word_edge_form_units_says_it_is(
        self, ipa: IPAFeatures
    ) -> None:
        # The space is the one boundary ipa.xml does not declare, so
        # validate_ipa asks form.units for its tier instead of restating
        # it. This is what says the two layers cannot drift apart: if
        # form.units stops calling a space a word edge, this fails.
        (space,) = units(" ", ipa)
        assert space.is_boundary and space.level == "word"
        (issue,) = [
            i for i in ipa.validate_ipa("kæt  dɒɡ") if i["code"] == "empty_constituent"
        ]
        assert space.level in issue["message"]

    def test_a_space_beside_a_hash_is_the_same_tier_twice(
        self, ipa: IPAFeatures
    ) -> None:
        # Consequence of the line above, and the most debatable member of
        # the flagged set: '#kæt# #dɒɡ#' writes the word edge twice at one
        # juncture, so it asserts two empty words -- and both layers agree
        # it does, which is why it is reported rather than excused.
        assert codes(ipa, "#kæt# #dɒɡ#").count("empty_constituent") == 2
        assert ipakit.rewrite("#kæt# #dɒɡ#", "∅ -> ə / % _") == "#əkæt# #ədɒɡ#"
        assert [n.to_ipa() for n in Form.parse("#kæt# #dɒɡ#").tree().at("word")] == [
            "kæt",
            "dɒɡ",
        ]


class TestWhatTheCheckDeliberatelyDoesNotSee:
    """If one of these starts being flagged, this fails and the documented
    limits in ``validate_ipa`` need updating. Coverage can then only change
    deliberately, in either direction."""

    @pytest.mark.parametrize("form", ["kæt.", "#kæt#", "kæt#", "#kæt", "kæt "])
    def test_a_single_mark_against_a_form_edge_is_canonical(
        self, ipa: IPAFeatures, form: str
    ) -> None:
        # The edge already delimits the outermost tier, so the mark
        # asserts no constituent beyond what the edge gives.
        assert codes(ipa, form) == []

    @pytest.mark.parametrize("form", ["kæt.#", "#.kæt", "kæt. .dɒɡ", "kæt .dɒɡ"])
    def test_a_weaker_mark_beside_a_stronger_one_is_not_degenerate(
        self, ipa: IPAFeatures, form: str
    ) -> None:
        # Only a *same-level* pair is flagged. That spares 'kæt.#' -- a
        # syllable break subsumed by a word edge -- and by the same rule
        # it makes the check blind to '#.kæt'. Blind, and known to be.
        assert codes(ipa, form) == []

    def test_a_tab_is_not_read_as_a_word_boundary_here(self, ipa: IPAFeatures) -> None:
        # ``Form.parse`` treats every whitespace character as a word-level
        # edge; ``validate_ipa``'s standalone set contains only ' ', so a
        # tab is an unknown symbol and no run of tabs can be seen as
        # degenerate. The two layers disagree about tabs, which is a
        # finding this lane did not fix.
        assert codes(ipa, "kæt\t\tdɒɡ") == ["unknown_symbol", "unknown_symbol"]

    def test_the_check_cannot_see_across_an_unknown_symbol_either_way(
        self, ipa: IPAFeatures
    ) -> None:
        # Only a matched phone clears the pending boundary, so junk
        # between two dots does not hide the empty syllable -- and the
        # unknown symbol is still reported in its own right.
        assert codes(ipa, ".@.") == [
            "unknown_symbol",
            "empty_constituent",
            "no_segments",
        ]


class TestAFormThatNamesNoSoundSaysSo:
    @pytest.mark.parametrize("form", [".", "#", " ", "..", "ː", "˥", "|"])
    def test_marks_alone_are_reported(self, ipa: IPAFeatures, form: str) -> None:
        assert "no_segments" in codes(ipa, form)

    def test_it_is_a_warning(self, ipa: IPAFeatures) -> None:
        (issue,) = [i for i in ipa.validate_ipa(".") if i["code"] == "no_segments"]
        assert issue["type"] == "warning"
        assert issue["position"] == "0"

    def test_the_empty_string_asserted_nothing_and_is_not_reported(
        self, ipa: IPAFeatures
    ) -> None:
        # Nothing was discarded, so there is nothing to be audible about.
        assert ipa.validate_ipa("") == []

    def test_junk_alone_is_not_reported_twice(self, ipa: IPAFeatures) -> None:
        # ``unknown_symbol`` has already said what was lost, and an
        # unknown character is not an asserted constituent.
        assert codes(ipa, "@") == ["unknown_symbol"]

    def test_a_lone_tie_is_left_to_malformed_tie(self, ipa: IPAFeatures) -> None:
        # The tie branch already reports the loss on its own terms.
        assert codes(ipa, "͡") == ["malformed_tie"]

    def test_a_form_with_one_segment_is_not_reported(self, ipa: IPAFeatures) -> None:
        assert codes(ipa, "#a#") == []

    def test_both_codes_can_hold_at_once(self, ipa: IPAFeatures) -> None:
        # '..' asserts an empty syllable *and* names no sound. Two
        # different statements, both true.
        assert codes(ipa, "..") == ["empty_constituent", "no_segments"]


class TestTheRewriteRegressionGuardIsUntouched:
    """``tests/test_rules.py`` pins that a dot beside a word edge does not
    block the edge, over exactly these four forms. A check that fired as an
    error, or repaired, would break a guard that catches a real defect."""

    @pytest.mark.parametrize("form", ["kæt", "kæt.", "kæt..", "kæt.#"])
    def test_all_four_still_rewrite(self, ipa: IPAFeatures, form: str) -> None:
        assert ipakit.rewrite(form, "t -> ʔ / _ #") == form.replace("t", "ʔ")

    @pytest.mark.parametrize("form", ["kæt", "kæt.", "kæt..", "kæt.#"])
    def test_none_of_the_four_is_an_error(self, ipa: IPAFeatures, form: str) -> None:
        assert ipa.is_valid_ipa(form) is True
        errors = [i for i in ipa.validate_ipa(form) if i["type"] == "error"]
        assert errors == [], form
