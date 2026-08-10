"""Moraic tone-bearing-unit declaration for gairaigo model fixtures."""

from __future__ import annotations

from ._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ._tiergraph_builder import GraphBuilder


def declarations() -> Declarations:
    return Declarations(
        (
            TierDeclaration("mora", frozenset({"value"})),
            TierDeclaration("tone", frozenset({"tone"})),
        ),
        (FeatureDeclaration("value"), FeatureDeclaration("tone")),
        (
            RelationDeclaration(
                "associates-with",
                source_tiers=frozenset({"tone"}),
                target_tiers=frozenset({"mora"}),
                target_arity=(1, None),
            ),
        ),
    )


def build(morae: tuple[str, ...], tone: str) -> Graph:
    builder = GraphBuilder(declarations())
    hosts = tuple(
        builder.append_input_atom("mora", {"value": value}) for value in morae
    )
    tone_event = builder.add_event("tone", 0, {"tone": tone}, duration=0)
    builder.relate((tone_event,), "associates-with", hosts)
    return builder.build()
