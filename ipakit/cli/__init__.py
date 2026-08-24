"""Command-line interface for ipakit.

Organized into subcommands:
    ipakit features <phone>     Get features for an IPA phone
    ipakit describe <phone>     Human-readable phone description
    ipakit notebook             Write the tutorial notebook here, to run
    ipakit corpus ...           Build, inspect, and query form corpora
    ipakit convert ...          Convert notation, serialize Forms, render katakana
    ipakit query ...            Query phones by features
    ipakit rules ...            Rewrite rules and derived morae
    ipakit distance ...         Calculate phonetic distances
    ipakit hierarchy ...        Generate phone hierarchies
    ipakit analysis ...         Analyze phones (describe, natural-class, minimal-pairs)
    ipakit analyze ...          Inspect/validate the feature data files (alias: data)
    ipakit info ...             Package and data info
    ipakit phoible ...          Read mounted PHOIBLE doculect inventories
    ipakit tract ...            Draw the mid-sagittal tract figure
    ipakit tiergraph ...        Render a form's tier graph as Graphviz DOT

Note the two similarly-named groups: `analysis` analyzes phones, while
`analyze` (alias `data`) inspects and validates the underlying data files.

Use 'help' anywhere to get help on the next command:
    ipakit help                 General help
    ipakit help convert         Help on convert group
    ipakit convert help         Same as above
    ipakit convert to-cmu --help  Help on to-cmu

Exit status is uniform across every subcommand:
    0  the command succeeded and its input was read in full
    1  the command failed ('Error: ...' on stderr)
    2  the command line was not understood (argparse)
    3  the command ran, but part of the input could not be read

See :mod:`ipakit.cli.policy` for why the third case is a status of its
own rather than a warning alone, and for what ``--lax`` turns off.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

from .analysis_cmds import AnalysisGroup, DescribeCommand
from .analyze import AnalyzeGroup
from .base import Command, add_lax_arg
from .convert import ConvertGroup
from .corpus import CorpusGroup
from .distance import DistanceGroup
from .features import FeaturesCommand
from .hierarchy import HierarchyGroup
from .info import InfoGroup
from .notebook import NotebookCommand
from .phoible import PhoibleGroup
from .policy import report
from .query import QueryGroup
from .rules import RulesGroup
from .tiergraph import TiergraphCommand
from .tract import TractGroup

# All command groups for help lookup
GROUPS = [
    CorpusGroup,
    ConvertGroup,
    QueryGroup,
    RulesGroup,
    DistanceGroup,
    HierarchyGroup,
    AnalysisGroup,
    AnalyzeGroup,
    InfoGroup,
    PhoibleGroup,
    TractGroup,
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
  ipakit corpus init speech-corpus     # Create an empty form corpus
  ipakit convert to-cmu "kˈæt"         # IPA to CMU: K AE1 T (stress on the vowel)
  ipakit convert from-cmu K AE1 T        # CMU to IPA: kˈæt
  ipakit convert to-json "kæt"          # Versioned graph-backed Form JSON
  ipakit convert to-katakana "hɑt"      # Attested loanword adaptation: ホット
  ipakit query match plosive bilabial  # Find: b p ɓ ʘ
  ipakit query match +voi plo bil      # Voiced bilabial plosives: b ɓ
  ipakit rules apply -s american-english pˈɪn   # broad to narrow: pʰˈɪ̃n
  ipakit rules trace -s american-english bˈʌtɚ  # which rule fired, and where
  ipakit rules morae "hɑt"              # Attested adaptation morae: ho t to
  ipakit analysis natural-class p t k  # Find shared features
  ipakit analysis minimal-pairs p      # Find similar phones
  ipakit distance pair p b             # Raw feature distance: ~0.04
  ipakit distance confusability p b    # inventory-relative
  ipakit distance word kæt kæd         # word similarity
  ipakit hierarchy text                # Text hierarchy
  ipakit analyze validate              # Validate XML
  ipakit phoible --help                # Mounted PHOIBLE inventory commands
  ipakit tract draw t -o t.svg         # Mid-sagittal figure for 't'
  ipakit tiergraph "kæt" -o kæt.dot    # Complete ordered tier graph
  ipakit tract heads                   # Head shapes a figure can be drawn on
  ipakit notebook                      # The tutorial, as cells you run

Exit status (uniform across every subcommand):
  0  succeeded, and the input was read in full
  1  the command failed ('Error: ...' on stderr)
  2  the command line was not understood
  3  ran, but part of the input could not be read and was dropped;
     what was dropped is named on stderr. --lax reports 0 instead.
""",
    )

    # Global options
    parser.add_argument("--ipa-xml", type=Path, help="Path to ipa.xml")
    parser.add_argument("--cmu-xml", type=Path, help="Path to cmu.xml")
    add_lax_arg(parser, top_level=True)

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register standalone commands (not in groups)
    for cmd_cls in [
        FeaturesCommand,
        DescribeCommand,
        NotebookCommand,
        TiergraphCommand,
    ]:
        cmd_parser = subparsers.add_parser(
            cmd_cls.name,
            aliases=cmd_cls.aliases,
            help=cmd_cls.help,
        )
        cmd_cls.add_arguments(cmd_parser)
        add_lax_arg(cmd_parser)
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
        # ``query`` predates the corpus DSL as an inventory-query group.
        # Keep those named subcommands while making the new form-level door
        # read naturally as ``ipakit query '<dsl>' IPA...``.
        if argv[:1] in (["query"], ["q"]) and len(argv) > 1:
            inventory_commands = {
                "find",
                "match",
                "m",
                "list",
                "l",
                "features",
                "f",
                "classes",
                "shorts",
                "s",
            }
            if argv[1] not in inventory_commands and not argv[1].startswith("-"):
                return [argv[0], "find", *argv[1:]]
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

    # Every leaf command (standalone or group subcommand) is dispatched here.
    if hasattr(args, "cmd_cls") and args.cmd_cls is not None:
        cmd: Command = args.cmd_cls(args)
        # Warnings are caught rather than left to the interpreter so the
        # loss they report can reach the exit status, and so the message
        # is not deduplicated by source line -- see ipakit.cli.policy.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                status = cmd.run()
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                status = 1
            finally:
                # Flush/close the output file if the command opened one (-o).
                cmd._close_output()
        return report(caught, status, lax=getattr(args, "lax", False))

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
