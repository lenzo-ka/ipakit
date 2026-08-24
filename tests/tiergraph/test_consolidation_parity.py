from __future__ import annotations

import json

from scripts.consolidation_parity import corpus_bytes

import tiergraph


def test_parity_corpus_escaped_graph_is_native_and_round_trips() -> None:
    escaped = json.loads(corpus_bytes())["escaped"]
    graph = tiergraph.wire.loads(escaped)
    assert tiergraph.wire.loads(tiergraph.wire.dumps(graph)) == graph
    assert graph.tiers[0].declaration.long_name == "custom~/tier"
    assert graph.tiers[0].items[0].attributes[0].name.local_name == "feature~/key"
