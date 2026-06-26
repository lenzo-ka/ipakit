"""Analysis commands - describe, natural-class, minimal-pairs."""

from __future__ import annotations

import argparse

from .base import Command, CommandGroup, add_format_arg, add_no_defaults_arg


class DescribeCommand(Command):
    """Generate human-readable IPA description for a phone.

    Produces standard phonetic terminology like "voiceless bilabial plosive"
    for consonants or "open-mid front unrounded vowel" for vowels.

    Examples:
        ipakit describe p              # voiceless bilabial plosive
        ipakit describe ɛ              # open-mid front unrounded vowel
        ipakit describe t͡ʃ             # voiceless postalveolar affricate
        ipakit describe l              # voiced lateral alveolar approximant
        ipakit desc ŋ                  # voiced velar nasal
    """

    name = "describe"
    aliases = ["desc"]
    help = (
        "Generate human-readable description (e.g., 'p' → 'voiceless bilabial plosive')"
    )

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phone", help="IPA phone symbol to describe")
        add_format_arg(parser)

    def run(self) -> int:
        phone = self.ipa.expand_ligatures(self.args.phone)
        description = self.ipa.describe(phone)

        if self.format == "json":
            self.output_json({"phone": phone, "description": description})
        else:
            print(description)
        return 0


class NaturalClassCommand(Command):
    """Find features shared by all phones in a set (natural class).

    In phonology, a natural class is a set of phones that share certain
    phonetic features. This command finds the intersection of features
    that unify the given phones.

    By default every shared feature (including defaults) is shown; use
    --no-defaults to see only the explicitly-set ones, as below.

    Examples:
        ipakit analysis natural-class p t k --no-defaults  # manner=plosive
        ipakit an natural-class b d ɡ --no-defaults        # manner=plosive voiced=+
        ipakit an natural-class i e ɛ --no-defaults        # backness=front manner=vowel
        ipakit an nc m n ŋ --no-defaults                   # manner=nasal voiced=+
        ipakit an nc p t k -f json                         # JSON output
    """

    name = "natural-class"
    aliases = ["nc"]
    help = (
        "Find features shared by a set of phones (e.g., 'p t k' → plosive, voiceless)"
    )

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phones", nargs="+", help="IPA phone symbols to analyze")
        add_format_arg(parser)
        add_no_defaults_arg(parser)

    def run(self) -> int:
        phones = [self.ipa.expand_ligatures(p) for p in self.args.phones]
        with_defaults = not self.args.no_defaults

        shared = self.ipa.natural_class(phones, with_defaults=with_defaults)

        if not shared:
            return self.error("No shared features found")

        if self.format == "json":
            self.output_json({"phones": phones, "shared_features": shared})
        else:
            for feat, val in sorted(shared.items()):
                print(f"{feat}={val}")
        return 0


class MinimalPairsCommand(Command):
    """Find phones that differ by approximately one feature (minimal pairs).

    Minimal pairs are phones that differ in only one phonetic feature.
    This is useful for understanding phonological contrasts and for
    language teaching (learners confuse similar sounds).

    Examples:
        ipakit analysis minimal-pairs p    # ɸ, f, p͡f (manner)...
        ipakit an minimal-pairs i          # e, e͡ə (height)...
        ipakit an mp s                     # ɧ, ʃ, θ (place)...
        ipakit an mp p -f json             # JSON output
        ipakit an mp p --max-distance 0.5  # Include more distant phones
    """

    name = "minimal-pairs"
    aliases = ["mp"]
    help = "Find phones differing by ~one feature (e.g., 'p' → 'ɸ', 'f', 't'...)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phone", help="Reference IPA phone symbol")
        parser.add_argument(
            "--max-distance",
            "-d",
            type=float,
            default=0.3,
            help="Maximum phonetic distance (default: 0.3 ≈ 1-2 features)",
        )
        add_format_arg(parser)

    def run(self) -> int:
        phone = self.ipa.expand_ligatures(self.args.phone)

        if phone not in self.ipa.phones:
            return self.error(f"Unknown phone: {phone}")

        pairs = self.ipa.minimal_pairs(phone, max_distance=self.args.max_distance)

        if not pairs:
            return self.error(f"No minimal pairs found for {phone}")

        if self.format == "json":
            result = [
                {"phone": p, "differs_in": feat, "value": val} for p, feat, val in pairs
            ]
            self.output_json({"reference": phone, "pairs": result})
        else:
            ref_desc = self.ipa.describe(phone)
            print(f"{phone} ({ref_desc})")
            print("-" * 40)
            for p, feat, val in pairs:
                desc = self.ipa.describe(p)
                print(f"  {p}  {feat}={val}  ({desc})")
        return 0


class NearestCommand(Command):
    """Find the n nearest phones by phonetic distance.

    Ranks all phones by their phonetic similarity to the reference phone,
    based on feature distance. Useful for finding related sounds or
    potential confusion pairs.

    Examples:
        ipakit analysis nearest p          # Show 10 nearest phones to p
        ipakit an nearest p -n 5           # Show 5 nearest
        ipakit an near ɛ -f json           # JSON output
    """

    name = "nearest"
    aliases = ["near"]
    help = "Find n nearest phones by distance (e.g., 'p' → 'ɸ', 'f'...)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phone", help="Reference IPA phone symbol")
        parser.add_argument(
            "-n",
            type=int,
            default=10,
            help="Number of results (default: 10)",
        )
        add_format_arg(parser)

    def run(self) -> int:
        phone = self.ipa.expand_ligatures(self.args.phone)

        if phone not in self.ipa.phones:
            return self.error(f"Unknown phone: {phone}")

        nearest = self.ipa.nearest_phones(phone, n=self.args.n)

        if not nearest:
            return self.error("No phones found")

        if self.format == "json":
            result = [{"phone": p, "distance": round(d, 4)} for p, d in nearest]
            self.output_json({"reference": phone, "nearest": result})
        else:
            ref_desc = self.ipa.describe(phone)
            print(f"{phone} ({ref_desc})")
            print("-" * 50)
            for p, dist in nearest:
                desc = self.ipa.describe(p)
                print(f"  {p}  {dist:.3f}  {desc}")
        return 0


class ValidateCommand(Command):
    """Validate an IPA string for well-formedness.

    Checks for common issues:
    - Unknown symbols (not valid IPA)
    - Orphan diacritics (diacritic without base phone)
    - Malformed tie bars
    - Duplicate diacritics

    Exit codes:
        0: Valid (no errors)
        1: Invalid (has errors)

    Examples:
        ipakit analysis validate "kæt"     # Valid - exit 0
        ipakit an validate "kæt̪"           # Valid - dental diacritic
        ipakit an validate "k@t"           # Invalid - unknown symbol
        ipakit an validate "̃a"             # Invalid - orphan diacritic
        ipakit an val "kæt" -f json        # JSON output
        ipakit an val "kæt" --strict       # Treat warnings as errors
    """

    name = "validate"
    aliases = ["val"]
    help = "Check IPA string for well-formedness"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to validate")
        parser.add_argument(
            "--strict",
            "-s",
            action="store_true",
            help="Treat warnings as errors",
        )
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Suppress output, just set exit code",
        )
        add_format_arg(parser)

    def run(self) -> int:
        ipa = self.args.ipa
        issues = self.ipa.validate_ipa(ipa, strict=self.args.strict)

        has_errors = any(issue["type"] == "error" for issue in issues)

        if self.args.quiet:
            return 1 if has_errors else 0

        if self.format == "json":
            self.output_json(
                {
                    "input": ipa,
                    "valid": not has_errors,
                    "issues": issues,
                }
            )
        else:
            if not issues:
                print(f"Valid: {ipa}")
            else:
                print(f"Issues in: {ipa}")
                print("-" * 40)
                for issue in issues:
                    label = "ERROR" if issue["type"] == "error" else "WARNING"
                    print(f"  {label} [{issue['code']}] {issue['message']}")
                    print(f"      at position {issue['position']}")

        return 1 if has_errors else 0


class AnalysisGroup(CommandGroup):
    """Phonetic analysis commands.

    Tools for analyzing phones and their relationships:
    natural classes, minimal pairs, similarity, and validation.

    Subcommands:
        describe       Human-readable IPA description
        natural-class  Find shared features across phones
        minimal-pairs  Find phones differing by one feature
        nearest        Find phonetically similar phones
        validate       Check IPA string for well-formedness

    Examples:
        ipakit analysis describe p
        ipakit analysis natural-class p t k
        ipakit analysis minimal-pairs s
        ipakit analysis nearest ɛ
        ipakit analysis validate "kæt"
    """

    name = "analysis"
    aliases = ["an"]
    help = (
        "Phonetic analysis (describe, natural-class, minimal-pairs, nearest, validate)"
    )
    commands = [
        DescribeCommand,
        NaturalClassCommand,
        MinimalPairsCommand,
        NearestCommand,
        ValidateCommand,
    ]
