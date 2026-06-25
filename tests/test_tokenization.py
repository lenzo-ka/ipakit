"""Tests for IPA tokenization and normalization."""

import pytest

from ipakit import IPAFeatures


class TestTokenization:
    """Tests for IPA tokenization."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_tokenize_simple(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize_ipa("pat")
        assert tokens == ["p", "a", "t"]

    def test_tokenize_with_diacritics(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize_ipa("pʰat")
        assert tokens == ["pʰ", "a", "t"]

    def test_tokenize_affricates(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize_ipa("t͡ʃ")
        assert tokens == ["t͡ʃ"]

    def test_tokenize_legacy_affricate(self, ipa: IPAFeatures) -> None:
        # Legacy ligature should be expanded then tokenized as single unit
        tokens = ipa.tokenize_ipa("ʧ")
        assert tokens == ["t͡ʃ"]

    def test_tokenize_multiple_diacritics(self, ipa: IPAFeatures) -> None:
        # Phone with multiple diacritics
        tokens = ipa.tokenize_ipa("pʰʲ")
        assert len(tokens) == 1
        assert tokens[0] == "pʰʲ"

    def test_tokenize_long_vowel(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize_ipa("iː")
        assert tokens == ["iː"]

    def test_tokenize_nasalized_vowel(self, ipa: IPAFeatures) -> None:
        # IPA nasalization uses combining tilde (U+0303)
        nasalized_a = "a\u0303"  # a + combining tilde
        tokens = ipa.tokenize_ipa(nasalized_a)
        assert tokens == [nasalized_a]


class TestSegmentation:
    """Tests for IPA segmentation (space-separated output)."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_segment_simple(self, ipa: IPAFeatures) -> None:
        result = ipa.segment_ipa("pat")
        assert result == "p a t"

    def test_segment_with_diacritics(self, ipa: IPAFeatures) -> None:
        result = ipa.segment_ipa("pʰat")
        assert result == "pʰ a t"

    def test_segment_affricates(self, ipa: IPAFeatures) -> None:
        result = ipa.segment_ipa("t͡ʃat")
        assert "t͡ʃ" in result


class TestLigatureExpansion:
    """Tests for legacy ligature expansion."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_expand_legacy_ligatures(self, ipa: IPAFeatures) -> None:
        assert ipa.expand_ligatures("ʧ") == "t͡ʃ"
        assert ipa.expand_ligatures("ʤ") == "d͡ʒ"
        assert ipa.expand_ligatures("ʦ") == "t͡s"

    def test_expand_preserves_modern(self, ipa: IPAFeatures) -> None:
        assert ipa.expand_ligatures("t͡ʃ") == "t͡ʃ"

    def test_expand_tie_bar_below(self, ipa: IPAFeatures) -> None:
        # Tie bar below should become tie bar above
        assert ipa.expand_ligatures("t͜s") == "t͡s"


class TestNormalization:
    """Tests for IPA normalization."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_normalize_adds_ties(self, ipa: IPAFeatures) -> None:
        result = ipa.normalize_ipa("tʃ eɪ n dʒ")
        assert "t͡ʃ" in result
        assert "e͡ɪ" in result
        assert "d͡ʒ" in result

    def test_add_tie_bars(self, ipa: IPAFeatures) -> None:
        assert ipa.add_tie_bars("ts") == "t͡s"
        assert ipa.add_tie_bars("dz") == "d͡z"

    def test_add_tie_bars_preserves_existing(self, ipa: IPAFeatures) -> None:
        assert ipa.add_tie_bars("t͡s") == "t͡s"


class TestLookalikes:
    """Tests for lookalike character normalization."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_lookalikes_loaded(self, ipa: IPAFeatures) -> None:
        assert len(ipa.lookalikes) > 0
        assert "g" in ipa.lookalikes  # keyboard g -> script g
        assert ":" in ipa.lookalikes  # colon -> triangular colon

    def test_normalize_g(self, ipa: IPAFeatures) -> None:
        # Keyboard g (U+0067) should become IPA ɡ (U+0261)
        result = ipa.normalize_lookalikes("gat")
        assert result == "ɡat"
        assert result[0] == "\u0261"  # IPA script g

    def test_normalize_colon(self, ipa: IPAFeatures) -> None:
        # Keyboard : should become IPA ː (triangular colon)
        result = ipa.normalize_lookalikes("pa:t")
        assert "ː" in result

    def test_normalize_apostrophe(self, ipa: IPAFeatures) -> None:
        # Keyboard ' should become IPA ʼ (ejective marker)
        result = ipa.normalize_lookalikes("p'a")
        assert "ʼ" in result

    def test_normalize_question_mark(self, ipa: IPAFeatures) -> None:
        # Keyboard ? should become IPA ʔ (glottal stop)
        result = ipa.normalize_lookalikes("a?a")
        assert "ʔ" in result

    def test_expand_ligatures_includes_lookalikes(self, ipa: IPAFeatures) -> None:
        # expand_ligatures should also normalize lookalikes
        result = ipa.expand_ligatures("gat")
        assert result[0] == "\u0261"  # IPA script g


class TestCompose:
    """Tests for composing features from phone + diacritics."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def test_compose_simple(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("p")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"

    def test_compose_with_diacritic(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("pʰ")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"
        assert bundles[0]["release"] == "aspirated"

    def test_compose_multi_segment(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("pat")
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"

    def test_compose_preserves_class(self, ipa: IPAFeatures) -> None:
        # Composed segment should retain phone class, not diacritic class
        bundles = ipa.compose("pʰ")
        assert bundles[0]["class"] == "phone"

    def test_compose_voicing_diacritics(self, ipa: IPAFeatures) -> None:
        # Devoicing diacritic should set voiced to -
        bundles = ipa.compose("b̥")  # devoiced b
        assert bundles[0]["voiced"] == "-"
