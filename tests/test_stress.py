"""Tests for stress normalization (syllable-initial <-> nucleus placement).

``normalize_stress_to_nucleus`` moves IPA-dict-style syllable-initial stress
(``ˈhɛ.ləʊ``) to ipakit's nucleus convention (``hˈɛ.ləʊ``);
``normalize_stress_to_syllable`` is the inverse, for output. These are
standalone normalization utilities -- the CMU mapper already resolves stress
placement on its own, so they are not part of the conversion pipeline.
"""

from __future__ import annotations

import pytest
from ipakit import IPAFeatures


@pytest.fixture
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestStressToNucleus:
    @pytest.mark.parametrize(
        "src,expected",
        [
            ("ˈhɛ.ləʊ", "hˈɛ.ləʊ"),  # stress moves onto the nucleus, break kept
            ("ˈɛ.ləʊ", "ˈɛ.ləʊ"),  # already before the nucleus (no onset)
            ("ˌɪn.təˈnæʃ", "ˌɪn.tə.nˈæʃ"),  # secondary + primary
            ("ˈkæt", "kˈæt"),  # single syllable
            ("ˈpi.tsə", "pˈi.tsə"),
        ],
    )
    def test_examples(self, ipa: IPAFeatures, src: str, expected: str) -> None:
        assert ipa.normalize_stress_to_nucleus(src) == expected

    def test_no_stress_unchanged(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_nucleus("kæt") == "kæt"
        assert ipa.normalize_stress_to_nucleus("wɔtɚ") == "wɔtɚ"


class TestStressToSyllable:
    def test_strips_breaks_by_default(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_syllable("hˈɛ.ləʊ") == "ˈhɛləʊ"
        assert ipa.normalize_stress_to_syllable("kˈæt") == "ˈkæt"

    def test_keep_syllables(self, ipa: IPAFeatures) -> None:
        assert (
            ipa.normalize_stress_to_syllable("hˈɛ.ləʊ", keep_syllables=True)
            == "ˈhɛ.ləʊ"
        )

    def test_no_stress(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_syllable("kæt") == "kæt"


class TestStressRoundTrip:
    @pytest.mark.parametrize(
        "src", ["ˈhɛ.ləʊ", "ˈɛ.ləʊ", "ˌɪn.təˈnæʃ", "ˈkæt", "ˈpi.tsə"]
    )
    def test_nucleus_then_syllable_recovers_source(
        self, ipa: IPAFeatures, src: str
    ) -> None:
        # Syllable-initial stress survives a round trip when breaks are kept.
        nucleus = ipa.normalize_stress_to_nucleus(src)
        assert ipa.normalize_stress_to_syllable(nucleus, keep_syllables=True) == src
