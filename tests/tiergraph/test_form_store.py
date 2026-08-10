from __future__ import annotations

import dataclasses

import ipakit
import ipakit.form as form_module
from ipakit import Form, Interval, Timing

FEATURES = ipakit.load_ipa_features()


def test_parsed_form_owns_graph_and_projects_compatibility_fields() -> None:
    form = Form.parse("#a..b#", FEATURES)

    assert "units" not in form.__dict__
    assert "intervals" not in form.__dict__
    assert "_tiergraph_graph" in form.__dict__
    assert [unit.text for unit in form.units] == list("#a..b#")
    assert form.intervals == ()


def test_compatibility_projection_is_memoized_across_form_surface(
    monkeypatch,
) -> None:
    constructions: dict[int, int] = {}
    original_init = form_module._CompatibilityProjection.__init__

    def counted_init(self, graph) -> None:
        graph_id = id(graph)
        constructions[graph_id] = constructions.get(graph_id, 0) + 1
        original_init(self, graph)

    monkeypatch.setattr(form_module._CompatibilityProjection, "__init__", counted_init)
    form = Form.parse("#a.b#", FEATURES)
    peer = Form.parse("#a.b#", FEATURES)

    units = form.units
    assert form.units is units
    assert form.units[0] is form.units[0]
    assert form.intervals is form.intervals
    assert form == peer
    assert form.to_ipa() == "#a.b#"
    form.tree()
    form.to_dict()
    assert tuple(form) == units
    assert constructions
    assert max(constructions.values()) <= 1


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


def test_interval_projection_retains_caller_order_across_tiers() -> None:
    parsed = Form.parse("abcd", FEATURES)
    intervals = (
        Interval("mora", 0, 2, FEATURES),
        Interval("syllable", 1, 4, FEATURES),
    )

    assert Form.of(parsed.units, intervals).intervals == intervals


def test_constructed_form_round_trip_retains_timing_and_interval_order() -> None:
    parsed = Form.parse("abcd", FEATURES)
    units = tuple(
        dataclasses.replace(unit, timing=Timing(index / 10, 0.1))
        for index, unit in enumerate(parsed.units)
    )
    intervals = (
        Interval("mora", 0, 2, FEATURES, Timing(0.0, 0.2)),
        Interval("syllable", 1, 4, FEATURES, Timing(0.1, 0.3)),
        Interval("mora", 0, 2, FEATURES, Timing(0.4, 0.2)),
    )
    held = Form.of(units, intervals)

    assert held.units == units
    assert tuple(unit.timing for unit in held.units) == tuple(
        unit.timing for unit in units
    )
    assert held.intervals == intervals
    assert Form.from_dict(held.to_dict(), FEATURES) == held


def test_rebuilt_form_round_trip_retains_timed_duplicate_intervals() -> None:
    parsed = Form.parse("#ab#", FEATURES)
    intervals = (
        Interval("syllable", 0, 2, FEATURES, Timing(0.0, 0.2)),
        Interval("mora", 1, 3, FEATURES, Timing(0.1, 0.1)),
        Interval("syllable", 0, 2, FEATURES, Timing(0.3, 0.2)),
    )
    rebuilt = Form.rebuild(parsed.segments, parsed.boundaries, intervals, FEATURES)

    assert rebuilt.intervals == intervals
    assert Form.from_dict(rebuilt.to_dict(), FEATURES) == rebuilt


def test_constructed_form_accepts_a_tier_declared_by_a_custom_inventory(
    tmp_path,
) -> None:
    source = FEATURES.xml_path.read_text(encoding="utf-8")
    anchor = '<value name="morph" short="mph" href="Morpheme"/>'
    path = tmp_path / "ipa.xml"
    path.write_text(
        source.replace(anchor, f'{anchor}\n      <value name="gesture" short="gst"/>'),
        encoding="utf-8",
    )
    extended = ipakit.IPAFeatures(xml_path=path)
    parsed = Form.parse("ata", extended)
    interval = Interval("gesture", 1, 3, extended)

    assert Form.of(parsed.units, (interval,)).intervals == (interval,)
