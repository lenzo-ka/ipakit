#!/usr/bin/env python
"""Generate ``docs/tutorial.md`` by executing every example in its source.

The tutorial is a **derived artifact**, in the same sense as
``docs/figures/*.svg`` and ``ipakit/data/confusion.json``: the prose is
written by hand, the *results* are not written at all. ``build`` runs
every call in ``docs/tutorial.src.md`` and emits the document with real
output embedded; ``check`` regenerates into memory and compares bytes.

That single check subsumes "every example works and prints what the page
says it prints", because a wrong output is a byte difference. It is the
same guard ``scripts/confusion.py validate`` gives the distance matrix,
and it exists for the reason ``docs/reviewing.md`` gives at length:
documentation drifting away from behavior is this repo's most frequent
recurring failure, and a tutorial is the worst place for it because its
readers are the ones who cannot yet tell when it is wrong.

Two block types in the source are executed.

``console-run``
    Each ``$ ...`` line is run as a command; stdout, then stderr, is
    inserted beneath it. Emitted as a ``console`` block, which is the
    shape ``tests/test_cli.py`` already replays for ``docs/rules.md``.

``python-run``
    Parsed into top-level statements. An expression is evaluated and its
    ``repr`` quoted beside or beneath it; anything else (an import, an
    assignment, a ``def``) is executed silently so later lines can use
    it. A trailing ``#`` comment in the source is authorial and is kept,
    with the value placed after it.

Everything else passes through unchanged, so the prose is untouched.

**Determinism.** A byte-identical check demands it. ``PYTHONHASHSEED`` is
pinned for the subprocesses, the CLI is invoked as ``python -m
ipakit.cli`` from the repository root so no install is required, and the
repository root is the only path that could appear in output -- it is
replaced by ``ipakit`` if it ever shows up, and that is the *only*
normalization applied. Nothing else is rewritten: a generator that
quietly tidies output would hide the difference it exists to reveal.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import difflib
import io
import os
import re
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "tutorial.src.md"
TARGET = ROOT / "docs" / "tutorial.md"

# Import the checkout, not whatever happens to be installed: the page must
# describe the tree it is generated from.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FENCE = re.compile(r"^```(console-run|python-run)[ \t]*$")
#: Width at which a quoted value moves from beside a call to beneath it.
WIDTH = 78

BANNER = (
    "<!-- Generated from tutorial.src.md by scripts/tutorial.py. "
    "Do not edit: run `make tutorial`. -->"
)


# --------------------------------------------------------------------------
# console blocks
# --------------------------------------------------------------------------


def run_command(command: str) -> tuple[str, str]:
    """Run one shell command from the repository root."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONWARNINGS"] = "default"
    env["COLUMNS"] = "80"
    # The documented spelling is the installed console script. Running the
    # module is the same entry point (pyproject: ipakit = "ipakit.cli:main")
    # and needs no install, so the page can be regenerated from a checkout.
    spelled = command.strip()
    if spelled.startswith("ipakit "):
        argv = [sys.executable, "-m", "ipakit.cli"] + _split(spelled[len("ipakit ") :])
    else:
        raise SystemExit(f"tutorial: only 'ipakit ...' commands may be run: {command}")
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env=env)
    return _clean(proc.stdout), _clean(proc.stderr)


def _split(text: str) -> list[str]:
    import shlex

    return shlex.split(text)


def _clean(text: str) -> str:
    """Strip trailing blanks and hide the only path that can vary."""
    text = text.replace(str(ROOT), "ipakit")
    return "\n".join(line.rstrip() for line in text.rstrip("\n").split("\n"))


def render_console(lines: list[str]) -> list[str]:
    out = ["```console"]
    for line in lines:
        if not line.strip():
            continue
        if not line.startswith("$ "):
            raise SystemExit(f"tutorial: console-run line must start with '$ ': {line}")
        out.append(line)
        stdout, stderr = run_command(line[2:])
        for stream in (stdout, stderr):
            if stream:
                out.extend(stream.split("\n"))
    out.append("```")
    return out


# --------------------------------------------------------------------------
# python blocks
# --------------------------------------------------------------------------


def render_python(block: str, env: dict) -> list[str]:
    tree = ast.parse(block)
    lines = block.split("\n")
    out = ["```python"]
    for index, stmt in enumerate(tree.body):
        start, end = stmt.lineno - 1, stmt.end_lineno
        source = "\n".join(lines[start:end])
        # blank lines the author put between statements are kept
        if index and lines[start - 1].strip() == "":
            out.append("")
        body, comment = split_comment(source)
        if isinstance(stmt, ast.Expr):
            value = evaluate(stmt, env)
            out.extend(quote(body.rstrip(), comment, value))
        else:
            execute(stmt, env)
            out.append(source)
    out.append("```")
    return out


def evaluate(stmt: ast.Expr, env: dict):
    node = ast.Expression(stmt.value)
    ast.fix_missing_locations(node)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.redirect_stdout(io.StringIO()):
            return eval(compile(node, "<tutorial>", "eval"), env)


def execute(stmt: ast.stmt, env: dict) -> None:
    node = ast.Module([stmt], [])
    ast.fix_missing_locations(node)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(node, "<tutorial>", "exec"), env)


def quote(body: str, comment: str, value) -> list[str]:
    """Put the value beside the call, or beneath it when it will not fit.

    The value comes first and the author's note after it, matching the
    ``# 'kaː'   lengthen`` shape the hand-written docs already use.
    """
    if value is None:
        return [body] if not comment else [f"{body}  # {comment}"]
    shown = repr(value)
    note = f"   {comment}" if comment else ""
    beside = f"{body}  # {shown}{note}"
    if len(beside) <= WIDTH and "\n" not in shown:
        return [beside]
    head = [body] if not comment else [f"{body}  # {comment}"]
    indent = " " * (len(body) - len(body.lstrip()))
    wrapped = textwrap.wrap(
        shown,
        width=WIDTH - len(indent) - 2,
        initial_indent="",
        subsequent_indent="",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return head + [f"{indent}# {piece}" for piece in wrapped]


def split_comment(source: str) -> tuple[str, str]:
    """Separate an authorial trailing comment from the code."""
    last = source.split("\n")[-1]
    body, marker, comment = partition_comment(last)
    if not marker:
        return source, ""
    prefix = source.split("\n")[:-1]
    return "\n".join(prefix + [body.rstrip()]), comment.strip()


def partition_comment(line: str) -> tuple[str, str, str]:
    out: list[str] = []
    in_str = None
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


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def strip_front_matter(source: str) -> str:
    """Drop the source-only notes at the top of the source file.

    A source that opens with an HTML comment is explaining *itself* -- how
    to edit it, which fences run -- which is guidance for whoever edits the
    source and noise for whoever reads the page. Everything through the
    first ``-->`` is dropped.
    """
    if not source.lstrip().startswith("<!--"):
        return source
    end = source.index("-->") + len("-->")
    return source[end:].lstrip("\n")


def generate() -> str:
    source = strip_front_matter(SOURCE.read_text(encoding="utf-8"))
    lines = source.split("\n")
    env: dict = {}
    out: list[str] = []
    index = 0
    inserted_banner = False
    while index < len(lines):
        line = lines[index]
        match = FENCE.match(line)
        if not match:
            out.append(line)
            index += 1
            if not inserted_banner and line.startswith("# "):
                out.append("")
                out.append(BANNER)
                inserted_banner = True
            continue
        kind = match.group(1)
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].rstrip() != "```":
            body.append(lines[index])
            index += 1
        index += 1  # closing fence
        if kind == "console-run":
            out.extend(render_console(body))
        else:
            out.extend(render_python("\n".join(body), env))
    text = "\n".join(out)
    return text.rstrip("\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["build", "check"])
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"tutorial: no source at {SOURCE}", file=sys.stderr)
        return 1

    fresh = generate()
    if args.action == "build":
        TARGET.write_text(fresh, encoding="utf-8")
        print(f"tutorial: wrote {TARGET.relative_to(ROOT)}")
        return 0

    if not TARGET.exists():
        print(
            "tutorial: docs/tutorial.md is missing; run `make tutorial`",
            file=sys.stderr,
        )
        return 1
    current = TARGET.read_text(encoding="utf-8")
    if current == fresh:
        print("tutorial: docs/tutorial.md is current")
        return 0
    diff = difflib.unified_diff(
        current.split("\n"),
        fresh.split("\n"),
        fromfile="docs/tutorial.md (checked in)",
        tofile="docs/tutorial.md (regenerated)",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    print(
        "\ntutorial: the regenerated tutorial differs from the one checked in.\n"
        "Either the library changed what it prints, or docs/tutorial.src.md is\n"
        "stale. Read the diff and decide which -- a changed value here is a\n"
        "behavior change, not a formatting nit -- then run `make tutorial`.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
