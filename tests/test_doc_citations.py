"""Every test a document cites must exist.

Four modules named by `docs/tiergraph-acceptance.md` were retired in one
commit and the table went on citing them: eighteen of its forty-four
citations resolved to nothing, and five criteria had no surviving witness
at all. Nothing noticed, because nothing reads that file.

This gates EXISTENCE and deliberately not COVERAGE. Whether a named test
actually exercises the criterion beside it cannot be settled by reading,
and a check that pretended to would certify the shape of a citation
rather than the property it claims -- which is worse than no check,
because it reads as rigor. The table's own preamble carries the coverage
half as a stated silence; this closes the half that is mechanical.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CITATION = re.compile(r"(tests/[\w/]+\.py)(?:::(\w+))?")

# Documents whose test citations are gated. A document is added here when
# it starts naming tests as evidence, which is the moment its citations
# become load-bearing.
GATED = ("docs/tiergraph-acceptance.md",)


def _citations(document: Path) -> list[tuple[str, str | None, str]]:
    text = document.read_text(encoding="utf-8")
    out: list[tuple[str, str | None, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for path, name in CITATION.findall(line):
            out.append((path, name or None, f"{document.name}:{line_no}"))
    return out


def _defines(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }


@pytest.mark.parametrize("document", GATED)
def test_every_cited_test_file_exists(document: str) -> None:
    missing = [
        f"{where} -> {path}"
        for path, _, where in _citations(ROOT / document)
        if not (ROOT / path).is_file()
    ]
    assert not missing, missing


@pytest.mark.parametrize("document", GATED)
def test_every_cited_test_name_is_defined(document: str) -> None:
    missing = []
    for path, name, where in _citations(ROOT / document):
        target = ROOT / path
        if name is None or not target.is_file():
            continue
        if name not in _defines(target):
            missing.append(f"{where} -> {path}::{name}")
    assert not missing, missing


@pytest.mark.parametrize("document", GATED)
def test_the_sweep_is_not_vacuous(document: str) -> None:
    """A gate that finds nothing to check reports success either way."""
    found = _citations(ROOT / document)
    assert len(found) > 20, len(found)
    assert sum(1 for _, name, _ in found if name is not None) > 15
