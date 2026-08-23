"""Lane M decisions that were deliberately left open by implementation lanes."""

from __future__ import annotations

import hashlib
import json

import pytest
from ipakit import FormBuilder, IPAFeatures
from ipakit._cmu_graph import read as read_cmu
from ipakit._codecs import DeliverySelectionError, render_delivery
from ipakit._ipa_graph import declarations as ipa_declarations
from ipakit._panphon_graph import fingerprint
from ipakit._tiergraph import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FeatureDeclaration,
    Graph,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder
from ipakit._tiergraph_json import Model, dumps

import tiergraph


def test_declarations_are_referenced_and_fingerprinted_over_canonical_identity() -> (
    None
):
    identity = {"provider": "panphon", "features": ("syl", "son"), "domain": [-1, 0, 1]}
    canonical = json.dumps(identity, separators=(",", ":"), sort_keys=True)
    assert (
        fingerprint(("syl", "son"))
        == "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    )
    graph = read_cmu(("AH1",))
    assert tiergraph.wire.loads(tiergraph.wire.dumps(graph)) == graph
    assert graph.relation_declarations


def test_feature_keys_are_lexical_including_inventory_extensions() -> None:
    inventory = IPAFeatures()
    names = [feature.name for feature in ipa_declarations(inventory).features]
    assert names == sorted(names)
    declarations = Declarations(
        (TierDeclaration("phone", frozenset({"z-extension", "a-core"})),),
        (FeatureDeclaration("z-extension"), FeatureDeclaration("a-core")),
        (),
    )
    graph = Graph(
        declarations,
        (
            ClockNode(
                groups=(EventGroup("phone", (Event({"z-extension": 2, "a-core": 1}),)),)
            ),
            ClockNode(),
        ),
    )
    wire = dumps(graph, Model("extension", "1", declarations))
    assert wire.index('"a-core"') < wire.index('"z-extension"')


def test_durable_labels_are_declared_data_while_paths_are_revision_local() -> None:
    declarations = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        (),
    )
    first = GraphBuilder(declarations)
    first.append_input_atom("item", {"label": "durable"})
    original = first.build()
    second = GraphBuilder(declarations)
    second.append_input_atom("item", {"label": "new"})
    second.add_event("item", 0, {"label": "durable"})
    revised = second.build()
    assert original.resolve("/clock/0/item/0").event.features["label"] == "durable"  # type: ignore[union-attr]
    assert revised.resolve("/clock/0/item/1").event.features["label"] == "durable"  # type: ignore[union-attr]


def test_acyclicity_is_per_declared_relation_not_their_union() -> None:
    declarations = Declarations(
        (TierDeclaration("item"),),
        (),
        (
            RelationDeclaration("a", acyclic=True),
            RelationDeclaration("b", acyclic=True),
        ),
    )
    events = EventGroup("item", (Event({}), Event({})))
    graph = Graph(
        declarations,
        (ClockNode(groups=(events,)), ClockNode()),
        (
            Relation(("/clock/0/item/0",), "a", ("/clock/0/item/1",)),
            Relation(("/clock/0/item/1",), "b", ("/clock/0/item/0",)),
        ),
    )
    assert len(graph.relations) == 2


def test_ipa_resolved_views_are_opt_in_but_cmu_facts_are_authoritative() -> None:
    form = IPAFeatures().read("a")
    assert "features" not in form.to_dict()["units"][0]
    assert "features" in form.to_dict(self_contained=True)["units"][0]
    cmu = read_cmu(("AH1",))
    attributes = {
        value.name.local_name: value.lexical
        for value in cmu.tiers[0].items[0].attributes
    }
    assert attributes == {"phone": "AH", "stress": "primary"}


def test_rendering_selection_is_profile_explicit_and_choices_never_guess() -> None:
    inventory = IPAFeatures()
    builder = GraphBuilder(ipa_declarations(inventory))
    choice = builder.add_event("analysis", 0, {}, duration=0)
    first = builder.add_event("delivery", 0, {}, duration=0)
    second = builder.add_event("delivery", 0, {}, duration=0)
    builder.relate((choice,), "alternatives", (first, second))
    graph = builder.build()
    with pytest.raises(DeliverySelectionError, match="require a selection"):
        render_delivery(graph)
    assert render_delivery(graph, selected="/clock/0/delivery/0")


def test_public_builder_returns_form_and_navigation_stays_on_form() -> None:
    builder = FormBuilder()
    utterance = builder.begin("utterance")
    segments = builder.append_ipa("kæt")
    builder.end(utterance)
    builder.contain(utterance, segments)
    builder.add_root(utterance)
    form = builder.build()
    assert form.to_ipa() == "kæt"
    assert form.leaves(form.roots[0]) == form.direct_children(form.roots[0])


def test_public_builder_renumbers_compatibility_units_across_raw_appends() -> None:
    builder = FormBuilder()
    builder.append_ipa("ka")
    builder.append_ipa("ta")
    form = builder.build()

    assert tuple(unit.text for unit in form.units) == ("k", "a", "t", "a")
    assert form.to_ipa() == "kata"
    assert json.loads(form.to_json())["units"]
    assert [
        event.features["compatibility-index"]
        for node in form.__dict__["_tiergraph_index"].clock
        for group in node.groups
        for event in group.events
        if "compatibility-index" in event.features
    ] == [0, 1, 2, 3]


def test_public_builder_two_phrase_pattern_projects_and_round_trips() -> None:
    builder = FormBuilder()
    utterance = builder.begin("utterance")
    phrases = []
    for text in ("ka", "ta"):
        phrase = builder.begin("phrase")
        segments = builder.append_ipa(text)
        builder.end(phrase)
        builder.contain(phrase, segments)
        phrases.append(phrase)
    builder.end(utterance)
    builder.contain(utterance, phrases)
    builder.add_root(utterance)

    form = builder.build()
    assert tuple(unit.text for unit in form.units) == ("k", "a", "t", "a")
    assert form.to_ipa() == "kata"
    assert type(form).from_json(form.to_json()) == form
