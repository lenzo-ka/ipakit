"""Convert commands - format conversions between IPA, CMU, and X-SAMPA."""

from __future__ import annotations

import argparse

from .base import Command, CommandGroup, add_format_arg


class ToCmuCommand(Command):
    """Convert IPA string to CMU ARPABET symbols.

    CMU ARPABET is the phonetic alphabet used by the CMU Pronouncing Dictionary.
    Vowels include stress markers (0=no stress, 1=primary, 2=secondary).

    Examples:
        ipakit convert to-cmu "kæt"        # K AE0 T
        ipakit convert to-cmu "ˈhɛloʊ"     # HH EH1 L OW0
        ipakit c to-cmu "kæt" --no-stress  # K AE T
        ipakit c to-cmu "kæt" -f json      # ["K", "AE0", "T"]
    """

    name = "to-cmu"
    aliases = []
    help = "Convert IPA to CMU ARPABET (e.g., 'kæt' → 'K AE0 T')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        parser.add_argument(
            "--no-stress", action="store_true", help="Omit stress markers from vowels"
        )
        add_format_arg(parser)

    def run(self) -> int:
        result = self.cmu.ipa_to_cmu(self.args.ipa, with_stress=not self.args.no_stress)
        if self.format == "json":
            self.output_json(result)
        else:
            print(" ".join(result))
        return 0


class ToIpaCommand(Command):
    """Convert CMU ARPABET symbols to IPA string.

    Accepts space-separated CMU symbols. Stress markers on vowels
    are converted to IPA stress marks (ˈ for primary, ˌ for secondary).

    Examples:
        ipakit convert to-ipa K AE1 T      # kˈæt
        ipakit convert to-ipa HH EH1 L OW0 # hˈɛlo͡ʊ
        ipakit c to-ipa P IY1 T S AH0      # pˈitsə
    """

    name = "to-ipa"
    aliases = []
    help = "Convert CMU ARPABET to IPA (e.g., 'K AE1 T' → 'kˈæt')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "cmu", nargs="+", help="CMU symbols (space-separated, e.g., K AE1 T)"
        )

    def run(self) -> int:
        symbols = (
            self.args.cmu if isinstance(self.args.cmu, list) else self.args.cmu.split()
        )
        result = self.cmu.cmu_to_ipa(symbols)
        print(result)
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
    aliases = []
    help = "Convert IPA to X-SAMPA ASCII notation"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")

    def run(self) -> int:
        result = self.ipa.ipa_to_xsampa(self.args.ipa)
        print(result)
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
    aliases = []
    help = "Convert X-SAMPA ASCII notation to IPA"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("xsampa", help="X-SAMPA string to convert")

    def run(self) -> int:
        from .. import xsampa_to_ipa

        result = xsampa_to_ipa(self.args.xsampa)
        print(result)
        return 0


class NormalizeCommand(Command):
    """Normalize an IPA string to canonical form.

    Applies normalizations including:
    - Converting legacy ligatures to tie-bar form (ʧ → t͡ʃ)
    - Converting tie-bar-below to tie-bar-above (t͜ʃ → t͡ʃ)
    - Joining space-separated segments

    Examples:
        ipakit convert normalize "tʃ"      # t͡ʃ (adds tie bar)
        ipakit convert normalize "ʧ"       # t͡ʃ (legacy ligature)
        ipakit c norm "tʃ eɪ n"            # t͡ʃe͡ɪn (ties added within segments)
    """

    name = "normalize"
    aliases = ["norm"]
    help = "Normalize IPA to canonical form (adds tie bars, resolves ligatures)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "ipa", help="IPA string to normalize (may be space-separated)"
        )

    def run(self) -> int:
        result = self.ipa.normalize_ipa(self.args.ipa)
        print(result)
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
    aliases = ["tok"]
    help = "Split IPA string into segments (keeps diacritics attached)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to tokenize")
        add_format_arg(parser)

    def run(self) -> int:
        tokens = self.ipa.tokenize_ipa(self.args.ipa)
        if self.format == "json":
            self.output_json(tokens)
        else:
            print(" ".join(tokens))
        return 0


class AddTiesCommand(Command):
    """Add tie bars between phones in a multi-phone segment.

    Used to create affricates and diphthongs from their components.
    The tie bar (◌͡◌) indicates co-articulation.

    Examples:
        ipakit convert add-ties "ts"       # t͡s
        ipakit convert add-ties "dʒ"       # d͡ʒ
        ipakit c add-ties "aɪ"             # a͡ɪ (diphthong)
    """

    name = "add-ties"
    aliases = []
    help = "Add tie bars to create affricates/diphthongs (e.g., 'ts' → 't͡s')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "segment", help="Segment to add tie bars to (e.g., 'ts', 'dʒ', 'aɪ')"
        )

    def run(self) -> int:
        result = self.ipa.add_tie_bars(self.args.segment)
        print(result)
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
    aliases = []
    help = "Convert IPA to TIMIT phoneset (e.g., 'kæt' → 'k ae t')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")
        add_format_arg(parser)

    def run(self) -> int:
        from ..phonemaps import to_timit

        result = to_timit(self.args.ipa)
        if self.format == "json":
            self.output_json(result)
        else:
            print(" ".join(result))
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
    aliases = []
    help = "Convert TIMIT phoneset to IPA (e.g., 'k ae t' → 'kæt')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("timit", nargs="+", help="TIMIT symbols (space-separated)")

    def run(self) -> int:
        from ..phonemaps import from_timit

        result = from_timit(self.args.timit)
        print(result)
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
    aliases = ["to-kirsh"]
    help = "Convert IPA to Kirshenbaum ASCII (e.g., 'ʃɑk' → 'SAk')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("ipa", help="IPA string to convert")

    def run(self) -> int:
        from ..phonemaps import to_kirshenbaum

        result = to_kirshenbaum(self.args.ipa)
        print(result)
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
    aliases = ["from-kirsh"]
    help = "Convert Kirshenbaum ASCII to IPA (e.g., 'SAk' → 'ʃɑk')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument("kirshenbaum", help="Kirshenbaum string to convert")

    def run(self) -> int:
        from ..phonemaps import from_kirshenbaum

        result = from_kirshenbaum(self.args.kirshenbaum)
        print(result)
        return 0


class ConvertGroup(CommandGroup):
    """Convert between IPA and various phonetic notations.

    Subcommands:
        to-cmu         IPA → CMU ARPABET (speech synthesis)
        to-ipa         CMU ARPABET → IPA
        to-xsampa      IPA → X-SAMPA (ASCII)
        from-xsampa    X-SAMPA → IPA
        to-timit       IPA → TIMIT (speech recognition)
        from-timit     TIMIT → IPA
        to-kirshenbaum IPA → Kirshenbaum ASCII-IPA
        from-kirshenbaum Kirshenbaum → IPA
        normalize      Canonicalize IPA (tie bars, ligatures)
        tokenize       Split IPA into segments
        add-ties       Create affricates/diphthongs with tie bars
    """

    name = "convert"
    aliases = ["c"]
    help = "Convert between IPA, CMU, X-SAMPA, TIMIT, Kirshenbaum"
    commands = [
        ToCmuCommand,
        ToIpaCommand,
        ToXsampaCommand,
        FromXsampaCommand,
        ToTimitCommand,
        FromTimitCommand,
        ToKirshenbaumCommand,
        FromKirshenbaumCommand,
        NormalizeCommand,
        TokenizeCommand,
        AddTiesCommand,
    ]
