"""Native Form admission keeps facts the former linear projection omitted."""

from dataclasses import replace

import ipakit
import pytest
from ipakit import Form, FormBuilder, IPAFeatures, Timing
from ipakit._containment_projection import ContainmentProjectionInput
from ipakit._form_profile import provider_identity
from ipakit._graph_facts import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FeatureDeclaration,
    TierDeclaration,
)
from ipakit._graph_facts import Timing as GraphTiming
from ipakit._rewrite_graph import japanese_moraic_fixture

import tiergraph as tg
from tiergraph import wire


def test_actual_japanese_shared_mora_graph_roundtrip():
    ipa = IPAFeatures()
    original = japanese_moraic_fixture("hot", ipa)
    encoded = original.to_json()
    restored = Form.from_json(encoded, ipa)
    assert restored.to_json() == encoded
    assert tg.to_data(restored.graph) == tg.to_data(original.graph)
    assert tuple(e["value"] for e in restored.tier_events("mora")) == ("ho", "t", "to")
    assert restored.to_ipa() == "hotːo"
    assert restored.roots == original.roots
    for path in original.__dict__["_tiergraph_index"].containment_input.refs:
        assert restored.parents(path) == original.parents(path)
    assert "digraph" in restored.to_dot()


def test_typed_qualified_json_and_optional_timing():
    ipa = IPAFeatures()
    declarations = Declarations(
        (TierDeclaration("token", frozenset({"fact"}), ("urn:test:form", "token")),),
        (FeatureDeclaration("fact", ("urn:test:form", "fact")),),
        (),
    )
    value = {
        "null": None,
        "false": False,
        "integer": 1,
        "double": 1.0,
        "sequence": ["p", "t"],
    }
    source = ContainmentProjectionInput.from_facts(
        declarations,
        (
            ClockNode(
                groups=(
                    EventGroup(
                        "token",
                        (
                            Event(
                                {"fact": value},
                                duration=0,
                                timing=GraphTiming(0.2, 0.3),
                            ),
                        ),
                    ),
                )
            ),
        ),
        roots=("/clock/0/token/0",),
    )
    original = Form._from_projection_input(source, features=ipa)
    restored = Form.from_json(original.to_json(), ipa)
    assert tg.to_data(restored.graph) == tg.to_data(original.graph)
    facts = restored.tier_events("token")[0]["fact"]
    assert facts["null"] is None and facts["false"] is False
    assert type(facts["integer"]) is int and type(facts["double"]) is float
    assert restored.at("/clock/0/token/0").timing.duration == 0.3


def test_empty_custom_provider_binding_is_explicit():
    custom = IPAFeatures(supplements=["aspirated-stops"])
    original = FormBuilder(custom).build()
    encoded = original.to_json()
    assert Form.from_json(encoded, custom).to_json() == encoded
    with pytest.raises(ValueError, match="inventory"):
        Form.from_json(encoded)


def test_mutated_loaded_provider_refuses_serialization_and_restoration():
    ipa = IPAFeatures()
    original = ipa.read("p")
    encoded = original.to_json()
    ipa.features["manner"].desc += " changed"
    with pytest.raises(ValueError, match="inventory"):
        original.to_json()
    with pytest.raises(ValueError, match="inventory"):
        Form.from_json(encoded, ipa)


def test_provider_identity_does_not_include_read_caches():
    ipa = IPAFeatures()
    before = provider_identity(ipa)
    ipa.read("ˈpʰaː")
    _ = ipa.stress_markers, ipa.features_by_mode, ipa.tie_marks
    assert provider_identity(ipa) == before


def test_unit_timing_and_literal_structure_survive():
    ipa = IPAFeatures()
    parsed = ipa.read("ⁿd͡ʒʷ")
    timed = Form.of((replace(parsed.units[0], timing=Timing(0.1, 0.4)),))
    restored = Form.from_json(timed.to_json(), ipa)
    assert restored.units[0].timing == Timing(0.1, 0.4)
    assert restored.units[0].segment.to_dict() == parsed.units[0].segment.to_dict()


def test_native_reader_returns_graph_and_form_reader_requires_profile():
    graph = tg.Graph((tg.NamespaceDeclaration("test", "urn:test"),), (), ())
    document = ipakit.write_graph_json(graph)
    assert isinstance(ipakit.read_graph_json(document), tg.Graph)
    with pytest.raises(ValueError, match="Form profile"):
        Form.from_json(document)
    with pytest.raises(ValueError):
        Form.from_json('{"type":"ipakit.form","v":2,"units":[]}')
    with pytest.raises(ValueError):
        ipakit.read_graph_json('{"format_version":"old","graph":{}}')


def test_pretty_and_compact_are_same_native_document():
    original = ipakit.read("t͜s")
    compact = original.to_json()
    pretty = original.to_json(pretty=True)
    assert len(compact) < len(pretty)
    assert wire.to_data(wire.loads(compact)) == wire.to_data(wire.loads(pretty))
    assert compact == wire.dump_compact(original.graph)


def test_opaque_value_refuses_with_source_context():
    builder = FormBuilder()
    builder.add_event("analysis", {"value": object()}, duration=0)
    with pytest.raises(ValueError, match="unrepresentable Form feature 'value'"):
        builder.build().to_json()


def test_conflicting_derived_scalar_payload_refuses():
    declarations = Declarations(
        (TierDeclaration("target", frozenset({"arc"})),),
        (FeatureDeclaration("arc"),),
        (),
    )
    source = ContainmentProjectionInput.from_facts(
        declarations,
        (
            ClockNode(
                groups=(EventGroup("target", (Event({"arc": 1.0}, duration=0),)),)
            ),
        ),
    )
    form = Form._from_projection_input(source)
    owner = form.graph.resolve_item(tg.DurableItemRef("/clock/0/target/0"))
    altered = (
        form.graph.edit()
        .set_attribute(
            owner,
            tg.AttributeValue(
                tg.QualifiedName(
                    "https://ipakit.dev/tiergraph/containment-projection/v1", "arc"
                ),
                tg.XsdType.DOUBLE,
                "2",
            ),
        )
        .freeze()
    )
    with pytest.raises(ValueError, match="constructor profile"):
        Form.from_json(wire.dump_compact(altered))


def test_native_profile_registry_reports_its_partial_scope():
    from ipakit._form_profile import graph_profile

    profile = graph_profile(IPAFeatures())
    registry = tg.ProfileRegistry()
    registry.register(profile)
    graph, roles = profile.satisfaction_witness()
    reports = registry.reports(graph, roles)
    assert any(report.unconfirmed for report in reports)
