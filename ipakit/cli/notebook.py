"""Notebook command - write out the tutorial notebook.

Top-level rather than inside a group: a student looking for somewhere to
start reads ``ipakit --help`` and has to find it there.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import ClassVar

from .._notebook import notebook
from .base import Command


class NotebookCommand(Command):
    """Write the tutorial notebook into a directory you can work in.

    The notebook is the tutorial with the answers taken out: the same
    examples docs/tutorial.md prints results for, as cells you run. It
    ships in the package, so this is a copy out of the install rather
    than anything built here.

    Examples:
        ipakit notebook              # into the current directory
        ipakit notebook -o ~/class   # somewhere else
        ipakit notebook --force      # overwrite a copy already there
    """

    name = "notebook"
    aliases: ClassVar[list[str]] = []
    help = "Write the tutorial notebook here, to run yourself"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "--output",
            "-o",
            type=Path,
            default=Path("."),
            metavar="DIR",
            help="Directory to write into (default: the current one)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite a notebook of the same name",
        )

    def run(self) -> int:
        try:
            written = notebook(self.args.output, force=self.args.force)
        except FileExistsError as exc:
            return self.error(f"{exc}; pass --force to overwrite it, or -o DIR")
        # Not self.print: -o names the directory here, so there is no
        # output file for the base class to have opened.
        print(f"wrote {written}")
        print(f"open it with: jupyter lab {written}")
        return 0
