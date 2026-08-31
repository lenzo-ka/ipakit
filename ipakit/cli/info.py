"""Info commands - quick reference information."""

from __future__ import annotations

import argparse
from typing import ClassVar

from .base import Command, CommandGroup, add_format_arg


class StressCommand(Command):
    """Show IPA stress marker information.

    IPA uses two stress markers:
        ˈ (U+02C8) - Primary stress
        ˌ (U+02CC) - Secondary stress

    Standard IPA writes the marker before the stressed syllable; ipakit
    normalizes it onto the syllable nucleus (the vowel) so conversions
    round-trip, e.g. /hˈɛlo͡ʊ/.

    In CMU ARPABET, stress is indicated by numbers on vowels:
        1 = primary stress
        2 = secondary stress
        0 = no stress

    Examples:
        ipakit info stress                 # Show stress markers
        ipakit info stress -f json         # JSON format
        ipakit i stress                    # Short form
    """

    name = "stress"
    aliases: ClassVar[list[str]] = []
    help = "Show IPA stress marker symbols and meanings"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        if self.format == "json":
            self.output_json(self.ipa.stress_markers)
        else:
            print("IPA STRESS MARKERS")
            print("-" * 40)
            for marker, level in self.ipa.stress_markers.items():
                # The name is the declared value the marker states, not a
                # test against the level. `{"ˈ": 1, "ˌ": 2}` was a table
                # this package shipped and removed; deciding the name from
                # the level is that table again, written as a comparison,
                # and a third declared level would print "secondary".
                name = self.ipa.diacritics[marker].features["stress"]
                codepoint = f"U+{ord(marker):04X}"
                print(f"  {marker}  {name:12}  level {level}  ({codepoint})")
            print()
            print("Usage: standard IPA writes the marker before the stressed")
            print("  syllable; ipakit normalizes it onto the nucleus (vowel),")
            print("  e.g. /hˈɛlo͡ʊ/, so converters round-trip.")
        return 0


class InfoGroup(CommandGroup):
    """Quick reference information about IPA symbols and conventions.

    Subcommands:
        stress   IPA stress marker symbols

    Examples:
        ipakit info stress                 # Stress marker reference
    """

    name = "info"
    aliases: ClassVar[list[str]] = ["i"]
    help = "Quick reference (stress markers, symbols)"
    commands: ClassVar[list[type[Command]]] = [StressCommand]
