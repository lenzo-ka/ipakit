#!/usr/bin/env python3
"""Measure articulatory target anchoring in the X-Ray Microbeam corpus.

The corpus is licensed external data and is never bundled. Set
``IPAKIT_XRMB_DIR`` or pass ``--corpus``; absence prints an explanation and
exits successfully. The pipeline is deliberately ordered: a waveform/pellet
clock sanity gate must pass before forced alignment or target statistics run.

Prompts are the two citation-word and sentence tasks transcribed in
``tests/fixtures/xrmb_anchor_prompts.json`` from Westbury et al. (1994),
Appendix A. Oral-motor tasks are not used.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import statistics
import tempfile
import wave
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from articulatory import (
    CORPUS_ENV,
    EXPECTED_SPEAKERS,
    MICRONS_PER_MM,
    MISSING,
    PELLETS,
    Point,
    read_outline,
)
from ipakit.align import align

ROOT = Path(__file__).parents[1]
PROMPTS = ROOT / "tests/fixtures/xrmb_anchor_prompts.json"
DEFAULT_REPORT = ROOT / "docs/anchor-study.md"
TASKS = ("002", "007")
SYNC_SPEAKERS = 5
SYNC_TOLERANCE_S = 0.050
SYNC_MIN_TOKENS = 6
WINDOW_PAD_S = 0.060

# PocketSphinx's English model is the closed inventory producing these IPA
# symbols. Classes are articulatory event classes, split by manner where the
# same kinematic observable supports it.
CLASSES = {
    "p": "bilabial-stop",
    "b": "bilabial-stop",
    "m": "bilabial-nasal",
    "t": "alveolar-stop",
    "d": "alveolar-stop",
    "n": "alveolar-nasal",
    "s": "alveolar-fricative",
    "z": "alveolar-fricative",
}
VOWELS = frozenset("aeiouɑæɔəɚɛɜɪʊʌ")

TimedFrame = tuple[float, tuple[Point | None, ...]]


@dataclass(frozen=True)
class Token:
    speaker: str
    task: str
    symbol: str
    class_name: str
    onset: float
    duration: float
    event: float

    @property
    def fraction(self) -> float:
        return (self.event - self.onset) / self.duration


def read_timed_frames(path: Path) -> list[TimedFrame]:
    """Read timestamps and pellets using articulatory.py's exact discipline."""
    rows = []
    with path.open(encoding="latin-1") as handle:
        for line in handle:
            fields = line.split("\t")
            if len(fields) < 1 + 2 * len(PELLETS):
                continue
            try:
                raw = [int(field) for field in fields[: 1 + 2 * len(PELLETS)]]
            except ValueError:
                continue
            points = []
            for index in range(len(PELLETS)):
                x_raw, y_raw = raw[1 + 2 * index : 3 + 2 * index]
                points.append(
                    None
                    if abs(x_raw) >= MISSING or abs(y_raw) >= MISSING
                    else (x_raw / MICRONS_PER_MM, y_raw / MICRONS_PER_MM)
                )
            rows.append((raw[0] / 1_000_000.0, tuple(points)))
    if len(rows) < 100:
        raise ValueError(f"{path}: read only {len(rows)} usable rows")
    if any(a[0] >= b[0] for a, b in zip(rows, rows[1:], strict=False)):
        raise ValueError(f"{path}: timestamps are not strictly increasing")
    return rows


def _resample_for_alignment(source: Path, destination: Path) -> None:
    """Linear PCM resampling to the acoustic model's required 16 kHz."""
    with wave.open(str(source), "rb") as reader:
        if (
            reader.getnchannels() != 1
            or reader.getsampwidth() != 2
            or reader.getcomptype() != "NONE"
        ):
            raise ValueError(f"{source}: expected mono 16-bit PCM WAV")
        source_rate = reader.getframerate()
        samples = array.array("h", reader.readframes(reader.getnframes()))
    if source_rate == 16_000:
        result = samples
    else:
        count = round(len(samples) * 16_000 / source_rate)
        result = array.array("h")
        for out_index in range(count):
            position = out_index * source_rate / 16_000
            left = min(int(position), len(samples) - 1)
            right = min(left + 1, len(samples) - 1)
            weight = position - left
            result.append(round(samples[left] * (1 - weight) + samples[right] * weight))
    with wave.open(str(destination), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(result.tobytes())


def align_task(wav_path: Path, prompt: str):
    with tempfile.TemporaryDirectory(prefix="ipakit-anchor-") as directory:
        converted = Path(directory) / "alignment.wav"
        _resample_for_alignment(wav_path, converted)
        return align(converted, prompt)


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("quantile of empty sequence")
    ordered = sorted(values)
    at = q * (len(ordered) - 1)
    lower = int(at)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (at - lower)


def _clean(samples: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Discard the outer 0.1% of a local kinematic observable."""
    if len(samples) < 8:
        return []
    values = [value for _, value in samples]
    low, high = _quantile(values, 0.001), _quantile(values, 0.999)
    return [(time, value) for time, value in samples if low <= value <= high]


def _interpolate_outline(outline: Sequence[Point], x: float) -> float | None:
    for left, right in zip(outline, outline[1:], strict=False):
        if left[0] <= x <= right[0]:
            if right[0] == left[0]:
                return (left[1] + right[1]) / 2
            weight = (x - left[0]) / (right[0] - left[0])
            return left[1] + weight * (right[1] - left[1])
    return None


def _observable(
    frames: Sequence[TimedFrame], class_name: str, outline: Sequence[Point]
) -> list[tuple[float, float]]:
    values = []
    for time, frame in frames:
        if class_name.startswith("bilabial"):
            upper, lower = frame[0], frame[1]
            if upper is not None and lower is not None:
                values.append((time, math.dist(upper, lower)))
        elif class_name.startswith("alveolar"):
            tip = frame[2]
            if tip is not None:
                palate_y = _interpolate_outline(outline, tip[0])
                if palate_y is not None:
                    values.append((time, palate_y - tip[1]))
    return _clean(values)


def _window(frames: Sequence[TimedFrame], start: float, end: float) -> list[TimedFrame]:
    return [row for row in frames if start <= row[0] <= end]


def event_time(
    frames: Sequence[TimedFrame],
    outline: Sequence[Point],
    class_name: str,
    onset: float,
    duration: float,
) -> float | None:
    held = _window(frames, onset - WINDOW_PAD_S, onset + duration + WINDOW_PAD_S)
    if class_name == "vowel":
        positions = []
        for time, frame in held:
            points = [frame[index] for index in (4, 5) if frame[index] is not None]
            if points:
                positions.append(
                    (
                        time,
                        sum(p[0] for p in points) / len(points),
                        sum(p[1] for p in points) / len(points),
                    )
                )
        speeds = []
        for before, after in zip(positions, positions[1:], strict=False):
            dt = after[0] - before[0]
            if dt > 0:
                speeds.append(
                    (
                        after[0],
                        math.hypot(after[1] - before[1], after[2] - before[2]) / dt,
                    )
                )
        clean = _clean(speeds)
        return min(clean, key=lambda item: item[1])[0] if clean else None
    observable = _observable(held, class_name, outline)
    return min(observable, key=lambda item: item[1])[0] if observable else None


def _classify(symbol: str) -> str | None:
    if symbol in CLASSES:
        return CLASSES[symbol]
    return "vowel" if any(character in VOWELS for character in symbol) else None


def _wave_samples(path: Path) -> tuple[int, array.array[int]]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path}: expected mono 16-bit PCM WAV")
        return source.getframerate(), array.array(
            "h", source.readframes(source.getnframes())
        )


def _burst_time(path: Path, onset: float, duration: float) -> float | None:
    rate, samples = _wave_samples(path)
    begin = max(1, round((onset + 0.45 * duration) * rate))
    end = min(len(samples), round((onset + duration + 0.080) * rate))
    width = max(1, round(0.004 * rate))
    if end - begin < width:
        return None
    best = max(
        range(begin, end - width),
        key=lambda index: sum(
            abs(samples[i] - samples[i - 1]) for i in range(index, index + width)
        ),
    )
    return (best + width / 2) / rate


def _release_time(observable: Sequence[tuple[float, float]]) -> float | None:
    if len(observable) < 4:
        return None
    minimum = min(range(len(observable)), key=lambda index: observable[index][1])
    derivatives = []
    for before, after in zip(
        observable[minimum:], observable[minimum + 1 :], strict=False
    ):
        dt = after[0] - before[0]
        if dt > 0:
            derivatives.append((after[0], (after[1] - before[1]) / dt))
    clean = _clean(derivatives)
    return max(clean, key=lambda item: item[1])[0] if clean else None


def sync_gate(
    root: Path, prompts: dict[str, str]
) -> tuple[bool, list[float], list[str]]:
    errors = []
    differences = []
    speakers = sorted(path for path in root.glob("JW*") if path.is_dir())[
        :SYNC_SPEAKERS
    ]
    for speaker_path in speakers:
        task = "007"
        wav_path = speaker_path / f"tp{task}.wav"
        track_path = speaker_path / f"tp{task}.txy"
        try:
            form = align_task(wav_path, prompts[task])
            frames = read_timed_frames(track_path)
            outline = read_outline(speaker_path / "PAL.DAT")
        except (OSError, ValueError) as exc:
            errors.append(f"{speaker_path.name}/tp{task}: {exc}")
            continue
        for unit in form.units:
            timing = unit.timing
            symbol = unit.text
            class_name = CLASSES.get(symbol)
            if timing is None or class_name not in {"bilabial-stop", "alveolar-stop"}:
                continue
            burst = _burst_time(wav_path, timing.start, timing.duration)
            held = _window(
                frames, timing.start - 0.04, timing.start + timing.duration + 0.10
            )
            release = _release_time(_observable(held, class_name, outline))
            if burst is not None and release is not None:
                differences.append(release - burst)
    if len(differences) < SYNC_MIN_TOKENS:
        errors.append(
            f"sync gate found {len(differences)} usable stop releases; need {SYNC_MIN_TOKENS}"
        )
        return False, differences, errors
    absolute_errors = [abs(value) for value in differences]
    upper_quartile_error = _quantile(absolute_errors, 0.75)
    if upper_quartile_error > SYNC_TOLERANCE_S:
        errors.append(
            "75th-percentile absolute audio-pellet release difference "
            f"{upper_quartile_error:.3f}s exceeds {SYNC_TOLERANCE_S:.3f}s"
        )
        return False, differences, errors
    return True, differences, errors


def collect(root: Path, prompts: dict[str, str]) -> tuple[list[Token], list[str]]:
    tokens = []
    refusals = []
    speakers = sorted(path for path in root.glob("JW*") if path.is_dir())
    if len(speakers) != EXPECTED_SPEAKERS:
        raise SystemExit(
            f"{root} holds {len(speakers)} speakers; expected {EXPECTED_SPEAKERS}"
        )
    for speaker_path in speakers:
        outline = read_outline(speaker_path / "PAL.DAT")
        if len(outline) < 2:
            raise SystemExit(f"{speaker_path}/PAL.DAT: read only {len(outline)} points")
        for task in TASKS:
            wav_path = speaker_path / f"tp{task}.wav"
            track_path = speaker_path / f"tp{task}.txy"
            if not wav_path.is_file() or not track_path.is_file():
                refusals.append(f"{speaker_path.name}/tp{task}: missing wav or track")
                continue
            try:
                form = align_task(wav_path, prompts[task])
                frames = read_timed_frames(track_path)
            except (OSError, ValueError) as exc:
                refusals.append(f"{speaker_path.name}/tp{task}: {exc}")
                continue
            for unit in form.units:
                timing = unit.timing
                symbol = unit.text
                class_name = _classify(symbol)
                if timing is None or class_name is None or timing.duration <= 0:
                    continue
                event = event_time(
                    frames, outline, class_name, timing.start, timing.duration
                )
                if event is not None:
                    tokens.append(
                        Token(
                            speaker_path.name,
                            task,
                            symbol,
                            class_name,
                            timing.start,
                            timing.duration,
                            event,
                        )
                    )
    return tokens, refusals


def _summary(tokens: Sequence[Token]) -> tuple[float, float, float, float]:
    values = [token.fraction for token in tokens]
    return (
        statistics.median(values),
        _quantile(values, 0.25),
        _quantile(values, 0.75),
        sum(value < 0 for value in values) / len(values),
    )


def _table(groups: Iterable[tuple[str, Sequence[Token]]]) -> list[str]:
    lines = [
        "| group | n | median | Q1 | Q3 | before onset |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, tokens in groups:
        if not tokens:
            continue
        median, q1, q3, before = _summary(tokens)
        lines.append(
            f"| {name} | {len(tokens)} | {median:.3f} | {q1:.3f} | {q3:.3f} | {before:.1%} |"
        )
    return lines


def render_report(
    path: Path,
    tokens: Sequence[Token],
    refusals: Sequence[str],
    differences: Sequence[float],
) -> None:
    by_class: dict[str, list[Token]] = defaultdict(list)
    for token in tokens:
        by_class[token.class_name].append(token)
    recommendations = {}
    for name, held in by_class.items():
        median = _summary(held)[0]
        recommendations[name] = (
            "onset" if abs(median) <= abs(median - 0.5) else "center"
        )
    lines = [
        "# XRMB anchor study",
        "",
        "**Verdict: the audio-pellet sync gate passed. The table below is the generated result; its per-class recommendations are evidence for the timed sampler and do not estimate a universal phonological alignment rule.**",
        "",
        "## Sync gate",
        "",
        f"{len(differences)} clear stop releases across the first {SYNC_SPEAKERS} speakers; median absolute waveform-burst to pellet-release difference **{statistics.median(abs(value) for value in differences):.3f} s** and 75th percentile **{_quantile([abs(value) for value in differences], 0.75):.3f} s** (gate: 75th percentile <= {SYNC_TOLERANCE_S:.3f} s).",
        "",
        "## Headline distributions",
        "",
    ]
    for name, held in sorted(by_class.items()):
        median, q1, q3, before = _summary(held)
        lines.append(
            f"- **{name}:** median {median:.3f} of the acoustic segment (IQR {q1:.3f}-{q3:.3f}); {before:.1%} of targets precede acoustic onset."
        )
    lines += ["", *_table(sorted(by_class.items())), "", "## By speaker", ""]
    speaker_groups = defaultdict(list)
    for token in tokens:
        speaker_groups[(token.speaker, token.class_name)].append(token)
    lines += _table(
        (f"{speaker} / {class_name}", held)
        for (speaker, class_name), held in sorted(speaker_groups.items())
    )
    lines += ["", "## By segment duration", ""]
    duration_groups = []
    for name, held in sorted(by_class.items()):
        cut = statistics.median(token.duration for token in held)
        duration_groups.append(
            (
                f"{name} / short (< {cut:.3f} s)",
                [token for token in held if token.duration < cut],
            )
        )
        duration_groups.append(
            (
                f"{name} / long (>= {cut:.3f} s)",
                [token for token in held if token.duration >= cut],
            )
        )
    lines += _table(duration_groups)
    lines += ["", "## Recommended defaults", ""]
    for name, anchor in sorted(recommendations.items()):
        lines.append(f"- `{name}`: **`{anchor}`**")
    unique = set(recommendations.values())
    verdict = "one global anchor" if len(unique) == 1 else "per-class anchors"
    lines += [
        "",
        f"The observed medians support **{verdict}** among the tested `center`/`onset` choices. These binary recommendations select whichever candidate is closer to the measured median; the distributions, not that discretization, are the primary result.",
        "",
        "## Alignment refusals",
        "",
        f"Aligned task files: **{len(set((token.speaker, token.task) for token in tokens))}**. Refused or missing task files: **{len(refusals)}**. Refusals are listed rather than silently dropped.",
        "",
    ]
    lines.extend(f"- `{message}`" for message in refusals)
    lines += [
        "" if refusals else "- None.",
        "## Scope and provenance",
        "",
        "Targets use kinematics alone inside a 60 ms padded acoustic window: UL-LL distance minima for bilabials, T1-to-`PAL.DAT` clearance minima for alveolars, and T3/T4 speed minima for vowels. Local outer 0.1% observable samples are discarded under the same quantile rationale as `scripts/articulatory.py`; missing sentinels are never interpolated. Anchor fraction is exactly `(t_event - t_onset) / duration`.",
        "",
        "This grounds target timing for the measured XRMB English reading tasks and these pellet observables. It does not ground unmeasured places, other languages, spontaneous speech, causal accounts of anticipation, or the acoustic aligner's phone boundaries.",
        "",
        "Prompts are task 2 (citation words) and task 7 (sentences), transcribed in `tests/fixtures/xrmb_anchor_prompts.json` from Westbury, Turner & Dembowski (1994), *X-Ray Microbeam Speech Production Database User's Handbook*, Appendix A, pp. 84-85. Handbook PDF: <https://www.ling.uni-potsdam.de/~gafos/fhs_atelier/ubdbman.pdf> (accessed 2026-08-10). Oral-motor tasks were excluded.",
        "",
        "The corpus is licensed external data, was read in place, and no corpus content is included here.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--corpus",
        default=os.environ.get(CORPUS_ENV),
        help=f"mounted XRMB database (default: ${CORPUS_ENV})",
    )
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT, help="generated Markdown report"
    )
    parser.add_argument(
        "command", nargs="?", choices=("sync", "study"), default="study"
    )
    args = parser.parse_args(argv)
    if not args.corpus or not Path(args.corpus).is_dir():
        location = f" at {args.corpus}" if args.corpus else ""
        print(f"XRMB corpus not found{location}; set ${CORPUS_ENV} or pass --corpus")
        print("external licensed data is not bundled; nothing to do")
        return 0
    payload = json.loads(PROMPTS.read_text())
    prompts = {task: row["prompt"] for task, row in payload["tasks"].items()}
    root = Path(args.corpus)
    passed, differences, errors = sync_gate(root, prompts)
    print(f"sync: {'PASS' if passed else 'FAIL'} ({len(differences)} stop releases)")
    for error in errors:
        print(f"  {error}")
    if not passed:
        print("STOP: no alignment statistics were computed")
        return 1
    if args.command == "sync":
        return 0
    tokens, refusals = collect(root, prompts)
    if not tokens:
        raise SystemExit("alignment produced no measurable tokens")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    render_report(args.report, tokens, refusals, differences)
    counts = Counter(token.class_name for token in tokens)
    print(
        "tokens: "
        + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    )
    print(f"refusals: {len(refusals)}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
