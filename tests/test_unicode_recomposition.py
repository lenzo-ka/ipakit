"""Canonical reordering must not strand a symbol's own combining mark.

`canonicalize_unicode` decomposes to NFD so the parser sees base plus
mark, then rebuilds the registered symbols that ship precomposed. Doing
that by substring replace assumed the base and its mark stay adjacent,
which canonical ordering does not guarantee.
"""

import unicodedata

import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestRecomposition:
    def test_a_reordered_mark_still_recomposes(self, ipa: IPAFeatures) -> None:
        # ç is U+00E7; the velarization overlay U+0334 has ccc 1 and the
        # cedilla ccc 202, so NFD orders the overlay first and the base
        # and its cedilla are no longer adjacent. Read naively, ç became
        # c -- a palatal fricative silently turned into a plosive.
        assert ipa.canonicalize_unicode("ç̴") == "ç" + "̴"
        assert ipa.get_features("ç̴")["manner"] == "fricative"
        assert ipa.get_features("ç̴")["place"] == "palatal"
        assert ipa.get_features("ç̴")["velarized"] == "+"

    def test_no_precomposed_symbol_is_lost_under_any_diacritic(
        self, ipa: IPAFeatures
    ) -> None:
        # The general form: whatever mark is applied, a symbol that ships
        # precomposed must survive canonicalization.
        precomposed = [s for s in ipa.phones if unicodedata.normalize("NFD", s) != s]
        assert precomposed
        for symbol in precomposed:
            for mark in ipa.diacritics:
                canonical = ipa.canonicalize_unicode(symbol + mark)
                assert symbol in canonical, (symbol, hex(ord(mark)))

    def test_canonicalization_is_idempotent(self, ipa: IPAFeatures) -> None:
        for text in ["ç̴", "ä", "ť", "ã", "t͡s", "kʷ", "ç"]:
            once = ipa.canonicalize_unicode(text)
            assert ipa.canonicalize_unicode(once) == once, text

    def test_the_levels_agree_on_precomposed_bases(self, ipa: IPAFeatures) -> None:
        # The invariant the stranding broke: one string, one answer.
        for symbol in ("ç", "ä", "ť"):
            for mark in ipa.diacritics:
                unit = symbol + mark
                try:
                    structured = ipa.segment(unit).scalar()
                except ValueError:
                    continue
                assert bool(ipa.get_features(unit)) == bool(structured), unit


class TestCombinedPlaceReadsAsItsName:
    """A combining value's canonical spelling joins components with the
    combiner. That is machine notation, and the data declares the
    conventional name as an alias for exactly this purpose."""

    def test_describe_uses_the_conventional_name(self, ipa: IPAFeatures) -> None:
        assert ipa.describe("w") == "voiced labial-velar approximant"
        assert ipa.describe("ɥ") == "voiced labial-palatal approximant"
        assert ipa.describe("k͡p") == "voiceless labial-velar plosive"

    def test_the_combiner_does_not_reach_the_reader(self, ipa: IPAFeatures) -> None:
        for symbol in ("w", "ɥ", "ʍ", "k͡p", "ɡ͡b", "ŋ͡m"):
            assert ipa.features["place"].COMBINER not in ipa.describe(symbol), symbol

    def test_ordinary_values_keep_their_canonical_spelling(
        self, ipa: IPAFeatures
    ) -> None:
        # An alias on a plain value is a synonym, not a readable form:
        # `plosive` must not print as `stop`, nor `tap` as `flap`.
        assert "plosive" in ipa.describe("p")
        assert "stop" not in ipa.describe("p")
