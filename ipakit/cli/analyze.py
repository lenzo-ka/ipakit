"""Analyze commands - analysis, validation, and statistics."""

from __future__ import annotations

import argparse

from .base import Command, CommandGroup, add_format_arg, add_no_defaults_arg


class ValidateCommand(Command):
    """Validate the IPA XML definition file.

    Checks for:
    - Undeclared features used by phones
    - Invalid feature values
    - Missing required features (e.g., place for consonants)
    - Missing height/backness for vowels

    Exit code: 0 if valid, 1 if errors found.

    Examples:
        ipakit analyze validate            # Check bundled ipa.xml
        ipakit analyze validate -f json    # JSON result with error list
        ipakit a v --ipa-xml custom.xml    # Validate custom file
    """

    name = "validate"
    aliases = ["v"]
    help = "Validate IPA XML file for consistency errors"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        errors = self.ipa.validate()

        if self.format == "json":
            self.output_json({"valid": len(errors) == 0, "errors": errors})
            return 0 if not errors else 1

        if errors:
            print(f"INVALID: {len(errors)} error(s):")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("VALID")
        return 0


class SummaryCommand(Command):
    """Show summary statistics about the IPA inventory.

    Displays:
    - Total counts (phones, diacritics, features)
    - Manner distribution (plosive, fricative, vowel, etc.)
    - Feature usage (how many phones specify each feature)

    Examples:
        ipakit analyze summary             # Human-readable summary
        ipakit analyze summary -f json     # JSON for processing
        ipakit a s                          # Short form
    """

    name = "summary"
    aliases = ["s"]
    help = "Summary statistics (counts, distributions)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        s = self.ipa.summary()

        if self.format == "json":
            self.output_json(s)
            return 0

        print("SUMMARY")
        print("=" * 60)
        print(f"Phones: {s['n_phones']}")
        print(f"Diacritics: {s['n_diacritics']}")
        print(f"Features: {s['n_features']}")
        print()

        print("MANNER DISTRIBUTION")
        print("-" * 40)
        for manner, count in sorted(
            s["manner_distribution"].items(), key=lambda x: -x[1]
        ):
            print(f"  {manner}: {count}")
        print()

        print("FEATURE USAGE")
        print("-" * 40)
        for feat, count in sorted(s["feature_usage"].items(), key=lambda x: -x[1]):
            default = self.ipa.features[feat].default
            suffix = f" [default: {default}]" if default else ""
            print(f"  {feat}: {count}{suffix}")
        return 0


class CountsCommand(Command):
    """Show detailed feature value counts.

    For each feature, shows how many phones have each value.
    Useful for understanding the distribution of phonetic
    properties in the inventory.

    Examples:
        ipakit analyze counts              # All feature counts
        ipakit analyze counts -f json      # JSON format
        ipakit a c                          # Short form
    """

    name = "counts"
    aliases = ["c"]
    help = "Detailed feature value counts"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        counts = self.ipa.feature_counts()
        usage = self.ipa.feature_usage()

        if self.format == "json":
            self.output_json({"counts": counts, "usage": usage})
            return 0

        print("FEATURE VALUE COUNTS")
        print("=" * 60)

        for feat_name in sorted(self.ipa.features.keys()):
            feat = self.ipa.features[feat_name]
            n = usage.get(feat_name, 0)
            suffix = f" (default: {feat.default})" if feat.default else ""
            print(f"\n{feat_name}: {n} phones{suffix}")

            if feat_name in counts and counts[feat_name]:
                for value, count in sorted(
                    counts[feat_name].items(), key=lambda x: -x[1]
                ):
                    print(f"  {value}: {count}")
            else:
                print("  (not used)")
        return 0


class PhonesCommand(Command):
    """List all phones with their feature values.

    Outputs the complete phone inventory with all features.
    Multiple formats available for different use cases:
    - text: Human-readable with defaults marked
    - tsv/csv: For spreadsheet import
    - json: For programmatic processing

    Examples:
        ipakit analyze phones               # Readable list
        ipakit analyze phones -f tsv        # Tab-separated
        ipakit analyze phones -f csv        # Comma-separated
        ipakit analyze phones -f json       # JSON dict
        ipakit a p --no-defaults            # Only explicit features
    """

    name = "phones"
    aliases = ["p"]
    help = "List all phones with features (text, tsv, csv, json)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser, ["text", "tsv", "csv", "json"])
        add_no_defaults_arg(parser)

    def run(self) -> int:
        with_defaults = not self.args.no_defaults

        if self.format == "json":
            data = {
                symbol: self.ipa.get_features(symbol, with_defaults=with_defaults)
                for symbol in sorted(self.ipa.phones.keys())
            }
            self.output_json(data)
            return 0

        feat_names = sorted(self.ipa.features.keys())

        if self.format == "tsv":
            print("phone\t" + "\t".join(feat_names))
            for symbol in sorted(self.ipa.phones.keys()):
                feats = self.ipa.get_features(symbol, with_defaults=with_defaults)
                values = [feats.get(f, "") for f in feat_names]
                print(f"{symbol}\t" + "\t".join(values))

        elif self.format == "csv":
            print("phone," + ",".join(feat_names))
            for symbol in sorted(self.ipa.phones.keys()):
                feats = self.ipa.get_features(symbol, with_defaults=with_defaults)
                values = [feats.get(f, "") for f in feat_names]
                print(f"{symbol}," + ",".join(values))

        else:
            for symbol in sorted(self.ipa.phones.keys()):
                feats = self.ipa.get_features(symbol, with_defaults=with_defaults)
                print(f"\n{symbol}:")
                for f in feat_names:
                    if val := feats.get(f):
                        is_default = (
                            f not in self.ipa.phones[symbol].features
                            and self.ipa.features[f].default == val
                        )
                        suffix = " (default)" if is_default else ""
                        print(f"  {f}: {val}{suffix}")
        return 0


class DiacriticsCommand(Command):
    """List all diacritics with their feature modifications.

    Diacritics modify base phones by adding or changing features
    (e.g., aspiration, nasalization, palatalization).

    Examples:
        ipakit analyze diacritics          # List all diacritics
        ipakit analyze diacritics -f json  # JSON format
        ipakit a d                          # Short form
    """

    name = "diacritics"
    aliases = ["d"]
    help = "List all diacritics with feature modifications"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)

    def run(self) -> int:
        if self.format == "json":
            data = {
                symbol: d.features for symbol, d in sorted(self.ipa.diacritics.items())
            }
            self.output_json(data)
            return 0

        print("DIACRITICS")
        print("=" * 60)
        for symbol, diac in sorted(self.ipa.diacritics.items()):
            feats = ", ".join(
                f"{k}={v}" for k, v in sorted(diac.features.items()) if k != "class"
            )
            print(f"  {symbol}: {feats}")
        return 0


class ReportCommand(Command):
    """Generate a comprehensive analysis report.

    Combines multiple analyses into a single report:
    - Summary statistics
    - Feature definitions
    - Manner distribution
    - Validation results
    - Sample distance calculations

    Examples:
        ipakit analyze report              # Full report to stdout
        ipakit analyze report > report.txt # Save to file
        ipakit a r                          # Short form
    """

    name = "report"
    aliases = ["r"]
    help = "Full analysis report (summary, validation, samples)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

    def run(self) -> int:
        print("=" * 70)
        print("IPA FEATURES ANALYSIS REPORT")
        print("=" * 70)
        print()

        s = self.ipa.summary()
        print(f"Phones: {s['n_phones']}")
        print(f"Diacritics: {s['n_diacritics']}")
        print(f"Features: {s['n_features']}")
        print()

        print("FEATURE DEFINITIONS")
        print("-" * 40)
        for name, feat in sorted(self.ipa.features.items()):
            suffix = f" (default: {feat.default})" if feat.default else ""
            if feat.type in ("binary", "ternary"):
                print(f"  {name}: {feat.type}{suffix}")
            else:
                print(f"  {name}: {feat.values}{suffix}")
        print()

        print("MANNER DISTRIBUTION")
        print("-" * 40)
        for manner, count in sorted(
            s["manner_distribution"].items(), key=lambda x: -x[1]
        ):
            print(f"  {manner}: {count}")
        print()

        print("VALIDATION")
        print("-" * 40)
        errors = self.ipa.validate()
        if errors:
            print(f"INVALID: {len(errors)} error(s):")
            for err in errors:
                print(f"  - {err}")
        else:
            print("VALID")
        print()

        print("SAMPLE DISTANCES")
        print("-" * 40)
        pairs = [("p", "b"), ("p", "t"), ("t", "d"), ("a", "i"), ("i", "u"), ("s", "z")]
        for p1, p2 in pairs:
            if p1 in self.ipa and p2 in self.ipa:
                d = self.ipa.distance(p1, p2)
                print(f"  {p1} - {p2}: {d:.3f}")

        return 0


class AnalyzeGroup(CommandGroup):
    """Analyze and validate IPA feature data.

    Tools for inspecting the IPA inventory, validating data
    consistency, and generating statistics.

    Subcommands:
        validate    Check XML for errors
        summary     Overview statistics
        counts      Feature value distributions
        phones      List all phones with features
        diacritics  List all diacritics
        report      Comprehensive analysis report

    Examples:
        ipakit analyze validate           # Check for errors
        ipakit analyze summary            # Quick overview
        ipakit analyze report             # Full report
    """

    name = "analyze"
    aliases = ["a"]
    help = "Analyze and validate (validate, summary, counts, phones, report)"
    commands = [
        ValidateCommand,
        SummaryCommand,
        CountsCommand,
        PhonesCommand,
        DiacriticsCommand,
        ReportCommand,
    ]
