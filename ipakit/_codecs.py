"""Private graph renderers and edit codecs.

The tier graph deliberately has no notion of printable tiers.  A
``RenderProfile`` is the missing model/codec declaration: it names the ordered
lanes and the structured field each lane permits this codec to expose.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._tiergraph import Event, Graph, _escape

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


def render_graph(form: Any, profile: RenderProfile) -> str:
    """Render only declared lanes, in input order where that order is retained."""

    if isinstance(form, Graph):
        return _render_scaffold(form, profile)
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


def _render_scaffold(graph: Graph, profile: RenderProfile) -> str:
    """Temporary non-Form codec bridge; construction callers retire by P9."""
    declared = {tier.name for tier in graph.declarations.tiers}
    unknown = [lane.tier for lane in profile.lanes if lane.tier not in declared]
    if unknown:
        raise ValueError(f"render profile names undeclared tiers: {unknown}")
    lane_by_tier = {lane.tier: lane for lane in profile.lanes}
    lane_order = {lane.tier: index for index, lane in enumerate(profile.lanes)}
    events = []
    fallback = 0
    for tick, node in enumerate(graph.clock):
        for group in node.groups:
            lane = lane_by_tier.get(group.tier)
            if lane is None:
                continue
            for event in group.events:
                compatibility_index = event.features.get("compatibility-index")
                key = (
                    (
                        int(compatibility_index)
                        if isinstance(compatibility_index, int)
                        else tick
                    ),
                    (
                        0
                        if isinstance(compatibility_index, int)
                        else lane_order[group.tier]
                    ),
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
    graph: Graph, syllable_tier: str = "syllable", tone_tier: str = "tone"
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


def _event_table(graph: Graph) -> dict[str, tuple[int, str, Event]]:
    return {
        f"/clock/{tick}/{_escape(group.tier)}/{index}": (tick, group.tier, event)
        for tick, node in enumerate(graph.clock)
        for group in node.groups
        for index, event in enumerate(group.events)
    }


def _selected_delivery(graph: Graph, selected: object | None) -> str | None:
    alternatives = [r for r in graph.relations if r.name == "alternatives"]
    candidates = tuple(
        target for relation in alternatives for target in relation.targets
    )
    if selected is not None:
        if not isinstance(selected, str) or selected not in candidates:
            raise DeliverySelectionError(
                f"delivery selection {selected!r} is not a candidate; candidates are {list(candidates)!r}"
            )
        return selected
    selections = [r.targets[0] for r in graph.relations if r.name == "selects"]
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
    graph: Graph,
    selected: object | None = None,
    profile: DeliveryProfile = DEFAULT_DELIVERY_PROFILE,
    *,
    boundary_glyphs: Mapping[str, str] | None = None,
) -> DeliveryRenderings:
    """Project a selected alternative into house, segmental, and word surfaces."""

    table = _event_table(graph)
    selected = _selected_delivery(graph, selected)
    scoped: set[str] | None = None
    if selected is not None:
        scoped = {selected}
        changed = True
        while changed:
            changed = False
            for relation in graph.relations:
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
    for relation in graph.relations:
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
            for relation in graph.relations
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


@dataclass(frozen=True)
class SignatureEdit:
    """A graph edit result plus the ordinary graph references it created."""

    graph: Graph
    created: tuple[str, ...]
    hosts: tuple[str, ...]
    boundaries: tuple[str, ...] = ()


def apply_signature(
    graph: Graph,
    text: str,
    inventory: Any,
    hosts: Sequence[str] | None = None,
    *,
    host_tier: str = "syllable",
) -> SignatureEdit:
    """Apply a validated signature as stress events, never as a stored tier."""

    from ._ipa_graph import BOUNDARY_TIER, PROSODY_TIER, parse_signature
    from ._tiergraph_builder import _copy_builder

    signature = parse_signature(text, inventory)
    table = _event_table(graph)
    if hosts is None:
        hosts = tuple(
            ref
            for ref, (_, tier, _) in sorted(
                table.items(), key=lambda item: (item[1][0], item[0])
            )
            if tier == host_tier
        )
    hosts = tuple(hosts)
    if len(signature.stress) != len(hosts):
        raise ValueError(
            f"signature slot count {len(signature.stress)} does not equal host count {len(hosts)}"
        )
    for host in hosts:
        if host not in table:
            raise ValueError(f"signature host does not exist: {host}")
    builder, copied = _copy_builder(graph)
    made = []
    for host, value in zip(hosts, signature.stress, strict=True):
        tick = table[host][0]
        event = builder.add_event(
            PROSODY_TIER,
            tick,
            {"stress": value, "provenance": "prosodic-signature-edit"},
            duration=0,
        )
        builder.relate((event,), "associates-with", (copied[host],))
        # Retain the previous fact as provenance rather than overwriting it.
        previous = [
            relation.sources[0]
            for relation in graph.relations
            if relation.name == "associates-with"
            and host in relation.targets
            and table.get(relation.sources[0], (None, None, None))[1] == PROSODY_TIER
        ]
        if previous:
            builder.relate((event,), "derived-from", (copied[previous[-1]],))
        made.append(event)
    existing_boundaries = [
        (ref, tick, event)
        for ref, (tick, tier, event) in sorted(
            table.items(), key=lambda item: (item[1][0], item[0])
        )
        if tier == BOUNDARY_TIER and event.features.get("level") != "syllable"
    ]
    if signature.boundaries and len(signature.boundaries) != len(existing_boundaries):
        raise ValueError(
            f"signature boundary count {len(signature.boundaries)} does not equal "
            f"declared boundary count {len(existing_boundaries)}"
        )
    for glyph, (old_ref, tick, _old) in zip(
        signature.boundaries, existing_boundaries, strict=True
    ):
        declared = inventory.separators.get(glyph) or inventory.diacritics.get(glyph)
        if declared is None or "level" not in declared.features:
            raise ValueError(f"undeclared signature boundary: {glyph!r}")
        event = builder.add_event(
            BOUNDARY_TIER,
            tick,
            {
                "symbol": glyph,
                "level": declared.features["level"],
                "provenance": "prosodic-signature-edit",
            },
            duration=0,
        )
        builder.relate((event,), "derived-from", (copied[old_ref],))
    edited = builder.build()
    created = tuple(
        ref
        for ref, (_, tier, event) in _event_table(edited).items()
        if tier in {PROSODY_TIER, BOUNDARY_TIER}
        and event.features.get("provenance") == "prosodic-signature-edit"
    )
    boundary_refs = tuple(
        ref for ref in created if _event_table(edited)[ref][1] == BOUNDARY_TIER
    )
    return SignatureEdit(edited, created, hosts, boundary_refs)
