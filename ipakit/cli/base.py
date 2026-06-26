"""Base utilities for CLI commands."""

from __future__ import annotations

import argparse
import json
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from ..constants import DEFAULT_CMU_MAP, DEFAULT_IPA_FEATS

if TYPE_CHECKING:
    from ..features import IPAFeatures
    from ..mapper import CMUMapper


class Command(ABC):
    """Base class for CLI commands."""

    name: str  # Subcommand name
    aliases: list[str] = []  # Short aliases
    help: str  # Help text

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self._ipa: IPAFeatures | None = None
        self._cmu: CMUMapper | None = None
        self._output_file: IO[str] | None = None

    @property
    def ipa(self) -> IPAFeatures:
        """Lazy-load IPAFeatures."""
        if self._ipa is None:
            from ..features import IPAFeatures

            xml_path = getattr(self.args, "ipa_xml", None) or DEFAULT_IPA_FEATS
            self._ipa = IPAFeatures(xml_path)
        return self._ipa

    @property
    def cmu(self) -> CMUMapper:
        """Lazy-load CMUMapper."""
        if self._cmu is None:
            from ..mapper import CMUMapper

            xml_path = getattr(self.args, "cmu_xml", None) or DEFAULT_CMU_MAP
            self._cmu = CMUMapper(xml_path)
        return self._cmu

    @property
    def format(self) -> str:
        """Get output format from args."""
        return getattr(self.args, "format", "text")

    @property
    def output_path(self) -> Path | None:
        """Get output file path from args."""
        return getattr(self.args, "output", None)

    @abstractmethod
    def run(self) -> int:
        """Execute the command. Return exit code."""
        ...

    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add command-specific arguments to parser."""
        ...

    # --- Output helpers ---

    def _get_output(self) -> IO[str]:
        """Get output stream (file or stdout)."""
        if self._output_file is not None:
            return self._output_file
        if self.output_path:
            self._output_file = open(self.output_path, "w", encoding="utf-8")
            return self._output_file
        return sys.stdout

    def _close_output(self) -> None:
        """Close output file if opened."""
        if self._output_file is not None:
            self._output_file.close()
            self._output_file = None

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to output (file or stdout)."""
        kwargs.setdefault("file", self._get_output())
        print(*args, **kwargs)

    def output(self, text: str) -> None:
        """Output text to file or stdout."""
        self.print(text)

    def output_json(self, data: Any, indent: int = 2) -> None:
        """Output data as JSON."""
        self.print(json.dumps(data, indent=indent, ensure_ascii=False))

    def get_aliases(self, canonical: str) -> list[str]:
        """Get aliases for a canonical phone/diacritic name."""
        return [
            alias
            for alias, canon in self.ipa.ligature_map.items()
            if canon == canonical
        ]

    def order_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """Order a feature dict according to feature_order.

        Puts 'name' first, then 'aliases', then 'class' (structural metadata),
        then features in declaration order.
        """
        ordered = {}
        # Put 'name' first if present
        if "name" in features:
            ordered["name"] = features["name"]
        # Put 'aliases' second if present
        if "aliases" in features:
            ordered["aliases"] = features["aliases"]
        # Put 'class' third if present (structural metadata, not a phonetic feature)
        if "class" in features:
            ordered["class"] = features["class"]
        # Then add phonetic features in declaration order
        for key in self.ipa.feature_order:
            if key in features:
                ordered[key] = features[key]
        return ordered

    def output_lines(self, lines: list[str]) -> None:
        """Output lines."""
        for line in lines:
            self.print(line)

    def output_table(
        self, rows: list[list[str]], headers: list[str] | None = None
    ) -> None:
        """Output data as aligned table."""
        all_rows = [headers] + rows if headers else rows
        if not all_rows:
            return
        widths = [
            max(len(str(row[i])) for row in all_rows) for i in range(len(all_rows[0]))
        ]
        if headers:
            self.print(
                "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
            )
            self.print("  ".join("-" * w for w in widths))
        for row in rows:
            self.print(
                "  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True))
            )

    def output_result(
        self, data: Any, text_formatter: Callable[[Any], str] | None = None
    ) -> None:
        """Output structured data as JSON or formatted text.

        Args:
            data: The structured data to output
            text_formatter: Optional function(data) -> str for text output.
                           If None, uses default formatting based on data type.
        """
        if self.format == "json":
            self.output_json(data)
        elif text_formatter:
            self.print(text_formatter(data))
        elif isinstance(data, list):
            for item in data:
                self.print(item)
        elif isinstance(data, dict):
            for k, v in data.items():
                self.print(f"{k}: {v}")
        else:
            self.print(str(data))

    def error(self, message: str) -> int:
        """Print error to stderr and return exit code 1."""
        print(f"Error: {message}", file=sys.stderr)
        return 1


class CommandGroup(ABC):
    """Base class for command groups (subcommand containers)."""

    name: str  # Group name
    aliases: list[str] = []  # Short aliases
    help: str  # Help text
    commands: list[type[Command]] = []  # Subcommands

    @classmethod
    def register(
        cls, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]
    ) -> None:
        """Register this command group and its subcommands."""
        parser = subparsers.add_parser(
            cls.name,
            aliases=cls.aliases,
            help=cls.help,
        )
        group_sub = parser.add_subparsers(
            dest=f"{cls.name}_cmd", help=f"{cls.name} commands"
        )

        for cmd_cls in cls.commands:
            cmd_parser = group_sub.add_parser(
                cmd_cls.name,
                aliases=cmd_cls.aliases,
                help=cmd_cls.help,
            )
            cmd_cls.add_arguments(cmd_parser)
            cmd_parser.set_defaults(cmd_cls=cmd_cls)


def add_format_arg(
    parser: argparse.ArgumentParser, choices: list[str] | None = None
) -> None:
    """Add --format argument to parser."""
    if choices is None:
        choices = ["text", "json"]
    parser.add_argument(
        "--format", "-f", choices=choices, default="text", help="Output format"
    )
    if "json" in choices:
        parser.add_argument(
            "--json",
            "-j",
            action="store_const",
            const="json",
            dest="format",
            help="Output as JSON (shorthand for --format json)",
        )


def add_output_arg(parser: argparse.ArgumentParser) -> None:
    """Add --output argument to parser."""
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (default: stdout)"
    )


def add_strict_arg(parser: argparse.ArgumentParser) -> None:
    """Add --strict argument to reject lookalike characters."""
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: reject lookalike characters instead of normalizing them",
    )


def add_no_defaults_arg(parser: argparse.ArgumentParser) -> None:
    """Add --no-defaults argument to parser."""
    parser.add_argument(
        "--no-defaults", action="store_true", help="Don't include default values"
    )
