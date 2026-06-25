"""Distance commands - phonetic distance calculations."""

from __future__ import annotations

import argparse

from .base import Command, CommandGroup, add_format_arg


class PairCommand(Command):
    """Calculate phonetic distance between two phones.

    Returns a value from 0.0 (identical) to 1.0 (maximally different).
    Distance is computed based on feature differences, with ordinal
    features (like height, backness) using scaled distances.

    Examples:
        ipakit distance pair p b           # 0.0435 (voicing difference)
        ipakit distance pair p t           # 0.0100 (place difference)
        ipakit d pair a i                  # ~0.15 (vowel height/backness)
        ipakit d pair p ɑ                  # ~0.5 (consonant vs vowel)
        ipakit d pair p b -f json          # {"phone1": "p", "phone2": "b", "distance": 0.0435}
    """

    name = "pair"
    aliases = []
    help = "Distance between two phones (0.0=identical, 1.0=max different)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phone1", help="First IPA phone symbol")
        parser.add_argument("phone2", help="Second IPA phone symbol")
        add_format_arg(parser)

    def run(self) -> int:
        if self.args.phone1 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone1}")
        if self.args.phone2 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone2}")

        d = self.ipa.distance(self.args.phone1, self.args.phone2)

        if self.format == "json":
            self.output_json(
                {
                    "phone1": self.args.phone1,
                    "phone2": self.args.phone2,
                    "distance": d,
                }
            )
        else:
            print(f"{d:.4f}")
        return 0


class SegmentCommand(Command):
    """Calculate distance between two IPA segments with diacritics.

    Unlike 'pair' which works on base phones, this handles complex
    segments including diacritics (aspiration, palatalization, etc.)
    and multi-phone segments (affricates, diphthongs).

    Examples:
        ipakit distance segment "pʰ" "p"   # Aspirated vs plain
        ipakit distance segment "t͡s" "s"   # Affricate vs fricative
        ipakit d seg "pʲ" "p"               # Palatalized vs plain
        ipakit d seg "a͡ɪ" "a͡ʊ"             # Diphthong comparison
    """

    name = "segment"
    aliases = ["seg"]
    help = "Distance between segments (handles diacritics, affricates)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("seg1", help="First IPA segment (may include diacritics)")
        parser.add_argument("seg2", help="Second IPA segment")
        add_format_arg(parser)

    def run(self) -> int:
        d = self.ipa.segment_distance(self.args.seg1, self.args.seg2)

        if self.format == "json":
            self.output_json(
                {
                    "segment1": self.args.seg1,
                    "segment2": self.args.seg2,
                    "distance": d,
                }
            )
        else:
            print(f"{d:.4f}")
        return 0


class MatrixCommand(Command):
    """Generate a pairwise distance matrix for multiple phones.

    Computes distances between all pairs of phones and displays
    as a symmetric matrix. Useful for clustering analysis or
    visualizing phonetic similarity.

    Examples:
        ipakit distance matrix p b t d      # 4x4 matrix
        ipakit distance matrix              # Default: first 20 phones
        ipakit d matrix p t k -f tsv        # Tab-separated for import
        ipakit d matrix a e i o u -f json   # JSON with phones + matrix
    """

    name = "matrix"
    aliases = []
    help = "Pairwise distance matrix for multiple phones"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "phones",
            nargs="*",
            help="Phones to include (default: first 20 alphabetically)",
        )
        add_format_arg(parser, ["text", "tsv", "json"])

    def run(self) -> int:
        phones = (
            self.args.phones
            if self.args.phones
            else sorted(self.ipa.phones.keys())[:20]
        )
        matrix = self.ipa.pairwise_distances(phones)

        if self.format == "json":
            self.output_json({"phones": phones, "matrix": matrix})
        elif self.format == "tsv":
            print("\t" + "\t".join(phones))
            for i, p1 in enumerate(phones):
                row = [f"{matrix[i][j]:.3f}" for j in range(len(phones))]
                print(f"{p1}\t" + "\t".join(row))
        else:
            width = max(len(p) for p in phones)
            header = " " * (width + 1) + "  ".join(p.center(5) for p in phones)
            print(header)
            for i, p1 in enumerate(phones):
                row = "  ".join(f"{matrix[i][j]:.3f}" for j in range(len(phones)))
                print(f"{p1.ljust(width)} {row}")
        return 0


class DistanceGroup(CommandGroup):
    """Calculate phonetic distances between IPA phones.

    Distance is based on feature differences, ranging from 0.0
    (identical) to 1.0 (maximally different). Ordinal features
    like vowel height use scaled distances.

    Subcommands:
        pair     Distance between two base phones
        segment  Distance between complex segments (with diacritics)
        matrix   Pairwise distance matrix for multiple phones

    Examples:
        ipakit distance pair p b       # Voicing difference: ~0.04
        ipakit distance segment pʰ p   # Aspiration difference
        ipakit distance matrix p t k   # 3x3 comparison matrix
    """

    name = "distance"
    aliases = ["d"]
    help = "Calculate phonetic distances (pair, segment, matrix)"
    commands = [PairCommand, SegmentCommand, MatrixCommand]
