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
import itertools
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import head, tract_point  # noqa: E402

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

#: Shape assertions. The parse either reproduces the published table exactly or
#: it is wrong; these are not floors.
EXPECTED_COLUMNS = 18
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
            f"  {symbol:3} {word:7} {len(column):>8} {length:>9.2f} "
            f"{min(column):>9.2f}"
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


def cmd_arc(table: Table, args: argparse.Namespace) -> int:
    """Whether ``arc`` is the proportional midline position it says it is.

    Reads no external data -- it is here because every other measurement in
    this script assumes it, and the assumption had never been checked.
    """
    print("Declared arc against normalized arclength along each head's own midline.\n")
    worst = 0.0
    for name in ("adult-male", "adult-female", "child"):
        shape = head(name)
        points = shape.midline
        run = [0.0]
        for before, after in zip(points, points[1:], strict=False):
            step = ((after.x - before.x) ** 2 + (after.y - before.y) ** 2) ** 0.5
            run.append(run[-1] + step)
        total = run[-1]
        gaps = [
            abs(distance / total - point.arc)
            for point, distance in zip(points, run, strict=True)
        ]
        worst = max(worst, max(gaps))
        print(f"  {name:14} max |declared arc - arclength fraction| = {max(gaps):.3f}")
        if name == "adult-male":
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
            print(f"  {'':14} the places occlusions reach: {said}")
    print(f"\nlargest over all shipped heads: {worst:.3f}")
    print(
        "Heads never affect distance, so nothing is wrong today. But the comparison\n"
        "in this script reads the two as the same quantity, and nothing else does.\n"
        "Reading each declared arc as its own midline's arclength instead changes no\n"
        "verdict in `occlusions`, which is why that section is reported as it stands."
    )
    return 0


COMMANDS = {
    "table": cmd_table,
    "occlusions": cmd_occlusions,
    "vowels": cmd_vowels,
    "stability": cmd_stability,
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
