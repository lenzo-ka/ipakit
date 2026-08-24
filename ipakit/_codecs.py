"""Private graph renderers and edit codecs.

The tier graph deliberately has no notion of printable tiers.  A
``RenderProfile`` is the missing model/codec declaration: it names the ordered
lanes and the structured field each lane permits this codec to expose.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import tiergraph as tg

from ._graph_facts import Event, Relation

if TYPE_CHECKING:
    from .form import Form

ValueRenderer = Callable[[Event], str]


@dataclass(frozen=True)
class RenderLane:
    """One tier and its explicitly licensed surface projection."""

    tier: str
    feature: str
    renderer: ValueRenderer | None = None

    def render(self, event: Event) -> str:
        if self.renderer is not None:
            return self.renderer(event)
        value = event.features.get(self.feature, "")
        if self.feature == "value" and hasattr(value, "to_ipa"):
            return str(value.to_ipa())
        return str(value)


@dataclass(frozen=True)
class RenderProfile:
    """The complete ordered set of tiers a codec is allowed to spell."""

    lanes: tuple[RenderLane, ...]


def render_graph(form: Form, profile: RenderProfile) -> str:
    """Render only declared lanes, in input order where that order is retained."""

    graph = form._graph
    index = form.__dict__["_tiergraph_index"]
    containment = form._containment
    declared = set(containment.tier_names)
    unknown = [lane.tier for lane in profile.lanes if lane.tier not in declared]
    if unknown:
        raise ValueError(f"render profile names undeclared tiers: {unknown}")
    lane_by_tier = {lane.tier: lane for lane in profile.lanes}
    lane_order = {lane.tier: index for index, lane in enumerate(profile.lanes)}
    events: list[tuple[tuple[int, int, int], Event, RenderLane]] = []
    fallback = 0
    for path, event in index.event_items(containment, graph):
        tier = containment.event_tiers[path]
        lane = lane_by_tier.get(tier)
        if lane is not None:
            tick = int(path.split("/")[2])
            compatibility_index = event.features.get("compatibility-index")
            key = (
                (
                    int(compatibility_index)
                    if isinstance(compatibility_index, int)
                    else tick
                ),
                (0 if isinstance(compatibility_index, int) else lane_order[tier]),
                fallback,
            )
            events.append((key, event, lane))
            fallback += 1
    return "".join(lane.render(event) for _, event, lane in sorted(events))


def ipa_profile(*, exact: bool = False) -> RenderProfile:
    """The IPA profile's declared segment/boundary surface lanes."""

    field = "spelling" if exact else "value"
    return RenderProfile(
        (
            RenderLane("segment", field),
            RenderLane("zero", "symbol"),
            RenderLane("boundary", "symbol"),
        )
    )


def render_pinyin(
    graph: tg.Graph, syllable_tier: str = "syllable", tone_tier: str = "tone"
) -> str:
    """Place syllable-hosted tone on the nucleus selected by Pinyin spelling."""

    from .bridges.pinyin import PINYIN

    return PINYIN.render(graph, syllable_tier, tone_tier)


@dataclass(frozen=True)
class DeliveryProfile:
    """Surface choices for three projections of one prominence analysis."""

    host_tier: str = "syllable"
    word_tier: str = "word"
    prosody_tier: str = "prosody"
    boundary_tier: str = "boundary"
    spelling_feature: str = "spelling"


DEFAULT_DELIVERY_PROFILE = DeliveryProfile()


@dataclass(frozen=True)
class DeliveryRenderings:
    prosodic_signature: str
    segmental_signature: str
    orthographic_delivery: str


class DeliverySelectionError(ValueError):
    """Rendering cannot resolve exactly one declared delivery candidate."""


def _native_event_relations(graph: Form) -> tuple[Relation, ...]:
    """Expose authoritative native item relations in compatibility coordinates."""
    projection = graph._containment
    names = {native: old for old, native in projection.relation_names.items()}
    return tuple(
        Relation(
            tuple(projection.new_to_old[source] for source in relation.sources),
            names[relation.declaration],
            tuple(projection.new_to_old[target] for target in relation.targets),
        )
        for relation in graph._graph.polyadic_relations
        if relation.declaration in names
        and all(source in projection.new_to_old for source in relation.sources)
        and all(target in projection.new_to_old for target in relation.targets)
    )


def _selected_delivery(graph: Form, selected: object | None) -> str | None:
    relations = _native_event_relations(graph)
    alternatives = tuple(r for r in relations if r.name == "alternatives")
    candidates = tuple(
        target for relation in alternatives for target in relation.targets
    )
    if selected is not None:
        if not isinstance(selected, str) or selected not in candidates:
            raise DeliverySelectionError(
                f"delivery selection {selected!r} is not a candidate; candidates are {list(candidates)!r}"
            )
        return selected
    selections = [r.targets[0] for r in relations if r.name == "selects"]
    if len(selections) > 1:
        raise DeliverySelectionError("delivery graph has more than one selection")
    if selections:
        return selections[0]
    if candidates:
        raise DeliverySelectionError(
            f"delivery alternatives require a selection; candidates are {list(candidates)!r}"
        )
    return None


def render_delivery(
    graph: Form,
    selected: object | None = None,
    profile: DeliveryProfile = DEFAULT_DELIVERY_PROFILE,
    *,
    boundary_glyphs: Mapping[str, str] | None = None,
) -> DeliveryRenderings:
    """Project a selected alternative into house, segmental, and word surfaces."""

    index = graph.__dict__["_tiergraph_index"]
    table = {
        path: (int(path.split("/")[2]), graph._containment.event_tiers[path], event)
        for path, event in index.event_items(graph._containment, graph._graph)
    }
    relations = _native_event_relations(graph)
    selected = _selected_delivery(graph, selected)
    scoped: set[str] | None = None
    if selected is not None:
        scoped = {selected}
        changed = True
        while changed:
            changed = False
            for relation in relations:
                if relation.name not in {"contains", "realized-by"}:
                    continue
                if any(source in scoped for source in relation.sources):
                    before = len(scoped)
                    scoped.update(relation.targets)
                    changed |= len(scoped) != before

    hosts = sorted(
        (
            (tick, ref, event)
            for ref, (tick, tier, event) in table.items()
            if tier == profile.host_tier
        ),
        key=lambda item: (item[0], item[1]),
    )
    stress = {ref: "none" for _, ref, _ in hosts}
    for relation in relations:
        if relation.name != "associates-with" or len(relation.sources) != 1:
            continue
        source = relation.sources[0]
        if scoped is not None and source not in scoped:
            continue
        resolved = table.get(source)
        if resolved is None or resolved[1] != profile.prosody_tier:
            continue
        value = resolved[2].features.get("stress")
        if value in {"none", "primary", "secondary"}:
            for target in relation.targets:
                if target in stress:
                    stress[target] = str(value)
    slots = {"none": ".", "primary": "ˈ", "secondary": "ˌ"}
    boundaries = boundary_glyphs or {"word": "#", "phrase": "|", "utterance": "‖"}
    boundary_after: dict[int, list[str]] = {}
    for _, (tick, tier, event) in table.items():
        if tier != profile.boundary_tier:
            continue
        level = str(event.features.get("level", ""))
        glyph = boundaries.get(level)
        if glyph is not None:
            boundary_after.setdefault(tick, []).append(glyph)

    house: list[str] = []
    segmental: list[str] = []
    for tick, ref, event in hosts:
        slot = slots[stress[ref]]
        spelling = str(
            event.features.get(
                profile.spelling_feature, event.features.get("value", "")
            )
        )
        house.append(slot)
        segmental.append(slot + spelling)
        for glyph in boundary_after.get(tick + (event.structural_duration or 0), ()):
            house.append(glyph)
            segmental.append(f" {glyph} ")

    # Words are rendered from their contained syllables when that relation is
    # available; this permits prominence inside a word without mutating it.
    word_refs = [
        ref for ref, (_, tier, _) in table.items() if tier == profile.word_tier
    ]
    orthographic: list[str] = []
    for word_ref in word_refs:
        children = [
            target
            for relation in relations
            if relation.name == "contains" and word_ref in relation.sources
            for target in relation.targets
            if target in stress
        ]
        if children:
            pieces = []
            for child in children:
                event = table[child][2]
                piece = str(
                    event.features.get(
                        profile.spelling_feature, event.features.get("value", "")
                    )
                )
                pieces.append(
                    piece.upper()
                    if stress[child] == "primary"
                    else piece.capitalize() if stress[child] == "secondary" else piece
                )
            orthographic.append("".join(pieces))
        else:
            event = table[word_ref][2]
            spelling = str(
                event.features.get(
                    profile.spelling_feature, event.features.get("value", "")
                )
            )
            orthographic.append(spelling)
    return DeliveryRenderings(
        "".join(house), "".join(segmental).strip(), " ".join(orthographic)
    )
