"""Tests for module-level API functions."""

import ipakit


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_distance(self) -> None:
        assert ipakit.distance("p", "p") == 0.0
        assert ipakit.distance("p", "b") > 0

    def test_features(self) -> None:
        feats = ipakit.features("p")
        assert feats["manner"] == "plosive"
        assert feats["place"] == "bilabial"

    def test_to_cmu(self) -> None:
        result = ipakit.to_cmu("p")
        assert result == ["P"]

    def test_to_ipa(self) -> None:
        result = ipakit.to_ipa(["P"])
        assert result == "p"

    def test_tokenize(self) -> None:
        result = ipakit.tokenize("pat")
        assert result == ["p", "a", "t"]

    def test_segment(self) -> None:
        result = ipakit.segment("pat")
        assert result == "p a t"

    def test_normalize(self) -> None:
        result = ipakit.normalize("tʃ")
        assert result == "t͡ʃ"

    def test_add_ties(self) -> None:
        result = ipakit.add_ties("ts")
        assert result == "t͡s"


class TestXSAMPAFunctions:
    """Tests for X-SAMPA related functions."""

    def test_xsampa_to_ipa_basic(self) -> None:
        assert ipakit.xsampa_to_ipa("p") == "p"
        assert ipakit.xsampa_to_ipa("a") == "a"
        assert ipakit.xsampa_to_ipa("t") == "t"

    def test_xsampa_to_ipa_extended(self) -> None:
        # Uppercase X-SAMPA = IPA extensions
        assert ipakit.xsampa_to_ipa("S") == "ʃ"
        assert ipakit.xsampa_to_ipa("A") == "ɑ"
        assert ipakit.xsampa_to_ipa("E") == "ɛ"

    def test_features_from_xsampa(self) -> None:
        bundles = ipakit.features_from_xsampa("pat")
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"


class TestCMUFeatures:
    """Tests for getting features from CMU input."""

    def test_features_from_cmu(self) -> None:
        bundles = ipakit.features_from_cmu(["P", "AE1", "T"])
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[0]["place"] == "bilabial"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"
        assert bundles[2]["place"] == "alveolar"


class TestQueryFunctions:
    """Tests for query-related module functions."""

    def test_feature_bundles_single(self) -> None:
        bundles = ipakit.feature_bundles("p")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"

    def test_feature_bundles_multi(self) -> None:
        bundles = ipakit.feature_bundles("pat")
        assert len(bundles) == 3

    def test_phones_matching(self) -> None:
        result = ipakit.phones_matching({"manner": "plosive", "place": "bilabial"})
        assert "p" in result
        assert "b" in result

    def test_features_to_shorts(self) -> None:
        shorts = ipakit.features_to_shorts({"manner": "plosive"})
        assert "plo" in shorts

    def test_shorts_to_features(self) -> None:
        feats = ipakit.shorts_to_features(["plo", "bil"])
        assert feats["manner"] == "plosive"
        assert feats["place"] == "bilabial"
