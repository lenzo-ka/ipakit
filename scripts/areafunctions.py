#!/usr/bin/env python3
"""Measure ipakit's tract geometry against MRI-derived vocal tract area functions.

ipakit places every phone at an ``(arc, offset)`` in a normalized tract, where
``arc`` is proportional position along the midline, 0 at the lips to 1 at the
glottis. Those anchors were hand-placed. This script holds them against a
published measurement of the same quantity:

    Story, Brad H., Ingo R. Titze and Eric A. Hoffman (1996).
    "Vocal tract area functions from magnetic resonance imaging",
    J. Acoust. Soc. Am. 100(1), 537-554.  https://doi.org/10.1121/1.415960

Table III (p. 546) gives equal-interval area functions -- cross-sectional area
in cm^2 every 0.396825 cm from the glottis -- for 18 vocal tract shapes from one
adult male subject: 12 vowels, 3 nasals and 3 plosives, each with its measured
tract length. Dividing distance-from-glottis by tract length gives exactly the
quantity ``arc`` claims to be, so the two can be compared without fitting.

    python scripts/areafunctions.py table        # parse it, and check the parse
    python scripts/areafunctions.py occlusions   # declared place vs measured closure
    python scripts/areafunctions.py vowels       # every supralaryngeal local minimum
    python scripts/areafunctions.py stability    # what a rank correlation depends on
    python scripts/areafunctions.py bands        # two sources against one band each
    python scripts/areafunctions.py replicate    # does a coordinate reproduce?
    python scripts/areafunctions.py intra        # ... for one speaker, twice?
    python scripts/areafunctions.py anchors      # where the four locations sit
    python scripts/areafunctions.py all

The paper is copyrighted and is NOT bundled: CI will not have it, so every
subcommand exits 0 with a message when it is absent. Point ``--source`` at a
plain-text extraction of your own copy, or set ``$IPAKIT_STORY1996_TEXT``.

``table`` asserts the shape of what it read -- 18 columns, the published tract
lengths, and section counts that predict every short row in the table -- so a
run over a bad extraction fails loudly instead of reporting clean numbers over
nothing. See docs/reviewing.md for why, and docs/design/tract-validation.md for
what the numbers turned out to be, which of them survive, and which do not.

The vowel symbols in the PDF's text layer are custom-encoded and unreadable.
They are not used. Column order comes from the example words in Table II
(p. 539), which extract cleanly, and is confirmed independently by the natural
speech formants in Table IV (p. 548) against Peterson & Barney (1952).
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import (  # noqa: E402
    MidlinePoint,
    head,
    landmarks,
    tract_point,
)

#: Environment variable naming a text extraction of the paper. No default path
#: is baked in: the paper is copyrighted, not redistributable, and a path from
#: one machine is noise in the repository and a broken default everywhere else.
SOURCE_ENV = "IPAKIT_STORY1996_TEXT"

#: The section interval, stated in the caption of Table III.
INTERVAL_CM = 0.396825

#: The 18 imaged shapes, in the column order of Table III, which is the order
#: of Table II. Named by the example word Table II gives, because that is what
#: the text layer preserves; the IPA symbol is this reader's reading of it.
SHAPES: tuple[tuple[str, str, float], ...] = (
    ("i", "heed", 16.67),
    ("ɪ", "hid", 16.67),
    ("ɛ", "head", 15.88),
    ("æ", "had", 16.67),
    ("ʌ", "ton", 17.46),
    ("ɑ", "hod", 17.46),
    ("ɔ", "paw", 17.46),
    ("o", "hoe", 17.46),
    ("ʊ", "hood", 17.46),
    ("u", "who", 18.25),
    ("ɝ", "earth", 17.46),
    ("l", "lump", 18.25),
    ("m", "mum", 17.46),
    ("n", "numb", 17.46),
    ("ŋ", "ung", 17.46),
    ("p", "puck", 17.46),
    ("t", "tuck", 17.46),
    ("k", "cut", 17.46),
)

#: The vowels, in Table III order. ``l`` is imaged and reported with them --
#: "any open tract shape was considered to be a vowel" (p. 544) -- but it is a
#: lateral, and a mid-sagittal area function is the one plane that cannot see
#: what makes it one, so it is left out of every vowel comparison here.
VOWELS = tuple(sym for sym, _, _ in SHAPES[:11])

#: The occluded shapes. Their constriction is where the area is zero, which the
#: data states outright -- no window to choose and no minimum to be fragile.
OCCLUDED = ("p", "m", "t", "n", "k", "ŋ")

#: Story et al. (p. 544): the tract "shows a widening ... that starts at 2 to 3
#: cm and narrows again at approximately 4 to 5 cm", the piriform sinuses
#: merging into the main tube. That narrowing is in every shape and is not a
#: lingual constriction, so a minimum-seeking read has to start above it -- and
#: nothing fixes where. This is the free parameter ``stability`` measures.
DEFAULT_GLOTTAL_CM = 5.0

#: The labial end, excluded for the same reason in the other direction: a
#: rounded vowel's narrowest section is its lip aperture, which Gaines et al.
#: (2021) measure as a separate task parameter from tongue body constriction,
#: and which a vowel's ``arc`` does not claim to describe. Over 1 to 4 cm this
#: changes nothing; it is a parameter so that can be seen rather than asserted.
DEFAULT_LABIAL_CM = 2.0

#: How much wider than its narrowest section a constriction may be and still
#: count as the same constriction. There is no principled value, so ``bands``
#: sweeps it and prints the sweep: a verdict that moves across this range is a
#: report of the factor, the way the rank correlation was a report of the
#: cutoff.
DEPTH_FACTORS = (1.25, 1.5, 2.0, 3.0, 4.0)

#: The second measured source, and the only one that covers more than one
#: speaker:
#:
#:     Wood, Sidney (1979). "A radiographic analysis of constriction locations
#:     for vowels", J. Phonetics 7(1), 25-43.
#:     https://doi.org/10.1016/S0095-4470(19)31031-9
#:
#: 38 sets of mid-sagittal tracings from the literature covering 12 languages,
#: plus new X-ray motion films of Southern British English and Egyptian Arabic
#: -- "confirms these four constriction locations without exception by 40
#: subjects in 13 languages" (p. 27). The tongue narrows the tract at one of
#: four locations, and conclusion 2 (p. 41) gives each one its family: "[i-ɛ,
#: y-ø]-like, [u-ʊ, ɨ]-like, [o-ɔ, ɣ]-like and [ɑ-a-æ]-like respectively".
#:
#: The distance is from the glottal source, and is the value Wood feeds to the
#: Stevens & House (1955) nomograms in his Fig. 5 (p. 30). It is a location, not
#: a measured band: Wood anchors the four anatomically and tabulates no extent.
#: Reading it as an ``arc`` therefore divides by a tract length -- each shape's
#: own published length, so that no single divisor is chosen here.
#:
#: ``ʌ`` is named in no family. Fig. 5 superimposes Southern British English
#: vowel areas on the four nomogram surfaces and puts it on the lower pharyngeal
#: one with ``æ`` and ``ɑ``, which is what it is read as here. The band it lands
#: in below spans 0.50 to the glottis, so both readings of it are inside and no
#: verdict here turns on the choice.
#:
#: ``ɝ`` is imaged by Story et al. and has no family: Wood's four cover the
#: cardinal space and not the American English rhotic.
WOOD_LOCATIONS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("hard palate", 12.0, ("i", "ɪ", "ɛ")),
    ("soft palate", 8.5, ("u", "ʊ")),
    ("upper pharynx", 6.5, ("o", "ɔ")),
    ("lower pharynx", 4.5, ("ɑ", "æ", "ʌ")),
)

#: The tract length the Stevens & House (1955) three-parameter model uses, and
#: so the divisor that turns Wood's four distances into proportions.
WOOD_REFERENCE_CM = 17.5

#: What ipakit already calls each of Wood's four locations. The names line up
#: exactly -- hard palate, soft palate, upper pharynx, lower pharynx against
#: palatal, velar, uvular, pharyngeal -- and the arcs do not, so adopting the
#: classification and keeping the declared place arcs are two different changes.
#: ``anchors`` measures the difference rather than arguing it. The arcs on this
#: side are read live from ``ipa.xml`` and are not repeated here.
WOOD_AS_PLACE = {
    "hard palate": "palatal",
    "soft palate": "velar",
    "upper pharynx": "uvular",
    "lower pharynx": "pharyngeal",
}

#: The third source, and the only measured one covering more than one speaker:
#:
#:     Yang, Ching-Shyang and Hideki Kasuya (1994). "Accurate measurement of
#:     vocal tract shapes from magnetic resonance images of child, female and
#:     male subjects", ICSLP 94, Yokohama, 623-626.
#:     https://doi.org/10.21437/ICSLP.1994-158
#:
#: Tables 1-3 (p. 625) give equi-length area functions for the five Japanese
#: vowels from an adult male, an adult female and a boy -- 15 in all, each with
#: its own printed tract length ``L`` and section length ``dl``. Sections are
#: "numbered from the glottis to the lips, indicating the last one to be the
#: area of the lip opening" (p. 625), the opposite end from Story et al.
#:
#: The scan has no text layer, so ``--second`` wants a CSV of the three tables:
#: a header ``subject,vowel,L_cm,dl_cm,section,area_cm2`` and one row per
#: section. ``replicate`` re-derives ``L`` from the section count and ``dl`` and
#: fails if the two disagree, which is what a transcription of a table can be
#: checked against without the table.
SECOND_ENV = "IPAKIT_YANG1994_CSV"

#: The fourth source, and the only one that images the same speaker twice:
#:
#:     Story, Brad H. (2008). "Comparison of magnetic resonance imaging-based
#:     vocal tract area functions obtained from the same speaker in 1994 and
#:     2002", J. Acoust. Soc. Am. 123(1), 327-335.
#:     https://doi.org/10.1121/1.2805683
#:
#: Table I gives 44 cross-sectional areas per vowel for the eleven American
#: English vowels [i ɪ e ɛ æ ʌ ɑ ɔ o ʊ u], from images collected on 22 May 2002
#: from the speaker of Story, Titze & Hoffman (1996), whose images were
#: collected in June 1994. Same speaker, same laboratory, same procedure, eight
#: years apart -- so it asks of a per-vowel coordinate the one question the
#: other sources cannot. Cross-speaker and cross-language disagreement can
#: always be answered by saying the sources measured different people speaking
#: different languages. This cannot.
#:
#: ``--third`` wants the same CSV shape as ``--second``:
#: ``subject,vowel,L_cm,dl_cm,section,area_cm2``, sections numbered from the
#: glottis, which is this table's own stated convention. The self-check differs
#: by one section: this paper's printed tract length is ``sections * dl``, where
#: Yang & Kasuya's is ``(sections - 1) * dl``.
THIRD_ENV = "IPAKIT_STORY2008_CSV"

#: The vowels both Story sets image. The 1996 set has ``ɝ`` and no ``e``; the
#: 2002 set has ``e`` and no ``ɝ``. Ten are common, and the comparison is over
#: those ten -- pairing ``e`` with ``ɛ``, or ``ɝ`` with anything, would be the
#: substitution this measurement exists to avoid.
BOTH_SESSIONS = ("i", "ɪ", "ɛ", "æ", "ʌ", "ɑ", "ɔ", "o", "ʊ", "u")

#: Which Story et al. shape each Japanese vowel is held against, and which of
#: Wood's families it belongs to. Read as IPA, the paper's own five symbols are
#: ipakit phones; the narrow readings [ä] and [ɯ] conventionally given to
#: Japanese /a/ and /u/ are part of why cross-language coordinates for one
#: symbol should not be expected to coincide, and that is a finding here rather
#: than a correction applied before measuring.
JAPANESE = (
    ("a", "lower pharynx"),
    ("i", "hard palate"),
    ("u", "soft palate"),
    ("e", "hard palate"),
    ("o", "upper pharynx"),
)

#: Shape assertions. The parse either reproduces the published table exactly or
#: it is wrong; these are not floors.
EXPECTED_COLUMNS = 18
EXPECTED_SECOND_COLUMNS = 15
EXPECTED_THIRD_COLUMNS = 11
EXPECTED_THIRD_SECTIONS = 44
EXPECTED_SECTIONS = tuple(round(length / INTERVAL_CM) for _, _, length in SHAPES)

ROW = re.compile(r"^(\d+)\s+((?:[\d.]+\s+)*[\d.]+)\s*$")


class Table:
    """Table III, parsed: one area function per imaged shape."""

    def __init__(self, area: dict[str, list[float]]) -> None:
        self.area = area

    def length(self, symbol: str) -> float:
        return len(self.area[symbol]) * INTERVAL_CM

    def centers(self, symbol: str) -> list[float]:
        """Distance from the glottis to the center of each section, in cm."""
        return [(n + 0.5) * INTERVAL_CM for n in range(len(self.area[symbol]))]

    def arc(self, symbol: str, section: int) -> float:
        """``arc`` of a section's center: 0 at the lips, 1 at the glottis."""
        count = len(self.area[symbol])
        return (count - section - 0.5) / count

    def extent(self, symbol: str, section: int) -> tuple[float, float]:
        """``arc`` a whole section spans, front edge first."""
        count = len(self.area[symbol])
        return ((count - section - 1) / count, (count - section) / count)

    def minima(self, symbol: str) -> list[tuple[float, float, float]]:
        """Interior local minima as ``(arc, cm from glottis, area)``.

        Every one of them, with no window applied: which are artifacts of the
        piriform sinuses and which are constrictions is the reader's call, and
        the point of returning all of them is that the call can be seen.
        """
        column = self.area[symbol]
        return [
            (self.arc(symbol, n), (n + 0.5) * INTERVAL_CM, column[n])
            for n in range(1, len(column) - 1)
            if column[n] < column[n - 1] and column[n] < column[n + 1]
        ]

    def narrowest(
        self, symbol: str, glottal_cm: float, labial_cm: float
    ) -> tuple[float, float, float] | None:
        """The narrowest section between the two cutoffs, or None if none is."""
        column = self.area[symbol]
        limit = self.length(symbol) - labial_cm
        inside = [
            n
            for n, center in enumerate(self.centers(symbol))
            if glottal_cm <= center <= limit
        ]
        if not inside:
            return None
        best = min(inside, key=lambda n: column[n])
        return (self.arc(symbol, best), (best + 0.5) * INTERVAL_CM, column[best])

    def band(
        self, symbol: str, glottal_cm: float, labial_cm: float, depth: float
    ) -> tuple[float, float, float] | None:
        """The extent of a vowel's constriction as ``(front, back, cm^2)``.

        A constriction is a region and not a point -- both external sources say
        so, and the argmin over eleven vowels is what
        docs/design/tract-validation.md 3 refuses. This grows the narrowest
        section outward while the area stays within ``depth`` of it, which is
        the closest thing an area function offers to the zero-area run that
        makes the occlusion check in ``occlusions`` free of any parameter.
        """
        column = self.area[symbol]
        found = self.narrowest(symbol, glottal_cm, labial_cm)
        if found is None:
            return None
        floor = found[2] * depth
        best = min(
            (n for n in range(len(column)) if column[n] == found[2]),
            key=lambda n: abs(self.arc(symbol, n) - found[0]),
        )
        low = best
        while low > 0 and column[low - 1] <= floor:
            low -= 1
        high = best
        while high < len(column) - 1 and column[high + 1] <= floor:
            high += 1
        return (self.extent(symbol, high)[0], self.extent(symbol, low)[1], found[2])

    def closure(self, symbol: str, ceiling: float = 0.0) -> tuple[float, float]:
        """The ``arc`` span over which the tract is closed, front edge first."""
        shut = [n for n, value in enumerate(self.area[symbol]) if value <= ceiling]
        if not shut:
            raise ValueError(f"{symbol!r} has no section at or below {ceiling} cm^2")
        return (self.extent(symbol, shut[-1])[0], self.extent(symbol, shut[0])[1])


def parse(text: str) -> Table:
    """Read Table III out of a text extraction, and check that it was read.

    The table is column-ragged: a shape with a shorter tract has fewer
    sections, so its column stops early and later rows are narrower. Nothing in
    the row says which columns are still alive -- but the published tract
    lengths do, and that makes the parse self-checking. Section counts derived
    from the lengths have to predict the width of every row in the table, and a
    misread digit or a dropped column breaks the prediction immediately.
    """
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("TABLE III.")),
        None,
    )
    if start is None:
        raise ValueError("no line beginning 'TABLE III.' -- is this the right paper?")
    rows: dict[int, list[float]] = {}
    for line in lines[start : start + 80]:
        match = ROW.match(line.strip())
        if match:
            rows[int(match.group(1))] = [float(v) for v in match.group(2).split()]
    if not rows:
        raise ValueError("found the caption but no numbered rows under it")

    columns: list[list[float]] = [[] for _ in SHAPES]
    for number in sorted(rows):
        alive = [i for i, count in enumerate(EXPECTED_SECTIONS) if count >= number]
        values = rows[number]
        if len(values) != len(alive):
            raise ValueError(
                f"row {number} has {len(values)} values; the published tract "
                f"lengths say {len(alive)} columns are still open there"
            )
        for index, value in zip(alive, values, strict=True):
            columns[index].append(value)
    for (symbol, word, _), column, expected in zip(
        SHAPES, columns, EXPECTED_SECTIONS, strict=True
    ):
        if len(column) != expected:
            raise ValueError(
                f"{symbol!r} ({word}) read {len(column)} sections, expected {expected}"
            )
    if len(columns) != EXPECTED_COLUMNS:
        raise ValueError(f"read {len(columns)} columns, expected {EXPECTED_COLUMNS}")
    return Table(
        {symbol: column for (symbol, _, _), column in zip(SHAPES, columns, strict=True)}
    )


def spearman(xs: list[float], ys: list[float]) -> float:
    """Rank correlation, ties averaged."""

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    top = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    bottom = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return top / bottom if bottom else float("nan")


def declared() -> dict[str, float | None]:
    """The ``arc`` ipakit computes for each imaged shape, from its own data."""
    features = IPAFeatures()
    out: dict[str, float | None] = {}
    for symbol, _, _ in SHAPES:
        bundle = features.get_features(symbol)
        out[symbol] = tract_point(features, bundle).arc if bundle else None
    return out


def cmd_table(table: Table, args: argparse.Namespace) -> int:
    print(f"Table III, {EXPECTED_COLUMNS} shapes, {INTERVAL_CM} cm per section\n")
    print(f"  {'':3} {'word':7} {'sections':>8} {'length cm':>9} {'min cm^2':>9}")
    for symbol, word, length in SHAPES:
        column = table.area[symbol]
        print(
            f"  {symbol:3} {word:7} {len(column):>8} {length:>9.2f} {min(column):>9.2f}"
        )
    print(
        "\nevery column has the section count its published tract length predicts, "
        "and\nevery short row has the width those counts predict"
    )
    return 0


def cmd_occlusions(table: Table, args: argparse.Namespace) -> int:
    """Declared place arc against the measured closure. No free parameter."""
    arcs = declared()
    print("Occlusion: where the area function reaches zero, against the arc")
    print("ipakit declares for the phone's place.\n")
    print(f"  {'':3} {'declared':>8}  {'measured closure':>18}   verdict")
    inside = 0
    for symbol in OCCLUDED:
        value = arcs[symbol]
        if value is None:
            print(f"  {symbol:3} {'unregistered':>8}")
            continue
        front, back = table.closure(symbol)
        if front <= value <= back:
            inside += 1
            verdict = "inside"
        else:
            verdict = f"outside by {min(abs(value - front), abs(value - back)):.3f}"
        print(f"  {symbol:3} {value:>8.2f}  {front:>8.3f}-{back:<9.3f}   {verdict}")
    print(f"\n{inside} of {len(OCCLUDED)} declared place arcs inside the closure")
    print(
        "The two that are not are both velar, both in the same direction, and the\n"
        "size of the miss tracks the vowel context -- see docs/design/"
        "tract-validation.md 2."
    )
    return 0


def cmd_vowels(table: Table, args: argparse.Namespace) -> int:
    """Every supralaryngeal local minimum, so the window choice is visible."""
    arcs = declared()
    print("Vowels: every interior local minimum of the area function, as")
    print("(arc from the lips / cm^2). Sections whose center is below")
    print(f"{args.glottal:.1f} cm from the glottis are marked * -- Story et al. p. 544")
    print("puts the piriform sinus narrowing at 4 to 5 cm, in every shape.\n")
    print(f"  {'':3} {'declared':>8}   minima")
    for symbol in VOWELS:
        value = arcs[symbol]
        shown = []
        for arc, center, area in table.minima(symbol):
            if center < 3.0:
                continue
            shown.append(
                f"{arc:.2f}/{area:.2f}" + ("*" if center < args.glottal else "")
            )
        head_ = "unregistered" if value is None else f"{value:.2f}"
        print(f"  {symbol:3} {head_:>8}   {' '.join(shown)}")
    print(
        "\nThe five back vowels share one declared arc, because a vowel reads arc "
        "from\nbackness alone. The data puts u and o near one location and ɑ, ɔ and "
        "ʌ near\nanother, with nothing of this speaker's between them."
    )
    return 0


def cmd_stability(table: Table, args: argparse.Namespace) -> int:
    """What a rank correlation over the vowels depends on. It is the cutoff."""
    arcs = declared()
    usable = [s for s in VOWELS if arcs[s] is not None]
    cuts = [3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    print("Rank correlation between the declared arc and the windowed minimum,")
    print(f"over {len(usable)} vowels, as the glottal-end cutoff moves.")
    print(f"Labial exclusion held at {args.labial:.1f} cm.\n")
    print(f"  {'cutoff cm':>9} {'rho':>8} {'concordant':>11} {'of pairs':>9}")
    for cut in cuts:
        found = {s: table.narrowest(s, cut, args.labial) for s in usable}
        if any(v is None for v in found.values()):
            continue
        rho = spearman(
            [float(arcs[s] or 0.0) for s in usable],
            [found[s][0] for s in usable],  # type: ignore[index]
        )
        agree = pairs = 0
        for a, b in itertools.combinations(usable, 2):
            da = float(arcs[a] or 0.0) - float(arcs[b] or 0.0)
            if da == 0.0:
                continue
            pairs += 1
            db = found[a][0] - found[b][0]  # type: ignore[index]
            agree += da * db > 0
        print(f"  {cut:>9.1f} {rho:>+8.3f} {agree:>11} {pairs:>9}")
    print(
        "\nNothing outside this table fixes the cutoff, and the figure moves across "
        "the\nwhole interpretable range as it slides. A number reported from any one "
        "row\nwould be a report of that row. This is why "
        "docs/design/tract-validation.md\nrefuses the vowel figure and keeps the "
        "occlusion check."
    )
    return 0


class Second(Table):
    """Yang & Kasuya Tables 1-3: one area function per subject and vowel.

    Keyed ``subject/vowel``. Every section-counting method on :class:`Table`
    works unchanged -- ``arc`` and ``extent`` are proportions of the column --
    and only the two that need centimetres are overridden, because each column
    prints its own section length.
    """

    def __init__(self, area: dict[str, list[float]], interval: dict[str, float]):
        super().__init__(area)
        self.interval = interval

    def length(self, symbol: str) -> float:
        return (len(self.area[symbol]) - 1) * self.interval[symbol]

    def centers(self, symbol: str) -> list[float]:
        step = self.interval[symbol]
        return [(n + 0.5) * step for n in range(len(self.area[symbol]))]


def parse_second(text: str) -> Second:
    """Read the CSV, and check it against the tract lengths it carries.

    A transcription of a printed table cannot be checked against the table, but
    it can be checked against itself: the paper prints ``L`` and ``dl`` per
    column as well as the sections, and ``(sections - 1) * dl`` has to give
    ``L``. A dropped or duplicated row breaks that at once.
    """
    area: dict[str, list[float]] = {}
    interval: dict[str, float] = {}
    stated: dict[str, float] = {}
    rows = [
        line for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    reader = csv.DictReader(rows)
    for row in reader:
        key = f"{row['subject']}/{row['vowel']}"
        area.setdefault(key, []).append(float(row["area_cm2"]))
        interval[key] = float(row["dl_cm"])
        stated[key] = float(row["L_cm"])
    if len(area) != EXPECTED_SECOND_COLUMNS:
        raise ValueError(
            f"read {len(area)} columns, expected {EXPECTED_SECOND_COLUMNS} "
            "(5 vowels for each of 3 subjects)"
        )
    for key, column in area.items():
        derived = (len(column) - 1) * interval[key]
        if abs(derived - stated[key]) > 0.05:
            raise ValueError(
                f"{key}: {len(column)} sections of {interval[key]} cm give "
                f"{derived:.2f} cm, against a printed length of {stated[key]}"
            )
    return Second(area, interval)


class Intra(Second):
    """Story (2008) Table I: one area function per vowel, one speaker.

    Identical to :class:`Second` but for the relation between the printed tract
    length and the section length. Yang & Kasuya's ``L`` spans the gaps between
    section centers and so is ``(sections - 1) * dl``; this table's ``L`` is the
    whole tube, ``sections * dl``. Getting that wrong shifts every arc by half a
    section, which is 0.011 of the tract -- small, and larger than some of the
    misses this script reports, so it is worth being exact about.
    """

    def length(self, symbol: str) -> float:
        return len(self.area[symbol]) * self.interval[symbol]


def parse_intra(text: str) -> Intra:
    """Read the CSV, and check it against the tract lengths it carries."""
    area: dict[str, list[float]] = {}
    interval: dict[str, float] = {}
    stated: dict[str, float] = {}
    rows = [
        line for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    for row in csv.DictReader(rows):
        key = row["vowel"]
        area.setdefault(key, []).append(float(row["area_cm2"]))
        interval[key] = float(row["dl_cm"])
        stated[key] = float(row["L_cm"])
    if len(area) != EXPECTED_THIRD_COLUMNS:
        raise ValueError(
            f"read {len(area)} columns, expected {EXPECTED_THIRD_COLUMNS} vowels"
        )
    for key, column in area.items():
        if len(column) != EXPECTED_THIRD_SECTIONS:
            raise ValueError(
                f"{key}: {len(column)} sections, expected {EXPECTED_THIRD_SECTIONS}"
            )
        derived = len(column) * interval[key]
        if abs(derived - stated[key]) > 0.05:
            raise ValueError(
                f"{key}: {len(column)} sections of {interval[key]} cm give "
                f"{derived:.2f} cm, against a printed length of {stated[key]}"
            )
    return Intra(area, interval)


def wood_arcs() -> dict[str, tuple[str, float]]:
    """Wood's location for each imaged vowel, as an ``arc`` from the lips.

    A location is a distance from the glottal source, so it becomes an arc
    against a tract length. Each shape's own published length is used, so the
    conversion introduces no divisor of this reader's choosing -- the same
    reason ``docs/articulatory-data.md`` divides by each speaker's declared
    head length rather than by one number for everybody.
    """
    lengths = {symbol: length for symbol, _, length in SHAPES}
    out: dict[str, tuple[str, float]] = {}
    for name, from_glottis, family in WOOD_LOCATIONS:
        for symbol in family:
            length = lengths[symbol]
            out[symbol] = (name, (length - from_glottis) / length)
    return out


def wood_proportional() -> dict[str, float]:
    """The same four locations read as fixed proportions of any tract.

    Subtracting a fixed number of centimetres is a reading of Wood's anatomical
    claim, and it is the wrong one off an adult male: on the 13.3 cm tract of
    Yang & Kasuya's boy it puts the hard palate at ``arc`` 0.10, forward of the
    teeth. ``arc`` is a proportion, so the proportional reading is the one that
    transfers -- against the 17.5 cm the Stevens & House model uses, which is
    the model Wood's four distances parameterize.
    """
    return {
        name: (WOOD_REFERENCE_CM - cm) / WOOD_REFERENCE_CM
        for name, cm, _ in WOOD_LOCATIONS
    }


def cmd_bands(table: Table, args: argparse.Namespace) -> int:
    """Two sources against one measured band each, the way ``occlusions`` does.

    ``stability`` shows why a rank correlation over these vowels cannot be
    reported. This is the instrument that can be: a band from the data, and an
    anchor that is either in it or not.
    """
    arcs = declared()
    wood = wood_arcs()
    print("Wood (1979) puts every vowel constriction at one of four locations,")
    print("over 40 subjects in 13 languages. Story et al. supply the only bands:")
    print("the run of sections around the narrowest one that stays within a")
    print(f"factor of {args.depth:g} of it. Both anchors are held against that band.\n")
    print(f"  {'':3} {'band':>13}  {'ipakit':>6} {'':8}  {'Wood':>6} {'':8}  location")
    counts = {"ipakit": 0, "wood": 0}
    comparable = 0
    for symbol in VOWELS:
        found = table.band(symbol, args.glottal, args.labial, args.depth)
        if found is None or symbol not in wood:
            reason = "no family" if found is not None else "no minimum in window"
            print(f"  {symbol:3} {'':>13}  {'':>6} {'':8}  {'':>6} {'':8}  {reason}")
            continue
        front, back, area = found
        comparable += 1
        cells = []
        for key, value in (("ipakit", arcs[symbol]), ("wood", wood[symbol][1])):
            if value is None:
                cells.append(f"{'':>6} {'':8}")
                continue
            if front <= value <= back:
                counts[key] += 1
                cells.append(f"{value:>6.3f} {'inside':8}")
            else:
                miss = min(abs(value - front), abs(value - back))
                cells.append(f"{value:>6.3f} {'by ' + format(miss, '.3f'):8}")
        print(
            f"  {symbol:3} {front:.3f}-{back:<7.3f}  {cells[0]}  {cells[1]}  "
            f"{wood[symbol][0]} ({area:.2f} cm^2)"
        )
    print(
        f"\n{counts['wood']} of {comparable} of Wood's locations inside the measured "
        f"band, against\n{counts['ipakit']} of {comparable} of the arcs ipakit "
        "declares."
    )

    print("\nThe same counts as the band widens, and as the piriform cutoff moves.")
    print("A verdict that moves with either is a report of the parameter.\n")
    print(f"  {'depth':>6} {'cutoff cm':>9} {'n':>4} {'ipakit':>7} {'Wood':>6}")
    for depth in DEPTH_FACTORS:
        for cut in (4.0, 5.0, 6.0, 7.0):
            hits = {"ipakit": 0, "wood": 0}
            usable = 0
            for symbol in VOWELS:
                found = table.band(symbol, cut, args.labial, depth)
                if found is None or symbol not in wood:
                    continue
                usable += 1
                front, back, _ = found
                for key, value in (("ipakit", arcs[symbol]), ("wood", wood[symbol][1])):
                    if value is not None and front <= value <= back:
                        hits[key] += 1
            print(
                f"  {depth:>6.2f} {cut:>9.1f} {usable:>4} {hits['ipakit']:>7} "
                f"{hits['wood']:>6}"
            )
    return 0


def cmd_replicate(table: Table, args: argparse.Namespace) -> int:
    """Does a per-vowel coordinate reproduce across speakers and languages?

    This is the question a table fitted to one speaker cannot answer about
    itself. Story et al. image one adult male of American English; Yang &
    Kasuya image an adult male, an adult female and a boy of Japanese. Both
    tabulate an area function, so the same band instrument reads both.
    """
    second = getattr(args, "table_two", None)
    if second is None:
        print(
            f"no second source given: pass --second or set ${SECOND_ENV} to a "
            "CSV of\nYang & Kasuya (1994) Tables 1-3. See this module's "
            "docstring for the columns."
        )
        return 0
    proportional = wood_proportional()
    features = IPAFeatures()
    arcs = {
        vowel: tract_point(features, features.get_features(vowel)).arc
        for vowel, _ in JAPANESE
    }

    print("Yang & Kasuya (1994) Tables 1-3: the five Japanese vowels from an adult")
    print("male, an adult female and a boy. Same instrument as `bands`, and Wood's")
    print("four locations read as proportions of the tract rather than as centimetres")
    print("subtracted from it, which a 13.3 cm tract cannot carry.\n")
    print(f"  {'':16} {'constriction':>12} {'band':>13} {'Wood':>6} {'ipakit':>7}")
    measured: dict[str, list[float]] = {}
    inside = {"wood": 0, "ipakit": 0, "n": 0}
    for subject in ("male", "female", "boy"):
        for vowel, location in JAPANESE:
            key = f"{subject}/{vowel}"
            found = second.band(key, args.glottal, args.labial, args.depth)
            narrow = second.narrowest(key, args.glottal, args.labial)
            if found is None or narrow is None:
                print(f"  {key:16} {'no minimum in the window':>12}")
                continue
            measured.setdefault(vowel, []).append(narrow[0])
            front, back, _ = found
            wood = proportional[location]
            mine = arcs[vowel]
            inside["n"] += 1
            marks = ""
            for which, value in (("wood", wood), ("ipakit", mine)):
                if value is not None and front <= value <= back:
                    inside[which] += 1
                    marks += " in"
                else:
                    marks += " --"
            print(
                f"  {key:16} {narrow[0]:>12.3f} {front:.3f}-{back:<7.3f} "
                f"{wood:>6.3f} {mine if mine is not None else 0.0:>7.2f}{marks}"
            )

    print(
        f"\n{inside['wood']} of {inside['n']} of Wood's locations inside the measured "
        f"band, against\n{inside['ipakit']} of {inside['n']} of the arcs ipakit "
        "declares."
    )

    print("\nThe same vowel across the sources that measured it, as arc from the lips.")
    print("A coordinate per (height, backness) cell has to be one number here.\n")
    print(
        f"  {'':3} {'Story (en)':>11} {'Yang & Kasuya (ja)':>26} {'Wood':>6} "
        f"{'spread':>7}"
    )
    for vowel, location in JAPANESE:
        here = measured.get(vowel, [])
        theirs = " ".join(f"{value:.3f}" for value in here)
        # Only where the *same* symbol is imaged by both. Story et al. image no
        # /a/ and no /e/: their nearest columns are ɑ and ɛ, which are other
        # vowels, and putting one under the other would be the assumption this
        # subcommand exists to test.
        story = (
            table.narrowest(vowel, args.glottal, args.labial)
            if vowel in VOWELS
            else None
        )
        pool = list(here) + ([story[0]] if story else [])
        spread = max(pool) - min(pool) if len(pool) > 1 else float("nan")
        shown = f"{story[0]:.3f}" if story else "not imaged"
        print(
            f"  {vowel:3} {shown:>11} {theirs:>26} {proportional[location]:>6.3f} "
            f"{spread:>7.3f}"
        )
    print(
        "\nThe spread column is what a fitted table would have to pick one value "
        "from.\nSee docs/design/vowel-constriction.md for what it is read as."
    )
    return 0


def cmd_intra(table: Table, args: argparse.Namespace) -> int:
    """Does a per-vowel coordinate reproduce for one speaker across sessions?

    ``replicate`` asks whether a coordinate survives a change of speaker and
    language, and it does not. The obvious reply is that those were different
    people speaking different languages, and that a coordinate could still be
    well defined once a speaker is fixed. Story (2008) is that reply's test: the
    speaker of Story, Titze & Hoffman (1996), re-imaged eight years later by the
    same author with the same procedure.
    """
    third = getattr(args, "table_three", None)
    if third is None:
        print(
            f"no third source given: pass --third or set ${THIRD_ENV} to a CSV "
            "of\nStory (2008) Table I. See this module's docstring for the "
            "columns."
        )
        return 0
    arcs = declared()
    wood = wood_arcs()

    print("Story, Titze & Hoffman (1996) and Story (2008) image the same speaker")
    print("in June 1994 and May 2002. Same lab, same procedure, same eleven-vowel")
    print("task. Ten vowels are in both sets. Bands are the same instrument as")
    print(f"`bands`, at a depth factor of {args.depth:g}.\n")
    print(
        f"  {'':3} {'1994 band':>14} {'1994':>6}  {'2002 band':>14} {'2002':>6}  "
        f"{'move':>5}  {'overlap':>7}"
    )
    moves: list[tuple[str, float]] = []
    overlapping = 0
    usable = 0
    for symbol in BOTH_SESSIONS:
        old = table.band(symbol, args.glottal, args.labial, args.depth)
        new = third.band(symbol, args.glottal, args.labial, args.depth)
        old_point = table.narrowest(symbol, args.glottal, args.labial)
        new_point = third.narrowest(symbol, args.glottal, args.labial)
        if old is None or new is None or old_point is None or new_point is None:
            print(f"  {symbol:3} {'no minimum in the window':>14}")
            continue
        usable += 1
        move = abs(new_point[0] - old_point[0])
        moves.append((symbol, move))
        touches = not (old[1] < new[0] or new[1] < old[0])
        overlapping += touches
        print(
            f"  {symbol:3} {old[0]:.3f}-{old[1]:<8.3f} {old_point[0]:>6.3f}  "
            f"{new[0]:.3f}-{new[1]:<8.3f} {new_point[0]:>6.3f}  "
            f"{move:>5.3f}  {'yes' if touches else 'NO':>7}"
        )

    if usable:
        worst = max(moves, key=lambda pair: pair[1])
        median = sorted(move for _, move in moves)[len(moves) // 2]
        print(
            f"\nThe same speaker's own constriction moves a median of {median:.3f} of "
            f"tract\nlength between the two sessions, and {worst[1]:.3f} for "
            f"[{worst[0]}]. The two bands\noverlap for {overlapping} of {usable} "
            "vowels."
        )

    print("\nHow much of that is the piriform cutoff. A move that holds across the")
    print("range a reader could defend is the speaker; one that does not is the")
    print("parameter, and section 3 of tract-validation.md refuses those.\n")
    print(f"  {'':3} " + " ".join(f"{cut:>6.1f}" for cut in (4.0, 5.0, 6.0, 7.0)))
    stable: list[tuple[str, float]] = []
    for symbol in BOTH_SESSIONS:
        cells = []
        seen: list[float] = []
        for cut in (4.0, 5.0, 6.0, 7.0):
            old_point = table.narrowest(symbol, cut, args.labial)
            new_point = third.narrowest(symbol, cut, args.labial)
            if old_point is None or new_point is None:
                cells.append(f"{'--':>6}")
                continue
            move = abs(new_point[0] - old_point[0])
            seen.append(move)
            cells.append(f"{move:>6.3f}")
        print(f"  {symbol:3} " + " ".join(cells))
        if seen:
            stable.append((symbol, min(seen)))
    big = [symbol for symbol, floor in stable if floor >= 0.10]
    print(
        "\nMoving by at least 0.100 of tract length at every cutoff: "
        + (", ".join(f"[{symbol}]" for symbol in big) if big else "none")
        + ".\nThe declared `backness` span is 0.24 in total, front 0.32 to back "
        "0.56."
    )

    print("\nAnd the check `bands` makes, run again on the 2002 session alone.")
    print("A classification that survives a re-imaging is a different claim from")
    print("one fitted to a single session.\n")
    print(f"  {'':3} {'2002 band':>14}  {'ipakit':>6} {'':8}  {'Wood':>6} {'':8}")
    counts = {"ipakit": 0, "wood": 0}
    comparable = 0
    for symbol in BOTH_SESSIONS:
        new = third.band(symbol, args.glottal, args.labial, args.depth)
        if new is None or symbol not in wood:
            continue
        front, back, _ = new
        comparable += 1
        cells = []
        for key, value in (("ipakit", arcs[symbol]), ("wood", wood[symbol][1])):
            if value is None:
                cells.append(f"{'':>6} {'':8}")
                continue
            if front <= value <= back:
                counts[key] += 1
                cells.append(f"{value:>6.3f} {'inside':8}")
            else:
                miss = min(abs(value - front), abs(value - back))
                cells.append(f"{value:>6.3f} {'by ' + format(miss, '.3f'):8}")
        print(f"  {symbol:3} {front:.3f}-{back:<8.3f}  {cells[0]}  {cells[1]}")
    print(
        f"\n{counts['wood']} of {comparable} of Wood's locations inside the 2002 "
        f"band, against\n{counts['ipakit']} of {comparable} of the arcs ipakit "
        "declares."
    )
    return 0


def cmd_anchors(table: Table, args: argparse.Namespace) -> int:
    """Where would the four locations sit, if the classification were adopted?

    Two changes get run together and are not the same one. Adopting Wood's
    four-way classification says which family a vowel belongs to. Placing those
    families says where the family is, and there are two answers already on the
    table: the proportions Wood's own four distances give against the tract
    length his nomograms use, and the arcs ``place`` already declares under the
    same four names. They differ, and the difference is measurable by the same
    band instrument as everything else here rather than arguable.
    """
    families = {symbol: name for name, _, family in WOOD_LOCATIONS for symbol in family}
    place_arcs = landmarks(IPAFeatures()).places
    proportional = wood_proportional()
    arcs = declared()

    print("Wood's four locations, placed two ways.\n")
    print(f"  {'location':>14} {'ipakit name':>11} {'Wood':>6} {'place':>6} {'gap':>6}")
    for name, _, _ in WOOD_LOCATIONS:
        under = WOOD_AS_PLACE[name]
        mine = place_arcs.get(under)
        gap = abs(proportional[name] - mine) if mine is not None else float("nan")
        print(
            f"  {name:>14} {under:>11} {proportional[name]:>6.3f} "
            f"{mine if mine is not None else float('nan'):>6.3f} {gap:>6.3f}"
        )

    def anchor_of(symbol: str, reading: str) -> float | None:
        if reading == "backness":
            return arcs.get(symbol)
        name = families.get(symbol)
        if name is None:
            return None
        if reading == "Wood":
            return proportional[name]
        return place_arcs.get(WOOD_AS_PLACE[name])

    sources: list[tuple[str, Table, tuple[str, ...]]] = [
        ("Story 1996", table, VOWELS),
    ]
    third = getattr(args, "table_three", None)
    if third is not None:
        sources.append(("Story 2002", third, BOTH_SESSIONS))
    second = getattr(args, "table_two", None)
    if second is not None:
        sources.append(
            (
                "Yang & Kasuya",
                second,
                tuple(
                    f"{subject}/{vowel}"
                    for subject in ("male", "female", "boy")
                    for vowel, _ in JAPANESE
                ),
            )
        )
        for subject in ("male", "female", "boy"):
            for vowel, location in JAPANESE:
                families[f"{subject}/{vowel}"] = location
                arcs[f"{subject}/{vowel}"] = arcs.get(vowel)

    readings = ("backness", "Wood", "place")
    print("\nBand inclusion, one row per source, at the default settings.")
    print("`backness` is what a vowel reads today; `Wood` is his four proportions;")
    print("`place` is his four families read at the arcs ipa.xml already declares.\n")
    print(f"  {'source':>14} {'bands':>6} " + " ".join(f"{r:>9}" for r in readings))
    totals = dict.fromkeys(readings, 0)
    every = 0
    for label, source, keys in sources:
        counts = dict.fromkeys(readings, 0)
        usable = 0
        for key in keys:
            found = source.band(key, args.glottal, args.labial, args.depth)
            if found is None or key not in families:
                continue
            usable += 1
            front, back, _ = found
            for reading in readings:
                value = anchor_of(key, reading)
                if value is not None and front <= value <= back:
                    counts[reading] += 1
        every += usable
        for reading in readings:
            totals[reading] += counts[reading]
        print(
            f"  {label:>14} {usable:>6} "
            + " ".join(f"{counts[r]:>9}" for r in readings)
        )
    print(f"  {'all':>14} {every:>6} " + " ".join(f"{totals[r]:>9}" for r in readings))

    print("\nAnd the same three counts as both free parameters move.\n")
    print(
        f"  {'depth':>6} {'cutoff':>6} {'bands':>6} "
        + " ".join(f"{r:>9}" for r in readings)
    )
    margins: list[float] = []
    behind = 0
    rows = 0
    for depth in DEPTH_FACTORS:
        for cut in (4.0, 5.0, 6.0, 7.0):
            counts = dict.fromkeys(readings, 0)
            usable = 0
            for _, source, keys in sources:
                for key in keys:
                    found = source.band(key, cut, args.labial, depth)
                    if found is None or key not in families:
                        continue
                    usable += 1
                    front, back, _ = found
                    for reading in readings:
                        value = anchor_of(key, reading)
                        if value is not None and front <= value <= back:
                            counts[reading] += 1
            rows += 1
            margins.append(counts["Wood"] - counts["place"])
            behind += counts["backness"] < min(counts["Wood"], counts["place"])
            print(
                f"  {depth:>6.2f} {cut:>6.1f} {usable:>6} "
                + " ".join(f"{counts[r]:>9}" for r in readings)
            )
    print(
        f"\n`backness` is below both of the other two in {behind} of {rows} rows. "
        "That\nordering is not a report of either parameter, and it is the finding."
    )
    print(
        f"Wood against place runs from {min(margins):+d} to {max(margins):+d} bands "
        "of 35 over the same\nsweep, and changes sign inside it: the instrument does "
        "not separate them."
    )
    return 0


def cmd_arc(table: Table, args: argparse.Namespace) -> int:
    """Whether ``arc`` is the proportional midline position it says it is.

    Reads no external data -- it is here because every other measurement in
    this script assumes it, and the assumption had never been checked.
    """
    print("Declared arc against normalized arclength along each head's own polyline.\n")

    def arclength(points: Sequence[MidlinePoint]) -> tuple[list[float], float]:
        run = [0.0]
        for before, after in zip(points, points[1:], strict=False):
            step = ((after.x - before.x) ** 2 + (after.y - before.y) ** 2) ** 0.5
            run.append(run[-1] + step)
        return run, run[-1]

    worst = 0.0
    for name in ("adult-male", "adult-female", "child"):
        shape = head(name)
        # The nasal branch on the same footing as the midline. It declares
        # the same attributes, is interpolated by the same code, and makes
        # the same claim about its own arc -- 0 at the nostrils to 1 at the
        # velopharyngeal port. Reporting only the midlines called 0.062 the
        # largest disagreement in a file whose largest is a nasal one.
        for label, branch in (("midline", shape.midline), ("nasal", shape.nasal)):
            if len(branch) < 2:
                continue
            run, total = arclength(branch)
            gaps = [
                abs(distance / total - point.arc)
                for point, distance in zip(branch, run, strict=True)
            ]
            worst = max(worst, max(gaps))
            said = f"{name} {label}"
            print(
                f"  {said:22} max |declared arc - arclength fraction| = {max(gaps):.3f}"
            )
        if name == "adult-male":
            points = shape.midline
            run, total = arclength(points)
            spots: dict[str, float] = {}
            places = IPAFeatures().features["place"].coordinates
            for value in ("bilabial", "alveolar", "velar"):
                arc = places[value]["arc"]
                for i in range(len(points) - 1):
                    if points[i].arc <= arc <= points[i + 1].arc:
                        span = points[i + 1].arc - points[i].arc
                        t = (arc - points[i].arc) / span if span else 0.0
                        spots[value] = (run[i] + (run[i + 1] - run[i]) * t) / total
                        break
            said = ", ".join(
                f"{value} {places[value]['arc']:.2f} -> {spot:.3f}"
                for value, spot in spots.items()
            )
            print(f"  {'':22} the places occlusions reach: {said}")
    print(f"\nlargest over all shipped polylines: {worst:.3f}")
    print(
        "Heads never affect distance, so nothing is wrong today. Reading each\n"
        "declared arc as its own midline's arclength instead changes no verdict in\n"
        "`occlusions`, which is why that section is reported as it stands.\n"
        "`scripts/invariants.py` now gates all of this: the vertex arcs against what\n"
        "ipa.xml declares, these six gaps against what they are, and the ascent that\n"
        "`Head.project` assumes. This subcommand is the readable view of that check."
    )
    return 0


COMMANDS = {
    "table": cmd_table,
    "occlusions": cmd_occlusions,
    "vowels": cmd_vowels,
    "stability": cmd_stability,
    "bands": cmd_bands,
    "replicate": cmd_replicate,
    "intra": cmd_intra,
    "anchors": cmd_anchors,
    "arc": cmd_arc,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        default=os.environ.get(SOURCE_ENV),
        help=f"text extraction of the paper (default: ${SOURCE_ENV})",
    )
    parser.add_argument(
        "--glottal",
        type=float,
        default=DEFAULT_GLOTTAL_CM,
        help="ignore sections nearer the glottis than this, in cm",
    )
    parser.add_argument(
        "--labial",
        type=float,
        default=DEFAULT_LABIAL_CM,
        help="ignore sections nearer the lips than this, in cm",
    )
    parser.add_argument(
        "--depth",
        type=float,
        default=2.0,
        help="how much wider than its narrowest section a band may run",
    )
    parser.add_argument(
        "--second",
        default=os.environ.get(SECOND_ENV),
        help=f"CSV of Yang & Kasuya (1994) Tables 1-3 (default: ${SECOND_ENV})",
    )
    parser.add_argument(
        "--third",
        default=os.environ.get(THIRD_ENV),
        help=f"CSV of Story (2008) Table I (default: ${THIRD_ENV})",
    )
    parser.add_argument("command", choices=[*COMMANDS, "all"], help="what to measure")
    args = parser.parse_args(argv)

    if args.command == "arc":
        return cmd_arc(Table({}), args)

    if not args.source:
        print(
            f"no source given: pass --source or set ${SOURCE_ENV} to a text "
            "extraction of\nStory, Titze & Hoffman (1996). The paper is "
            "copyrighted and is not bundled."
        )
        return 0
    path = Path(args.source)
    if not path.exists():
        print(f"{path} does not exist; nothing to measure.")
        return 0
    # A source that is present but not what it should be is a failure, not an
    # absence: exiting 0 there is how a run reports clean numbers over nothing.
    try:
        table = parse(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as error:
        print(f"{path}: {error}", file=sys.stderr)
        return 1

    args.table_two = None
    if args.second:
        path_two = Path(args.second)
        if path_two.exists():
            try:
                args.table_two = parse_second(
                    path_two.read_text(encoding="utf-8", errors="replace")
                )
            except ValueError as error:
                print(f"{path_two}: {error}", file=sys.stderr)
                return 1

    args.table_three = None
    if args.third:
        path_three = Path(args.third)
        if path_three.exists():
            try:
                args.table_three = parse_intra(
                    path_three.read_text(encoding="utf-8", errors="replace")
                )
            except ValueError as error:
                print(f"{path_three}: {error}", file=sys.stderr)
                return 1

    if args.command != "all":
        return COMMANDS[args.command](table, args)
    for name, run in COMMANDS.items():
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        status = run(table, args)
        if status:
            return status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
