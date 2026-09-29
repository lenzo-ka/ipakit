#!/usr/bin/env python3
"""Generate ipakit's TIMIT-label-to-house-IPA phonemap."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "ipakit" / "data" / "phonemaps" / "timit.xml"
SOURCE = "NISTIR 4930 §4.3"
SOURCE_URL = "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir4930.pdf"


@dataclass(frozen=True)
class Row:
    """One TIMIT label, its house IPA, and the NIST definition transcribed."""

    ipa: str
    timit: str
    citation: str


@dataclass(frozen=True)
class Group:
    """A rendered section of the phonemap."""

    title: str
    rows: tuple[Row, ...]


def row(ipa: str, timit: str, description: str) -> Row:
    """Attach the common section citation to one compact source description."""
    return Row(ipa, timit, f"{SOURCE}: {description}")


GROUPS = (
    Group(
        "Silence",
        (row("␣", "h#", "begin/end marker for silence or non-speech events"),),
    ),
    Group(
        "Vowels",
        (
            row("i", "iy", "vowel table, iy as in “beet”"),
            row("ɪ", "ih", "vowel table, ih as in “bit”"),
            row("ɛ", "eh", "vowel table, eh as in “bet”"),
            row("æ", "ae", "vowel table, ae as in “bat”"),
            row("ɑ", "aa", "vowel table, aa as in “bott”"),
            row("ɔ", "ao", "vowel table, ao as in “bought”"),
            row("ʊ", "uh", "vowel table, uh as in “book”"),
            row("u", "uw", "vowel table, uw as in “boot”"),
            row("ʌ", "ah", "vowel table, ah as in “but”"),
            row("ə", "ax", "vowel table, ax as in “about”"),
            row("ɚ", "axr", "vowel table, axr as in “butter”"),
            row("ɝ", "er", "vowel table, er as in “bird”"),
            row("ɨ", "ix", "vowel table, ix as in “debit”"),
        ),
    ),
    Group(
        "Diphthongs",
        (
            row("e͜ɪ", "ey", "vowel table, ey as in “bait”"),
            row("o͜ʊ", "ow", "vowel table, ow as in “boat”"),
            row("a͜ɪ", "ay", "vowel table, ay as in “bite”"),
            row("a͜ʊ", "aw", "vowel table, aw as in “bout”"),
            row("ɔ͜ɪ", "oy", "vowel table, oy as in “boy”"),
        ),
    ),
    Group(
        "Semivowels and glides",
        (
            row("j", "y", "semivowels and glides table, y as in “yacht”"),
            row("w", "w", "semivowels and glides table, w as in “way”"),
            row("ɹ", "r", "semivowels and glides table, r as in “ray”"),
            row("l", "l", "semivowels and glides table, l as in “lay”"),
        ),
    ),
    Group(
        "Nasals",
        (
            row("m", "m", "nasal table, m as in “mom”"),
            row("n", "n", "nasal table, n as in “noon”"),
            row("ŋ", "ng", "nasal table, ng as in “sing”"),
            row("m̩", "em", "nasal table, syllabic em as in “bottom”"),
            row("n̩", "en", "nasal table, syllabic en as in “button”"),
            row("ŋ̩", "eng", "nasal table, syllabic eng as in “Washington”"),
        ),
    ),
    Group(
        "Fricatives",
        (
            row("f", "f", "fricative table, f as in “fin”"),
            row("v", "v", "fricative table, v as in “van”"),
            row("θ", "th", "fricative table, th as in “thin”"),
            row("ð", "dh", "fricative table, dh as in “then”"),
            row("s", "s", "fricative table, s as in “sea”"),
            row("z", "z", "fricative table, z as in “zone”"),
            row("ʃ", "sh", "fricative table, sh as in “she”"),
            row("ʒ", "zh", "fricative table, zh as in “azure”"),
            row("h", "hh", "semivowels and glides table, hh as in “hay”"),
            row("ɦ", "hv", "voiced h, typically intervocalic; example “ahead”"),
        ),
    ),
    Group(
        "Affricates",
        (
            row("t͡ʃ", "ch", "affricate table, ch as in “choke”"),
            row("d͡ʒ", "jh", "affricate table, jh as in “joke”"),
        ),
    ),
    Group(
        "Plosives",
        (
            row("p", "p", "stop table, p as in “pea”"),
            row("b", "b", "stop table, b as in “bee”"),
            row("t", "t", "stop table, t as in “tea”"),
            row("d", "d", "stop table, d as in “day”"),
            row("k", "k", "stop table, k as in “key”"),
            row("ɡ", "g", "stop table, g as in “gay”"),
            row("ʔ", "q", "glottal stop; table example “bat”"),
        ),
    ),
    Group(
        "Flaps",
        (
            row("ɾ", "dx", "flap, as in “muddy” or “dirty”"),
            row("ɾ̃", "nx", "nasal flap, as in “winner”"),
        ),
    ),
)

EXTRA_GROUPS = (
    Group(
        "Stop closure intervals",
        (
            row("p̚", "pcl", "closure interval of p, distinct from its release"),
            row("b̚", "bcl", "closure interval of b, distinct from its release"),
            row("t̚", "tcl", "closure interval of t, distinct from its release"),
            row("d̚", "dcl", "closure interval of d, distinct from its release"),
            row("k̚", "kcl", "closure interval of k, distinct from its release"),
            row("ɡ̚", "gcl", "closure interval of g, distinct from its release"),
        ),
    ),
    Group(
        "Additional allophones",
        (
            row("l̩", "el", "semivowels and glides table, syllabic el as in “bottle”"),
            row("u̟", "ux", "fronted u, an allophone of uw in alveolar contexts"),
            row("ə̥", "ax-h", "short devoiced schwa between voiceless consonants"),
        ),
    ),
    Group(
        "Additional silence labels",
        (
            row("␣", "epi", "epenthetic silence, as in “slow”"),
            row("␣", "pau", "pause"),
        ),
    ),
)

TIMIT_ROWS = tuple(row_ for group in (*GROUPS, *EXTRA_GROUPS) for row_ in group.rows)
ROWS_BY_LABEL = {row_.timit: row_ for row_ in TIMIT_ROWS}


def _map_line(item: Row, indent: str = "    ") -> str:
    return (
        f"{indent}<map ipa={quoteattr(item.ipa)} timit={quoteattr(item.timit)} "
        f"note={quoteattr(item.citation)}/>"
    )


def render() -> str:
    """Render the complete 61-label declaration deterministically."""
    if len(TIMIT_ROWS) != 61 or len(ROWS_BY_LABEL) != 61:
        raise ValueError("the TIMIT table must contain 61 unique labels")
    if any(not item.citation.startswith(f"{SOURCE}:") for item in TIMIT_ROWS):
        raise ValueError("every TIMIT label needs a NISTIR 4930 §4.3 citation")

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        (
            '<phonemap description="IPA to TIMIT phoneset" from="ipa" to="timit" '
            f"upstream={quoteattr(SOURCE)} upstream-url={quoteattr(SOURCE_URL)} "
            'artifact="Phonetic and Phonemic Symbol Codes transcribed to house IPA" '
            'version="NISTIR 4930 (February 1993)" license="BSD-2-Clause" '
            'kind="speech-corpus-phone-map">'
        ),
        "    <!--",
        "    This ipakit-authored BSD-2-Clause map transcribes the TIMIT corpus",
        "    labels documented by Garofolo et al., NISTIR 4930 (February 1993),",
        '    §4.3, "Phonetic and Phonemic Symbol Codes," printed pp. 29–31.',
        "    NIST defines the labels; the house IPA spellings are ipakit's work.",
        "    -->",
        "",
    ]
    for group in GROUPS:
        lines.append(f"    <!-- {group.title} -->")
        lines.extend(_map_line(item) for item in group.rows)
        lines.append("")
    lines.append("    <extras>")
    for group in EXTRA_GROUPS:
        lines.append(f"        <!-- {group.title} -->")
        lines.extend(_map_line(item, "        ") for item in group.rows)
        lines.append("")
    lines[-1] = "    </extras>"
    lines.append("</phonemap>")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the generated map, print it, or check the shipped bytes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "check"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    rendered = render()
    if args.action == "generate":
        if args.write:
            OUTPUT.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    shipped = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
    if shipped != rendered:
        print(
            "timit-map: generated artifact differs; run "
            "scripts/timit_map.py generate --write",
            file=sys.stderr,
        )
        return 1
    print("OK: TIMIT phonemap matches its generator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
