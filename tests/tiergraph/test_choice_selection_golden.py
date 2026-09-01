"""The canonical wire form of a choice-selection graph, pinned.

``choice_selection_v1.json`` is the golden. Its point is that the wire
form is order-independent: the same graph built membership-first and
selection-first must dump to the same bytes, so the file is asserted
against twice rather than once.

Regenerate it from this module's own builder, which is what produced it::

    PYTHONHASHSEED=0 python -c "import sys; sys.path.insert(0, '.'); \
        from tests.tiergraph.test_choice_selection_golden import \
            _choice_selection_graph, GOLDEN; \
        import tiergraph as tg; \
        GOLDEN.write_text(tg.wire.dumps(_choice_selection_graph()))"

The other tiergraph baselines document their regeneration in
``baselines/README.md`` and this one did not, which is worth more than it
looks: a golden nobody can regenerate is a fixture that eventually gets
edited by hand to make a test pass, and a hand-edited golden asserts
whatever was typed rather than whatever the code produces.

It will need regenerating when the tiergraph pin moves. The file carries
two attribute declarations on the ``position`` domain, and that value is
dropped from the wire schema at 0.2.0, so the declarations become
``boundary`` and these bytes change with them.
"""

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
