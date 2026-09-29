#!/usr/bin/env python
"""Write the five canonical public CLTS import envelopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ipakit._clts_input import FORMAT, HOST
from ipakit.clts import CLTSInputError, import_document, import_tokens

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "tests" / "fixtures" / "clts_import"


def _canonical(data: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def fixtures() -> dict[str, bytes]:
    preserved_document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [
            {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
            {"raw": "⁵"},
            {"raw": "☃"},
        ],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    invalid_document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "p", "time": {"start": 0.0}}],
    }
    try:
        import_document(invalid_document)
    except CLTSInputError as error:
        error_data = error.to_data()
    else:  # pragma: no cover - a changed public refusal must stop regeneration
        raise AssertionError("invalid timing unexpectedly imported")

    values = {
        "complete.json": import_tokens(["p", "b"]).to_data(),
        "empty.json": import_tokens([]).to_data(),
        "refused.json": import_tokens(["p", "a", "+", "tˢ", "p"]).to_data(),
        "preserved.json": import_document(
            preserved_document, unsupported="preserve"
        ).to_data(),
        "error.json": error_data,
    }
    return {name: _canonical(data) for name, data in values.items()}


def write(output: Path = OUTPUT) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (output / name).write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    write(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
