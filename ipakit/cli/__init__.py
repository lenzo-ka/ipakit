"""Command-line interface for ipakit.

Organized into subcommands:
    ipakit features <phone>     Get features for an IPA phone
    ipakit convert ...          Convert between IPA/CMU/X-SAMPA
    ipakit query ...            Query phones by features
    ipakit distance ...         Calculate phonetic distances
    ipakit hierarchy ...        Generate phone hierarchies
    ipakit analyze ...          Analyze and validate data
    ipakit info ...             Package and data info

Use 'help' anywhere to get help on the next command:
    ipakit help                 General help
    ipakit help convert         Help on convert group
    ipakit convert help         Same as above
    ipakit convert to-cmu --help  Help on to-cmu
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis_cmds import AnalysisGroup, DescribeCommand
from .analyze import AnalyzeGroup
from .base import Command
from .convert import ConvertGroup
from .distance import DistanceGroup
from .features import FeaturesCommand
from .hierarchy import HierarchyGroup
from .info import InfoGroup
from .query import QueryGroup

# All command groups for help lookup
GROUPS = [
    ConvertGroup,
    QueryGroup,
    DistanceGroup,
    HierarchyGroup,
    AnalysisGroup,
    AnalyzeGroup,
    InfoGroup,
]


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="ipakit",
        description="IPA phonetic features toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ipakit features p                    # Get features for 'p'
  ipakit features "pʰ" --short         # Get short names for aspirated p
  ipakit describe p                    # "voiceless bilabial plosive"
  ipakit convert to-cmu "kˈæt"         # IPA to CMU: K AE1 T (stress on the vowel)
  ipakit convert to-ipa K AE1 T        # CMU to IPA: kˈæt
  ipakit query match plosive bilabial  # Find: b p ɓ
  ipakit query match +voi plo bil      # Voiced bilabial plosives: b ɓ
  ipakit analysis natural-class p t k  # Find shared features
  ipakit analysis minimal-pairs p      # Find similar phones
  ipakit distance pair p b             # Raw feature distance: ~0.04
  ipakit distance confusability p b    # Inventory-relative: 0.8454
  ipakit distance word kæt kæd         # Word similarity: 0.9742
  ipakit hierarchy text                # Text hierarchy
  ipakit analyze validate              # Validate XML
""",
    )

    # Global options
    parser.add_argument("--ipa-xml", type=Path, help="Path to ipa.xml")
    parser.add_argument("--cmu-xml", type=Path, help="Path to cmu.xml")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register standalone commands (not in groups)
    for cmd_cls in [FeaturesCommand, DescribeCommand]:
        cmd_parser = subparsers.add_parser(
            cmd_cls.name,
            aliases=cmd_cls.aliases,
            help=cmd_cls.help,
        )
        cmd_cls.add_arguments(cmd_parser)
        cmd_parser.set_defaults(cmd_cls=cmd_cls)

    # Register command groups
    for group in GROUPS:
        group.register(subparsers)

    return parser


def _preprocess_help(argv: list[str]) -> list[str]:
    """Transform 'help' anywhere in args to --help in the right place.

    Examples:
        ['help']                    → ['--help']
        ['help', 'convert']         → ['convert', '--help']
        ['convert', 'help']         → ['convert', '--help']
        ['convert', 'help', 'to-cmu'] → ['convert', 'to-cmu', '--help']
        ['convert', 'to-cmu', 'help'] → ['convert', 'to-cmu', '--help']
    """
    if "help" not in argv:
        return argv

    # Remove 'help' and collect non-help args
    result = [a for a in argv if a != "help"]

    # Add --help at the end
    result.append("--help")
    return result


def main() -> int:
    """Main entry point."""
    # Preprocess to handle 'help' anywhere in command
    argv = _preprocess_help(sys.argv[1:])

    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Direct command (features)
    if hasattr(args, "cmd_cls") and args.cmd_cls is not None:
        try:
            cmd: Command = args.cmd_cls(args)
            return cmd.run()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Every real command and subcommand sets `cmd_cls` (see create_parser and
    # CommandGroup.register), and an empty command line is handled above. So if
    # we reach here, a command GROUP was named with no subcommand (e.g.
    # `ipakit convert`, or its alias `ipakit c`). Show that group's help:
    # parse_args([group, "-h"]) prints the help and exits via SystemExit, so
    # control never returns past this call.
    parser.parse_args([args.command, "-h"])
    return 0  # unreachable (argparse -h exits); kept for the type checker


if __name__ == "__main__":
    sys.exit(main())
