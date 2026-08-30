"""Syllabification command - language-relative IPA syllabification."""

from __future__ import annotations

import argparse
from typing import Any

from ..syllable import Syllabification, languages, syllabify
from .base import IPA, Command, add_format_arg


class SyllabifyCommand(Command):
    """Syllabify an IPA form using a language declaration.

    The output reports every syllable interval and any unsyllabified residue.
    Conflicts between stated and freely derived syllable edges are also shown.

    Examples:
        ipakit syllabify wɔtɚ --language english
        ipakit syllabify konstruir --language spanish
        ipakit syllabify toːkʲoː --language japanese
        ipakit syllabify ma --language mandarin
        ipakit syllabify --languages
    """

    name = "syllabify"
    aliases: list[str] = []
    help = "Syllabify an IPA form using a language declaration"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.add_argument(
            "form",
            nargs="?",
            help="IPA transcription to syllabify (not orthography)",
        )
        parser.add_argument(
            "--language",
            "-l",
            help="Language declaration to use; see --languages",
        )
        parser.add_argument(
            "--languages",
            action="store_true",
            help="List available language declarations and exit",
        )
        add_format_arg(parser)

    @staticmethod
    def _intervals(result: Syllabification, tier: str) -> list[dict[str, Any]]:
        return [
            {
                "start": interval.start,
                "end": interval.end,
                "text": "".join(
                    unit.text
                    for unit in result.form.units[interval.start : interval.end]
                ),
            }
            for interval in result.form.intervals
            if interval.tier == tier
        ]

    def run(self) -> int:
        if self.args.languages:
            available = list(languages())
            if self.format == "json":
                self.output_json(available)
            else:
                self.output_lines(available)
            return 0

        if self.args.form is None:
            return self.error("An IPA form is required (or use --languages)")
        if self.args.language is None:
            return self.error("--language is required (see --languages)")

        result = syllabify(self.args.form, self.args.language, self.ipa)
        syllables = self._intervals(result, "syllable")
        morae = self._intervals(result, "mora")
        unsyllabified = [
            {
                "start": start,
                "end": end,
                "text": "".join(unit.text for unit in result.form.units[start:end]),
            }
            for start, end in result.unsyllabified
        ]
        conflicts: list[dict[str, Any]] = [
            {
                "at": conflict.at,
                "stated": conflict.stated,
                "derived": list(conflict.derived),
                "text": conflict.text,
            }
            for conflict in result.conflicts
        ]

        if self.format == "json":
            data: dict[str, Any] = {
                "form": self.args.form,
                "language": self.args.language,
                "syllables": syllables,
                "unsyllabified": unsyllabified,
                "conflicts": conflicts,
            }
            if morae:
                data["morae"] = morae
            self.output_json(data)
            return 0

        self.print(f"form: {self.args.form}")
        self.print(f"language: {self.args.language}")
        self.print("syllables:")
        for interval in syllables:
            self.print(f"  {interval['start']}:{interval['end']} {interval['text']}")
        if morae:
            self.print("morae:")
            for interval in morae:
                self.print(
                    f"  {interval['start']}:{interval['end']} {interval['text']}"
                )
        self.print("unsyllabified:")
        for interval in unsyllabified:
            self.print(f"  {interval['start']}:{interval['end']} {interval['text']}")
        if conflicts:
            self.print("conflicts:")
            for conflict in conflicts:
                derived = ",".join(str(edge) for edge in conflict["derived"])
                self.print(
                    f"  at {conflict['at']}: stated={conflict['stated']} "
                    f"derived={derived} text={conflict['text']}"
                )
        return 0
