#!/usr/bin/env python
"""Check the values quoted in the hand-written documents.

``docs/tutorial.md`` is generated, so its examples cannot drift --
``scripts/tutorial.py check`` regenerates it and compares bytes. The other
documents are written by hand with executed examples pasted in, and
nothing was keeping them true: ``pytest --doctest-modules`` covers
docstrings inside the package, and ``tests/test_cli.py`` replays the
``console`` blocks in ``docs/rules.md``, but a ``python`` block in
``README.md`` or ``docs/form.md`` was checked by whoever last edited it
and never again.

``docs/reviewing.md`` names documentation drifting away from behavior as
a first-class recurring failure here, so this closes that hole from the
same direction: every expression in a ``python`` fence is evaluated, and
where the document quotes a value beside or beneath it, the two must
agree.

What counts as a quoted value is deliberately conservative -- a comment
that does not parse as a Python literal is prose, and prose is not
checked. The count of what *was* checked is printed and asserted against
a floor, so this cannot go quietly vacuous the way ``docs/reviewing.md``
warns about.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FENCE = re.compile(r"```(python|console)([^\n]*)\n(.*?)```", re.S)

#: A ``python`` fence tagged ```` ```python no-run ```` is an illustrative
#: fragment -- a function-body excerpt, a snippet that names context the
#: document did not define, or a recipe with a side effect -- not a
#: self-contained example with a value to check. It still highlights as
#: Python (renderers key on the first word), but this reader skips it and
#: says how many it skipped, so the exemption cannot go quietly.
NO_RUN = "no-run"
EXC = re.compile(
    r"^([A-Za-z_][A-Za-z_0-9]*(?:Error|Warning|Exception))\b:?\s*(.*)$", re.S
)

#: Generated, and guarded by ``scripts/tutorial.py check`` instead.
GENERATED = {"tutorial.md", "tutorial.src.md"}

#: A floor, not a total. The totals move whenever a document gains an
#: example; a floor only fails when a *sweep* has collapsed, which is the
#: failure mode ``docs/reviewing.md`` says to guard against.
FLOOR = 90


def literal(text: str) -> tuple[object, bool]:
    """The value a comment quotes, ignoring any prose after it."""
    text = text.strip()
    if not text:
        return None, False
    try:
        return ast.literal_eval(text), True
    except Exception:
        pass
    # A quoted value may be followed by a note: "'kaː'   lengthen". Take the
    # longest prefix that parses, but do not let a trailing comma turn the
    # value into a tuple it was never written as.
    for end in range(len(text) - 1, 0, -1):
        chunk = text[:end].rstrip().rstrip(",").rstrip()
        if not chunk:
            continue
        try:
            value = ast.literal_eval(chunk)
        except Exception:
            continue
        if isinstance(value, tuple) and not chunk.startswith("("):
            continue
        return value, True
    return None, False


def partition_comment(line: str) -> tuple[str, str, str]:
    out: list[str] = []
    in_str: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if in_str:
            if char == "\\":
                out.append(char)
                index += 1
                if index < len(line):
                    out.append(line[index])
                index += 1
                continue
            if char == in_str:
                in_str = None
        elif char in "'\"":
            in_str = char
        elif char == "#":
            return "".join(out), "#", line[index + 1 :]
        out.append(char)
        index += 1
    return "".join(out), "", ""


def quoted(lines: list[str], stmt: ast.stmt) -> str:
    """The comment beside a statement, or on the line under it."""
    _, marker, comment = partition_comment(lines[stmt.end_lineno - 1])
    if marker and comment.strip():
        return comment.strip()
    index = stmt.end_lineno
    if index < len(lines) and lines[index].strip().startswith("#"):
        return lines[index].strip().lstrip("#").strip()
    return ""


def wildcard_match(want: str, got: str) -> bool:
    """``...`` in a quoted message elides whatever the document skipped."""
    want = want.strip().rstrip(".")
    if "..." not in want:
        return got.startswith(want) or want in got
    pattern = ".*".join(re.escape(piece) for piece in want.split("..."))
    return re.search(pattern, got, re.S) is not None


def check_block(block: str, env: dict, report: list) -> tuple[int, int]:
    checked = failed = 0
    lines = block.split("\n")
    try:
        tree = ast.parse(block)
    except SyntaxError:
        # An illustrative fragment, not a runnable example.
        return 0, 0
    for stmt in tree.body:
        if isinstance(stmt, ast.Assert):
            # A document quoting an assertion is quoting test source, not
            # offering an example -- docs/reviewing.md shows the shape a
            # sweep's floor should take. There is nothing here to run.
            continue
        source = ast.get_source_segment(block, stmt) or ""
        want = quoted(lines, stmt)
        expecting = EXC.match(want) if want else None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with contextlib.redirect_stdout(io.StringIO()):
                    if isinstance(stmt, ast.Expr):
                        node = ast.Expression(stmt.value)
                        ast.fix_missing_locations(node)
                        value = eval(compile(node, "<doc>", "eval"), env)
                    else:
                        module = ast.Module([stmt], [])
                        ast.fix_missing_locations(module)
                        exec(compile(module, "<doc>", "exec"), env)
                        continue
        except Exception as error:
            if expecting and type(error).__name__ == expecting.group(1):
                checked += 1
                if not wildcard_match(expecting.group(2), str(error)):
                    failed += 1
                    report.append((source, want, f"{type(error).__name__}: {error}"))
                continue
            # An example that needs context the document did not give is a
            # documentation problem too, but not one this script can judge;
            # it is reported and left to a reader.
            checked += 1
            failed += 1
            report.append(
                (
                    source,
                    want or "(no value quoted)",
                    f"raised {type(error).__name__}: {error}",
                )
            )
            continue
        if expecting:
            checked += 1
            failed += 1
            report.append((source, want, f"did not raise; returned {value!r}"))
            continue
        if not want:
            continue
        wanted, ok = literal(want)
        if not ok:
            continue
        checked += 1
        if wanted != value and repr(value) != want.strip():
            failed += 1
            report.append((source, want, repr(value)))
    return checked, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--floor", type=int, default=FLOOR)
    args = parser.parse_args()

    paths = [ROOT / "README.md"] + sorted(
        path for path in (ROOT / "docs").rglob("*.md") if path.name not in GENERATED
    )
    total = failures = skipped_total = 0
    for path in paths:
        env: dict = {}
        report: list = []
        checked = failed = skipped = 0
        for language, info, block in FENCE.findall(path.read_text(encoding="utf-8")):
            if language != "python":
                continue
            if NO_RUN in info:
                skipped += 1
                continue
            one, two = check_block(block, env, report)
            checked, failed = checked + one, failed + two
        total += checked
        failures += failed
        skipped_total += skipped
        if checked or failed or skipped:
            mark = "ok  " if not failed else "FAIL"
            name = path.relative_to(ROOT)
            note = f", {skipped} illustrative skipped" if skipped else ""
            print(f"  [{mark}] {name}: {checked} values checked, {failed} wrong{note}")
        for source, want, got in report:
            print(f"         {' '.join(source.split())[:88]}")
            print(f"           document says: {want}")
            print(f"           library gives: {got}")

    tail = f" ({skipped_total} illustrative fences skipped)" if skipped_total else ""
    print(f"\n{total} quoted values checked in the hand-written documents{tail}")
    if total < args.floor:
        print(
            f"only {total} values checked, below the floor of {args.floor}: the "
            "documents or this reader moved and the sweep stopped covering them",
            file=sys.stderr,
        )
        return 1
    if failures:
        print(
            f"\n{failures} quoted value(s) disagree with the library. Either the "
            "behavior changed and the document needs updating, or the document "
            "was wrong when it was written.",
            file=sys.stderr,
        )
        return 1
    print("every quoted value agrees with the library")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
