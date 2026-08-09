from __future__ import annotations

import json
from pathlib import Path

import pytest
from ipakit import IPAFeatures, Segment
from ipakit._ipa_graph import declarations as ipa_declarations
from ipakit._tiergraph import (
    ClockNode,
    Declarations,
    EndpointKind,
    Event,
    EventGroup,
    FeatureDeclaration,
    Graph,
    GraphValidationError,
    RefinedSpan,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_json import IPAValues, Model, dumps, from_data, loads, to_data


def generic_model() -> Model:
    declarations = Declarations(
        (
            TierDeclaration("a/b~c", frozenset({"value"})),
            TierDeclaration("choice", frozenset({"value"})),
        ),
        (FeatureDeclaration("value"),),
        (
            RelationDeclaration(
                "inserts",
                source_kinds=frozenset(
                    {EndpointKind.COARSE_TICK, EndpointKind.REFINED_GAP}
                ),
                source_arity=(1, 1),
            ),
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
    return Model("generic-test", "1", declarations)


def generic_graph() -> Graph:
    model = generic_model()
    source = "/clock/0/a~1b~0c/0"
    choices = ("/clock/0/choice/0", "/clock/0/choice/1")
    return Graph(
        model.declarations,
        (
            ClockNode(
                1,
                (
                    EventGroup("a/b~c", (Event({"value": {"z": 2, "a": 1}}),)),
                    EventGroup(
                        "choice", (Event({"value": "x"}), Event({"value": "y"}))
                    ),
                ),
            ),
            ClockNode(
                3,
                (
                    EventGroup(
                        "a/b~c",
                        (
                            Event(
                                {"value": "between"},
                                span=RefinedSpan("/clock/1/gaps/0", "/clock/1/gaps/1"),
                            ),
                        ),
                    ),
                ),
            ),
            ClockNode(),
        ),
        (
            Relation(("/clock/2",), "inserts", (choices[0],)),
            Relation((source,), "alternatives", choices),
            Relation((source,), "selects", (choices[1],)),
        ),
        (source,),
    )


def test_generic_envelope_round_trip_and_canonical_bytes() -> None:
    model = generic_model()
    graph = generic_graph()
    data = to_data(graph, model)
    assert data["type"] == "tiergraph"
    assert data["v"] == 1
    assert data["model"] == {"name": "generic-test", "version": "1"}
    assert data["tiers"] == ["a/b~c", "choice"]
    assert data["clock"][1]["gaps"] == [{}, {}, {}]  # type: ignore[index]
    assert "duration" not in data["clock"][0]["a/b~c"][0]  # type: ignore[index]
    assert data["clock"][1]["a/b~c"][0]["span"] == {  # type: ignore[index]
        "start": "/clock/1/gaps/0",
        "end": "/clock/1/gaps/1",
    }
    assert from_data(data, model) == graph
    assert loads(dumps(graph, model), model) == graph
    assert dumps(graph, model) == dumps(graph, model)
    assert '"id"' not in dumps(graph, model)


def test_structured_segment_round_trip_does_not_reparse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = IPAFeatures()
    fixture = json.loads(
        (Path(__file__).parent / "structured_segment_v3.json").read_text()
    )
    segment = Segment.from_dict(fixture["value"], inventory)
    declared = ipa_declarations(inventory)
    feature_values = {
        "value": segment,
        "spelling": fixture["spelling"],
        **fixture["features"],
        **fixture["prosody"],
        "provenance": tuple(tuple(item) for item in fixture["provenance"]),
    }
    if "class" not in {feature.name for feature in declared.features}:
        pytest.xfail("IPA declarations omit the structured fixture's class feature")
    graph = Graph(
        declared,
        (
            ClockNode(groups=(EventGroup("segment", (Event(feature_values),)),)),  # type: ignore[arg-type]
            ClockNode(),
        ),
    )
    model = Model("ipakit-segmental", "1", declared, IPAValues(inventory))
    data = to_data(graph, model)
    event = data["clock"][0]["segment"][0]  # type: ignore[index]
    assert event == fixture

    def parser_was_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("IPA parser was called")

    for name in {"segment", "parse", "tokenize", "read"} | {
        name for name in dir(inventory) if name.startswith("_parse")
    }:
        monkeypatch.setattr(inventory, name, parser_was_called)
    restored = from_data(data, model)
    restored_value = restored.clock[0].groups[0].events[0].features["value"]
    assert isinstance(restored_value, Segment)
    assert restored_value.to_dict() == fixture["value"]
    assert restored.clock[0].groups[0].events[0].features["spelling"] == "ⁿd͡ʒʷː"


@pytest.mark.parametrize(
    "mutation, reason",
    [
        (lambda data: data["clock"].append({"gaps": []}), "gap"),
        (lambda data: data["clock"][0].update({"gaps": [{"id": 1}]}), "gap"),
        (lambda data: data["roots"].append("/clock/9/a~1b~0c/0"), "dangling"),
        (
            lambda data: data["links"].append(
                [["/clock/0/gaps/0"], "inserts", ["/clock/0/choice/0"]]
            ),
            "noncanonical",
        ),
        (
            lambda data: data["clock"][1]["a/b~c"][0].update(
                {"span": {"start": "/clock/1/gaps/2", "end": "/clock/1/gaps/1"}}
            ),
            "precedes",
        ),
    ],
)
def test_malformed_references_endpoints_and_clocks_are_rejected(
    mutation: object, reason: str
) -> None:
    data = to_data(generic_graph(), generic_model())
    mutation(data)  # type: ignore[operator]
    with pytest.raises(GraphValidationError, match=reason):
        from_data(data, generic_model())


def test_choice_rejections_survive_restoration() -> None:
    model = generic_model()
    source = "/clock/0/a~1b~0c/0"
    first, second = "/clock/0/choice/0", "/clock/0/choice/1"
    bad_links = (
        ([[[source], "alternatives", [first, first]]], "distinct"),
        (
            [
                [[source], "alternatives", [first]],
                [[source], "alternatives", [second]],
            ],
            "at most one alternatives",
        ),
        (
            [
                [[source], "alternatives", [first, second]],
                [[source], "selects", [first]],
                [[source], "selects", [second]],
            ],
            "at most one selects",
        ),
        (
            [
                [[source], "alternatives", [first]],
                [[source], "selects", [second]],
            ],
            "not a member",
        ),
    )
    for replacement, reason in bad_links:
        data = to_data(generic_graph(), model)
        data["links"] = replacement
        with pytest.raises(GraphValidationError, match=reason):
            from_data(data, model)
