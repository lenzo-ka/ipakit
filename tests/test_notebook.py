"""The tutorial notebook: a second rendering that cannot drift from the first.

``docs/tutorial.md`` and ``ipakit/notebooks/ipakit-tutorial.ipynb`` come
out of one authored source, ``docs/tutorial.src.md``, through one parse.
The page is the tutorial with the answers in it; the notebook is the same
examples with the answers taken out, for a reader to run. What makes the
notebook trustworthy is not that anything here executes it -- nothing
does -- but that its cells *are* the blocks ``scripts/tutorial.py check``
executes to build the page. An example that stops working fails that
check first.

So this file asks the questions that check cannot: does the notebook
regenerate byte for byte, is it a well-formed notebook, does every code
cell still correspond to a runnable block in the source, and is it empty
of results. The last is the shipped property -- a notebook with outputs
in it would be neither comparable byte for byte nor worth opening -- so
it is asserted rather than assumed.

Exactly one cell is the generator's own, the setup that makes a cell show
every value it computes rather than only the last. It is pinned to its
text here, so the correspondence stays a correspondence: one declared
exception, and no room for a second.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest

ROOT = Path(__file__).resolve().parent.parent

# The generator lives in scripts/, which is not a package -- the same
# reach tests/test_notation.py and tests/test_zero.py make.
sys.path.insert(0, str(ROOT / "scripts"))

from tutorial import (  # noqa: E402
    NOTEBOOK,
    PREAMBLE,
    PREAMBLE_NOTE,
    commands,
    notebook,
    parse,
)

SOURCE = ROOT / "docs" / "tutorial.src.md"


@pytest.fixture(scope="module")
def shipped() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


class TestItIsWhatTheGeneratorWrites:
    """The guard, mirroring ``scripts/tutorial.py check`` for the page."""

    def test_it_regenerates_byte_for_byte(self) -> None:
        assert NOTEBOOK.read_text(encoding="utf-8") == notebook(), (
            "the checked-in notebook is not what the generator writes; "
            "run `make notebook`"
        )

    def test_make_check_would_catch_that(self) -> None:
        """The byte comparison is a release gate, not only a test here."""
        proc = subprocess.run(
            [sys.executable, "scripts/tutorial.py", "check", "notebook"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr


class TestItIsAWellFormedNotebook:
    """Valid ``.ipynb`` JSON, asked of the file rather than of nbformat.

    The generator writes the JSON by hand, so the shape is checked by hand
    too -- a suite that
    imported ``nbformat`` to check this would be asserting that a
    dev-only package agrees with itself.
    """

    def test_the_top_level_keys_are_there(self, shipped: dict) -> None:
        assert set(shipped) == {"cells", "metadata", "nbformat", "nbformat_minor"}
        assert shipped["nbformat"] == 4
        assert isinstance(shipped["nbformat_minor"], int)

    def test_it_names_a_python_kernel(self, shipped: dict) -> None:
        assert shipped["metadata"]["kernelspec"]["language"] == "python"

    def test_every_cell_is_well_formed(self, shipped: dict) -> None:
        assert len(shipped["cells"]) > 20, "the notebook collapsed to a stub"
        for index, cell in enumerate(shipped["cells"]):
            assert cell["cell_type"] in ("markdown", "code"), index
            assert isinstance(cell["metadata"], dict), index
            assert isinstance(cell["source"], list), index
            assert cell["source"], f"cell {index} is empty"
            assert all(isinstance(line, str) for line in cell["source"]), index
            # nbformat's line list: every line but the last keeps its newline.
            assert all(line.endswith("\n") for line in cell["source"][:-1]), index
            assert not cell["source"][-1].endswith("\n"), index

    def test_it_ships_with_no_results_in_it(self, shipped: dict) -> None:
        """The shipped property. Both halves, on every code cell.

        Outputs would make the file nondeterministic, which is what the
        byte comparison above depends on, and would put an embedded SVG
        of a vocal tract in a wheel. An execution count would say the
        notebook had been run somewhere it had not.
        """
        code = [c for c in shipped["cells"] if c["cell_type"] == "code"]
        assert code, "no code cells to check"
        for index, cell in enumerate(code):
            assert cell["outputs"] == [], f"code cell {index} carries output"
            assert cell["execution_count"] is None, f"code cell {index} was run"


class TestTheTwoRenderingsCannotDrift:
    """Every cell is a block of the source, bar the one that is declared.

    The generator writes exactly one cell of its own, and it is named
    here rather than allowed for: "a cell that came from nowhere" is the
    hole a drift guard cannot have, so the exception is pinned to that
    string and everything after it has to be a block.
    """

    def test_the_generator_adds_one_cell_and_says_which(self, shipped: dict) -> None:
        note, preamble = shipped["cells"][:2]
        assert note["cell_type"] == "markdown"
        assert "".join(note["source"]) == PREAMBLE_NOTE
        assert preamble["cell_type"] == "code"
        assert "".join(preamble["source"]) == PREAMBLE
        # It has to say it is not the tutorial, because it is read first.
        assert "generator" in PREAMBLE_NOTE

    def test_the_added_cell_is_inert_outside_ipython(self) -> None:
        """A reader who runs the file as a script gets no traceback from it.

        ``get_ipython`` is a name IPython injects, so outside a kernel it
        is undefined rather than ``None`` -- which is why the guard is a
        ``NameError`` and not a truth test.
        """
        namespace: dict = {}
        exec(compile(PREAMBLE, "<preamble>", "exec"), namespace)
        assert namespace["shell"] is None
        assert "IPython" not in namespace

    def test_every_other_code_cell_is_a_runnable_block(self, shipped: dict) -> None:
        blocks = parse(SOURCE.read_text(encoding="utf-8"))
        expected = [
            (
                "\n".join(f"!{c}" for c in commands(block.lines))
                if block.kind == "console-run"
                else "\n".join(block.lines).strip("\n")
            )
            for block in blocks
            if block.kind in ("console-run", "python-run")
        ]
        assert len(expected) > 20, "the source has stopped declaring runnable blocks"
        written = [
            "".join(cell["source"])
            for cell in shipped["cells"]
            if cell["cell_type"] == "code"
        ]
        assert written[0] == PREAMBLE, "the added cell is no longer the first"
        assert written[1:] == expected

    def test_a_shell_cell_asks_for_the_command_the_page_runs(
        self, shipped: dict
    ) -> None:
        """``$ ipakit ...`` on the page is ``!ipakit ...`` in a cell."""
        shell = [
            line
            for cell in shipped["cells"]
            if cell["cell_type"] == "code"
            for line in "".join(cell["source"]).split("\n")
            if line.startswith("!")
        ]
        assert shell, "no shell cells found"
        assert all(line.startswith("!ipakit ") for line in shell), shell


class TestWritingACopy:
    """``ipakit notebook`` and ``ipakit.notebook`` hand over the same bytes."""

    def test_the_api_writes_the_shipped_file(self, tmp_path: Path) -> None:
        written = ipakit.notebook(tmp_path)
        assert written == tmp_path / "ipakit-tutorial.ipynb"
        assert written.read_bytes() == NOTEBOOK.read_bytes()

    def test_it_makes_a_directory_that_is_not_there(self, tmp_path: Path) -> None:
        written = ipakit.notebook(tmp_path / "class" / "week-one")
        assert written.is_file()

    def test_it_refuses_to_clobber(self, tmp_path: Path) -> None:
        first = ipakit.notebook(tmp_path)
        first.write_text("my own work", encoding="utf-8")
        with pytest.raises(FileExistsError, match="already exists"):
            ipakit.notebook(tmp_path)
        assert first.read_text(encoding="utf-8") == "my own work"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        first = ipakit.notebook(tmp_path)
        first.write_text("my own work", encoding="utf-8")
        assert ipakit.notebook(tmp_path, force=True).read_bytes() == (
            NOTEBOOK.read_bytes()
        )

    def test_the_command_writes_it_and_says_where(self, tmp_path: Path, capsys) -> None:
        from ipakit.cli import main

        argv = ["ipakit", "notebook", "-o", str(tmp_path)]
        old, sys.argv = sys.argv, argv
        try:
            assert main() == 0
        finally:
            sys.argv = old
        out = capsys.readouterr().out
        target = tmp_path / "ipakit-tutorial.ipynb"
        assert target.read_bytes() == NOTEBOOK.read_bytes()
        assert str(target) in out
        assert "jupyter" in out

    def test_the_command_says_what_happened_rather_than_clobbering(
        self, tmp_path: Path, capsys
    ) -> None:
        from ipakit.cli import main

        (tmp_path / "ipakit-tutorial.ipynb").write_text("mine", encoding="utf-8")
        argv = ["ipakit", "notebook", "-o", str(tmp_path)]
        old, sys.argv = sys.argv, argv
        try:
            assert main() == 1
        finally:
            sys.argv = old
        err = capsys.readouterr().err
        assert "already exists" in err and "--force" in err
        assert (tmp_path / "ipakit-tutorial.ipynb").read_text(
            encoding="utf-8"
        ) == "mine"
