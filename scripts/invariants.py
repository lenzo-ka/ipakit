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
import hashlib
import itertools
import json
import sys
import unicodedata
import warnings
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit import IPAFeatures
from ipakit.constants import METADATA_ATTRS

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

#: Midline vertices whose ``arc`` names no value declared in ``ipa.xml``.
#: A head's midline is a hand-traced polyline whose vertices sit at the
#: declared places, so the arc column is a second copy of numbers
#: ``ipa.xml`` owns; a vertex at an arc nothing declares is the escape,
#: and it is stated so it can only be added on purpose. All carry the
#: X-Ray Microbeam diameter run between declared anchors: ``0.40`` between
#: the palatal and velar, and ``0.11`` (the palate outline's front edge,
#: the alveolar ridge) plus ``0.15``, ``0.17`` and ``0.21`` sampling the
#: measured palate arch between the alveolar front and the vault, where the
#: dome's curve sits on no phonetic place. See docs/articulatory-data.md.
UNDECLARED_VERTEX_ARCS = frozenset({0.11, 0.15, 0.17, 0.21, 0.40})

#: The largest disagreement, per shipped polyline, between a vertex's
#: declared ``arc`` and its own polyline's normalized cumulative
#: arclength -- the two readings of "proportional position along the
#: midline" that ``docs/design/tract-validation.md`` 1 relies on being
#: the same quantity.
#:
#: Pinned rather than bounded, deliberately. The smallest tolerance that
#: passes today is 0.064, and adjacent declared places sit 0.03 to 0.06
#: apart (``bilabial``->``labiodental`` 0.03, ``alveolar``->
#: ``postalveolar`` 0.06), so every threshold this data would pass also
#: permits a vertex to sit where the next place over lives. A bound that
#: cannot fail is not a guard. The six numbers are stated instead, so
#: the disagreement is a known quantity that moves only on purpose --
#: in either direction.
ARCLENGTH_GAPS = {
    ("adult-female", "midline"): 0.034624,
    ("adult-female", "nasal"): 0.000041,
    ("adult-male", "midline"): 0.027431,
    ("adult-male", "nasal"): 0.000050,
    ("child", "midline"): 0.061651,
    ("child", "nasal"): 0.063599,
}

#: How far a pinned gap may move before it counts as a change. Loose
#: enough that the four printed digits are the whole statement, tight
#: enough that moving any vertex by a thousandth of the tract fails.
ARCLENGTH_EPSILON = 5e-4

# Provenance and the zero are read through the library's own API --
# `IPAFeatures.notations`, `.notation_of`, `.zeros`,
# `ipakit.extensions_in`, `.is_pure_ipa`. This file used to *define*
# those four reads, which made the invariant the only definition of the
# thing it exists to check: a script is not an API, and one name read
# twice is the rule being broken in the place that enforces it.


def declared_symbols(ipa: IPAFeatures) -> dict[str, dict[str, str]]:
    """Every symbol the inventory declares, with what it declared.

    Every element class ``<classes>`` names, each read off the table the
    loader routes it into. The enumeration lives on the inventory, because
    the supplement loader has to ask the same question -- is this symbol
    already taken -- and two hand-written tuples of the same four tables is
    the shape this repository drifts on.
    """
    return ipa.declared_symbols


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
        "to_xsampa": ipakit.to_xsampa,
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

    The one collapse that is by design is a nucleus and the diphthongs
    built on it: the flat projection of ``a͜ɪ`` *is* ``a``, so the
    sentence read off it is ``a``'s sentence and there is nothing for the
    describer to have got wrong. :func:`_nucleus_and_its_diphthongs` says
    all of that and no more.

    Every clause of it is load-bearing, because each one alone excuses a
    real collision. Two phones that are merely both atomic are not a
    nucleus and its diphthongs. Neither are two diphthongs with no
    nucleus between them, nor a diphthong sharing a sentence with a vowel
    it is not built on, nor one whose bundle has drifted off its
    nucleus's -- the last being how eight derived diphthongs once
    acquired explicit features, which is the defect ``docs/reviewing.md``
    tells this story about. An exception that asks only which *kinds* the
    group holds excuses all four, and the first of them is every
    collision this check exists to find.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for phone in ipa.phones:
        groups[ipa.describe(phone)].append(phone)
    bad = [
        f"{description!r} names {members}"
        for description, members in groups.items()
        if len(members) > 1 and not _nucleus_and_its_diphthongs(ipa, members)
    ]
    return _report("descriptions distinguish phones", bad, len(ipa.phones))


def _nucleus_and_its_diphthongs(ipa: IPAFeatures, members: list[str]) -> bool:
    """Whether phones sharing a description are one vowel and its glides.

    Exactly one member is atomic; every other member is a diphthong that
    opens on that member and carries its phonetic bundle.
    """
    from ipakit.segment import Kind

    segments = {m: ipa.segment(m) for m in members}
    nuclei = [m for m, s in segments.items() if s.kind is Kind.ATOMIC]
    if len(nuclei) != 1:
        return False
    nucleus = nuclei[0]
    bundle = _phonetic(ipa.get_features(nucleus))
    return all(
        s.kind is Kind.DIPHTHONG
        and s.constituents[0].base == nucleus
        and _phonetic(ipa.get_features(m)) == bundle
        for m, s in segments.items()
        if m != nucleus
    )


def _phonetic(bundle: dict[str, str]) -> dict[str, str]:
    """A bundle without the keys that name the entry rather than the sound.

    A diphthong's ``href`` points at the article on diphthongs and its
    nucleus's at the article on that vowel, which is provenance
    disagreeing, not phonetics.
    """
    return {k: v for k, v in bundle.items() if k not in METADATA_ATTRS}


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


def check_classes_are_total(ipa: IPAFeatures) -> bool:
    """A feature carrying a natural class is declared on every phone.

    A positive class query resolves to *exclusions only*: ``['obstruent']``
    becomes "manner is none of the six sonorant manners", because a
    bracket is a conjunction and the class is carried as the complement of
    its own members. That reading is exactly right while every phone
    states a manner, and vacuous the moment one does not -- a bundle with
    no ``manner`` key excludes nothing and so satisfies the query, and
    ``obstruent`` would quietly match the vowels.

    Nothing is in that position today: every feature a class is declared
    over is stated by every registered phone, with defaults and without.
    So this is not a fix, it is the assumption the resolver makes, written
    down where something reads it. The day a class is declared over a
    partial feature, positive class queries go silently wide, and this is
    what says so.

    Read off the declaration in both directions -- which features carry
    classes, and which phones state them -- so a class added to the data
    joins the check without this function being edited.
    """
    carrying = {
        name: sorted(feat.value_classes)
        for name, feat in ipa.features.items()
        if feat.value_classes
    }
    failures = []
    if not carrying:
        failures.append("no natural class is declared; this check is vacuous")
    checked = 0
    for name, classes in sorted(carrying.items()):
        for with_defaults in (True, False):
            missing = [
                phone
                for phone in ipa.phones
                if name not in ipa.get_features(phone, with_defaults=with_defaults)
            ]
            checked += 1
            if missing:
                failures.append(
                    f"feature {name!r} carries the natural class(es) {classes} "
                    f"but {len(missing)} phone(s) do not state it "
                    f"(with_defaults={with_defaults}): {missing[:5]}; a "
                    "positive class query over it matches them vacuously"
                )
    return _report(
        "every feature carrying a natural class is total over the inventory",
        failures,
        checked,
    )


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


def check_head_arcs(ipa: IPAFeatures) -> bool:
    """``arc`` means one thing across the two files that state it.

    ``ipa.xml`` declares an ``arc`` on the values of ``place``,
    ``backness`` and ``articulator``. ``heads.xml`` states one again on
    every polyline vertex, and hand-places an ``(x, y)`` beside it. That
    is three readings of one quantity and, until this check, no gate
    between any of them:

    * **the vertex names a declared arc.** A head's midline is traced
      through the declared places, so its arc column is a copy of
      numbers ``ipa.xml`` owns. Changing ``place=velar`` from 0.45 to
      0.47 leaves the 0.45 vertex behind and nothing notices -- the
      constriction is simply drawn at an interpolated spot that no
      longer means what it says. Vertices at an arc nothing declares are
      the stated escape (:data:`UNDECLARED_VERTEX_ARCS`).
    * **the arc column agrees with the coordinates.** ``arc`` is
      documented as proportional position along the midline, so a
      vertex's arc should be its own polyline's normalized cumulative
      arclength. It is not, by up to 0.064, and no tolerance both passes
      and means anything -- so the disagreement is pinned rather than
      bounded (:data:`ARCLENGTH_GAPS`).
    * **both readings ascend together.** ``Head.project`` and
      ``_project_along`` locate a point by scanning for the bracketing
      pair, which assumes the arcs increase; interpolating a diameter
      over a polyline that doubles back would return a position off the
      wall it is measured to.

    The nasal branches are checked on the same footing as the midlines.
    They declare the same attributes, are interpolated by the same code,
    and make the same claim about their own arc (0 at the nostrils to 1
    at the port) -- and they are where the largest disagreement in the
    shipped file actually is, which is why leaving them out would have
    reported a clean 0.062 over a file whose worst point is 0.064.
    """
    import math

    from ipakit.tract import heads

    declared = {
        round(coords["arc"], 6)
        for name in ("place", "backness", "articulator")
        if (feat := ipa.features.get(name)) is not None
        for coords in feat.coordinates.values()
        if coords.get("arc") is not None
    }
    failures: list[str] = []
    checked = 0
    for head_name, shape in sorted(heads().items()):
        for label, points in (("midline", shape.midline), ("nasal", shape.nasal)):
            if len(points) < 2:
                continue
            checked += 1
            run = [0.0]
            for before, after in itertools.pairwise(points):
                run.append(run[-1] + math.hypot(after.x - before.x, after.y - before.y))
            total = run[-1]
            if not total:
                failures.append(f"{head_name} {label}: polyline has zero length")
                continue
            for before, after in itertools.pairwise(points):
                if before.arc >= after.arc:
                    failures.append(
                        f"{head_name} {label}: arc does not ascend at "
                        f"{before.arc} -> {after.arc}; project() locates a "
                        "point by the bracketing pair and would miss it"
                    )
            for length, onward in itertools.pairwise(run):
                if length >= onward:
                    failures.append(
                        f"{head_name} {label}: the polyline doubles back at "
                        f"arclength {length}"
                    )
            if label == "midline":
                stray = sorted(
                    {round(p.arc, 6) for p in points}
                    - declared
                    - UNDECLARED_VERTEX_ARCS
                )
                if stray:
                    failures.append(
                        f"{head_name} midline: vertices at {stray}, which "
                        "ipa.xml declares for no place, backness or "
                        "articulator; either the declaration moved and the "
                        "head did not, or the vertex belongs in "
                        "UNDECLARED_VERTEX_ARCS with a reason"
                    )
            gap = max(
                abs(length / total - point.arc)
                for length, point in zip(run, points, strict=True)
            )
            pinned = ARCLENGTH_GAPS.get((head_name, label))
            if pinned is None:
                failures.append(
                    f"{head_name} {label}: no pinned arclength gap; a new "
                    f"polyline disagrees with its own arc column by {gap:.6f} "
                    "and nothing had stated what that is allowed to be"
                )
            elif abs(gap - pinned) > ARCLENGTH_EPSILON:
                failures.append(
                    f"{head_name} {label}: arc against its own arclength "
                    f"disagrees by {gap:.6f}, pinned at {pinned:.6f}"
                )
    for key in sorted(ARCLENGTH_GAPS):
        if key[0] not in heads():
            failures.append(f"pinned gap for {key}, which no head declares")
    if not checked:
        failures.append("no head polyline checked; this check is vacuous")
    return _report("arc means one thing in ipa.xml and heads.xml", failures, checked)


def check_derived_artifacts() -> bool:
    """Every recorded derived artifact matches its byte-level pin."""
    root = Path(__file__).resolve().parent.parent
    record_path = root / "tests" / "tiergraph" / "baselines" / "derived-artifacts.json"
    failures = []
    records = json.loads(record_path.read_text(encoding="utf-8"))["artifacts"]
    for record in records:
        exemption = record.get("exemption")
        if exemption is not None:
            if not isinstance(exemption, str) or not exemption.strip():
                failures.append(f"{record['path']}: exemption has no reason")
            continue
        path = root / record["path"]
        if not path.is_file():
            failures.append(f"{record['path']}: missing")
            continue
        contents = path.read_bytes()
        actual = hashlib.sha256(contents).hexdigest()
        if len(contents) != record["bytes"] or actual != record["sha256"]:
            failures.append(
                f"{record['path']}: stale (recorded {record['bytes']} bytes / "
                f"{record['sha256']}, actual {len(contents)} bytes / {actual})"
            )
    return _report("derived artifacts current", failures, len(records))


def check_fusion_arity(ipa: IPAFeatures) -> bool:
    """Invariant 5: every added articulator costs at least a release phase.

    The two sides are intentionally read through the public metric. In
    particular, this check does not import or recompute the arity derivation;
    otherwise it would merely restate the implementation and could not catch a
    missing or weakened charge.
    """
    release = ipa.distance("t", "tʰ")
    failures = []
    checked = 0
    phones = list(ipa.phones)
    for i, left in enumerate(phones):
        x = ipa.segment(left)
        for right in phones[i + 1 :]:
            y = ipa.segment(right)
            x_speech = ipa.get_features(left).get("manner") != "silence"
            y_speech = ipa.get_features(right).get("manner") != "silence"
            if (
                not x_speech
                or not y_speech
                or x.phased
                or y.phased
                or {len(x.constituents), len(y.constituents)}
                != {
                    1,
                    2,
                }
            ):
                continue
            checked += 1
            articulator = ipa.distance(left, right)
            if articulator < release:
                failures.append(
                    f"{left!r} / {right!r}: added articulator costs "
                    f"{articulator:.6f}, below release phase {release:.6f}"
                )
    if not checked:
        failures.append("no unordered one-to-two constituent pair checked")
    return _report(
        "every added articulator costs at least a release phase", failures, checked
    )


#: The ``<value>`` attributes the loader reads only for a feature that
#: takes its values from ``<value>`` elements. A typed feature takes its
#: value *set* from its ``<type>``, so these are never looked at on one.
POSTURAL_ATTRS = ("arc", "offset", "articulator", "aperture", "alias")


def check_typed_values_declare_no_geometry(ipa: IPAFeatures) -> bool:
    """A typed feature's values may not declare geometry, because the
    loader would not read it.

    ``IPAFeatures`` builds ``coordinates``, ``articulators``,
    ``apertures`` and the alias map inside the branch for features that
    list their own ``<value>`` elements. A feature with ``type="binary"``
    or ``type="ternary"`` takes its values from the ``<type>`` instead
    and goes down the other branch, where those attributes are never
    looked at -- so ``<value name="+" arc="0.19"/>`` on a binary feature
    loads clean, validates against ``ipa.rng`` (which makes ``arc``
    optional on any ``<value>``, with no dependency on the parent's
    type), and does exactly nothing.

    That is a silent wrong answer waiting for the first person who tries
    to give a binary feature a position -- which is the obvious thing to
    reach for, since ``rounded`` and ``rhotacized`` are both binary and
    both name articulations the geometry does not carry. It cost this
    lane a measurement to find out that a coordinate declared there
    evaporates.

    The suite already asserts the *result* -- ``test_metric.py``'s
    ``test_typed_features_carry_no_per_value_tables`` checks that a
    loaded typed ``Feature`` has no coordinate tables. That passes
    whether the XML declared any or not, because the loader drops them
    either way. This is the converse, read off the document: it fails on
    the declaration rather than on what survived it.
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(ipa.xml_path).getroot()
    typed = set(ipa.types)
    failures: list[str] = []
    checked = 0
    features = root.find("features")
    for elem in features.findall("feature") if features is not None else []:
        name = elem.get("name")
        if not name or elem.get("type") not in typed:
            continue
        for value in elem.findall("value"):
            checked += 1
            stated = [a for a in POSTURAL_ATTRS if value.get(a) is not None]
            if stated:
                failures.append(
                    f"{name}={value.get('name')!r} declares {stated}, and "
                    f"{name} is typed {elem.get('type')!r} so the loader "
                    "never reads them; the declaration would be silently "
                    "inert"
                )
    if not checked:
        failures.append("no typed feature declares a value; this check is vacuous")
    return _report("a typed feature's values declare no geometry", failures, checked)


#: What a borrowed vocabulary is: the value set, the spellings that
#: resolve into it, and what each value carries.
BORROWED = frozenset(
    {
        "values",
        "value_aliases",
        "offscale",
        "coordinates",
        "articulators",
        "apertures",
        "lip_dofs",
        "value_classes",
    }
)
#: What is the borrower's own, and why. Every one of these is a fact about
#: the *declaration* rather than about the values: which host class it
#: applies to, how a mark stating it combines, what it is called.
#:
#: ``labels`` is the one that is neither obvious nor cosmetic. A label is
#: how a value reads out in a description, and a description reads a
#: modifier out *because* its feature declares one -- so a borrowed label
#: would put the source's word into the name of the borrower's host, which
#: is the rename that made `place` the wrong carrier for a vowel's
#: constriction in the first place.
NOT_BORROWED = {
    "name": "the borrower's own name",
    "default": "what the borrower reports unstated, which the source does not decide",
    "center": "the borrower's unmarked ordinal center",
    "type": "the borrower's comparison discipline",
    "desc": "the borrower's own description",
    "axis": "the borrower's own axis, though a borrower will usually share it",
    "mode": "how a mark stating the borrower combines with its base",
    "place": "the constriction a secondary articulation adds, if the borrower is one",
    "constriction": "whether the borrower's constriction has no single location (a rhotic); the borrower's own fact, not the source's",
    "vocabulary": "the borrowing itself",
    "applies": "which hosts the borrower is expected on",
    "sequence": "whether the borrower's values may be trajectories",
    "over": "the scale the borrower's values move along",
    "moves": "a move is read only beside `over`, which is the borrower's own",
    "labels": "how a value reads out in a description; see above",
    "bare": (
        "which feature answers a plain term, which is notation and stays "
        "with the lender for the same reason its short codes do"
    ),
}


def check_borrowed_vocabulary_is_total(_: IPAFeatures) -> bool:
    """Every field of a ``Feature`` is classified as borrowed or not.

    The check below compares the borrowed ones. What it cannot see is a
    field nobody thought about: add a per-value table to ``Feature``,
    forget to copy it in the loader, and the borrower silently has an
    empty one while the source has a full one -- a second declaration of
    the same thing, arrived at by omission, which is exactly what
    borrowing exists to prevent. So the partition is asserted total, and a
    new field fails here until it is put on one side or the other.
    """
    from dataclasses import fields

    from ipakit.models import Feature

    declared = {f.name for f in fields(Feature)}
    failures = [
        f"Feature.{name} is neither borrowed nor declared as the borrower's own"
        for name in sorted(declared - BORROWED - set(NOT_BORROWED))
    ]
    failures += [
        f"{name!r} is classified here and is not a field of Feature"
        for name in sorted((BORROWED | set(NOT_BORROWED)) - declared)
    ]
    return _report(
        "every Feature field is borrowed or the borrower's own",
        failures,
        len(declared),
    )


def check_borrowed_vocabulary(ipa: IPAFeatures) -> bool:
    """A feature that borrows a value set is not a second copy of it.

    ``constriction-location`` declares ``vocabulary="place"``: a nucleus
    constricts at one of the places ``place`` already locates, and where
    ``velar`` is must be stated once. This is the same hazard the
    secondary-articulation set was -- three copies of one set in three
    modules, agreeing by habit until one drifted and ``l`` and ``ɫ`` came
    out identical -- reached before there are copies to drift.

    Read off the document as well as off the load, because the two say
    different things. The document says the borrower spells no ``<value>``
    of its own, which is what stops a value being added on one side only.
    The load says the tables came out equal, which is what the readers
    actually see. A check on either alone passes a file where the
    borrowing silently did not happen.

    Cross-references are the acknowledged gap in the grammars
    (``ipa.rng``), so the resolution is checked here: ``vocabulary`` must
    name a feature, and name one declared *earlier*, since the loader
    copies as it goes and a forward reference would quietly load a feature
    with no values at all.
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(ipa.xml_path).getroot()
    features = root.find("features")
    elems = list(features.findall("feature")) if features is not None else []
    declared_before: set[str] = set()
    failures: list[str] = []
    checked = 0
    for elem in elems:
        name = elem.get("name")
        if not name:
            continue
        source_name = elem.get("vocabulary")
        if source_name is None:
            declared_before.add(name)
            continue
        checked += 1
        if source_name not in declared_before:
            failures.append(
                f"{name} borrows {source_name!r}, which is not a feature "
                "declared before it"
            )
            declared_before.add(name)
            continue
        if own := [v.get("name") for v in elem.findall("value")]:
            failures.append(
                f"{name} borrows {source_name!r} and also spells {own}; the "
                "loader drops one of the two and nothing says which"
            )
        if elem.get("type") in ipa.types:
            failures.append(
                f"{name} borrows {source_name!r} and is typed "
                f"{elem.get('type')!r}, which is a second value set"
            )
        feature, source = ipa.features[name], ipa.features[source_name]
        for attr in sorted(BORROWED):
            if getattr(feature, attr) != getattr(source, attr):
                failures.append(
                    f"{name}.{attr} is not {source_name}.{attr}; the two are "
                    "two declarations of one thing and will drift"
                )
        declared_before.add(name)
    if not checked:
        failures.append("no feature borrows a vocabulary; this check is vacuous")
    return _report("a borrowed vocabulary is one declaration", failures, checked)


def check_no_symbol_states_an_inapplicable_feature(ipa: IPAFeatures) -> bool:
    """A symbol does not declare a feature its own class is outside.

    ``applies`` says which hosts a feature is expected on -- ``channel``
    and ``retroflex`` on consonants, ``rhotacized`` and
    ``constriction-location`` on nuclei -- and a value stated outside that
    class is read by nothing that routes on it while still sitting in the
    bundle, where the metric compares it and ``to_phone`` matches on it.
    Nothing refused one: the grammars state structure and never
    vocabulary, so a symbol element takes any attribute at all, and the
    loader keeps it.

    Reached from ``constriction-location``, where the mistake is easy and
    silent: vowels state one, the attribute is spelled the same on
    every symbol element, and a consonant given one would take no branch
    that reads it and draw no complaint from anything.
    """
    failures: list[str] = []
    checked = 0
    for symbol in ipa.phones:
        bundle = ipa.get_features(symbol)
        for name, value in ipa.get_features(symbol, with_defaults=False).items():
            if name not in ipa.features:
                continue
            checked += 1
            if not ipa.feature_applies(name, bundle):
                failures.append(
                    f"{symbol} states {name}={value!r}, which `applies` puts "
                    "outside its class: nothing reads it and everything "
                    "compares it"
                )
    return _report(
        "no symbol states a feature outside its own class", failures, checked
    )


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
        check_classes_are_total(ipa),
        check_contour_marks(ipa),
        check_projection_coherence(ipa, args.quick),
        check_head_arcs(ipa),
        check_typed_values_declare_no_geometry(ipa),
        check_borrowed_vocabulary_is_total(ipa),
        check_borrowed_vocabulary(ipa),
        check_no_symbol_states_an_inapplicable_feature(ipa),
        check_fusion_arity(ipa),
        check_derived_artifacts(),
    ]
    ok = all(results)
    print("\n" + ("all invariants hold" if ok else "INVARIANTS VIOLATED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
