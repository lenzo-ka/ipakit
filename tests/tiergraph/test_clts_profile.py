"""Synthetic source facts exercise native structure, not CLTS resolution."""

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from ipakit._clts_input import FORMAT, HOST, InputError
from ipakit._clts_profile import (
    SourceProfileSpec,
    construct,
    declarations,
    graph_profile,
    metadata,
    name,
    restore,
)
from ipakit._containment_projection import ContainmentProjection
from ipakit._fact_builder import FactBuilder
from ipakit._graph_facts import (
    Declarations,
    FeatureDeclaration,
    GraphValidationError,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._provenance import SourceMetadata

import tiergraph as tg

NS = "urn:fixture:source"


def spec(**changes):
    return replace(
        SourceProfileSpec(
            SourceMetadata(
                "fixture", "urn:fixture", "synthetic", "1", "fixture", "test"
            ),
            "fixture-provider",
            "fixture-manifest",
            ("tone", "consonant"),
            (
                FeatureDeclaration("claims", (NS, "claims")),
                FeatureDeclaration("unused", (NS, "unused")),
            ),
        ),
        **changes,
    )


def resolution(kind="consonant", values=None):
    return {
        "provider": "fixture-provider",
        "status": "resolved",
        "sounds": [{"kind": kind, "canonical": "synthetic", "values": values or {}}],
    }


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
    graph = construct(doc, records, schema)
    restored = tg.loads(tg.dumps(graph))
    assert restore(restored, schema) == (doc, tuple(records))
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
        d.name for d in graph.relation_declarations
    }


def test_empty_schema_profile_and_presence():
    schema = spec()
    graph = construct([], [], schema)
    assert restore(tg.loads(tg.dumps(graph)), schema)[0] == {
        "format": FORMAT,
        "version": 1,
        "tokens": [],
    }
    assert tg.QualifiedName(NS, "unused") in {
        d.name for d in graph.relation_declarations
    }
    explicit = {"format": FORMAT, "version": 1, "tokens": [], "relations": []}
    assert restore(construct(explicit, [], schema), schema)[0] == explicit
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


@pytest.mark.parametrize(
    "change",
    [
        {"provider_fingerprint": "different"},
        {"manifest_fingerprint": "different"},
        {"domains": {"unused": (True,)}},
        {"fields": (FeatureDeclaration("different", (NS, "different")),)},
        {"kinds": ("tone",)},
    ],
)
def test_bound_profile_refuses_changed_declarations(change):
    graph = construct([], [], spec())
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        restore(graph, spec(**change))


def test_unused_declaration_and_metadata_tamper_refuse():
    schema = spec()
    graph = construct([], [], schema)
    lost = replace(
        graph,
        relation_declarations=tuple(
            d
            for d in graph.relation_declarations
            if d.name != tg.QualifiedName(NS, "unused")
        ),
    )
    with pytest.raises(ValueError, match="constructor layout"):
        restore(lost, schema)
    # Alter a native JSON scalar without altering the claimed profile digest.
    hits = [
        (tg.ItemRef(t.declaration.name, i), a)
        for t in graph.tiers
        for i, item in enumerate(t.items)
        for a in item.attributes
        if a.lexical == "fixture-provider"
    ]
    assert hits
    ref, attr = hits[0]
    changed = graph.set_attribute(ref, replace(attr, lexical="tampered"))
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
                "status": "unknown",
                "sounds": [],
            }
    doc = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "x"}, {"raw": "y"}],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    with pytest.raises(InputError, match="resolved tone"):
        construct(doc, records, spec())


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
    graph = construct(doc, records, spec())
    assert restore(graph, spec())[0] == doc
    doc["relations"][1]["source"] = "/tokens/1"
    with pytest.raises(ValueError):
        construct(doc, records, spec())


def test_domain_types_and_unknown_claims():
    schema = spec(domains={"claims": (False,)})
    construct(["x"], [resolution(values={"claims": False})], schema)
    with pytest.raises(InputError, match="outside declared"):
        construct(["x"], [resolution(values={"claims": 0})], schema)
    with pytest.raises(InputError, match="undeclared"):
        construct(["x"], [resolution(values={"other": 1})], schema)


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
    graph = construct(["x"], [record], schema)
    value["nested"].append("changed")
    record["sounds"][0]["values"]["claims"]["nested"].append("changed")
    assert metadata(schema) == before
    assert restore(graph, schema)[1][0]["sounds"][0]["values"] == {
        "claims": {"nested": [False, 0, None]}
    }


def test_unrelated_native_content_refused_not_dropped():
    schema = spec()
    graph = construct([], [], schema)
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
    graph = construct([], [], schema)
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
    graph = construct(["x"], [resolution()], schema)
    changed = replace(
        graph,
        polyadic_relations=tuple(
            (
                replace(r, targets=(tg.ItemRef(name("source-token"), 0),))
                if r.declaration == name("raw")
                else r
            )
            for r in graph.polyadic_relations
        ),
    )
    with pytest.raises(ValueError):
        restore(changed, schema)


def test_clock_and_role_mutations_refuse():
    schema = spec()
    graph = construct(["x"], [resolution()], schema)
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
        [{"provider": "other", "status": "unknown", "sounds": []}],
        [{"provider": "fixture-provider", "status": "resolved", "sounds": []}],
    ],
)
def test_resolution_boundary_refuses_without_guessing(records):
    with pytest.raises(InputError):
        construct(["unknown"], records, spec())


def test_fresh_process_restores_without_optional_providers(tmp_path):
    graph = construct(
        ["t͜s", "é", "é"], [resolution(), resolution(), resolution()], spec()
    )
    root = Path(__file__).resolve().parents[2]
    code = """
import builtins, sys
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
from ipakit._clts_profile import SourceProfileSpec, restore
from ipakit._graph_facts import FeatureDeclaration
from ipakit._provenance import SourceMetadata
spec = SourceProfileSpec(SourceMetadata('fixture','urn:fixture','synthetic','1','fixture','test'), 'fixture-provider', 'fixture-manifest', ('tone','consonant'), (FeatureDeclaration('claims',('urn:fixture:source','claims')), FeatureDeclaration('unused',('urn:fixture:source','unused'))))
document, records = restore(tg.loads(sys.stdin.read()), spec)
assert [token['raw'] for token in document['tokens']] == ['t͜s','é','é']
assert len(records) == 3
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        input=tg.dumps(graph),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
