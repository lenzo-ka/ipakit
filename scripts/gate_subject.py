#!/usr/bin/env python3
"""Assert and print the source trees imported by the release gate.

ipakit must be imported from this working tree; tiergraph is a published
dependency, so its installed path and version are reported for the record.
"""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata
from pathlib import Path
from types import ModuleType

import ipakit

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
    try:
        tiergraph_version = metadata.version("tiergraph")
    except metadata.PackageNotFoundError:
        tiergraph_version = "unknown"

    ipakit_commit = git(ROOT, "rev-parse", "HEAD")
    ipakit_dirty = bool(git(ROOT, "status", "--porcelain", "--untracked-files=normal"))
    print(
        "gate subject [executed]: "
        f"ipakit_path={ipakit_path}; ipakit_commit={ipakit_commit}; "
        f"ipakit_dirty={'yes' if ipakit_dirty else 'no'}; "
        f"tiergraph_path={tiergraph_path}; tiergraph_version={tiergraph_version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
