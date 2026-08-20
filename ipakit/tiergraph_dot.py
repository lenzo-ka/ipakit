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

    By default, rows show which tiers the form uses. Set
    ``include_empty_tiers`` to show which tiers its model permits.
    """
    from .form import Form

    if not isinstance(form, Form):
        raise TypeError("form must be an ipakit.Form")
    index = form.__dict__["_tiergraph_index"]
    # Bind the cached phonetic presentation to the live authoritative corpus.
    for path in index.containment_input.refs:
        form._graph.resolve_item(__import__("tiergraph").DurableItemRef(path))
    return cast(str, index.dot_with_empty_tiers if include_empty_tiers else index.dot)


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
