"""Tests for CMU ARPABET mapping."""

from __future__ import annotations

import warnings

import ipakit
import pytest
from ipakit import CMUMapper, IPAFeatures

from tests.corpus import assert_swept, self_spelling_phones, single_mark_units


class TestIPAtoCMU:
    """Tests for IPA to CMU conversion."""

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
        result = mapper.ipa_to_cmu("a͜ɪ", with_stress=True)
        assert result == ["AY0"]


class TestCMUtoIPA:
    """Tests for CMU to IPA conversion."""

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

    def test_consonants_round_trip(self, mapper: CMUMapper) -> None:
        consonants = ["p", "t", "k", "b", "d", "s", "z", "m", "n", "l"]
        for ipa_in in consonants:
            cmu = mapper.ipa_to_cmu(ipa_in, with_stress=False)
            ipa_out = mapper.cmu_to_ipa(cmu)
            assert ipa_out == ipa_in, f"Round trip failed for {ipa_in}"


def _stressed_symbols(mapper: CMUMapper, ipa: IPAFeatures) -> list[str]:
    """Every ARPABET symbol the table can write, stress digits included.

    Converted out of the table's own IPA spellings under each declared
    stress mark, rather than listed here: a row added to ``cmu.xml``, or
    a third stress level declared in ``ipa.xml``, joins the sweep below
    without this file being edited.
    """
    return sorted(
        {
            symbol
            for spelling in mapper.get_ipa_phones()
            for mark in ("", *ipa.stress_markers)
            for symbol in mapper.ipa_to_cmu(mark + spelling)
        }
    )


class TestOneTokenizer:
    """``to_cmu`` and ``segments`` are one reading of a string.

    They were two. ``to_cmu`` walked the table's own keys longest-first,
    so an untied ``ɔɪ`` matched the row for ``OY`` where ``segments``
    reads the two vowels the string actually spells, and 31 of CMUdict's
    135,166 entries came back a phone short under ``strict=True`` with
    nothing raised. The claim now is structural rather than case by case:
    a conversion is one lookup per segment, and the segments are the
    tokenizer's answer.
    """

    def test_every_row_of_the_table_spells_exactly_one_unit(
        self, ipa: IPAFeatures, mapper: CMUMapper
    ) -> None:
        """The premise the design rests on: ARPABET is a phone set.

        A row spelling two units could never be matched by a per-segment
        lookup, so it would be dead data -- and one spelling none would
        be a row that silently never fires.
        """
        rows = [*mapper.get_ipa_phones(), *mapper.get_ipa_phones(include_extras=True)]
        for spelling in rows:
            assert len(ipa.segments(spelling)) == 1, spelling
        assert len(rows) > 50, "the CMU table collapsed; this sweep is vacuous"

    def test_a_unit_never_becomes_two_arpabet_phones(self, ipa: IPAFeatures) -> None:
        """One segment in, at most one symbol out, over the whole sweep
        corpus: the property that makes the two readings comparable at
        all. At most, because ARPABET spells 39 phones and the inventory
        spells thousands."""
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # most units have no ARPABET symbol
            for unit in single_mark_units():
                assert len(ipakit.to_cmu(unit, with_stress=False)) <= 1, unit
                checked += 1
        assert_swept(checked)

    def test_a_word_converts_to_one_symbol_per_convertible_segment(
        self, ipa: IPAFeatures
    ) -> None:
        """And the count holds over a string of them, which is where the
        old walk went wrong: it merged across a segment boundary the
        tokenizer had already drawn."""
        phones = [p for p in self_spelling_phones() if ipakit.to_cmu(p)]
        checked = 0
        for left in phones:
            for right in phones:
                word = left + right
                assert len(ipakit.to_cmu(word, with_stress=False)) == len(
                    ipa.segments(word)
                ), word
                checked += 1
        assert checked > 1000, f"sweep covered only {checked} pairs"

    def test_every_arpabet_pair_round_trips(
        self, ipa: IPAFeatures, mapper: CMUMapper
    ) -> None:
        """``to_cmu(from_cmu(x)) == x`` over every ordered pair of symbols.

        Pairs rather than singletons because every failure was a *merge*:
        ``from_cmu`` writes adjacent phones with no boundary marker, so
        the two-phone sequences are exactly where a reader that invents a
        boundary shows itself. Five ordered pairs failed before this lane
        -- ``AO0 IH0``, ``AO1 IH0``, ``AO2 IH0`` (to ``OY``), ``T SH``
        (to ``CH``) and ``D ZH`` (to ``JH``); the first four account for
        all 31 CMUdict entries, and ``D ZH`` never occurs in the lexicon.
        """
        symbols = _stressed_symbols(mapper, ipa)
        checked = 0
        for left in symbols:
            for right in symbols:
                pair = [left, right]
                assert mapper.ipa_to_cmu(mapper.cmu_to_ipa(pair)) == pair
                checked += 1
        assert checked > 4000, f"sweep covered only {checked} pairs"

    def test_the_tie_is_what_makes_two_vowels_one_segment(self) -> None:
        """The reported entry, both ways round."""
        assert ipakit.to_cmu("nˈɔɪŋ", strict=True) == ["N", "AO1", "IH0", "NG"]
        assert ipakit.to_cmu("nˈɔ͜ɪŋ", strict=True) == ["N", "OY1", "NG"]
        assert ipakit.from_cmu(["N", "AO1", "IH0", "NG"]) == "nˈɔɪŋ"
        assert ipakit.from_cmu(["N", "OY1", "NG"]) == "nˈɔ͜ɪŋ"


class TestEitherTieGlyph:
    """ARPABET has one ``CH``, so it cannot say which tie was written.

    The table was keyed on one glyph per category and refused the other,
    in opposite directions -- ``cmu.xml`` spells its affricates with the
    over-tie and its diphthongs with the under-tie, so ``t͜ʃ`` and ``e͡ɪ``
    both raised while their variants converted. The rejected diphthong
    spelling is what a TTS front end set to its safest output emits.
    """

    @pytest.mark.parametrize("glyph", ["͡", "͜"])
    def test_every_tied_row_converts_under_either_glyph(
        self, ipa: IPAFeatures, mapper: CMUMapper, glyph: str
    ) -> None:
        tied = [p for p in mapper.get_ipa_phones() if ipa.tie_bars & set(p)]
        for spelling in tied:
            variant = "".join(glyph if ch in ipa.tie_bars else ch for ch in spelling)
            assert mapper.ipa_to_cmu(variant, strict=True) == mapper.ipa_to_cmu(
                spelling, strict=True
            ), variant
        assert len(tied) >= 7, f"only {len(tied)} tied rows; sweep is thin"

    def test_the_two_glyphs_are_still_two_units_to_the_tokenizer(
        self, ipa: IPAFeatures
    ) -> None:
        """What the mapper reads through is not a normalization of the
        input: the sense distinction the glyphs carry is intact, and
        only the *target* is blind to it."""
        assert ipa.segment("t͡ʃ") != ipa.segment("t͜ʃ")
        assert ipa.segment("t͡ʃ").to_ipa() == "t͡ʃ"


class TestMapperIntrospection:
    """Tests for the mapper's validation and inventory-listing methods."""

    def test_validate_ipa_for_cmu_ok(self, mapper: CMUMapper) -> None:
        assert mapper.validate_ipa_for_cmu("kæt") == []

    def test_validate_ipa_for_cmu_reports_unconvertible(
        self, mapper: CMUMapper
    ) -> None:
        assert mapper.validate_ipa_for_cmu("kæt4") == ["4"]

    def test_get_cmu_symbols(self, mapper: CMUMapper) -> None:
        syms = mapper.get_cmu_symbols()
        assert "K" in syms and "AE" in syms
        # include_extras is a superset.
        assert mapper.get_cmu_symbols(include_extras=True) >= syms

    def test_get_ipa_phones(self, mapper: CMUMapper) -> None:
        phones = mapper.get_ipa_phones()
        assert "p" in phones and "k" in phones
        assert mapper.get_ipa_phones(include_extras=True) >= phones
