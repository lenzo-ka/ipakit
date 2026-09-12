"""Declared native value retention, independent of public Form admission."""

import math

import pytest
from ipakit._containment_projection import ContainmentProjection
from ipakit._fact_builder import FactBuilder
from ipakit._graph_facts import (
    Declarations,
    FeatureDeclaration,
    GraphValidationError,
    RelationDeclaration,
    TierDeclaration,
    Timing,
)

import tiergraph as tg


def declared_value(*args):
    # Lazy import lets endpoint regressions exercise the actual old parent.
    from ipakit._containment_projection import declared_value as read

    return read(*args)


def assert_json_value(actual, expected):
    assert type(actual) is type(expected)
    assert actual == expected
    if isinstance(expected, dict):
        for key, value in expected.items():
            assert_json_value(actual[key], value)
    elif isinstance(expected, list):
        for item, value in zip(actual, expected, strict=True):
            assert_json_value(item, value)


def declarations(*features):
    return Declarations(
        (
            TierDeclaration("token", frozenset(f.name for f in features)),
            TierDeclaration("sound"),
        ),
        tuple(features),
        (
            RelationDeclaration(
                "resolves",
                source_tiers=frozenset({"token"}),
                target_tiers=frozenset({"sound"}),
            ),
        ),
    )


def graph_for(value):
    builder = FactBuilder(
        declarations(FeatureDeclaration("claims", ("urn:test:clts", "claims")))
    )
    builder.append_input_atom("token", {"claims": value}, timing=Timing(0.25, 0.1))
    source = builder.build_input()
    projection = ContainmentProjection.from_input(source)
    return source, projection.graph, projection.old_to_new[source.refs[0]]


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        7,
        -8,
        1.25,
        "⁵",
        [],
        {},
        {"raw": "t͜s", "claims": ["affricate", None, False, 2, 0.5]},
    ],
)
def test_literal_declared_values_survive_native_codec(value):
    source, graph, event = graph_for(value)
    restored = tg.loads(tg.dumps(graph))
    # Literal input, not merely equality between two already-lossy encoders.
    assert_json_value(
        declared_value(restored, event, tg.QualifiedName("urn:test:clts", "claims")),
        value,
    )
    assert len(source.clock) == 2
    resolved = restored.resolve_item(tg.DurableItemRef(source.refs[0]))
    assert resolved == event
    item = next(t for t in restored.tiers if t.declaration.name == event.tier).items[
        event.index
    ]
    times = {
        a.name.local_name: float(a.lexical)
        for a in item.attributes
        if a.name.local_name.startswith("timing-")
    }
    assert times == {"timing-start": 0.25, "timing-duration": 0.1}


@pytest.mark.parametrize(
    "value",
    [
        object(),
        b"bytes",
        {1: "not a string key"},
        math.inf,
        math.nan,
        {"nested": [object()]},
    ],
)
def test_unsupported_values_are_refused(value):
    with pytest.raises(ValueError):
        graph_for(value)


def test_cache_key_includes_opted_in_values():
    _, left, le = graph_for("left")
    _, right, re = graph_for("right")
    name = tg.QualifiedName("urn:test:clts", "claims")
    assert declared_value(left, le, name) == "left"
    assert declared_value(right, re, name) == "right"


def test_object_key_insertion_order_is_not_a_second_encoding():
    _, left, _ = graph_for({"b": 2, "a": 1})
    _, right, _ = graph_for({"a": 1, "b": 2})
    assert tg.dump_bytes(left) == tg.dump_bytes(right)


def test_opted_in_value_requires_tier_admission():
    builder = FactBuilder(
        declarations(FeatureDeclaration("claims", ("urn:test", "claims")))
    )
    builder.append_input_atom("sound", {"claims": "not admitted"})
    with pytest.raises(GraphValidationError, match="not admitted"):
        ContainmentProjection.from_input(builder.build_input())


def test_reserved_native_identity_refuses():
    builder = FactBuilder(
        declarations(
            FeatureDeclaration(
                "claims",
                ("https://ipakit.dev/tiergraph/containment-projection/v1", "claims"),
            )
        )
    )
    builder.append_input_atom("token", {"claims": "bad identity"})
    with pytest.raises(GraphValidationError, match="reserved namespace"):
        ContainmentProjection.from_input(builder.build_input())


def test_qualified_names_do_not_alias_and_occurrences_stay_ordered():
    builder = FactBuilder(
        declarations(
            FeatureDeclaration("first", ("urn:test:one", "claim")),
            FeatureDeclaration("second", ("urn:test:two", "claim")),
        )
    )
    builder.append_input_atom("token", {"first": "a", "second": "b"})
    builder.append_input_atom("token", {"first": "a", "second": None})
    source = builder.build_input()
    p = ContainmentProjection.from_input(source)
    graph = tg.loads(tg.dumps(p.graph))
    events = [p.old_to_new[ref] for ref in source.refs]
    assert [
        declared_value(graph, e, tg.QualifiedName("urn:test:one", "claim"))
        for e in events
    ] == ["a", "a"]
    assert [
        declared_value(graph, e, tg.QualifiedName("urn:test:two", "claim"))
        for e in events
    ] == ["b", None]
    assert len(source.clock) == 3
    with pytest.raises(GraphValidationError, match="exactly one"):
        declared_value(graph, events[0], tg.QualifiedName("urn:absent", "claim"))


def test_duplicate_qualified_identity_refuses():
    with pytest.raises(GraphValidationError, match="duplicate native"):
        declarations(
            FeatureDeclaration("one", ("urn:test", "same")),
            FeatureDeclaration("two", ("urn:test", "same")),
        )


@pytest.mark.parametrize(
    "reverse_source,reverse_target", [(True, False), (False, True)]
)
def test_event_relation_tier_restrictions_are_enforced(reverse_source, reverse_target):
    builder = FactBuilder(declarations())
    token = builder.append_input_atom("token", {})
    sound = builder.add_event("sound", 0, {})
    builder.relate(
        [sound if reverse_source else token],
        "resolves",
        [token if reverse_target else sound],
    )
    with pytest.raises(tg.ExecutionError):
        ContainmentProjection.from_input(builder.build_input())


def test_valid_event_relation_survives_native_codec():
    builder = FactBuilder(declarations())
    token = builder.append_input_atom("token", {})
    sound = builder.add_event("sound", 0, {})
    builder.relate([token], "resolves", [sound])
    p = ContainmentProjection.from_input(builder.build_input())
    restored = tg.loads(tg.dumps(p.graph))
    declaration = next(
        d
        for d in restored.relation_declarations
        if d.name == p.relation_names["resolves"]
    )
    assert declaration.sources.tiers == (p.tier_names["token"],)
    assert declaration.targets.tiers == (p.tier_names["sound"],)


def test_legacy_graph_is_not_opted_in():
    builder = FactBuilder(declarations(FeatureDeclaration("claims")))
    builder.append_input_atom("token", {"claims": "legacy omission"})
    graph = ContainmentProjection.from_input(builder.build_input()).graph
    assert not any("declared-values" in ns.namespace for ns in graph.namespaces)


@pytest.mark.parametrize(
    "name",
    [
        "spelling",
        "prominence",
        "atom",
        "output",
        "exemplar",
        "notes",
        "kind",
        "articulator",
        "source-value",
        "arc",
        "offset",
        "target-index",
        "compatibility-unit",
        "compatibility-interval",
        "compatibility-index",
        "input",
    ],
)
@pytest.mark.parametrize(
    "value", [True, False, 0, 0.74, "foreign", {"nested": [None, True, 3]}]
)
def test_foreign_names_do_not_inherit_private_payload_semantics(name, value):
    builder = FactBuilder(declarations(FeatureDeclaration(name, ("urn:foreign", name))))
    builder.append_input_atom("token", {name: value})
    source = builder.build_input()
    projection = ContainmentProjection.from_input(source)
    graph = tg.loads(tg.dumps(projection.graph))
    event = projection.old_to_new[source.refs[0]]
    assert_json_value(
        declared_value(graph, event, tg.QualifiedName("urn:foreign", name)), value
    )
    item = next(t for t in graph.tiers if t.declaration.name == event.tier).items[
        event.index
    ]
    # Independent literal expectation: only the real structural span, never a
    # private spelling, numeric attribute, or compatibility interpretation.
    assert {a.name.local_name: a.lexical for a in item.attributes} == {
        "structural-duration": "1"
    }


def test_foreign_names_do_not_override_actual_timing_and_span():
    builder = FactBuilder(
        declarations(
            FeatureDeclaration("timing-start", ("urn:foreign", "timing-start")),
            FeatureDeclaration(
                "structural-duration", ("urn:foreign", "structural-duration")
            ),
        )
    )
    builder.append_input_atom(
        "token",
        {"timing-start": False, "structural-duration": {"claim": 99}},
        timing=Timing(0.25, 0.1),
    )
    source = builder.build_input()
    projection = ContainmentProjection.from_input(source)
    graph = tg.loads(tg.dumps(projection.graph))
    event = projection.old_to_new[source.refs[0]]
    assert_json_value(
        declared_value(graph, event, tg.QualifiedName("urn:foreign", "timing-start")),
        False,
    )
    assert_json_value(
        declared_value(
            graph, event, tg.QualifiedName("urn:foreign", "structural-duration")
        ),
        {"claim": 99},
    )
    item = next(t for t in graph.tiers if t.declaration.name == event.tier).items[
        event.index
    ]
    actual = {a.name.local_name: float(a.lexical) for a in item.attributes}
    assert actual == {
        "structural-duration": 1,
        "timing-start": 0.25,
        "timing-duration": 0.1,
    }


@pytest.mark.parametrize("foreign_support", ["input", "compatibility-index"])
def test_active_legacy_unit_cannot_reinterpret_foreign_support(foreign_support):
    from ipakit import IPAFeatures

    names = ("compatibility-unit", "input", "compatibility-index")
    builder = FactBuilder(
        declarations(
            *(
                FeatureDeclaration(
                    name, ("urn:foreign", name) if name == foreign_support else None
                )
                for name in names
            )
        )
    )
    builder.append_input_atom(
        "token",
        {
            "compatibility-unit": IPAFeatures().read("a").units[0],
            "input": True,
            "compatibility-index": 0,
        },
    )
    with pytest.raises(
        GraphValidationError, match="requires legacy input and compatibility-index"
    ):
        ContainmentProjection.from_input(builder.build_input())


def test_legacy_unit_and_independent_foreign_values_coexist():
    from ipakit import IPAFeatures

    builder = FactBuilder(
        declarations(
            FeatureDeclaration("compatibility-unit"),
            FeatureDeclaration("input"),
            FeatureDeclaration("compatibility-index"),
            FeatureDeclaration("arc", ("urn:foreign", "arc")),
            FeatureDeclaration("text", ("urn:foreign", "text")),
        )
    )
    builder.append_input_atom(
        "token",
        {
            "compatibility-unit": IPAFeatures().read("a").units[0],
            "input": True,
            "compatibility-index": 0,
            "arc": True,
            "text": "foreign",
        },
    )
    source = builder.build_input()
    projection = ContainmentProjection.from_input(source)
    graph = tg.loads(tg.dumps(projection.graph))
    event = projection.old_to_new[source.refs[0]]
    assert_json_value(
        declared_value(graph, event, tg.QualifiedName("urn:foreign", "arc")), True
    )
    assert_json_value(
        declared_value(graph, event, tg.QualifiedName("urn:foreign", "text")), "foreign"
    )
    item = next(t for t in graph.tiers if t.declaration.name == event.tier).items[
        event.index
    ]
    actual = {a.name.local_name: a.lexical for a in item.attributes}
    assert actual["text"] == "a"
    assert actual["input"] == "true"
    assert actual["compatibility-index"] == "0"
    assert "arc" not in actual
