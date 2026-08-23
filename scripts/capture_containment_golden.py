#!/usr/bin/env python3
"""Regenerate legacy-implementation containment answers at the recorded commit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "485f7a7c631001b58acfffc2884011081e0bcd19"
OUTPUT = ROOT / "tests/tiergraph/baselines/containment-navigation.json"

CAPTURE = r"""
import hashlib
import inspect
import json
from dataclasses import fields
from scripts.containment_oracle import _routes, corpus
from ipakit._tiergraph import Graph, RelationDeclaration
from ipakit._tiergraph_builder import GraphBuilder

def adversarial_fixture(kind):
    relation_names = ("b", "a") if kind == "canonical-relation-order" else ("a", "b")
    declarations = __import__("ipakit._tiergraph", fromlist=["Declarations"]).Declarations(
        (__import__("ipakit._tiergraph", fromlist=["TierDeclaration"]).TierDeclaration("item", frozenset({"label"})),),
        (__import__("ipakit._tiergraph", fromlist=["FeatureDeclaration"]).FeatureDeclaration("label"),),
        tuple(RelationDeclaration(
            name, containment=True, acyclic=True,
            target_arity=(0, None) if kind == "empty-target" else (1, None),
            allow_empty_target=kind == "empty-target",
        ) for name in relation_names),
    )
    builder = GraphBuilder(declarations)
    root = builder.append_input_atom("item", {"label": "root"})
    first = builder.append_input_atom("item", {"label": "first"})
    second = builder.append_input_atom("item", {"label": "second"})
    if kind == "canonical-relation-order":
        builder.contain(root, (second,), relation="b")
        builder.contain(root, (first,), relation="a")
    elif kind == "shared-parent-incidence":
        builder.contain(root, (first,), relation="a")
        builder.contain(root, (first,), relation="b")
    else:
        builder.contain(root, (), relation="a")
    return builder.build()

def boundary_fixture():
    module = __import__("ipakit._tiergraph", fromlist=["Declarations"])
    declarations = module.Declarations(
        (module.TierDeclaration("item", frozenset({"label"})),),
        (module.FeatureDeclaration("label"),),
        (RelationDeclaration(
            "boundary-owns", containment=True, acyclic=True,
            target_kinds=frozenset({module.EndpointKind.COARSE_TICK}),
        ),),
    )
    builder = GraphBuilder(declarations)
    builder.append_input_atom("item", {"label": "root"})
    base = builder.build()
    return Graph(
        base.declarations, base.clock,
        (module.Relation(("/clock/0/item/0",), "boundary-owns", ("/clock/1",)),),
    )

def source_hash():
    functions = (RelationDeclaration.__post_init__, Graph._validate_relation,
                 Graph._validate_endpoints, Graph._validate_acyclic,
                 GraphBuilder.contain)
    text = "\n".join(inspect.getsource(function) for function in functions)
    return hashlib.sha256(text.encode()).hexdigest()

def structural_class(graph):
    containment = {d.name for d in graph.declarations.relations if d.containment}
    relations = tuple(r for r in graph.relations if r.name in containment)
    targets = [target for relation in relations for target in relation.targets]
    return {
        "containment_declarations": len(containment),
        "source_arities": sorted({len(r.sources) for r in relations}),
        "target_arities": sorted({len(r.targets) for r in relations}),
        "repeated_target_incidence": any(len(r.targets) != len(set(r.targets)) for r in relations),
        "shared_targets": len(targets) != len(set(targets)),
        "target_tier_cardinalities": sorted({len({graph.resolve(t).tier for t in r.targets}) for r in relations}),
    }

fixtures = {}
rows = list(corpus())
rows.extend((
    ("fixture:canonical-relation-order", adversarial_fixture("canonical-relation-order")),
    ("fixture:shared-parent-incidence", adversarial_fixture("shared-parent-incidence")),
    ("fixture:empty-target", adversarial_fixture("empty-target")),
))
for name, graph in rows:
    tiers = tuple(d.name for d in graph.declarations.tiers)
    answers = {}
    for ref in graph.event_references():
        answers[ref] = {
            "direct": graph.direct_children(ref),
            "descendants": graph.descendants(ref),
            "leaves": graph.leaves(ref),
            "parents": graph.parents(ref),
            "ancestors": graph.ancestors(ref),
            "routes": _routes(graph, ref),
            "direct_by_tier": {tier: graph.direct_children(ref, tier) for tier in tiers},
            "descendants_by_tier": {tier: graph.descendants(ref, tier) for tier in tiers},
        }
    fixtures[name] = {
        "class": structural_class(graph),
        "answers": answers,
    }

artifact = {
    "_generated": "Generated; never hand-edit. Regenerate with PYTHONHASHSEED=0 python scripts/capture_containment_golden.py generate",
    "source_commit": "SOURCE_COMMIT",
    "accepted_domain": "Exactly graphs whose containment instances have one event source and only event targets (including a declared empty target side); across multiple relations, repeated incidence is retained. Navigation is identical to the legacy implementation on every accepted graph.",
    "refusals": {
        "source_cardinality_other_than_one": "Refused by instance index and relation name because joint or empty-source containment navigation is not defined by OrderedContainment.",
        "boundary_endpoint_relation": "Refused by relation name because tiergraph OrderedContainment is item-only; lift when tiergraph supports boundary containment traversal. No mainline ipakit profile or named fixture constructs this shape.",
    },
    "refused_constructions": {
        "boundary-owns": {
            "legacy_direct_children": boundary_fixture().direct_children("/clock/0/item/0"),
            "projection": "refused by relation name",
        },
    },
    "routing": {
        "accepted_event_only_relations": "Delegated to tiergraph OrderedContainment; the consumer composes canonical order and per-relation inverse multiplicity across relations.",
        "boundary_endpoint_relations": "Refused before projection; there is no kernel path until tiergraph supports boundary containment traversal.",
    },
    "population": {
        "kind": "fixture-derived structural classes, derived and checked, with constructor/validator drift guard",
        "boundary": "the named fixtures in this artifact",
        "outside_member_example": "boundary-owns: legacy direct_children(root) returns the coarse-tick boundary; projection refuses boundary-owns by name",
        "surface": {
            "relation_declaration_fields": [field.name for field in fields(RelationDeclaration)],
            "constructor_validator_sha256": source_hash(),
        },
    },
    "fixtures": fixtures,
}
print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
""".replace("SOURCE_COMMIT", SOURCE_COMMIT)


def render() -> str:
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED=0 is required")
    with tempfile.TemporaryDirectory(prefix="ipakit-containment-golden-") as tmp:
        archive = subprocess.run(
            ["git", "-C", str(ROOT), "archive", SOURCE_COMMIT],
            check=True,
            capture_output=True,
        ).stdout
        subprocess.run(["tar", "-x", "-C", tmp], check=True, input=archive)
        environment = dict(os.environ)
        tiergraph_source = Path(__import__("tiergraph").__file__).resolve().parents[1]
        environment["PYTHONPATH"] = os.pathsep.join((tmp, str(tiergraph_source)))
        rendered = subprocess.run(
            [sys.executable, "-c", CAPTURE],
            cwd=tmp,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    # Every embedded fixture remains the captured legacy oracle.  Replace only
    # the migrated native subsystem slices with the current adapter's answers.
    from containment_oracle import _answers, _as_json, _structural_class, corpus

    payload = json.loads(rendered)
    graphs = dict(corpus())
    for name in ("profile:cmu", "profile:mora"):
        graph = graphs[name]
        payload["fixtures"][name] = {
            "class": _as_json(_structural_class(graph)),
            "answers": _as_json(_answers(graph)),
        }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "generate"))
    args = parser.parse_args()
    rendered = render()
    if args.action == "generate":
        OUTPUT.write_text(rendered, encoding="utf-8")
    elif OUTPUT.read_text(encoding="utf-8") != rendered:
        raise SystemExit(
            "containment golden is not reproducible; run "
            "PYTHONHASHSEED=0 python scripts/capture_containment_golden.py generate"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
