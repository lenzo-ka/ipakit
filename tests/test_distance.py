"""Tests for phonetic distance calculation."""

import pytest
from ipakit import IPAFeatures


class TestPhoneDistance:
    """Tests for distance between individual phones."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_distance_identical(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "p") == 0.0
        assert ipa.distance("a", "a") == 0.0

    def test_distance_voicing_pair(self, ipa: IPAFeatures) -> None:
        # p and b differ only in voicing
        d = ipa.distance("p", "b")
        assert 0 < d < 0.5

    def test_distance_different_place(self, ipa: IPAFeatures) -> None:
        # p and t differ in place
        d = ipa.distance("p", "t")
        assert 0 < d < 0.5

    def test_distance_vowel_consonant(self, ipa: IPAFeatures) -> None:
        # Vowel vs consonant should be more distant than voicing pairs
        d_vowel_cons = ipa.distance("a", "p")
        d_voicing = ipa.distance("p", "b")
        assert d_vowel_cons > d_voicing

    def test_distance_unknown(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "X") == 1.0
        assert ipa.distance("X", "X") == 1.0

    def test_distance_symmetric(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "b") == ipa.distance("b", "p")
        assert ipa.distance("s", "z") == ipa.distance("z", "s")

    def test_distance_affricates(self, ipa: IPAFeatures) -> None:
        d = ipa.distance("t͡ʃ", "d͡ʒ")
        assert 0 < d < 0.5  # differ in voicing


class TestSegmentDistance:
    """Tests for distance between segments (phones with diacritics)."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_segment_distance_simple(self, ipa: IPAFeatures) -> None:
        d = ipa.segment_distance("p", "b")
        assert 0 < d < 1.0

    def test_segment_distance_with_diacritics(self, ipa: IPAFeatures) -> None:
        d = ipa.segment_distance("pʰ", "p")
        assert 0 < d < 1.0

    def test_segment_distance_identical(self, ipa: IPAFeatures) -> None:
        assert ipa.segment_distance("pʰ", "pʰ") == 0.0


class TestPairwiseDistances:
    """Tests for pairwise distance matrix."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_pairwise_distances_shape(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)

    def test_pairwise_distances_diagonal_zero(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert matrix[0][0] == 0.0
        assert matrix[1][1] == 0.0
        assert matrix[2][2] == 0.0

    def test_pairwise_distances_symmetric(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert matrix[0][1] == matrix[1][0]
        assert matrix[0][2] == matrix[2][0]
        assert matrix[1][2] == matrix[2][1]

    def test_pairwise_distances_positive(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        # Off-diagonal should be positive
        assert matrix[0][1] > 0
        assert matrix[0][2] > 0
