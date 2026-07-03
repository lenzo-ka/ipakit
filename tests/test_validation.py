"""Tests for validation and statistics."""

from ipakit import IPAFeatures


class TestValidate:
    """Tests for validate method."""

    def test_validate_no_critical_errors(self, ipa: IPAFeatures) -> None:
        errors = ipa.validate()
        critical = [e for e in errors if "Missing" in e]
        assert len(critical) == 0

    def test_shipped_data_validates_clean(self, ipa: IPAFeatures) -> None:
        # The bundled ipa.xml must pass validate() with zero errors. Metadata
        # attributes (href, xsampa, ...) are not phonetic features and must not
        # be reported as "undeclared". See METADATA_ATTRS in constants.py.
        assert ipa.validate() == []

    def test_validate_returns_list(self, ipa: IPAFeatures) -> None:
        errors = ipa.validate()
        assert isinstance(errors, list)

    def test_validate_reports_invalid_feature_value(self) -> None:
        # Fresh (non-shared) instance: corrupt one phone's feature to an
        # undeclared value and confirm validate() flags it.
        bad = IPAFeatures()
        bad.phones["p"].features["voiced"] = "bogus"
        errors = bad.validate()
        assert any("bogus" in e and "'p'" in e for e in errors)

    def test_validate_reports_missing_place_for_consonant(self) -> None:
        bad = IPAFeatures()
        bad.phones["t"].features.pop("place", None)
        errors = bad.validate()
        assert any("Missing 'place'" in e and "'t'" in e for e in errors)

    def test_validate_reports_undeclared_feature(self) -> None:
        bad = IPAFeatures()
        bad.phones["p"].features["madeup"] = "x"
        errors = bad.validate()
        assert any("Undeclared feature 'madeup'" in e for e in errors)


class TestStatistics:
    """Tests for statistical methods."""

    def test_feature_counts(self, ipa: IPAFeatures) -> None:
        counts = ipa.feature_counts()
        assert "manner" in counts
        assert "plosive" in counts["manner"]
        assert counts["manner"]["plosive"] > 0

    def test_feature_usage(self, ipa: IPAFeatures) -> None:
        usage = ipa.feature_usage()
        assert "manner" in usage
        assert usage["manner"] > 0
        # manner should be used by most phones
        assert usage["manner"] > 50

    def test_summary(self, ipa: IPAFeatures) -> None:
        s = ipa.summary()
        assert "n_phones" in s
        assert "n_features" in s
        assert "n_diacritics" in s
        assert "feature_counts" in s
        assert "feature_usage" in s
        assert "manner_distribution" in s
        assert s["n_phones"] > 100
        assert s["n_features"] > 5


class TestMixinIntegration:
    """Tests for mixin integration with IPAFeatures."""

    def test_distance_mixin_methods(self, ipa: IPAFeatures) -> None:
        assert hasattr(ipa, "distance")
        assert hasattr(ipa, "segment_distance")
        assert hasattr(ipa, "pairwise_distances")
        assert callable(ipa.distance)

    def test_hierarchy_mixin_methods(self, ipa: IPAFeatures) -> None:
        assert hasattr(ipa, "build_hierarchy")
        assert hasattr(ipa, "hierarchy_to_text")
        assert hasattr(ipa, "hierarchy_to_dot")
        assert callable(ipa.build_hierarchy)

    def test_validation_mixin_methods(self, ipa: IPAFeatures) -> None:
        assert hasattr(ipa, "validate")
        assert hasattr(ipa, "feature_counts")
        assert hasattr(ipa, "feature_usage")
        assert hasattr(ipa, "summary")
        assert callable(ipa.validate)
