#!/usr/bin/env python3
"""Assert and print the source trees imported by the release gate.

``TIERGRAPH_COMMIT`` is deliberately supplied for every invocation.  It is
not stored in this repository: tiergraph is unpublished, and each checkout or
CI job must declare the exact revision it means to measure.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import ipakit

import tiergraph

ROOT = Path(__file__).resolve().parents[1]
FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


def fail(field: str, expected: str, actual: str) -> None:
    raise SystemExit(
        f"gate subject mismatch: {field}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


def git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise SystemExit(f"gate subject: cannot inspect {path}: {detail}")
    return result.stdout.strip()


def source_path(module: ModuleType) -> Path:
    filename = getattr(module, "__file__", None)
    if filename is None:
        raise SystemExit(f"gate subject: {module.__name__} has no filesystem source")
    return Path(filename).resolve()


def main() -> int:
    expected_tiergraph = os.environ.get("TIERGRAPH_COMMIT", "")
    if not FULL_COMMIT.fullmatch(expected_tiergraph):
        fail(
            "tiergraph commit declaration",
            "TIERGRAPH_COMMIT=<40 lowercase hex>",
            expected_tiergraph or "<unset>",
        )

    ipakit_path = source_path(ipakit)
    expected_ipakit = (ROOT / "ipakit").resolve()
    if not ipakit_path.is_relative_to(expected_ipakit):
        fail("ipakit import path", str(expected_ipakit), str(ipakit_path))

    tiergraph_path = source_path(tiergraph)
    tiergraph_root = Path(git(tiergraph_path.parent, "rev-parse", "--show-toplevel"))
    actual_tiergraph = git(tiergraph_root, "rev-parse", "HEAD")
    if actual_tiergraph != expected_tiergraph:
        fail("tiergraph commit", expected_tiergraph, actual_tiergraph)

    tiergraph_dirty = git(
        tiergraph_root, "status", "--porcelain", "--untracked-files=normal"
    )
    if tiergraph_dirty:
        fail("tiergraph working tree", "clean", "dirty")

    ipakit_commit = git(ROOT, "rev-parse", "HEAD")
    ipakit_dirty = bool(git(ROOT, "status", "--porcelain", "--untracked-files=normal"))
    print(
        "gate subject [executed]: "
        f"ipakit_path={ipakit_path}; ipakit_commit={ipakit_commit}; "
        f"ipakit_dirty={'yes' if ipakit_dirty else 'no'}; "
        f"tiergraph_path={tiergraph_path}; tiergraph_commit={actual_tiergraph}; "
        "tiergraph_dirty=no"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
