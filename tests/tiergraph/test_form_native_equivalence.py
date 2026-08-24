from __future__ import annotations

import dataclasses

import ipakit
from ipakit import Form, FormBuilder, Interval, Timing
from ipakit._containment_projection import (
    ContainmentProjection,
    ContainmentProjectionInput,
)

FEATURES = ipakit.load_ipa_features()


def _hierarchy() -> Form:
    builder = FormBuilder(FEATURES)
    utterance = builder.begin("utterance")
    phrase = builder.begin("phrase")
    segments = builder.append_ipa("kæt")
    builder.end(phrase)
    builder.end(utterance)
    builder.contain(phrase, segments)
    builder.contain(utterance, (phrase,))
    builder.add_root(utterance)
    return builder.build()


def _relation_shapes() -> Form:
    builder = FormBuilder(FEATURES)
    owner = builder.begin("utterance")
    first, second = builder.append_ipa("ab")
    builder.end(owner)
    builder.contain(owner, (first, second))
    builder.relate((first,), "alternatives", (first, second))
    builder.relate((first,), "selects", (second,))
    # Position-anchored relations are deliberately omitted by the current
    # projection. Keep that behavior pinned until its dedicated cutover.
    builder.relate((builder._builder.tick(0),), "inserts", (first,))
    builder.add_root(owner)
    return builder.build()


def _corpus() -> tuple[tuple[str, Form], ...]:
    parsed = Form.parse("#t͡s.∅ˈa..b#", FEATURES)
    held = Form.of(
        parsed.units,
        (
            Interval("syllable", 0, 4, FEATURES, Timing(0.0, 0.3)),
            Interval("mora", 1, 5, FEATURES),
            Interval("syllable", 0, 4, FEATURES, Timing(0.4, 0.2)),
        ),
    )
    edited = dataclasses.replace(held, intervals=held.intervals[1:])
    return (
        ("parsed-refined", parsed),
        ("form-of-held-intervals", held),
        ("dataclass-edited", edited),
        ("builder-hierarchy", _hierarchy()),
        ("relations-current-drops", _relation_shapes()),
    )


def test_native_fact_assembly_matches_embedded_capture_byte_for_byte() -> None:
    for name, form in _corpus():
        captured = form.__dict__["_tiergraph_index"].containment_input
        native = ContainmentProjectionInput.from_facts(
            captured.declarations,
            captured.clock,
            captured.relations,
            captured.roots,
        )

        assert native == captured, name
        expected = ContainmentProjection.build_captured(captured).graph
        actual = ContainmentProjection.build_captured(native).graph

        assert actual == expected, name
        assert actual.tiers == expected.tiers, name
        assert actual.position_values == expected.position_values, name
        assert actual.polyadic_relations == expected.polyadic_relations, name
        assert tuple(actual.canonical_items()) == tuple(
            expected.canonical_items()
        ), name
        assert tuple(
            item.durable_id for tier in actual.tiers for item in tier.items
        ) == tuple(
            item.durable_id for tier in expected.tiers for item in tier.items
        ), name
