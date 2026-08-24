"""Render tier graphs as deterministic Graphviz DOT."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .form import Form


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


def _identifier(value: str) -> str:
    return "".join(
        character if character.isalnum() else f"_{ord(character):x}_"
        for character in value
    )
