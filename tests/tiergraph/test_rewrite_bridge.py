from __future__ import annotations

import json
from pathlib import Path

import ipakit
import pytest
from ipakit._rewrite_graph import (
    japanese_moraic_fixture,
    japanese_moraic_fixtures,
    project_derivation,
)
from ipakit._tiergraph_builder import GraphBuilder

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
def test_attested_japanese_adaptations_use_the_rewrite_bridge(name):
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
    compatibility = {
        link.name
        for link in form.__dict__["_tiergraph_index"].containment_input.relations
    }
    assert names["rewrites-to"] in authoritative
    if len(fixture.output) > len(fixture.source):
        # ``inserts`` targets a clock position, not an event, so it rides the
        # compatibility surface (which feeds ``to_dot``) but is absent from the
        # authoritative polyadic graph.  Pin both facts so the divergence stays
        # known rather than drifting into a silently dropped relation.
        assert "inserts" in compatibility
        assert names["inserts"] not in authoritative


def test_phantoms_do_not_corrupt_the_compatibility_surface():
    inventory = ipakit.load_ipa_features()
    form = japanese_moraic_fixture("strike", inventory)
    assert tuple(unit.text for unit in form.units) == tuple(
        unit.text for unit in inventory.read("stɹa͜ɪk").units
    )


def test_malformed_compatibility_graph_has_a_typed_failure():
    inventory = ipakit.load_ipa_features()
    source = inventory.read("p")
    from ipakit._ipa_graph import declarations

    builder = GraphBuilder(declarations(inventory))
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


def _bridge_fixture_data(form):
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
            for node in form.__dict__["_tiergraph_index"].clock
        ],
        "roots": list(form.roots),
        "links": [
            [list(link.sources), link.name, list(link.targets)]
            for link in form.__dict__["_tiergraph_index"].containment_input.relations
        ],
    }


def test_hot_bridge_projection_matches_serialized_fixture():
    inventory = ipakit.load_ipa_features()
    live = _bridge_fixture_data(japanese_moraic_fixture("hot", inventory))
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
    form = japanese_moraic_fixture("hot", inventory)
    steps = {
        event.features["derivation-step"]
        for _, event in _events(form, "narrow") + _events(form, "allophonic")
        if "derivation-step" in event.features
    }
    assert steps == set(range(len(derivation.fired)))
    assert len(derivation.fired) == 3
