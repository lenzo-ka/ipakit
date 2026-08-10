"""IPA profile declarations over the generic tier-graph kernel.

The inventory supplies feature and mark vocabulary, while this module states
the graph roles that the inventory intentionally does not: clock behavior,
semantic hosts, containment, delivery alternatives, and provenance links.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from ._tiergraph import (
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from .features import IPAFeatures

SEGMENT_TIER = "segment"
ZERO_TIER = "zero"
BOUNDARY_TIER = "boundary"
PROSODY_TIER = "prosody"
_PROFILE_FEATURES = frozenset(
    {"value", "spelling", "symbol", "provenance", "input", "phantom", "class"}
)


class OccurrenceKind(StrEnum):
    """Input occurrence kinds whose clock effects differ."""

    SEGMENT = "segment"
    ZERO = "zero"
    BOUNDARY = "boundary"
    ATTACHED_ATTRIBUTE = "attached-attribute"
    INPUT_SILENCE = "input-silence"
    DERIVED_SILENCE = "derived-silence"


@dataclass(frozen=True)
class ClockTreatment:
    """Declared effect of an IPA occurrence on the input-owned clock."""

    consumes_span: bool
    refines_tick: bool = False
    structural_duration: int = 0


CLOCK_TREATMENTS: Mapping[OccurrenceKind, ClockTreatment] = {
    OccurrenceKind.SEGMENT: ClockTreatment(True, structural_duration=1),
    OccurrenceKind.ZERO: ClockTreatment(True, structural_duration=1),
    OccurrenceKind.BOUNDARY: ClockTreatment(False, refines_tick=True),
    OccurrenceKind.ATTACHED_ATTRIBUTE: ClockTreatment(False),
    OccurrenceKind.INPUT_SILENCE: ClockTreatment(True, structural_duration=1),
    OccurrenceKind.DERIVED_SILENCE: ClockTreatment(False),
}


def declarations(inventory: IPAFeatures) -> Declarations:
    """Build IPA declarations from one inventory.

    Feature names and their contribution modes come from ``ipa.xml`` so a
    supplement or inventory extension becomes graph-addressable without a
    second feature list in Python.
    """

    inventory_names = frozenset(inventory.feature_order)
    feature_names = inventory_names | _PROFILE_FEATURES
    prosodic = inventory.features_by_mode.get("prosodic", frozenset())
    structural = inventory.features_by_mode.get("structural", frozenset())
    common = frozenset({"value", "spelling", "provenance", "input", "phantom"})
    declared_tier = inventory.features.get("tier")
    hierarchy_tiers = tuple(
        dict.fromkeys(
            [
                *inventory.features["level"].values,
                *(declared_tier.values if declared_tier is not None else ()),
                "foot",
            ]
        )
    )
    tiers = (
        *(TierDeclaration(name, common) for name in hierarchy_tiers),
        TierDeclaration(SEGMENT_TIER, common | inventory_names | frozenset({"class"})),
        TierDeclaration(ZERO_TIER, common | frozenset({"symbol"})),
        TierDeclaration(BOUNDARY_TIER, common | structural | frozenset({"symbol"})),
        TierDeclaration(PROSODY_TIER, common | prosodic | frozenset({"symbol"})),
        TierDeclaration("delivery", common),
        TierDeclaration("analysis", common),
    )
    event_kinds = frozenset({EndpointKind.EVENT})
    relations = (
        RelationDeclaration("contains", acyclic=True, containment=True),
        RelationDeclaration(
            "associates-with",
            source_tiers=frozenset({PROSODY_TIER}),
            target_tiers=prosody_host_tiers(inventory),
        ),
        RelationDeclaration("realized-by"),
        RelationDeclaration("derived-from", acyclic=True),
        RelationDeclaration(
            "inserts",
            source_kinds=frozenset(
                {EndpointKind.COARSE_TICK, EndpointKind.REFINED_GAP}
            ),
            target_kinds=event_kinds,
            source_arity=(1, 1),
        ),
        RelationDeclaration(
            "alternatives", ordered=False, choice=True, target_arity=(1, None)
        ),
        RelationDeclaration(
            "selects",
            ordered=False,
            source_arity=(1, 1),
            target_arity=(1, 1),
            member_of="alternatives",
        ),
    )
    return Declarations(
        tiers,
        tuple(FeatureDeclaration(name) for name in sorted(feature_names)),
        relations,
    )


def prosody_host_tiers(inventory: IPAFeatures) -> frozenset[str]:
    """Return semantic hosts without treating written placement as attachment."""

    boundary_levels = set(inventory.features["level"].values)
    return frozenset(boundary_levels | {"foot", SEGMENT_TIER, PROSODY_TIER})


@dataclass(frozen=True)
class Signature:
    """Stress slots and boundary glyphs decoded from the house notation."""

    stress: tuple[str, ...]
    boundaries: tuple[str, ...]


def parse_signature(text: str, inventory: IPAFeatures) -> Signature:
    """Decode the declared signature alphabet without reading IPA segments."""

    stress_values = {
        symbol: inventory.diacritics[symbol].features["stress"]
        for symbol in inventory.stress_markers
    }
    unmarked_stress_values = set(inventory.features["stress"].values) - set(
        stress_values.values()
    )
    if len(unmarked_stress_values) != 1:
        raise ValueError("stress signature requires exactly one unmarked value")
    stress_values[inventory.syllable_break] = unmarked_stress_values.pop()
    boundary_symbols = {
        symbol
        for symbol, phone in {**inventory.separators, **inventory.diacritics}.items()
        if "level" in phone.features
        and phone.features["level"] != "syllable"
        and phone.features.get("linking") != "+"
    }
    slots: list[str] = []
    boundaries: list[str] = []
    for symbol in text:
        if symbol in stress_values:
            slots.append(stress_values[symbol])
        elif symbol in boundary_symbols:
            boundaries.append(symbol)
        elif not symbol.isspace():
            raise ValueError(f"undeclared prosodic signature symbol: {symbol!r}")
    return Signature(tuple(slots), tuple(boundaries))


def assign_signature(
    text: str, hosts: Sequence[str], inventory: IPAFeatures
) -> tuple[tuple[str, str], ...]:
    """Pair every signature slot with exactly one selected semantic host."""

    signature = parse_signature(text, inventory)
    if len(signature.stress) != len(hosts):
        raise ValueError(
            f"signature slot count {len(signature.stress)} does not equal "
            f"host count {len(hosts)}"
        )
    return tuple(zip(hosts, signature.stress, strict=True))
