#!/usr/bin/env python3
"""Capture the whole unit corpus, and diff two captures, so lanes compare.

Six review rounds each rebuilt the same measurement by hand: enumerate the
units the inventory can spell, project each one, then diff before against
after and explain every mover. Because each lane wrote its own enumeration,
the corpus drifted -- two lanes a day apart reported 7921 and 8338 units and
neither could tell whether the other had a different inventory or a different
definition. This script is that enumeration, written once.

The corpus
----------

    every phone, and every phone + one diacritic, that spells itself back:

        unit in {base} | {base + mark}   for base in phones, mark in diacritics
        kept when      ipa.segment(unit).to_ipa() == unit

``sweep.py corpus`` prints the totals for the commit you are on.

Why this definition and not a strict-parse one. The alternative in use was
"parses strictly", i.e. ``segment(unit, strict=True)`` does not raise. That
count moved 8618 -> 8340 when ``fix: bind a stress mark to the unit that
follows it`` changed what the parser refuses, without a single phone or
diacritic changing. It measures the parser's error policy as much as the
inventory. Re-emission held at 7921 across the same commits. A corpus meant
to make two lanes comparable should depend on what the data spells, not on
how strict today's parser is.

Bare phones are in the corpus because they are the same predicate with the
empty mark, and because keeping them makes the sweep cover the registered
inventory as well as the composed units -- which is where the described
defects actually lived, on both sides.

The corpus is not pinned to a number here. It has legitimately moved three
times in this repo's history (7426 -> 7882 -> 7921 marked units, as the phone
count went 135 -> 140 -> 139), so a hardcoded total would be edited more
often than it would catch anything. What is asserted is that the sweep cannot
go vacuous or silently collapse: a floor, every phone contributing its bare
unit, every phone contributing at least one marked unit, and most marks
contributing something. The exact totals go into the capture, and ``diff``
reports a change in them as its first line.

Using it
--------

    git switch main
    python scripts/sweep.py capture -o /tmp/before.json
    git switch my-branch
    python scripts/sweep.py capture -o /tmp/after.json
    python scripts/sweep.py diff /tmp/before.json /tmp/after.json

``diff`` classifies every mover -- appeared, disappeared, gained a word, lost
a word, altered a word, features moved, distance-from-base moved -- and
checks the predicate two separate lanes wanted: no pre-existing word is lost
or altered, only added. ``--require-monotone`` makes that predicate gate the
exit status.

    python scripts/sweep.py corpus     # the definition, the counts, the escapes

Measurements are taken under ``PYTHONHASHSEED=0``; the script re-execs itself
to get there rather than trusting the caller to remember.

See docs/reviewing.md for why the sweep is the shape the review takes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit  # noqa: E402
from ipakit import IPAFeatures  # noqa: E402

FORMAT = 1

# The distance is a float sum; cross-version rounding differs in the last bit.
# A real change moves it by orders of magnitude more than this.
TOLERANCE = 1e-9

# Floors, not pins -- see the module docstring. They exist so a sweep that has
# silently stopped composing anything fails loudly instead of reporting a
# clean diff over nothing.
MIN_CORPUS = 4000
MIN_MARKS_USED = 40


def _ensure_hash_seed() -> None:
    """Measure under PYTHONHASHSEED=0, or refuse to measure.

    Set iteration order reaches the derived features and, through them, the
    distance; an unfixed seed shows up as a few hundred spurious movers at
    ~1e-16. Rather than depend on the caller remembering the prefix, re-exec
    with the seed set. An explicitly wrong seed is an error, not something to
    quietly override.
    """
    seed = os.environ.get("PYTHONHASHSEED")
    if seed == "0":
        return
    if seed is not None:
        raise SystemExit(
            f"PYTHONHASHSEED={seed!r} makes this measurement unstable; "
            "run with PYTHONHASHSEED=0, or unset it and let this script set it."
        )
    print("re-exec under PYTHONHASHSEED=0", file=sys.stderr)
    os.execve(
        sys.executable,
        [sys.executable, *sys.argv],
        {**os.environ, "PYTHONHASHSEED": "0"},
    )


def corpus(ipa: IPAFeatures) -> list[tuple[str, str, str]]:
    """``(unit, base, mark)`` for every unit in the corpus, in inventory order.

    ``mark`` is the empty string for a bare phone. The order is the order the
    data declares, and the capture keeps it, so two captures list the same
    units in the same places and a plain diff of the two files is readable.

    Warnings are silenced here: the prosodic marks warn on every base they are
    tried against, and the point of the loop is to find out which combinations
    are well-formed, not to be told so once per candidate.
    """
    units: list[tuple[str, str, str]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for base in ipa.phones:
            for mark in ("", *ipa.diacritics):
                unit = base + mark
                try:
                    if ipa.segment(unit).to_ipa() != unit:
                        continue
                except Exception:  # noqa: BLE001 - not self-spelling either way
                    continue
                units.append((unit, base, mark))
    return units


def check_corpus(ipa: IPAFeatures, units: list[tuple[str, str, str]]) -> None:
    """Fail loudly if the sweep has gone vacuous or lost a whole class.

    Shape, not size: "every phone still contributes" catches one base that
    stopped composing, which a total large enough to look healthy would hide.
    """
    if len(units) < MIN_CORPUS:
        raise SystemExit(f"corpus collapsed: {len(units)} units, floor {MIN_CORPUS}")
    bare = {base for _, base, mark in units if not mark}
    if bare != set(ipa.phones):
        missing = sorted(set(ipa.phones) - bare)
        raise SystemExit(
            f"{len(missing)} phones do not spell themselves back: {missing}"
        )
    marked = {base for _, base, mark in units if mark}
    if marked != set(ipa.phones):
        missing = sorted(set(ipa.phones) - marked)
        raise SystemExit(f"{len(missing)} phones take no mark at all: {missing}")
    used = {mark for _, _, mark in units if mark}
    if len(used) < MIN_MARKS_USED:
        raise SystemExit(f"only {len(used)} marks compose, floor {MIN_MARKS_USED}")
    duplicates = len(units) - len({unit for unit, _, _ in units})
    if duplicates:
        raise SystemExit(f"{duplicates} units are spelled by two different bases")


def unused_marks(ipa: IPAFeatures, units: list[tuple[str, str, str]]) -> list[str]:
    """Marks that compose with nothing -- the corpus's known blind spot.

    These are the prosodic and boundary glyphs, which bind a unit rather than
    modify one. Printed by ``corpus`` so the limit stays known rather than
    assumed shut; if one of them starts composing, the list gets shorter and
    the change is visible.
    """
    used = {mark for _, _, mark in units if mark}
    return [mark for mark in ipa.diacritics if mark not in used]


def project(ipa: IPAFeatures, unit: str, base: str, mark: str) -> dict[str, Any]:
    """What the library says about one unit, in one comparable record.

    ``d_from_base`` is the distance from the unit to the phone it is built
    on -- what the mark is worth in the metric. It is the per-unit number the
    review rounds kept recomputing, and unlike the pairwise matrix (already
    guarded by ``confusion.py``) it covers the composed units too.
    """
    return {
        "base": base,
        "mark": mark,
        "kind": ipa.segment(unit).kind.value,
        "describe": ipa.describe(unit),
        "features": dict(sorted(ipa.get_features(unit).items())),
        "d_from_base": ipa.distance(unit, base),
    }


def _git_head() -> str:
    """The commit a capture was taken at, so a diff can name its ends."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return done.stdout.strip()


def take_capture(ipa: IPAFeatures) -> dict[str, Any]:
    """The whole corpus, projected, with the counts it was taken over."""
    units = corpus(ipa)
    check_corpus(ipa, units)
    return {
        "format": FORMAT,
        "ipakit": ipakit.__version__,
        "head": _git_head(),
        "phones": len(ipa.phones),
        "diacritics": len(ipa.diacritics),
        "corpus": len(units),
        "units": {unit: project(ipa, unit, base, mark) for unit, base, mark in units},
    }


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    rest = iter(long)
    return all(word in rest for word in short)


def classify(before: str, after: str) -> str:
    """How a description moved: it gained, lost, or altered a word.

    Word-level rather than string-level, because that is the distinction the
    review rounds needed. Adding "palatalized" to a description is additive
    and safe; replacing "alveolar" with "dental" is not; and to a plain string
    comparison both are just "it changed".
    """
    a, b = before.split(), after.split()
    if _is_subsequence(a, b):
        return "gained"
    if _is_subsequence(b, a):
        return "lost"
    return "altered"


def feature_delta(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Every key that gained, lost, or changed a value."""
    lines = []
    for key in sorted(set(before) | set(after)):
        was, now = before.get(key), after.get(key)
        if was != now:
            lines.append(f"{key}: {was!r} -> {now!r}")
    return lines


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise SystemExit(
            f"{path}: capture format {data.get('format')!r}, expected {FORMAT}"
        )
    return data


def _show(label: str, movers: list[str], limit: int) -> None:
    for line in movers[:limit]:
        print(f"         {line}")
    if len(movers) > limit:
        print(f"         ... and {len(movers) - limit} more {label} (--limit 0 = all)")


def cmd_capture(args: argparse.Namespace) -> int:
    model = take_capture(IPAFeatures())
    # Not sort_keys: the units keep inventory order, so two captures line up
    # line for line and `diff` on the raw files is usable as a cross-check.
    text = json.dumps(model, ensure_ascii=False, indent=1) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(
            f"wrote {args.output}: {model['corpus']} units over "
            f"{model['phones']} phones, {model['diacritics']} diacritics "
            f"(at {model['head']})"
        )
    else:
        sys.stdout.write(text)
    return 0


def cmd_corpus(_: argparse.Namespace) -> int:
    ipa = IPAFeatures()
    units = corpus(ipa)
    check_corpus(ipa, units)
    bare = sum(1 for _, _, mark in units if not mark)
    used = len({mark for _, _, mark in units if mark})
    print(
        f"corpus: {len(units)} units = {bare} bare phones + {len(units) - bare} "
        f"marked, kept from {len(ipa.phones)} x {len(ipa.diacritics) + 1} candidates"
    )
    print("  kept when segment(unit).to_ipa() == unit")
    print(f"  marks that compose: {used} of {len(ipa.diacritics)}")
    blind = unused_marks(ipa, units)
    print(f"  marks that compose with nothing ({len(blind)}): {' '.join(blind)}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    before, after = _load(Path(args.before)), _load(Path(args.after))
    limit = args.limit if args.limit > 0 else sys.maxsize

    print(
        f"sweep diff: {args.before} ({before['head']}) "
        f"-> {args.after} ({after['head']})\n"
    )
    changed = "" if before["corpus"] == after["corpus"] else "   CHANGED"
    print(
        f"  corpus {before['corpus']} -> {after['corpus']}"
        f"   phones {before['phones']} -> {after['phones']}"
        f"   diacritics {before['diacritics']} -> {after['diacritics']}{changed}"
    )

    old, new = before["units"], after["units"]
    appeared = sorted(set(new) - set(old))
    disappeared = sorted(set(old) - set(new))
    shared = [unit for unit in old if unit in new]

    described: dict[str, list[str]] = {"gained": [], "lost": [], "altered": []}
    featured: list[str] = []
    moved: list[str] = []
    for unit in shared:
        a, b = old[unit], new[unit]
        if a["describe"] != b["describe"]:
            described[classify(a["describe"], b["describe"])].append(
                f"{unit}: {a['describe']!r} -> {b['describe']!r}"
            )
        delta = feature_delta(a["features"], b["features"])
        if a["kind"] != b["kind"]:
            delta.append(f"kind: {a['kind']!r} -> {b['kind']!r}")
        if delta:
            featured.append(f"{unit}: " + "; ".join(delta))
        if abs(a["d_from_base"] - b["d_from_base"]) > TOLERANCE:
            moved.append(
                f"{unit}: d(unit, {a['base']}) "
                f"{a['d_from_base']:.6f} -> {b['d_from_base']:.6f}"
            )

    total = len(shared)
    words = sum(len(v) for v in described.values())
    print(f"\n  appeared:    {len(appeared)}")
    _show("appeared", appeared, limit)
    print(f"  disappeared: {len(disappeared)}")
    _show("disappeared", disappeared, limit)
    print(
        f"\n  descriptions moved: {words} of {total}"
        f"   (gained {len(described['gained'])},"
        f" lost {len(described['lost'])},"
        f" altered {len(described['altered'])})"
    )
    for kind in ("gained", "lost", "altered"):
        if described[kind]:
            print(f"    {kind} a word: {len(described[kind])}")
            _show(f"{kind} a word", described[kind], limit)
    print(f"\n  features moved: {len(featured)} of {total}")
    _show("feature movers", featured, limit)
    print(f"  distance from base moved: {len(moved)} of {total}")
    _show("distance movers", moved, limit)

    monotone = not described["lost"] and not described["altered"] and not disappeared
    mark = "ok  " if monotone else "FAIL"
    print(f"\n  [{mark}] monotone: no pre-existing word is lost or altered, only added")
    return 1 if args.require_monotone and not monotone else 0


def main(argv: list[str] | None = None) -> int:
    _ensure_hash_seed()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="project the whole corpus to JSON")
    p_cap.add_argument("-o", "--output", help="file to write (default stdout)")
    p_cap.set_defaults(func=cmd_capture)

    p_dif = sub.add_parser("diff", help="report every mover between two captures")
    p_dif.add_argument("before")
    p_dif.add_argument("after")
    p_dif.add_argument(
        "--limit", type=int, default=20, help="movers to list per class (0 = all)"
    )
    p_dif.add_argument(
        "--require-monotone",
        action="store_true",
        help="exit 1 if any pre-existing word was lost or altered",
    )
    p_dif.set_defaults(func=cmd_diff)

    p_cor = sub.add_parser("corpus", help="print the corpus definition and counts")
    p_cor.set_defaults(func=cmd_corpus)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
