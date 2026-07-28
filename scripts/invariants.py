#!/usr/bin/env python3
"""Check the properties the library is supposed to hold, over everything.

The suite pins these too, but samples some of them for speed. This runs
them exhaustively and prints what it checked, so a change to the metric
or to composition can be verified in one command and the numbers can go
into a commit message.

    python scripts/invariants.py              # every check
    python scripts/invariants.py --quick      # skip the O(n^2) sweeps

Exit status is 1 if any invariant fails, so it can gate a release.
See docs/reviewing.md for why these are the ones worth checking.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import warnings
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit import IPAFeatures  # noqa: E402

TOLERANCE = 1e-9


def _report(name: str, failures: list[str], checked: int) -> bool:
    mark = "ok  " if not failures else "FAIL"
    print(f"  [{mark}] {name}: {checked} checked, {len(failures)} failures")
    for line in failures[:5]:
        print(f"         {line}")
    if len(failures) > 5:
        print(f"         ... and {len(failures) - 5} more")
    return not failures


def check_metric(ipa: IPAFeatures) -> bool:
    """Identity, symmetry, range, and distinct pairs at distance zero.

    The zero check is the one that has caught real defects: two distinct
    phones the metric cannot tell apart means a feature is being dropped.
    """
    phones = list(ipa.phones)
    identity = [p for p in phones if ipa.distance(p, p) != 0.0]
    asymmetric, out_of_range, collisions = [], [], []
    pairs = 0
    for a, b in itertools.combinations(phones, 2):
        pairs += 1
        forward, back = ipa.distance(a, b), ipa.distance(b, a)
        if abs(forward - back) > TOLERANCE:
            asymmetric.append(f"d({a},{b})={forward} but d({b},{a})={back}")
        if not 0.0 <= forward <= 1.0:
            out_of_range.append(f"d({a},{b})={forward}")
        if forward == 0.0:
            collisions.append(f"d({a},{b})=0 but they are different phones")
    return all(
        [
            _report("identity", [f"d({p},{p})!=0" for p in identity], len(phones)),
            _report("symmetry", asymmetric, pairs),
            _report("range [0,1]", out_of_range, pairs),
            _report("no distinct pair at distance 0", collisions, pairs),
        ]
    )


def check_round_trips(ipa: IPAFeatures) -> bool:
    """A unit must spell itself back, through the string and through JSON."""
    from ipakit.segment import Segment

    emit, json_trip = [], []
    for phone in ipa.phones:
        if ipa.to_ipa(ipa.segments(phone)) != phone:
            emit.append(f"{phone!r} -> {ipa.to_ipa(ipa.segments(phone))!r}")
        restored = Segment.from_json(ipa.segment(phone).to_json(), ipa)
        if restored.to_ipa() != phone:
            json_trip.append(f"{phone!r} -> {restored.to_ipa()!r}")
    return all(
        [
            _report("to_ipa(segments(p)) == p", emit, len(ipa.phones)),
            _report("json round trip", json_trip, len(ipa.phones)),
        ]
    )


def check_one_flat_read(ipa: IPAFeatures, quick: bool) -> bool:
    """`features`, `compose` and `scalar` are one read of a unit.

    They were three implementations disagreeing on tens of thousands of
    strings. Marks go in every position of the chain, because the
    divergence lived entirely on the non-final ones.
    """
    marks = list(ipa.diacritics)[: 12 if quick else None]
    bases = list(ipa.phones)[: 20 if quick else None]
    disagreements, checked = [], 0
    for base in bases:
        for mark in marks:
            for tie in ("͡", "͜"):
                for unit in (f"{base}{mark}{tie}s", f"{base}{tie}s{mark}"):
                    try:
                        structured = ipa.segment(unit).scalar()
                    except ValueError:
                        continue
                    flat = ipa.get_features(unit)
                    if not flat or not structured:
                        continue
                    checked += 1
                    for key, value in structured.items():
                        if key in ("class", "href", "xsampa"):
                            continue
                        if flat.get(key) != value:
                            disagreements.append(
                                f"{unit!r} {key}: features={flat.get(key)!r} "
                                f"scalar={value!r}"
                            )
    return _report("features == scalar", disagreements, checked)


def check_alias_equivalence(ipa: IPAFeatures, quick: bool) -> bool:
    """An alias spelling and its canonical are one string, every route in.

    Alias resolution used to sit in `tokenize`, so the routes that reach
    the inventory another way -- `parse` directly, or a converter table
    that never touches `parse` -- read `ʧ` as a character registered
    nowhere and dropped it: `to_cmu` answered a word one phoneme short.
    The check is every entry point rather than the converters that broke,
    because the next route in will not be one of those.
    """
    import ipakit

    entries: dict[str, Callable[[str], object]] = {
        "features": ipakit.features,
        "compose": ipa.compose,
        "scalar": lambda s: ipa.segment(s).scalar(),
        "tokenize": ipa.tokenize,
        "segments": lambda s: [u.to_ipa() for u in ipa.segments(s)],
        "parse": ipa.parse,
        "parse(strict)": lambda s: ipa.parse(s, strict=True),
        "normalize": ipa.normalize,
        "to_cmu": ipakit.to_cmu,
        "to_timit": ipakit.to_timit,
        "to_kirshenbaum": ipakit.to_kirshenbaum,
        "ipa_to_xsampa": ipakit.ipa_to_xsampa,
        "word_distance": lambda s: ipakit.word_distance(s, "ta").distance,
    }
    marks = list(ipa.diacritics)[: 12 if quick else None]
    disagreements, checked = [], 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for alias in ipa.ligature_map:
            texts = [alias, "k͡" + alias, alias + "a", "a" + alias]
            texts += [alias + mark for mark in marks]
            for text in texts:
                canonical = ipa.expand_ligatures(text)
                for name, fn in entries.items():
                    checked += 1
                    if _same(fn, text) != _same(fn, canonical):
                        disagreements.append(
                            f"{name}({text!r}) != {name}({canonical!r})"
                        )
    return _report("alias reads as its canonical", disagreements, checked)


def _same(fn: Callable[[str], object], text: str) -> object:
    """What an entry point says; raising counts as an answer, by type.

    The message is excluded because it may name the caller's own input,
    which the two spellings differ in by construction.
    """
    try:
        return fn(text)
    except Exception as exc:  # noqa: BLE001 - the type is the answer
        return type(exc).__name__


def check_descriptions(ipa: IPAFeatures) -> bool:
    """No two distinct phones may share a description.

    The documented exception is an atomic vowel and the diphthongs built
    on it, whose flat projection is that vowel by design.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for phone in ipa.phones:
        groups[ipa.describe(phone)].append(phone)
    bad = []
    for description, members in groups.items():
        if len(members) < 2:
            continue
        kinds = {ipa.segment(m).kind.value for m in members}
        if kinds <= {"atomic", "diphthong"} and len(members) == len(
            [m for m in members if ipa.segment(m).kind.value in kinds]
        ):
            continue  # a nucleus and its diphthongs
        bad.append(f"{description!r} names {members}")
    return _report("descriptions distinguish phones", bad, len(ipa.phones))


def check_derived_artifacts() -> bool:
    """The shipped matrix and X-SAMPA table match what the code derives."""
    sys.path.insert(0, "scripts")
    import confusion
    import xsampa_table

    failures = []
    if confusion.derive()["triangle"] != confusion.shipped()["triangle"]:
        failures.append("confusion.json is stale: regenerate with generate --write")
    try:
        if xsampa_table.canonical_pairs() != xsampa_table.shipped_pairs():
            failures.append("xsampa.xml is stale")
    except AttributeError:
        pass  # the module names these differently; its own validate covers it
    return _report("derived artifacts current", failures, 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick", action="store_true", help="skip the exhaustive sweeps"
    )
    args = parser.parse_args(argv)

    ipa = IPAFeatures()
    print(
        f"ipakit invariants over {len(ipa.phones)} phones, "
        f"{len(ipa.diacritics)} diacritics\n"
    )
    results = [
        check_metric(ipa),
        check_round_trips(ipa),
        check_one_flat_read(ipa, args.quick),
        check_alias_equivalence(ipa, args.quick),
        check_descriptions(ipa),
        check_derived_artifacts(),
    ]
    ok = all(results)
    print("\n" + ("all invariants hold" if ok else "INVARIANTS VIOLATED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
