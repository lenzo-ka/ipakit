"""Moraic tone-bearing-unit declaration for gairaigo model fixtures."""

from __future__ import annotations

from tiergraph.build import document
from tiergraph.build import item as graph_item

import tiergraph as tg

_NAMESPACE = "urn:ipakit:mora"


def declarations() -> tuple[tg.AttributeDeclaration, ...]:
    """Return the native declarations for authoritative mora item facts."""
    return tuple(
        tg.AttributeDeclaration(
            tg.QualifiedName(_NAMESPACE, name),
            tg.AttributeDomain.ITEM,
            tg.XsdType.STRING,
        )
        for name in ("value", "tone")
    )


def build(morae: tuple[str, ...], tone: str) -> tg.Graph:
    """Build a native mora graph with one tone-to-mora association."""
    builder = document(_NAMESPACE, prefix="mora")
    for declaration in declarations():
        builder.attribute(
            declaration.name,
            declaration.value_type,
            domain=declaration.domain,
        )

    mora_tier = builder.tier(
        "mora",
        (graph_item(value=value) for value in morae),
        item_type="mora",
        membership="mora-members",
    )
    tone_tier = builder.tier(
        "tone",
        (graph_item(tone=tone),),
        item_type="tone",
        membership="tone-members",
    )

    association = builder.qname("associates-with")
    item_side = (tg.RelationEndpointKind.ITEM,)
    builder.declare(
        tg.PolyadicRelationDeclaration(
            association,
            tg.RelationSideDeclaration(
                item_side, (tone_tier.name,), minimum=1, maximum=1
            ),
            tg.RelationSideDeclaration(
                item_side, (mora_tier.name,), minimum=1, maximum=None
            ),
        )
    )
    builder.relate(
        tg.PolyadicRelationInstance(
            association,
            (tone_tier.ref(0),),
            tuple(mora_tier.ref(index) for index in range(len(morae))),
        )
    )
    return builder.build()
