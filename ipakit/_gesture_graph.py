"""Private gestural profile layered over the inventory-backed IPA graph.

The tier-graph kernel contains no articulatory vocabulary.  This profile reads
that vocabulary from :mod:`ipakit.tract` and merely declares where projected
occurrences live.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, cast

import tiergraph

from ._fact_builder import copy_fact_builder
from ._graph_facts import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
    Timing,
)
from ._ipa_graph import SEGMENT_TIER
from ._ipa_graph import declarations as ipa_declarations
from .features import IPAFeatures
from .segment import Segment
from .tract import TractPoint, constrictions

if TYPE_CHECKING:
    from ._containment_projection import ContainmentProjectionInput

GESTURE_TIER = "gesture"
TARGET_TIER = "articulatory-target"
PROJECTS_TO = "projects-to"
_ARTICULATORY_FEATURES = frozenset(
    {"kind", "arc", "offset", "articulator", "source-value", "target-index"}
)


def declarations(inventory: IPAFeatures) -> Declarations:
    """Declare gesture/target tiers without adding vocabulary to the kernel."""

    base = ipa_declarations(inventory)
    additions = tuple(
        FeatureDeclaration(name)
        for name in sorted(_ARTICULATORY_FEATURES - base._feature_names)
    )
    return Declarations(
        (
            *base.tiers,
            TierDeclaration(GESTURE_TIER, _ARTICULATORY_FEATURES),
            TierDeclaration(TARGET_TIER, _ARTICULATORY_FEATURES),
        ),
        (*base.features, *additions),
        (
            *base.relations,
            RelationDeclaration(
                PROJECTS_TO,
                source_tiers=frozenset({SEGMENT_TIER, GESTURE_TIER}),
                target_tiers=frozenset({GESTURE_TIER, TARGET_TIER}),
                source_arity=(1, 1),
                target_arity=(1, 1),
            ),
        ),
    )


def project(
    source: ContainmentProjectionInput,
    inventory: IPAFeatures,
    *,
    gesture_timing: Mapping[str, Sequence[Timing | None]] | None = None,
    target_timing: Mapping[str, Sequence[Timing | None]] | None = None,
) -> tiergraph.Graph:
    """Project segment occurrences through the inventory's tract declarations.

    Timing maps are keyed by source segment JSON Pointer and then by projected
    constriction index.  Their values decorate occurrences only; the reusable
    :class:`Segment` is never changed.
    """

    expected = ipa_declarations(inventory)
    if source.declarations != expected:
        raise ValueError("gesture projection requires this inventory's IPA graph")
    declared = declarations(inventory)
    gesture_timing = gesture_timing or {}
    target_timing = target_timing or {}
    from ._containment_projection import (
        ContainmentProjection,
        ContainmentProjectionInput,
    )

    builder, handles = copy_fact_builder(source, declared)

    for tick, node in enumerate(source.clock):
        segment_group = next((g for g in node.groups if g.tier == SEGMENT_TIER), None)
        if segment_group is not None:
            for segment_index, segment_event in enumerate(segment_group.events):
                source_ref = f"/clock/{tick}/{SEGMENT_TIER}/{segment_index}"
                value = segment_event.features.get("value")
                if not isinstance(value, Segment):
                    continue
                bundle = inventory.get_features(value.to_ipa())
                points = constrictions(inventory, bundle)
                for target_index, point in enumerate(points):
                    facts = _point_features(point, value.to_ipa(), target_index)
                    duration = segment_event.structural_duration or 0
                    gesture = builder.add_event(
                        GESTURE_TIER,
                        tick,
                        facts,
                        duration=duration,
                        timing=_timing_at(gesture_timing, source_ref, target_index),
                    )
                    target = builder.add_event(
                        TARGET_TIER,
                        tick,
                        facts,
                        duration=0,
                        timing=_timing_at(target_timing, source_ref, target_index),
                    )
                    builder.relate((handles[source_ref],), PROJECTS_TO, (gesture,))
                    builder.relate((gesture,), PROJECTS_TO, (target,))
    projection_input = cast(ContainmentProjectionInput, builder.build_input())
    return ContainmentProjection.from_input(
        projection_input, preserved_relation_names=frozenset({PROJECTS_TO})
    ).graph


def _point_features(point: TractPoint, source: str, index: int) -> dict[str, object]:
    return {
        "kind": "constriction",
        "arc": point.arc,
        "offset": point.offset,
        "articulator": point.articulator,
        "source-value": source,
        "target-index": index,
    }


def _timing_at(
    values: Mapping[str, Sequence[Timing | None]], source: str, index: int
) -> Timing | None:
    sequence = values.get(source, ())
    return sequence[index] if index < len(sequence) else None
