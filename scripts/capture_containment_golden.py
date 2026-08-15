#!/usr/bin/env python3
"""Regenerate pre-migration containment answers from the recorded commit."""

from __future__ import annotations

import argparse
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
for name, graph in corpus():
    if name == "fixture:cross-relation-cycle":
        continue
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
    "accepted_domain": "Navigation answers are unchanged on every graph the projection accepts; the projection accepts single-source containment instances and refuses multi-source ones by name.",
    "population": {
        "kind": "fixture-derived structural classes with constructor/validator drift guard",
        "boundary": "the named fixtures in this artifact",
        "outside_member_example": "a boundary-endpoint containment graph",
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
    return rendered


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
