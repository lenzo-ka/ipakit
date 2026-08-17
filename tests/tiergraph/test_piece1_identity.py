from __future__ import annotations

from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder, add_event_copy, remove_events_copy
from ipakit._tiergraph_identity import DurableEventIdentity

from tiergraph import DurableItemRef, ItemRef


def _graph_with_shiftable_events():
    declarations = Declarations(
        (
            TierDeclaration("input", frozenset({"value"})),
            TierDeclaration("derived", frozenset({"value"})),
        ),
        (FeatureDeclaration("value"),),
        (),
    )
    builder = GraphBuilder(declarations)
    builder.append_input_atom("input", {"value": "clock owner"})
    builder.add_event("derived", 0, {"value": "remove"}, duration=0)
    builder.add_event("derived", 0, {"value": "survive"}, duration=0)
    return builder.build()


def test_durable_event_identity_projects_to_legacy_pointer_and_generic_coordinate():
    graph = _graph_with_shiftable_events()
    identity = DurableEventIdentity.build(graph)
    path = "/clock/0/derived/1"

    durable = identity.durable(path)

    assert isinstance(durable, DurableItemRef)
    assert identity.path(durable) == path
    assert isinstance(identity.coordinate(durable), ItemRef)


def test_survivor_identity_outlives_legacy_pointer_shift() -> None:
    graph = _graph_with_shiftable_events()
    before = DurableEventIdentity.build(graph)
    survivor = before.durable("/clock/0/derived/1")

    edited = remove_events_copy(graph, ("/clock/0/derived/0",))
    after = DurableEventIdentity.build(edited)

    assert after.path(survivor) == "/clock/0/derived/0"
    assert edited.at(after.path(survivor)).features["value"] == "survive"


def test_replay_preserves_all_survivor_ids_and_new_ids_do_not_collide() -> None:
    graph = _graph_with_shiftable_events()
    removed = graph.at("/clock/0/derived/0").durable_id
    survivor = graph.at("/clock/0/derived/1").durable_id

    edited = remove_events_copy(graph, ("/clock/0/derived/0",))
    edited = add_event_copy(edited, "derived", 0, {"value": "new"}, duration=0)
    ids = {
        event.durable_id
        for node in edited.clock
        for group in node.groups
        for event in group.events
    }

    assert survivor in ids
    assert removed not in ids
    assert len(ids) == len(set(ids))
