from __future__ import annotations

import json

import pytest
from ipakit._panphon_graph import NATIVE_TO_PANPHON, build, fingerprint
from ipakit._tiergraph_json import dumps, loads

panphon = pytest.importorskip("panphon", reason="install the interop extra")


def test_panphon_own_names_values_and_deterministic_fingerprint():
    graph, model = build(("p", "a", "n"))
    assert model.version == fingerprint(tuple(panphon.FeatureTable().names))
    assert model.version.startswith("sha256:") and len(model.version) == 71
    events = [
        event for node in graph.clock for group in node.groups for event in group.events
    ]
    assert all(
        set(event.features.values()) <= {-1, 0, 1, "p", "a", "n"} for event in events
    )
    wire = dumps(graph, model)
    assert json.loads(wire)["model"] == {"name": "panphon", "version": model.version}
    assert loads(wire, model) == graph
    assert NATIVE_TO_PANPHON.source == "ipakit" and NATIVE_TO_PANPHON.losses


def test_same_representative_topology_is_feature_declaration_independent():
    graph, _ = build(("p", "a", "n"))
    assert graph.event_references() == (
        "/clock/0/segment/0",
        "/clock/1/segment/0",
        "/clock/2/segment/0",
    )
