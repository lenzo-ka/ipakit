"""Distance commands - phonetic distance calculations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from ..distance_model import DistanceModel
from ..models import Phoneset
from .base import Command, CommandGroup, add_format_arg

if TYPE_CHECKING:
    from ..features import IPAFeatures


def add_model_args(parser: argparse.ArgumentParser) -> None:
    """Add the DistanceModel reference/shape options shared by model commands."""
    parser.add_argument(
        "--phoneset",
        "-p",
        type=Path,
        metavar="FILE",
        help="Reference inventory file (one phone per line); default: full bundled IPA",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="Percentile exponent; >1 spreads dissimilar pairs apart (default: 1.0)",
    )


def build_model(
    ipa: IPAFeatures, args: argparse.Namespace, **extra: object
) -> DistanceModel:
    """Build a DistanceModel from shared CLI args (global, or --phoneset-scoped)."""
    if getattr(args, "phoneset", None):
        phoneset = Phoneset.from_file(args.phoneset)
        return DistanceModel.for_phoneset(ipa, phoneset, gamma=args.gamma, **extra)  # type: ignore[arg-type]
    return DistanceModel.global_(ipa, gamma=args.gamma, **extra)  # type: ignore[arg-type]


class PairCommand(Command):
    """Calculate phonetic distance between two phones.

    Returns a value from 0.0 (identical) to 1.0 (maximally different).
    Distance is computed based on feature differences, with ordinal
    features (like height, backness) using scaled distances.

    Examples:
        ipakit distance pair p b           # 0.0435 (voicing difference)
        ipakit distance pair p t           # 0.0100 (place difference)
        ipakit d pair a i                  # 0.0417 (vowel height/backness)
        ipakit d pair p ɑ                  # 0.1467 (consonant vs vowel)
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
                    "distance": round(d, 4),
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
                    "distance": round(d, 4),
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
                cells = [f"{matrix[i][j]:.3f}" for j in range(len(phones))]
                print(f"{p1}\t" + "\t".join(cells))
        else:
            width = max(len(p) for p in phones)
            header = " " * (width + 1) + "  ".join(p.center(5) for p in phones)
            print(header)
            for i, p1 in enumerate(phones):
                row = "  ".join(f"{matrix[i][j]:.3f}" for j in range(len(phones)))
                print(f"{p1.ljust(width)} {row}")
        return 0


class ConfusabilityCommand(Command):
    """Inventory-relative confusability and distance between two phones.

    Unlike 'pair' (raw feature distance), this uses the distribution-aware
    DistanceModel: the score is a percentile within a reference inventory, so
    it answers "how confusable are these *relative to* the inventory?".
    Confusability runs 0.0 (distinct) to 1.0 (identical); distance is its
    complement. Scope the inventory with --phoneset (default: full bundled IPA).

    Examples:
        ipakit distance confusability p b      # confusability=0.8454 distance=0.1546
        ipakit distance conf p t               # confusability=0.9762 distance=0.0238
        ipakit d conf p b --phoneset eng.txt   # percentile within eng.txt's phones
        ipakit d conf p b --gamma 2            # sharpen: push dissimilar pairs apart
        ipakit d conf p b -j                   # JSON with reference info
    """

    name = "confusability"
    aliases = ["conf"]
    help = "Inventory-relative confusability/distance between two phones"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("phone1", help="First IPA phone symbol")
        parser.add_argument("phone2", help="Second IPA phone symbol")
        add_model_args(parser)
        add_format_arg(parser)

    def run(self) -> int:
        if self.args.phone1 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone1}")
        if self.args.phone2 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone2}")

        model = build_model(self.ipa, self.args)
        a, b = self.args.phone1, self.args.phone2
        conf = model.confusability(a, b)
        dist = model.distance(a, b)
        name = model.reference_name
        size = len(model.reference_phones)

        if self.format == "json":
            self.output_json(
                {
                    "phone1": a,
                    "phone2": b,
                    "confusability": round(conf, 4),
                    "distance": round(dist, 4),
                    "reference": name,
                    "reference_size": size,
                    "gamma": model.gamma,
                }
            )
        else:
            print(
                f"{a} ~ {b}: confusability={conf:.4f} distance={dist:.4f}"
                f"  [reference: {name}, {size} phones]"
            )
        return 0


class WordCommand(Command):
    """Inventory-relative distance and similarity between two IPA words.

    Aligns the words with the DistanceModel's inventory-relative substitution
    costs (weighted Levenshtein). Similarity runs 0.0 to 1.0. Scope the
    inventory with --phoneset; pass --threshold to also report a similar
    decision (with the model's length-ratio short-circuits applied).

    Examples:
        ipakit distance word kæt kæd           # similarity=0.9742
        ipakit distance word kæt dɒɡ           # similarity=0.8440
        ipakit d word kæt kæd --threshold 0.9  # also prints: similar=True
        ipakit d word kæt kæd --phoneset eng.txt  # similarity within eng.txt
        ipakit d word kæt kæd -j               # JSON (similarity + raw edit cost)
    """

    name = "word"
    aliases = ["w"]
    help = "Inventory-relative distance/similarity between two IPA words"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("word1", help="First IPA word")
        parser.add_argument("word2", help="Second IPA word")
        parser.add_argument(
            "--threshold",
            "-t",
            type=float,
            default=None,
            help="If set, also report whether similarity meets this threshold",
        )
        parser.add_argument(
            "--sub-mode",
            choices=["simple", "di"],
            default="simple",
            help="Substitution-cost mode (default: simple)",
        )
        add_model_args(parser)
        add_format_arg(parser)

    def run(self) -> int:
        threshold = self.args.threshold
        model = build_model(
            self.ipa,
            self.args,
            sub_mode=self.args.sub_mode,
            threshold=threshold,
        )
        w1, w2 = self.args.word1, self.args.word2
        result = model.word_distance(w1, w2)
        name = model.reference_name
        size = len(model.reference_phones)

        data: dict[str, object] = {
            "word1": w1,
            "word2": w2,
            "distance": round(result.distance, 4),
            "similarity": round(result.similarity, 4),
            "reference": name,
            "reference_size": size,
            "gamma": model.gamma,
            "sub_mode": model.sub_mode,
        }
        if threshold is not None:
            data["threshold"] = threshold
            data["similar"] = model.is_similar(w1, w2)

        if self.format == "json":
            self.output_json(data)
        else:
            print(
                f"{w1} ~ {w2}: similarity={result.similarity:.4f}"
                f"  [reference: {name}, {size} phones]"
            )
            if threshold is not None:
                print(f"similar={data['similar']} (threshold={threshold})")
        return 0


class DistanceGroup(CommandGroup):
    """Calculate phonetic distances between IPA phones and words.

    Two flavors: 'pair'/'segment'/'matrix' give the raw feature distance
    (0.0 identical to 1.0 maximal); 'confusability'/'word' use the
    distribution-aware DistanceModel, scoring as a percentile within a
    reference inventory (scope it with --phoneset).

    Subcommands:
        pair           Feature distance between two base phones
        segment        Feature distance between complex segments (diacritics)
        matrix         Pairwise feature-distance matrix for multiple phones
        confusability  Inventory-relative confusability/distance (phones)
        word           Inventory-relative distance/similarity (IPA words)

    Examples:
        ipakit distance pair p b               # Raw feature distance: ~0.04
        ipakit distance confusability p b      # Inventory-relative: 0.8454
        ipakit distance word kæt kæd           # Word similarity: 0.9742
        ipakit distance matrix p t k           # 3x3 comparison matrix
    """

    name = "distance"
    aliases = ["d"]
    help = "Phonetic distances (pair, segment, matrix, confusability, word)"
    commands = [
        PairCommand,
        SegmentCommand,
        MatrixCommand,
        ConfusabilityCommand,
        WordCommand,
    ]
