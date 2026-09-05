"""Construct the tier graph selected by a TextGrid span-view profile."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tiergraph.core import RelationDeclaration

import tiergraph as tg

from .form import Timing

NS = "https://ipakit.dev/textgrid/v1"


def name(local: str) -> tg.QualifiedName:
    return tg.QualifiedName(NS, local)


BASE = name("base")
CLOCK = name("clock")
BASE_ITEM = name("base-item")
SPAN_ITEM = name("interval")
POINT_ITEM = name("point")
CLOCK_ITEM = name("clock-item")
COVERAGE = name("coverage")
POINT_COVERAGE = name("point-coverage")
CLOCK_BINDING = name("clock-binding")
SPELLING = name("spelling")
SCORE = name("score")
UNIT = name("unit")
START = name("start")
DURATION = name("duration")
UNTIMED = name("untimed")


def boundary(
    index: int, size: int, tier: tg.QualifiedName = BASE
) -> tg.DurableBoundaryRef:
    if index == 0:
        return tg.DurableBoundaryRef(tier, tg.BoundarySide.BEFORE)
    if index == size:
        return tg.DurableBoundaryRef(tier, tg.BoundarySide.AFTER)
    return tg.DurableBoundaryRef(
        tg.DurableItemRef(f"ipakit-textgrid-{tier.local_name}-{index}"),
        tg.BoundarySide.BEFORE,
    )


def build(
    timings: Sequence[Timing | None],
    span_items: Sequence[tuple[tg.QualifiedName, Sequence[tuple[str, int, int]]]],
    point_items: Sequence[tuple[tg.QualifiedName, Sequence[tuple[str, int]]]],
    *,
    unit: str = "s",
) -> tg.Graph:
    """Build one graph whose declarations match the shipped profile vocabulary."""
    base_items = tuple(
        tg.Item(
            f"ipakit-textgrid-base-{index}",
            (
                ()
                if timing is None
                else (
                    tg.AttributeValue(
                        START,
                        tg.XsdType.DECIMAL,
                        format(Decimal(str(timing.start)), "f"),
                    ),
                    tg.AttributeValue(
                        DURATION,
                        tg.XsdType.DECIMAL,
                        format(Decimal(str(timing.duration)), "f"),
                    ),
                )
            ),
        )
        for index, timing in enumerate(timings)
    )
    clock_items = tuple(
        tg.Item(f"ipakit-textgrid-clock-{i}") for i in range(len(timings))
    )
    tiers: list[tg.Tier] = [
        tg.Tier(tg.TierDeclaration(BASE, "base"), base_items),
        tg.Tier(tg.TierDeclaration(CLOCK, "clock"), clock_items),
    ]
    declarations: list[RelationDeclaration] = [
        tg.SimpleRelationDeclaration(name("base-members"), BASE, BASE_ITEM),
        tg.SimpleRelationDeclaration(name("clock-members"), CLOCK, CLOCK_ITEM),
        tg.BipartiteRelationDeclaration(
            CLOCK_BINDING,
            BASE_ITEM,
            CLOCK_ITEM,
            left_endpoint=tg.RelationEndpointKind.BOUNDARY,
            right_endpoint=tg.RelationEndpointKind.BOUNDARY,
        ),
        tg.BipartiteRelationDeclaration(COVERAGE, BASE_ITEM, SPAN_ITEM),
        tg.BipartiteRelationDeclaration(
            POINT_COVERAGE,
            BASE_ITEM,
            POINT_ITEM,
            left_endpoint=tg.RelationEndpointKind.BOUNDARY,
        ),
    ]
    relations: list[tg.RelationInstance] = [
        tg.RelationInstance(
            CLOCK_BINDING, boundary(i, len(timings)), boundary(i, len(timings), CLOCK)
        )
        for i in range(len(timings) + 1)
    ]
    for tier_name, values in span_items:
        tiers.append(
            tg.Tier(
                tg.TierDeclaration(tier_name, tier_name.local_name),
                tuple(
                    tg.Item(
                        f"ipakit-textgrid-{tier_name.local_name}-{i}",
                        (tg.AttributeValue(SPELLING, tg.XsdType.STRING, value),),
                    )
                    for i, (value, _, _) in enumerate(values)
                ),
                (tg.AttributeValue(UNTIMED, tg.XsdType.BOOLEAN, "true"),),
            )
        )
        declarations.append(
            tg.SimpleRelationDeclaration(
                name(f"{tier_name.local_name}-members"), tier_name, SPAN_ITEM
            )
        )
        for item_index, (_, start, end) in enumerate(values):
            relations.extend(
                tg.RelationInstance(
                    COVERAGE, tg.ItemRef(BASE, base), tg.ItemRef(tier_name, item_index)
                )
                for base in range(start, end)
            )
    for tier_name, point_values in point_items:
        tiers.append(
            tg.Tier(
                tg.TierDeclaration(tier_name, tier_name.local_name),
                tuple(
                    tg.Item(
                        f"ipakit-textgrid-{tier_name.local_name}-{i}",
                        (tg.AttributeValue(SPELLING, tg.XsdType.STRING, value),),
                    )
                    for i, (value, _) in enumerate(point_values)
                ),
                (tg.AttributeValue(UNTIMED, tg.XsdType.BOOLEAN, "true"),),
            )
        )
        declarations.append(
            tg.SimpleRelationDeclaration(
                name(f"{tier_name.local_name}-members"), tier_name, POINT_ITEM
            )
        )
        relations.extend(
            tg.RelationInstance(
                POINT_COVERAGE,
                boundary(at, len(timings)),
                tg.ItemRef(tier_name, i),
            )
            for i, (_, at) in enumerate(point_values)
        )
    return tg.Graph(
        (tg.NamespaceDeclaration("ipakit-textgrid", NS),),
        tuple(tiers),
        tuple(declarations),
        tuple(relations),
        (
            tg.AttributeDeclaration(
                SPELLING, tg.AttributeDomain.ITEM, tg.XsdType.STRING
            ),
            tg.AttributeDeclaration(SCORE, tg.AttributeDomain.ITEM, tg.XsdType.DECIMAL),
            tg.AttributeDeclaration(
                UNIT, tg.AttributeDomain.DOCUMENT, tg.XsdType.STRING
            ),
            tg.AttributeDeclaration(START, tg.AttributeDomain.ITEM, tg.XsdType.DECIMAL),
            tg.AttributeDeclaration(
                DURATION, tg.AttributeDomain.ITEM, tg.XsdType.DECIMAL
            ),
            tg.AttributeDeclaration(
                UNTIMED, tg.AttributeDomain.TIER, tg.XsdType.BOOLEAN
            ),
        ),
        attributes=(tg.AttributeValue(UNIT, tg.XsdType.STRING, unit),),
    )


def clock(graph: tg.Graph) -> tg.ClockProfile:
    """Read the clock through its declarations so validation stays in tiergraph."""
    return tg.ClockProfile.from_data(
        graph,
        {
            "clock_tier": CLOCK.to_data(),
            "binding_relation": CLOCK_BINDING.to_data(),
            "rate_attribute": None,
            "unit_attribute": UNIT.to_data(),
            "tick_attribute": None,
            "gap_attribute": None,
            "untimed_attribute": UNTIMED.to_data(),
            "start_attribute": START.to_data(),
            "duration_attribute": DURATION.to_data(),
        },
    )
