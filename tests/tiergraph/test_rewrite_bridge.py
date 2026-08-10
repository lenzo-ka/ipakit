from __future__ import annotations

import ipakit
import pytest
from ipakit._rewrite_graph import japanese_moraic_fixture, japanese_moraic_fixtures
from ipakit._tiergraph_builder import GraphBuilder


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
