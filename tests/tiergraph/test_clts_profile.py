"""Synthetic source facts exercise native structure, not CLTS resolution."""

import builtins
import os
import subprocess
import sys
from dataclasses import replace
from importlib import metadata as package_metadata
from pathlib import Path

import pytest
from ipakit import clts
from ipakit._clts_input import FORMAT, HOST, InputError
from ipakit._clts_profile import (
    FINAL_MANIFEST_KIND,
    ORDER,
    SourceProfileSpec,
    construct,
    core_bipa_basis,
    core_bipa_resolutions,
    core_bipa_spec,
    declarations,
    graph_profile,
    manifest_metadata,
    metadata,
    name,
    profile_basis,
    require_final_manifest,
    require_manifest_kind,
    restore,
)
from ipakit._containment_projection import ContainmentProjection, declared_value
from ipakit._fact_builder import FactBuilder
from ipakit._graph_facts import (
    Declarations,
    FeatureDeclaration,
    GraphValidationError,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._identity import identity_fingerprint
from ipakit._provenance import SourceMetadata
from ipakit.clts import read_snapshot

import tiergraph as tg

NS = "urn:fixture:source"
HOUSE_NS = "urn:fixture:house"
MAPPING = "fixture-mapping"
HERE = Path(__file__).parent
CORE_EXAMPLE = HERE / "fixtures" / "clts_core_bipa_profile.json"


def spec(**changes):
    return replace(
        SourceProfileSpec(
            SourceMetadata(
                "fixture", "urn:fixture", "synthetic", "1", "fixture", "test"
            ),
            "fixture-provider",
            "fixture-manifest",
            MAPPING,
            ("tone", "consonant"),
            (
                FeatureDeclaration("claims", (NS, "claims")),
                FeatureDeclaration("unused", (NS, "unused")),
            ),
            (FeatureDeclaration("house-symbol", (HOUSE_NS, "symbol")),),
            manifest_kind="fixture",
        ),
        **changes,
    )


def resolution(kind="consonant", values=None):
    return {
        "provider": "fixture-provider",
        "status": "resolved",
        "sounds": [{"kind": kind, "canonical": "synthetic", "values": values or {}}],
    }


def projection(status="not-attempted", **values):
    return {"mapping": MAPPING, "status": status, **values}


def not_attempted(count):
    return [projection() for _ in range(count)]


def supported(symbol):
    return projection("supported", facts=[{"house-symbol": symbol}])


@pytest.mark.parametrize(
    "wrapper", [lambda x: (x,), lambda x: [(x,)], lambda x: {"nested": (x,)}]
)
def test_profile_owns_every_native_json_container(wrapper):
    leaf = []
    schema = spec(domains={"claims": (wrapper(leaf),)})
    before = metadata(schema)
    before_identity = schema.identity
    leaf.append(1)
    assert metadata(schema) == before
    assert schema.identity == before_identity == before["fingerprint"]


def test_profile_identity_is_typed_and_hashable():
    boolean = spec(domains={"claims": (False,)})
    integer = spec(domains={"claims": (0,)})
    assert boolean != integer
    assert boolean == spec(domains={"claims": (False,)})
    assert len({boolean, integer, spec(domains={"claims": (False,)})}) == 2


def test_profile_normalizes_native_arrays_without_losing_json_types():
    tuples = spec(domains={"claims": ((False, 0, None, ()),)})
    lists = spec(domains={"claims": ([False, 0, None, []],)})
    assert tuples == lists
    assert metadata(tuples)["domains"] == {"claims": [[False, 0, None, []]]}
    assert tuples != spec(domains={"claims": ([0, False, None, []],)})


def test_profile_identity_includes_constructor_field_bindings():
    first = spec(fields=(FeatureDeclaration("first", (NS, "same")),))
    second = spec(fields=(FeatureDeclaration("second", (NS, "same")),))
    assert first != second


def test_profile_refuses_mutable_source_metadata():
    with pytest.raises(ValueError, match="source metadata fields"):
        spec(source=replace(spec().source, version=[]))


def test_bound_profile_registry_names_are_distinct():
    first = graph_profile(spec())
    second = graph_profile(spec(provider_fingerprint="second-provider"))
    assert first.name != second.name
    registry = tg.ProfileRegistry()
    registry.register(first)
    registry.register(second)


def test_unknown_sound_status_roundtrips():
    record = {"provider": "fixture-provider", "status": "unknown-sound", "sounds": []}
    schema = spec()
    assert restore(construct(["?"], [record], not_attempted(1), schema), schema)[1] == (
        record,
    )


def test_marker_status_roundtrips_without_calling_it_unknown():
    record = {"provider": "fixture-provider", "status": "marker", "sounds": []}
    schema = spec()
    assert restore(construct(["+"], [record], not_attempted(1), schema), schema)[1] == (
        record,
    )


def test_core_bipa_adapter_exact_records_and_miss_statuses():
    snapshot = read_snapshot()
    records = core_bipa_resolutions(snapshot, ("t", "⁵", " ɺ̣", "+", "☃"))
    assert records[0] == {
        "provider": (
            "sha256:8b5620aed4b88e6d14d02ddbd6e404fbe9bf9b13577851acd244a95b5793dcc4"
        ),
        "status": "resolved",
        "sounds": [
            {
                "kind": "consonant",
                "canonical": "t",
                "values": {
                    "features": ["alveolar", "consonant", "stop", "voiceless"],
                    "alias": False,
                    "normalized": False,
                    "declaration": "t",
                },
            }
        ],
    }
    assert records[1]["sounds"] == [
        {
            "kind": "tone",
            "canonical": "⁵",
            "values": {
                "features": ["from-high", "short", "tone"],
                "alias": False,
                "normalized": False,
                "declaration": "⁵",
            },
        }
    ]
    assert [record["status"] for record in records] == [
        "resolved",
        "resolved",
        "unknown-sound",
        "marker",
        "outside-artifact-domain",
    ]
    assert all(not record["sounds"] for record in records[2:])


def test_reduced_core_bipa_distinguishes_unknown_from_artifact_miss():
    data = read_snapshot().to_data()
    data["requested"] = ["t", "☃"]
    data["entries"] = {"t": data["entries"]["t"]}
    data["excluded"] = {"☃": "unknown-source-spelling"}
    material = {key: value for key, value in data.items() if key != "identity"}
    snapshot = clts.Snapshot({**material, "identity": identity_fingerprint(material)})

    raws = ("t", "☃", "ai")
    records = core_bipa_resolutions(snapshot, raws)

    assert {
        raw: record["status"] for raw, record in zip(raws, records, strict=True)
    } == {
        "t": "resolved",
        "☃": "unknown-sound",
        "ai": "outside-artifact-domain",
    }
    assert records[0]["sounds"][0]["canonical"] == "t"
    assert records[1]["sounds"] == records[2]["sounds"] == []


def test_live_resolvable_omission_stays_outside_artifact_domain(
    monkeypatch: pytest.MonkeyPatch,
):
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for the live resolver witness")
    pytest.importorskip("pyclts")
    live = clts.extract_snapshot(Path(value), tokens=["ai", "☃"])
    assert live.to_data()["entries"]["ai"]["kind"] == "diphthong"
    assert live.to_data()["excluded"] == {"☃": "unknown-sound"}

    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "pyclts" or name.startswith("pyclts."):
            raise AssertionError("profile adapter attempted a live resolver fallback")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert core_bipa_resolutions(read_snapshot(), ("ai",)) == (
        {
            "provider": (
                "sha256:8b5620aed4b88e6d14d02ddbd6e404fbe9bf9b13577851acd244a95b5793dcc4"
            ),
            "status": "outside-artifact-domain",
            "sounds": [],
        },
    )


def test_core_bipa_exact_nfc_nfd_spellings_keep_their_raws():
    snapshot = read_snapshot()
    schema = core_bipa_spec(snapshot)
    raws = ["ç", "ç"]
    records = core_bipa_resolutions(snapshot, raws)
    projections_in = [
        {"mapping": schema.mapping_identity, "status": "not-attempted"} for _ in raws
    ]
    document, restored, projections = restore(
        construct(raws, records, projections_in, schema), schema
    )
    assert [token["raw"] for token in document["tokens"]] == ["ç", "ç"]
    assert [record["sounds"][0]["values"]["normalized"] for record in restored] == [
        True,
        True,
    ]
    assert [record["sounds"][0]["values"]["declaration"] for record in restored] == [
        "ç",
        "ç",
    ]
    assert list(projections) == projections_in


def test_core_bipa_spec_binds_verified_final_manifest():
    snapshot = read_snapshot()
    schema = core_bipa_spec(snapshot)
    manifest = manifest_metadata()
    assert schema.provider_fingerprint == snapshot.identity
    assert schema.mapping_identity == (
        "sha256:75d0647365cec49b1151e22c9a909ddf1995ce3f6e5e203d8ab6e62969b6e860"
    )
    assert core_bipa_basis() == (
        "sha256:6078e6a669c7517792c96bf1fbdec0a07e44260cba5e20cb0b49d6682b741cba"
    )
    assert schema.identity == (
        "sha256:97d89d0c1a879618c1de6b7a5f06cd350d143fb5672b0553a7bfd84961a28127"
    )
    assert [(field.name, field.value_name) for field in schema.house_fields] == [
        (
            "house-symbol",
            ("https://ipakit.dev/tiergraph/house-projection/v1", "symbol"),
        ),
        (
            "house-kind",
            ("https://ipakit.dev/tiergraph/house-projection/v1", "kind"),
        ),
    ]
    assert schema.manifest_kind == manifest["kind"] == FINAL_MANIFEST_KIND
    assert schema.manifest_fingerprint == manifest["fingerprint"]
    require_final_manifest(schema)
    with pytest.raises(ValueError, match="manifest kind mismatch"):
        require_manifest_kind(schema, "interim")


def test_profile_basis_excludes_exactly_mapping_with_literal_keys():
    schema = core_bipa_spec(
        mapping_identity=(
            "sha256:75d0647365cec49b1151e22c9a909ddf1995ce3f6e5e203d8ab6e62969b6e860"
        )
    )
    material = metadata(schema)
    basis_material = {
        key: value
        for key, value in material.items()
        if key not in {"mapping", "fingerprint"}
    }
    assert set(basis_material) == {
        "id",
        "version",
        "roles",
        "schema",
        "fields",
        "house-fields",
        "domains",
        "kinds",
        "source",
        "provider",
        "manifest",
        "coverage",
        "invalidation",
        "decides",
        "undecided",
    }
    assert profile_basis(schema) == identity_fingerprint(basis_material)
    assert profile_basis(
        replace(schema, mapping_identity="sha256:" + "0" * 64)
    ) == profile_basis(schema)


def test_core_bipa_committed_example_has_hand_authored_facts():
    graph = tg.loads(CORE_EXAMPLE.read_text())
    document, records, projections = restore(graph, core_bipa_spec())
    assert [token["raw"] for token in document["tokens"]] == [
        "t",
        "⁵",
        "t",
        " ɺ̣",
        "+",
        "☃",
        "ts",
    ]
    assert document["tokens"][0]["time"] == {"start": 1.25, "duration": 0.5}
    assert document["relations"] == [
        {
            "type": "clts:source-tone-host",
            "source": "/tokens/1",
            "target": "/tokens/0",
        }
    ]
    assert [record["status"] for record in records] == [
        "resolved",
        "resolved",
        "resolved",
        "unknown-sound",
        "marker",
        "outside-artifact-domain",
        "resolved",
    ]
    mapping = "sha256:75d0647365cec49b1151e22c9a909ddf1995ce3f6e5e203d8ab6e62969b6e860"
    assert projections == (
        {
            "mapping": mapping,
            "status": "supported",
            "facts": [{"house-symbol": "t", "house-kind": "segment"}],
        },
        {
            "mapping": mapping,
            "status": "unsupported",
            "code": "outside-reviewed-token-context",
        },
        {
            "mapping": mapping,
            "status": "supported",
            "facts": [{"house-symbol": "t", "house-kind": "segment"}],
        },
        {"mapping": mapping, "status": "not-attempted"},
        {"mapping": mapping, "status": "not-attempted"},
        {"mapping": mapping, "status": "not-attempted"},
        {
            "mapping": mapping,
            "status": "unsupported",
            "code": "unasserted-house-juncture",
        },
    )
    assert declared_value(graph, tg.ItemRef(name("metadata"), 0), name("coverage")) == {
        "status": "preserved",
        "source_complete": True,
        "house_complete": False,
    }
    ticks = {
        int(attribute.lexical)
        for boundary in graph.boundary_values
        for attribute in boundary.attributes
        if attribute.name.local_name == "tick"
    }
    assert ticks == {0, 1, 2, 3, 4, 5, 6, 7}


def test_core_bipa_example_regeneration_is_byte_equal():
    root = Path(__file__).resolve().parents[2]
    code = r"""
import builtins, runpy, sys
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] == 'pyclts':
        raise AssertionError('pyclts import attempted')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(root / "scripts/clts_profile_example.py"),
        ],
        cwd=root,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == CORE_EXAMPLE.read_bytes()


def test_native_roundtrip_clock_children_times_hosts():
    schema = spec()
    doc = {
        "format": FORMAT,
        "version": 1,
        "tokens": [
            {"raw": "t͜s", "time": {"start": 0, "duration": 0.2}},
            {"raw": "⁵"},
            {"raw": "t͜s", "time": {"start": 0, "duration": 0}},
        ],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    first = resolution(values={"claims": {"literal": [False, 0, None, ""]}})
    first["sounds"].append({"kind": "consonant", "canonical": "second", "values": {}})
    records = [
        first,
        resolution("tone"),
        {
            "provider": "fixture-provider",
            "status": "outside-artifact-domain",
            "sounds": [],
        },
    ]
    graph = construct(doc, records, not_attempted(3), schema)
    restored = tg.loads(tg.dumps(graph))
    assert restore(restored, schema) == (
        doc,
        tuple(records),
        tuple(not_attempted(3)),
    )
    assert {
        a.lexical
        for boundary in graph.boundary_values
        for a in boundary.attributes
        if a.name.local_name == "tick"
    } == {"0", "1", "2", "3"}
    children = next(
        t for t in graph.tiers if t.declaration.name == name("source-sound")
    )
    assert len(children.items) == 3
    assert all(
        not any(a.name.local_name.startswith("timing-") for a in item.attributes)
        for item in children.items
    )
    assert tg.QualifiedName(NS, "unused") in {
        d.name for d in graph.attribute_declarations
    }


def test_empty_schema_profile_and_presence():
    schema = spec()
    graph = construct([], [], [], schema)
    assert restore(tg.loads(tg.dumps(graph)), schema)[0] == {
        "format": FORMAT,
        "version": 1,
        "tokens": [],
    }
    assert tg.QualifiedName(NS, "unused") in {
        d.name for d in graph.attribute_declarations
    }
    assert declared_value(graph, tg.ItemRef(name("metadata"), 0), name("coverage")) == {
        "status": "complete",
        "source_complete": True,
        "house_complete": True,
    }
    explicit = {"format": FORMAT, "version": 1, "tokens": [], "relations": []}
    assert restore(construct(explicit, [], [], schema), schema)[0] == explicit
    assert (
        metadata(schema)["fingerprint"]
        != metadata(spec(domains={"unused": (False, 0)}))["fingerprint"]
    )
    registry = tg.ProfileRegistry()
    profile = graph_profile(schema)
    registry.register(profile)
    assert (
        registry.report(profile.name, graph, schema.roles()).outcome
        is tg.ProfileOutcome.SATISFIED_AS_CHECKED
    )
    assert (
        registry.report(profile.name, *profile.refusal_witness()).outcome
        is tg.ProfileOutcome.REFUSED
    )


def test_supported_house_facts_roundtrip_in_supplied_projects_order_without_ticks():
    schema = spec()
    records = [resolution(), resolution()]
    projections = [supported("first"), supported("second")]
    graph = construct(["x", "y"], records, projections, schema)

    assert restore(tg.loads(tg.dumps(graph)), schema)[2] == tuple(projections)
    house = next(
        tier
        for tier in graph.tiers
        if tier.declaration.name == name("house-projection")
    )
    assert len(house.items) == 2
    assert {
        int(attribute.lexical)
        for boundary in graph.boundary_values
        for attribute in boundary.attributes
        if attribute.name.local_name == "tick"
    } == {0, 1, 2}
    assert all(
        next(
            attribute
            for attribute in item.attributes
            if attribute.name.local_name == "structural-duration"
        ).lexical
        == "0"
        for item in house.items
    )
    projects = [
        relation
        for relation in graph.polyadic_relations
        if relation.declaration == name("projects")
    ]
    assert sorted(
        int(attribute.lexical)
        for relation in projects
        for attribute in relation.attributes
        if attribute.name == ORDER
    ) == [0, 1]


def test_unsupported_projection_cannot_carry_a_house_fact():
    bad = projection(
        "unsupported",
        code="unasserted-house-juncture",
        facts=[{"house-symbol": "invented"}],
    )
    with pytest.raises(InputError, match="status and projection fields disagree"):
        construct(["ts"], [resolution()], [bad], spec())

    schema = spec()
    graph = construct(["ts"], [resolution()], [supported("invented")], schema)
    changed = graph.set_attribute(
        tg.ItemRef(name("source-token"), 0),
        tg.JsonAttributeValue(
            name("projection"),
            {
                "mapping": MAPPING,
                "status": "unsupported",
                "code": "unasserted-house-juncture",
            },
        ),
    )
    with pytest.raises(ValueError, match="not owned by a supported projection"):
        restore(changed, schema)


def test_not_attempted_projection_cannot_claim_house_complete():
    schema = spec()
    graph = construct(["x"], [resolution()], not_attempted(1), schema)
    changed = graph.set_attribute(
        tg.ItemRef(name("metadata"), 0),
        tg.JsonAttributeValue(
            name("coverage"),
            {
                "status": "complete",
                "source_complete": True,
                "house_complete": True,
            },
        ),
    )
    with pytest.raises(ValueError, match="coverage does not match"):
        restore(changed, schema)


def test_projection_refuses_a_foreign_mapping_identity():
    foreign = {"mapping": "foreign-mapping", "status": "not-attempted"}
    with pytest.raises(InputError, match="another mapping"):
        construct(["x"], [resolution()], [foreign], spec())

    schema = spec()
    graph = construct(["x"], [resolution()], not_attempted(1), schema)
    changed = graph.set_attribute(
        tg.ItemRef(name("source-token"), 0),
        tg.JsonAttributeValue(name("projection"), foreign),
    )
    with pytest.raises(InputError, match="another mapping"):
        restore(changed, schema)


def test_restore_refuses_reversed_projects_order():
    schema = spec()
    graph = construct(
        ["x", "y"],
        [resolution(), resolution()],
        [supported("first"), supported("second")],
        schema,
    )
    relations = []
    for relation in graph.polyadic_relations:
        if relation.declaration != name("projects"):
            relations.append(relation)
            continue
        attributes = []
        for attribute in relation.attributes:
            attributes.append(
                replace(attribute, lexical=str(1 - int(attribute.lexical)))
                if attribute.name == ORDER
                else attribute
            )
        relations.append(replace(relation, attributes=tuple(attributes)))
    changed = replace(graph, polyadic_relations=tuple(relations))
    with pytest.raises(ValueError, match="projects relation order"):
        restore(changed, schema)


@pytest.mark.parametrize(
    "change",
    [
        {"provider_fingerprint": "different"},
        {"manifest_fingerprint": "different"},
        {"manifest_kind": "different"},
        {"mapping_identity": "different"},
        {"domains": {"unused": (True,)}},
        {"fields": (FeatureDeclaration("different", (NS, "different")),)},
        {
            "house_fields": (
                FeatureDeclaration("different-house", (HOUSE_NS, "different")),
            )
        },
        {"kinds": ("tone",)},
    ],
)
def test_bound_profile_refuses_changed_declarations(change):
    graph = construct([], [], [], spec())
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        restore(graph, spec(**change))


def test_unused_declaration_and_metadata_tamper_refuse():
    schema = spec()
    graph = construct([], [], [], schema)
    lost = replace(
        graph,
        attribute_declarations=tuple(
            d
            for d in graph.attribute_declarations
            if d.name != tg.QualifiedName(NS, "unused")
        ),
    )
    with pytest.raises(ValueError, match="constructor layout"):
        restore(lost, schema)
    # Alter the native JSON profile without changing its claimed fingerprint.
    metadata_tier = next(
        t for t in graph.tiers if t.declaration.name == name("metadata")
    )
    attr = next(
        a for a in metadata_tier.items[0].attributes if a.name == name("profile")
    )
    assert isinstance(attr, tg.JsonAttributeValue)
    payload = attr.to_value()
    payload["provider"] = "tampered"
    changed = graph.set_attribute(
        tg.ItemRef(name("metadata"), 0), tg.JsonAttributeValue(attr.name, payload)
    )
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        restore(changed, schema)


@pytest.mark.parametrize(
    "source,target",
    [("consonant", "consonant"), ("tone", "tone"), (None, "consonant"), ("tone", None)],
)
def test_host_kind_refusals(source, target):
    records = [resolution(target), resolution(source)]
    for i, kind in enumerate((target, source)):
        if kind is None:
            records[i] = {
                "provider": "fixture-provider",
                "status": "unknown-sound",
                "sounds": [],
            }
    doc = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "x"}, {"raw": "y"}],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    with pytest.raises(InputError, match="resolved tone"):
        construct(doc, records, not_attempted(2), spec())


def test_native_unique_source_not_single_parent():
    doc = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "x"}, {"raw": "y"}, {"raw": "z"}],
        "relations": [
            {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"},
            {"type": HOST, "source": "/tokens/2", "target": "/tokens/0"},
        ],
    }
    records = [resolution(), resolution("tone"), resolution("tone")]
    graph = construct(doc, records, not_attempted(3), spec())
    assert restore(graph, spec())[0] == doc
    doc["relations"][1]["source"] = "/tokens/1"
    with pytest.raises(ValueError):
        construct(doc, records, not_attempted(3), spec())


def test_supplied_relation_order_is_native_and_restores_exactly():
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "x"}, {"raw": "y"}, {"raw": "z"}],
        "relations": [
            {"type": HOST, "source": "/tokens/2", "target": "/tokens/0"},
            {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"},
        ],
    }
    records = [resolution(), resolution("tone"), resolution("tone")]
    graph = construct(document, records, not_attempted(3), spec())
    other = {
        **document,
        "relations": list(reversed(document["relations"])),
    }
    assert restore(tg.loads(tg.dumps(graph)), spec())[0] == document
    assert tg.dumps(graph) != tg.dumps(
        construct(other, records, not_attempted(3), spec())
    )
    orders = sorted(
        int(attribute.lexical)
        for relation in graph.polyadic_relations
        if relation.declaration == name("source-tone-host")
        for attribute in relation.attributes
        if attribute.name == ORDER
    )
    assert orders == [0, 1]


def test_hand_added_relation_refused_by_constructor_layout_count():
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "x"}, {"raw": "y"}, {"raw": "z"}],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    schema = spec()
    graph = construct(
        document,
        [resolution(), resolution("tone"), resolution("tone")],
        not_attempted(3),
        schema,
    )
    editor = graph.edit()
    editor.add_relation(
        tg.PolyadicRelationInstance(
            name("source-tone-host"),
            (tg.ItemRef(name("source-token"), 2),),
            (tg.ItemRef(name("source-token"), 0),),
            attributes=(tg.AttributeValue(ORDER, tg.XsdType.INTEGER, "1"),),
        )
    )
    changed = editor.freeze()
    with pytest.raises(ValueError, match="relation count mismatch"):
        restore(changed, schema)


def test_domain_types_and_unknown_claims():
    schema = spec(domains={"claims": (False,)})
    construct(["x"], [resolution(values={"claims": False})], not_attempted(1), schema)
    with pytest.raises(InputError, match="outside declared"):
        construct(["x"], [resolution(values={"claims": 0})], not_attempted(1), schema)
    with pytest.raises(InputError, match="undeclared"):
        construct(["x"], [resolution(values={"other": 1})], not_attempted(1), schema)


def test_native_qualified_names_and_endpoint_restrictions():
    declared = declarations(spec())
    builder = FactBuilder(declared)
    token = builder.append_input_atom("source-token", {"raw": "x"})
    child = builder.add_event("source-sound", 0, {"kind": "tone"})
    builder.relate([child], HOST, [token])
    with pytest.raises(ValueError):
        ContainmentProjection.from_input(builder.build_input())
    assert declared.tiers[0].native_name == (
        name("source-token").namespace,
        "source-token",
    )


def test_qualified_declaration_collisions_and_reserved_namespace():
    with pytest.raises(GraphValidationError):
        TierDeclaration(
            "bad",
            native_name=(
                "https://ipakit.dev/tiergraph/containment-projection/v1",
                "clock",
            ),
        )
    with pytest.raises(GraphValidationError, match="duplicate native tier"):
        Declarations(
            (
                TierDeclaration("a", native_name=(NS, "same")),
                TierDeclaration("b", native_name=(NS, "same")),
            ),
            (),
            (),
        )
    with pytest.raises(GraphValidationError, match="duplicate native relation"):
        Declarations(
            (),
            (FeatureDeclaration("x", (NS, "same")),),
            (RelationDeclaration("other", native_name=(NS, "same")),),
        )


def test_nested_domain_and_input_mutation_do_not_change_graph():
    value = {"nested": [False, 0, None]}
    schema = spec(domains={"claims": (value,)})
    before = metadata(schema)
    record = resolution(values={"claims": {"nested": [False, 0, None]}})
    graph = construct(["x"], [record], not_attempted(1), schema)
    value["nested"].append("changed")
    record["sounds"][0]["values"]["claims"]["nested"].append("changed")
    assert metadata(schema) == before
    assert restore(graph, schema)[1][0]["sounds"][0]["values"] == {
        "claims": {"nested": [False, 0, None]}
    }


def test_unrelated_native_content_refused_not_dropped():
    schema = spec()
    graph = construct([], [], [], schema)
    extra = replace(
        graph,
        tiers=graph.tiers
        + (tg.Tier(tg.TierDeclaration(name("unrelated"), "unrelated"), ()),),
    )
    with pytest.raises(ValueError, match="constructor layout"):
        restore(extra, schema)
    assert any(t.declaration.name == name("unrelated") for t in extra.tiers)


def test_native_relation_constraint_mutation_refused():
    schema = spec()
    graph = construct([], [], [], schema)
    changed = replace(
        graph,
        relation_declarations=tuple(
            (
                replace(d, unique_sources=False)
                if d.name == name("source-tone-host")
                else d
            )
            for d in graph.relation_declarations
        ),
    )
    with pytest.raises(ValueError, match="constructor layout"):
        restore(changed, schema)


def test_declared_value_target_requires_native_json_profile():
    schema = spec()
    graph = construct(["x"], [resolution()], not_attempted(1), schema)
    token_tier = next(
        tier for tier in graph.tiers if tier.declaration.name == name("source-token")
    )
    raw = next(a for a in token_tier.items[0].attributes if a.name == name("raw"))
    assert isinstance(raw, tg.JsonAttributeValue)
    changed = graph.set_attribute(
        tg.ItemRef(name("source-token"), 0),
        tg.JsonAttributeValue(raw.name, {"not": "a token string"}),
    )
    with pytest.raises(ValueError):
        restore(changed, schema)


def test_clock_and_role_mutations_refuse():
    schema = spec()
    graph = construct(["x"], [resolution()], not_attempted(1), schema)
    boundary = graph.boundary_values[0]
    tick = next(a for a in boundary.attributes if a.name.local_name == "tick")
    changed = graph.set_attribute(boundary.reference, replace(tick, lexical="9"))
    with pytest.raises(ValueError, match="constructor layout"):
        restore(changed, schema)
    # Removing a referenced role is already a native graph error, not a profile pass.
    with pytest.raises(ValueError):
        replace(
            graph,
            tiers=tuple(
                t for t in graph.tiers if t.declaration.name != name("metadata")
            ),
        )


@pytest.mark.parametrize(
    "records",
    [
        None,
        {},
        "x",
        [],
        [{"provider": "other", "status": "unknown-sound", "sounds": []}],
        [{"provider": "fixture-provider", "status": "resolved", "sounds": []}],
    ],
)
def test_resolution_boundary_refuses_without_guessing(records):
    with pytest.raises(InputError):
        construct(["unknown"], records, not_attempted(1), spec())


def test_fresh_process_restores_without_optional_providers(tmp_path):
    root = Path(__file__).resolve().parents[2]
    code = """
import builtins, sys
from importlib import metadata
from pathlib import Path
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] in {'pyclts', 'panphon'}:
        raise AssertionError('optional provider import attempted')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
import ipakit
assert Path(ipakit.__file__).resolve().parent.parent == Path(sys.argv[1])
import tiergraph as tg
assert metadata.version('tiergraph') == sys.argv[2]
from ipakit._clts_profile import core_bipa_spec, restore
document, records, projections = restore(tg.loads(sys.stdin.read()), core_bipa_spec())
assert [token['raw'] for token in document['tokens']] == ['t','⁵','t',' ɺ̣','+','☃','ts']
assert [record['status'] for record in records] == ['resolved','resolved','resolved','unknown-sound','marker','outside-artifact-domain','resolved']
assert [record['status'] for record in projections] == ['supported','unsupported','supported','not-attempted','not-attempted','not-attempted','unsupported']
assert projections[1]['code'] == 'outside-reviewed-token-context'
assert projections[-1]['code'] == 'unasserted-house-juncture'
"""
    python_path = os.pathsep.join(
        str(root) if entry == "" else entry for entry in sys.path
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(root),
            package_metadata.version("tiergraph"),
        ],
        input=CORE_EXAMPLE.read_text(),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": python_path,
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert result.returncode == 0, result.stderr
