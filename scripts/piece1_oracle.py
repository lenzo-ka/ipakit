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
from ipakit._corpus_query import Match, _unit_paths  # noqa: E402


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


def capture() -> dict[str, Any]:
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
    root = hierarchy.roots[0]
    paths = _unit_paths(hierarchy)
    match = Match(tuple(paths[index] for index in sorted(paths)), "k\u00e6t")

    units = held.units
    projected_intervals = held.intervals
    lean = held.to_json()
    self_contained = held.to_json(self_contained=True)
    hierarchy_dot = hierarchy.to_dot()
    held_dot = held.to_dot()
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
                projected is supplied
                for projected, supplied in zip(units, input_units, strict=True)
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
            "at_object_identity": {
                path: hierarchy.at(path) is hierarchy.at(path)
                for path in (root, "/clock/1/segment/0", "/clock/1")
            },
            "match_paths": list(match.paths),
            "unit_path_crosswalk": [[index, path] for index, path in paths.items()],
            "wire_type_version": [json.loads(lean)["type"], json.loads(lean)["v"]],
        },
    }


CONTRACT_MUTATIONS = (
    "memoized_units",
    "intervals",
    "dataclass_behavior",
    "builder_handles",
    "canonical_pointer",
    "at_object_identity",
    "match_paths",
    "wire_bytes",
    "dot_identity",
)


def mutate_contract(document: dict[str, Any], contract: str) -> None:
    """Apply one synthetic regression at each audited public-contract surface."""
    contracts = document["contracts"]
    if contract == "memoized_units":
        contracts["memoized_units_tuple"] = False
        contracts["memoized_unit_objects"] = False
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
    elif contract == "at_object_identity":
        contracts["at_object_identity"]["/clock/1/segment/0"] = False
    elif contract == "match_paths":
        contracts["match_paths"] = list(reversed(contracts["match_paths"]))
    elif contract == "wire_bytes":
        document["canonical_bytes"]["held_sha256"] = "0" * 64
    elif contract == "dot_identity":
        document["canonical_bytes"]["held_dot"] += "// mutated\n"
    else:
        raise ValueError(f"unknown Piece-1 contract: {contract}")


def encoded(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def check(*, mutation: str | None = None) -> None:
    expected = GOLDEN.read_bytes()
    document = capture()
    if mutation is not None:
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
