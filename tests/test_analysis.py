"""Tests for analysis functions: describe, natural_class, minimal_pairs, validate_ipa."""

import ipakit
from ipakit import IPAFeatures


class TestDescribe:
    """Tests for describe() function."""

    def test_describe_voiceless_plosive(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("p")
        assert "voiceless" in desc
        assert "bilabial" in desc
        assert "plosive" in desc

    def test_describe_voiced_plosive(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("b")
        assert "voiced" in desc
        assert "bilabial" in desc
        assert "plosive" in desc

    def test_describe_vowel(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("ɛ")
        assert "open-mid" in desc
        assert "front" in desc
        assert "vowel" in desc

    def test_describe_rounded_vowel(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("u")
        assert "rounded" in desc
        assert "vowel" in desc

    def test_describe_affricate(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("t͡ʃ")
        assert "voiceless" in desc
        assert "affricate" in desc

    def test_describe_lateral(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("l")
        assert "lateral" in desc
        assert "approximant" in desc

    def test_describe_nasal(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("n")
        assert "nasal" in desc
        assert "alveolar" in desc

    def test_describe_unknown(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("X")
        assert "unknown" in desc

    def test_describe_module_function(self) -> None:
        desc = ipakit.describe("p")
        assert "voiceless" in desc
        assert "bilabial" in desc
        assert "plosive" in desc


class TestNaturalClass:
    """Tests for natural_class() function."""

    def test_voiceless_plosives(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p", "t", "k"])
        assert shared.get("manner") == "plosive"
        assert shared.get("voiced") == "-"

    def test_voiced_plosives(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["b", "d", "ɡ"])
        assert shared.get("manner") == "plosive"
        assert shared.get("voiced") == "+"

    def test_front_vowels(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["i", "e", "ɛ"])
        assert shared.get("manner") == "vowel"
        assert shared.get("backness") == "front"

    def test_nasals(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["m", "n", "ŋ"])
        assert shared.get("manner") == "nasal"
        assert shared.get("voiced") == "+"

    def test_bilabials(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p", "b", "m"])
        assert shared.get("place") == "bilabial"

    def test_empty_list(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class([])
        assert shared == {}

    def test_single_phone(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p"])
        # Single phone returns all its features
        assert "manner" in shared
        assert "place" in shared

    def test_module_function(self) -> None:
        shared = ipakit.natural_class(["p", "t", "k"])
        assert shared.get("manner") == "plosive"


class TestMinimalPairs:
    """Tests for minimal_pairs() function."""

    def test_minimal_pairs_p(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("p")
        phones = [p for p, _, _ in pairs]
        # b should be a minimal pair (differs in voicing)
        assert "b" in phones

    def test_minimal_pairs_s(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("s")
        phones = [p for p, _, _ in pairs]
        # z should be a minimal pair (differs in voicing)
        assert "z" in phones

    def test_minimal_pairs_returns_tuples(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("p")
        assert len(pairs) > 0
        for item in pairs:
            assert len(item) == 3
            phone, feat, val = item
            assert isinstance(phone, str)
            assert isinstance(feat, str)
            assert isinstance(val, str)

    def test_minimal_pairs_unknown_phone(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("X")
        assert pairs == []

    def test_module_function(self) -> None:
        pairs = ipakit.minimal_pairs("p")
        phones = [p for p, _, _ in pairs]
        assert "b" in phones


class TestNearestPhones:
    """Tests for nearest_phones() function."""

    def test_nearest_returns_list(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=5)
        assert isinstance(nearest, list)
        assert len(nearest) <= 5

    def test_nearest_sorted_by_distance(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=10)
        distances = [d for _, d in nearest]
        assert distances == sorted(distances)

    def test_nearest_includes_similar(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=10)
        phones = [p for p, _ in nearest]
        # Similar phones should include other bilabial/plosive sounds
        # Note: voiced pair "b" may not be top 5 due to voicing weight
        assert len(phones) > 0
        # At least check that we get plosives or bilabials
        assert any(p in phones for p in ["t", "k", "b", "ɸ", "f"])

    def test_nearest_unknown_phone(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("X")
        assert nearest == []

    def test_module_function(self) -> None:
        nearest = ipakit.nearest_phones("p", n=3)
        assert len(nearest) == 3
        # Check structure: list of (phone, distance) tuples
        for phone, dist in nearest:
            assert isinstance(phone, str)
            assert isinstance(dist, float)
            assert 0 <= dist <= 1


class TestValidateIPA:
    """Tests for validate_ipa() function."""

    def test_valid_simple(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("kæt")
        assert issues == []

    def test_valid_with_diacritics(self, ipa: IPAFeatures) -> None:
        # Dental diacritic on t
        issues = ipa.validate_ipa("t̪")
        assert issues == []

    def test_valid_affricate(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("t͡ʃ")
        assert issues == []

    def test_valid_with_stress(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("ˈkæt")
        assert issues == []

    def test_valid_with_syllable_break(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("hɛ.loʊ")
        assert issues == []

    def test_valid_with_word_boundary(self, ipa: IPAFeatures) -> None:
        # '#' is a word separator in ipa.xml (data-driven; was rejected before).
        assert ipa.validate_ipa("kæt#dɒɡ") == []

    def test_valid_tone_letter(self, ipa: IPAFeatures) -> None:
        # Spacing tone letters are standalone suprasegmentals.
        assert ipa.validate_ipa("ma˥") == []

    def test_unknown_symbol(self, ipa: IPAFeatures) -> None:
        # Use actual non-IPA characters (note: x, y, z ARE valid IPA)
        issues = ipa.validate_ipa("k@t")  # @ is not IPA
        assert len(issues) >= 1
        codes = [i["code"] for i in issues]
        assert "unknown_symbol" in codes

    def test_unknown_symbol_details(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("@")  # @ is not IPA
        assert len(issues) == 1
        issue = issues[0]
        assert issue["type"] == "error"
        assert issue["code"] == "unknown_symbol"
        assert issue["symbol"] == "@"
        assert issue["position"] == "0"

    def test_orphan_diacritic(self, ipa: IPAFeatures) -> None:
        # Nasal diacritic at start (no base phone)
        issues = ipa.validate_ipa("̃a")
        codes = [i["code"] for i in issues]
        assert "orphan_diacritic" in codes

    def test_malformed_tie_at_boundary(self, ipa: IPAFeatures) -> None:
        # A tie bar with nothing to tie on one side is malformed. Covers a lone
        # tie, a leading tie, and a trailing tie -- none is a valid composite.
        tie = "͡"
        for bad in (tie, tie + "a", "a" + tie):
            codes = [i["code"] for i in ipa.validate_ipa(bad)]
            assert "malformed_tie" in codes, f"{bad!r} should flag malformed_tie"

    def test_valid_tie_composite_is_clean(self, ipa: IPAFeatures) -> None:
        # A well-formed affricate must NOT be flagged.
        assert ipa.validate_ipa("t͡ʃ") == []

    def test_duplicate_diacritic_warning(self, ipa: IPAFeatures) -> None:
        # Same diacritic twice on one segment
        issues = ipa.validate_ipa("t̪̪")
        codes = [i["code"] for i in issues]
        assert "duplicate_diacritic" in codes
        # Should be a warning, not error
        dupe_issue = next(i for i in issues if i["code"] == "duplicate_diacritic")
        assert dupe_issue["type"] == "warning"

    def test_strict_mode(self, ipa: IPAFeatures) -> None:
        # In strict mode, warnings become errors
        issues = ipa.validate_ipa("t̪̪", strict=True)
        dupe_issue = next(i for i in issues if i["code"] == "duplicate_diacritic")
        assert dupe_issue["type"] == "error"

    def test_is_valid_ipa_true(self, ipa: IPAFeatures) -> None:
        assert ipa.is_valid_ipa("kæt") is True

    def test_is_valid_ipa_false(self, ipa: IPAFeatures) -> None:
        assert ipa.is_valid_ipa("k@t") is False  # @ is not IPA

    def test_is_valid_ipa_with_warning(self, ipa: IPAFeatures) -> None:
        # Warnings don't make it invalid
        assert ipa.is_valid_ipa("t̪̪") is True

    def test_module_function_valid(self) -> None:
        issues = ipakit.validate_ipa("kæt")
        assert issues == []

    def test_module_function_invalid(self) -> None:
        issues = ipakit.validate_ipa("k@t")  # @ is not IPA
        assert len(issues) >= 1

    def test_is_valid_module_function(self) -> None:
        assert ipakit.is_valid_ipa("kæt") is True
        assert ipakit.is_valid_ipa("k@t") is False  # @ is not IPA
