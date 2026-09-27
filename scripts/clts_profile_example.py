#!/usr/bin/env python3
"""Generate the committed core-BIPA source-profile example."""

from __future__ import annotations

import argparse
from pathlib import Path

from ipakit._clts_input import FORMAT, HOST
from ipakit._clts_profile import (
    construct,
    core_bipa_resolutions,
    core_bipa_spec,
)
from ipakit.clts import read_snapshot

import tiergraph as tg


def example_document() -> dict[str, object]:
    return {
        "format": FORMAT,
        "version": 1,
        "tokens": [
            {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
            {"raw": "⁵"},
            {"raw": "t"},
            {"raw": " ɺ̣"},
            {"raw": "+"},
            {"raw": "☃"},
            {"raw": "ts"},
        ],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }


def generate() -> str:
    snapshot = read_snapshot()
    document = example_document()
    raws = [token["raw"] for token in document["tokens"]]  # type: ignore[index]
    spec = core_bipa_spec(snapshot)
    projections = [
        {
            "mapping": spec.mapping_identity,
            "status": "supported",
            "facts": [{"house-symbol": "t", "house-kind": "segment"}],
        },
        {
            "mapping": spec.mapping_identity,
            "status": "supported",
            "facts": [{"house-symbol": "⁵", "house-kind": "prosody"}],
        },
        {
            "mapping": spec.mapping_identity,
            "status": "supported",
            "facts": [{"house-symbol": "t", "house-kind": "segment"}],
        },
        *(
            {"mapping": spec.mapping_identity, "status": "not-attempted"}
            for _ in range(3)
        ),
        {
            "mapping": spec.mapping_identity,
            "status": "unsupported",
            "code": "unasserted-house-juncture",
        },
    ]
    graph = construct(
        document, core_bipa_resolutions(snapshot, raws), projections, spec
    )
    return tg.dumps(graph)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = generate()
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered)


if __name__ == "__main__":
    main()
