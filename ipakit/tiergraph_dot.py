"""Render tier graphs as deterministic Graphviz DOT.

The clock row is the authority for order: every coarse tick is printed from
left to right and joined to its successor. Each event has a trigger edge from
the clock position it occupies; that edge is what "edge-triggered" means here,
and its layout weight registers the event vertically with that moment. Events
are emitted by tier declaration index, clock tick, and event index; relation
order is already canonical in :class:`~ipakit._tiergraph.Graph`. No unordered
collection controls output.

Refined gaps are drawn because ``gap_count`` distinguishes positions inside a
clock tick. Omitting them would make events and span endpoints at different
refined positions look coincident, contradicting the graph's ordering model.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from ._tiergraph import EndpointKind, Graph

if TYPE_CHECKING:
    from .form import Form


def dumps(graph: Graph, *, include_empty_tiers: bool = False) -> str:
    """Return byte-stable DOT for ``graph``, including its complete clock.

    By default, tier rows answer "which tiers does this graph use?" and omit
    declared tiers with no events. Set ``include_empty_tiers`` to answer "which
    tiers does this model permit?" by drawing every declared tier.
    """
    if not isinstance(graph, Graph) and not all(
        hasattr(graph, name)
        for name in ("clock", "declarations", "relations", "resolve", "position")
    ):
        raise TypeError("graph must be an ipakit tier graph")
    lines = [
        "digraph tiergraph {",
        '  graph [rankdir=TB, newrank=true, ranksep="0.62 equally", nodesep=0.28, splines=line];',
        '  node [fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize=9];',
        "",
        "  // The clock spine is the total order.",
        "  { rank=same;",
        '    score_start_clock [shape=plaintext, label="clock"];',
    ]
    positions: list[str] = []
    for tick, clock_node in enumerate(graph.clock):
        for gap in range(clock_node.gap_count):
            node_id = _position_id(tick, gap, clock_node.gap_count)
            label = str(tick) if clock_node.gap_count == 1 else f"{tick}.{gap}"
            lines.append(
                f"    {node_id} [shape=circle, width=0.46, fixedsize=true, "
                f'group="time_{len(positions)}", label="{label}"];'
            )
            positions.append(node_id)
    for left, right in zip(positions, positions[1:], strict=False):
        lines.append(f"    {left} -> {right} [weight=100];")
    lines.extend(("  }", ""))

    tier_labels: list[str] = []
    event_starts: dict[str, str] = {}
    tier_slots: list[list[str]] = []
    position_indexes = {node_id: index for index, node_id in enumerate(positions)}
    for tier in graph.declarations.tiers:
        references: list[str] = []
        for tick, clock_node in enumerate(graph.clock):
            group = next(
                (
                    candidate
                    for candidate in clock_node.groups
                    if candidate.tier == tier.name
                ),
                None,
            )
            if group is not None:
                references.extend(
                    f"/clock/{tick}/{_pointer_escape(tier.name)}/{index}"
                    for index in range(len(group.events))
                )
        if not references and not include_empty_tiers:
            continue
        tier_label = f"tier_label_{_identifier(tier.name)}"
        tier_labels.append(tier_label)
        references_at: list[list[str]] = [[] for _ in positions]
        for reference in references:
            start_id, _ = _event_position_ids(graph, reference)
            event_starts[reference] = start_id
            references_at[position_indexes[start_id]].append(reference)
        slots: list[str] = []
        lines.append(f"  subgraph tier_{_identifier(tier.name)} {{")
        lines.append("    rank=same;")
        lines.append(
            f'    {tier_label} [shape=plaintext, label="{_quote(tier.name)}"];'
        )
        for position_index, position_references in enumerate(references_at):
            if position_references:
                slot = _event_id(position_references[0])
                for reference in position_references:
                    event = graph.resolve(reference).event
                    assert event is not None
                    label = _event_label(tier.name, event.features)
                    lines.append(
                        f'    {_event_id(reference)} [shape=box, group="time_{position_index}", '
                        f'label="{_quote(label)}"];'
                    )
            else:
                slot = f"guide_{_identifier(tier.name)}_{position_index}"
                lines.append(
                    f'    {slot} [shape=point, width=0.01, label="", '
                    f'group="time_{position_index}", style=invis];'
                )
            slots.append(slot)
        for left, right in zip(slots, slots[1:], strict=False):
            lines.append(f"    {left} -> {right} [style=invis, weight=100];")
        for left, right in zip(references, references[1:], strict=False):
            lines.append(
                f"    {_event_id(left)} -> {_event_id(right)} "
                '[color="#888888", penwidth=0.8, arrowsize=0.55, constraint=false];'
            )
        for reference in references:
            start_id, end_id = _event_position_ids(graph, reference)
            if start_id == end_id:
                continue
            lines.append(
                f"    {_event_id(reference)} -> {slots[position_indexes[end_id]]} "
                '[xlabel="extent", color="#777777", style=dashed, arrowhead=tee, '
                "arrowsize=0.6, fontsize=8, constraint=false];"
            )
        lines.extend(("  }", ""))
        tier_slots.append(slots)

    lines.append("  // The score brace joins lane starts in declaration order.")
    row_anchors = ["score_start_clock", *tier_labels]
    for upper, lower in zip(row_anchors, row_anchors[1:], strict=False):
        lines.append(
            f'  {upper} -> {lower} [dir=none, color="#333333", penwidth=2.4, weight=100];'
        )
    lines.append("")

    lines.append("  // Register every lane to the clock's time columns.")
    for position_index, clock_id in enumerate(positions):
        column = [clock_id, *(slots[position_index] for slots in tier_slots)]
        for upper, lower in zip(column, column[1:], strict=False):
            lines.append(
                f"  {upper} -> {lower} [style=invis, weight=1000, arrowhead=none];"
            )
    lines.append("")

    lines.append("  // Trigger every event from the clock position it occupies.")
    for reference in _ordered_event_references(graph):
        lines.append(
            f"  {event_starts[reference]} -> {_event_id(reference)} "
            '[color="#2f6f9f", penwidth=1.35, arrowsize=0.65, weight=100];'
        )

    if graph.relations:
        lines.extend(("", "  // Declared relations."))
    for relation in graph.relations:
        for source in relation.sources:
            for target in relation.targets:
                lines.append(
                    f"  {_endpoint_id(graph, source)} -> {_endpoint_id(graph, target)} "
                    f'[label="{_quote(relation.name)}", color="#5555aa", constraint=false];'
                )
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_dot(form: Form, *, include_empty_tiers: bool = False) -> str:
    """Return DOT for a public :class:`~ipakit.Form`.

    Rendered from the one authoritative tiergraph graph (``form._graph``) by the
    sibling :mod:`tiergraph_dot` renderer, driven by ipakit-supplied
    presentation hooks and a per-item clock binding. By default, rows show which
    tiers the form uses; set ``include_empty_tiers`` to show which tiers its
    model permits.
    """
    from .form import Form

    if not isinstance(form, Form):
        raise TypeError("form must be an ipakit.Form")
    return _render_via_sibling(form._graph, include_empty_tiers=include_empty_tiers)


# --- Sibling-renderer migration ------------------------------------------------
#
# ipakit no longer emits DOT itself: it hands the authoritative graph to the
# sibling ``tiergraph_dot.dumps`` with three presentation hooks and a clock
# binding. The hooks recover ipakit's phonetic labels, event ids, and tier
# names; the binding places every non-clock item on the structural clock spine.

_CONTAINMENT_NS = "https://ipakit.dev/tiergraph/containment-projection/v1"


def _render_via_sibling(graph: Any, *, include_empty_tiers: bool) -> str:
    import json

    import tiergraph as tg
    import tiergraph_dot as sibling
    from tiergraph import ClockPosition, ItemRef, QualifiedName

    from .segment import Constituent, Segment, Sense

    inventory = None  # resolved lazily; only segment labels need it

    # Index every item by identity: its ItemRef, durable id, and flat attributes.
    ref_of: dict[int, Any] = {}
    item_by_ref: dict[Any, Any] = {}
    attrs_of: dict[int, dict[str, str]] = {}
    durable_of: dict[int, str] = {}
    for tier in graph.tiers:
        tier_qname = tier.declaration.name
        for index, item in enumerate(tier.items):
            reference = ItemRef(tier_qname, index)
            ref_of[id(item)] = reference
            item_by_ref[reference] = item
            attrs_of[id(item)] = {
                value.name.local_name: value.lexical for value in item.attributes
            }
            durable_of[id(item)] = item.durable_id

    clock_tier = next(
        tier.declaration.name
        for tier in graph.tiers
        if tier.declaration.long_name == "clock"
    )

    # Parent -> children, from the projected containment ("contains-N") relations.
    child_map: dict[Any, list[Any]] = {}
    for relation in graph.polyadic_relations:
        if relation.declaration.local_name.startswith("contains-"):
            for source in relation.sources:
                child_map.setdefault(source, []).extend(relation.targets)

    def _position(pointer: str) -> ClockPosition:
        # "/clock/T" (coarse, gap 0) or "/clock/T/gaps/G" (refined).
        parts = pointer.split("/")
        gap = int(parts[4]) if len(parts) > 4 else 0
        return ClockPosition(int(parts[2]), gap)

    span_memo: dict[Any, tuple[ClockPosition, ClockPosition]] = {}

    def _span(reference: Any) -> tuple[ClockPosition, ClockPosition]:
        cached = span_memo.get(reference)
        if cached is not None:
            return cached
        item = item_by_ref[reference]
        attributes = attrs_of[id(item)]
        if "span-start" in attributes:
            # Interval item (syllable/mora/word/morph): explicit span endpoints.
            result = (
                _position(attributes["span-start"]),
                _position(attributes["span-end"]),
            )
        elif "structural-duration" in attributes:
            # Flat item (segment/boundary): durable-id tick + structural extent.
            tick = int(durable_of[id(item)].split("/")[2])
            duration = int(attributes["structural-duration"])
            result = (ClockPosition(tick, 0), ClockPosition(tick + duration, 0))
        else:
            # Structural container (e.g. an utterance): span its descendants.
            spans = [_span(child) for child in child_map.get(reference, ())]
            key = lambda position: (position.tick, position.gap)  # noqa: E731
            result = (
                min((start for start, _ in spans), key=key),
                max((end for _, end in spans), key=key),
            )
        span_memo[reference] = result
        return result

    def tier_name(tier: Any) -> str:
        return cast(str, tier.declaration.long_name)

    def node_id(reference: Any) -> str:
        return "event_" + _identifier(durable_of[id(item_by_ref[reference])])

    def item_label(item: Any, tier: Any) -> str | None:
        attributes = attrs_of[id(item)]
        token: str | None = None
        if attributes.get("spelling", "").strip():
            token = attributes["spelling"]
        elif attributes.get("symbol", "").strip():
            token = attributes["symbol"]
        elif "segment-json" in attributes:
            nonlocal inventory
            if inventory is None:
                from .form import _default

                inventory = _default(None)
            encoded = json.loads(attributes["segment-json"])
            # Bare display grapheme: the segment spelled WITHOUT its prosody,
            # mirroring ``Unit.core`` so a stressed "ˈa" still labels as "a".
            segment = Segment(
                tuple(
                    Constituent(
                        part["base"],
                        tuple(part["modifiers"]),
                        tuple(part["approach"]),
                    )
                    for part in encoded["constituents"]
                ),
                tuple(Sense(value) for value in encoded["junctures"]),
                (),
                _features=inventory,
            )
            token = segment.to_ipa()
        elif attributes.get("text", "").strip():
            token = attributes["text"]
        if token is None:
            # Interval items carry no presentation token: label with the tier.
            return cast(str, tier.declaration.long_name)
        prominence = attributes.get("prominence")
        if isinstance(prominence, str):
            token += f"\nprominence: {prominence}"
        return token

    def binding(item: Any) -> tuple[ClockPosition, ClockPosition]:
        return _span(ref_of[id(item)])

    def relation_name(relation: Any) -> str | None:
        # Containment is one polyadic per depth (contains-0, contains-1, …);
        # the embedded renderer drew it as the single bipartite name "contains".
        if relation.declaration.local_name.startswith("contains"):
            return "contains"
        return None

    def relation_style(relation: Any) -> str | None:
        if relation.declaration.local_name.startswith("contains"):
            return "bipartite"
        return None

    clock = tg.ClockProfile.from_position_values(
        graph,
        clock_tier,
        tick_attribute=QualifiedName(_CONTAINMENT_NS, "tick"),
        gap_attribute=QualifiedName(_CONTAINMENT_NS, "gap"),
        collapse_shared_boundaries=True,
    )
    presentation = sibling.DotPresentation(
        tier_name=tier_name,
        node_id=node_id,
        item_label=item_label,
        relation_name=relation_name,
        relation_style=relation_style,
    )
    # Annotate the result so mypy is satisfied whether or not tiergraph_dot is
    # resolvable in the lint environment: with it installed dumps returns str
    # (no cast needed); without it dumps is Any, which is assignable to this
    # str-typed binding, so the return is not "Any".
    rendered: str = sibling.dumps(
        graph,
        clock=clock,
        presentation=presentation,
        binding=binding,
        include_empty_tiers=include_empty_tiers,
    )
    return rendered


def _ordered_event_references(graph: Graph) -> tuple[str, ...]:
    references: list[str] = []
    for tick, clock_node in enumerate(graph.clock):
        for tier in graph.declarations.tiers:
            group = next(
                (
                    candidate
                    for candidate in clock_node.groups
                    if candidate.tier == tier.name
                ),
                None,
            )
            if group is not None:
                references.extend(
                    f"/clock/{tick}/{_pointer_escape(tier.name)}/{index}"
                    for index in range(len(group.events))
                )
    return tuple(references)


def _event_label(tier: str, features: Mapping[str, Any]) -> str:
    for name in ("spelling", "symbol", "value"):
        value = features.get(name)
        if isinstance(value, (str, int, float)) and str(value).strip():
            label = str(value)
            prominence = features.get("prominence")
            if isinstance(prominence, str):
                label += f"\nprominence: {prominence}"
            return label
    return tier


def _event_position_ids(graph: Graph, reference: str) -> tuple[str, str]:
    resolved = graph.resolve(reference)
    assert resolved.event is not None
    event = resolved.event
    if event.span is not None:
        start = graph.position(event.span.start, span_endpoint=True)
        end = graph.position(event.span.end, span_endpoint=True)
    else:
        start = graph.position(f"/clock/{resolved.tick}")
        end_tick = resolved.tick + (event.structural_duration or 0)
        end = graph.position(f"/clock/{end_tick}")
    return (
        _position_id(start.tick, start.gap, graph.clock[start.tick].gap_count),
        _position_id(end.tick, end.gap, graph.clock[end.tick].gap_count),
    )


def _endpoint_id(graph: Graph, pointer: str) -> str:
    resolved = graph.resolve(pointer)
    if resolved.kind is EndpointKind.EVENT:
        return _event_id(pointer)
    return _position_id(
        resolved.tick, resolved.gap or 0, graph.clock[resolved.tick].gap_count
    )


def _position_id(tick: int, gap: int, gap_count: int) -> str:
    return f"clock_{tick}" if gap_count == 1 else f"clock_{tick}_gap_{gap}"


def _event_id(pointer: str) -> str:
    return "event_" + _identifier(pointer)


def _identifier(value: str) -> str:
    return "".join(
        character if character.isalnum() else f"_{ord(character):x}_"
        for character in value
    )


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
