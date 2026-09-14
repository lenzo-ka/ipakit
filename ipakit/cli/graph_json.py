"""Validate and canonicalize the current native Graph format."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import ClassVar

from ..graph_json import read_graph_json, write_graph_json
from .base import Command, add_output_arg


class GraphJsonCommand(Command):
    """Validate native Graph JSON and emit its canonical spelling.

    Accept literal JSON, - for stdin, or --from-file PATH. This applies the
    native graph contract; Form inventory admission belongs to convert from-json.
    --validate succeeds silently; --pretty changes only whitespace.
    """

    name = "graph-json"
    aliases: ClassVar[list[str]] = []
    help = "Validate or canonicalize native Graph JSON"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument(
            "document", nargs="?", help="Native JSON text, or - for stdin"
        )
        source.add_argument("--from-file", type=Path, metavar="PATH")
        parser.add_argument("--pretty", action="store_true", help="Indent output")
        parser.add_argument(
            "--validate", action="store_true", help="Validate without output"
        )
        add_output_arg(parser)

    def run(self) -> int:
        document = (
            self.args.from_file.read_bytes()
            if self.args.from_file is not None
            else sys.stdin.read() if self.args.document == "-" else self.args.document
        )
        graph = read_graph_json(document)
        if not self.args.validate:
            self.print(write_graph_json(graph, pretty=self.args.pretty), end="")
        return 0
