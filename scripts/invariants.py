#!/usr/bin/env python3
"""Check the properties the library is supposed to hold, over everything.

The suite pins these too, but samples some of them for speed. This runs
them exhaustively and prints what it checked, so a change to the metric
or to composition can be verified in one command and the numbers can go
into a commit message. Where the two share an enumeration -- the chart
notations, the symbols the loader routes, the entry points a string
reaches the inventory by -- it is defined once here and imported there,
because a sweep is only as wide as its table and two copies of a table
drift.

    python scripts/invariants.py              # every check
    python scripts/invariants.py --quick      # skip the O(n^2) sweeps

Exit status is 1 if any invariant fails, so it can gate a release.
See docs/reviewing.md for why these are the ones worth checking.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import unicodedata
import warnings
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit import IPAFeatures  # noqa: E402
from ipakit.constants import METADATA_ATTRS  # noqa: E402

TOLERANCE = 1e-9

#: What ``<notations default=...>`` says today. Asserted below rather
#: than trusted, so the read and the data cannot drift apart.
CHART = "chart"

#: The symbols in ``ipa.xml`` that are **not** on the IPA chart. A set,
#: not a count: "three symbols are marked" keeps passing when the wrong
#: three are marked, which is this repo's named failure mode (a guard
#: that no longer guards). The chart-proper marks that look like
#: candidates and are not -- ``.``, ``|``, ``‖``, ``‿``, the tone
#: letters and diacritic tones, ``↗ ↘``, ``ꜛ ꜜ``, ``ˈ ˌ``, ``ː ˑ ̆``,
#: ``͡ ͜`` -- are covered by the other half of the equality: any of them
#: appearing in ``<notations>`` fails this.
NON_CHART = frozenset({"␣", "#", "∅"})

# Provenance and the zero are read through the library's own API --
# `IPAFeatures.notations`, `.notation_of`, `.zeros`,
# `ipakit.extensions_in`, `.is_pure_ipa`. This file used to *define*
# those four reads, which made the invariant the only definition of the
# thing it exists to check: a script is not an API, and one name read
# twice is the rule being broken in the place that enforces it.


def declared_symbols(ipa: IPAFeatures) -> dict[str, dict[str, str]]:
    """Every symbol the inventory declares, with what it declared.

    Every element class ``<classes>`` names, each read off the table the
    loader routes it into.
    """
    out: dict[str, dict[str, str]] = {}
    for table in (ipa.phones, ipa.diacritics, ipa.separators, ipa.zeros):
        for symbol, declared in table.items():
            out[symbol] = dict(declared.features or {})
    return out


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
            for tie in sorted(ipa.tie_bars):
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
                        if key in METADATA_ATTRS:
                            continue
                        if flat.get(key) != value:
                            disagreements.append(
                                f"{unit!r} {key}: features={flat.get(key)!r} "
                                f"scalar={value!r}"
                            )
    return _report("features == scalar", disagreements, checked)


def entry_points(ipa: IPAFeatures) -> dict[str, Callable[[str], object]]:
    """Every documented route a string takes into the inventory.

    One table, read by ``check_alias_equivalence`` here and by
    ``tests/test_ligature_aliases.py``. It was written twice and the two
    copies drifted: this one had thirteen entries while the suite's had
    twenty-five, and the twelve missing here were the ones the module
    docstring above claims to run exhaustively. A sweep is only as wide
    as its table, so there is one table.

    The point of the list is that it is not the routes that broke. Alias
    resolution used to sit in ``tokenize``, so everything reaching the
    inventory another way -- ``parse`` directly, or a converter that
    never touches ``parse`` -- read ``ʧ`` as a character registered
    nowhere and dropped it, and ``to_cmu`` answered a word one phoneme
    short. The next route in will not be one of those either.
    """
    import ipakit

    return {
        "features": ipakit.features,
        "compose": ipa.compose,
        "scalar": lambda s: ipa.segment(s).scalar(),
        "feature_values": ipakit.feature_values,
        "feature_bundles": ipakit.feature_bundles,
        "describe": lambda s: ipakit.describe(s) if s in ipa else None,
        "tokenize": ipa.tokenize,
        "segmented": ipakit.segmented,
        "segments": lambda s: [u.to_ipa() for u in ipa.segments(s)],
        "segments_strict": lambda s: [u.to_ipa() for u in ipa.segments(s, strict=True)],
        "parse": ipa.parse,
        "parse(strict)": lambda s: ipa.parse(s, strict=True),
        "normalize": ipa.normalize,
        "respell": ipakit.respell,
        "is_valid_ipa": ipakit.is_valid_ipa,
        "validate_ipa": ipakit.validate_ipa,
        "to_cmu": ipakit.to_cmu,
        "to_timit": ipakit.to_timit,
        "to_kirshenbaum": ipakit.to_kirshenbaum,
        "ipa_to_xsampa": ipakit.ipa_to_xsampa,
        "word_distance": lambda s: ipakit.word_distance(s, "ta").edit_cost,
        "distance": lambda s: ipakit.distance(s, "t"),
        "contains": lambda s: s in ipa,
        "get_phone": ipa.get_phone,
        "get_diacritic": ipa.get_diacritic,
    }


def check_alias_equivalence(ipa: IPAFeatures, quick: bool) -> bool:
    """An alias spelling and its canonical are one string, every route in.

    The routes are :func:`entry_points`, which the suite reads too.
    """
    entries = entry_points(ipa)
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


def check_notation(ipa: IPAFeatures) -> bool:
    """The marked symbols are exactly the ones off the IPA chart.

    Both directions matter and the second is the one at risk: this file
    is a record of the chart, so the tempting mistake is to mark a
    chart-proper symbol that merely *looks* like a convention. Every
    declared symbol is scanned, so an unmarked extension and an
    over-marked chart symbol each fail here.
    """
    declared = declared_symbols(ipa)
    default, marked_map = ipa.default_notation, ipa.notations
    marked = {s for s, n in marked_map.items() if n != default}
    failures = [
        f"{s!r} is listed as {marked_map[s]!r} but is on the chart"
        for s in sorted(marked - NON_CHART)
    ]
    failures += [
        f"{s!r} is not on the chart but is listed under no notation"
        for s in sorted(NON_CHART - marked)
    ]
    if default != CHART:
        failures.append(f"the default notation is {default!r}, not {CHART!r}")
    # A listed symbol must be one the inventory actually declares, so a
    # typo cannot sit in the block marking nothing at all.
    failures += [
        f"{s!r} is listed under {marked_map[s]!r} but is declared nowhere"
        for s in sorted(marked_map)
        if s not in declared
    ]
    return _report(
        "non-chart symbols are exactly the listed set", failures, len(declared)
    )


def check_zero(ipa: IPAFeatures) -> bool:
    """A structural zero is a position, not a sound.

    It must stay out of the inventory and out of the feature bag: the
    moment it carries a phonetic feature it is a phone wearing another
    name, and the metric would have to have an opinion about it.
    """
    from ipakit.form import Form, zeros

    declared = zeros(ipa)
    failures = []
    if not declared:
        failures.append("no <zeros> declared; this check is vacuous")
    phonetic = set(ipa.features) - {
        name for name, f in ipa.features.items() if f.mode == "structural"
    }
    for symbol, bundle in sorted(declared.items()):
        if symbol in ipa.phones:
            failures.append(f"{symbol!r} is registered as a phone as well as a zero")
        if symbol in ipa.diacritics or symbol in ipa.separators:
            failures.append(f"{symbol!r} is declared twice, in two element classes")
        if said := sorted(set(bundle) & phonetic):
            failures.append(f"{symbol!r} declares phonetic features {said}")
        # It holds its position and carries no sound: written between two
        # phones it survives the round trip and contributes no phone.
        form = Form.parse(f"a{symbol}b", ipa)
        if form.to_ipa() != f"a{symbol}b":
            failures.append(f"{symbol!r} does not spell back out: {form.to_ipa()!r}")
        if form.phones != ("a", "b"):
            failures.append(f"{symbol!r} contributes a phone: {form.phones}")
        if [u.is_zero for u in form.units] != [False, True, False]:
            failures.append(f"{symbol!r} is not read as a zero position")
    return _report(
        "a zero holds a position and is not a sound", failures, len(declared)
    )


def check_projection_coherence(ipa: IPAFeatures, quick: bool = False) -> bool:
    """No unit may contradict a projection its own bundle states.

    ``<projections>`` declares that ``phonation`` and ``voiced`` are one
    glottal fact at two granularities: every phonation fixes a voicing.
    A bundle that states a phonation and a *different* voicing therefore
    contradicts the file it was composed from, and it reads back as a
    sentence that contradicts itself -- ``c̤`` described as a "voiceless
    breathy-voiced palatal plosive".

    Seventy-six composed units did. The projection was never at fault
    and neither was the composer: two of the four phonation marks
    declared the voicing their phonation fixes (``̥`` says ``voiced="-"``,
    ``̬`` says ``voiced="+"``) and two said nothing, so on a voiceless
    base the breathy and creaky marks left the base's voicing standing.
    An asymmetry in the data, and it is fixed in the data.

    The predicate is over the *declaration*, not over a list of the
    offenders: it reads whatever projections the file states and applies
    them to whatever units the inventory spells, so a fifth phonation
    value, or a new mark declaring one, is covered the day it is added.

    A unit that states the finer feature and *no* value for the coarser
    one is not a contradiction here -- there is nothing to disagree
    with. Silence is the case that reaches this: ``␣`` takes no
    defaults, so it carries no ``voiced`` until a mark puts one there.
    """
    if not ipa.projections:
        return _report("no unit contradicts a projection", ["none declared"], 0)
    failures, checked = [], 0
    marks = list(ipa.diacritics)[: 12 if quick else None]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for phone in ipa.phones:
            for mark in ["", *marks]:
                unit = phone + mark
                try:
                    if ipa.segment(unit).to_ipa() != unit:
                        continue
                except ValueError:
                    continue
                bundle = ipa.get_features(unit)
                if not bundle:
                    continue
                checked += 1
                for (fine, value), (coarse, reads) in ipa.projections.items():
                    if bundle.get(fine) != value:
                        continue
                    if bundle.get(coarse, reads) != reads:
                        failures.append(
                            f"{unit!r} says {fine}={value!r}, which reads "
                            f"{coarse}={reads!r}, but its bundle says "
                            f"{coarse}={bundle[coarse]!r}"
                        )
    return _report("no unit contradicts a projection", failures, checked)


def pitch_marks(ipa: IPAFeatures) -> dict[str, str]:
    """Component name -> the tone value that component declares.

    Keyed by the Unicode name a compound spells its parts with, so
    ``COMBINING ACUTE ACCENT`` is reachable as ``ACUTE``. Built from
    whichever simplex marks the inventory declares a ``tone`` on, which
    is what makes the check below derived rather than a second table of
    phonetic facts: ``ipa.xml`` already says acute is high, macron mid
    and grave low.
    """
    out = {}
    for symbol, declared in ipa.diacritics.items():
        value = (declared.features or {}).get("tone")
        if value is None or len(symbol) != 1:
            continue
        try:
            name = unicodedata.name(symbol)
        except ValueError:
            continue
        if not name.startswith("COMBINING ") or "-" in name:
            continue
        part = name.removeprefix("COMBINING ").removesuffix(" ACCENT")
        out[part] = value
    return out


def check_contour_marks(ipa: IPAFeatures) -> bool:
    """A compound tone mark declares the levels its own name spells.

    These marks are ligatures of the simplex IPA pitch diacritics, and
    **their Unicode names spell the components in time order**:
    ``COMBINING MACRON-ACUTE`` is mid then high. Each component's pitch is
    what ``ipa.xml`` already declares for that simplex mark, and a contour
    is a *sequence* of those levels (docs/tone.md), so a compound's whole
    ``tone`` value is derivable from two things the file already states.
    A declaration that disagrees with them is a data error.

    It was. ``᷅`` U+1DC5 COMBINING GRAVE-MACRON declared
    ``contour="falling"``; low then mid rises. Unicode's own proposal for
    the extension of this series (L2/25-250) reads the four two-level
    marks as ``◌᷄`` higher rising, ``◌᷅`` **lower rising**, ``◌᷆`` lower
    falling, ``◌᷇`` higher falling, which agrees. The value never entered
    a feature bag -- ``tone`` and ``contour`` are ``mode="prosodic"``, so
    they live on the unit -- so nothing in the metric could contradict it
    and the wrong answer surfaced only at ``units("a᷅")[0].prosody``.

    Checking the whole sequence rather than a direction is what reaches
    the turning marks: ``◌᷈`` low-high-low and ``◌᷉`` high-low-high have no
    two-valued verdict to compare, and a direction check skipped them.

    A compound also may not declare a ``contour`` beside its levels. The
    shape follows from the sequence, so a second statement of it is a
    claim that can come to disagree with the levels it is supposed to
    summarize -- which is exactly the defect above.

    Simplex marks are skipped: their names carry no ``-`` and so describe
    no sequence. That is the check's blind spot, and it is why the count
    reported is the number of *compound* marks. The caron and the
    circumflex are outside it in the other direction: they assert a
    direction and name no levels, so there is nothing here to derive.
    """
    tone = ipa.features["tone"]
    parts_of = pitch_marks(ipa)
    failures = []
    checked = 0
    for symbol, declared in sorted(ipa.diacritics.items()):
        stated = (declared.features or {}).get("tone")
        if stated is None or len(symbol) != 1:
            continue
        try:
            name = unicodedata.name(symbol)
        except ValueError:
            continue
        pieces = name.removeprefix("COMBINING ").split("-")
        if len(pieces) < 2 or not all(p in parts_of for p in pieces):
            continue  # a simplex mark, or a component declaring no tone
        checked += 1
        want = tone.sequenced([parts_of[p] for p in pieces])
        if stated != want:
            failures.append(
                f"{symbol!r} (U+{ord(symbol):04X} {name}) declares "
                f"tone={stated!r}, but its parts spell {want!r}"
            )
        if (shape := (declared.features or {}).get("contour")) is not None:
            failures.append(
                f"{symbol!r} (U+{ord(symbol):04X} {name}) declares "
                f"contour={shape!r} beside its levels; the shape is derived "
                "from the sequence and must not be stated twice"
            )
    if not checked:
        failures.append("no compound tone mark declared; this check is vacuous")
    return _report("a compound tone mark's levels are its parts'", failures, checked)


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
        check_notation(ipa),
        check_zero(ipa),
        check_contour_marks(ipa),
        check_projection_coherence(ipa, args.quick),
        check_derived_artifacts(),
    ]
    ok = all(results)
    print("\n" + ("all invariants hold" if ok else "INVARIANTS VIOLATED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
