from __future__ import annotations

import json
from pathlib import Path

import ipakit
import pytest
from ipakit._fact_builder import FactBuilder
from ipakit._rewrite_graph import (
    japanese_moraic_fixture,
    japanese_moraic_fixtures,
    project_derivation,
)

import tiergraph

HERE = Path(__file__).parent


def _events(form, tier):
    return [
        (path, event)
        for path, (_, event) in form.__dict__["_tiergraph_index"].events.items()
        if form._containment.event_tiers[path] == tier
    ]


def _one_step_derivation(inventory, edits, result):
    seed = (
        ipakit.rules.RuleSet.parse("t -> s", inventory).derive("ta", inventory).edits[0]
    )
    traced = tuple(
        ipakit.rules.Edit(
            rule=rule,
            start=start,
            end=end,
            replacement=tuple(inventory.read(replacement).units),
            before="ta"[start:end],
            after=replacement,
            site=seed.site,
        )
        for rule, start, end, replacement in edits
    )
    return ipakit.rules.Derivation(
        start="ta",
        result=result,
        steps=(ipakit.rules.Step("batch", "ta", result, traced),),
    )


def test_one_step_projection_keeps_adjacent_edits_and_their_rule_provenance():
    inventory = ipakit.load_ipa_features()
    derivation = _one_step_derivation(
        inventory,
        (("t-to-s", 0, 1, "s"), ("a-to-o", 1, 2, "o")),
        "so",
    )

    form = project_derivation(derivation, inventory)

    assert form.to_ipa() == "so"
    events = [event for _, event in _events(form, "narrow")]
    assert [
        (event.features["spelling"], event.features["rule"]) for event in events
    ] == [
        ("s", "t-to-s"),
        ("o", "a-to-o"),
    ]


def test_one_step_projection_keeps_same_start_edits():
    inventory = ipakit.load_ipa_features()
    derivation = _one_step_derivation(
        inventory,
        (("insert-s", 0, 0, "s"), ("t-to-d", 0, 1, "d")),
        "sda",
    )

    form = project_derivation(derivation, inventory)

    assert form.to_ipa() == "sda"
    events = [event for _, event in _events(form, "narrow")]
    assert [
        (event.features["spelling"], event.features["rule"]) for event in events
    ] == [
        ("s", "insert-s"),
        ("d", "t-to-d"),
        ("a", "batch"),
    ]


@pytest.mark.parametrize("name", japanese_moraic_fixtures())
def test_curated_japanese_adaptations_use_the_rewrite_bridge(name):
    inventory = ipakit.load_ipa_features()
    fixture = japanese_moraic_fixtures()[name]
    form = japanese_moraic_fixture(name, inventory)
    assert form.to_ipa() == fixture.output
    assert (
        tuple(event.features["value"] for _, event in _events(form, "mora"))
        == fixture.morae
    )
    assert all(event.structural_duration == 0 for _, event in _events(form, "mora"))
    names = form._containment.relation_names
    authoritative = {
        relation.declaration for relation in form._graph.polyadic_relations
    }
    unit_view = {
        link.name
        for link in form.__dict__["_tiergraph_index"].containment_input.relations
    }
    assert names["rewrites-to"] in authoritative
    if len(fixture.output) > len(fixture.source):
        assert "inserts" in unit_view
        assert names["inserts"] in authoritative
        declaration = next(
            item
            for item in form._graph.relation_declarations
            if item.name == names["inserts"]
        )
        assert declaration.sources.endpoint_kinds == (
            tiergraph.RelationEndpointKind.BOUNDARY,
        )
        assert declaration.targets.endpoint_kinds == (
            tiergraph.RelationEndpointKind.ITEM,
        )
        instances = tuple(
            relation
            for relation in form._graph.polyadic_relations
            if relation.declaration == names["inserts"]
        )
        assert instances
        assert all(
            len(relation.sources) == 1
            and isinstance(relation.sources[0], tiergraph.DurableBoundaryRef)
            and relation.targets
            and all(
                isinstance(target, tiergraph.ItemRef) for target in relation.targets
            )
            for relation in instances
        )


def test_phantoms_do_not_corrupt_the_unit_surface():
    inventory = ipakit.load_ipa_features()
    form = japanese_moraic_fixture("strike", inventory)
    assert tuple(unit.text for unit in form.units) == tuple(
        unit.text for unit in inventory.read("stɹa͜ɪk").units
    )


def test_chained_phantoms_preserve_the_rule_engines_total_order():
    """The graph records the ordered result; it does not rescan phantoms."""
    inventory = ipakit.load_ipa_features()
    form = japanese_moraic_fixture("hot", inventory)
    observed = [
        (
            tick,
            group.tier,
            event.features["spelling"],
            event.features.get("derivation-step"),
            event.features.get("source-site-order"),
            event.features.get("application-order"),
            event.features.get("target-index"),
        )
        for tick, node in enumerate(form.__dict__["_tiergraph_index"].clock)
        for group in node.groups
        for event in group.events
        if event.features.get("phantom")
    ]

    assert observed == [
        (0, "narrow", "h", None, None, None, None),
        (0, "allophonic", "h", None, None, None, None),
        (0, "allophonic", "h", None, None, None, None),
        (0, "mora", "ho", None, None, None, None),
        (1, "narrow", "o", 0, 0, 0, 0),
        (1, "allophonic", "o", None, None, None, None),
        (1, "allophonic", "o", None, None, None, None),
        (2, "narrow", "t", None, None, None, None),
        (2, "allophonic", "tː", 1, 0, 0, 0),
        (2, "allophonic", "tː", None, None, None, None),
        (2, "mora", "t", None, None, None, None),
        (2, "mora", "to", None, None, None, None),
        (3, "allophonic", "o", 2, 0, 0, 0),
    ]


def test_insertion_then_deletion_keeps_cross_tier_input_clock_positions():
    inventory = ipakit.load_ipa_features()
    derivation = ipakit.rules.RuleSet.parse(
        "∅ -> ə / a _\na -> ∅ / _ ə", inventory
    ).derive("a", inventory)
    form = project_derivation(derivation, inventory)
    index = form.__dict__["_tiergraph_index"]

    assert derivation.result == "ə"
    assert [
        (tick, group.tier, event.features["spelling"], event.features["trace"])
        for tick, node in enumerate(index.clock)
        for group in node.groups
        for event in group.events
        if group.tier in {"narrow", "allophonic"}
    ] == [
        (0, "narrow", "a", "no-op"),
        (1, "narrow", "ə", "∅ -> ə / a _: ∅ -> ə @1"),
        (1, "allophonic", "ə", "no-op"),
    ]
    links = {
        (link.sources, link.name, link.targets)
        for link in index.containment_input.relations
    }
    assert (("/clock/1",), "inserts", ("/clock/1/narrow/0",)) in links
    assert (("/clock/0/narrow/0",), "rewrites-to", ()) in links
    assert (
        ("/clock/1/narrow/0",),
        "rewrites-to",
        ("/clock/1/allophonic/0",),
    ) in links


def test_malformed_unit_projection_graph_has_a_typed_failure():
    inventory = ipakit.load_ipa_features()
    source = inventory.read("p")
    from ipakit._ipa_graph import declarations

    builder = FactBuilder(declarations(inventory))
    unit = source.units[0]
    facts = {
        "value": unit.segment,
        "spelling": unit.text,
        "input": True,
        "unit": unit,
        "unit-index": 1,
    }
    builder.append_input_atom("segment", facts)
    malformed = ipakit.Form._from_projection_input(builder.build_input())
    with pytest.raises(ipakit.FormProjectionError, match="not contiguous"):
        _ = malformed.units


def test_alignment_is_rich_but_retains_the_pair_surface():
    inventory = ipakit.load_ipa_features()
    result = inventory.word_distance("kæt", "kæd", return_alignment=True)
    assert result.alignment is not None
    assert list(result.alignment) == [("k", "k"), ("æ", "æ"), ("t", "d")]
    assert [step.op for step in result.alignment.steps] == ["match", "match", "sub"]
    assert result.alignment.edit_cost == result.edit_cost
    assert result.alignment.similarity == result.similarity
    assert result.alignment.steps[-1].terms


def test_distance_alignment_capture_is_the_live_oracle():
    inventory = ipakit.load_ipa_features()
    captured = json.loads((HERE / "baselines" / "distance-alignments.json").read_text())
    for case in captured["pairs"]:
        result = inventory.word_distance(
            case["left"], case["right"], return_alignment=True
        )
        assert result.alignment is not None
        expected = case["word_distance"]
        assert [list(pair) for pair in result.alignment] == expected["alignment"]
        assert result.edit_cost == expected["edit_cost"]
        assert result.similarity == expected["similarity"]
        assert result.coverage == expected["coverage"]
        assert result.costs == expected["costs"]
        assert (
            inventory.word_similarity(case["left"], case["right"])
            == case["word_similarity"]
        )
        assert (
            inventory.explain_word_distance(case["left"], case["right"])
            == case["explain_word_distance"]
        )


def test_hot_bridge_projection_matches_serialized_fixture():
    from tiergraph.wire import to_data

    inventory = ipakit.load_ipa_features()
    live = to_data(japanese_moraic_fixture("hot", inventory)._graph)
    expected = json.loads(
        (HERE / "fixtures" / "hot_bridge_projection.json").read_text()
    )
    assert live == expected


def _assert_hot_provenance(source):
    events = source.events
    assert [
        (path, event.features["rule"], event.features["trace"])
        for path, event in events.items()
        if "rule" in event.features
    ] == [
        ("/clock/0/narrow/0", "ɑ is short o", "no-op"),
        ("/clock/0/allophonic/0", "gemination (after a consonant)", "no-op"),
        ("/clock/0/allophonic/1", "o after a coronal stop (final)", "no-op"),
        ("/clock/1/narrow/0", "ɑ is short o", "ɑ is short o: ɑ -> o @1"),
        ("/clock/1/allophonic/0", "gemination (after a consonant)", "no-op"),
        ("/clock/1/allophonic/1", "o after a coronal stop (final)", "no-op"),
        ("/clock/2/narrow/0", "ɑ is short o", "no-op"),
        (
            "/clock/2/allophonic/0",
            "gemination (after a consonant)",
            "gemination (after a consonant): t -> tː @2",
        ),
        ("/clock/2/allophonic/1", "o after a coronal stop (final)", "no-op"),
        (
            "/clock/3/allophonic/0",
            "o after a coronal stop (final)",
            "o after a coronal stop (final): ∅ -> o @3",
        ),
    ]
    assert [
        (path, event.features["mora-kind"])
        for path, event in events.items()
        if "mora-kind" in event.features
    ] == [
        ("/clock/0/mora/0", "ordinary"),
        ("/clock/2/mora/0", "geminate-half"),
        ("/clock/2/mora/1", "ordinary"),
    ]
    assert [
        (
            path,
            event.features["derivation-step"],
            event.features["application-order"],
            event.features["source-site-order"],
        )
        for path, event in events.items()
        if "derivation-step" in event.features
    ] == [
        ("/clock/1/narrow/0", 0, 0, 0),
        ("/clock/2/allophonic/0", 1, 0, 0),
        ("/clock/3/allophonic/0", 2, 0, 0),
    ]


def test_hot_bridge_keeps_prelowering_provenance():
    form = japanese_moraic_fixture("hot", ipakit.load_ipa_features())
    _assert_hot_provenance(form.__dict__["_tiergraph_index"].containment_input)


@pytest.mark.parametrize(
    "field",
    [
        "rule",
        "trace",
        "mora-kind",
        "derivation-step",
        "application-order",
        "source-site-order",
    ],
)
def test_hot_provenance_witness_detects_each_field_mutation(field):
    from dataclasses import replace

    form = japanese_moraic_fixture("hot", ipakit.load_ipa_features())
    source = form.__dict__["_tiergraph_index"].containment_input
    path = "/clock/2/mora/0" if field == "mora-kind" else "/clock/1/narrow/0"
    event = source.events[path]
    value = event.features[field]
    mutated = replace(
        event,
        features={
            **event.features,
            field: value + 1 if type(value) is int else "changed",
        },
    )
    changed = replace(source, events={**source.events, path: mutated})
    with pytest.raises(AssertionError):
        _assert_hot_provenance(changed)


def test_only_fired_steps_materialize_projection_events():
    inventory = ipakit.load_ipa_features()
    fixture = japanese_moraic_fixtures()["hot"]
    derivation = ipakit.rules.shipped("japanese-moraic", inventory).derive(
        fixture.source, inventory
    )
    form = japanese_moraic_fixture("hot", inventory)
    steps = {
        event.features["derivation-step"]
        for _, event in _events(form, "narrow") + _events(form, "allophonic")
        if "derivation-step" in event.features
    }
    assert steps == set(range(len(derivation.fired)))
    assert len(derivation.fired) == 3
