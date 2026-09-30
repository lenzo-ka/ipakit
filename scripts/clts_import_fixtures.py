#!/usr/bin/env python
"""Write every canonical public CLTS result variant."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ipakit._clts_input import FORMAT, HOST
from ipakit.clts import CLTSInputError, emit_tokens, import_document, import_tokens

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "tests" / "fixtures" / "clts_import"


def _line(result: Any) -> bytes:
    return (result.to_json() + "\n").encode("utf-8")


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
        error_result = error
    else:  # pragma: no cover - a changed public refusal must stop regeneration
        raise AssertionError("invalid timing unexpectedly imported")

    complete = import_tokens(["p", "b"])
    tied = import_tokens(["t͜s"], unsupported="preserve")
    unavailable = import_tokens(["☃"], unsupported="preserve")
    values = {
        "complete.json": complete,
        "empty.json": import_tokens([]),
        "refused.json": import_tokens(["p", "a", "+", "tˢ", "p"]),
        "preserved.json": import_document(preserved_document, unsupported="preserve"),
        "error.json": error_result,
        "emit-source.json": emit_tokens(tied, spelling="source"),
        "emit-bipa.json": emit_tokens(complete, spelling="bipa"),
        "emit-bipa-authorized-loss.json": emit_tokens(
            tied, spelling="bipa", allow_loss=True
        ),
        "emit-bipa-refused-loss.json": emit_tokens(tied, spelling="bipa"),
        "emit-bipa-refused-unavailable.json": emit_tokens(
            unavailable, spelling="bipa", allow_loss=True
        ),
    }
    return {name: _line(result) for name, result in values.items()}


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
