#!/usr/bin/env python3
"""Verify an editable tiergraph shadow against ipakit's dependency pin."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import tiergraph

ROOT = Path(__file__).resolve().parents[1]
TIERGRAPH_SPEC = re.compile(r"^tiergraph\s*@\s*git\+[^\s]+@(?P<sha>[0-9a-f]{40})$")


class PinMismatch(AssertionError):
    """The editable tiergraph checkout does not match pyproject.toml."""


def pinned_sha(pyproject: Path = ROOT / "pyproject.toml") -> str:
    """Read the tiergraph Git revision from the project dependency spec."""
    with pyproject.open("rb") as stream:
        dependencies = tomllib.load(stream)["project"]["dependencies"]

    tiergraph_specs = [
        spec for spec in dependencies if spec.partition("@")[0].strip() == "tiergraph"
    ]
    if len(tiergraph_specs) != 1:
        raise PinMismatch(
            "tiergraph pin declaration mismatch: expected exactly one tiergraph "
            f"dependency in {pyproject}, found {tiergraph_specs}"
        )
    match = TIERGRAPH_SPEC.fullmatch(tiergraph_specs[0])
    if match is None:
        raise PinMismatch(
            "tiergraph pin declaration mismatch: expected a git URL ending in a "
            f"full 40-character lowercase commit SHA, found {tiergraph_specs[0]!r}"
        )
    return match.group("sha")


def module_path(module: ModuleType = tiergraph) -> Path:
    filename = getattr(module, "__file__", None)
    if filename is None:
        raise PinMismatch("tiergraph pin: tiergraph has no filesystem source")
    return Path(filename).resolve()


def git_output(path: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def worktree_for(path: Path) -> Path | None:
    root = git_output(path.parent, "rev-parse", "--show-toplevel")
    return Path(root).resolve() if root else None


def is_python_install(source: Path) -> bool:
    """Return whether source is installed below site-packages/dist-packages."""
    return any(part in {"site-packages", "dist-packages"} for part in source.parts)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def head_for(root: Path) -> str:
    head = git_output(root, "rev-parse", "HEAD")
    if head is None or re.fullmatch(r"[0-9a-fA-F]{40}", head) is None:
        raise PinMismatch(f"tiergraph pin: cannot resolve Git HEAD for {root}")
    return head.lower()


def verify(
    *,
    expected: str | None = None,
    source: Path | None = None,
    resolve_worktree: Callable[[Path], Path | None] = worktree_for,
    resolve_head: Callable[[Path], str] = head_for,
) -> str | None:
    """Return the checkout HEAD, or ``None`` for an installed distribution."""
    expected = (expected or pinned_sha()).lower()
    source = (source or module_path()).resolve()
    if is_python_install(source):
        print(
            "tiergraph pin [SKIP]: resolved tiergraph.__file__ is under a Python "
            f"install location ({source}); wheel installs are already resolved "
            f"from the pyproject.toml pin {expected}"
        )
        return None

    worktree = resolve_worktree(source)
    if worktree is None:
        raise PinMismatch(
            "tiergraph appears to be a source/editable install but its git state "
            f"cannot be read to verify the pin: {source}"
        )
    worktree = worktree.resolve()
    if not is_relative_to(source, worktree):
        raise PinMismatch(
            "tiergraph appears to be a source/editable install but its resolved "
            f"Git worktree does not contain tiergraph.__file__: {worktree}; {source}"
        )

    actual = resolve_head(worktree).lower()
    if actual != expected:
        raise PinMismatch(
            "tiergraph pin mismatch:\n"
            f"  expected (pyproject.toml): {expected}\n"
            f"  actual checkout HEAD:     {actual}\n"
            f"  resolved tiergraph.__file__: {source}"
        )
    print(
        "tiergraph pin [PASS]: "
        f"pyproject={expected}; checkout_head={actual}; tiergraph.__file__={source}"
    )
    return actual


def main() -> int:
    try:
        verify()
    except PinMismatch as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
