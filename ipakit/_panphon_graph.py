"""Development-only PanPhon declaration adapter (no production import)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from tiergraph.build import document
from tiergraph.build import item as graph_item

import tiergraph as tg

from ._identity import identity_fingerprint

_NAMESPACE = "urn:ipakit:panphon"


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


def declaration(names: tuple[str, ...]) -> tuple[tg.AttributeDeclaration, ...]:
    """Return native declarations for PanPhon spelling and feature facts."""
    return (
        tg.AttributeDeclaration(
            tg.QualifiedName(_NAMESPACE, "spelling"),
            tg.AttributeDomain.ITEM,
            tg.XsdType.STRING,
        ),
        *(
            tg.AttributeDeclaration(
                tg.QualifiedName(_NAMESPACE, name),
                tg.AttributeDomain.ITEM,
                tg.XsdType.INTEGER,
            )
            for name in names
        ),
    )


def fingerprint(names: tuple[str, ...]) -> str:
    return identity_fingerprint(
        {"provider": "panphon", "features": names, "domain": [-1, 0, 1]}
    )


def build(spellings: tuple[str, ...]) -> tg.Graph:
    """Build a native segment graph retaining every PanPhon feature column."""
    names, values = bundles(spellings)
    builder = document(_NAMESPACE, prefix="panphon")
    for declared in declaration(names):
        builder.attribute(
            declared.name,
            declared.value_type,
            domain=declared.domain,
        )
    builder.tier(
        "segment",
        (
            graph_item(
                spelling=spelling,
                attrs=cast(Mapping[str | tg.QualifiedName, object], bundle),
            )
            for spelling, bundle in zip(spellings, values, strict=True)
        ),
        item_type="segment",
        membership="segment-members",
    )
    return builder.build()


NATIVE_TO_PANPHON = DirectionalMapping(
    "ipakit",
    "panphon",
    "explicit representative spelling lookup",
    ("native feature names and non-binary domains are not preserved",),
)
