"""Query commands - search phones by phonetic features."""

from __future__ import annotations

import argparse
from typing import Any

from ..constants import MAX_EXAMPLE_PHONES
from ..models import Feature
from .base import (
    Command,
    CommandGroup,
    add_format_arg,
    add_no_defaults_arg,
    add_output_arg,
)


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
    aliases = ["m"]
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
    aliases = ["l"]
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
    aliases = []
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
    aliases = ["f"]
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
        ipakit q shorts manner=plosive -s      # → plo
        ipakit q shorts +voi plo               # Expand to full features
    """

    name = "shorts"
    aliases = []
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
            "-s",
            action="store_true",
            help="Convert feature=value pairs to short names",
        )
        add_format_arg(parser)

    def run(self) -> int:
        if self.args.to_shorts:
            # Parse feature=value pairs
            feats = {}
            for item in self.args.terms:
                if "=" in item:
                    k, v = item.split("=", 1)
                    feats[k] = v
            shorts = self.ipa.features_to_shorts(feats)
            print(" ".join(shorts))
        else:
            # Convert short names to features
            feats = self.ipa.shorts_to_features(self.args.terms)
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
    aliases = ["q"]
    help = "Query phones by features (match, list, features, classes, shorts)"
    commands = [
        MatchCommand,
        ListCommand,
        FeaturesListCommand,
        ClassesCommand,
        ShortsCommand,
    ]
