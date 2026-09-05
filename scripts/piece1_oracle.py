#!/usr/bin/env python3
"""Piece-1 byte golden and public-identity differential oracle."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests/tiergraph/baselines/piece1-canonical-store.json"
sys.path.insert(0, str(ROOT))

import ipakit  # noqa: E402
from ipakit import Form, FormBuilder, Interval, Timing  # noqa: E402
from ipakit._containment_projection import ContainmentProjectionInput  # noqa: E402
from ipakit._corpus_query import Match, _unit_paths  # noqa: E402
from ipakit._fact_builder import FactBuilder  # noqa: E402
from ipakit._graph_facts import (  # noqa: E402
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)


class OracleMismatch(AssertionError):
    """The current public surface differs from the captured Piece-1 oracle."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hierarchy() -> tuple[Form, dict[str, bool]]:
    builder = FormBuilder()
    utterance = builder.begin("utterance")
    segments = builder.append_ipa("k\u00e6t")
    builder.end(utterance)
    builder.contain(utterance, segments)
    builder.add_root(utterance)
    handle_contract = {
        "utterance_is_opaque": not isinstance(utterance, (str, int)),
        "distinct_handles": len({id(utterance), *(id(item) for item in segments)}) == 4,
        "current_tick": builder.current_tick == 3,
    }
    return builder.build(), handle_contract


def _refusal(action: Any) -> dict[str, str]:
    """Capture the byte-bearing public diagnostic, including its exception type."""
    # `PathRefusal` subclasses neither `tiergraph.Refusal` nor `ValueError`
    # -- its MRO is (PathRefusal, Exception), and it has been that at v0.1.0
    # and at HEAD alike, so this is not a regression. What changed is which
    # exception these fixtures REACH: a path refusal now arrives where a
    # ValueError used to, so a handler that named only the base types stopped
    # recording and started crashing. Path addressing carries its own
    # `PathRefusalCode`, separate from `RefusalStage`, so it is enumerated
    # rather than assumed to arrive under the document-reader base. If it
    # later joins `Refusal`, this tuple still catches it.
    # Imported here rather than at module scope, as the rest of this file does.
    from tiergraph.path import PathRefusal

    try:
        action()
    except (TypeError, ValueError, PathRefusal) as error:
        message = str(error)
        return {
            "type": type(error).__name__,
            "message": message,
            "utf8_hex": message.encode("utf-8").hex(),
        }
    raise AssertionError("Piece-1 refusal fixture unexpectedly succeeded")


def _containment_refusal(*, boundary: bool) -> None:
    declarations = Declarations(
        (TierDeclaration("item", frozenset({"label"})),),
        (FeatureDeclaration("label"),),
        (
            RelationDeclaration(
                "contains",
                containment=True,
                acyclic=True,
                source_arity=(1, 1) if boundary else (2, 2),
                target_kinds=(
                    frozenset({EndpointKind.EVENT, EndpointKind.COARSE_TICK})
                    if boundary
                    else frozenset({EndpointKind.EVENT})
                ),
            ),
        ),
    )
    builder = FactBuilder(declarations)
    first = builder.append_input_atom("item", {"label": "first"})
    second = builder.append_input_atom("item", {"label": "second"})
    third = builder.append_input_atom("item", {"label": "third"})
    if not boundary:
        builder.relate((first, second), "contains", (third,))
        form = Form._from_projection_input(builder.build_input())
    else:
        base = builder.build_input()
        form = Form._from_projection_input(
            ContainmentProjectionInput.from_facts(
                base.declarations,
                base.clock,
                (Relation(("/clock/0/item/0",), "contains", ("/clock/1",)),),
            )
        )
    form.direct_children("/clock/0/item/0")


def _refusal_bytes(inventory: Any, hierarchy: Form, input_units: Any) -> dict[str, Any]:
    refined = Form.parse("#a", inventory)
    return {
        "containment_multi_source": _refusal(
            lambda: _containment_refusal(boundary=False)
        ),
        "containment_boundary_endpoint": _refusal(
            lambda: _containment_refusal(boundary=True)
        ),
        "malformed_pointer": _refusal(lambda: hierarchy.at("/clock//segment/0")),
        "dangling_resolution": _refusal(lambda: hierarchy.at("/clock/999/segment/0")),
        "invalid_refined_gap": _refusal(lambda: refined.at("/clock/0/gaps/9")),
        "invalid_interval": _refusal(lambda: Interval("syllable", -1, 0, inventory)),
        "interval_past_form": _refusal(
            lambda: Form.of(input_units, (Interval("syllable", 0, 99, inventory),))
        ),
    }


def _resolved_kind(value: Any) -> str:
    """Return the stable public graph kind used by the resolution contract."""
    return type(value).__name__


def capture(*, at_mutation: str | None = None) -> dict[str, Any]:
    inventory = ipakit.load_ipa_features()
    parsed = Form.parse("#a..b#", inventory)
    input_units = parsed.units
    intervals = (
        Interval("syllable", 0, 3, inventory, Timing(0.0, 0.3)),
        Interval("mora", 1, 4, inventory),
        Interval("syllable", 0, 3, inventory, Timing(0.4, 0.2)),
    )
    held = Form.of(input_units, intervals)
    peer = Form.of(input_units, intervals)
    replacement = dataclasses.replace(held, intervals=())
    hierarchy, handles = _hierarchy()
    refined = Form.parse("#a", inventory)
    root = hierarchy.roots[0]
    child = "/clock/1/segment/0"
    paths = _unit_paths(hierarchy)
    match = Match(tuple(paths[index] for index in sorted(paths)), "k\u00e6t")

    units = held.units
    projected_intervals = held.intervals
    lean = held.to_json()
    self_contained = held.to_json(self_contained=True)
    hierarchy_dot = hierarchy.to_dot()
    held_dot = held.to_dot()
    at_cases = (
        ("utterance_event", hierarchy, "/clock/0/utterance/0"),
        ("segment_event_1", hierarchy, "/clock/1/segment/0"),
        ("segment_event_2", hierarchy, "/clock/2/segment/0"),
        ("coarse_tick_0", hierarchy, "/clock/0"),
        ("coarse_tick_1", hierarchy, "/clock/1"),
        ("refined_coarse_tick_0", refined, "/clock/0"),
        ("refined_gap_0", refined, "/clock/0/gaps/0"),
    )
    resolved = [form.at(path) for _, form, path in at_cases]
    if at_mutation == "fugu_all_paths_one_object":
        fixed_by_form = {id(form): form.at("/clock/0") for _, form, _ in at_cases}
        resolved = [fixed_by_form[id(form)] for _, form, _ in at_cases]
    elif at_mutation == "wrong_type_per_path":
        resolved = [
            form.at(f"/clock/{path.split('/')[2]}") for _, form, path in at_cases
        ]
    elif at_mutation is not None:
        raise ValueError(f"unknown Form.at behavior mutation: {at_mutation}")
    return {
        "format": "ipakit-piece1-oracle-v1",
        "forms": {
            "parsed": parsed.to_json(),
            "held": lean,
            "held_self_contained": self_contained,
            "hierarchy": hierarchy.to_json(),
        },
        "canonical_bytes": {
            "held_sha256": _sha256(lean),
            "held_self_contained_sha256": _sha256(self_contained),
            "hierarchy_dot": hierarchy_dot,
            "hierarchy_dot_sha256": _sha256(hierarchy_dot),
            "held_dot": held_dot,
            "held_dot_sha256": _sha256(held_dot),
        },
        "contracts": {
            "memoized_units_tuple": held.units is units,
            "memoized_unit_objects": all(
                unit is iterated
                for unit, iterated in zip(held.units, tuple(held), strict=True)
            ),
            "reconstructed_unit_values": all(
                unit == supplied and repr(unit) == repr(supplied)
                for unit, supplied in zip(held.units, input_units, strict=True)
            ),
            "memoized_intervals_tuple": held.intervals is projected_intervals,
            "intervals": [
                [item.tier, item.start, item.end] for item in projected_intervals
            ],
            "dataclass_fields": [field.name for field in dataclasses.fields(Form)],
            "replace_intervals": len(replacement.intervals),
            "equality": held == peer,
            "hash": hash(held) == hash(peer),
            "distinct_equality": held != replacement,
            "distinct_hash": hash(held) != hash(replacement),
            "builder_handles": handles,
            "roots": list(hierarchy.roots),
            "root_spelling": root,
            "children": list(hierarchy.direct_children(root)),
            "navigation": {
                "descendants": list(hierarchy.descendants(root)),
                "leaves": list(hierarchy.leaves(root)),
                "parents": list(hierarchy.parents(child)),
                "ancestors": list(hierarchy.ancestors(child)),
            },
            "at_mapping": [
                {"label": label, "path": path, "kind": _resolved_kind(value)}
                for (label, _, path), value in zip(at_cases, resolved, strict=True)
            ],
            "at_identity_matrix": [
                [left is right for right in resolved] for left in resolved
            ],
            "at_repeat_identity": [
                value is form.at(path)
                for (_, form, path), value in zip(at_cases, resolved, strict=True)
            ],
            "match_paths": list(match.paths),
            "unit_path_crosswalk": [[index, path] for index, path in paths.items()],
            "wire_type_version": [json.loads(lean)["type"], json.loads(lean)["v"]],
            "refusal_bytes": _refusal_bytes(inventory, hierarchy, input_units),
        },
    }


REFUSAL_NAMES = (
    "containment_multi_source",
    "containment_boundary_endpoint",
    "malformed_pointer",
    "dangling_resolution",
    "invalid_refined_gap",
    "invalid_interval",
    "interval_past_form",
)

AT_BEHAVIOR_MUTATIONS = ("fugu_all_paths_one_object", "wrong_type_per_path")

CONTRACT_MUTATIONS = (
    "memoized_units",
    "reconstructed_unit_values",
    "intervals",
    "dataclass_behavior",
    "builder_handles",
    "canonical_pointer",
    "navigation",
    "match_paths",
    "wire_bytes",
    "dot_identity",
    *(f"refusal_bytes:{name}" for name in REFUSAL_NAMES),
    *AT_BEHAVIOR_MUTATIONS,
)


def mutate_contract(document: dict[str, Any], contract: str) -> None:
    """Apply one synthetic regression at each audited public-contract surface."""
    contracts = document["contracts"]
    if contract == "memoized_units":
        contracts["memoized_units_tuple"] = False
        contracts["memoized_unit_objects"] = False
    elif contract == "reconstructed_unit_values":
        contracts["reconstructed_unit_values"] = False
    elif contract == "intervals":
        contracts["memoized_intervals_tuple"] = False
        contracts["intervals"][0][1] += 1
        contracts["intervals"][0], contracts["intervals"][1] = (
            contracts["intervals"][1],
            contracts["intervals"][0],
        )
    elif contract == "dataclass_behavior":
        contracts["dataclass_fields"] = contracts["dataclass_fields"][:-1]
        contracts["replace_intervals"] = 1
        contracts["equality"] = False
        contracts["hash"] = False
        contracts["distinct_equality"] = False
        contracts["distinct_hash"] = False
    elif contract == "builder_handles":
        contracts["builder_handles"]["utterance_is_opaque"] = False
        contracts["builder_handles"]["distinct_handles"] = False
    elif contract == "canonical_pointer":
        contracts["root_spelling"] = "/clock/0/utterance/1"
    elif contract == "navigation":
        for values in contracts["navigation"].values():
            values.clear()
    elif contract == "match_paths":
        contracts["match_paths"] = list(reversed(contracts["match_paths"]))
    elif contract == "wire_bytes":
        document["canonical_bytes"]["held_sha256"] = "0" * 64
    elif contract == "dot_identity":
        document["canonical_bytes"]["held_dot"] += "// mutated\n"
    elif contract.startswith("refusal_bytes:"):
        refusal = contracts["refusal_bytes"][contract.partition(":")[2]]
        refusal["message"] += " (mutated)"
        refusal["utf8_hex"] = refusal["message"].encode("utf-8").hex()
    else:
        raise ValueError(f"unknown Piece-1 contract: {contract}")


def encoded(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def check(*, mutation: str | None = None) -> None:
    expected = GOLDEN.read_bytes()
    at_mutation = mutation if mutation in AT_BEHAVIOR_MUTATIONS else None
    document = capture(at_mutation=at_mutation)
    if mutation is not None and at_mutation is None:
        document = copy.deepcopy(document)
        mutate_contract(document, mutation)
    actual = encoded(document)
    if actual != expected:
        raise OracleMismatch(
            "Piece-1 oracle differs from its pre-change golden "
            f"(expected {hashlib.sha256(expected).hexdigest()}, "
            f"actual {hashlib.sha256(actual).hexdigest()})"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "check", "prove"))
    args = parser.parse_args()
    if args.mode == "capture":
        GOLDEN.write_bytes(encoded(capture()))
        print(f"captured {GOLDEN.relative_to(ROOT)}")
    elif args.mode == "check":
        check()
        print("piece1 oracle [PASS]")
    else:
        check()
        for contract in CONTRACT_MUTATIONS:
            try:
                check(mutation=contract)
            except OracleMismatch:
                print(f"piece1 oracle {contract} mutation [EXPECTED FAIL]")
            else:
                raise AssertionError(
                    f"Piece-1 oracle did not detect its {contract} mutation"
                )


if __name__ == "__main__":
    main()
