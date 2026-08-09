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

    def test_from_cmu(self) -> None:
        result = ipakit.from_cmu(["P"])
        assert result == "p"

    def test_from_cmu_is_the_cmu_entry_point(self) -> None:
        # from_cmu names its source format as its siblings do. The former
        # to_ipa alias is gone, and the name now means segments -> string.
        assert ipakit.from_cmu(["K", "AE1", "T"]) == "kˈæt"
        assert ipakit.from_cmu(["P"]) == "p"
        assert "from_cmu" in ipakit.__all__
        assert ipakit.to_ipa(ipakit.segments("kæt")) == "kæt"

    def test_generic_phonemap_functions_exported(self) -> None:
        # ipa_to_phonemap / phonemap_to_ipa are now part of the public surface.
        assert ipakit.ipa_to_phonemap("kæt", "timit") == ["k", "ae", "t"]
        assert ipakit.phonemap_to_ipa(["k", "ae", "t"], "timit") == "kæt"
        assert "ipa_to_phonemap" in ipakit.__all__
        assert "phonemap_to_ipa" in ipakit.__all__

    def test_tokenize(self) -> None:
        result = ipakit.tokenize("pat")
        assert result == ["p", "a", "t"]

    def test_read_and_read_json_share_the_representation(self) -> None:
        parsed = ipakit.read("kæt.ˈ.dɒɡ", strict=True)
        restored = ipakit.read_json(parsed.to_json())
        assert restored == parsed
        assert restored.to_ipa() == "kæt.ˈ.dɒɡ"
        assert "read" in ipakit.__all__
        assert "read_json" in ipakit.__all__

    def test_segmented(self) -> None:
        assert ipakit.segmented("pat") == "p a t"

    def test_segment_returns_a_segment(self) -> None:
        # `segment` names the Segment concept; `segmented` is the string.
        assert ipakit.segment("t͡s").kind.value == "affricate"

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


class TestEmptyInputs:
    """Edge cases: empty strings must not raise."""

    def test_tokenize_empty(self) -> None:
        assert ipakit.tokenize("") == []

    def test_every_entry_point_calls_two_empties_identical(self) -> None:
        # These three used to disagree: distance and segment_distance
        # answered 1.0 while word_distance answered 0.0, so the two public
        # entry points gave opposite answers to one question. "Nothing
        # comparable" and "maximally far apart" are different claims, and
        # only the first is true of two empty inputs.
        assert ipakit.distance("", "") == 0.0
        assert ipakit.segment_distance("", "") == 0.0
        r = ipakit.word_distance("", "")
        assert r.edit_cost == 0.0
        assert r.similarity == 1.0

    def test_an_empty_input_against_a_spoken_one_is_still_max(self) -> None:
        # Identity must not cost the silence-is-a-deletion claim: every
        # position is unmatched, so the mean is 1.0 with no special case.
        assert ipakit.segment_distance("", "a") == 1.0
        assert ipakit.segment_distance("kat", "") == 1.0

    def test_feature_bundles_empty(self) -> None:
        assert ipakit.feature_bundles("") == []

    def test_describe_empty_does_not_raise(self) -> None:
        # describe on empty input returns a string rather than raising.
        assert isinstance(ipakit.describe(""), str)
