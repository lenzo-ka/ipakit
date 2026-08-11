"""Katakana rendering of attested gairaigo adaptations on the mora tier.

This codec describes forms Japanese licenses; it is not an accent simulator.
"""

from __future__ import annotations

from ._tiergraph import Graph
from .bridges.kana import KANA


def render(graph: Graph) -> str:
    return KANA.render(graph)
