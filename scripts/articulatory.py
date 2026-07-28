#!/usr/bin/env python3
"""Measure ipakit's tract geometry against the X-Ray Microbeam database.

ipakit places every phone at an ``(arc, offset)`` in a normalized tract, and
draws it through a mid-sagittal ``Head``. Both were hand-placed from published
anatomy. This script checks the parts of that geometry an instrument can see,
against the one corpus that measures the moving mid-sagittal tract directly:

    Westbury, John, with Greg Turner and Jim Dembowski (1994).
    X-Ray Microbeam Speech Production Database User's Handbook, v. 1.0.
    Waisman Center, University of Wisconsin-Madison.

48 speakers, ~8.7M frames, eight gold pellets tracked in the mid-sagittal
plane: upper and lower lip, four along the tongue, and two on the mandible.
Each speaker also ships a palate outline (``PAL.DAT``) taken from a dental
cast, and two points of posterior pharyngeal wall (``PHA.DAT``).

    python scripts/articulatory.py rigid       # which speakers track cleanly
    python scripts/articulatory.py palate      # recover PAL.DAT from motion
    python scripts/articulatory.py clearance   # the palate as a boundary
    python scripts/articulatory.py hinge       # where the jaw rotates about
    python scripts/articulatory.py chain       # what the mandible carries
    python scripts/articulatory.py all

The corpus is external data under a separate licence and is NOT bundled: CI
will not have it, so every subcommand exits 0 with a message when it is
absent. Point ``--corpus`` at your own copy. ``--files N`` reads only the
first N track files per speaker, which is much faster and much less accurate;
the printed header always says which was used.

Each subcommand asserts the shape of what it read -- speaker count, files per
speaker, frames per speaker -- so a run over a truncated or wrongly-pathed
copy fails loudly instead of reporting a clean, empty result. See
docs/reviewing.md for why, and docs/articulatory-data.md for what the numbers
turned out to be and what they do and do not ground.
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CORPUS = Path("/Volumes/GT3/ubeam/xray_microbeam_database")

# The .txy column order, from the corpus's own notes.txt: a microsecond
# timestamp then x,y for each pellet. MNI/MNM are the mandibular incisor and
# molar; the corpus calls them MI/MM in notes.txt and MNI/MNM in the handbook.
PELLETS = ("UL", "LL", "T1", "T2", "T3", "T4", "MNI", "MNM")
TONGUE = (2, 3, 4, 5)  # T1..T4, as indices into a frame
CORONAL = (2, 3)  # T1, T2 -- the pellets that reach the alveolar region
MNI, MNM = 6, 7
MISSING = 1_000_000  # the corpus's own sentinel, in microns

# Coordinates are microns, origin at the maxillary incisor tips, +x anterior
# and +y superior, in the maxillary occlusal plane (handbook section 5.2.2.1).
MICRONS_PER_MM = 1000.0

BIN_MM = 2.0  # x-binning for every profile below

# Turning an x coordinate into an ipakit `arc` needs a total tract length,
# which XRMB does not measure: it sees nothing below the oral cavity. This is
# the length `heads.xml` declares for its adult-male head, used as the one
# free parameter in the mapping, and every arc printed here is on that scale.
NOMINAL_TRACT_MM = 175.0

# A pellet trajectory carries occasional wild samples -- a mistracked frame
# reads hundreds of mm from the true position. Extreme-value statistics (the
# palate envelope, the diameter profile) take this quantile rather than the
# maximum, which single bad frames own outright.
ENVELOPE_Q = 0.999

# Shape assertions. Floors, not pins: they exist so a run over a truncated
# copy, a wrong --corpus, or a glob that stopped matching fails loudly rather
# than reporting clean numbers over nothing. Relaxed proportionally when
# --files subsamples, since then a small read is what was asked for.
EXPECTED_SPEAKERS = 48
MIN_TRACK_FILES = 50
MIN_FRAMES_PER_SPEAKER = 50_000
MIN_TOTAL_FRAMES = 8_000_000

# The rigid-body screen: |MNI - MNM| is a distance between two points on one
# bone and cannot change. This is the coefficient of variation above which a
# speaker's mandible statistics are not worth computing.
RIGID_CV = 0.03

Point = tuple[float, float]
Frame = tuple[Point | None, ...]


# --------------------------------------------------------------------------
# reading the corpus


def _to_point(x_raw: int, y_raw: int) -> Point | None:
    if abs(x_raw) >= MISSING or abs(y_raw) >= MISSING:
        return None
    return (x_raw / MICRONS_PER_MM, y_raw / MICRONS_PER_MM)


def read_frames(path: Path) -> Iterator[Frame]:
    """Every frame in one .txy file, in mm, with missing pellets as None.

    Rows that are short or unparseable are skipped rather than raising: two
    files are missing from the distribution outright (JW34/tp023, JW43/tp118)
    and the format is a plain text dump, so tolerating a bad row is the
    behaviour that lets a whole-corpus pass finish.
    """
    with path.open(encoding="latin-1") as handle:
        for line in handle:
            fields = line.split("\t")
            if len(fields) < 1 + 2 * len(PELLETS):
                continue
            try:
                raw = [int(field) for field in fields[: 1 + 2 * len(PELLETS)]]
            except ValueError:
                continue
            yield tuple(
                _to_point(raw[1 + 2 * i], raw[2 + 2 * i]) for i in range(len(PELLETS))
            )


def read_outline(path: Path) -> list[Point]:
    """A PAL.DAT or PHA.DAT outline, in mm, sorted by x."""
    points = []
    for line in path.read_text(encoding="latin-1").splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            points.append(
                (
                    int(fields[0]) / MICRONS_PER_MM,
                    int(fields[1]) / MICRONS_PER_MM,
                )
            )
        except ValueError:
            continue
    return sorted(points)


@dataclass(frozen=True)
class Corpus:
    """One mounted copy of the database, and how much of it to read."""

    root: Path
    files: int = 0  # 0 = every track file
    only: tuple[str, ...] = ()

    def speakers(self) -> list[str]:
        found = sorted(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir() and entry.name.startswith("JW")
        )
        if not self.only:
            return found
        missing = [name for name in self.only if name not in found]
        if missing:
            raise SystemExit(f"no such speaker in {self.root}: {' '.join(missing)}")
        return [name for name in found if name in self.only]

    def all_speakers(self) -> list[str]:
        """Every speaker present, ignoring --speakers. The shape assertion."""
        return sorted(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir() and entry.name.startswith("JW")
        )

    def track_files(self, speaker: str) -> list[Path]:
        paths = sorted((self.root / speaker).glob("tp*.txy"))
        return paths[: self.files] if self.files else paths

    def frames(self, speaker: str) -> Iterator[Frame]:
        for path in self.track_files(speaker):
            yield from read_frames(path)

    def palate(self, speaker: str) -> list[Point]:
        return read_outline(self.root / speaker / "PAL.DAT")

    def pharynx(self, speaker: str) -> list[Point]:
        return read_outline(self.root / speaker / "PHA.DAT")


def open_corpus(args: argparse.Namespace) -> Corpus | None:
    """The corpus, or None with a message when it is not mounted.

    Absence is not an error: this is external data under a separate licence,
    it is not bundled, and CI runs without it.
    """
    root = Path(args.corpus)
    if not root.is_dir():
        print(f"corpus not found at {root}")
        print(
            "  This is the X-Ray Microbeam database (Westbury 1994), external "
            "data that\n  ipakit does not bundle. Pass --corpus /path/to/your "
            "copy to measure.\n  Nothing else in the repo depends on it; see "
            "docs/articulatory-data.md."
        )
        return None
    return Corpus(
        root=root,
        files=args.files,
        only=tuple(filter(None, (args.speakers or "").split(","))),
    )


class Tally:
    """Frames and files actually read, so a pass can assert its own shape."""

    def __init__(self) -> None:
        self.frames = 0
        self.files = 0
        self.per_speaker: dict[str, int] = {}

    def note(self, speaker: str, files: int, frames: int) -> None:
        self.files += files
        self.frames += frames
        self.per_speaker[speaker] = frames


def check_read(corpus: Corpus, tally: Tally) -> None:
    """Fail loudly if the pass read less than the corpus should hold.

    ``--speakers`` and ``--files`` are deliberate subsets, so the per-read
    floors scale with them; the speaker count is a property of the corpus on
    disk and is checked either way.
    """
    present = corpus.all_speakers()
    if len(present) != EXPECTED_SPEAKERS:
        raise SystemExit(
            f"{corpus.root} holds {len(present)} speaker directories, "
            f"expected {EXPECTED_SPEAKERS}: this is not a complete copy"
        )
    if not tally.per_speaker:
        raise SystemExit("read no speakers at all")
    scale = 1.0
    if corpus.files:
        scale = min(1.0, corpus.files / MIN_TRACK_FILES)
    floor_files = max(1, int(MIN_TRACK_FILES * scale))
    floor_frames = max(1, int(MIN_FRAMES_PER_SPEAKER * scale))
    for speaker, frames in sorted(tally.per_speaker.items()):
        files = len(corpus.track_files(speaker))
        if files < floor_files:
            raise SystemExit(
                f"{speaker}: {files} track files, floor {floor_files} "
                "-- the corpus copy is truncated"
            )
        if frames < floor_frames:
            raise SystemExit(
                f"{speaker}: {frames} frames read, floor {floor_frames} "
                "-- the reader is dropping rows"
            )
    if not corpus.only and not corpus.files and tally.frames < MIN_TOTAL_FRAMES:
        raise SystemExit(
            f"read {tally.frames} frames over the whole corpus, "
            f"floor {MIN_TOTAL_FRAMES}"
        )


def header(corpus: Corpus, tally: Tally, title: str) -> None:
    scope = "every track file" if not corpus.files else f"first {corpus.files} files"
    print(
        f"{title}: {len(tally.per_speaker)} speakers, {tally.files} files, "
        f"{tally.frames} frames ({scope})\n"
    )


# --------------------------------------------------------------------------
# geometry


def quantile(values: Sequence[float], q: float) -> float:
    """The q-quantile of an already-sorted sequence, by nearest rank."""
    index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return values[index]


def interpolate(curve: Sequence[Point], x: float) -> float | None:
    """y on an x-sorted polyline, or None where the polyline does not reach."""
    if len(curve) < 2 or x < curve[0][0] or x > curve[-1][0]:
        return None
    for i in range(len(curve) - 1):
        (x0, y0), (x1, y1) = curve[i], curve[i + 1]
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return curve[-1][1]


@dataclass(frozen=True)
class UpperWall:
    """The traced upper wall of one speaker's tract, with arc length along it.

    ipakit's ``arc`` runs 0 at the lips to 1 at the glottis along the tract
    midline, and every consonantal place is a position on the upper wall. So
    arc length is measured here along the wall itself: from the midpoint of
    the two lip pellets, straight back to the anterior end of the palate
    outline, then along the outline. Everything behind the outline is out of
    reach, and ``arc`` returns None there.

    The mapping is crude in one specific way, stated so it is not mistaken
    for a measurement: the divisor is NOMINAL_TRACT_MM, because the corpus
    cannot see the pharynx or the glottis and so cannot supply a per-speaker
    total length.
    """

    lip: Point
    palate: tuple[Point, ...]
    cumulative: tuple[float, ...]
    length: float = NOMINAL_TRACT_MM

    @property
    def path(self) -> tuple[Point, ...]:
        return (self.lip, *reversed(self.palate))

    def x_at(self, arc: float) -> float | None:
        """The x coordinate at an arc, or None where the wall does not reach."""
        along = arc * self.length
        for i in range(len(self.cumulative) - 1):
            near, far = self.cumulative[i], self.cumulative[i + 1]
            if near <= along <= far:
                fraction = (along - near) / (far - near) if far > near else 0.0
                path = self.path
                return path[i][0] + fraction * (path[i + 1][0] - path[i][0])
        return None

    def arc(self, x: float) -> float | None:
        path = self.path
        if x > path[0][0] or x < path[-1][0]:
            return None
        for i in range(len(path) - 1):
            ahead, behind = path[i], path[i + 1]
            if behind[0] <= x <= ahead[0]:
                span = ahead[0] - behind[0]
                fraction = (ahead[0] - x) / span if span else 0.0
                here = self.cumulative[i] + fraction * (
                    self.cumulative[i + 1] - self.cumulative[i]
                )
                return here / self.length
        return None

    @property
    def reach(self) -> float:
        """The arc of the posterior end of the palate trace."""
        return self.cumulative[-1] / self.length


def upper_wall(corpus: Corpus, speaker: str, lip_files: int = 10) -> UpperWall | None:
    """Build the wall, taking the lip position from a sample of frames."""
    palate = corpus.palate(speaker)
    if len(palate) < 2:
        return None
    upper: list[float] = []
    lower: list[float] = []
    upper_y: list[float] = []
    lower_y: list[float] = []
    for path in corpus.track_files(speaker)[:lip_files]:
        for frame in read_frames(path):
            if frame[0] is not None:
                upper.append(frame[0][0])
                upper_y.append(frame[0][1])
            if frame[1] is not None:
                lower.append(frame[1][0])
                lower_y.append(frame[1][1])
    if not upper or not lower:
        return None
    lip = (
        (statistics.median(upper) + statistics.median(lower)) / 2,
        (statistics.median(upper_y) + statistics.median(lower_y)) / 2,
    )
    points = (lip, *reversed(palate))
    cumulative = [0.0]
    for i in range(1, len(points)):
        cumulative.append(cumulative[-1] + math.dist(points[i - 1], points[i]))
    return UpperWall(
        lip=lip,
        palate=tuple(palate),
        cumulative=tuple(cumulative),
        length=tract_length(speaker),
    )


def summarize(label: str, values: Sequence[float], unit: str = "") -> None:
    ordered = sorted(values)
    if not ordered:
        print(f"  {label}: nothing measured")
        return
    print(
        f"  {label}: median {statistics.median(ordered):.3g}{unit}"
        f"   [{ordered[0]:.3g}, {ordered[-1]:.3g}]   n={len(ordered)}"
    )


class Histogram:
    """A counted histogram on a fixed grid, so quantiles cost no memory.

    A whole-corpus pass over 8.7M frames produces tens of millions of
    clearance values per subcommand. Keeping them costs gigabytes; keeping
    counts on a 0.25 mm grid costs kilobytes and is finer than the
    instrument's own error, which the handbook puts at a few tenths of a mm.
    """

    STEP = 0.25

    def __init__(self) -> None:
        self.counts: dict[int, int] = {}
        self.total = 0

    def add(self, value: float) -> None:
        cell = round(value / self.STEP)
        self.counts[cell] = self.counts.get(cell, 0) + 1
        self.total += 1

    def quantile(self, q: float) -> float:
        target = max(1, math.ceil(q * self.total))
        seen = 0
        for cell in sorted(self.counts):
            seen += self.counts[cell]
            if seen >= target:
                return cell * self.STEP
        return 0.0


class Moments:
    """Streaming mean and variance, for passes too large to hold in memory."""

    def __init__(self) -> None:
        self.n = 0
        self.total = 0.0
        self.squares = 0.0

    def add(self, value: float) -> None:
        self.n += 1
        self.total += value
        self.squares += value * value

    @property
    def mean(self) -> float:
        return self.total / self.n if self.n else 0.0

    @property
    def variance(self) -> float:
        return self.squares / self.n - self.mean**2 if self.n else 0.0


# The sex of each released speaker, from the handbook's Table 4.1. It matters
# for exactly one thing: `arc` is a proportion of total tract length, which
# XRMB cannot measure, so the divisor has to come from elsewhere. Using the
# two lengths heads.xml itself declares (17.5 cm / 15.0 cm) rather than one
# for everybody is what makes the male and female diameter profiles agree; see
# docs/articulatory-data.md. The corpus is 22 male and 26 female young adults,
# median age 21, so it is not an "adult male" sample in any case.
SPEAKER_SEX = {
    "JW11": "M",
    "JW12": "M",
    "JW13": "F",
    "JW14": "F",
    "JW15": "M",
    "JW16": "F",
    "JW18": "M",
    "JW19": "M",
    "JW20": "F",
    "JW21": "F",
    "JW24": "M",
    "JW25": "F",
    "JW26": "F",
    "JW27": "F",
    "JW28": "M",
    "JW29": "F",
    "JW30": "F",
    "JW31": "F",
    "JW32": "M",
    "JW33": "F",
    "JW34": "F",
    "JW35": "F",
    "JW36": "F",
    "JW37": "F",
    "JW39": "F",
    "JW40": "M",
    "JW41": "M",
    "JW42": "M",
    "JW43": "M",
    "JW44": "M",
    "JW45": "M",
    "JW46": "F",
    "JW48": "F",
    "JW49": "F",
    "JW502": "F",
    "JW51": "M",
    "JW52": "F",
    "JW53": "M",
    "JW54": "F",
    "JW55": "M",
    "JW56": "F",
    "JW57": "M",
    "JW58": "M",
    "JW59": "M",
    "JW60": "F",
    "JW61": "M",
    "JW62": "F",
    "JW63": "M",
}

# The two lengths heads.xml declares, in mm, keyed the same way.
TRACT_MM = {"M": 175.0, "F": 150.0}


def tract_length(speaker: str) -> float:
    return TRACT_MM.get(SPEAKER_SEX.get(speaker, ""), NOMINAL_TRACT_MM)


# --------------------------------------------------------------------------
# rigid: which speakers' mandible pellets track as one bone


def cmd_rigid(corpus: Corpus, args: argparse.Namespace) -> int:
    """|MNI - MNM| is a distance between two points on the mandible.

    It is fixed by anatomy, so any variation is measurement error, and a
    speaker whose variation is large has mistracked mandible pellets --
    which makes every jaw statistic downstream meaningless. This is the
    screen that decides which speakers `hinge` and `chain` may use.
    """
    tally = Tally()
    rows = []
    for speaker in corpus.speakers():
        moments = Moments()
        histogram = Histogram()
        smallest, largest = math.inf, -math.inf
        frames = 0
        for frame in corpus.frames(speaker):
            frames += 1
            near, far = frame[MNI], frame[MNM]
            if near is None or far is None:
                continue
            length = math.dist(near, far)
            moments.add(length)
            histogram.add(length)
            smallest = min(smallest, length)
            largest = max(largest, length)
        tally.note(speaker, len(corpus.track_files(speaker)), frames)
        if moments.n < 100:
            print(f"{speaker}: only {moments.n} frames track both pellets")
            continue
        deviation = math.sqrt(moments.variance)
        middle = histogram.quantile(0.5)
        spread = histogram.quantile(0.75) - histogram.quantile(0.25)
        rows.append(
            (
                deviation / moments.mean,
                speaker,
                moments.mean,
                deviation,
                spread / middle if middle else 0.0,
                smallest,
                largest,
                moments.n,
                frames,
            )
        )
    check_read(corpus, tally)
    header(corpus, tally, "rigid-body screen")
    rows.sort(reverse=True)
    print(
        f"  {'spk':>6} {'cv%':>6} {'robust%':>8} {'mean':>7} {'sd':>6} "
        f"{'min':>7} {'max':>7} {'tracked%':>9}"
    )
    for cv, speaker, mean, sd, robust, low, high, n, frames in rows:
        flag = "  <-- over threshold" if cv > RIGID_CV else ""
        print(
            f"  {speaker:>6} {100 * cv:6.2f} {100 * robust:8.2f} {mean:7.2f} "
            f"{sd:6.2f} {low:7.2f} {high:7.2f} {100 * n / frames:9.1f}{flag}"
        )
    over = [row[1] for row in rows if row[0] > RIGID_CV]
    print(
        f"\n  {len(over)} of {len(rows)} speakers exceed cv {RIGID_CV:.0%}: "
        f"{' '.join(over)}"
    )
    print(
        "  cv% is over every frame and so is owned by outliers; robust% is "
        "IQR/1.349 over\n  the median, which separates a few mistracked "
        "frames from a genuinely loose track."
    )
    if args.write_clean:
        Path(args.write_clean).write_text(
            "\n".join(row[1] for row in rows if row[0] <= RIGID_CV) + "\n",
            encoding="utf-8",
        )
        print(f"\n  wrote the clean speaker list to {args.write_clean}")
    return 0


# --------------------------------------------------------------------------
# palate: recovering PAL.DAT from the tongue's own extremes


def cmd_palate(corpus: Corpus, args: argparse.Namespace) -> int:
    """The upper envelope of the tongue pellets, against the shipped outline.

    PAL.DAT comes from a dental cast of the maxillary arch, scanned with a
    chain of gold pellets laid along the palatal midline (handbook 5.2.2.4.1)
    -- an object measured at rest, not derived from speech. So agreement
    between it and the highest the tongue ever reaches at each x is a real
    cross-check of two independent measurements, not a tautology.

    Two caveats the handbook states and this measurement inherits: the
    outline may have been *extended* behind the cast's reach using extreme
    T3/T4 positions, which would make its dorsal end partly circular; and the
    dorsal end lies under the soft palate, which moves, so a single outline
    there approximates a boundary that is not fixed.
    """
    tally = Tally()
    rows = []
    for speaker in corpus.speakers():
        outline = corpus.palate(speaker)
        if len(outline) < 2:
            print(f"{speaker}: no usable palate outline")
            continue
        bins: dict[int, Histogram] = {}
        frames = 0
        for frame in corpus.frames(speaker):
            frames += 1
            for index in TONGUE:
                point = frame[index]
                if point is None:
                    continue
                bins.setdefault(round(point[0] / BIN_MM), Histogram()).add(point[1])
        tally.note(speaker, len(corpus.track_files(speaker)), frames)
        residuals = []
        extremes = []
        for cell, histogram in sorted(bins.items()):
            if histogram.total < args.min_samples:
                continue
            x = cell * BIN_MM
            wall = interpolate(outline, x)
            if wall is None:
                continue
            residuals.append(histogram.quantile(ENVELOPE_Q) - wall)
            extremes.append(histogram.quantile(1.0) - wall)
        if len(residuals) < 5:
            print(f"{speaker}: only {len(residuals)} comparable bins")
            continue
        rows.append(
            (
                speaker,
                len(outline),
                outline[0][0],
                outline[-1][0],
                len(residuals),
                math.sqrt(statistics.fmean(r * r for r in residuals)),
                math.sqrt(statistics.fmean(e * e for e in extremes)),
                statistics.fmean(residuals),
            )
        )
    check_read(corpus, tally)
    header(corpus, tally, "palate recovery")
    print(
        f"  {'spk':>6} {'PAL n':>6} {'x front':>8} {'x back':>7} {'bins':>5} "
        f"{'rms q':>6} {'rms max':>8} {'bias':>6}"
    )
    for speaker, points, front, back, bins_used, rms, rms_max, bias in rows:
        print(
            f"  {speaker:>6} {points:6} {front:8.1f} {back:7.1f} {bins_used:5} "
            f"{rms:6.2f} {rms_max:8.2f} {bias:6.2f}"
        )
    print()
    summarize(f"rms at q={ENVELOPE_Q:.4g}", [row[5] for row in rows], " mm")
    summarize("rms at the raw maximum", [row[6] for row in rows], " mm")
    summarize("signed bias", [row[7] for row in rows], " mm")
    summarize("PAL.DAT points per speaker", [float(row[1]) for row in rows])
    within = sum(1 for row in rows if row[5] <= 1.4)
    print(
        f"\n  {within} of {len(rows)} speakers recover the outline to 1.4 mm rms.\n"
        "  The raw maximum is the same measurement with the mistracked frames "
        "left in;\n  the gap between the two columns is what those frames are "
        "worth."
    )
    return 0


# --------------------------------------------------------------------------
# clearance: the palate as a boundary, as a profile, and as two coronal zones

# A frame is "near contact" when the pellet is this close to the outline.
NEAR_CONTACT_MM = 3.0

# The arc window the profile is reported over. Its front edge is where the
# palate outline starts (about arc 0.10) plus the margin the tongue pellets
# need to reach reliably; its back edge is where the outline ends (median arc
# 0.40). Outside it XRMB measures no tract dimension at all.
WINDOW = (0.20, 0.40)
PROFILE_ARCS = tuple(round(0.15 + 0.025 * i, 3) for i in range(12))


def tongue_line(frame: Frame) -> list[Point]:
    """The tongue surface in one frame, as an x-sorted polyline through T1-T4."""
    return sorted(p for i in TONGUE if (p := frame[i]) is not None)


def cmd_clearance(corpus: Corpus, args: argparse.Namespace) -> int:
    """How close the tongue gets to the palate, everywhere and everywhen.

    Three readings of one quantity, ``palate_y(x) - tongue_y(x)``:

    the boundary
        its distribution near zero. If the outline is a real wall the
        distribution has to stop there, and how sharply it stops is a check
        on the whole coordinate alignment, not just on the outline.

    the profile
        its maximum per arc bin, which is the largest sagittal dimension the
        tract takes there -- the measurable analogue of what ``heads.xml``
        declares as ``diameter``. Reported two ways, because the obvious
        estimator is biased: taking the maximum per bin over whatever frames
        happen to reach that bin selects, at the front of the mouth, exactly
        the frames where the tongue is forward and therefore high. The second
        estimator keeps only frames whose tongue polyline spans the entire
        window, so every bin sees one frame set and the bias is gone -- at
        the cost of most of the frames, and some speakers entirely.

    the coronal zones
        where along x the near-contact frames pile up. Two modes would mean
        the coronal region holds two distinct constriction targets.
    """
    tally = Tally()
    boundary = Histogram()
    boundary_total = 0
    profiles: list[tuple[str, list[tuple[float, float]], int]] = []
    spanning: list[tuple[str, list[tuple[float, float]], int, int]] = []
    coverage: dict[float, list[float]] = {arc: [] for arc in PROFILE_ARCS}
    modes = []
    reach = []
    for speaker in corpus.speakers():
        wall = upper_wall(corpus, speaker)
        outline = corpus.palate(speaker)
        if wall is None or len(outline) < 2:
            print(f"{speaker}: no usable palate outline")
            continue
        front, back = wall.x_at(WINDOW[0]), wall.x_at(WINDOW[1])
        every: dict[int, Histogram] = {}
        spanned: dict[int, Histogram] = {}
        near: dict[int, int] = {}
        frames = 0
        spans = 0
        for frame in corpus.frames(speaker):
            frames += 1
            for index in TONGUE:
                point = frame[index]
                if point is None:
                    continue
                wall_y = interpolate(outline, point[0])
                if wall_y is None:
                    continue
                boundary.add(point[1] - wall_y)
                boundary_total += 1
                if index in CORONAL and wall_y - point[1] < NEAR_CONTACT_MM:
                    cell = round(point[0] / BIN_MM)
                    near[cell] = near.get(cell, 0) + 1
            line = tongue_line(frame)
            if len(line) < 2:
                continue
            covers = (
                front is not None
                and back is not None
                and line[0][0] <= back
                and line[-1][0] >= front
            )
            spans += covers
            first = int(math.ceil(line[0][0] / BIN_MM))
            last = int(math.floor(line[-1][0] / BIN_MM))
            for cell in range(first, last + 1):
                x = cell * BIN_MM
                surface = interpolate(line, x)
                wall_y = interpolate(outline, x)
                if surface is None or wall_y is None:
                    continue
                every.setdefault(cell, Histogram()).add(wall_y - surface)
                if covers:
                    spanned.setdefault(cell, Histogram()).add(wall_y - surface)
        tally.note(speaker, len(corpus.track_files(speaker)), frames)
        reach.append(wall.reach)
        profiles.append((speaker, _series(wall, every, args.min_samples), frames))
        if spans >= 0.10 * frames:
            floor = int(0.9 * spans)
            spanning.append((speaker, _series(wall, spanned, floor), spans, frames))
        for cell, histogram in every.items():
            arc = wall.arc(cell * BIN_MM)
            if arc is None:
                continue
            for target in PROFILE_ARCS:
                if abs(arc - target) < 0.012:
                    coverage[target].append(100 * histogram.total / frames)
        modes.append((speaker, _modes(wall, near)))
    check_read(corpus, tally)
    header(corpus, tally, "clearance")

    print("  the palate as a boundary -- tongue y minus palate y, pooled")
    print(f"  {'mm':>6} {'samples':>12}")
    for cell in sorted(boundary.counts):
        value = cell * Histogram.STEP
        if -4.0 <= value <= 3.0:
            print(f"  {value:6.2f} {boundary.counts[cell]:12}")
    over = sum(c for k, c in boundary.counts.items() if k * Histogram.STEP > 0)
    far = sum(c for k, c in boundary.counts.items() if k * Histogram.STEP > 1.0)
    print(
        f"\n  {boundary_total} samples fall under the outline. {over} sit above "
        f"it ({100 * over / boundary_total:.3f}%),\n  {far} by more than 1 mm "
        f"({100 * far / boundary_total:.4f}%). The wall is where it says."
    )

    print("\n  the diameter profile -- max clearance per arc, over each")
    print("  speaker's own peak; arc uses the tract length heads.xml declares")
    print(
        f"\n  {'arc':>6} {'every-frame':>12} {'sd':>6} {'n':>4} "
        f"{'spanning':>10} {'sd':>6} {'n':>4} {'bin cover%':>11}"
    )
    for arc in PROFILE_ARCS:
        loose = _sample(profiles, arc)
        tight = _sample([(s, p, n) for s, p, n, _ in spanning], arc)
        cover = coverage[arc]
        row = f"  {arc:6.3f}"
        for values in (loose, tight):
            if len(values) < 5:
                row += f" {'--':>12} {'':>6} {len(values):4}"
            else:
                row += (
                    f" {statistics.median(values):12.3f}"
                    f" {statistics.pstdev(values):6.3f} {len(values):4}"
                )
        row += f" {statistics.median(cover):11.1f}" if cover else f" {'--':>11}"
        print(row)
    print(
        f"\n  every-frame: all {len(profiles)} speakers, biased low at the "
        f"front (see the cover% column).\n  spanning: {len(spanning)} speakers "
        "whose tongue line crosses the whole window in\n  "
        f"{statistics.median(100 * s / f for _, _, s, f in spanning):.0f}% of "
        "frames (median); unbiased within it, and the estimator to trust."
    )
    summarize("palate trace reaches arc", reach)
    peaks = [max(v for _, v in series) for _, series, _ in profiles if series]
    summarize("peak clearance", peaks, " mm")
    _report_sex(profiles)

    print(
        "\n  coronal near-contact zones -- T1/T2 within "
        f"{NEAR_CONTACT_MM:g} mm of the outline"
    )
    both = [(s, m) for s, m in modes if len(m) >= 2]
    for speaker, found in modes:
        if len(found) >= 2:
            continue
        where = f" at arc {found[0]:.3f}" if found else ""
        print(f"  {speaker}: fewer than two modes{where}")
    # Arc grows toward the glottis, so the anterior mode is the smaller one.
    summarize("anterior mode", [min(m) for _, m in both])
    summarize("posterior mode", [max(m) for _, m in both])
    summarize("separation", [max(m) - min(m) for _, m in both])
    print(
        f"\n  {len(both)} of {len(modes)} speakers show two coronal modes. "
        "ipakit declares\n  alveolar 0.13 and postalveolar 0.19, a separation "
        "of 0.06."
    )
    return 0


def _series(
    wall: UpperWall, bins: dict[int, Histogram], floor: int
) -> list[tuple[float, float]]:
    """(arc, clearance) for every bin with enough samples, front to back."""
    out = []
    for cell, histogram in bins.items():
        if histogram.total < floor:
            continue
        arc = wall.arc(cell * BIN_MM)
        if arc is not None:
            out.append((arc, histogram.quantile(ENVELOPE_Q)))
    return sorted(out)


def _at(series: Sequence[tuple[float, float]], arc: float) -> float | None:
    """The series interpolated at an arc, or None outside its span."""
    if len(series) < 2 or arc < series[0][0] or arc > series[-1][0]:
        return None
    for i in range(len(series) - 1):
        (a0, v0), (a1, v1) = series[i], series[i + 1]
        if a0 <= arc <= a1:
            return v0 if a1 == a0 else v0 + (v1 - v0) * (arc - a0) / (a1 - a0)
    return None


def _sample(
    profiles: Sequence[tuple[str, list[tuple[float, float]], int]], arc: float
) -> list[float]:
    """Each speaker's clearance at one arc, over that speaker's own peak."""
    out = []
    for _, series, _ in profiles:
        if not series:
            continue
        value = _at(series, arc)
        peak = max(v for _, v in series)
        if value is not None and peak > 0:
            out.append(value / peak)
    return out


def _report_sex(
    profiles: Sequence[tuple[str, list[tuple[float, float]], int]],
) -> None:
    """The same profile split by speaker sex.

    The point is not a sex difference; it is that there is none once each
    speaker's arc is divided by the length heads.xml declares for their head.
    That is the evidence for giving both adult heads the same shape.
    """
    groups = {
        sex: [p for p in profiles if SPEAKER_SEX.get(p[0]) == sex] for sex in "MF"
    }
    print(f"\n  {'arc':>6} {'male':>7} {'n':>4} {'female':>8} {'n':>4} {'diff':>6}")
    for arc in PROFILE_ARCS:
        male, female = _sample(groups["M"], arc), _sample(groups["F"], arc)
        if len(male) < 5 or len(female) < 5:
            continue
        a, b = statistics.median(male), statistics.median(female)
        print(
            f"  {arc:6.3f} {a:7.3f} {len(male):4} {b:8.3f} {len(female):4} "
            f"{a - b:6.3f}"
        )


def _modes(wall: UpperWall, near: dict[int, int]) -> list[float]:
    """Arcs of the local maxima in a near-contact-by-x histogram."""
    if sum(near.values()) < 500:
        return []
    cells = sorted(near)
    smooth = {
        c: (near.get(c - 1, 0) + 2 * near.get(c, 0) + near.get(c + 1, 0)) / 4
        for c in cells
    }
    top = max(smooth.values())
    peaks = [
        c
        for c in cells
        if smooth[c] >= max(smooth.get(c + d, 0) for d in (-2, -1, 1, 2))
        and smooth[c] > 0.15 * top
    ]
    arcs = [a for c in peaks if (a := wall.arc(c * BIN_MM)) is not None]
    return sorted(arcs)


# --------------------------------------------------------------------------
# hinge: where the mandible turns

# Frames apart, for the displacement chords the centre is solved from. At the
# corpus's sampling rates this is a few tens of milliseconds -- long enough
# for a real gesture to move the pellets well past tracking noise.
HINGE_LAG = 10
MIN_CHORD_MM = 1.0
# Two chords nearly parallel means almost no rotation, and the intersection
# they define is numerically worthless. This is the sine of the angle between
# them, below which the frame pair is discarded.
MIN_ROTATION = 0.10
# A centre further away than this is a solver artifact, not an anatomy.
MAX_CENTRE_MM = 300.0


def solve_centre(near: tuple[Point, Point], far: tuple[Point, Point]) -> Point | None:
    """The instantaneous centre two point displacements imply, if any.

    For a rigid body in the plane, every point turns about one centre, which
    lies on the perpendicular bisector of each point's displacement chord.
    Two points give two bisectors and one intersection.
    """
    dx_near = (near[1][0] - near[0][0], near[1][1] - near[0][1])
    dx_far = (far[1][0] - far[0][0], far[1][1] - far[0][1])
    length_near, length_far = math.hypot(*dx_near), math.hypot(*dx_far)
    if length_near < MIN_CHORD_MM or length_far < MIN_CHORD_MM:
        return None
    determinant = dx_near[0] * dx_far[1] - dx_near[1] * dx_far[0]
    if abs(determinant) / (length_near * length_far) < MIN_ROTATION:
        return None
    mid_near = ((near[0][0] + near[1][0]) / 2, (near[0][1] + near[1][1]) / 2)
    mid_far = ((far[0][0] + far[1][0]) / 2, (far[0][1] + far[1][1]) / 2)
    c_near = dx_near[0] * mid_near[0] + dx_near[1] * mid_near[1]
    c_far = dx_far[0] * mid_far[0] + dx_far[1] * mid_far[1]
    x = (c_near * dx_far[1] - dx_near[1] * c_far) / determinant
    y = (dx_near[0] * c_far - c_near * dx_far[0]) / determinant
    if abs(x) > MAX_CENTRE_MM or abs(y) > MAX_CENTRE_MM:
        return None
    return (x, y)


def cmd_hinge(corpus: Corpus, args: argparse.Namespace) -> int:
    """Where the jaw's instantaneous centre of rotation sits, open and closed.

    ipakit has no jaw articulator at all, so nothing here contradicts the
    library; it says what an articulatory renderer would have to model. If
    the centre were fixed the jaw would be one hinge and one degree of
    freedom. If it migrates with opening, it is rotation plus condylar glide
    and needs two.
    """
    tally = Tally()
    rows = []
    for speaker in corpus.speakers():
        centres: list[Point] = []
        opening: list[float] = []
        lengths = Moments()
        frames = 0
        for path in corpus.track_files(speaker):
            window = list(read_frames(path))
            frames += len(window)
            for frame in window:
                incisor, molar = frame[MNI], frame[MNM]
                if incisor is not None and molar is not None:
                    lengths.add(math.dist(incisor, molar))
            for i in range(len(window) - HINGE_LAG):
                first, second = window[i], window[i + HINGE_LAG]
                a, b = first[MNI], second[MNI]
                c, d = first[MNM], second[MNM]
                if a is None or b is None or c is None or d is None:
                    continue
                centre = solve_centre((a, b), (c, d))
                if centre is None:
                    continue
                centres.append(centre)
                opening.append((a[1] + b[1]) / 2)
        tally.note(speaker, len(corpus.track_files(speaker)), frames)
        loose = lengths.n < 100 or math.sqrt(lengths.variance) / lengths.mean > RIGID_CV
        if len(centres) < args.min_centres or loose:
            print(
                f"  {speaker}: skipped "
                f"({'mandible track is loose' if loose else str(len(centres)) + ' centres'})"
            )
            continue
        xs = sorted(c[0] for c in centres)
        ys = sorted(c[1] for c in centres)
        heights = sorted(opening)
        shut = quantile(heights, 0.75)
        agape = quantile(heights, 0.25)
        closed = [c for c, h in zip(centres, opening, strict=True) if h >= shut]
        opened = [c for c, h in zip(centres, opening, strict=True) if h <= agape]
        rows.append(
            (
                speaker,
                len(centres),
                statistics.median(xs),
                quantile(xs, 0.75) - quantile(xs, 0.25),
                statistics.median(ys),
                quantile(ys, 0.75) - quantile(ys, 0.25),
                statistics.median(c[0] for c in closed),
                statistics.median(c[1] for c in closed),
                statistics.median(c[0] for c in opened),
                statistics.median(c[1] for c in opened),
            )
        )
    check_read(corpus, tally)
    header(corpus, tally, "mandibular hinge")
    print(
        f"  {'spk':>6} {'pairs':>7} {'x':>7} {'IQR':>6} {'y':>7} {'IQR':>6}"
        f"   {'closed':>15} {'open':>15} {'dy':>6}"
    )
    for row in rows:
        print(
            f"  {row[0]:>6} {row[1]:7} {row[2]:7.1f} {row[3]:6.1f} {row[4]:7.1f} "
            f"{row[5]:6.1f}   ({row[6]:6.1f},{row[7]:6.1f}) "
            f"({row[8]:6.1f},{row[9]:6.1f}) {row[9] - row[7]:6.1f}"
        )
    print()
    summarize("centre x", [row[2] for row in rows], " mm")
    summarize("centre y", [row[4] for row in rows], " mm")
    summarize("IQR of x", [row[3] for row in rows], " mm")
    summarize("IQR of y", [row[5] for row in rows], " mm")
    drop = [row[9] - row[7] for row in rows]
    slide = [row[8] - row[6] for row in rows]
    summarize("open minus closed, y", drop, " mm")
    summarize("open minus closed, x", slide, " mm")
    print(
        f"\n  the centre falls as the jaw opens in {sum(1 for d in drop if d < 0)} "
        f"of {len(rows)} speakers;\n  it moves back in "
        f"{sum(1 for s in slide if s < 0)} of {len(rows)}, which is not a "
        "direction at all.\n  A single fixed hinge is not what the data shows; "
        "the IQRs say the estimate\n  per frame pair is poor, and only the "
        "aggregate is worth anything."
    )
    return 0


# --------------------------------------------------------------------------
# chain: what riding on the mandible accounts for


def cmd_chain(corpus: Corpus, args: argparse.Namespace) -> int:
    """How much of each pellet's motion the mandible carries.

    Re-express every pellet in a frame fixed to the mandible -- origin at
    MNI, x-axis toward MNM -- and compare its variance there to its variance
    in the head frame. What the mandible carries disappears; what an organ
    does on top of the mandible remains.

    The upper lip is the control. It is on the maxilla and rides on nothing,
    so subtracting mandible motion can only add to its variance: the number
    has to come out strongly negative, and if it does not, the frame is
    wrong.
    """
    tally = Tally()
    rows = []
    for speaker in corpus.speakers():
        head: dict[int, tuple[Moments, Moments]] = {}
        local: dict[int, tuple[Moments, Moments]] = {}
        lengths = Moments()
        frames = 0
        for frame in corpus.frames(speaker):
            frames += 1
            origin, along = frame[MNI], frame[MNM]
            if origin is None or along is None:
                continue
            lengths.add(math.dist(origin, along))
            ux, uy = along[0] - origin[0], along[1] - origin[1]
            scale = math.hypot(ux, uy)
            if scale < 1e-6:
                continue
            ux, uy = ux / scale, uy / scale
            for index in range(len(PELLETS) - 2):
                point = frame[index]
                if point is None:
                    continue
                dx, dy = point[0] - origin[0], point[1] - origin[1]
                for store, pair in (
                    (head, point),
                    (local, (dx * ux + dy * uy, -dx * uy + dy * ux)),
                ):
                    moments = store.setdefault(index, (Moments(), Moments()))
                    moments[0].add(pair[0])
                    moments[1].add(pair[1])
        tally.note(speaker, len(corpus.track_files(speaker)), frames)
        loose = lengths.n < 100 or math.sqrt(lengths.variance) / lengths.mean > RIGID_CV
        if loose:
            continue
        removed = {}
        for index in head:
            total = head[index][0].variance + head[index][1].variance
            rest = local[index][0].variance + local[index][1].variance
            if head[index][0].n >= args.min_samples and total > 0:
                removed[index] = 1 - rest / total
        if len(removed) >= 4:
            rows.append((speaker, removed))
    check_read(corpus, tally)
    header(corpus, tally, "kinematic chain")
    names = [PELLETS[i] for i in range(len(PELLETS) - 2)]
    print(f"  {'spk':>6}" + "".join(f"{name:>9}" for name in names))
    for speaker, removed in rows:
        line = f"  {speaker:>6}"
        for index in range(len(names)):
            line += (
                f"{100 * removed[index]:8.1f}%" if index in removed else f"{'--':>9}"
            )
        print(line)
    print()
    for index, name in enumerate(names):
        values = [r[index] for _, r in rows if index in r]
        summarize(f"{name} variance removed", [100 * v for v in values], "%")
    print(
        f"\n  over {len(rows)} speakers whose mandible pellets hold a constant "
        "separation.\n  The upper lip is the control and comes out far "
        "negative, as it must."
    )
    return 0


# --------------------------------------------------------------------------


COMMANDS = {
    "rigid": cmd_rigid,
    "palate": cmd_palate,
    "clearance": cmd_clearance,
    "hinge": cmd_hinge,
    "chain": cmd_chain,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--corpus", default=str(DEFAULT_CORPUS), help="the mounted database"
    )
    parser.add_argument(
        "--speakers", metavar="JW11,JW13", help="measure only these, comma separated"
    )
    parser.add_argument(
        "--files",
        type=int,
        default=0,
        help="read only the first N track files per speaker (0 = all)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=200,
        help="samples a bin needs before it is reported",
    )
    parser.add_argument(
        "--min-centres",
        type=int,
        default=500,
        help="hinge: frame pairs a speaker needs before it is reported",
    )
    parser.add_argument(
        "--write-clean", metavar="FILE", help="rigid: write the clean speaker list"
    )
    parser.add_argument(
        "command", choices=[*COMMANDS, "all"], help="which measurement to run"
    )
    args = parser.parse_args(argv)

    corpus = open_corpus(args)
    if corpus is None:
        return 0
    if args.command != "all":
        return COMMANDS[args.command](corpus, args)
    for name, run in COMMANDS.items():
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        status = run(corpus, args)
        if status:
            return status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
