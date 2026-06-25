#!/usr/bin/env python
"""Generate and validate the global phone confusion matrix (data/confusion.json).

The matrix is the pairwise feature-distance matrix over the full bundled IPA
inventory, derived from ipa.xml + ipakit's distance metric (no external dep).
It is a committed derived cache: regenerate when ipa.xml or the metric changes;
`validate` guards against drift.

    python scripts/confusion.py validate
    python scripts/confusion.py generate [--write] [--space distance|similarity]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.constants import DEFAULT_CONFUSION  # noqa: E402
from ipakit.features import IPAFeatures  # noqa: E402

VERSION = "1.0"


def derive(space: str = "distance") -> dict[str, Any]:
    """Canonical model from ipa.xml + the metric. Deterministic and reproducible."""
    ipa = IPAFeatures()
    phones = list(ipa.phones)
    m = ipa.pairwise_distances(phones)  # symmetric, diagonal 0.0
    n = len(phones)
    triangle = [
        (m[i][j] if space == "distance" else 1.0 - m[i][j])
        for i in range(n)
        for j in range(i + 1, n)
    ]
    return {
        "version": VERSION,
        "reference": "ipa",
        "space": space,
        "phones": phones,
        "triangle": triangle,
    }


def shipped() -> dict[str, Any]:
    result: dict[str, Any] = json.loads(DEFAULT_CONFUSION.read_text(encoding="utf-8"))
    return result


def render(model: dict[str, Any]) -> str:
    # Compact: ~11k floats, machine-generated, never hand-edited.
    return json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n"


def cmd_validate(_: argparse.Namespace) -> int:
    d = derive()
    try:
        s = shipped()
    except FileNotFoundError:
        print(f"MISSING: {DEFAULT_CONFUSION} (run: confusion.py generate --write)")
        return 1
    if d["phones"] != s.get("phones"):
        print("DRIFT: phone inventory/order differs (ipa.xml changed?).")
        return 1
    if d["space"] != s.get("space"):
        print(f"DRIFT: space shipped={s.get('space')!r} derived={d['space']!r}.")
        return 1
    if d["triangle"] != s.get("triangle"):
        diffs = sum(a != b for a, b in zip(d["triangle"], s.get("triangle", [])))
        print(f"DRIFT: {diffs} matrix cells differ; regenerate confusion.json.")
        return 1
    print(f"OK: shipped confusion.json matches derived ({len(d['phones'])} phones).")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    text = render(derive(space=args.space))
    if args.write:
        DEFAULT_CONFUSION.write_text(text, encoding="utf-8")
        print(f"Wrote {DEFAULT_CONFUSION}")
    else:
        sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_val = sub.add_parser("validate", help="check shipped matrix matches derived")
    p_val.set_defaults(func=cmd_validate)
    p_gen = sub.add_parser("generate", help="emit the derived matrix")
    p_gen.add_argument(
        "--write", action="store_true", help="overwrite data/confusion.json"
    )
    p_gen.add_argument(
        "--space", choices=["distance", "similarity"], default="distance"
    )
    p_gen.set_defaults(func=cmd_generate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
