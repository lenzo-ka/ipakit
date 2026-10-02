"""Distance commands - phonetic distance calculations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from ..distance_model import DistanceModel
from ..models import Phoneset
from .base import IPA, Command, CommandGroup, add_format_arg, add_output_arg
from .metrics import AcrossCommand, MetricsCommand

if TYPE_CHECKING:
    from ..features import IPAFeatures


def add_applicable_only_arg(parser: argparse.ArgumentParser) -> None:
    """Add the opt-in feature-applicability denominator."""
    parser.add_argument(
        "--applicable-only",
        action="store_true",
        help="Count only features applicable to both compared hosts",
    )


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
    add_applicable_only_arg(parser)


def build_model(
    ipa: IPAFeatures, args: argparse.Namespace, **extra: object
) -> DistanceModel:
    """Build a DistanceModel from shared CLI args (global, or --phoneset-scoped)."""
    if getattr(args, "applicable_only", False):
        phones = (
            list(Phoneset.from_file(args.phoneset))
            if getattr(args, "phoneset", None)
            else None
        )
        return DistanceModel.derive(
            ipa,
            phones=phones,
            gamma=args.gamma,
            applicable_only=True,
            **extra,  # type: ignore[arg-type]
        )
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
        add_applicable_only_arg(parser)
        add_format_arg(parser)

    def run(self) -> int:
        if self.args.phone1 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone1}")
        if self.args.phone2 not in self.ipa:
            return self.error(f"Unknown phone: {self.args.phone2}")

        d = self.ipa.distance(
            self.args.phone1,
            self.args.phone2,
            applicable_only=self.args.applicable_only,
        )

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
        add_applicable_only_arg(parser)
        add_format_arg(parser)

    def run(self) -> int:
        d = self.ipa.segment_distance(
            self.args.seg1,
            self.args.seg2,
            applicable_only=self.args.applicable_only,
        )

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
        add_applicable_only_arg(parser)
        add_format_arg(parser, ["text", "tsv", "json"])

    def run(self) -> int:
        phones = (
            self.args.phones
            if self.args.phones
            else sorted(self.ipa.phones.keys())[:20]
        )
        matrix = self.ipa.pairwise_distances(
            phones, applicable_only=self.args.applicable_only
        )

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


class PositionsCommand(Command):
    """Inventory-relative percentile positions for two phones.

    Unlike 'pair' (raw feature distance), this uses the distribution-aware
    DistanceModel. Similarity position is the pair's percentile in the
    reference inventory; distance position is its complement. Neither is a
    structural magnitude comparable to 'pair', and neither is comparable across
    inventories. Distance position 0.0 means identity; the closest distinct pair sits
    just above it. Scope the inventory with --phoneset (default: full bundled
    IPA).

    Examples:
        ipakit distance positions p b          # two complementary positions
        ipakit distance pos p t                # a nearer pair scores higher
        ipakit d pos p b --phoneset eng.txt    # positions within eng.txt's phones
        ipakit d pos p b --gamma 2             # same ranking, spacing stretched
        ipakit d pos p b -j                    # JSON with reference info
    """

    name = "positions"
    aliases: ClassVar[list[str]] = ["pos"]
    help = "Inventory-relative percentile positions between two phones"
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
        similarity_position = model.similarity_position(a, b)
        distance_position = model.distance_position(a, b)
        name = model.reference_name
        size = len(model.reference_phones)

        if self.format == "json":
            self.output_json(
                {
                    "phone1": a,
                    "phone2": b,
                    "similarity_position": round(similarity_position, 4),
                    "distance_position": round(distance_position, 4),
                    "reference": name,
                    "reference_size": size,
                    "gamma": model.gamma,
                }
            )
        else:
            print(
                f"{a} ~ {b}: similarity_position={similarity_position:.4f} "
                f"distance_position={distance_position:.4f}"
                f"  [reference: {name}, {size} phones]"
            )
        return 0


class TranscriptionCommand(Command):
    """Distance and similarity between two IPA transcription strings.

    Two measures, matching the two this group already offers for phones.
    By default this aligns the words with the DistanceModel's position-derived
    substitution costs (weighted Levenshtein). --raw is the
    counterpart of 'pair': the plain feature-distance alignment, which is
    what ipakit.transcription_distance() and ipakit.transcription_similarity() return.

    The two disagree, and are meant to: for kæt ~ kæd the model says
    0.9870 and the raw measure says 0.9841. Without --raw there was no
    command line spelling of the second number at all, so a reader
    comparing the API against the CLI saw a discrepancy where there was
    a choice of measure.

    Similarity runs 0.0 to 1.0. Scope the inventory with --phoneset; pass
    --threshold to also report a similar decision (with the model's
    length-ratio short-circuits applied).

    Coverage -- the shorter transcription's token count over the longer's -- is
    reported beside the similarity when the two differ in length, and is
    never folded into it. It is what separates "these differ throughout"
    from "one is a truncation of the other", two readings the score alone
    cannot tell apart.

    Examples:
        ipakit distance transcription kæt kæd           # one segment differs
        ipakit distance transcription kæt dɒɡ           # unrelated words
        ipakit distance transcription kæt kæd --raw     # the raw feature-cost measure
        ipakit d transcription kæt kæd --threshold 0.9  # also prints: similar=True
        ipakit d transcription kæt kæd --phoneset eng.txt  # similarity within eng.txt
        ipakit d transcription kæt kæd -j               # JSON (similarity + raw edit cost)
    """

    name = "transcription"
    aliases: ClassVar[list[str]] = ["word", "w"]
    help = "Alignment cost/similarity with position-derived substitutions"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "transcription1", metavar="TRANSCRIPTION1", help="First IPA transcription"
        )
        parser.add_argument(
            "transcription2", metavar="TRANSCRIPTION2", help="Second IPA transcription"
        )
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
            help="Use the raw feature distance (ipakit.transcription_distance) instead "
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
        """The raw feature-cost measure -- ipakit.transcription_distance's answer.

        ``strict=False`` because the CLI reports a lossy read through the
        exit status rather than by failing (:mod:`ipakit.cli.policy`):
        the warning the read raises becomes status 3, which is how every
        other soft-reading subcommand answers. Passing ``strict=True``
        here would make this one command exit 1 on input that the rest
        of the command line exits 3 on.
        """
        w1, w2 = self.args.transcription1, self.args.transcription2
        result = self.ipa.transcription_distance(
            w1,
            w2,
            strict=False,
            applicable_only=self.args.applicable_only,
        )
        data: dict[str, object] = {
            "transcription1": w1,
            "transcription2": w2,
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
        """A per-position alignment trace -- ipakit.explain_transcription_distance."""
        w1, w2 = self.args.transcription1, self.args.transcription2
        steps = self.ipa.explain_transcription_distance(
            w1,
            w2,
            strict=False,
            applicable_only=self.args.applicable_only,
        )
        if self.format == "json":
            self.output_json(
                {"transcription1": w1, "transcription2": w2, "steps": steps}
            )
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
        w1, w2 = self.args.transcription1, self.args.transcription2
        # The library model is strict by default. The CLI deliberately uses
        # its shared soft-read policy: warn, print the qualified answer, and
        # let the policy layer turn the warning into exit status 3.
        result = model.transcription_distance(w1, w2, strict=False)
        name = model.reference_name
        size = len(model.reference_phones)

        data: dict[str, object] = {
            "transcription1": w1,
            "transcription2": w2,
            "edit_cost": round(result.edit_cost, 4),
            "similarity": round(result.similarity, 4),
            "coverage": round(result.coverage, 4),
            "reference": name,
            "reference_size": size,
            "gamma": model.gamma,
        }
        if threshold is not None:
            data["threshold"] = threshold
            data["similar"] = model.is_similar(w1, w2, strict=False)

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
    flat-cost ``distance transcription --raw`` calculation.

    Examples:
        ipakit distance directional kætə kæt
        ipakit d directional kætə kæt --delete-cost 0.25
        ipakit d directional kæt kætə --insert-cost 0.5 -j
    """

    name = "directional"
    aliases: ClassVar[list[str]] = ["dir"]
    help = "Directional reference-to-hypothesis transcription distance"
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
        add_applicable_only_arg(parser)
        add_format_arg(parser)

    def run(self) -> int:
        reference = self.args.reference
        hypothesis = self.args.hypothesis
        result = self.ipa.directional_transcription_distance(
            reference,
            hypothesis,
            insert_cost=self.args.insert_cost,
            delete_cost=self.args.delete_cost,
            weighted=not self.args.unweighted,
            strict=False,
            applicable_only=self.args.applicable_only,
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
    question, and it is spelled apart from 'transcription' on purpose: a maximum over
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
        add_applicable_only_arg(parser)
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
                    self.args.form,
                    self.args.acceptable,
                    strict=False,
                    mode=mode,
                    applicable_only=self.args.applicable_only,
                )
            ]
        else:
            ranked = self.ipa.rank_pronunciations(
                self.args.form,
                self.args.acceptable,
                n=self.args.n,
                strict=False,
                mode=mode,
                applicable_only=self.args.applicable_only,
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
    exactly as given -- unlike 'transcription', which tokenizes a string and may join
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
        add_applicable_only_arg(parser)
        add_format_arg(parser)

    def run(self) -> int:
        t1 = self.args.seq1.split()
        t2 = self.args.seq2.split()
        mode = "local" if self.args.local else "global"
        result = self.ipa.sequence_distance(
            t1, t2, mode=mode, applicable_only=self.args.applicable_only
        )
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


class MapCommand(Command):
    """Map one phoneset onto another, by nearest phone or one-to-one.

    Two operations, because "the mapping" between two phonesets is
    ambiguous and they answer different questions.

    NEAREST (the default) is directional and many-to-one: every source
    phone gets its closest target, whether or not the target set holds
    anything like it. Several sources may land on one target, and that
    is the interesting part -- each such collapse is a contrast the
    source drew that the target cannot.

    ONE-TO-ONE (--one-to-one) is a matching: each phone used at most
    once, chosen to minimize TOTAL distance over the whole set. That is
    not what taking each phone's nearest in turn gives, and the greedy
    answer is worse without saying so. Surplus phones on the larger side
    come back unmapped rather than forced onto a partner.

    Examples:
        ipakit distance map english.txt spanish.txt
        ipakit distance map english.txt spanish.txt --one-to-one
        ipakit distance map cmudict mfa
        ipakit distance map cmudict target.txt --to-style wild
        ipakit distance map a.txt b.txt --max-distance 0.1
        ipakit distance map a.txt b.txt -f json

    SOURCE and TARGET may each be a named inventory or a phoneset file. Run
    ``ipakit inventory list`` for names; style options describe file notation.
    """

    name = "map"
    aliases: ClassVar[list[str]] = []
    help = "Map one phoneset onto another (nearest, or one-to-one)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("source", help="Source inventory name or file")
        parser.add_argument("target", help="Target inventory name or file")
        parser.add_argument(
            "--from-style", metavar="NAME", help="Notation of a source file"
        )
        parser.add_argument(
            "--to-style", metavar="NAME", help="Notation of a target file"
        )
        parser.add_argument(
            "--one-to-one",
            action="store_true",
            help="Match one-to-one minimizing total distance, instead of nearest",
        )
        parser.add_argument(
            "--no-tie",
            action="store_true",
            help=(
                "Take entries exactly as written. By default a line parsing "
                "to more than one segment gets the ties it left out, taking "
                "the format at its word: one phone per line"
            ),
        )
        parser.add_argument(
            "--wild",
            action="store_true",
            help=(
                "Also read wild spellings: ASCII stand-ins (g, :, ?, ') and "
                "the other tie convention. Off by default, so a valid tied "
                "construction is never rewritten behind your back"
            ),
        )
        parser.add_argument(
            "--max-distance",
            type=float,
            metavar="D",
            help="Refuse a pairing past this distance; the phone is reported unmapped",
        )
        add_applicable_only_arg(parser)
        add_format_arg(parser, ["text", "json", "tsv", "markdown"])
        add_output_arg(parser)

    def run(self) -> int:
        from ..inventories import inventories
        from ..inventory_comparison import inventory_comparison_report
        from ..inventory_renderers import (
            inventory_surface_view,
            render_inventory_json,
            render_inventory_markdown,
            render_inventory_text,
            render_inventory_tsv,
        )

        known = set(inventories())

        def resolve(token: str):  # type: ignore[no-untyped-def]
            path = Path(token)
            if token in known and path.exists():
                raise ValueError(
                    f"{token} is both an inventory and a file here; "
                    f"write ./{token} for the file"
                )
            if token in known:
                return token
            if not path.exists():
                raise FileNotFoundError(
                    f"no inventory or file {token!r}; run 'ipakit inventory list' "
                    "for the names"
                )
            return path

        from_style = self.args.from_style
        to_style = self.args.to_style
        if self.args.wild:
            if from_style or to_style:
                return self.error("--wild cannot be combined with a style option")
            from_style = to_style = "wild"

        def one_phone_error(phone: str, style: str | None) -> str:
            hints = []
            if self.args.no_tie:
                hints.append("drop --no-tie to read it as one")
            if style is None:
                hints.append("--wild may help")
            suffix = f"; {'; '.join(hints)}" if hints else ""
            return f"cannot read {phone!r} as one phone{suffix}"

        try:
            operands = (resolve(self.args.source), resolve(self.args.target))
            resolved = []
            for side, selected in zip(operands, (from_style, to_style), strict=True):
                view, changes = inventory_surface_view(
                    side,
                    style=selected,
                    ipa=self.ipa,
                    tied=not self.args.no_tie,
                )
                resolved.append(view)
                for kind, before, after in changes:
                    print(f"{kind}: {before} -> {after}", file=sys.stderr)
            report = inventory_comparison_report(
                resolved[0],
                resolved[1],
                mapping="one-to-one" if self.args.one_to_one else "nearest",
                max_distance=self.args.max_distance,
                detail=True,
                strip=None,
                ipa=self.ipa,
                applicable_only=self.args.applicable_only,
            )
        except FileNotFoundError as error:
            return self.error(str(error))
        except OSError as error:
            return self.error(f"cannot read phoneset: {error}")
        except ValueError as error:
            if str(error).startswith("cannot read"):
                print(f"Error: {error}", file=sys.stderr)
                return 3
            return self.error(str(error))

        unreadable = [
            (side, member.source_token, member.reason)
            for side, view in zip(("source", "target"), resolved, strict=True)
            for member in view.members
            if member.status == "unreadable"
        ]
        for side, entry, reason in unreadable:
            selected = from_style if side == "source" else to_style
            name = selected or "ipa"
            if reason == f"cannot read {entry!r} as one phone":
                reason = one_phone_error(entry, selected)
            print(
                f"Error: cannot read {entry!r} as {name} on {side} side: {reason}",
                file=sys.stderr,
            )
        status = 3 if unreadable else 0
        if self.format == "json":
            self.output(render_inventory_json(report).rstrip("\n"))
        elif self.format == "tsv":
            self.output(render_inventory_tsv(report).rstrip("\n"))
        elif self.format == "markdown":
            self.output(
                render_inventory_markdown(report, direction="a_to_b").rstrip("\n")
            )
        else:
            self.output(render_inventory_text(report, direction="a_to_b").rstrip("\n"))
        return status


class CompareCommand(Command):
    """Compare two phonesets as sets, directional mappings, and similarities.

    A and B may each be a named inventory or a phoneset file. The comparison
    reads house IPA, strips and reports stress marks by default, preserves
    declaration order, and reports nearest mappings in both directions.
    """

    name = "compare"
    aliases: ClassVar[list[str]] = []
    help = "Compare two phonesets in both directions"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.add_argument("a", help="First inventory name or file")
        parser.add_argument("b", help="Second inventory name or file")
        parser.add_argument("--from-style", metavar="NAME", help="Notation of file A")
        parser.add_argument("--to-style", metavar="NAME", help="Notation of file B")
        parser.add_argument(
            "--strip",
            choices=("stress", "prosodic", "none"),
            default="stress",
            help="Marks to strip before comparison (default: stress)",
        )
        parser.add_argument(
            "--coverage-at",
            metavar="DISTANCE",
            type=float,
            action="append",
            default=[],
            help="Report coverage within this caller-chosen raw distance",
        )
        add_applicable_only_arg(parser)
        add_format_arg(parser, ["text", "json", "tsv", "markdown"])
        add_output_arg(parser)

    def run(self) -> int:
        from ..inventories import inventories
        from ..inventory_comparison import inventory_comparison_report
        from ..inventory_renderers import (
            inventory_surface_view,
            render_inventory_json,
            render_inventory_markdown,
            render_inventory_text,
            render_inventory_tsv,
        )

        known = set(inventories())
        if any(value < 0 for value in self.args.coverage_at):
            return self.error("--coverage-at must be non-negative")

        def resolve(token: str):  # type: ignore[no-untyped-def]
            path = Path(token)
            if token in known and path.exists():
                raise ValueError(
                    f"{token} is both an inventory and a file here; "
                    f"write ./{token} for the file"
                )
            if token in known:
                return token
            if not path.exists():
                raise FileNotFoundError(
                    f"no inventory or file {token!r}; run 'ipakit inventory list' "
                    "for the names"
                )
            return path

        try:
            left, _ = inventory_surface_view(
                resolve(self.args.a), style=self.args.from_style, ipa=self.ipa
            )
            right, _ = inventory_surface_view(
                resolve(self.args.b), style=self.args.to_style, ipa=self.ipa
            )
            report = inventory_comparison_report(
                left,
                right,
                mapping="nearest",
                detail=True,
                coverage_at=tuple(self.args.coverage_at),
                ipa=self.ipa,
                strip=None if self.args.strip == "none" else self.args.strip,
                applicable_only=self.args.applicable_only,
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            return self.error(str(error))
        unreadable = [
            (label, member)
            for label, view in (("A", left), ("B", right))
            for member in view.members
            if member.status == "unreadable"
        ]
        for label, member in unreadable:
            print(
                f"Error: cannot read {member.source_token!r} on {label} side: "
                f"{member.reason}",
                file=sys.stderr,
            )
        if self.format == "json":
            self.output(render_inventory_json(report).rstrip("\n"))
        elif self.format == "tsv":
            self.output(render_inventory_tsv(report).rstrip("\n"))
        elif self.format == "markdown":
            self.output(render_inventory_markdown(report).rstrip("\n"))
        else:
            self.output(render_inventory_text(report).rstrip("\n"))
        return 3 if unreadable else 0


class DistanceGroup(CommandGroup):
    """Calculate phonetic distances between IPA phones, transcriptions, and phone sequences.

    Two flavors: 'pair'/'segment'/'matrix' give raw feature-distance magnitudes
    (0.0 identical to 1.0 maximal); 'positions' gives complementary
    percentile positions in a reference inventory, and 'transcription' aligns with
    substitution costs derived from those positions. Positions are not raw
    distances and are not comparable across inventories (scope them with
    --phoneset).

    Subcommands:
        pair           Feature distance between two base phones
        segment        Feature distance between complex segments (diacritics)
        matrix         Pairwise feature-distance matrix for multiple phones
        positions      Inventory-relative percentile positions (phones; alias pos)
        transcription  Alignment cost/similarity with position-derived substitutions
        directional    Directional reference-to-hypothesis transcription distance
        nearest        Best match of a form against a set of acceptable variants
        map            Map one phoneset onto another
        compare        Compare phonesets as sets, mappings, and a matrix
        seq            Distance between two pre-tokenized phone sequences
        metrics        Registered metric names
        across         Exact-token comparisons across selected metrics

    Examples:
        ipakit distance pair p b               # Raw feature distance: ~0.05
        ipakit distance positions p b          # inventory-relative
        ipakit distance transcription kæt kæd           # word similarity
        ipakit distance matrix p t k           # 3x3 comparison matrix
    """

    name = "distance"
    aliases: ClassVar[list[str]] = ["d"]
    help = (
        "Raw distances, inventory positions, and mapping (pair, segment, matrix, "
        "positions, transcription, directional, nearest, map, compare, seq, metrics, across)"
    )
    commands: ClassVar[list[type[Command]]] = [
        PairCommand,
        SegmentCommand,
        MatrixCommand,
        PositionsCommand,
        TranscriptionCommand,
        DirectionalCommand,
        NearestCommand,
        MapCommand,
        CompareCommand,
        SeqCommand,
        MetricsCommand,
        AcrossCommand,
    ]
