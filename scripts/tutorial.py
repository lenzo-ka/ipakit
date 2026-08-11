#!/usr/bin/env python
"""Render ``docs/tutorial.src.md`` as a page and as a notebook.

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

**The notebook is the same parse with a different emitter.** :func:`parse`
splits the source once; :func:`generate` renders the page and
:func:`notebook` renders ``ipakit/notebooks/ipakit-tutorial.ipynb``, where
prose becomes a markdown cell, ``python-run`` a code cell and
``console-run`` a code cell of ``!``-prefixed shell lines. One authored
source, two renderings -- which is what keeps the notebook from rotting:
its cells are the blocks ``check`` already executes, so an example that
stops working turns the byte-identical page check red before anyone opens
the notebook. Exactly one cell is the generator's own -- :data:`PREAMBLE`,
which is there because IPython shows only a cell's last value -- and it
is the only one; every other cell is a block. The notebook ships
**without outputs**: deterministic enough to compare byte for byte, small
enough to carry no embedded SVG, and blank enough that a student has to
run it to see anything. Writing it executes nothing.

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
import json
import os
import re
import subprocess
import sys
import textwrap
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "tutorial.src.md"
TARGET = ROOT / "docs" / "tutorial.md"
BASICS_SOURCE = ROOT / "docs" / "tutorial-basics.src.md"
BASICS_TARGET = ROOT / "docs" / "tutorial-basics.md"
#: The notebook ships inside the package, not under ``docs/``: it is the
#: rendering a student is meant to leave with, and only what the wheel
#: carries reaches somebody who has no checkout.
NOTEBOOK = ROOT / "ipakit" / "notebooks" / "ipakit-tutorial.ipynb"

# Import the checkout, not whatever happens to be installed: the page must
# describe the tree it is generated from.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FENCE = re.compile(r"^```(console-run|python-run)[ \t]*$")
#: Width at which a quoted value moves from beside a call to beneath it.
WIDTH = 78

#: Placed under the first heading of each rendering, naming the ``make``
#: target that rewrites it.
BANNER = (
    "<!-- Generated from {source} by scripts/tutorial.py. "
    "Do not edit: run `make {target}`. -->"
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


def commands(lines: list[str]) -> list[str]:
    """The commands a ``console-run`` block asks for, without the prompt."""
    out = []
    for line in lines:
        if not line.strip():
            continue
        if not line.startswith("$ "):
            raise SystemExit(f"tutorial: console-run line must start with '$ ': {line}")
        out.append(line[2:])
    return out


def render_console(lines: list[str]) -> list[str]:
    out = ["```console"]
    for command in commands(lines):
        out.append(f"$ {command}")
        stdout, stderr = run_command(command)
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
# the parse both renderings share
# --------------------------------------------------------------------------


class Block(NamedTuple):
    """One run of source lines: ``prose``, ``python-run`` or ``console-run``."""

    kind: str
    lines: list[str]


def parse(source: str) -> list[Block]:
    """Split the authored source into blocks, running nothing.

    Both emitters walk this list, so a fence the page executes and a
    cell the notebook offers are the same block rather than two readings
    of one file that could come to disagree.
    """
    lines = strip_front_matter(source).split("\n")
    blocks: list[Block] = []
    prose: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = FENCE.match(line)
        if not match:
            prose.append(line)
            index += 1
            continue
        if prose:
            blocks.append(Block("prose", prose))
            prose = []
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].rstrip() != "```":
            body.append(lines[index])
            index += 1
        index += 1  # closing fence
        blocks.append(Block(match.group(1), body))
    if prose:
        blocks.append(Block("prose", prose))
    return blocks


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


def generate(source: Path = SOURCE, target: str = "tutorial") -> str:
    """The page: every runnable block executed, its output embedded."""
    env: dict = {}
    out: list[str] = []
    inserted_banner = False
    for block in parse(source.read_text(encoding="utf-8")):
        if block.kind == "console-run":
            out.extend(render_console(block.lines))
        elif block.kind == "python-run":
            out.extend(render_python("\n".join(block.lines), env))
        else:
            for line in block.lines:
                out.append(line)
                if not inserted_banner and line.startswith("# "):
                    out.append("")
                    out.append(BANNER.format(source=source.name, target=target))
                    inserted_banner = True
    text = "\n".join(out)
    return text.rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# notebook
# --------------------------------------------------------------------------

#: ``.ipynb`` is JSON, so writing one is ``json.dump`` on a dict and needs
#: neither ``nbformat`` nor Jupyter -- which is the point: ipakit declares
#: no runtime dependencies, and obtaining the notebook must not add one.
#: Format 4.4 rather than 4.5 because 4.5 requires a per-cell ``id``, and
#: an identifier invented by the generator is a byte in the file that says
#: nothing about the tutorial.
NBFORMAT = (4, 4)

KERNELSPEC = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}

#: The one cell the generator writes rather than renders, and the note that
#: says so. IPython displays a cell's last expression and nothing else,
#: while a third of the tutorial's blocks compute several values in a row --
#: so without this, running the notebook shows *less* than reading the page,
#: in a document whose whole subject is what the library returns. It is the
#: only cell that does not come from a block, which is why
#: ``tests/test_notebook.py`` names it and permits exactly one.
PREAMBLE_NOTE = (
    "Setup, from the generator rather than from the tutorial: it makes a cell "
    "show every value it computes, not only the last one. Nothing below "
    "depends on it -- run it once and forget it."
)
#: Guarded rather than assumed: ``get_ipython`` is a name IPython injects, so
#: outside a kernel it is not merely ``None`` but undefined, and the cell has
#: to be inert there instead of raising at somebody who ran the file as a
#: script. IPython is imported only where it is already running, so this adds
#: nothing to what obtaining or reading the notebook requires.
PREAMBLE = """\
try:
    shell = get_ipython()
except NameError:
    shell = None

if shell is not None:
    from IPython.core.interactiveshell import InteractiveShell

    InteractiveShell.ast_node_interactivity = "all"\
"""


def cell_source(text: str) -> list[str]:
    """Split as nbformat stores a cell: newlines kept, none on the last line."""
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + lines[-1:]


def cell(kind: str, text: str) -> dict[str, Any]:
    """One cell, with no result in it.

    A code cell carries ``execution_count: null`` and no outputs. That is
    the shipped property, not an oversight: it is what makes the file
    deterministic enough for ``check`` to compare byte for byte, and it
    leaves the answers to the reader who runs the cell.
    """
    if kind == "markdown":
        return {"cell_type": "markdown", "metadata": {}, "source": cell_source(text)}
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": cell_source(text),
    }


def notebook() -> str:
    """The notebook: the same blocks, offered rather than answered."""
    cells: list[dict[str, Any]] = [
        cell("markdown", PREAMBLE_NOTE),
        cell("code", PREAMBLE),
    ]
    inserted_banner = False
    for block in parse(SOURCE.read_text(encoding="utf-8")):
        if block.kind == "console-run":
            # ``!`` is how a notebook spells "run this in a shell", and the
            # command is the one the page runs, prompt removed.
            cells.append(
                cell("code", "\n".join(f"!{c}" for c in commands(block.lines)))
            )
            continue
        if block.kind == "python-run":
            cells.append(cell("code", "\n".join(block.lines).strip("\n")))
            continue
        lines = list(block.lines)
        if not inserted_banner:
            for position, line in enumerate(lines):
                if line.startswith("# "):
                    lines[position + 1 : position + 1] = [
                        "",
                        BANNER.format(source=SOURCE.name, target="notebook"),
                    ]
                    inserted_banner = True
                    break
        text = "\n".join(lines).strip("\n")
        # Prose between two adjacent fences is a blank line and nothing else.
        if text.strip():
            cells.append(cell("markdown", text))
    document = {
        "cells": cells,
        "metadata": {"kernelspec": KERNELSPEC, "language_info": {"name": "python"}},
        "nbformat": NBFORMAT[0],
        "nbformat_minor": NBFORMAT[1],
    }
    return json.dumps(document, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

#: What each rendering is called, where it goes, what writes it, and the
#: ``make`` target that rewrites it when it goes stale.
ARTIFACTS: dict[str, tuple[Path, Callable[[], str], str]] = {
    "markdown": (TARGET, lambda: generate(SOURCE, "tutorial"), "tutorial"),
    "basics": (
        BASICS_TARGET,
        lambda: generate(BASICS_SOURCE, "tutorial-basics"),
        "tutorial-basics",
    ),
    "notebook": (NOTEBOOK, notebook, "notebook"),
}


def build(name: str) -> int:
    path, render, _ = ARTIFACTS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(), encoding="utf-8")
    print(f"tutorial: wrote {path.relative_to(ROOT).as_posix()}")
    return 0


def check(name: str) -> int:
    path, render, target = ARTIFACTS[name]
    source = BASICS_SOURCE if name == "basics" else SOURCE
    where = path.relative_to(ROOT).as_posix()
    fresh = render()
    if not path.exists():
        print(f"tutorial: {where} is missing; run `make {target}`", file=sys.stderr)
        return 1
    current = path.read_text(encoding="utf-8")
    if current == fresh:
        print(f"tutorial: {where} is current")
        return 0
    diff = difflib.unified_diff(
        current.split("\n"),
        fresh.split("\n"),
        fromfile=f"{where} (checked in)",
        tofile=f"{where} (regenerated)",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    print(
        f"\ntutorial: the regenerated {where} differs from the one checked in.\n"
        f"Either the library changed what it prints, or {source.relative_to(ROOT)} is\n"
        "stale. Read the diff and decide which -- a changed value here is a\n"
        f"behavior change, not a formatting nit -- then run `make {target}`.",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["build", "check"])
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=[*ARTIFACTS, "all"],
        help="which rendering (default: both)",
    )
    args = parser.parse_args()

    missing = [source for source in (SOURCE, BASICS_SOURCE) if not source.exists()]
    if missing:
        print(f"tutorial: no source at {missing[0]}", file=sys.stderr)
        return 1

    names = list(ARTIFACTS) if args.target == "all" else [args.target]
    run = build if args.action == "build" else check
    # Every rendering is visited, so one stale artifact does not hide another.
    return max(run(name) for name in names)


if __name__ == "__main__":
    raise SystemExit(main())
