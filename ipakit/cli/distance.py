"""Distance commands - phonetic distance calculations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from ..distance_model import DistanceModel
from ..models import Phoneset
from .base import IPA, Command, CommandGroup, add_format_arg

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
        help=(
            "Percentile exponent; monotone, so it reorders no phone pair "
            "(docs/distance.md section 9). Default: 1.0, the identity"
        ),
    )


def build_model(
    ipa: IPAFeatures, args: argparse.Namespace, **extra: object
) -> DistanceModel:
    """Build a DistanceModel from shared CLI args (global, or --phoneset-scoped)."""
    if getattr(args, "phoneset", None):
        phoneset = Phoneset.from_file(args.phoneset)
        return DistanceModel.for_phoneset(ipa, phoneset, gamma=args.gamma, **extra)  # type: ignore[arg-type]
    return DistanceModel.global_(ipa, gamma=args.gamma, **extra)  # type: ignore[arg-type]


def _coverage_note(coverage: float) -> str:
    """The coverage clause for a text line, empty where the words match in length.

    Printed beside the similarity and never inside it: a length ratio
    folded into the score would charge length a second time, on top of
    the gaps the alignment already pays for.
    """
    return "" if coverage == 1.0 else f"  coverage={coverage:.4f}"


class PairCommand(Command):
    """Calculate phonetic distance between two phones.

    Returns a value from 0.0 (identical) to 1.0 (maximally different).
    Distance is computed based on feature differences, with ordinal
    features (like height, backness) using scaled distances.

    Examples:
        ipakit distance pair p b           # a voicing difference
        ipakit distance pair p t           # a place difference
        ipakit d pair a i                  # vowel height and backness
        ipakit d pair p ɑ                  # across the consonant/vowel divide
        ipakit d pair p b -f json          # {"phone1": "p", "phone2": "b", "distance": ...}
    """

    name = "pair"
    aliases: ClassVar[list[str]] = []
    help = "Distance between two phones (0.0=identical, 1.0=max different)"
    reads_notation = IPA

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
    aliases: ClassVar[list[str]] = ["seg"]
    help = "Distance between segments (handles diacritics, affricates)"
    reads_notation = IPA

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
    aliases: ClassVar[list[str]] = []
    help = "Pairwise distance matrix for multiple phones"
    reads_notation = IPA

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
        ipakit distance confusability p b      # confusability and its complement
        ipakit distance conf p t               # a nearer pair scores higher
        ipakit d conf p b --phoneset eng.txt   # percentile within eng.txt's phones
        ipakit d conf p b --gamma 2            # same ranking, spacing stretched
        ipakit d conf p b -j                   # JSON with reference info
    """

    name = "confusability"
    aliases: ClassVar[list[str]] = ["conf"]
    help = "Inventory-relative confusability/distance between two phones"
    reads_notation = IPA

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
    """Distance and similarity between two IPA words.

    Two measures, matching the two this group already offers for phones.
    By default this is the inventory-relative one -- the counterpart of
    'confusability' -- aligning the words with the DistanceModel's
    percentile substitution costs (weighted Levenshtein). --raw is the
    counterpart of 'pair': the plain feature-distance alignment, which is
    what ipakit.word_distance() and ipakit.word_similarity() return.

    The two disagree, and are meant to: for kæt ~ kæd the model says
    0.9854 and the raw measure says 0.9833. Without --raw there was no
    command line spelling of the second number at all, so a reader
    comparing the API against the CLI saw a discrepancy where there was
    a choice of measure.

    Similarity runs 0.0 to 1.0. Scope the inventory with --phoneset; pass
    --threshold to also report a similar decision (with the model's
    length-ratio short-circuits applied).

    Coverage -- the shorter word's token count over the longer's -- is
    reported beside the similarity when the two differ in length, and is
    never folded into it. It is what separates "these differ throughout"
    from "one is a truncation of the other", two readings the score alone
    cannot tell apart.

    Examples:
        ipakit distance word kæt kæd           # one segment differs
        ipakit distance word kæt dɒɡ           # unrelated words
        ipakit distance word kæt kæd --raw     # the raw feature-cost measure
        ipakit d word kæt kæd --threshold 0.9  # also prints: similar=True
        ipakit d word kæt kæd --phoneset eng.txt  # similarity within eng.txt
        ipakit d word kæt kæd -j               # JSON (similarity + raw edit cost)
    """

    name = "word"
    aliases: ClassVar[list[str]] = ["w"]
    help = "Inventory-relative distance/similarity between two IPA words"
    reads_notation = IPA

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
            "--raw",
            action="store_true",
            help="Use the raw feature distance (ipakit.word_distance) instead "
            "of the inventory-relative model",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            help="Print a per-position alignment trace (raw feature path) "
            "instead of a single score",
        )
        add_model_args(parser)
        add_format_arg(parser)

    def _run_raw(self) -> int:
        """The raw feature-cost measure -- ipakit.word_distance's answer.

        ``strict=False`` because the CLI reports a lossy read through the
        exit status rather than by failing (:mod:`ipakit.cli.policy`):
        the warning the read raises becomes status 3, which is how every
        other soft-reading subcommand answers. Passing ``strict=True``
        here would make this one command exit 1 on input that the rest
        of the command line exits 3 on.
        """
        w1, w2 = self.args.word1, self.args.word2
        result = self.ipa.word_distance(w1, w2, strict=False)
        data: dict[str, object] = {
            "word1": w1,
            "word2": w2,
            "edit_cost": round(result.edit_cost, 4),
            "similarity": round(result.similarity, 4),
            "coverage": round(result.coverage, 4),
            "reference": "raw",
        }
        threshold = self.args.threshold
        if threshold is not None:
            data["threshold"] = threshold
            data["similar"] = result.similarity >= threshold

        if self.format == "json":
            self.output_json(data)
        else:
            print(
                f"{w1} ~ {w2}: similarity={result.similarity:.4f}"
                f"{_coverage_note(result.coverage)}  [raw feature distance]"
            )
            if threshold is not None:
                print(f"similar={data['similar']} (threshold={threshold})")
        return 0

    def _run_explain(self) -> int:
        """A per-position alignment trace -- ipakit.explain_word_distance."""
        w1, w2 = self.args.word1, self.args.word2
        steps = self.ipa.explain_word_distance(w1, w2, strict=False)
        if self.format == "json":
            self.output_json({"word1": w1, "word2": w2, "steps": steps})
            return 0
        print(f"{w1} ~ {w2}")
        for step in steps:
            a = step["a"] if step["a"] is not None else "-"
            b = step["b"] if step["b"] is not None else "-"
            print(f"  {step['op']:6} {a!s:>4} ~ {b!s:<4}  cost={step['cost']:.4f}")
            terms = cast("list[dict[str, object]]", step["terms"])
            for term in terms:
                if cast("float", term["cost"]) > 0:
                    va = term["a"] if term["a"] is not None else ""
                    vb = term["b"] if term["b"] is not None else ""
                    detail = f"{va} vs {vb}".strip(" vs")
                    print(f"         · {term['label']}: {detail} = {term['cost']}")
        return 0

    def run(self) -> int:
        if self.args.explain:
            return self._run_explain()
        if self.args.raw:
            return self._run_raw()
        threshold = self.args.threshold
        model = build_model(self.ipa, self.args, threshold=threshold)
        w1, w2 = self.args.word1, self.args.word2
        result = model.word_distance(w1, w2)
        name = model.reference_name
        size = len(model.reference_phones)

        data: dict[str, object] = {
            "word1": w1,
            "word2": w2,
            "edit_cost": round(result.edit_cost, 4),
            "similarity": round(result.similarity, 4),
            "coverage": round(result.coverage, 4),
            "reference": name,
            "reference_size": size,
            "gamma": model.gamma,
        }
        if threshold is not None:
            data["threshold"] = threshold
            data["similar"] = model.is_similar(w1, w2)

        if self.format == "json":
            self.output_json(data)
        else:
            print(
                f"{w1} ~ {w2}: similarity={result.similarity:.4f}"
                f"{_coverage_note(result.coverage)}"
                f"  [reference: {name}, {size} phones]"
            )
            if threshold is not None:
                print(f"similar={data['similar']} (threshold={threshold})")
        return 0


class DirectionalCommand(Command):
    """Directional edit distance from a reference to a hypothesis.

    Deletion prices apply to the reference (material omitted); insertion
    prices apply to the hypothesis (material supplied).  Giving the two sides
    different prices makes their roles observable.  The defaults match the
    flat-cost ``distance word --raw`` calculation.

    Examples:
        ipakit distance directional kætə kæt
        ipakit d directional kætə kæt --delete-cost 0.25
        ipakit d directional kæt kætə --insert-cost 0.5 -j
    """

    name = "directional"
    aliases: ClassVar[list[str]] = ["dir"]
    help = "Directional reference-to-hypothesis word distance"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.add_argument("reference", help="Target/reference IPA form")
        parser.add_argument("hypothesis", help="Observed/hypothesis IPA form")
        parser.add_argument(
            "--insert-cost",
            type=float,
            default=None,
            help="Flat cost for a phone supplied in the hypothesis (default: 1)",
        )
        parser.add_argument(
            "--delete-cost",
            type=float,
            default=None,
            help="Flat cost for a phone omitted from the reference (default: 1)",
        )
        parser.add_argument(
            "--unweighted",
            action="store_true",
            help="Use a flat substitution cost instead of feature distance",
        )
        add_format_arg(parser)

    def run(self) -> int:
        reference = self.args.reference
        hypothesis = self.args.hypothesis
        result = self.ipa.directional_word_distance(
            reference,
            hypothesis,
            insert_cost=self.args.insert_cost,
            delete_cost=self.args.delete_cost,
            weighted=not self.args.unweighted,
            strict=False,
        )
        data = {
            "reference": reference,
            "hypothesis": hypothesis,
            "edit_cost": round(result.edit_cost, 4),
            "similarity": round(result.similarity, 4),
            "coverage": round(result.coverage, 4),
            "costs": result.costs,
        }
        if self.format == "json":
            self.output_json(data)
        else:
            print(
                f"{reference} -> {hypothesis}: similarity={result.similarity:.4f} "
                f"edit_cost={result.edit_cost:.4f}{_coverage_note(result.coverage)} "
                f"[{result.costs}]"
            )
        return 0


class NearestCommand(Command):
    """The nearest acceptable pronunciation in a set, and which one matched.

    Scores a form against a set of acceptable variants -- a lexicon's several
    pronunciations, a homograph's two readings -- and reports the best match
    and which member won. This is the "is this an acceptable pronunciation?"
    question, and it is spelled apart from 'word' on purpose: a maximum over
    variants depends on how many are listed, so it must not be read as a
    word-to-word distance.

    Examples:
        ipakit distance nearest waɪnd wɪnd waɪnd     # wind: the 'turn' reading wins
        ipakit distance nearest ˈaɪðɚ ˈiːðɚ ˈaɪðɚ    # either: the aɪ variant
        ipakit d nearest kæt dɒɡ kæd                 # nearest of two, below 1.0
        ipakit d nearest kæt dɒɡ kæd -j              # JSON (form, accepted, similarity)
    """

    name = "nearest"
    aliases: ClassVar[list[str]] = []
    help = "Nearest acceptable pronunciation in a set (best match + which won)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("form", help="The observed IPA form")
        parser.add_argument(
            "acceptable",
            nargs="+",
            help="One or more acceptable IPA pronunciations to match against",
        )
        parser.add_argument(
            "-n",
            type=int,
            default=None,
            help="Show the n-best matches instead of only the nearest",
        )
        parser.add_argument(
            "--local",
            action="store_true",
            help="Match each candidate as a target embedded in the form "
            "(local fit) rather than whole-to-whole",
        )
        add_format_arg(parser)

    def run(self) -> int:
        # strict=False for the same reason 'word --raw' uses it: a lossy read
        # is reported through the exit status by ipakit.cli.policy, not by
        # failing the command.
        mode = "local" if self.args.local else "global"
        # No -n is the single nearest; -n K is the K-best.
        if self.args.n is None:
            ranked = [
                self.ipa.nearest_pronunciation(
                    self.args.form, self.args.acceptable, strict=False, mode=mode
                )
            ]
        else:
            ranked = self.ipa.rank_pronunciations(
                self.args.form,
                self.args.acceptable,
                n=self.args.n,
                strict=False,
                mode=mode,
            )
        total = len(self.args.acceptable)
        if self.format == "json":
            self.output_json(
                {
                    "form": self.args.form,
                    "mode": mode,
                    "candidates": total,
                    "matches": [
                        {"accepted": m.accepted, "similarity": round(m.similarity, 4)}
                        for m in ranked
                    ],
                }
            )
        else:
            for m in ranked:
                print(f"{m.form} \u2248 {m.accepted}: similarity={m.similarity:.4f}")
            if self.args.n is None:
                print(f"  (best of {total})")
        return 0


class SeqCommand(Command):
    """Distance/similarity between two PRE-TOKENIZED phone sequences.

    Each argument is a whitespace-separated list of phone tokens, aligned
    exactly as given -- unlike 'word', which tokenizes a string and may join
    or split units. Use this when you already have phone tokens (each token one
    unit) and want their boundaries respected.

    --local fits the second sequence as a target inside the first, with the
    first sequence's ends free, for a target embedded in a longer sequence.

    Examples:
        ipakit distance seq "t ʃ" "t͡ʃ"          # two units vs one: not equal
        ipakit distance seq "k æ t" "k æ d"       # a minimal pair
        ipakit d seq "b ə b t aɪ ɹ d" "t aɪ ɹ d" --local   # target embedded
        ipakit d seq "k æ t" "k æ d" -j
    """

    name = "seq"
    aliases: ClassVar[list[str]] = []
    help = "Distance/similarity between two pre-tokenized phone sequences"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("seq1", help="First phone sequence (space-separated)")
        parser.add_argument("seq2", help="Second phone sequence (space-separated)")
        parser.add_argument(
            "--local",
            action="store_true",
            help="Fit seq2 as a target embedded in seq1 (free ends on seq1)",
        )
        add_format_arg(parser)

    def run(self) -> int:
        t1 = self.args.seq1.split()
        t2 = self.args.seq2.split()
        mode = "local" if self.args.local else "global"
        result = self.ipa.sequence_distance(t1, t2, mode=mode)
        if self.format == "json":
            self.output_json(
                {
                    "seq1": t1,
                    "seq2": t2,
                    "mode": mode,
                    "similarity": round(result.similarity, 4),
                    "edit_cost": round(result.edit_cost, 4),
                    "coverage": round(result.coverage, 4),
                }
            )
        else:
            print(
                f"{' '.join(t1)} ~ {' '.join(t2)}: "
                f"similarity={result.similarity:.4f}  [{mode}]"
            )
        return 0


class DistanceGroup(CommandGroup):
    """Calculate phonetic distances between IPA phones, words, and phone sequences.

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
        directional    Directional reference-to-hypothesis word distance
        nearest        Best match of a form against a set of acceptable variants
        seq            Distance between two pre-tokenized phone sequences

    Examples:
        ipakit distance pair p b               # Raw feature distance: ~0.04
        ipakit distance confusability p b      # inventory-relative
        ipakit distance word kæt kæd           # word similarity
        ipakit distance matrix p t k           # 3x3 comparison matrix
    """

    name = "distance"
    aliases: ClassVar[list[str]] = ["d"]
    help = "Phonetic distances (pair, segment, matrix, confusability, word, directional, nearest, seq)"
    commands: ClassVar[list[type[Command]]] = [
        PairCommand,
        SegmentCommand,
        MatrixCommand,
        ConfusabilityCommand,
        WordCommand,
        DirectionalCommand,
        NearestCommand,
        SeqCommand,
    ]
