"""Tests for query and matching functionality."""

from ipakit import IPAFeatures


class TestPhonesMatching:
    """Tests for phones_matching query method."""

    def test_match_single_feature(self, ipa: IPAFeatures) -> None:
        # Match by manner
        result = ipa.phones_matching({"manner": "plosive"})
        assert "p" in result
        assert "t" in result
        assert "s" not in result  # fricative

    def test_match_multiple_features(self, ipa: IPAFeatures) -> None:
        # Voiceless bilabial plosive
        result = ipa.phones_matching(
            {"manner": "plosive", "place": "bilabial", "voiced": "-"}
        )
        assert "p" in result
        assert "b" not in result  # voiced

    def test_match_short_names_list(self, ipa: IPAFeatures) -> None:
        # Match using short name list
        result = ipa.phones_matching(["plo", "bil"])
        assert "p" in result
        assert "b" in result

    def test_match_binary_short_names(self, ipa: IPAFeatures) -> None:
        # Binary features with +/- prefix
        result = ipa.phones_matching(["-voi", "plo", "bil"])
        assert "p" in result
        assert "b" not in result  # voiced

    def test_match_ternary_short_names(self, ipa: IPAFeatures) -> None:
        # Ternary features (tongue-root) with 0 for neutral
        result = ipa.phones_matching(["0trt", "vow"])
        assert len(result) > 0

    def test_match_long_names_binary(self, ipa: IPAFeatures) -> None:
        # Long names for binary features
        result = ipa.phones_matching(["-voiced", "plosive", "bilabial"])
        assert "p" in result
        assert "b" not in result

    def test_match_long_names_ternary(self, ipa: IPAFeatures) -> None:
        result = ipa.phones_matching(["0tongue-root", "vowel"])
        assert len(result) > 0

    def test_match_with_defaults(self, ipa: IPAFeatures) -> None:
        # Without defaults, phones without explicit voiced=- won't match
        # With defaults (default=True), voiceless phones should match
        result = ipa.phones_matching(["-voi", "fri", "alv"], with_defaults=True)
        assert "s" in result

    def test_match_negation_ordinal(self, ipa: IPAFeatures) -> None:
        # Negation for ordinal features: -aspirated means NOT aspirated
        result = ipa.phones_matching(["plo", "-asp"], with_defaults=True)
        assert "p" in result
        # pʰ is aspirated so shouldn't be in simple phones
        # (pʰ is not a base phone, it's composed)


class TestShortsConversion:
    """Tests for short name conversion."""

    def test_features_to_shorts(self, ipa: IPAFeatures) -> None:
        feats = {"manner": "plosive", "place": "bilabial", "voiced": "-"}
        shorts = ipa.features_to_shorts(feats)
        assert "plo" in shorts
        assert "bil" in shorts
        assert "-voi" in shorts

    def test_shorts_to_features(self, ipa: IPAFeatures) -> None:
        shorts = ["plo", "bil", "-voi"]
        feats = ipa.shorts_to_features(shorts)
        assert feats["manner"] == "plosive"
        assert feats["place"] == "bilabial"
        assert feats["voiced"] == "-"

    def test_shorts_round_trip(self, ipa: IPAFeatures) -> None:
        original = {"manner": "fricative", "place": "alveolar", "voiced": "+"}
        shorts = ipa.features_to_shorts(original)
        recovered = ipa.shorts_to_features(shorts)
        for k, v in original.items():
            assert recovered[k] == v

    def test_ternary_shorts(self, ipa: IPAFeatures) -> None:
        # Ternary features: -, 0, +
        feats = {"tongue-root": "+"}
        shorts = ipa.features_to_shorts(feats)
        assert "+trt" in shorts

        feats = {"tongue-root": "0"}
        shorts = ipa.features_to_shorts(feats)
        assert "0trt" in shorts


class TestFeatureBundles:
    """Tests for feature_bundles function."""

    def test_single_phone(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("p")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"

    def test_multi_segment(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("pat")
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"

    def test_with_diacritics(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("pʰ")
        assert len(bundles) == 1
        assert bundles[0]["release"] == "aspirated"
