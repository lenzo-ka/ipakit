"""Hierarchy commands - generate phone hierarchies by features."""

from __future__ import annotations

import argparse
from pathlib import Path

from .base import Command, CommandGroup


def add_features_arg(parser: argparse.ArgumentParser) -> None:
    """Add --features argument for hierarchy commands."""
    parser.add_argument(
        "--features",
        "-f",
        help="Comma-separated feature order for grouping (e.g., 'manner,place,voiced')",
    )


class TextCommand(Command):
    """Generate a text tree showing phones grouped by features.

    Phones are recursively grouped by feature values, creating an
    indented tree structure. The feature order determines the
    grouping hierarchy (first feature = top level).

    Examples:
        ipakit hierarchy text                      # Default feature order
        ipakit hierarchy text -f manner            # Group by manner only
        ipakit hierarchy text -f manner,place      # Manner then place
        ipakit h text -f voiced,manner --indent 4  # Custom indentation
    """

    name = "text"
    aliases = []
    help = "Text tree grouped by features"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_features_arg(parser)
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="Number of spaces per indentation level (default: 2)",
        )

    def run(self) -> int:
        feature_order = self.args.features.split(",") if self.args.features else None
        result = self.ipa.hierarchy_to_text(
            feature_order=feature_order, indent=" " * self.args.indent
        )
        print(result)
        return 0


class DotCommand(Command):
    """Generate a DOT graph of phones grouped by features.

    Creates a Graphviz DOT file that can be rendered to PNG, SVG,
    or other formats. Use --render to automatically generate PNG
    (requires graphviz 'dot' command in PATH).

    Examples:
        ipakit hierarchy dot                       # Print DOT to stdout
        ipakit hierarchy dot -o phones.dot        # Save to file
        ipakit h dot -o phones.dot --render       # Save and render PNG
        ipakit h dot -f manner,place -t "Consonants"  # Custom title
    """

    name = "dot"
    aliases = []
    help = "DOT graph for Graphviz visualization"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_features_arg(parser)
        parser.add_argument(
            "--output",
            "-o",
            type=Path,
            help="Output file path (prints to stdout if not specified)",
        )
        parser.add_argument(
            "--render",
            "-r",
            action="store_true",
            help="Also render to PNG using graphviz (requires 'dot' command)",
        )
        parser.add_argument(
            "--title",
            "-t",
            default="IPA Phone Hierarchy",
            help="Graph title (default: 'IPA Phone Hierarchy')",
        )

    def run(self) -> int:
        feature_order = self.args.features.split(",") if self.args.features else None
        result = self.ipa.hierarchy_to_dot(
            feature_order=feature_order, title=self.args.title
        )

        if self.args.output:
            with open(self.args.output, "w") as f:
                f.write(result)
            print(f"Saved: {self.args.output}")

            if self.args.render:
                try:
                    import subprocess

                    png_path = self.args.output.with_suffix(".png")
                    subprocess.run(
                        ["dot", "-Tpng", str(self.args.output), "-o", str(png_path)],
                        check=True,
                    )
                    print(f"Rendered: {png_path}")
                except FileNotFoundError:
                    print(
                        "Warning: 'dot' command not found. Install graphviz to render."
                    )
                except Exception as e:
                    print(f"Warning: Could not render PNG: {e}")
        else:
            print(result)
        return 0


class JsonCommand(Command):
    """Generate a JSON hierarchy of phones grouped by features.

    Produces a nested JSON structure suitable for programmatic
    processing or web visualization (e.g., D3.js trees).

    Structure:
        {"feature": "manner", "children": {"plosive": {...}, ...}}
        Leaf nodes: {"phones": ["p", "b", ...]}

    Examples:
        ipakit hierarchy json                      # Full hierarchy
        ipakit hierarchy json -f manner            # Group by manner
        ipakit h json -f manner,place > tree.json  # Save to file
    """

    name = "json"
    aliases = []
    help = "JSON hierarchy for programmatic use"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_features_arg(parser)

    def run(self) -> int:
        feature_order = self.args.features.split(",") if self.args.features else None
        tree = self.ipa.build_hierarchy(feature_order=feature_order)
        self.output_json(tree)
        return 0


class HierarchyGroup(CommandGroup):
    """Generate hierarchical phone groupings by features.

    Creates tree structures showing how phones cluster based on
    their feature values. Useful for visualizing phonological
    patterns and natural classes.

    Subcommands:
        text   Indented text tree
        dot    Graphviz DOT format (for diagrams)
        json   JSON tree (for programmatic use)

    Examples:
        ipakit hierarchy text -f manner,place    # Text tree
        ipakit hierarchy dot -o tree.dot -r      # DOT + PNG
        ipakit hierarchy json > phones.json      # JSON export
    """

    name = "hierarchy"
    aliases = ["h"]
    help = "Generate phone hierarchies (text, dot, json)"
    commands = [TextCommand, DotCommand, JsonCommand]
