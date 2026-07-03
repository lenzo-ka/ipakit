"""Tests for IPAFeatures class - loading and basic operations."""

from ipakit import IPAFeatures


class TestLoading:
    """Tests for loading IPA data from XML."""

    def test_load_phones(self, ipa: IPAFeatures) -> None:
        assert len(ipa.phones) > 100
        assert "p" in ipa
        assert "ʃ" in ipa
        assert "ə" in ipa

    def test_load_diacritics(self, ipa: IPAFeatures) -> None:
        assert len(ipa.diacritics) > 20
        assert "ʰ" in ipa.diacritics
        assert "̃" in ipa.diacritics

    def test_load_features(self, ipa: IPAFeatures) -> None:
        assert "manner" in ipa.features
        assert "place" in ipa.features
        assert "voiced" in ipa.features

    def test_load_affricates(self, ipa: IPAFeatures) -> None:
        assert "t͡ʃ" in ipa.phones
        assert "d͡ʒ" in ipa.phones
        assert "t͡s" in ipa.phones
        assert "d͡z" in ipa.phones
        feats = ipa.get_features("t͡ʃ")
        assert feats["manner"] == "affricate"
        assert feats["place"] == "postalveolar"

    def test_load_classes(self, ipa: IPAFeatures) -> None:
        # Classes are stored as plural section names
        assert "phones" in ipa.classes
        assert "diacritics" in ipa.classes
        assert "suprasegmentals" in ipa.classes

    def test_feature_order_from_xml(self, ipa: IPAFeatures) -> None:
        order = ipa.feature_order
        assert isinstance(order, list)
        assert "manner" in order
        assert "place" in order
        assert "class" not in order  # structural metadata, not a feature
        assert order.index("manner") < order.index("place")

    def test_consonant_manners_derived(self, ipa: IPAFeatures) -> None:
        cm = ipa.consonant_manners
        assert isinstance(cm, frozenset)
        assert "plosive" in cm
        assert "fricative" in cm
        assert "vowel" not in cm
        assert "silence" not in cm


class TestGetFeatures:
    """Tests for getting features of phones."""

    def test_get_features_consonant(self, ipa: IPAFeatures) -> None:
        feats = ipa.get_features("p")
        assert feats["manner"] == "plosive"
        assert feats["place"] == "bilabial"
        assert feats["voiced"] == "-"

    def test_get_features_vowel(self, ipa: IPAFeatures) -> None:
        feats = ipa.get_features("i")
        assert feats["manner"] == "vowel"
        assert feats["height"] == "close"
        assert feats["backness"] == "front"

    def test_get_features_unknown(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("X") == {}

    def test_get_features_with_defaults(self, ipa: IPAFeatures) -> None:
        feats_with = ipa.get_features("p", with_defaults=True)
        feats_without = ipa.get_features("p", with_defaults=False)
        assert len(feats_with) >= len(feats_without)

    def test_phones_by_manner(self, ipa: IPAFeatures) -> None:
        plosives = ipa.phones_by_manner("plosive")
        assert "p" in plosives
        assert "t" in plosives
        assert "k" in plosives
        assert "s" not in plosives  # fricative

    def test_phones_by_feature(self, ipa: IPAFeatures) -> None:
        bilabials = ipa.phones_by_feature("place", "bilabial")
        assert "p" in bilabials
        assert "b" in bilabials
        assert "m" in bilabials
        assert "t" not in bilabials


class TestFeatureDefinitions:
    """Tests for feature definitions loaded from XML."""

    def test_feature_has_values(self, ipa: IPAFeatures) -> None:
        manner = ipa.features["manner"]
        assert "plosive" in manner.values
        assert "fricative" in manner.values
        assert "vowel" in manner.values

    def test_feature_has_type(self, ipa: IPAFeatures) -> None:
        assert ipa.features["voiced"].type == "binary"
        assert ipa.features["manner"].type == "ordinal"

    def test_feature_has_description(self, ipa: IPAFeatures) -> None:
        # Features should have descriptions loaded from XML
        manner = ipa.features["manner"]
        assert manner.desc is not None
        assert len(manner.desc) > 0

        voiced = ipa.features["voiced"]
        assert voiced.desc is not None

    def test_feature_default(self, ipa: IPAFeatures) -> None:
        # Binary features default to "-"
        assert ipa.features["voiced"].default == "-"
        # Ternary features default to "0"
        assert ipa.features["tongue-root"].default == "0"
        # Some ordinal features have explicit defaults
        assert ipa.features["airstream"].default == "pulmonic"


class TestAliases:
    """Tests for character aliases."""

    def test_ligature_map_loaded(self, ipa: IPAFeatures) -> None:
        assert len(ipa.ligature_map) > 0
        assert "ʧ" in ipa.ligature_map  # legacy ligature

    def test_tie_bar_below_alias(self, ipa: IPAFeatures) -> None:
        assert "͜" in ipa.ligature_map
        assert ipa.ligature_map["͜"] == "͡"

    def test_affricate_aliases(self, ipa: IPAFeatures) -> None:
        assert "t͜ʃ" in ipa.ligature_map
        assert ipa.ligature_map["t͜ʃ"] == "t͡ʃ"
        assert "ʧ" in ipa.ligature_map
        assert ipa.ligature_map["ʧ"] == "t͡ʃ"


class TestDerivedInventory:
    """Inventory pieces derived from ipa.xml (no hard-coded symbol tables)."""

    def test_separators_loaded(self, ipa: IPAFeatures) -> None:
        # '.' (syllable) and '#' (word) are separators, not phones.
        assert "." in ipa.separators
        assert "#" in ipa.separators
        assert "." not in ipa.phones

    def test_syllable_break_derived(self, ipa: IPAFeatures) -> None:
        assert ipa.syllable_break == "."

    def test_stress_to_marker_inverts(self, ipa: IPAFeatures) -> None:
        assert ipa.stress_to_marker == {1: "ˈ", 2: "ˌ"}
