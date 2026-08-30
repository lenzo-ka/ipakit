"""Draw the tier graph behind a form."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..form import Form
from .base import IPA, Command, add_output_arg


class TiergraphCommand(Command):
    """Write the complete ordered tier graph behind a form as Graphviz DOT.

    The graph is the store a Form is kept in: every unit, every tier it
    belongs to, and the order relations among them, rather than the flat
    string a transcription prints as. Render it with 'dot -Tsvg'.

    Examples:
        ipakit tiergraph "kæt" -o kaet.dot
        ipakit tiergraph --from-json form.json
    """

    name, aliases, help = "tiergraph", [], "Render a form's tier graph as DOT"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("ipa", nargs="?", help="IPA transcription to render")
        source.add_argument(
            "--from-json", type=Path, metavar="PATH", help="Render a Form JSON file"
        )
        parser.add_argument("--strict", action="store_true", help="Reject unknown IPA")
        add_output_arg(parser)

    def run(self) -> int:
        if self.args.from_json is not None:
            form = Form.from_json(
                self.args.from_json.read_text(encoding="utf-8"), self.ipa
            )
        else:
            form = self.ipa.read(self.args.ipa, strict=self.args.strict)
        self.output(form.to_dot().rstrip("\n"))
        return 0
