from __future__ import annotations

from pathlib import Path

from ipakit._containment_projection import (
    ContainmentProjection,
    ContainmentProjectionInput,
)
from ipakit._graph_facts import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)

import tiergraph as tg

GOLDEN = Path(__file__).with_name("choice_selection_v1.json")


def _choice_selection_graph(*, selection_first: bool = False) -> tg.Graph:
    declarations = Declarations(
        (TierDeclaration("analysis"), TierDeclaration("delivery")),
        (),
        (
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
        ),
    )
    clock = (
        ClockNode(
            groups=(
                EventGroup("analysis", (Event({}),)),
                EventGroup("delivery", (Event({}), Event({}))),
            )
        ),
        ClockNode(),
    )
    source = "/clock/0/analysis/0"
    first, second = "/clock/0/delivery/0", "/clock/0/delivery/1"
    alternatives = Relation((source,), "alternatives", (first, second))
    selects = Relation((source,), "selects", (second,))
    facts = ContainmentProjectionInput.from_facts(
        declarations,
        clock,
        (selects, alternatives) if selection_first else (alternatives, selects),
    )
    return ContainmentProjection.from_input(facts).graph


def test_choice_selection_native_lowering_matches_canonical_wire() -> None:
    golden = GOLDEN.read_text()
    membership_first = _choice_selection_graph()
    selection_first = _choice_selection_graph(selection_first=True)

    assert selection_first == membership_first
    assert tg.wire.dumps(membership_first) == golden
    assert tg.wire.dumps(selection_first) == golden
