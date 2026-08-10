from __future__ import annotations

import dataclasses

import ipakit
from ipakit import Form, Interval

FEATURES = ipakit.load_ipa_features()


def test_parsed_form_owns_graph_and_projects_compatibility_fields() -> None:
    form = Form.parse("#a..b#", FEATURES)

    assert "units" not in form.__dict__
    assert "intervals" not in form.__dict__
    assert "_tiergraph_graph" in form.__dict__
    assert [unit.text for unit in form.units] == list("#a..b#")
    assert form.intervals == ()


def test_constructed_form_builds_graph_and_replace_keeps_public_coordinates() -> None:
    parsed = Form.parse("a..b", FEATURES)
    interval = Interval("mora", 0, 2, FEATURES)
    held = Form.of(parsed.units, (interval,))

    replaced = dataclasses.replace(held, intervals=())

    assert held.units == parsed.units
    assert held.intervals == (interval,)
    assert replaced.units == held.units
    assert replaced.intervals == ()
    assert "units" not in replaced.__dict__
    assert "_tiergraph_graph" in replaced.__dict__


def test_interval_between_repeated_dots_uses_exact_refined_endpoint() -> None:
    parsed = Form.parse("a..b", FEATURES)
    held = Form.of(parsed.units, (Interval("mora", 0, 2, FEATURES),))
    graph = held.__dict__["_tiergraph_graph"]
    mora = next(
        event
        for node in graph.clock
        for group in node.groups
        if group.tier == "mora"
        for event in group.events
    )

    assert mora.span is not None
    assert mora.span.start == "/clock/0"
    assert mora.span.end == "/clock/1/gaps/1"
    assert held.intervals[0] == Interval("mora", 0, 2, FEATURES)
