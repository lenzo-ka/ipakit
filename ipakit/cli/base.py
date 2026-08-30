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
from .policy import LOSSY

if TYPE_CHECKING:
    from ..features import IPAFeatures
    from ..mapper import CMUMapper


#: Said on every command that reads IPA text from the command line.
#:
#: Every ASCII letter is a registered phone, so ``cat`` parses as the three
#: phones ``c a t`` and is answered as confidently as ``kæt`` is. Nothing in
#: the reader can tell an orthographic word from a real transcription --
#: ``kat`` is genuine IPA and is used throughout the test corpus -- so the
#: hazard is documented at the point of use rather than guessed at. The
#: ``--lax``/exit-3 policy does not fire here: it reports symbols that could
#: not be read, and these were all read.
#:
#: Written once and attached by :func:`register_command`, so a command that
#: declares ``reads_ipa`` cannot be missing the note.
ORTHOGRAPHY_NOTE = """
Input is IPA transcription, not orthography. Every ASCII letter is a
registered phone, so a word written in spelling -- 'cat', 'pin' -- is read
as the phones it spells and answered confidently rather than refused.
"""


class Command(ABC):
    """Base class for CLI commands."""

    name: str  # Subcommand name
    aliases: list[str] = []  # Short aliases
    help: str  # Help text

    #: True where the command reads IPA text from the command line.
    #:
    #: The only consumer is :func:`register_command`, which attaches
    #: :data:`ORTHOGRAPHY_NOTE` to the command's help. It is a declaration
    #: rather than something inferred from the argument list because an
    #: argument's name says nothing about the notation it carries:
    #: ``convert from-xsampa`` takes a transcription too, and it is not IPA.
    reads_ipa: bool = False

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

    #: Keys that precede the phonetic features, in the order they print.
    #: They are display metadata about the entry, not values of declared
    #: features -- ``feature_order`` holds none of them, so a key not
    #: listed here is dropped by :meth:`order_features` rather than
    #: printed at the end. Named once, so adding one is a single edit.
    METADATA_KEYS = ("name", "aliases", "class", "composed")

    def order_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """Order a feature dict for display.

        :data:`METADATA_KEYS` first, in that order, then the phonetic
        features in the order the data declares them.
        """
        ordered = {k: features[k] for k in self.METADATA_KEYS if k in features}
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


def register_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    cmd_cls: type[Command],
) -> argparse.ArgumentParser:
    """Register one leaf command under ``subparsers``.

    The one place a leaf is built, whether it hangs off the top level
    (:func:`ipakit.cli.create_parser`) or off a group
    (:meth:`CommandGroup.register`). It used to be written out in both, and
    ``add_lax_arg`` standing in both copies was the evidence: a flag every
    leaf is supposed to accept had already been added twice. The next one
    would have reached one family of commands and not the other.

    Three things every leaf gets, in this order:

    * the class docstring as the parser description, so ``--help`` says what
      the command is rather than only what it is called;
    * whatever :meth:`Command.add_arguments` adds, which may overwrite the
      description with the same docstring;
    * :data:`ORTHOGRAPHY_NOTE`, where the command declares ``reads_ipa`` --
      after ``add_arguments``, so it survives that overwrite.
    """
    parser = subparsers.add_parser(
        cmd_cls.name,
        aliases=cmd_cls.aliases,
        help=cmd_cls.help,
    )
    parser.description = cmd_cls.__doc__
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    cmd_cls.add_arguments(parser)
    if cmd_cls.reads_ipa:
        parser.description = (
            (parser.description or "").rstrip() + "\n" + ORTHOGRAPHY_NOTE
        )
    add_lax_arg(parser)
    parser.set_defaults(cmd_cls=cmd_cls)
    return parser


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
            register_command(group_sub, cmd_cls)


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
    """Add the soft-read opt-out flag (``features`` command).

    ``features`` is an interactive lookup, so it soft-reads ASCII
    stand-ins (``g``, ``:``, ``?``, ``'``) by default -- the one surface
    that does; the library parse path never does. ``--no-lookalikes``
    turns that off. Distinct from the converter ``--strict`` (see
    ``add_convert_strict_arg``), which is about unconvertible symbols.
    """
    parser.add_argument(
        "--no-lookalikes",
        dest="strict",
        action="store_true",
        help="Read ASCII stand-ins literally instead of as IPA (g : ? ')",
    )


def add_convert_strict_arg(parser: argparse.ArgumentParser) -> None:
    """Add the converter ``--strict`` flag (fail on unconvertible symbols)."""
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Raise an error on symbols that cannot be converted (default: skip)",
    )


def add_no_defaults_arg(parser: argparse.ArgumentParser) -> None:
    """Add --no-defaults argument to parser."""
    parser.add_argument(
        "--no-defaults", action="store_true", help="Don't include default values"
    )


def add_lax_arg(parser: argparse.ArgumentParser, *, top_level: bool = False) -> None:
    """Add the opt-out from the lossy-input exit status (see :mod:`.policy`).

    Deliberately **not** spelled ``--strict``. Two subcommands already
    write that word with two different meanings -- the converters (fail
    on symbols they cannot convert) and ``analysis validate`` (warnings
    are errors) -- and a third sense at the top level is the failure this
    repo has fixed twice already: one name, several declarations,
    agreeing only by habit. ``--lax`` names the one policy it turns off.

    Accepted both before the subcommand and on the subcommand itself,
    because a reader of the hint on stderr will type it wherever it
    falls naturally. The leaf copy defaults to ``SUPPRESS`` so it only
    *adds* to the namespace when written: an ordinary ``store_true``
    default on a subparser overwrites whatever the top-level parser put
    there, which would make ``ipakit --lax rules apply`` quietly inert.
    """
    parser.add_argument(
        "--lax",
        action="store_true",
        default=False if top_level else argparse.SUPPRESS,
        help=(f"Exit 0 instead of {LOSSY} when part of the input could not be read"),
    )
