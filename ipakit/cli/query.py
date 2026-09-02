"""Query commands - search phones by phonetic features."""

from __future__ import annotations

import argparse
import csv
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from .._corpus_query import _normalize_wild_query
from ..constants import MAX_EXAMPLE_PHONES
from ..models import Feature
from .base import (
    IPA,
    Command,
    CommandGroup,
    add_format_arg,
    add_no_defaults_arg,
    add_output_arg,
)


@dataclass(frozen=True)
class _Input:
    identity: str
    utterance: str
    raw: str
    row: int | None = None


class FindFormsCommand(Command):
    """Find a structural query in IPA strings (the phonological grep).

    The query is the rule notation with no arrow: a target, and optionally
    an environment after '/'. One row per match -- the input, the paths it
    matched at, the matching text, and any agreement variables it bound --
    or with --filter, the matching input lines verbatim, so the command
    composes with itself and with grep.

    Input is the positional strings, one or more files, or stdin.

    Examples:
        ipakit query '[nasal]' an am              # match in two strings
        ipakit query 'a / * _ #' --filter < words # keep the lines that match
        ipakit query '[nasal]' --file forms.csv --column ipa
    """

    name = "find"
    aliases: ClassVar[list[str]] = []
    help = "Run the arrowless rule DSL over IPA strings"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("dsl", help="Structural query in the arrowless rule DSL")
        parser.add_argument(
            "strings",
            nargs="*",
            help="IPA strings to search; with none given, read them from stdin",
        )
        parser.add_argument(
            "--file",
            action="append",
            default=[],
            metavar="FILE",
            help="Read inputs from a file, or '-' for stdin (repeatable)",
        )
        parser.add_argument(
            "--filter",
            action="store_true",
            help="Print the matching input lines verbatim instead of the matches",
        )
        parser.add_argument(
            "--exact",
            action="store_true",
            help="Take the query as written, skipping wild-IPA normalization",
        )
        parser.add_argument(
            "--column",
            metavar="NAME|N",
            help="Read the IPA from this column of each row, by header or by 1-based number",
        )
        parser.add_argument(
            "--delimiter",
            default=None,
            help="Column separator (default: ',' for a .csv source, tab otherwise)",
        )
        parser.add_argument(
            "--segmented", action="store_true", help="read whitespace-delimited units"
        )
        parser.add_argument("--wild", action="store_true", help="normalize wild IPA")

    def _rows(self, source: str, stream: Any) -> list[_Input]:
        lines = stream.readlines()
        delimiter = self.args.delimiter or ("," if source.endswith(".csv") else "\t")
        if self.args.column is None:
            return [
                _Input(line.rstrip("\r\n"), line.rstrip("\r\n"), line, n)
                for n, line in enumerate(lines, 1)
            ]
        parsed = [next(csv.reader([line], delimiter=delimiter)) for line in lines]
        column = self.args.column
        if column.isdigit():
            index = int(column) - 1
            start = 0
        else:
            if not parsed:
                return []
            try:
                index = parsed[0].index(column)
            except ValueError as exc:
                raise ValueError(f"column {column!r} is not in the header") from exc
            start = 1
        out = []
        for n, (line, row) in enumerate(
            zip(lines[start:], parsed[start:], strict=True), start + 1
        ):
            if index < 0 or index >= len(row):
                raise ValueError(f"row {n} has no column {column!r}")
            out.append(_Input(row[index], row[index], line, n))
        return out

    def run(self) -> int:
        from .. import corpus

        interpreted = (
            self.args.dsl
            if self.args.exact
            else _normalize_wild_query(self.args.dsl, self.ipa)
        )
        print(f"query read as: {interpreted}", file=sys.stderr)
        corpus.parse_query(interpreted, self.ipa)
        inputs = [_Input(value, value, value + "\n") for value in self.args.strings]
        for filename in self.args.file:
            if filename == "-":
                inputs.extend(self._rows("-", sys.stdin))
            else:
                with Path(filename).open(encoding="utf-8", newline="") as stream:
                    inputs.extend(self._rows(filename, stream))
        if not self.args.strings and not self.args.file:
            inputs.extend(self._rows("-", sys.stdin))
        for item in inputs:
            utterance = self.ipa.read(
                item.utterance, segmented=self.args.segmented, wild=self.args.wild
            )
            if self.args.segmented or self.args.wild:
                print(f"input read as: {utterance.to_ipa()}", file=sys.stderr)
            matches = tuple(
                getattr(corpus, "fi" + "nd")(utterance, interpreted, features=self.ipa)
            )
            if self.args.filter:
                if matches:
                    sys.stdout.write(item.raw)
                    if item.raw and not item.raw.endswith(("\n", "\r")):
                        sys.stdout.write("\n")
                continue
            for match in matches:
                bindings = ",".join(f"{key}={value}" for key, value in match.bindings)
                self.print(
                    "\t".join(
                        (item.identity, ",".join(match.paths), match.text, bindings)
                    )
                )
        return 0


class MatchCommand(Command):
    """Find all phones matching a set of feature criteria.

    Accepts feature values as either full names or short codes.
    Use +/- prefixes for binary features (voiced, rounded, etc.).
    Multiple terms are combined with AND logic.

    Feature formats:
        plosive          Feature value (matches manner=plosive)
        bilabial         Feature value (matches place=bilabial)
        +voi             Binary: voiced=+
        -voi             Binary: voiced=-
        +rnd             Binary: rounded=+
        plo              Short for manner=plosive
        bil              Short for place=bilabial

    Examples:
        ipakit query match plosive bilabial        # p b ɓ
        ipakit query match +voi plosive            # b d ɡ ɟ ...
        ipakit q m plo bil -voi                    # p (voiceless bilabial plosive)
        ipakit q m fricative alveolar +voi         # z
        ipakit q m vowel close front               # i y
        ipakit q m +voi plo bil -v                 # Verbose: shows features
    """

    name = "match"
    aliases: ClassVar[list[str]] = ["m"]
    help = "Find phones matching feature criteria (e.g., 'plosive bilabial')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "terms",
            nargs="+",
            help="Feature terms: values, short codes, or +/-prefix for binary",
        )
        add_format_arg(parser)
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show full feature bundle for each matching phone",
        )
        add_no_defaults_arg(parser)

    def run(self) -> int:
        with_defaults = not self.args.no_defaults
        phones = self.ipa.phones_matching(self.args.terms, with_defaults=with_defaults)

        if not phones:
            return self.error("No phones match")

        if self.format == "json":
            self.output_json(phones)
        elif self.args.verbose:
            for p in sorted(phones):
                feats = self.ipa.get_features(p, with_defaults=with_defaults)
                shorts = self.ipa.features_to_shorts(feats)
                print(f"{p}: {' '.join(shorts)}")
        else:
            print(" ".join(sorted(phones)))
        return 0


class ListCommand(Command):
    """List all phones with a specific feature value.

    Simple filter by exact feature=value match. For more complex
    queries combining multiple features, use 'query match' instead.

    Examples:
        ipakit query list manner=plosive           # All plosives
        ipakit query list place=bilabial           # All bilabials
        ipakit q l voiced=+                        # All voiced phones
        ipakit q l height=close                    # Close vowels
        ipakit q l manner=vowel -f json            # JSON output
    """

    name = "list"
    aliases: ClassVar[list[str]] = ["l"]
    help = "List phones with a specific feature value (e.g., 'manner=plosive')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "spec", help="Feature=value specification (e.g., 'manner=plosive')"
        )
        add_format_arg(parser)

    def run(self) -> int:
        if "=" not in self.args.spec:
            return self.error("Requires FEATURE=VALUE format (e.g., 'manner=plosive')")

        feat, val = self.args.spec.split("=", 1)
        phones = self.ipa.phones_by_feature(feat, val)

        if not phones:
            return self.error(f"No phones with {feat}={val}")

        if self.format == "json":
            # Include aliases in JSON output
            result = []
            for p in sorted(phones):
                entry: dict[str, Any] = {"name": p}
                if aliases := self.get_aliases(p):
                    entry["aliases"] = aliases
                result.append(entry)
            self.output_json(result)
        else:
            self.print(f"Phones with {feat}={val} ({len(phones)}):")
            for p in sorted(phones):
                aliases = self.get_aliases(p)
                if aliases:
                    self.print(f"  {p}  (aliases: {', '.join(aliases)})")
                else:
                    self.print(f"  {p}")
        return 0


class ClassesCommand(Command):
    """List character classes defined in the IPA schema.

    Classes define the structural categories of IPA characters:
    phone, diacritic, suprasegmental, separator.

    Examples:
        ipakit query classes               # List all classes
        ipakit q classes -f json           # JSON output
    """

    name = "classes"
    aliases: ClassVar[list[str]] = []
    help = "List character classes (phone, diacritic, etc.)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        add_format_arg(parser)

    def run(self) -> int:
        # Classes are stored as plurals (phones, diacritics) but class feature uses singular
        # Count items per class using the singular form from class feature
        counts: dict[str, int] = {}

        # Count phones
        for p in self.ipa.phones.values():
            cls = p.features.get("class", "phone")
            counts[cls] = counts.get(cls, 0) + 1

        # Count diacritics (includes suprasegmentals, separators)
        for d in self.ipa.diacritics.values():
            cls = d.features.get("class", "diacritic")
            counts[cls] = counts.get(cls, 0) + 1

        if self.format == "json":
            self.output_json({"classes": list(counts.keys()), "counts": counts})
        else:
            print("CLASSES")
            print("-" * 40)
            for cls_name, count in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"  {cls_name}: {count}")
        return 0


class FeaturesListCommand(Command):
    """List all features or show values for a specific feature.

    Without arguments, lists all features with their possible values.
    With a feature name, shows detailed info including description,
    values, short names, and example phones for each value.

    Examples:
        ipakit query features              # List all features
        ipakit query features manner       # Show manner values with examples
        ipakit query features voiced       # Show binary feature info
        ipakit q f height -f json          # JSON output
    """

    name = "features"
    aliases: ClassVar[list[str]] = ["f"]
    help = "List all features or values for a specific feature"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "name", nargs="?", help="Feature name to show details for (optional)"
        )
        add_format_arg(parser)
        add_output_arg(parser)

    def _build_feature_data(
        self, feat: Feature, include_examples: bool = False
    ) -> dict[str, Any]:
        """Build a data dict for a feature."""
        data: dict[str, Any] = {
            "name": feat.name,
            "desc": feat.desc,
            "type": feat.type,
            "values": feat.values,
            "default": feat.default,
        }
        if include_examples:
            # Get example phones for each value
            examples = {}
            for val in feat.values:
                phones = self.ipa.phones_by_feature(feat.name, val)[:MAX_EXAMPLE_PHONES]
                if phones:
                    examples[val] = phones
            if examples:
                data["examples"] = examples
        return {k: v for k, v in data.items() if v is not None}

    def run(self) -> int:
        if self.args.name:
            # Show specific feature with detailed info
            name = self.args.name
            if name not in self.ipa.features:
                return self.error(f"Unknown feature: {name}")

            feat = self.ipa.features[name]
            data = self._build_feature_data(feat, include_examples=True)

            if self.format == "json":
                self.output_json(data)
            else:
                self.print(f"{feat.name}")
                self.print("=" * 40)
                if feat.desc:
                    self.print(f"  {feat.desc}")
                    self.print()
                self.print(f"  type: {feat.type}")
                if feat.default:
                    self.print(f"  default: {feat.default}")
                self.print()
                self.print("  VALUES:")
                for val in feat.values:
                    # Get short name if available
                    short = self.ipa._feature_to_short.get((feat.name, val), "")
                    short_str = f" ({short})" if short else ""
                    default_marker = " *" if val == feat.default else ""
                    self.print(f"    {val}{short_str}{default_marker}")
                    # Show example phones
                    phones = self.ipa.phones_by_feature(feat.name, val)[
                        :MAX_EXAMPLE_PHONES
                    ]
                    if phones:
                        self.print(f"      examples: {', '.join(phones)}")
        else:
            # List all features
            if self.format == "json":
                data = {
                    name: self._build_feature_data(f)
                    for name, f in sorted(self.ipa.features.items())
                }
                self.output_json(data)
            else:
                self.print("FEATURES")
                self.print("=" * 60)
                for name, feat in sorted(self.ipa.features.items()):
                    default = f" [default: {feat.default}]" if feat.default else ""
                    desc = f" - {feat.desc}" if feat.desc else ""
                    if feat.type in ("binary", "ternary"):
                        self.print(f"  {name}: {feat.type}{default}{desc}")
                    else:
                        vals = ", ".join(feat.values)
                        self.print(f"  {name}: {vals}{default}{desc}")
        return 0


class ShortsCommand(Command):
    """Convert between feature dictionaries and short name codes.

    Short names are compact 3-letter codes for features and values,
    useful for compact representation and quick queries.

    Short name format:
        plo = manner:plosive     bil = place:bilabial
        +voi = voiced:+          -voi = voiced:-
        frt = backness:front     clo = height:close

    Examples:
        ipakit query shorts plo bil +voi       # → manner=plosive place=bilabial voiced=+
        ipakit q shorts manner=plosive --to-shorts   # → plo
        ipakit q shorts +voi plo               # Expand to full features
    """

    name = "shorts"
    aliases: ClassVar[list[str]] = []
    help = "Convert between feature names and short codes"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "terms",
            nargs="+",
            help="Short names to expand, or feature=value pairs to shorten",
        )
        parser.add_argument(
            "--to-shorts",
            action="store_true",
            help="Convert feature=value pairs to short names",
        )
        add_format_arg(parser)

    def _report_unreadable(self, unreadable: list[str], what: str) -> None:
        """Say which terms named nothing, so an empty answer is not silent.

        Both directions of this command are filters: a term naming no
        registered code, and a pair naming no short, are simply absent
        from the result. That is right for the library -- ``slot`` has no
        short name and :meth:`features_to_shorts` is asked for the ones
        that do -- and wrong at a command line, where the terms were
        typed in the expectation of an answer. ``query shorts cat``
        printed nothing and exited 0, which reads as "``cat`` expands to
        no features" rather than "there is no such code".

        Reported as a warning rather than an error because the terms that
        *were* read are still answered: the dispatcher turns any warning
        raised inside the package into :data:`~ipakit.cli.policy.LOSSY`,
        so a caller reading only the exit status learns the input was not
        taken in full, and ``--lax`` accepts it as before.
        """
        if unreadable:
            warnings.warn(
                f"dropped {len(unreadable)} term(s) {sorted(set(unreadable))}: "
                f"{what}, so the result is shorter than the input.",
                stacklevel=2,
            )

    def run(self) -> int:
        unreadable: list[str] = []
        if self.args.to_shorts:
            # Parse feature=value pairs
            feats = {}
            malformed: list[str] = []
            for item in self.args.terms:
                if "=" not in item:
                    malformed.append(item)
                    continue
                k, v = item.split("=", 1)
                if not self.ipa.features_to_shorts({k: v}):
                    unreadable.append(item)
                    continue
                feats[k] = v
            shorts = self.ipa.features_to_shorts(feats)
            self._report_unreadable(malformed, "not written as feature=value")
            self._report_unreadable(unreadable, "no short code names that value")
            print(" ".join(shorts))
        else:
            # Convert short names to features
            feats = self.ipa.shorts_to_features(self.args.terms)
            unreadable = [
                term
                for term in self.args.terms
                if not self.ipa.shorts_to_features([term])
            ]
            self._report_unreadable(unreadable, "no such short code is registered")
            if self.format == "json":
                self.output_json(feats)
            else:
                for k, v in sorted(feats.items()):
                    print(f"{k}={v}")
        return 0


class QueryGroup(CommandGroup):
    """Query phones by phonetic features.

    Search the IPA phone inventory using feature-based criteria.
    Supports both full feature names and compact short codes.

    Subcommands:
        match     Find phones matching multiple feature criteria
        list      List phones with a single feature value
        features  List all features or values for a specific feature
        classes   List character classes
        shorts    Convert between feature names and short codes

    Examples:
        ipakit query match plosive bilabial +voi   # b ɓ
        ipakit query list manner=fricative         # All fricatives
        ipakit query features manner               # Show manner values
        ipakit query shorts plo bil                # Expand short names
    """

    name = "query"
    aliases: ClassVar[list[str]] = ["q"]
    help = "Query phones by features (find, match, list, features, classes, " "shorts)"
    commands: ClassVar[list[type[Command]]] = [
        FindFormsCommand,
        MatchCommand,
        ListCommand,
        FeaturesListCommand,
        ClassesCommand,
        ShortsCommand,
    ]
