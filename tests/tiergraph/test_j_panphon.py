from __future__ import annotations

import pytest
from ipakit._panphon_graph import NATIVE_TO_PANPHON, build, declaration, fingerprint
from tiergraph.build import document
from tiergraph.build import item as graph_item

import tiergraph

panphon = pytest.importorskip("panphon", reason="install the interop extra")


def test_panphon_own_names_values_and_deterministic_fingerprint():
    graph = build(("p", "a", "n"))
    names = tuple(panphon.FeatureTable().names)
    version = fingerprint(names)
    assert version.startswith("sha256:") and len(version) == 71
    assert {declared.name.local_name for declared in graph.attribute_declarations} == {
        "spelling",
        *names,
    }
    for spelling, item in zip(("p", "a", "n"), graph.tiers[0].items, strict=True):
        attributes = {
            attribute.name.local_name: attribute.lexical
            for attribute in item.attributes
        }
        assert attributes.pop("spelling") == spelling
        assert set(attributes) == set(names)
        assert set(map(int, attributes.values())) <= {-1, 0, 1}
    assert tiergraph.wire.loads(tiergraph.wire.dumps(graph)) == graph
    assert NATIVE_TO_PANPHON.source == "ipakit" and NATIVE_TO_PANPHON.losses


def test_same_representative_topology_is_feature_declaration_independent():
    graph = build(("p", "a", "n"))
    spelling_only_builder = document("urn:ipakit:panphon", prefix="panphon")
    for declared in declaration(()):
        spelling_only_builder.attribute(
            declared.name, declared.value_type, domain=declared.domain
        )
    spelling_only_builder.tier(
        "segment",
        (graph_item(spelling=spelling) for spelling in ("p", "a", "n")),
        item_type="segment",
        membership="segment-members",
    )
    spelling_only = spelling_only_builder.build()
    tier = graph.tiers[0]
    assert tier.declaration.name.local_name == "segment"
    assert (
        tuple(ref.index for ref in graph.canonical_items())
        == tuple(ref.index for ref in spelling_only.canonical_items())
        == (0, 1, 2)
    )
    assert [
        next(
            attribute.lexical
            for attribute in item.attributes
            if attribute.name.local_name == "spelling"
        )
        for item in tier.items
    ] == ["p", "a", "n"]
