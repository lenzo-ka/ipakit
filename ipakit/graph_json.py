"""Read and write arbitrary native Graph documents through the shared codec."""

from __future__ import annotations

from tiergraph import Graph, wire


def read_graph_json(document: str | bytes) -> Graph:
    """Read a structurally validated native Graph without Form admission.

    For a current Form profile, ``ipakit.read_json`` additionally validates the
    explicit inventory and source-role binding and returns an actual Form.
    """
    return wire.loads(document)


def write_graph_json(graph: Graph, *, pretty: bool = False) -> str:
    """Write the sole current native format, compact by default."""
    if not isinstance(graph, Graph):
        raise TypeError("graph must be a tiergraph.Graph")
    return wire.dumps(graph) if pretty else wire.dump_compact(graph)
