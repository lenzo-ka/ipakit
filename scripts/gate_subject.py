#!/usr/bin/env python3
"""Assert and print the source trees imported by the release gate.

The tiergraph revision comes from the Git dependency in ``pyproject.toml``.
An editable development shadow is checked against it; an installed wheel has
no checkout to re-verify.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import ipakit
from scripts import tiergraph_pin

import tiergraph

ROOT = Path(__file__).resolve().parents[1]


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
    ipakit_path = source_path(ipakit)
    expected_ipakit = (ROOT / "ipakit").resolve()
    if not ipakit_path.is_relative_to(expected_ipakit):
        fail("ipakit import path", str(expected_ipakit), str(ipakit_path))

    tiergraph_path = source_path(tiergraph)
    actual_tiergraph = tiergraph_pin.verify(source=tiergraph_path)
    tiergraph_dirty = False
    if actual_tiergraph is not None:
        tiergraph_root = tiergraph_pin.worktree_for(tiergraph_path)
        assert tiergraph_root is not None
        tiergraph_dirty = bool(
            git(tiergraph_root, "status", "--porcelain", "--untracked-files=normal")
        )
        if tiergraph_dirty:
            fail("tiergraph working tree", "clean", "dirty")

    ipakit_commit = git(ROOT, "rev-parse", "HEAD")
    ipakit_dirty = bool(git(ROOT, "status", "--porcelain", "--untracked-files=normal"))
    print(
        "gate subject [executed]: "
        f"ipakit_path={ipakit_path}; ipakit_commit={ipakit_commit}; "
        f"ipakit_dirty={'yes' if ipakit_dirty else 'no'}; "
        f"tiergraph_path={tiergraph_path}; "
        f"tiergraph_commit={actual_tiergraph or 'wheel (pin verified by installer)'}; "
        f"tiergraph_dirty={'yes' if tiergraph_dirty else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
