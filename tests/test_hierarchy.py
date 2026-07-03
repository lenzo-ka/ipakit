"""Tests for hierarchy generation."""

from ipakit import IPAFeatures


def _leaf_phones(node: dict) -> set[str]:
    """Collect every phone in the leaves of a hierarchy node."""
    if "phones" in node:
        return set(node["phones"])
    if "children" in node:
        out: set[str] = set()
        for child in node["children"].values():
            out |= _leaf_phones(child)
        return out
    return set()


class TestBuildHierarchy:
    """Tests for building phone hierarchies."""

    def test_build_hierarchy_basic(self, ipa: IPAFeatures) -> None:
        tree = ipa.build_hierarchy(phones=["p", "b", "t", "d"])
        # 4 distinct phones must split into a feature node with children.
        assert "feature" in tree
        assert "children" in tree
        # Every input phone is reachable in the leaves; none is dropped.
        assert _leaf_phones(tree) == {"p", "b", "t", "d"}

    def test_build_hierarchy_custom_order(self, ipa: IPAFeatures) -> None:
        tree = ipa.build_hierarchy(
            phones=["p", "b", "t", "d"], feature_order=["voiced", "place"]
        )
        # Top split is the first feature in the requested order.
        assert tree["feature"] == "voiced"
        assert _leaf_phones(tree) == {"p", "b", "t", "d"}


class TestHierarchyToText:
    """Tests for text hierarchy output."""

    def test_hierarchy_to_text_basic(self, ipa: IPAFeatures) -> None:
        text = ipa.hierarchy_to_text(phones=["p", "b"])
        assert len(text) > 0

    def test_hierarchy_to_text_custom_indent(self, ipa: IPAFeatures) -> None:
        text = ipa.hierarchy_to_text(phones=["p", "b", "t"], indent="    ")
        assert len(text) > 0
        # Nested groups are rendered with the custom 4-space indent.
        assert "    " in text


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
