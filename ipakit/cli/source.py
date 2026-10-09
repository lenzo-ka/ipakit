"""Build and inspect managed tables from user-supplied source trees."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

from .base import NO_NOTATION, Command, CommandGroup, add_format_arg

if TYPE_CHECKING:
    from ..source_cache import SourceStatus


def _cache_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache",
        type=Path,
        help="Managed source-cache root (else IPAKIT_SOURCE_CACHE or the user cache)",
    )


def _short_revision(value: str | None) -> str:
    return "-" if value is None else f"{value[:8]}…"


def _status_text(item: SourceStatus) -> str:
    fields = [
        f"{item.provider:<8}{item.state:<14}",
        f"tag={item.expected_tag}",
        f"revision={_short_revision(item.observed_revision or item.expected_revision)}",
    ]
    if item.state == "stale-format":
        fields.extend(
            (f"format={item.observed_format}", f"required={item.expected_format}")
        )
    else:
        fields.append(f"format={item.observed_format or item.expected_format}")
    if item.built_at is not None:
        fields.append(f"built-at={item.built_at}")
    line = " ".join(fields)
    if item.detail:
        line += f"; {item.detail}"
    return line


class SourceStatusCommand(Command):
    """Report managed source state without fetching, building, or writing."""

    name = "status"
    aliases: ClassVar[list[str]] = []
    help = "Report managed source state without changing it"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "provider",
            nargs="?",
            choices=("all", "espeak"),
            default="all",
            help="Source provider to inspect (default: all)",
        )
        _cache_argument(parser)
        add_format_arg(parser)

    def run(self) -> int:
        from ..sources import status

        providers: tuple[Literal["espeak"], ...] = ("espeak",)
        results = [
            status(provider, cache_dir=self.args.cache) for provider in providers
        ]
        if self.format == "json":
            self.output_json(
                {
                    "complete": all(item.state == "ready" for item in results),
                    "results": [item.to_dict() for item in results],
                }
            )
        else:
            for item in results:
                self.print(_status_text(item))
        return 0


class SourceBuildCommand(Command):
    """Build managed tables offline from a pinned eSpeak NG source tree."""

    name = "build"
    aliases: ClassVar[list[str]] = []
    help = "Build managed tables from a local pinned source tree"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("provider", choices=("espeak",), help="Source provider")
        parser.add_argument(
            "--source",
            type=Path,
            help="Local source tree (else IPAKIT_ESPEAK_NG)",
        )
        _cache_argument(parser)
        add_format_arg(parser)

    def run(self) -> int:
        from ..sources import build, status

        built = build(
            self.args.provider,
            source=self.args.source,
            cache_dir=self.args.cache,
        )
        if self.format == "json":
            self.output_json(built)
        else:
            item = status(
                self.args.provider,
                source=self.args.source,
                cache_dir=self.args.cache,
            )
            self.print(_status_text(item))
        return 0


class SourceReceiptCommand(Command):
    """Print the validated receipt for a managed source build."""

    name = "receipt"
    aliases: ClassVar[list[str]] = []
    help = "Print a managed build receipt"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("provider", choices=("espeak",), help="Source provider")
        _cache_argument(parser)
        add_format_arg(parser)

    def run(self) -> int:
        from ..sources import receipt

        data = receipt(self.args.provider, cache_dir=self.args.cache)
        if self.format == "json":
            self.output_json(data)
        else:
            revision = data["source-policy"]["revision"]
            value = revision.get("commit", revision.get("sha256"))
            build = data["build"]
            self.print(
                "espeak "
                f"tag={revision['tag']} revision={value} "
                f"format={build['format']} built-at={build['built-at']} "
                f"fingerprint={data['fingerprint']}"
            )
        return 0


class SourceGroup(CommandGroup):
    """Build and inspect user-supplied source tables."""

    name = "source"
    aliases: ClassVar[list[str]] = []
    help = "Build and inspect user-supplied source tables"
    commands: ClassVar[list[type[Command]]] = [
        SourceStatusCommand,
        SourceBuildCommand,
        SourceReceiptCommand,
    ]
