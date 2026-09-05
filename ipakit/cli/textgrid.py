"""Read and write Praat TextGrid documents."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from ..form import Form
from ..textgrid import profiles, read, write
from .base import IPA, Command, CommandGroup, add_format_arg, add_output_arg


def _tier_map(value: str) -> Mapping[str, str]:
    pairs: dict[str, str] = {}
    for pair in value.split(","):
        parts = pair.split("=")
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"tier-map pair {pair!r} is malformed; accepted form: name=role"
            )
        pairs[parts[0]] = parts[1]
    return pairs


class TextGridWriteCommand(Command):
    """Write an IPA form as a Praat TextGrid.

    Examples:
        ipakit textgrid write "kæt"
        ipakit textgrid write "kæt dɒɡ" --profile words -o speech.TextGrid
    """

    name, aliases, help = "write", [], "Write IPA as a Praat TextGrid"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ipa", help="IPA transcription to write (not orthography)")
        parser.add_argument(
            "--profile",
            default="segments",
            help=f"TextGrid profile ({', '.join(profiles())})",
        )
        add_output_arg(parser)

    def run(self) -> int:
        try:
            form = Form.parse(self.args.ipa, features=self.ipa)
            self.output(
                write(
                    form,
                    self.args.profile,
                    features=self.ipa,
                ).rstrip("\n")
            )
        except ValueError as error:
            return self.error(str(error))
        return 0


class TextGridReadCommand(Command):
    """Read a Praat TextGrid as an IPA form and tier intervals.

    Examples:
        ipakit textgrid read speech.TextGrid --profile mfa
        ipakit textgrid read speech.TextGrid --tier-map phones=segment,words=word
    """

    name, aliases, help = "read", [], "Read a Praat TextGrid as an IPA form"
    reads_notation = None

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("file", type=Path, help="TextGrid file to read")
        mapping = parser.add_mutually_exclusive_group()
        mapping.add_argument(
            "--profile", help=f"TextGrid profile ({', '.join(profiles())})"
        )
        mapping.add_argument(
            "--tier-map",
            help="Comma-separated TextGrid tier-to-role mapping",
        )
        parser.add_argument("--unit", default="s", help="Physical coordinate unit")
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        try:
            mapping = (
                None if self.args.tier_map is None else _tier_map(self.args.tier_map)
            )
            form = read(
                self.args.file.read_bytes(),
                profile=self.args.profile,
                tier_map=mapping,
                unit=self.args.unit,
                features=self.ipa,
            )
        except (OSError, ValueError) as error:
            return self.error(str(error))
        if self.format == "json":
            self.output_json(form.to_dict())
            return 0
        self.print(form.to_ipa())
        for interval in form.intervals:
            timing = ""
            if interval.timing is not None:
                timing = (
                    f" {interval.timing.start}..{interval.timing.end} {self.args.unit}"
                )
            self.print(f"{interval.tier} {interval.start}..{interval.end}{timing}")
        return 0


class TextGridGroup(CommandGroup):
    """Commands for Praat TextGrid interchange."""

    name = "textgrid"
    aliases: ClassVar[list[str]] = []
    help = "Read and write Praat TextGrids"
    commands = [TextGridWriteCommand, TextGridReadCommand]
