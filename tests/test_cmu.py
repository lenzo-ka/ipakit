"""Tests for CMU ARPABET mapping."""

import pytest
from ipakit import CMUMapper


class TestIPAtoCMU:
    """Tests for IPA to CMU conversion."""

    @pytest.fixture
    def mapper(self) -> CMUMapper:
        return CMUMapper()

    def test_consonants(self, mapper: CMUMapper) -> None:
        assert mapper.ipa_to_cmu("p", with_stress=False) == ["P"]
        assert mapper.ipa_to_cmu("t", with_stress=False) == ["T"]
        assert mapper.ipa_to_cmu("k", with_stress=False) == ["K"]
        assert mapper.ipa_to_cmu("s", with_stress=False) == ["S"]

    def test_vowels_no_stress(self, mapper: CMUMapper) -> None:
        result = mapper.ipa_to_cmu("i", with_stress=False)
        assert result == ["IY"]

    def test_vowels_with_stress(self, mapper: CMUMapper) -> None:
        result = mapper.ipa_to_cmu("i", with_stress=True)
        assert result == ["IY0"]

    def test_primary_stress(self, mapper: CMUMapper) -> None:
        result = mapper.ipa_to_cmu("ˈi", with_stress=True)
        assert result == ["IY1"]

    def test_secondary_stress(self, mapper: CMUMapper) -> None:
        result = mapper.ipa_to_cmu("ˌi", with_stress=True)
        assert result == ["IY2"]

    def test_affricates(self, mapper: CMUMapper) -> None:
        assert mapper.ipa_to_cmu("t͡ʃ", with_stress=False) == ["CH"]
        assert mapper.ipa_to_cmu("d͡ʒ", with_stress=False) == ["JH"]

    def test_diphthongs(self, mapper: CMUMapper) -> None:
        result = mapper.ipa_to_cmu("a͡ɪ", with_stress=True)
        assert result == ["AY0"]


class TestCMUtoIPA:
    """Tests for CMU to IPA conversion."""

    @pytest.fixture
    def mapper(self) -> CMUMapper:
        return CMUMapper()

    def test_consonants(self, mapper: CMUMapper) -> None:
        assert mapper.cmu_to_ipa(["P"]) == "p"
        assert mapper.cmu_to_ipa(["T"]) == "t"
        assert mapper.cmu_to_ipa(["S"]) == "s"

    def test_vowels_unstressed(self, mapper: CMUMapper) -> None:
        assert mapper.cmu_to_ipa(["IY0"]) == "i"

    def test_vowels_primary_stress(self, mapper: CMUMapper) -> None:
        assert mapper.cmu_to_ipa(["IY1"]) == "ˈi"

    def test_vowels_secondary_stress(self, mapper: CMUMapper) -> None:
        assert mapper.cmu_to_ipa(["IY2"]) == "ˌi"

    def test_word(self, mapper: CMUMapper) -> None:
        # "hello" roughly
        result = mapper.cmu_to_ipa(["HH", "EH1", "L", "OW0"])
        assert "ˈ" in result  # has primary stress
        assert "ɛ" in result  # EH vowel
        assert "l" in result


class TestRoundTrip:
    """Tests for IPA <-> CMU round trips."""

    @pytest.fixture
    def mapper(self) -> CMUMapper:
        return CMUMapper()

    def test_consonants_round_trip(self, mapper: CMUMapper) -> None:
        consonants = ["p", "t", "k", "b", "d", "s", "z", "m", "n", "l"]
        for ipa_in in consonants:
            cmu = mapper.ipa_to_cmu(ipa_in, with_stress=False)
            ipa_out = mapper.cmu_to_ipa(cmu)
            assert ipa_out == ipa_in, f"Round trip failed for {ipa_in}"
