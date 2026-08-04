"""Scoring pre-tokenized phone sequences, n-best, and a local fit mode.

``word_distance`` tokenizes a string and may join or split units; the sequence
methods take phone-token lists and align them as given. ``mode="local"`` fits
one sequence as a target embedded in another. No lexicon is involved -- the
candidates are the sequences the caller supplies.
"""

import ipakit
import pytest
from ipakit.distance import PronunciationMatch, SequenceMatch


@pytest.fixture(scope="module")
def ipa() -> ipakit.IPAFeatures:
    return ipakit.IPAFeatures()


class TestPreTokenizedIsAlignedAsGiven:
    def test_identical_sequences_score_one(self, ipa):
        assert ipa.sequence_similarity(["k", "æ", "t"], ["k", "æ", "t"]) == 1.0

    def test_two_units_are_not_merged_into_an_affricate(self, ipa):
        # a string "tʃ" would tokenize to the affricate; the token list ["t","ʃ"]
        # stays two units, so it is not identical to the one-unit affricate.
        assert ipa.sequence_similarity(["t", "ʃ"], ["t͡ʃ"]) < 1.0

    def test_it_agrees_with_word_distance_on_the_same_tokens(self, ipa):
        toks1 = [t for t in ipa.tokenize("kæt") if not ipa.is_structural_token(t)]
        toks2 = [t for t in ipa.tokenize("kæd") if not ipa.is_structural_token(t)]
        assert ipa.sequence_similarity(toks1, toks2) == ipa.word_similarity(
            "kæt", "kæd"
        )


class TestLocalFit:
    def test_an_embedded_target_scores_one(self, ipa):
        haystack = ["b", "ə", "b", "k", "æ", "t"]
        assert ipa.sequence_similarity(haystack, ["k", "æ", "t"], mode="local") == 1.0

    def test_global_penalizes_the_surrounding_noise(self, ipa):
        haystack = ["b", "ə", "b", "k", "æ", "t"]
        assert ipa.sequence_similarity(haystack, ["k", "æ", "t"], mode="global") < 1.0

    def test_a_truncated_target_is_still_penalized(self, ipa):
        # the needle (second arg) must align fully; a missing needle phone costs.
        assert ipa.sequence_similarity(["k", "æ"], ["k", "æ", "t"], mode="local") < 1.0

    def test_similarity_is_in_range(self, ipa):
        s = ipa.sequence_similarity(["k", "æ", "t"], ["d", "ɒ", "ɡ"], mode="local")
        assert 0.0 <= s <= 1.0


class TestNbestRanking:
    def test_rank_sequences_is_best_first(self, ipa):
        ranked = ipa.rank_sequences(
            ["k", "æ", "t"], [["k", "ʊ", "t"], ["k", "æ", "t"], ["d", "ɒ", "ɡ"]]
        )
        assert ranked[0].candidate == ("k", "æ", "t")
        assert ranked[0].similarity == 1.0
        assert [m.similarity for m in ranked] == sorted(
            (m.similarity for m in ranked), reverse=True
        )

    def test_n_truncates(self, ipa):
        ranked = ipa.rank_sequences(
            ["k", "æ", "t"], [["k", "æ", "t"], ["k", "ʊ", "t"], ["d", "ɒ", "ɡ"]], n=2
        )
        assert len(ranked) == 2

    def test_a_tie_keeps_the_earliest(self, ipa):
        # inserting the same phone before or after the observed costs the same,
        # so these two candidates tie; the earliest-listed wins.
        a, b = ["a", "p"], ["p", "a"]
        assert ipa.sequence_similarity(["a"], a) == ipa.sequence_similarity(["a"], b)
        ranked = ipa.rank_sequences(["a"], [a, b])
        assert ranked[0].candidate == tuple(a)

    def test_empty_candidates_raise(self, ipa):
        with pytest.raises(ValueError, match="at least one"):
            ipa.rank_sequences(["k", "æ", "t"], [])

    def test_rank_pronunciations_and_nearest_agree(self, ipa):
        acc = ["ˈɹɛkɚd", "ɹɪˈkɔɹd"]
        ranked = ipa.rank_pronunciations("ɹɪˈkɔɹd", acc)
        nearest = ipa.nearest_pronunciation("ɹɪˈkɔɹd", acc)
        assert isinstance(ranked[0], PronunciationMatch)
        assert ranked[0].accepted == nearest.accepted == "ɹɪˈkɔɹd"


class TestModelIsGammaAware:
    def test_gamma_changes_the_sequence_similarity(self, ipa):
        a, b = ["k", "æ", "t"], ["d", "ɒ", "ɡ"]
        s1 = ipakit.distance_model(gamma=1.0).sequence_similarity(a, b)
        s2 = ipakit.distance_model(gamma=4.0).sequence_similarity(a, b)
        assert s1 != s2

    def test_model_local_finds_an_embedded_target(self, ipa):
        m = ipakit.distance_model(gamma=2.0)
        assert (
            m.sequence_similarity(["x", "k", "æ", "t"], ["k", "æ", "t"], mode="local")
            == 1.0
        )


class TestExports:
    def test_symbols_are_exported(self):
        assert ipakit.SequenceMatch is SequenceMatch
        for name in (
            "sequence_distance",
            "sequence_similarity",
            "rank_sequences",
            "rank_pronunciations",
        ):
            assert callable(getattr(ipakit, name))

    def test_sequence_match_carries_the_pair(self, ipa):
        m = ipa.rank_sequences(["k", "æ", "t"], [["k", "æ", "d"]])[0]
        assert m.observed == ("k", "æ", "t")
        assert m.candidate == ("k", "æ", "d")
        assert m.result.similarity == m.similarity
