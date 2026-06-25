"""Info commands - quick reference information."""

from __future__ import annotations

import argparse

from ..constants import STRESS_MARKERS
from .base import Command, CommandGroup, add_format_arg


class StressCommand(Command):
    """Show IPA stress marker information.

    IPA uses two stress markers:
        ˈ (U+02C8) - Primary stress (placed before stressed syllable)
        ˌ (U+02CC) - Secondary stress (placed before syllable)

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
    aliases = []
    help = "Show IPA stress marker symbols and meanings"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        if self.format == "json":
            self.output_json(STRESS_MARKERS)
        else:
            print("IPA STRESS MARKERS")
            print("-" * 40)
            for marker, level in STRESS_MARKERS.items():
                name = "primary" if level == 1 else "secondary"
                codepoint = f"U+{ord(marker):04X}"
                print(f"  {marker}  {name:12}  level {level}  ({codepoint})")
            print()
            print("Usage: Placed immediately before the stressed syllable")
            print("  Example: /ˈhɛloʊ/ (primary stress on first syllable)")
        return 0


class InfoGroup(CommandGroup):
    """Quick reference information about IPA symbols and conventions.

    Subcommands:
        stress   IPA stress marker symbols

    Examples:
        ipakit info stress                 # Stress marker reference
    """

    name = "info"
    aliases = ["i"]
    help = "Quick reference (stress markers, symbols)"
    commands = [StressCommand]
