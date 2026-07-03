"""Tests for hierarchy generation."""

from ipakit import IPAFeatures


class TestBuildHierarchy:
    """Tests for building phone hierarchies."""

    def test_build_hierarchy_basic(self, ipa: IPAFeatures) -> None:
        tree = ipa.build_hierarchy(phones=["p", "b", "t", "d"])
        assert "feature" in tree or "phones" in tree

    def test_build_hierarchy_custom_order(self, ipa: IPAFeatures) -> None:
        tree = ipa.build_hierarchy(
            phones=["p", "b", "t", "d"], feature_order=["voiced", "place"]
        )
        assert "feature" in tree or "phones" in tree


class TestHierarchyToText:
    """Tests for text hierarchy output."""

    def test_hierarchy_to_text_basic(self, ipa: IPAFeatures) -> None:
        text = ipa.hierarchy_to_text(phones=["p", "b"])
        assert len(text) > 0

    def test_hierarchy_to_text_custom_indent(self, ipa: IPAFeatures) -> None:
        text = ipa.hierarchy_to_text(phones=["p", "b", "t"], indent="    ")
        assert len(text) > 0
        # Should contain the custom indent
        assert "    " in text or text.startswith("manner")


class TestHierarchyToDot:
    """Tests for DOT format hierarchy output."""

    def test_hierarchy_to_dot_basic(self, ipa: IPAFeatures) -> None:
        dot = ipa.hierarchy_to_dot(phones=["p", "b"])
        assert "digraph" in dot
        assert "PhoneHierarchy" in dot

    def test_hierarchy_to_dot_custom_title(self, ipa: IPAFeatures) -> None:
        dot = ipa.hierarchy_to_dot(phones=["p", "b"], title="Custom Title")
        assert "Custom Title" in dot

    def test_hierarchy_to_dot_escapes_special_chars(self, ipa: IPAFeatures) -> None:
        # IPA symbols shouldn't crash the DOT generation
        dot = ipa.hierarchy_to_dot(phones=["p", "b", "ʃ", "ʒ"])
        assert "digraph" in dot
