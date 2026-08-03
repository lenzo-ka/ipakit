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
    python scripts/areafunctions.py female       # ... across two speakers of one language?
    python scripts/areafunctions.py anchors      # where the four locations sit
    python scripts/areafunctions.py chart        # can the vowel chart supply one?
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
import functools
import itertools
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
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
#: Wood restates the same four families twice more, and the restatements name
#: three symbols conclusion 2 does not. Wood (1990: 198) gives the palatal
#: family as "[i-ɛ,y-œ]-like" and the palatovelar one as "[u-ʊ,ɯ]-like"; his own
#: summary of the 1979 figure gives the third as "[o ɔ] and [ɤ ʌ]". So ``ʌ`` is
#: upper-pharyngeal here, which is where the measurement puts it too: Wood's
#: 0.629 is inside all three American English bands for it and his 0.743 inside
#: one of three. Reading it off Fig. 5 instead -- which superimposes Southern
#: British English formant areas on the four nomogram surfaces and assigns no
#: area to a surface -- put it in the lower pharyngeal family, and that is what
#: made the classification and the bands appear to disagree.
#:
#: ``ɝ`` is imaged by Story et al. and has no family: Wood's four cover the
#: cardinal space and not the American English rhotic.
WOOD_LOCATIONS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("hard palate", 12.0, ("i", "ɪ", "ɛ", "œ")),
    ("soft palate", 8.5, ("u", "ʊ", "ɯ")),
    ("upper pharynx", 6.5, ("o", "ɔ", "ʌ")),
    ("lower pharynx", 4.5, ("ɑ", "æ")),
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

#: The fifth source, and the only adult female of the language the other two
#: American English sets image:
#:
#:     Story, Brad H., Ingo R. Titze and Eric A. Hoffman (1998). "Vocal tract
#:     area functions for an adult female speaker based on volumetric imaging",
#:     J. Acoust. Soc. Am. 104(1), 471-487.
#:     https://doi.org/10.1121/1.423298
#:
#: Subject DJ, a 27-year-old female native to Texas, imaged on a GE Signa 1.5-T
#: scanner -- **a different speaker**, not a re-analysis of the male of Story,
#: Titze & Hoffman (1996). Table III (p. 476) gives ten vowels plus electron-beam
#: CT versions of ``i`` and ``ɑ``, and Table IV (p. 480) gives the rhotic ``ɝ``
#: twice, with and without its sublingual cavity folded into the main tube.
#: Sections run from the glottis, 0.396825 cm each, the same convention and the
#: same interval as the 1996 male.
#:
#: Two things this source can be asked that no other can. Whether a constriction
#: location survives a change of *speaker* within one language -- ``replicate``
#: changes language as well, and ``intra`` changes neither -- and what a second
#: American English speaker says about ``ʌ`` and ``ɝ``, the two symbols of the
#: fifteen unclassified ones that any measured source images at all.
#:
#: ``--fourth`` wants the same CSV shape as ``--second`` and ``--third``, plus a
#: ``dist_cm`` column carrying the paper's own printed distance from the glottis.
#: That column is what makes a transcription of an image-only table checkable
#: without the table: see :func:`parse_female`.
FOURTH_ENV = "IPAKIT_STORY1998_CSV"

#: The ten MRI vowels of Table III, in its column order, which is Table I's.
#: The two CT columns and the two ``ɝ`` columns are in the file and are not
#: here: the CT pair is a repeat of two of these ten by the same speaker on
#: another day and is reported as that, and ``ɝ`` has no family in Wood and is
#: the question ``female`` asks rather than an answer it scores.
FEMALE_VOWELS = ("i", "ɪ", "ɛ", "æ", "ʌ", "ɑ", "ɔ", "o", "ʊ", "u")

#: The subject's initials, as the paper gives them. Used as the CSV's
#: ``subject`` so the keys read ``DJ/i`` the way Yang & Kasuya's read
#: ``female/i``, and so one source's columns cannot be taken for another's.
FEMALE_SUBJECT = "DJ"

#: The two vowels Table III images twice, by MRI and by electron-beam CT, on
#: different days. Same speaker, same vowel, two instruments -- which is the
#: repeatability question Story (2008) asks over eight years, asked here over
#: a few days and across a change of scanner.
FEMALE_REPEATS = (("i", "i-ct"), ("ɑ", "ɑ-ct"))

#: The rhotic's two columns: with the sublingual cavity added to the main tube,
#: and without it. The caption says the choice touches sections 33 and 34 only,
#: which are inside the labial exclusion, so no constriction reported here turns
#: on it -- and both are carried so that can be seen rather than asserted.
FEMALE_RHOTIC = ("ɝ", "ɝ-nosub")

#: The vowels both Story sets image. The 1996 set has ``ɝ`` and no ``e``; the
#: 2002 set has ``e`` and no ``ɝ``. Ten are common, and the comparison is over
#: those ten -- pairing ``e`` with ``ɛ``, or ``ɝ`` with anything, would be the
#: substitution this measurement exists to avoid.
BOTH_SESSIONS = ("i", "ɪ", "ɛ", "æ", "ʌ", "ɑ", "ɔ", "o", "ʊ", "u")

#: The IPA vowel quadrilateral, measured off the Association's own drawing of
#: it -- *The International Phonetic Alphabet (revised to 2020)*, the Kiel PDF
#: at https://www.internationalphoneticassociation.org/IPAcharts/ -- by
#: interpreting the page's content stream and reading the coordinates of the
#: lines it strokes. The figure's glyphs are in a custom-encoded font and
#: extract to nonsense, which is a trap this reference library already records;
#: the *paths* are ordinary numbers and are what is read here.
#:
#: In page points: the front edge runs from (381.3, 501.2) to (458.9, 386.3),
#: the back edge from (532.7, 501.2) to (532.7, 386.3). So the close edge is
#: 151.4 wide, the open edge 73.8, the two rungs are 114.9 apart, and the back
#: edge is *vertical* while the front edge slants back by 77.6 as it descends.
#:
#: That is Jones's figure drawn to his stated proportions. The footnote to
#: *An Outline of English Phonetics* 9th edn 149 gives the open, back and close
#: edges "in the proportion 2:3:4" with right angles at the back edge; measured,
#: they are 2 : 3.11 : 4.10, so the 2020 chart reproduces a 1969 footnote to
#: within 4%.
#:
#: Two asymmetries, and they are different facts. The back edge is shorter than
#: the front edge, 114.9 against 138.7 -- Jones's own choice, and he gives the
#: reason at 137-139: between the four back cardinals the *tongue* moves less,
#: because the lips do part of the work. And the open edge is shorter than the
#: close edge, which is what makes the front and back columns converge as a
#: vowel opens. Only the second is a free number here; the first is a
#: consequence of it and of the right angles.
CHART_INSET = 77.6 / 151.4

#: Where each declared ``height`` value sits on that figure, as a fraction of
#: the 114.9-point drop from the close edge to the open edge. Read the same
#: way: the text-positioning matrices give a baseline per row without anyone
#: having to decode which glyph is which, and the four struck rungs (close,
#: close-mid, open-mid, open) fix the offset between a baseline and its rung.
#:
#: The measured fractions are 0.000, 0.155, 0.328, 0.489, 0.657, 0.820, 0.999 --
#: an even seven-rung ladder to within 0.013, which is what is used, because a
#: ladder read to three decimals off one drawing is a precision the drawing does
#: not have. ``height`` declares an ``offset`` per value and its steps are even
#: to the same tolerance.
CHART_ROWS = (
    "close",
    "near-close",
    "close-mid",
    "mid",
    "open-mid",
    "near-open",
    "open",
)

#: And each declared ``backness`` value, across the figure. The chart strikes
#: three columns -- front at 0.0, central at 0.500 measured, back at 1.0 -- and
#: draws no near-front or near-back line at all. Those two are ipakit's own
#: declaration, and they are placed here at the quarters, which is what their
#: declared arcs already are to within 0.01.
CHART_COLUMNS = ("front", "near-front", "central", "near-back", "back")

#: The three corners the quadrilateral is pinned to, as ``place`` names, and
#: the alternative each could defensibly take. The chart states no scale, no
#: anatomical anchor and no correspondence to centimetres, so a projection has
#: to be given its corners from outside the figure; these are the anatomical
#: names Wood's four locations already carry, which is the least arbitrary
#: anchoring available and the one most favourable to the construction. Every
#: corner lands on its own anchor by construction, so what the projection is
#: actually asked for is the interior of the figure.
CHART_CORNERS = (
    ("close", "front", ("palatal",)),
    ("close", "back", ("velar", "uvular")),
    ("open", "back", ("pharyngeal", "epiglottal")),
)

#: How far the tongue body stands off the midline, as a fraction of head
#: height. It cancels at the corners and does not in the interior, so it is a
#: free parameter of the construction and is swept. The shipped adult-male
#: midline is 1.0476 units long for a declared 17.5 cm, so these are roughly
#: 0.3 to 2.7 cm.
CHART_STANDOFFS = (0.02, 0.04, 0.08, 0.12, 0.16)

#: Which cell of the figure each measured vowel occupies, from ``ipa.xml``.
#: Read live rather than restated: ``chart`` asks what the figure would say
#: about a vowel ipakit has already placed in it.
#:
#: The rhotic has no cell of the figure's own -- ``ɝ`` is central and open-mid
#: by declaration, and its constriction is measured forward of ``i``.
CHART_SKIP = ("ɝ",)

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
EXPECTED_FOURTH_COLUMNS = 14
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


def declared(extra: Sequence[str] = ()) -> dict[str, float | None]:
    """The ``arc`` ipakit computes for each imaged shape, from its own data.

    ``extra`` names symbols outside Story et al.'s eighteen. Yang & Kasuya
    image Japanese ``/a/`` and ``/e/``, which Story does not, and without them
    a reading scored off this table is scored over nine of that source's
    fifteen columns while Wood's is scored over all fifteen. That is a bias in
    the instrument rather than in either reading, and it is why the caller
    passes the symbols it means to score rather than taking the shape list.
    """
    features = IPAFeatures()
    out: dict[str, float | None] = {}
    for symbol in [sym for sym, _, _ in SHAPES] + list(extra):
        bundle = features.get_features(symbol)
        out[symbol] = tract_point(features, bundle).arc if bundle else None
    return out


def backness_only(extra: Sequence[str] = ()) -> dict[str, float | None]:
    """The ``arc`` ``backness`` alone gives each imaged shape.

    Not the same question as :func:`declared`, and it stopped being the same
    question when vowels started stating a ``constriction-location``.
    ``anchors`` scores four readings and two of them would otherwise be the
    same column under two headings -- which is how a baseline goes stale
    without anything saying so, because the number moves and the header does
    not. This one reads the ``backness`` coordinate table directly, so the row
    the assessment records for it stays reproducible whatever a phone declares.
    """
    features = IPAFeatures()
    coordinates = features.features["backness"].coordinates
    out: dict[str, float | None] = {}
    for symbol in [sym for sym, _, _ in SHAPES] + list(extra):
        bundle = features.get_features(symbol)
        value = bundle.get("backness") if bundle else None
        out[symbol] = coordinates.get(value, {}).get("arc") if value else None
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


class Female(Intra):
    """Story, Titze & Hoffman (1998) Tables III and IV, keyed ``DJ/vowel``.

    The 1996 relation between the printed tract length and the section
    length, because it is the same laboratory, the same procedure and the
    same stated convention: section 1 is the glottal end, the last section
    is the lips, and the tube is ``sections * dl`` long. The columns are
    ragged -- 30 sections for ``æ`` and 38 for ``u`` -- which is the table's
    own record of how much longer a rounded vowel's tract is.
    """


def parse_female(text: str) -> Female:
    """Read the CSV, and check it against the distances it carries.

    Table III is an image in every copy of this paper: the text layer maps
    every IPA symbol to a different character, and the column headers along
    with them. So the risk this transcription runs is not a misread digit in
    one cell but a *row out of register* -- a dropped or duplicated line,
    which shifts every section under it by one and moves an arc by 1/38 of
    the tract without making any single number look wrong.

    The paper prints the distance from the glottis beside the section
    number, so the two can be re-derived from each other. A row at its
    right section has ``dist_cm`` within a rounding of ``section * dl``; a
    row out of register is a whole section away. Half a section is
    therefore the bound, and it is the one used, because it fails on
    exactly the mistake this check exists for and on nothing else.

    It is not a tight bound, and the reason is worth recording: the two
    tables round their own distance column differently. Table III prints
    ``section * 0.396825`` and Table IV prints ``section * 0.396``, though
    both captions state the interval as 0.396 825 cm. That is a printing
    inconsistency inside the paper, it reaches 0.032 cm by section 38, and
    a check tight enough to reject it would be rejecting the paper rather
    than the transcription.

    Perturbed, over the transcription this reads: dropping a row, adding
    one, moving a distance by a section, and losing a column are each
    refused, by name. **What it does not see** is a distance wrong by less
    than half a section, and an area copied from the neighbouring row with
    the section number left right -- the distance column pins which section
    a row is, and nothing here can pin what is in it. The three
    cross-checks that did that were made once, by hand, off the prose, and
    are recorded beside the CSV rather than run: the CT ``ɑ`` is "about 0.8
    cm longer than the MRI" and its column is two sections longer, and the
    paper's description of where each ``ɑ`` falls after its maximum picks
    out the right one of the two columns.
    """
    area: dict[str, list[float]] = {}
    interval: dict[str, float] = {}
    stated: dict[str, float] = {}
    printed: dict[str, list[tuple[int, float]]] = {}
    rows = [
        line for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    for row in csv.DictReader(rows):
        key = f"{row['subject']}/{row['vowel']}"
        area.setdefault(key, []).append(float(row["area_cm2"]))
        printed.setdefault(key, []).append((int(row["section"]), float(row["dist_cm"])))
        interval[key] = float(row["dl_cm"])
        stated[key] = float(row["L_cm"])
    if len(area) != EXPECTED_FOURTH_COLUMNS:
        raise ValueError(
            f"read {len(area)} columns, expected {EXPECTED_FOURTH_COLUMNS} "
            "(12 in Table III and 2 in Table IV)"
        )
    for key, column in area.items():
        step = interval[key]
        sections = [n for n, _ in printed[key]]
        if sections != list(range(1, len(column) + 1)):
            raise ValueError(f"{key}: sections are not 1..{len(column)} in order")
        for section, distance in printed[key]:
            if abs(distance - section * step) > step / 2:
                raise ValueError(
                    f"{key}: section {section} is printed at {distance} cm, "
                    f"more than half a section from the {section * step:.3f} cm "
                    "its own section number gives"
                )
        derived = len(column) * step
        if abs(derived - stated[key]) > 0.05:
            raise ValueError(
                f"{key}: {len(column)} sections of {step} cm give "
                f"{derived:.2f} cm, against a printed length of {stated[key]}"
            )
    return Female(area, interval)


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
            # A family may name a vowel no source here images -- `œ` and `ɯ`
            # are Wood's and nobody's MRI -- and those have no shape to divide
            # by. They are not dropped from the classification, only from this
            # reading of it.
            length = lengths.get(symbol)
            if length is None:
                continue
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


@functools.cache
def _midline() -> tuple[tuple[float, float, float], ...]:
    """A dense resampling of the shipped adult-male midline.

    Every point behind ``arc`` 0.45 carries ``provenance="extrapolated"``:
    ``docs/articulatory-data.md`` says outright that the X-Ray Microbeam
    instrument sees nothing behind 0.44, so the pharyngeal half of this
    polyline is drawn rather than measured. A projection that gets its
    behaviour from the tract's bend is getting it from there.
    """
    knots = [(p.arc, p.x, p.y) for p in head("adult-male").midline]
    dense: list[tuple[float, float, float]] = []
    for (a0, x0, y0), (a1, x1, y1) in itertools.pairwise(knots):
        for step in range(400):
            fraction = step / 400
            dense.append(
                (
                    a0 + fraction * (a1 - a0),
                    x0 + fraction * (x1 - x0),
                    y0 + fraction * (y1 - y0),
                )
            )
    dense.append(knots[-1])
    return tuple(dense)


@functools.cache
def _tangent(arc: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """The midline point at a declared arc, and its unit tangent there."""
    knots = [(p.arc, p.x, p.y) for p in head("adult-male").midline]
    for (a0, x0, y0), (a1, x1, y1) in itertools.pairwise(knots):
        if a0 <= arc <= a1:
            fraction = (arc - a0) / (a1 - a0)
            run, rise = x1 - x0, y1 - y0
            span = math.hypot(run, rise)
            return (x0 + fraction * run, y0 + fraction * rise), (
                run / span,
                rise / span,
            )
    raise ValueError(f"arc {arc} is off the midline")


def _corner(arc: float, standoff: float) -> tuple[float, float]:
    """Where the tongue body sits to constrict at ``arc``.

    Off the midline by ``standoff``, on the side the tongue is on -- the
    tangent turned a quarter turn, which is inferior over the oral run and
    anterior in the pharynx because the midline bends between them. It cancels
    at the three pinned corners and does not in the interior, which is why it
    is a free parameter of the construction rather than a detail of it.
    """
    (x, y), (run, rise) = _tangent(arc)
    return (x + standoff * rise, y - standoff * run)


def _projected(point: tuple[float, float]) -> float:
    """The arc of the midline point nearest a tongue-body position."""
    x, y = point
    return min(_midline(), key=lambda q: (q[1] - x) ** 2 + (q[2] - y) ** 2)[0]


@functools.cache
def _pivot() -> tuple[float, float]:
    """The centre of curvature of the tract, from three points on it.

    Not a free parameter: the circle through the palatal, uvular and
    pharyngeal midline points, which is where an arch sweeping those three
    would have to be centred.
    """
    places = landmarks(IPAFeatures()).places
    (ax, ay), (bx, by), (cx, cy) = (
        _tangent(places[name])[0] for name in ("palatal", "uvular", "pharyngeal")
    )
    scale = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    sa, sb, sc = ax**2 + ay**2, bx**2 + by**2, cx**2 + cy**2
    return (
        (sa * (by - cy) + sb * (cy - ay) + sc * (ay - by)) / scale,
        (sa * (cx - bx) + sb * (ax - cx) + sc * (bx - ax)) / scale,
    )


def chart_cell(height: str, backness: str, inset: float) -> tuple[float, float]:
    """A declared (height, backness) pair as a point of the quadrilateral.

    ``(0, 0)`` is the close front corner and ``(1, 1)`` the open back one. The
    front edge slants back by ``inset`` of the close edge's width as it
    descends, which is the figure's whole departure from a rectangle.
    """
    down = CHART_ROWS.index(height) / (len(CHART_ROWS) - 1)
    across = CHART_COLUMNS.index(backness) / (len(CHART_COLUMNS) - 1)
    return inset * down + across * (1 - inset * down), down


def chart_affine(
    cell: tuple[float, float], standoff: float, corners: tuple[float, ...]
) -> float:
    """The figure laid flat in the sagittal plane, three corners pinned.

    Three points fix an affine map, so pinning the close front, close back and
    open back corners places the whole figure, and the open front corner falls
    where the trapezoid puts it. Height is then one direction everywhere: the
    displacement that carries a close back vowel down the pharynx carries a
    close front vowel back along the palate.
    """
    across, down = cell
    front, back, low = (_corner(arc, standoff) for arc in corners)
    return _projected(
        (
            front[0] + across * (back[0] - front[0]) + down * (low[0] - back[0]),
            front[1] + across * (back[1] - front[1]) + down * (low[1] - back[1]),
        )
    )


def chart_polar(
    cell: tuple[float, float], standoff: float, corners: tuple[float, ...]
) -> float:
    """The figure wrapped around the tract's own bend instead.

    The same figure, read as the tongue arch it was named for: backness is an
    angle about the centre of curvature of the tract, height is how near the
    arch comes to the wall. Both readings lay the quadrilateral in the
    mid-sagittal plane and pin it to the same corners. The chart says nothing
    that chooses between them.
    """
    across, down = cell
    pivot = _pivot()

    def angle(arc: float) -> float:
        (x, y), _ = _tangent(arc)
        return math.atan2(y - pivot[1], x - pivot[0])

    swept = angle(corners[0]) + across * (angle(corners[2]) - angle(corners[0]))
    on_wall = min(
        _midline(),
        key=lambda q: abs(math.atan2(q[2] - pivot[1], q[1] - pivot[0]) - swept),
    )
    reach = math.hypot(on_wall[1] - pivot[0], on_wall[2] - pivot[1]) - standoff * (
        0.3 + down
    )
    return _projected(
        (pivot[0] + reach * math.cos(swept), pivot[1] + reach * math.sin(swept))
    )


#: The two readings, and the point of having two. Each lays the quadrilateral
#: in the mid-sagittal plane, pins it to the same three anatomical corners and
#: projects onto the same midline. They disagree about the interior by more
#: than the whole declared span, and nothing in the figure prefers either.
CHART_READINGS = {"affine": chart_affine, "polar": chart_polar}


def _chart_embeddings() -> list[tuple[str, float, float, tuple[float, ...]]]:
    """Every embedding swept: reading, front-edge inset, standoff, corners."""
    places = landmarks(IPAFeatures()).places
    return [
        (name, inset, standoff, corners)
        for name in CHART_READINGS
        for inset in (0.0, CHART_INSET, 0.7)
        for standoff in CHART_STANDOFFS
        for corners in itertools.product(
            *([places[n] for n in names] for _, _, names in CHART_CORNERS)
        )
    ]


def _chart_arcs(
    embedding: tuple[str, float, float, tuple[float, ...]],
    cells: dict[str, tuple[str, str]],
) -> dict[str, float]:
    """Every measured vowel's arc under one embedding."""
    name, inset, standoff, corners = embedding
    reading = CHART_READINGS[name]
    return {
        symbol: reading(chart_cell(height, backness, inset), standoff, corners)
        for symbol, (height, backness) in cells.items()
    }


def cmd_chart(table: Table, args: argparse.Namespace) -> int:
    """Can a constriction location be got out of the vowel chart's geometry?

    The quadrilateral is a stated model of tongue-body position with no free
    parameters to fit, so a location projected out of it would be a
    declaration rather than a fit -- which is the shape of evidence
    ``docs/design/vowel-constriction.md`` could not obtain from any source.
    This measures whether that projection exists.

    Two things are asked. Whether the figure's own asymmetry produces the
    height-by-backness interaction the measurement shows, which is what would
    make it worth having; and whether the answer survives the choices the
    figure does not make, which is what would make it a declaration.
    """
    cells = _chart_cells()
    sources = _chart_sources(table, args)
    places = landmarks(IPAFeatures()).places
    default = tuple(places[names[0]] for _, _, names in CHART_CORNERS)

    print(
        "The IPA quadrilateral, laid in the mid-sagittal plane and projected onto\n"
        "the shipped adult-male midline. Corners pinned at "
        + ", ".join(f"{n[0]} {places[n[0]]:.2f}" for _, _, n in CHART_CORNERS)
        + f";\nfront edge inset {CHART_INSET:.3f}, measured off the 2020 chart.\n"
    )
    for name, reading in CHART_READINGS.items():
        print(f"  {name}")
        print(f"  {'':>11}" + "".join(f"{b:>12}" for b in CHART_COLUMNS))
        for row in CHART_ROWS:
            print(
                f"  {row:>11}"
                + "".join(
                    f"{reading(chart_cell(row, col, CHART_INSET), 0.04, default):>12.3f}"
                    for col in CHART_COLUMNS
                )
            )
        print()

    print(
        "The interaction, against the differences `tests/test_vowel_tract_limit.py`\n"
        "pins the limit on. Height's effect at fixed backness is near zero at the\n"
        "front and large at the back, and a projection has to reproduce that.\n"
    )
    print(f"  {'reading':>10} {'front i-ɛ':>10} {'back u-ʌ':>10} {'back - front':>13}")
    front_step = _chart_step(sources, ("i", "ɛ"))
    back_step = _chart_step(sources, ("u", "ʌ"))
    need = back_step - front_step
    print(f"  {'measured':>10} {front_step:>+10.3f} {back_step:>+10.3f} {need:>+13.3f}")

    spread: dict[str, list[float]] = {symbol: [] for symbol in cells}
    gaps: list[float] = []
    hits: dict[str, list[int]] = {name: [] for name in CHART_READINGS}
    for embedding in _chart_embeddings():
        arcs = _chart_arcs(embedding, cells)
        for symbol, value in arcs.items():
            spread[symbol].append(value)
        gaps.append((arcs["ʌ"] - arcs["u"]) - (arcs["ɛ"] - arcs["i"]))
        hits[embedding[0]].append(_chart_score(sources, arcs))
        if embedding[1:] == (CHART_INSET, 0.04, default):
            print(
                f"  {embedding[0]:>10} {arcs['ɛ'] - arcs['i']:>+10.3f} "
                f"{arcs['ʌ'] - arcs['u']:>+10.3f} {gaps[-1]:>+13.3f}"
            )

    print(
        f"\nOver all {len(gaps)} embeddings the interaction runs {min(gaps):+.3f} to "
        f"{max(gaps):+.3f}, against\nthe {need:+.3f} the measurement asks for. It is "
        f"positive in {sum(1 for g in gaps if g > 0)} of {len(gaps)}, and reaches\n"
        f"{need:+.3f} in {sum(1 for g in gaps if g >= need)}."
    )

    counted = sum(
        1
        for _, source, keys in sources
        for key in keys
        if source.band(key, DEFAULT_GLOTTAL_CM, DEFAULT_LABIAL_CM, 2.0) is not None
        and key.split("/")[-1] in cells
    )
    # A floor, not a total: one source gives 10 bands and three give 35, and
    # which are mounted is the caller's business. What this refuses is a run
    # that scored nothing and printed counts anyway.
    assert counted > 5, f"only {counted} bands: the comparison is vacuous"
    # The Japanese vowels are passed, and it matters. `declared` takes the
    # symbols the caller means to score for the reason its own docstring
    # gives: Story images no /a/ and no /e/, so a reading built off the shape
    # list alone is scored over nine of Yang & Kasuya's fifteen columns while
    # Wood's is scored over all fifteen -- a bias in the instrument, worth six
    # bands, and it lands on the baseline every embedding here is measured
    # against.
    today = _chart_score(sources, declared([vowel for vowel, _ in JAPANESE]))
    families = {sym: name for name, _, family in WOOD_LOCATIONS for sym in family}
    families.update(dict(JAPANESE))
    proportional = wood_proportional()
    place_arcs = landmarks(IPAFeatures()).places
    wood = _chart_score(
        sources, {s: proportional.get(n) for s, n in families.items() if n}
    )
    as_place = _chart_score(
        sources,
        {s: place_arcs.get(WOOD_AS_PLACE[n]) for s, n in families.items() if n},
    )
    print(f"\nBand inclusion over the same embeddings, of {counted}.\n")
    print(
        f"  {'reading':>10} {'worst':>6} {'best':>6} {'over library':>14} "
        f"{'reaching place':>15}"
    )
    for name, counts in hits.items():
        print(
            f"  {name:>10} {min(counts):>6} {max(counts):>6} "
            f"{sum(1 for c in counts if c > today):>8} of {len(counts):<3} "
            f"{sum(1 for c in counts if c >= as_place):>9} of {len(counts):<3}"
        )
    print(f"  {'library':>10} {today:>6} {today:>6}   what tract_point answers now")
    print(f"  {'place':>10} {as_place:>6} {as_place:>6}   Wood's four families")
    print(f"  {'Wood':>10} {wood:>6} {wood:>6}   his own four proportions")
    every = [count for counts in hits.values() for count in counts]
    print(
        f"\nA verdict that runs from {min(every)} to {max(every)} on choices the "
        "chart does not make is a\nreport of the embedding, not of the chart. The "
        f"best of them beats Wood's {wood} at\n"
        f"{sum(1 for c in every if c > wood)} of {len(every)} settings, and finding "
        "the best is reading the scores and taking\none, which is the fit this "
        "measurement exists to avoid."
    )

    print("\nAnd what one cell's arc does across the embeddings.\n")
    print(f"  {'cell':>6} {'lowest':>8} {'highest':>8} {'spread':>8} {'measured':>9}")
    for symbol in sorted(spread, key=lambda s: min(spread[s]) - max(spread[s])):
        low, high = min(spread[symbol]), max(spread[symbol])
        found = _chart_measured(sources, symbol)
        shown = f"{found:>9.3f}" if found is not None else f"{'-':>9}"
        print(f"  {symbol:>6} {low:>8.3f} {high:>8.3f} {high - low:>8.3f}{shown}")
    print(
        "\nThe declared `backness` span is 0.24 end to end, and the cross-source\n"
        "spread that refused a fitted cell table ran 0.059 to 0.284."
    )
    return 0


def _chart_cells() -> dict[str, tuple[str, str]]:
    """Each measured vowel's cell of the figure, read from ``ipa.xml``."""
    ipa = IPAFeatures()
    cells: dict[str, tuple[str, str]] = {}
    for symbol in sorted({*VOWELS, *BOTH_SESSIONS, *(v for v, _ in JAPANESE)}):
        if symbol in CHART_SKIP:
            continue
        bundle = ipa.get_features(symbol)
        cells[symbol] = (bundle["height"], bundle["backness"])
    return cells


def _chart_sources(
    table: Table, args: argparse.Namespace
) -> list[tuple[str, Table, tuple[str, ...]]]:
    """The same bands ``anchors`` scores over, so the counts are comparable."""
    out: list[tuple[str, Table, tuple[str, ...]]] = [
        ("Story 1996", table, tuple(v for v in VOWELS if v not in CHART_SKIP))
    ]
    third = getattr(args, "table_three", None)
    if third is not None:
        out.append(("Story 2002", third, BOTH_SESSIONS))
    fourth = getattr(args, "table_four", None)
    if fourth is not None:
        out.append(
            (
                "Story 1998",
                fourth,
                tuple(f"{FEMALE_SUBJECT}/{vowel}" for vowel in FEMALE_VOWELS),
            )
        )
    second = getattr(args, "table_two", None)
    if second is not None:
        out.append(
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
    return out


def _chart_score(
    sources: list[tuple[str, Table, tuple[str, ...]]],
    arcs: Mapping[str, float | None],
) -> int:
    """How many measured bands a reading of the vowels lands inside."""
    inside = 0
    for _, source, keys in sources:
        for key in keys:
            band = source.band(key, DEFAULT_GLOTTAL_CM, DEFAULT_LABIAL_CM, 2.0)
            value = arcs.get(key.split("/")[-1])
            if band is not None and value is not None and band[0] <= value <= band[1]:
                inside += 1
    return inside


def _chart_step(
    sources: list[tuple[str, Table, tuple[str, ...]]], pair: tuple[str, str]
) -> float:
    """How far the measured constriction moves between two imaged vowels."""
    first, second = (_chart_measured(sources, symbol) for symbol in pair)
    assert first is not None and second is not None, pair
    return second - first


def _chart_measured(
    sources: list[tuple[str, Table, tuple[str, ...]]], symbol: str
) -> float | None:
    """The narrowest section's arc, from the first source that images it."""
    for _, source, keys in sources:
        for key in keys:
            if key.split("/")[-1] != symbol:
                continue
            found = source.narrowest(
                symbol if key == symbol else key, DEFAULT_GLOTTAL_CM, DEFAULT_LABIAL_CM
            )
            if found is not None:
                return found[0]
    return None


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


#: The candidate anchors an unclassified vowel could be declared at, as
#: ``place`` names. Nothing else is a candidate: `vowel-constriction.md` 8
#: refuses a value fitted to the sources, so a declaration has to land on an
#: arc the inventory already declares, and these are the four the tongue body
#: can reach. ``female`` scores every one of them against every band, which is
#: what turns "declare it" into a question with an answer.
CANDIDATES = ("palatal", "velar", "uvular", "pharyngeal")


def cmd_female(table: Table, args: argparse.Namespace) -> int:
    """A second speaker of the language the other two sessions image.

    ``replicate`` changes speaker and language together, so a coordinate
    that fails there can always be answered by saying the sources measured
    different people speaking different languages. ``intra`` changes
    neither and asks whether one speaker reproduces herself. This changes
    the speaker and holds the language, which is the case in between and
    the one a per-symbol declaration actually rests on: a coordinate
    declared for ``ʌ`` is a claim about the symbol, not about a person.

    And it is the only measured source that images two of the fifteen
    vowels stating no constriction location -- ``ʌ`` and ``ɝ`` -- so it is
    where the question of declaring either gets its evidence.
    """
    fourth = getattr(args, "table_four", None)
    if fourth is None:
        print(
            f"no fourth source given: pass --fourth or set ${FOURTH_ENV} to a "
            "CSV of\nStory, Titze & Hoffman (1998) Tables III and IV. See this "
            "module's docstring\nfor the columns."
        )
        return 0
    third = getattr(args, "table_three", None)
    arcs = declared()
    place_arcs = landmarks(IPAFeatures()).places

    def key(symbol: str) -> str:
        return f"{FEMALE_SUBJECT}/{symbol}"

    print("Story, Titze & Hoffman (1998): subject DJ, a 27-year-old female native")
    print("to Texas, on a GE Signa 1.5-T scanner. Table III's ten vowels, the two")
    print("electron-beam CT repeats, and Table IV's rhotic. Bands are the same")
    print(f"instrument as `bands`, at a depth factor of {args.depth:g}.\n")
    print(
        f"  {'':9} {'sections':>8} {'length cm':>9} {'narrowest':>9} {'cm':>6} "
        f"{'cm^2':>6}  {'band':>15} {'width':>6}"
    )
    wide = 0
    scored = 0
    for symbol in (*FEMALE_VOWELS, *(ct for _, ct in FEMALE_REPEATS), *FEMALE_RHOTIC):
        found = fourth.narrowest(key(symbol), args.glottal, args.labial)
        band = fourth.band(key(symbol), args.glottal, args.labial, args.depth)
        if found is None or band is None:
            print(f"  {symbol:9} {'no minimum in the window':>8}")
            continue
        width = band[1] - band[0]
        if symbol in FEMALE_VOWELS:
            scored += 1
            wide += width > 0.5
        print(
            f"  {symbol:9} {len(fourth.area[key(symbol)]):>8} "
            f"{fourth.length(key(symbol)):>9.2f} {found[0]:>9.3f} {found[1]:>6.2f} "
            f"{found[2]:>6.2f}  {band[0]:.3f}-{band[1]:<9.3f} {width:>6.3f}"
        )
    print(
        f"\n{wide} of this speaker's {scored} bands span more than half the tract "
        "and admit almost\nany anchor. That is the instrument's limit on this "
        "source and not a result:\nher area functions are flatter than the male's, "
        "and the paper says why -- the\nMR scanner's noise made her phonate much "
        "louder than conversational speech."
    )

    print("\nThe two vowels imaged twice, by MRI and by CT on different days.")
    print("Same speaker, same vowel, two instruments: the repeatability floor")
    print("under everything else here.\n")
    print(f"  {'':9} {'MRI':>6} {'CT':>6} {'move':>6}  {'bands overlap':>13}")
    for mri, ct in FEMALE_REPEATS:
        one = fourth.narrowest(key(mri), args.glottal, args.labial)
        two = fourth.narrowest(key(ct), args.glottal, args.labial)
        left = fourth.band(key(mri), args.glottal, args.labial, args.depth)
        right = fourth.band(key(ct), args.glottal, args.labial, args.depth)
        assert one and two and left and right
        touches = not (left[1] < right[0] or right[1] < left[0])
        print(
            f"  {mri:9} {one[0]:>6.3f} {two[0]:>6.3f} {abs(two[0] - one[0]):>6.3f}"
            f"  {'yes' if touches else 'NO':>13}"
        )

    sessions: list[tuple[str, Table]] = [("1996 male", table)]
    if third is not None:
        sessions.append(("2002 male", third))
    print("\nThe same vowel across every American English session held here, as the")
    print("arc of the narrowest section and the band around it.\n")
    print(
        f"  {'':3} "
        + " ".join(f"{name:>26}" for name, _ in sessions)
        + f" {'1998 female':>26}  {'shared':>13}"
    )
    for symbol in FEMALE_VOWELS:
        cells = []
        windows: list[tuple[float, float]] = []
        for _, source in sessions:
            found = source.narrowest(symbol, args.glottal, args.labial)
            band = source.band(symbol, args.glottal, args.labial, args.depth)
            if found is None or band is None:
                cells.append("no minimum")
                continue
            windows.append(band)
            cells.append(f"{found[0]:.3f} [{band[0]:.3f},{band[1]:.3f}]")
        found = fourth.narrowest(key(symbol), args.glottal, args.labial)
        band = fourth.band(key(symbol), args.glottal, args.labial, args.depth)
        assert found is not None and band is not None
        windows.append(band)
        cells.append(f"{found[0]:.3f} [{band[0]:.3f},{band[1]:.3f}]")
        low = max(w[0] for w in windows)
        high = min(w[1] for w in windows)
        shared = f"{low:.3f}-{high:.3f}" if low <= high else "none"
        print(
            f"  {symbol:3} " + " ".join(f"{c:>26}" for c in cells) + f"  {shared:>13}"
        )
    print(
        "\n`shared` is the intersection of the bands, which is where a single arc\n"
        "for the symbol would have to sit to satisfy every session at once."
    )

    print("\nWhat this speaker says about the arcs the library answers today, over")
    print("her bands narrower than half the tract -- the wide ones admit everything")
    print("and would count as agreement without being any.\n")
    print(f"  {'':3} {'band':>15} {'library':>7} {'':>16} {'Wood':>6} {'':>7}")
    proportional = wood_proportional()
    families = {sym: name for name, _, family in WOOD_LOCATIONS for sym in family}
    ahead = missed = 0
    hits = {"library": 0, "Wood": 0}
    narrow = 0
    for symbol in FEMALE_VOWELS:
        band = fourth.band(key(symbol), args.glottal, args.labial, args.depth)
        value = arcs[symbol]
        if band is None or value is None or band[1] - band[0] > 0.5:
            continue
        narrow += 1
        family = families.get(symbol)
        cells = []
        for name, anchor in (
            ("library", value),
            ("Wood", proportional[family] if family else None),
        ):
            if anchor is None:
                cells.append(f"{'no family':>23}")
                continue
            if band[0] <= anchor <= band[1]:
                hits[name] += 1
                verdict = "inside"
            else:
                if name == "library":
                    missed += 1
                    ahead += anchor < band[0]
                verdict = (
                    f"{'in front by' if anchor < band[0] else 'behind by'} "
                    f"{min(abs(anchor - band[0]), abs(anchor - band[1])):.3f}"
                )
            cells.append(f"{anchor:>6.3f} {verdict:18}")
        print(f"  {symbol:3} {band[0]:.3f}-{band[1]:<9.3f} " + " ".join(cells))
    print(
        f"\n{hits['library']} of {narrow} for the library and {hits['Wood']} of "
        f"{narrow} for Wood, and every one of the library's\n{missed} misses is the "
        "declared arc sitting in *front* of the measured band. That\nis one direction "
        "and not scatter. Wood's own four proportions all sit further\nback than the "
        "arcs `place` declares under the same four names, and that gap is\nwhere this "
        "speaker's back vowels fall."
    )

    print("\nʌ, the first of the two unclassified vowels this source images.")
    print("Every anchor the inventory could declare it at, against every band,")
    print("swept over both free parameters. `today` is what it reads now:")
    print(f"`backness` back, {arcs['ʌ']:.2f}, reported as approximate.\n")
    anchors = {"today": arcs["ʌ"], **{n: place_arcs[n] for n in CANDIDATES}}
    names = list(anchors)
    print(
        f"  {'depth':>6} {'cutoff':>6} {'bands':>6} "
        + " ".join(f"{n:>11}" for n in names)
    )
    totals = dict.fromkeys(names, 0)
    every = 0
    for depth in DEPTH_FACTORS:
        for cut in (4.0, 5.0, 6.0, 7.0):
            counts = dict.fromkeys(names, 0)
            usable = 0
            for _, source in sessions:
                band = source.band("ʌ", cut, args.labial, depth)
                if band is None:
                    continue
                usable += 1
                for name in names:
                    counts[name] += band[0] <= anchors[name] <= band[1]
            band = fourth.band(key("ʌ"), cut, args.labial, depth)
            if band is not None:
                usable += 1
                for name in names:
                    counts[name] += band[0] <= anchors[name] <= band[1]
            every += usable
            for name in names:
                totals[name] += counts[name]
            print(
                f"  {depth:>6.2f} {cut:>6.1f} {usable:>6} "
                + " ".join(f"{counts[n]:>11}" for n in names)
            )
    print(
        f"  {'all':>6} {'':>6} {every:>6} "
        + " ".join(f"{totals[n]:>11}" for n in names)
    )
    print(
        "\nThe measured constriction is behind every anchor forward of it and in\n"
        "front of the one behind it, and the vocabulary declares nothing between\n"
        "`uvular` and `pharyngeal`. Declaring either is a claim the bands do not\n"
        "carry; declaring `uvular` would also move no arc at all and only remove\n"
        "the `approximate` mark, which is withdrawing a true caveat."
    )

    print("\nɝ, the second. Wood's four families cover the cardinal space and not")
    print("the American English rhotic, so there is no classification to adopt --")
    print("only the two sessions that image it, and they are these.\n")
    rhotic: list[tuple[str, Table, str]] = [("1996 male", table, "ɝ")]
    for column in FEMALE_RHOTIC:
        rhotic.append(("1998 female " + column, fourth, key(column)))
    for name, source, column in rhotic:
        found = source.narrowest(column, args.glottal, args.labial)
        assert found is not None
        print(
            f"  {name}: tract {source.length(column):.2f} cm, narrowest {found[0]:.3f}"
        )
        for arc, center, area in source.minima(column):
            note = " below the piriform cutoff" if center < args.glottal else ""
            print(
                f"     minimum at arc {arc:.3f}  {center:5.2f} cm  {area:5.2f} cm^2{note}"
            )
        for depth in DEPTH_FACTORS:
            band = source.band(column, args.glottal, args.labial, depth)
            assert band is not None
            print(f"     band at depth {depth:.2f}: {band[0]:.3f}-{band[1]:.3f}")
    print(
        f"\nipakit reads ɝ at {arcs['ɝ']:.2f}, from `backness` central, reported as "
        "approximate.\nThe two sessions' bands are disjoint at every depth up to "
        "2.0, so no single\narc is inside both and the question is not which value "
        "to declare. Both\ncolumns carry three or more supralaryngeal minima, which "
        "is what Zhou et al.\n(2008) report of the rhotic -- palatal, pharyngeal "
        "and labial constrictions\nat once -- and an (arc, offset) holds one of "
        "them."
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
    japanese = [vowel for vowel, _ in JAPANESE]
    arcs = backness_only(japanese)
    live = declared(japanese)

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
        if reading == "library":
            return live.get(symbol)
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
    fourth = getattr(args, "table_four", None)
    if fourth is not None:
        sources.append(
            (
                "Story 1998",
                fourth,
                tuple(f"{FEMALE_SUBJECT}/{vowel}" for vowel in FEMALE_VOWELS),
            )
        )
        for vowel in FEMALE_VOWELS:
            key = f"{FEMALE_SUBJECT}/{vowel}"
            if vowel in families:
                families[key] = families[vowel]
            arcs[key] = arcs.get(vowel)
            live[key] = live.get(vowel)
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
                live[f"{subject}/{vowel}"] = live.get(vowel)

    readings = ("backness", "Wood", "place", "library")
    print("\nBand inclusion, one row per source, at the default settings.")
    print("`backness` is the backness coordinate alone; `Wood` is his four")
    print("proportions; `place` is his four families read at the arcs ipa.xml")
    print("declares; `library` is what `tract_point` answers for the symbol now.\n")
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
        f"of {every} over the same\nsweep, and changes sign inside it: the instrument "
        "does not separate them."
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
    "female": cmd_female,
    "anchors": cmd_anchors,
    "chart": cmd_chart,
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
    parser.add_argument(
        "--fourth",
        default=os.environ.get(FOURTH_ENV),
        help=(
            "CSV of Story, Titze & Hoffman (1998) Tables III and IV "
            f"(default: ${FOURTH_ENV})"
        ),
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

    args.table_four = None
    if args.fourth:
        path_four = Path(args.fourth)
        if path_four.exists():
            try:
                args.table_four = parse_female(
                    path_four.read_text(encoding="utf-8", errors="replace")
                )
            except ValueError as error:
                print(f"{path_four}: {error}", file=sys.stderr)
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
