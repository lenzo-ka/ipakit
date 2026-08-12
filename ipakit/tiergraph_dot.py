"""Render tier graphs as deterministic Graphviz DOT.

The clock row is the authority for order: every coarse tick is printed from
left to right and joined to its successor. Events are emitted by clock tick,
tier declaration index, and event index; relation order is already canonical
in :class:`~ipakit._tiergraph.Graph`. No unordered collection controls output.

Refined gaps are drawn because ``gap_count`` distinguishes positions inside a
clock tick. Omitting them would make events and span endpoints at different
refined positions look coincident, contradicting the graph's ordering model.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ._tiergraph import EndpointKind, Graph

if TYPE_CHECKING:
    from .form import Form


def dumps(graph: Graph, *, include_empty_tiers: bool = False) -> str:
    """Return byte-stable DOT for ``graph``, including its complete clock.

    By default, tier rows answer "which tiers does this graph use?" and omit
    declared tiers with no events. Set ``include_empty_tiers`` to answer "which
    tiers does this model permit?" by drawing every declared tier.
    """
    if not isinstance(graph, Graph):
        raise TypeError("graph must be an ipakit tier graph")
    lines = [
        "digraph tiergraph {",
        "  graph [rankdir=TB];",
        '  node [fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize=9];',
        "",
        "  // The clock spine is the total order.",
        "  { rank=same;",
    ]
    positions: list[str] = []
    for tick, clock_node in enumerate(graph.clock):
        for gap in range(clock_node.gap_count):
            node_id = _position_id(tick, gap, clock_node.gap_count)
            label = str(tick) if clock_node.gap_count == 1 else f"{tick}.{gap}"
            lines.append(
                f'    {node_id} [shape=circle, width=0.34, fixedsize=true, label="{label}"];'
            )
            positions.append(node_id)
    for left, right in zip(positions, positions[1:], strict=False):
        lines.append(f"    {left} -> {right} [weight=100];")
    lines.extend(("  }", ""))

    tier_labels: list[str] = []
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
        lines.append(f"  subgraph tier_{_identifier(tier.name)} {{")
        lines.append("    rank=same;")
        lines.append(
            f'    {tier_label} [shape=plaintext, label="{_quote(tier.name)}"];'
        )
        for reference in references:
            event = graph.resolve(reference).event
            assert event is not None
            label = _event_label(tier.name, event.features)
            lines.append(
                f'    {_event_id(reference)} [shape=box, label="{_quote(label)}"];'
            )
        for left, right in zip(references, references[1:], strict=False):
            lines.append(
                f"    {_event_id(left)} -> {_event_id(right)} [style=invis, weight=20];"
            )
        lines.extend(("  }", ""))

    lines.append("  // Keep the clock and tier rows in declaration order.")
    row_anchors = [positions[0], *tier_labels]
    for upper, lower in zip(row_anchors, row_anchors[1:], strict=False):
        lines.append(f"  {upper} -> {lower} [style=invis, weight=100];")
    lines.append("")

    lines.append("  // Anchor every event and show its half-open structural extent.")
    for reference in _ordered_event_references(graph):
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
        start_id = _position_id(
            start.tick, start.gap, graph.clock[start.tick].gap_count
        )
        end_id = _position_id(end.tick, end.gap, graph.clock[end.tick].gap_count)
        event_id = _event_id(reference)
        lines.append(f"  {start_id} -> {event_id} [style=dotted, arrowhead=none];")
        lines.append(
            f'  {event_id} -> {end_id} [style=dashed, label="extent", constraint=false];'
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
    return dumps(form._graph, include_empty_tiers=include_empty_tiers)


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
        if isinstance(value, (str, int, float)):
            return str(value)
    return tier


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
