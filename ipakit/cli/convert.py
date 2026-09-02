"""Convert commands - notation conversion and lossless form serialization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import ClassVar

from ..models import Phoneset
from .base import (
    IPA,
    Command,
    CommandGroup,
    add_convert_strict_arg,
    add_format_arg,
)


class ToCmuCommand(Command):
    """Convert IPA string to CMU ARPABET symbols.

    CMU ARPABET is the phonetic alphabet used by the CMU Pronouncing Dictionary.
    Vowels include stress markers (0=no stress, 1=primary, 2=secondary).

    Examples:
        ipakit convert to-cmu "kæt"        # K AE0 T
        ipakit convert to-cmu "ˈhɛlo͜ʊ"    # HH EH1 L OW0
        ipakit c to-cmu "kæt" --no-stress  # K AE T
        ipakit c to-cmu "kæt" -f json      # ["K", "AE0", "T"]
        ipakit c to-cmu "k4t" --strict     # error: unknown symbols ['4']
    """

    name = "to-cmu"
    aliases: ClassVar[list[str]] = []
    help = "Convert IPA to CMU ARPABET (e.g., 'kæt' → 'K AE0 T')"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        parser.add_argument(
            "--no-stress", action="store_true", help="Omit stress markers from vowels"
        )
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        result = self.cmu.ipa_to_cmu(
            self.args.ipa,
            with_stress=not self.args.no_stress,
            strict=self.args.strict,
        )
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(" ".join(result))
        return 0


class FromCmuCommand(Command):
    """Convert CMU ARPABET symbols to IPA string.

    Accepts space-separated CMU symbols. Stress markers on vowels
    are converted to IPA stress marks (ˈ for primary, ˌ for secondary).

    Examples:
        ipakit convert from-cmu K AE1 T      # kˈæt
        ipakit convert from-cmu HH EH1 L OW0 # hˈɛlo͡ʊ
        ipakit c from-cmu P IY1 T S AH0      # pˈitsə
    """

    name = "from-cmu"
    aliases: ClassVar[list[str]] = []
    help = "Convert CMU ARPABET to IPA (e.g., 'K AE1 T' → 'kˈæt')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "cmu", nargs="+", help="CMU symbols (space-separated, e.g., K AE1 T)"
        )
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        symbols = (
            self.args.cmu if isinstance(self.args.cmu, list) else self.args.cmu.split()
        )
        result = self.cmu.cmu_to_ipa(symbols, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class ToXsampaCommand(Command):
    """Convert IPA string to X-SAMPA notation.

    X-SAMPA is an ASCII representation of IPA, useful for systems
    that cannot display Unicode IPA characters.

    Examples:
        ipakit convert to-xsampa "ʃɑ"      # SA
        ipakit convert to-xsampa "kæt"     # k{t
        ipakit c to-xsampa "θɪŋk"          # TINk
    """

    name = "to-xsampa"
    aliases: ClassVar[list[str]] = []
    help = "Convert IPA to X-SAMPA ASCII notation"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        result = self.ipa.to_xsampa(self.args.ipa, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class FromXsampaCommand(Command):
    """Convert X-SAMPA notation to IPA string.

    X-SAMPA uses ASCII characters to represent IPA symbols.
    Uppercase letters typically map to IPA extensions.

    Examples:
        ipakit convert from-xsampa "SA"    # ʃɑ
        ipakit convert from-xsampa "k{t"   # kæt
        ipakit c from-xsampa "TINk"        # θɪŋk
    """

    name = "from-xsampa"
    reads_notation = "X-SAMPA"
    aliases: ClassVar[list[str]] = []
    help = "Convert X-SAMPA ASCII notation to IPA"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("xsampa", help="X-SAMPA string to convert")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        from .. import from_xsampa

        result = from_xsampa(self.args.xsampa, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class NormalizeCommand(Command):
    """Normalize an IPA string to canonical form.

    Applies normalizations including:
    - Converting legacy ligatures to tie-bar form (ʧ → t͡ʃ)
    - Joining space-separated segments

    Examples:
        ipakit convert normalize "tʃ"      # t͡ʃ (adds tie bar)
        ipakit convert normalize "ʧ"       # t͡ʃ (legacy ligature)
        ipakit c norm "tʃ eɪ n"            # t͡ʃe͡ɪn (ties added within segments)
    """

    name = "normalize"
    aliases: ClassVar[list[str]] = ["norm"]
    help = "Normalize IPA to canonical form (adds tie bars, resolves ligatures)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "ipa", help="IPA string to normalize (may be space-separated)"
        )
        parser.add_argument(
            "--delimiter",
            default="",
            metavar="SEP",
            help=(
                "Split the input on SEP and treat each piece as ONE phone, "
                "giving it the ties it was written without. Unset by "
                "default: nothing is tied, because a space here is the word "
                "separator and reading it as a phone separator would both "
                "invent ties and eat a boundary"
            ),
        )
        parser.add_argument(
            "--decompose",
            action="store_true",
            help=(
                "Emit NFD, every modifier its own character. The default is "
                "NFC, which is what downstream consumers expect"
            ),
        )
        add_format_arg(parser)

    def run(self) -> int:
        # The shell hands over a string, so splitting is done here where a
        # person chose the delimiter -- the library takes a sequence, and
        # never guesses that a space separates phones rather than words.
        result = self.ipa.normalize(
            self.args.ipa,
            delimiter=self.args.delimiter or None,
            compose=not self.args.decompose,
        )
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class TokenizeCommand(Command):
    """Tokenize an IPA string into individual segments.

    Splits IPA into phonological segments, keeping diacritics
    attached to their base characters and preserving affricates
    as single units.

    Examples:
        ipakit convert tokenize "kæt"      # k æ t
        ipakit convert tokenize "t͡ʃeɪnd͡ʒ" # t͡ʃ e ɪ n d͡ʒ
        ipakit c tok "pʰɪn" -f json        # ["pʰ", "ɪ", "n"]
    """

    name = "tokenize"
    aliases: ClassVar[list[str]] = ["tok"]
    help = "Split IPA string into segments (keeps diacritics attached)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to tokenize")
        add_format_arg(parser)

    def run(self) -> int:
        tokens = self.ipa.tokenize(self.args.ipa)
        if self.format == "json":
            self.output_json(tokens)
        else:
            self.print(" ".join(tokens))
        return 0


class ToJsonCommand(Command):
    """Parse IPA into the lean, versioned internal representation.

    Pass ``--self-contained`` to include resolved feature/prosody views and
    provenance for readers that do not carry the IPA inventory.

    Examples:
        ipakit convert to-json "#kæt.dɒɡ#"
        ipakit c to-json "kæt.ˈ.dɒɡ" --strict
    """

    name = "to-json"
    aliases: ClassVar[list[str]] = ["repr"]
    help = "Parse IPA into the complete JSON representation"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.add_argument("ipa", help="IPA string to parse")
        add_convert_strict_arg(parser)
        parser.add_argument(
            "--segmented", action="store_true", help="read whitespace-delimited units"
        )
        parser.add_argument("--wild", action="store_true", help="normalize wild IPA")
        parser.add_argument(
            "--self-contained",
            action="store_true",
            help="embed resolved segment views",
        )

    def run(self) -> int:
        self.output_json(
            self.ipa.read(
                self.args.ipa,
                strict=self.args.strict,
                segmented=self.args.segmented,
                wild=self.args.wild,
            ).to_dict(self_contained=self.args.self_contained)
        )
        return 0


class FromJsonCommand(Command):
    """Restore a JSON representation and emit its IPA spelling.

    Pass ``-`` to read JSON from standard input.

    Examples:
        ipakit convert from-json '{"v": 1, ...}'
        ipakit convert to-json "kæt" | ipakit convert from-json -
    """

    name = "from-json"
    aliases: ClassVar[list[str]] = []
    help = "Restore the JSON representation and emit IPA"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.add_argument("representation", help="JSON text, or - for stdin")

    def run(self) -> int:
        data = (
            sys.stdin.read()
            if self.args.representation == "-"
            else self.args.representation
        )
        self.print(self.ipa.read_json(data).to_ipa())
        return 0


class ToKatakanaCommand(Command):
    """Render an attested Japanese loanword adaptation in katakana.

    This is a small, fixture-backed gairaigo codec, not a Japanese-accent
    simulator.  Input must exactly match one of the attested IPA source forms;
    an unmapped form is refused rather than approximated.

    Examples:
        ipakit convert to-katakana "hɑt"       # ホット
        ipakit convert to-katakana "stɹa͜ɪk"   # ストライク
    """

    name = "to-katakana"
    aliases: ClassVar[list[str]] = []
    help = "Render an attested Japanese loanword adaptation (no approximation)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.add_argument("ipa", help="Attested source IPA form")

    def run(self) -> int:
        from .. import to_katakana

        try:
            rendered = to_katakana(self.args.ipa)
        except ValueError as error:
            return self.error(str(error))
        self.print(rendered)
        return 0


class AddTiesCommand(Command):
    """Tie the parts of a multi-segment phone into one.

    Used to write an affricate or a diphthong as the single phone it is,
    from components spelled without a tie.

    WHICH TIE IS NOT ONE CHOICE, and this is what the examples show. A
    junction between two vocalic parts takes the SEQUENTIAL TIE, U+035C
    COMBINING DOUBLE BREVE BELOW; every other junction takes the TIE BAR,
    U+0361 COMBINING DOUBLE INVERTED BREVE. So a diphthong and an
    affricate come back spelled differently, matching how ``ipa.xml``
    registers each. The choice is made per junction, so a run of three or
    more parts may carry both.

    Neither is the IPA undertie, U+203F, which links across a boundary
    and is a different mark for a different job.

    Examples:
        ipakit convert add-ties "ts"       # t͡s   (U+0361, affricate)
        ipakit convert add-ties "dʒ"       # d͡ʒ   (U+0361, affricate)
        ipakit c add-ties "aɪ"             # a͜ɪ   (U+035C, diphthong)
    """

    name = "add-ties"
    aliases: ClassVar[list[str]] = []
    help = "Add tie bars to create affricates/diphthongs (e.g., 'ts' → 't͡s')"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "segment", help="Segment to add tie bars to (e.g., 'ts', 'dʒ', 'aɪ')"
        )
        add_format_arg(parser)

    def run(self) -> int:
        result = self.ipa.add_ties(self.args.segment)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class ToTimitCommand(Command):
    """Convert IPA string to TIMIT phoneset symbols.

    TIMIT is a 61-phone set used in speech recognition research.
    Symbols are lowercase (unlike CMU ARPABET).

    Examples:
        ipakit convert to-timit "kæt"          # k ae t
        ipakit convert to-timit "hɛloʊ"        # hh eh l ow
        ipakit c to-timit "ʃɑk" -f json        # ["sh", "aa", "k"]
    """

    name = "to-timit"
    aliases: ClassVar[list[str]] = []
    help = "Convert IPA to TIMIT phoneset (e.g., 'kæt' → 'k ae t')"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        from ..phonemaps import to_timit

        result = to_timit(self.args.ipa, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(" ".join(result))
        return 0


class FromTimitCommand(Command):
    """Convert TIMIT phoneset symbols to IPA string.

    Accepts space-separated TIMIT symbols.

    Examples:
        ipakit convert from-timit k ae t       # kæt
        ipakit convert from-timit hh eh l ow   # hɛlo͡ʊ
        ipakit c from-timit sh aa k            # ʃɑk
    """

    name = "from-timit"
    aliases: ClassVar[list[str]] = []
    help = "Convert TIMIT phoneset to IPA (e.g., 'k ae t' → 'kæt')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("timit", nargs="+", help="TIMIT symbols (space-separated)")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        from ..phonemaps import from_timit

        result = from_timit(self.args.timit, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class ToKirshenbaumCommand(Command):
    """Convert IPA string to Kirshenbaum ASCII-IPA notation.

    Kirshenbaum is an ASCII representation of IPA for plain text/email.
    Uses uppercase for IPA extensions (S = ʃ, T = θ, etc.).

    Examples:
        ipakit convert to-kirshenbaum "ʃɑk"    # SAk
        ipakit convert to-kirshenbaum "kæt"    # k&t
        ipakit c to-kirsh "θɪŋk"               # TINk
    """

    name = "to-kirshenbaum"
    aliases: ClassVar[list[str]] = ["to-kirsh"]
    help = "Convert IPA to Kirshenbaum ASCII (e.g., 'ʃɑk' → 'SAk')"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        from ..phonemaps import to_kirshenbaum

        result = to_kirshenbaum(self.args.ipa, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class FromKirshenbaumCommand(Command):
    """Convert Kirshenbaum ASCII-IPA notation to IPA string.

    Parses Kirshenbaum ASCII representation and converts to IPA Unicode.

    Examples:
        ipakit convert from-kirshenbaum "SAk"  # ʃɑk
        ipakit convert from-kirshenbaum "k&t"  # kæt
        ipakit c from-kirsh "TINk"             # θɪŋk
    """

    name = "from-kirshenbaum"
    reads_notation = "Kirshenbaum"
    aliases: ClassVar[list[str]] = ["from-kirsh"]
    help = "Convert Kirshenbaum ASCII to IPA (e.g., 'SAk' → 'ʃɑk')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("kirshenbaum", help="Kirshenbaum string to convert")
        add_format_arg(parser)
        add_convert_strict_arg(parser)

    def run(self) -> int:
        from ..phonemaps import from_kirshenbaum

        result = from_kirshenbaum(self.args.kirshenbaum, strict=self.args.strict)
        if self.format == "json":
            self.output_json(result)
        else:
            self.print(result)
        return 0


class PhonesetCommand(Command):
    """Read a phoneset file that may be wild, write it in house style.

    A phoneset file is one phone per line, and the delimiting is what
    this command trusts: each line names a single phone, so anything
    that does not read as one is repaired rather than reinterpreted.

    Two different repairs, and they are not the same kind of thing:

    WILD SPELLINGS are text that is not house-style IPA -- the ASCII
    stand-ins ``g``, ``:``, ``?`` and ``'``, and tie conventions written
    the other way round. These go through ``from_wild``, which is where
    every soft read in the library lives.

    MISSING TIES are different. ``aɪ`` is well-formed IPA already, and
    means a SEQUENCE of two vowels; ``a͜ɪ`` means ONE diphthong. Nothing
    about the text says which was meant -- the DELIMITER does, because
    the file put it on one line. So a line parsing to more than one
    segment gets the ties it left out, at each junction, and a line that
    already reads as one phone is copied through byte for byte whatever
    convention it used.

    Every change is listed on stderr, so nothing is rewritten silently,
    and a line that cannot be read as one phone even after both repairs
    fails the run rather than being dropped from the output.

    Examples:
        ipakit convert phoneset en.phones
        ipakit convert phoneset en.phones -o en-house.phones
        ipakit convert phoneset wild.txt --quiet      # no change report
    """

    name = "phoneset"
    aliases: ClassVar[list[str]] = []
    help = "Rewrite a phoneset file in house style (wild spellings, missing ties)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("file", type=Path, help="Phoneset file, one phone per line")
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            metavar="FILE",
            help="Write here instead of standard output",
        )
        parser.add_argument(
            "--no-tie",
            action="store_true",
            help="Canonicalize wild spellings only; leave untied entries as written",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Do not list the changed entries on stderr",
        )

    def run(self) -> int:
        if not Path(self.args.file).exists():
            return self.error(f"No such phoneset file: {self.args.file}")
        source = Phoneset.from_file(self.args.file)

        out: list[str] = []
        wild: list[tuple[str, str]] = []
        tied: list[tuple[str, str]] = []
        refused: list[str] = []
        for member in source.phones:
            house = self.ipa.from_wild(member)
            if house != member:
                wild.append((member, house))
            if not self.args.no_tie and len(self.ipa.segments(house)) > 1:
                candidate = self.ipa.add_ties(house)
                if len(self.ipa.segments(candidate)) == 1:
                    tied.append((house, candidate))
                    house = candidate
                else:
                    refused.append(member)
            out.append(house)

        if refused:
            for member in refused:
                print(
                    f"cannot read {member!r} as one phone: its parts do not "
                    "compose, and a tie will not fix that",
                    file=sys.stderr,
                )
            return self.error(f"{len(refused)} entr(ies) unreadable; nothing written")

        text = "\n".join(out) + "\n"
        if self.args.output:
            Path(self.args.output).write_text(text, encoding="utf-8")
        else:
            self.print(text.rstrip("\n"))

        if not self.args.quiet:
            for before, after in wild:
                print(f"wild spelling: {before} -> {after}", file=sys.stderr)
            for before, after in tied:
                print(f"tied: {before} -> {after}", file=sys.stderr)
            unchanged = len(source.phones) - len(wild) - len(tied)
            print(
                f"{len(source.phones)} entries: {unchanged} unchanged, "
                f"{len(wild)} wild spelling(s), {len(tied)} tied",
                file=sys.stderr,
            )
        return 0


class ConvertGroup(CommandGroup):
    """Convert between IPA and various phonetic notations.

    Subcommands:
        to-cmu         IPA → CMU ARPABET (speech synthesis)
        from-cmu         CMU ARPABET → IPA
        to-xsampa      IPA → X-SAMPA (ASCII)
        from-xsampa    X-SAMPA → IPA
        to-timit       IPA → TIMIT (speech recognition)
        from-timit     TIMIT → IPA
        to-kirshenbaum IPA → Kirshenbaum ASCII-IPA
        from-kirshenbaum Kirshenbaum → IPA
        to-json       IPA → versioned Form JSON
        from-json     versioned Form JSON → IPA
        to-katakana   Attested Japanese loanword adaptation → katakana
        normalize      Canonicalize IPA (tie bars, ligatures)
        tokenize       Split IPA into segments
        add-ties       Create affricates/diphthongs with tie bars
    """

    name = "convert"
    aliases: ClassVar[list[str]] = ["c"]
    help = "Convert notation, serialize forms, and render attested adaptations"
    commands: ClassVar[list[type[Command]]] = [
        ToCmuCommand,
        FromCmuCommand,
        ToXsampaCommand,
        FromXsampaCommand,
        ToTimitCommand,
        FromTimitCommand,
        ToKirshenbaumCommand,
        FromKirshenbaumCommand,
        NormalizeCommand,
        TokenizeCommand,
        ToJsonCommand,
        FromJsonCommand,
        ToKatakanaCommand,
        AddTiesCommand,
        PhonesetCommand,
    ]
