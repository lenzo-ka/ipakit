"""Hierarchy generation mixin for IPAFeatures."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ._base import IPAFeaturesBase
from .constants import MAX_EXAMPLE_PHONES, MISSING_FEATURE_VALUE

# A hierarchy node is one of {"phones": [...]} or {"children": {...}, "feature": str}
HierarchyNode = dict[str, Any]


class HierarchyMixin(IPAFeaturesBase):
    """Mixin providing phone hierarchy generation."""

    def build_hierarchy(
        self,
        phones: list[str] | None = None,
        feature_order: list[str] | None = None,
    ) -> HierarchyNode:
        """Build a hierarchical grouping of phones by features."""
        phones = phones or list(self.phones.keys())
        feature_order = feature_order or self.feature_order

        # Compose each phone's full feature dict once, rather than recomputing it
        # at every recursion level and for every candidate split feature.
        feats = {p: self.get_features(p, with_defaults=True) for p in phones}

        def build_node(phone_set: list[str], remaining: list[str]) -> HierarchyNode:
            if not phone_set:
                return {}
            if len(phone_set) == 1 or not remaining:
                return {"phones": phone_set}

            # Find next feature that splits this set
            split_feat = None
            for f in remaining:
                values = {feats[p].get(f, MISSING_FEATURE_VALUE) for p in phone_set}
                values.discard(MISSING_FEATURE_VALUE)
                if len(values) > 1:
                    split_feat = f
                    break

            if split_feat is None:
                return {"phones": phone_set}

            groups: dict[str, list[str]] = defaultdict(list)
            for p in phone_set:
                val = feats[p].get(split_feat, MISSING_FEATURE_VALUE)
                groups[val].append(p)

            next_remaining = [f for f in remaining if f != split_feat]
            return {
                "children": {
                    val: build_node(grp, next_remaining)
                    for val, grp in sorted(groups.items())
                },
                "feature": split_feat,
            }

        return build_node(phones, feature_order)

    def hierarchy_to_text(
        self,
        phones: list[str] | None = None,
        feature_order: list[str] | None = None,
        indent: str = "  ",
    ) -> str:
        """Generate text representation of phone hierarchy."""
        tree = self.build_hierarchy(phones, feature_order)
        lines: list[str] = []

        def render(node: HierarchyNode, depth: int = 0, prefix: str = "") -> None:
            ind = indent * depth
            if "phones" in node:
                lines.append(f"{ind}{prefix}[{', '.join(sorted(node['phones']))}]")
            elif "feature" in node:
                if prefix:
                    lines.append(f"{ind}{prefix}")
                for val, child in sorted(node["children"].items()):
                    render(child, depth + 1, f"{node['feature']}={val}: ")

        render(tree)
        return "\n".join(lines)

    def hierarchy_to_dot(
        self,
        phones: list[str] | None = None,
        feature_order: list[str] | None = None,
        title: str = "Phone Hierarchy",
    ) -> str:
        """Generate DOT graph of phone hierarchy."""
        tree = self.build_hierarchy(phones, feature_order)
        lines = [
            "digraph PhoneHierarchy {",
            "    rankdir=TB;",
            "    node [shape=box, style=filled];",
            f'    label="{title}";',
            "    labelloc=t;",
            "",
        ]
        edges: list[str] = []
        counter = [0]

        def escape_dot(s: str) -> str:
            return s.replace("\\", "\\\\").replace('"', '\\"')

        def emit(node: HierarchyNode) -> str:
            node_id = f"n{counter[0]}"
            counter[0] += 1

            if "phones" in node:
                phones_list = sorted(node["phones"])
                label = (
                    ", ".join(phones_list)
                    if len(phones_list) <= MAX_EXAMPLE_PHONES
                    else f"{', '.join(phones_list[:MAX_EXAMPLE_PHONES])}... ({len(phones_list)})"
                )
                lines.append(
                    f'    {node_id} [label="{escape_dot(label)}", fillcolor=lightblue];'
                )
            elif "feature" in node:
                lines.append(
                    f'    {node_id} [label="{escape_dot(node["feature"])}", fillcolor=lightyellow];'
                )
                for val, child in sorted(node["children"].items()):
                    child_id = emit(child)
                    edges.append(
                        f'    {node_id} -> {child_id} [label="{escape_dot(val)}"];'
                    )
            return node_id

        emit(tree)
        lines.append("")
        lines.extend(edges)
        lines.append("}")
        return "\n".join(lines)
