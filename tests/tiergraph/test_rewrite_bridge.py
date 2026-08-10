from __future__ import annotations

import json
from pathlib import Path

import ipakit
import pytest
from ipakit._rewrite_graph import japanese_moraic_fixture, japanese_moraic_fixtures
from ipakit._tiergraph_builder import GraphBuilder

HERE = Path(__file__).parent


def _events(graph, tier):
    return [
        (f"/clock/{tick}/{group.tier}/{index}", event)
        for tick, node in enumerate(graph.clock)
        for group in node.groups
        if group.tier == tier
        for index, event in enumerate(group.events)
    ]


@pytest.mark.parametrize("name", japanese_moraic_fixtures())
def test_attested_japanese_adaptations_use_the_rewrite_bridge(name):
    inventory = ipakit.load_ipa_features()
    fixture = japanese_moraic_fixtures()[name]
    form = japanese_moraic_fixture(name, inventory)
    graph = form._graph
    assert form.to_ipa() == fixture.output
    assert (
        tuple(event.features["value"] for _, event in _events(graph, "mora"))
        == fixture.morae
    )
    assert all(event.structural_duration == 0 for _, event in _events(graph, "mora"))
    assert any(relation.name == "rewrites-to" for relation in graph.relations)
    if len(fixture.output) > len(fixture.source):
        assert any(relation.name == "inserts" for relation in graph.relations)


def test_phantoms_do_not_corrupt_the_compatibility_surface():
    inventory = ipakit.load_ipa_features()
    form = japanese_moraic_fixture("strike", inventory)
    assert tuple(unit.text for unit in form.units) == tuple(
        unit.text for unit in inventory.read("stɹa͜ɪk").units
    )


def test_malformed_compatibility_graph_has_a_typed_failure():
    inventory = ipakit.load_ipa_features()
    source = inventory.read("p")
    builder = GraphBuilder(source._graph.declarations)
    unit = source.units[0]
    facts = {
        "value": unit.segment,
        "spelling": unit.text,
        "input": True,
        "compatibility-unit": unit,
        "compatibility-index": 1,
    }
    builder.append_input_atom("segment", facts)
    malformed = ipakit.Form._from_graph(builder.build())
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


def _bridge_fixture_data(graph):
    """The complete topology plus stable, JSON-native bridge event facts."""
    return {
        "clock": [
            {
                "gaps": node.gap_count,
                "groups": [
                    {
                        "tier": group.tier,
                        "events": [
                            {
                                "features": {
                                    name: (
                                        event.features.get("spelling", str(value))
                                        if name == "value"
                                        else value
                                    )
                                    for name, value in event.features.items()
                                    if name != "compatibility-unit"
                                },
                                "duration": event.structural_duration,
                            }
                            for event in group.events
                        ],
                    }
                    for group in node.groups
                ],
            }
            for node in graph.clock
        ],
        "roots": list(graph.roots),
        "links": [
            [list(link.sources), link.name, list(link.targets)]
            for link in graph.relations
        ],
    }


def test_hot_bridge_projection_matches_serialized_fixture():
    inventory = ipakit.load_ipa_features()
    live = _bridge_fixture_data(japanese_moraic_fixture("hot", inventory)._graph)
    expected = json.loads(
        (HERE / "fixtures" / "hot_bridge_projection.json").read_text()
    )
    assert live == expected


def test_only_fired_steps_materialize_projection_events():
    inventory = ipakit.load_ipa_features()
    fixture = japanese_moraic_fixtures()["hot"]
    derivation = ipakit.rules.shipped("japanese-moraic", inventory).derive(
        fixture.source, inventory
    )
    graph = japanese_moraic_fixture("hot", inventory)._graph
    steps = {
        event.features["derivation-step"]
        for _, event in _events(graph, "narrow") + _events(graph, "allophonic")
        if "derivation-step" in event.features
    }
    assert steps == set(range(len(derivation.fired)))
    assert len(derivation.fired) == 3
