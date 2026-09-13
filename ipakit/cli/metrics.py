"""Named metric discovery and explicit-token comparison commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Command, add_format_arg, add_output_arg

if TYPE_CHECKING:
    from ..distance_registry import DistanceRegistry


def _registry(args: argparse.Namespace) -> DistanceRegistry:
    from ..distance_registry import DistanceRegistry, builtin_registry, ternary_metric
    from ..finite_declaration import read_ternary_declaration

    if args.ipa_xml is not None or args.cmu_xml is not None:
        raise ValueError(
            "named metrics use explicit registrations; select a custom table "
            "with --metric-declaration NAME=PATH"
        )
    registry = builtin_registry()
    for selection in args.metric_declaration or ():
        name, separator, path = selection.partition("=")
        if not separator or not name or not path:
            raise ValueError("--metric-declaration requires NAME=PATH")
        registry = DistanceRegistry(
            (
                *registry.registrations,
                ternary_metric(name, read_ternary_declaration(Path(path))),
            )
        )
    return registry


def _selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--metric-declaration",
        action="append",
        metavar="NAME=PATH",
        help="Register a custom ternary table with symmetric-difference costs; repeatable",
    )
    add_format_arg(parser)
    add_output_arg(parser)


class MetricsCommand(Command):
    """List names available for explicit metric selection.

    Include supplied ternary tables with --metric-declaration NAME=PATH.
    Discovery lists registrations; comparison reports their availability.
    """

    name = "metrics"
    help = "List registered distance metric names"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)

    def run(self) -> int:
        names = _registry(self.args).names
        if self.format == "json":
            self.output_json(names)
        else:
            self.output_lines(list(names))
        return 0


class AcrossCommand(Command):
    """Compare a JSON corpus of exact token arrays under named metrics.

    Repeat --metric NAME to select an ordered list, or use --metric all.
    --all-pairs independently selects every ordered pair of corpus positions.
    The report retains unavailable metrics and per-input refusals.
    """

    name = "across"
    help = "Compare exact token sequences under selected named metrics"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument(
            "--tokens-json",
            type=Path,
            required=True,
            help="JSON file containing at least two arrays of exact token strings",
        )
        parser.add_argument(
            "--metric",
            action="append",
            metavar="NAME",
            help="Select a metric; repeatable, or use all alone (default: all)",
        )
        parser.add_argument(
            "--all-pairs",
            action="store_true",
            help="Compare every ordered pair of distinct corpus positions; quadratic output",
        )

    def run(self) -> int:
        registry = _registry(self.args)
        names = self.args.metric or ["all"]
        selection = "all" if names == ["all"] else names
        corpus = json.loads(self.args.tokens_json.read_text(encoding="utf-8"))
        report = registry.compare_corpus(
            corpus,
            metrics=selection,
            all_pairs=self.args.all_pairs,
        )
        # This report preserves unavailable metrics and per-pair refusals in
        # every format. Exit0 means the requested report was produced.
        if self.format == "json":
            self.output_json(report)
        else:
            self.print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
