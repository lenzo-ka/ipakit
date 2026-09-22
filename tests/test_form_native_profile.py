"""Native Form admission keeps facts the former linear projection omitted."""

import copy
import json
import math
import os
import pickle
import subprocess
import sys
from collections.abc import MutableMapping
from dataclasses import replace

import ipakit
import pytest
from ipakit import Form, FormBuilder, IPAFeatures, Timing
from ipakit._containment_projection import ContainmentProjectionInput
from ipakit._form_profile import (
    NS,
    SOURCE_EVENTS,
    TIER_ROLE,
    provider_identity,
)
from ipakit._graph_facts import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FeatureDeclaration,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._graph_facts import Timing as GraphTiming
from ipakit._rewrite_graph import japanese_moraic_fixture

import tiergraph as tg
from tiergraph import wire


def _literal_form(values):
    ipa = IPAFeatures()
    declarations = Declarations(
        (TierDeclaration("token", frozenset({"fact"})),),
        (FeatureDeclaration("fact", ("urn:test:literals", "fact")),),
        (),
    )
    events = tuple(
        Event({} if value is ... else {"fact": value}, duration=0) for value in values
    )
    source = ContainmentProjectionInput.from_facts(
        declarations,
        (ClockNode(groups=(EventGroup("token", events),)),),
    )
    return Form._from_projection_input(source, features=ipa), ipa


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
    assert (
        sum(
            event.features.get("phantom") is True
            for event in restored.__dict__[
                "_tiergraph_index"
            ].containment_input.events.values()
        )
        == 13
    )
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


def test_json_literal_kinds_empty_values_unicode_qname_shape_and_absence():
    values = (
        False,
        0,
        0.0,
        -0.0,
        None,
        ...,
        [],
        {},
        {"namespace": "urn:undeclared:user", "local_name": "still-data"},
        {"κλειδί": "値🙂"},
    )
    original, ipa = _literal_form(values)
    restored = Form.from_json(original.to_json(), ipa)
    relation = next(
        relation
        for relation in restored.graph.polyadic_relations
        if relation.declaration == SOURCE_EVENTS
    )
    name = tg.QualifiedName("urn:test:literals", "fact")
    actual = []
    for target in relation.targets:
        item = next(
            tier
            for tier in restored.graph.tiers
            if tier.declaration.name == target.tier
        ).items[target.index]
        values_on_item = [value for value in item.attributes if value.name == name]
        actual.append(values_on_item[0].to_value() if values_on_item else ...)
    assert type(actual[0]) is bool and actual[0] is False
    assert type(actual[1]) is int and actual[1] == 0
    assert type(actual[2]) is float and math.copysign(1, actual[2]) == 1
    assert type(actual[3]) is float and math.copysign(1, actual[3]) == -1
    assert actual[4] is None and actual[5] is ...
    assert actual[6:] == list(values[6:])


def test_json_attachment_snapshots_caller_containers():
    caller = {"values": [False, 0, -0.0, None]}
    original, ipa = _literal_form((caller,))
    encoded = original.to_json()
    caller["values"].append("mutated")
    restored = Form.from_json(encoded, ipa)
    assert restored.at("/clock/0/token/0").features["fact"] == {
        "values": (False, 0, -0.0, None)
    }


@pytest.mark.parametrize("fault", ["domain", "type", "extra"])
def test_json_profile_wire_refuses_wrong_domain_type_and_extra_field(fault):
    document = Form.parse("a").to_dict()
    graph = document["graph"]
    declarations = graph["attribute_declarations"]
    profile_declaration = next(d for d in declarations if d["name"] == "form:profile")
    metadata_tier = next(
        tier
        for tier in graph["tiers"]
        if tier["declaration"]["name"] == "form:metadata"
    )
    profile = next(
        value
        for value in metadata_tier["items"][0]["attributes"]
        if value["name"] == "form:profile"
    )
    if fault == "domain":
        profile_declaration["domain"] = "tier"
    elif fault == "type":
        profile["value_type"] = "string"
    else:
        profile["lexical"] = "not permitted beside JSON value"
    with pytest.raises(ValueError):
        Form.from_json(json.dumps(document, ensure_ascii=False))


def test_json_attribute_survives_edit_machine_and_wire_roundtrips():
    original, ipa = _literal_form(({"state": [False, 0, -0.0, None]},))
    owner = original.graph.resolve_item(tg.DurableItemRef("/clock/0/token/0"))
    name = tg.QualifiedName("urn:test:literals", "fact")
    edited = (
        original.graph.edit()
        .set_attribute(owner, tg.JsonAttributeValue(name, {"edited": [1, 1.0]}))
        .freeze()
    )
    restored = Form.from_json(wire.dump_compact(edited), ipa)
    assert restored.at("/clock/0/token/0").features["fact"] == {"edited": (1, 1.0)}
    assert wire.loads(wire.dump_compact(edited)) == edited

    from tiergraph.machine import (
        AddItem,
        DeclareAttribute,
        DeclareNamespace,
        DeclareTier,
        Program,
    )
    from tiergraph.machine_codec import program_dumps, program_loads

    tier = tg.QualifiedName("urn:test:machine", "tier")
    attribute = tg.QualifiedName("urn:test:machine", "json")
    program = Program(
        (
            DeclareNamespace(tg.NamespaceDeclaration("m", "urn:test:machine")),
            DeclareTier(tg.TierDeclaration(tier, "machine")),
            DeclareAttribute(
                tg.AttributeDeclaration(
                    attribute, tg.AttributeDomain.ITEM, tg.JsonType.JSON
                )
            ),
            AddItem(
                tier,
                tg.Item(attributes=(tg.JsonAttributeValue(attribute, {"x": -0.0}),)),
            ),
        )
    )
    assert (
        program_loads(program_dumps(program)).unroll().graph == program.unroll().graph
    )


def test_metadata_point_is_untimed_and_sources_events_only():
    graph = Form.parse("ab").graph
    metadata = next(
        tier for tier in graph.tiers if tier.declaration.name.namespace == NS
    )
    assert metadata.items[0].durable_id is None
    assert all(
        not attribute.name.local_name.startswith(("timing-", "span-"))
        for attribute in metadata.items[0].attributes
    )
    touching = [
        relation
        for relation in graph.polyadic_relations
        if tg.ItemRef(metadata.declaration.name, 0)
        in (*relation.sources, *relation.targets)
    ]
    assert [relation.declaration for relation in touching] == [SOURCE_EVENTS]


def test_foreign_qualified_tier_role_cannot_shadow_house_role():
    form = Form.parse("a")
    foreign = tg.QualifiedName("urn:foreign", TIER_ROLE.local_name)
    target = next(
        tier.declaration.name
        for tier in form.graph.tiers
        if any(attribute.name == TIER_ROLE for attribute in tier.attributes)
    )
    altered = (
        form.graph.edit()
        .declare(tg.NamespaceDeclaration("foreign", "urn:foreign"))
        .declare(
            tg.AttributeDeclaration(foreign, tg.AttributeDomain.TIER, tg.XsdType.STRING)
        )
        .set_attribute(target, tg.AttributeValue(foreign, tg.XsdType.STRING, "segment"))
        .freeze()
    )
    with pytest.raises(ValueError, match="foreign-qualified Form role shadows"):
        Form.from_json(wire.dump_compact(altered))


def test_source_events_target_order_is_the_codebook_order():
    form = Form.parse("ab")
    relations = list(form.graph.polyadic_relations)
    index = next(
        index
        for index, relation in enumerate(relations)
        if relation.declaration == SOURCE_EVENTS
    )
    relation = relations[index]
    relations[index] = replace(relation, targets=tuple(reversed(relation.targets)))
    altered = replace(form.graph, polyadic_relations=tuple(relations))
    with pytest.raises(
        ValueError, match="source-events targets are outside codebook order"
    ):
        Form.from_json(wire.dump_compact(altered))


def test_relation_endpoint_and_source_relation_order_round_trip():
    ipa = IPAFeatures()
    declarations = Declarations(
        (TierDeclaration("token"),),
        (),
        (
            RelationDeclaration(
                "links",
                source_arity=(2, 2),
                target_arity=(2, 2),
            ),
            RelationDeclaration("follows"),
        ),
    )
    clock = (
        ClockNode(groups=(EventGroup("token", tuple(Event({}) for _ in range(4))),)),
    )
    paths = tuple(f"/clock/0/token/{index}" for index in range(4))
    relations = (
        Relation((paths[1], paths[0]), "links", (paths[3], paths[2])),
        Relation((paths[2],), "follows", (paths[1],)),
    )
    source = ContainmentProjectionInput.from_facts(declarations, clock, relations)
    restored = Form.from_json(
        Form._from_projection_input(source, features=ipa).to_json(), ipa
    )
    assert (
        restored.__dict__["_tiergraph_index"].containment_input.relations == relations
    )


def test_unit_and_event_timing_are_independent():
    ipa = IPAFeatures()
    base_unit = ipa.read("a").units[0]
    unit = replace(base_unit, timing=Timing(0.1, 0.2))
    declarations = Declarations(
        (TierDeclaration("token", frozenset({"unit", "unit-index", "input"})),),
        tuple(FeatureDeclaration(name) for name in ("unit", "unit-index", "input")),
        (),
    )
    source = ContainmentProjectionInput.from_facts(
        declarations,
        (
            ClockNode(
                groups=(
                    EventGroup(
                        "token",
                        (
                            Event(
                                {"unit": unit, "unit-index": 0, "input": True},
                                timing=GraphTiming(0.5, 0.4),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    restored = Form.from_json(
        Form._from_projection_input(source, features=ipa).to_json(), ipa
    )
    restored_event = restored.at("/clock/0/token/0")
    assert restored_event.timing == GraphTiming(0.5, 0.4)
    assert restored.units[0].timing == Timing(0.1, 0.2)


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


def test_provider_identity_is_cached_and_declaration_mutations_invalidate(
    monkeypatch: pytest.MonkeyPatch,
):
    import ipakit._form_profile as profile

    ipa = IPAFeatures()
    calls = 0
    snapshot = profile._snapshot

    def counted(value: object):
        nonlocal calls
        calls += 1
        return snapshot(value)

    monkeypatch.setattr(profile, "_snapshot", counted)
    identities = [provider_identity(ipa)]
    first_calls = calls
    assert first_calls > 0
    assert provider_identity(ipa) == identities[-1]
    assert calls == first_calls

    ipa.features["manner"].desc += " changed"
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]

    ipa.features["manner"].value_classes["fixture"] = frozenset({"stop"})
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]

    ipa.notations["fixture"] = "chart"
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]

    ipa.modes.append("fixture")
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]

    ipa.features["manner"].value_classes["mutable-fixture"] = {"stop"}
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]
    ipa.features["manner"].value_classes["mutable-fixture"] |= {"nasal"}
    identities.append(provider_identity(ipa))
    assert identities[-1] != identities[-2]


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


_IDENTITY_PROGRAM = """
import sys
from ipakit import IPAFeatures
from ipakit._form_profile import provider_identity
print(provider_identity(IPAFeatures()))
"""

_WRITE_PROGRAM = """
import sys
from ipakit import IPAFeatures
sys.stdout.write(IPAFeatures().read("ˈpʰaː.ta").to_json())
"""

_READ_PROGRAM = """
import sys
from ipakit import Form, IPAFeatures
encoded = sys.stdin.read()
form = Form.from_json(encoded, IPAFeatures())
print(form.to_ipa())
print(form.to_json() == encoded)
"""


def _subprocess(program: str, seed: str, stdin: str | None = None):
    environment = {**os.environ, "PYTHONHASHSEED": seed}
    return subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
        input=stdin,
        env=environment,
    ).stdout


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_provider_identity_is_the_same_in_another_process(seed: str):
    """Serializing here and restoring there needs one identity everywhere.

    The identity hashes mappings as ordered pairs, because their keys are not
    all strings, so nothing about the hash is order-free by construction.
    """
    assert _subprocess(_IDENTITY_PROGRAM, seed).strip() == provider_identity(
        IPAFeatures()
    )


def test_a_form_written_in_one_process_restores_in_another():
    written = _subprocess(_WRITE_PROGRAM, "1")
    read = _subprocess(_READ_PROGRAM, "12345", stdin=written).split("\n")
    assert read[0] == "ˈpʰaː.ta"
    assert read[1] == "True"


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop(next(iter(d))), id="dict-pop"),
        pytest.param(lambda d: d.popitem(), id="dict-popitem"),
        pytest.param(lambda d: d.clear(), id="dict-clear"),
        pytest.param(lambda d: d.setdefault("zz", None), id="dict-setdefault"),
        pytest.param(lambda d: d.update({"zz": None}), id="dict-update"),
        pytest.param(lambda d: d.__delitem__(next(iter(d))), id="dict-delitem"),
        pytest.param(lambda d: d.__ior__({"zz": None}), id="dict-ior"),
    ],
)
def test_every_mapping_mutator_invalidates_the_identity(mutate):
    ipa = IPAFeatures()
    before = provider_identity(ipa)
    mutate(ipa.notations)
    assert provider_identity(ipa) != before


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda v: v.append("zz"), id="append"),
        pytest.param(lambda v: v.extend(["zz"]), id="extend"),
        pytest.param(lambda v: v.insert(0, "zz"), id="insert"),
        pytest.param(lambda v: v.remove(v[0]), id="remove"),
        pytest.param(lambda v: v.pop(), id="pop"),
        pytest.param(lambda v: v.reverse(), id="reverse"),
        pytest.param(lambda v: v.sort(), id="sort"),
        pytest.param(lambda v: v.clear(), id="clear"),
        pytest.param(lambda v: v.__iadd__(["zz"]), id="iadd"),
        pytest.param(lambda v: v.__imul__(2), id="imul"),
    ],
)
def test_every_sequence_mutator_invalidates_the_identity(mutate):
    ipa = IPAFeatures()
    provider_identity(ipa)
    values = ipa.features["manner"].values
    before = provider_identity(ipa)
    mutate(values)
    assert provider_identity(ipa) != before


def test_a_declaration_the_identity_cannot_track_is_refused_at_wrap():
    """A mutable container the identity reads but cannot watch would go stale."""

    class Custom(MutableMapping):
        def __init__(self):
            self._data = {"a": 1}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def __delitem__(self, key):
            del self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

    ipa = IPAFeatures()
    object.__setattr__(ipa, "notations", Custom())
    with pytest.raises(TypeError, match="cannot track for mutation"):
        provider_identity(ipa)


def test_a_provider_that_has_served_a_form_still_copies_and_pickles():
    ipa = IPAFeatures()
    ipa.read("pa").to_json()
    before = provider_identity(ipa)
    for copied in (
        copy.deepcopy(ipa.notations),
        pickle.loads(pickle.dumps(ipa.notations)),
    ):
        assert dict(copied) == dict(ipa.notations)
        assert type(copied) is dict
    assert provider_identity(ipa) == before
