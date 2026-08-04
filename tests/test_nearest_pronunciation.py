"""Scoring against a set of acceptable pronunciations, not one (#167).

Every real lexicon lists several transcriptions per word -- free variants
(``iːðɚ``/``aɪðɚ``, optional schwa deletion), or a homograph read two ways
(``record`` the noun and the verb, ``wind`` the breeze and the turn). CMUdict
ships them per orthographic entry. The helper takes the best match over the
set and says which member won; it is the acceptability question, and must not
be reached for word-to-word distance.
"""

import ipakit
import pytest
from ipakit.distance import PronunciationMatch


class TestItTakesTheBestMatchNotTheFirst:
    def test_an_exact_member_wins_from_any_position(self) -> None:
        # the matching variant is listed second, yet it wins
        m = ipakit.nearest_pronunciation("waɪnd", ["wɪnd", "waɪnd"])
        assert m.accepted == "waɪnd"
        assert m.similarity == 1.0

    def test_the_other_reading_wins_for_the_other_form(self) -> None:
        m = ipakit.nearest_pronunciation("wɪnd", ["wɪnd", "waɪnd"])
        assert m.accepted == "wɪnd"
        assert m.similarity == 1.0

    def test_it_reports_which_homograph_reading_matched(self) -> None:
        acceptable = ["ˈɹɛkɚd", "ɹɪˈkɔɹd"]  # record: noun, verb
        noun = ipakit.nearest_pronunciation("ˈɹɛkɚd", acceptable)
        verb = ipakit.nearest_pronunciation("ɹɪˈkɔɹd", acceptable)
        assert noun.accepted == "ˈɹɛkɚd"
        assert verb.accepted == "ɹɪˈkɔɹd"
        assert noun.accepted != verb.accepted  # the set told them apart


class TestTheShapeOfTheResult:
    def test_it_carries_the_winning_pair_and_full_result(self) -> None:
        m = ipakit.nearest_pronunciation("fæmli", ["fæməli", "fæmli"])
        assert isinstance(m, PronunciationMatch)
        assert m.form == "fæmli"
        assert m.accepted == "fæmli"
        assert m.result.similarity == m.similarity

    def test_a_worse_match_scores_below_one(self) -> None:
        m = ipakit.nearest_pronunciation("kæt", ["dɒɡ", "kæd"])
        assert m.accepted == "kæd"  # nearer of the two
        assert m.similarity < 1.0


class TestBothSidesMayBeSets:
    def test_the_observed_form_may_have_variants_too(self) -> None:
        # a caller with variants on each side: max over the cross product
        m = ipakit.nearest_pronunciation(["ˈaɪðɚ", "ˈiːðɚ"], ["ˈiːðɚ", "ˈaɪðɚ"])
        assert m.similarity == 1.0  # some pair matches exactly

    def test_a_single_string_acceptable_is_accepted(self) -> None:
        m = ipakit.nearest_pronunciation("kæt", "kæt")
        assert m.similarity == 1.0


class TestDeterminismAndRefusal:
    def test_a_tie_keeps_the_earliest_listed(self) -> None:
        # "a" vs "ab" and "a" vs "ba" are both one insertion of the same
        # phone, so they tie; the earliest listed wins, deterministically.
        assert ipakit.word_similarity("a", "ab") == ipakit.word_similarity("a", "ba")
        m = ipakit.nearest_pronunciation("a", ["ab", "ba"])
        assert m.accepted == "ab"

    def test_an_empty_set_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            ipakit.nearest_pronunciation("kæt", [])
        with pytest.raises(ValueError, match="at least one"):
            ipakit.nearest_pronunciation([], ["kæt"])

    def test_it_is_exported(self) -> None:
        assert ipakit.PronunciationMatch is PronunciationMatch
        assert callable(ipakit.nearest_pronunciation)


class TestGroundedInCmudictVariants:
    """The motivating case: CMUdict lists several pronunciations per entry.

    No lexicon ships in the repo, so a few known entries stand in for the
    caller's lexicon -- the point is that the set is what a real lexicon
    hands you, not a citation form chosen by hand.
    """

    LEXICON = {
        "either": ["ˈiːðɚ", "ˈaɪðɚ"],
        "tomato": ["təˈmeɪtoʊ", "təˈmɑːtoʊ"],
        "data": ["ˈdeɪtə", "ˈdætə"],
    }

    def test_a_regional_form_finds_its_acceptable_variant(self) -> None:
        for _word, variants in self.LEXICON.items():
            for said in variants:
                m = ipakit.nearest_pronunciation(said, variants)
                assert m.similarity == 1.0
                assert m.accepted == said
