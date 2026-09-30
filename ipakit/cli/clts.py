"""Structured CLTS import and source/canonical token emission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, ClassVar

from .. import Form
from ..clts import (
    CLTSImport,
    CLTSInputError,
    _unique_object,
    emit_tokens,
    import_document,
    import_tokens,
    load_import,
)
from .base import NO_NOTATION, Command, CommandGroup


def _read_json(path: Path) -> Any:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=invalid_constant,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise CLTSInputError("invalid-input", "", str(error)) from error


def _selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--clts",
        type=Path,
        help="Explicit pinned CLTS checkout (requires --manifest and ipakit[interop])",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Final CLTS manifest to verify with the explicit checkout",
    )


class CLTSReadCommand(Command):
    """Import explicit CLTS tokens and write the complete result as JSON."""

    name = "read"
    aliases: ClassVar[list[str]] = []
    help = "Import explicit CLTS tokens or a structured input document"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument(
            "--tokens-json",
            type=Path,
            metavar="FILE",
            help="Read an explicit JSON array of token strings",
        )
        source.add_argument(
            "--input-json",
            type=Path,
            metavar="FILE",
            help="Read a structured ipakit-clts-input document",
        )
        parser.add_argument(
            "--projection",
            choices=("explicit-only", "house-convention-v1"),
            default="explicit-only",
            help="Select the reviewed house-projection policy",
        )
        parser.add_argument(
            "--unsupported",
            choices=("error", "preserve"),
            default="error",
            help="Refuse or preserve occurrences without a house projection",
        )
        parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
        _selection_arguments(parser)

    def run(self) -> int:
        try:
            if self.args.tokens_json is not None:
                result = import_tokens(
                    _read_json(self.args.tokens_json),
                    projection=self.args.projection,
                    unsupported=self.args.unsupported,
                    clts=self.args.clts,
                    manifest=self.args.manifest,
                )
            else:
                result = import_document(
                    _read_json(self.args.input_json),
                    projection=self.args.projection,
                    unsupported=self.args.unsupported,
                    clts=self.args.clts,
                    manifest=self.args.manifest,
                )
        except CLTSInputError as error:
            self.print(error.to_json(pretty=self.args.pretty))
            return 1
        self.print(result.to_json(pretty=self.args.pretty))
        return 0 if result.status in ("complete", "preserved") else 1


class CLTSEmitCommand(Command):
    """Emit exact source or canonical BIPA tokens from saved native JSON."""

    name = "emit"
    aliases: ClassVar[list[str]] = []
    help = "Emit source or canonical BIPA tokens from saved JSON"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--from-json",
            type=Path,
            required=True,
            metavar="FILE",
            help="Read a saved import envelope or native Form document",
        )
        parser.add_argument(
            "--spelling",
            choices=("source", "bipa"),
            default="source",
            help="Emit exact source tokens or canonical BIPA spelling",
        )
        parser.add_argument(
            "--allow-loss",
            action="store_true",
            help="Authorize reported loss in canonical BIPA spelling",
        )
        parser.add_argument("--pretty", action="store_true", help="Indent JSON output")

    def run(self) -> int:
        try:
            document = _read_json(self.args.from_json)
            source: CLTSImport | Form
            if isinstance(document, dict) and set(document) == {"form", "report"}:
                source = load_import(document)
            else:
                source = Form.from_dict(document)
            result = emit_tokens(
                source,
                spelling=self.args.spelling,
                allow_loss=self.args.allow_loss,
            )
        except CLTSInputError as error:
            self.print(error.to_json(pretty=self.args.pretty))
            return 1
        except (TypeError, ValueError) as error:
            public = CLTSInputError("invalid-input", "", str(error))
            self.print(public.to_json(pretty=self.args.pretty))
            return 1
        self.print(result.to_json(pretty=self.args.pretty))
        return 0 if result.status == "complete" else 1


class CLTSGroup(CommandGroup):
    """Import and emit source-preserving CLTS/BIPA documents."""

    name = "clts"
    aliases: ClassVar[list[str]] = []
    help = "Import and emit source-preserving CLTS/BIPA documents"
    commands: ClassVar[list[type[Command]]] = [CLTSReadCommand, CLTSEmitCommand]
