"""Keep the TierGraph acceptance map attached to executable witnesses."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
ACCEPTANCE = ROOT / "docs" / "tiergraph-acceptance.md"
TEST_REFERENCE = re.compile(
    r"`(?P<path>tests/[A-Za-z0-9_./-]+\.py)"
    r"(?:::(?P<node>[A-Za-z_][A-Za-z0-9_:]*))?`"
)


def _declared_nodes(path: Path) -> set[tuple[str, ...]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[tuple[str, ...]] = set()

    def walk(body: list[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add((*parents, statement.name))
            elif isinstance(statement, ast.ClassDef):
                current = (*parents, statement.name)
                found.add(current)
                walk(statement.body, current)

    walk(tree.body)
    return found


def test_every_acceptance_test_reference_resolves() -> None:
    """A renamed/deleted witness must make its acceptance claim fail here."""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    references = list(TEST_REFERENCE.finditer(text))
    assert references, "the acceptance table cites no executable tests"

    for match in references:
        path = ROOT / match.group("path")
        assert path.is_file(), f"missing acceptance witness: {match.group('path')}"
        node = match.group("node")
        if node is not None:
            parts = tuple(node.split("::"))
            assert parts in _declared_nodes(
                path
            ), f"missing acceptance witness: {match.group('path')}::{node}"


def test_acceptance_table_has_no_explicit_local_witness_gap() -> None:
    """The table's explicit gap marker is a failing state, not passive prose."""
    assert "no local witness" not in ACCEPTANCE.read_text(encoding="utf-8").lower()
