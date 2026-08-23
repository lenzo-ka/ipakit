"""Development-only PanPhon declaration adapter (no production import)."""

from __future__ import annotations

from dataclasses import dataclass

from ._identity import identity_fingerprint
from ._tiergraph import Declarations, FeatureDeclaration, Graph, TierDeclaration
from ._tiergraph_builder import GraphBuilder
from ._tiergraph_json import Model


@dataclass(frozen=True)
class DirectionalMapping:
    source: str
    target: str
    provenance: str
    losses: tuple[str, ...]


def bundles(
    spellings: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[dict[str, int], ...]]:
    """Return PanPhon's own feature names and numeric value domain lazily."""
    import panphon  # optional interop extra

    table = panphon.FeatureTable()
    names = tuple(table.names)
    result = []
    for spelling in spellings:
        vectors = table.word_fts(spelling)
        if len(vectors) != 1:
            raise ValueError(f"expected one PanPhon segment: {spelling!r}")
        vector = vectors[0]
        result.append({name: int(vector[name]) for name in names})
    return names, tuple(result)


def declaration(names: tuple[str, ...]) -> Declarations:
    return Declarations(
        (TierDeclaration("segment", frozenset(names) | frozenset({"spelling"})),),
        tuple(FeatureDeclaration(n) for n in (*names, "spelling")),
        (),
    )


def fingerprint(names: tuple[str, ...]) -> str:
    return identity_fingerprint(
        {"provider": "panphon", "features": names, "domain": [-1, 0, 1]}
    )


def model(names: tuple[str, ...]) -> Model:
    return Model("panphon", fingerprint(names), declaration(names))


def build(spellings: tuple[str, ...]) -> tuple[Graph, Model]:
    names, values = bundles(spellings)
    builder = GraphBuilder(declaration(names))
    for spelling, bundle in zip(spellings, values, strict=True):
        builder.append_input_atom("segment", {"spelling": spelling, **bundle})
    return builder.build(), model(names)


NATIVE_TO_PANPHON = DirectionalMapping(
    "ipakit",
    "panphon",
    "explicit representative spelling lookup",
    ("native feature names and non-binary domains are not preserved",),
)
