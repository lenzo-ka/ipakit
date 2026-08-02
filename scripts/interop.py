#!/usr/bin/env python3
"""Measure ipakit against the transcription ecosystem: CLTS/BIPA and PanPhon.

Every number in docs/design/interop.md comes from a subcommand here. The
point of writing them once, in the shape scripts/sweep.py and
scripts/articulatory.py already use, is that a design document is prose and
nothing checks prose -- so a claim that carries an argument has to be
re-runnable by whoever doubts it.

    python scripts/interop.py segmentation   # where the two tokenizers agree
    python scripts/interop.py ties           # what BIPA does to a tie bar
    python scripts/interop.py features       # where they describe a sound differently
    python scripts/interop.py similarity     # CLTS jaccard against ipakit distance
    python scripts/interop.py classes        # are SCA/DOLGO/ASJP natural classes?
    python scripts/interop.py generate       # description -> grapheme, both ways
    python scripts/interop.py phonemap       # would a BIPA map fit xsampa.xml's shape?
    python scripts/interop.py all

CLTS is external data under its own license and is NOT bundled: CI will not
have it, so every subcommand exits 0 with a message when it is absent. Clone
<https://github.com/cldf-clts/clts> and point --clts at it, or set
IPAKIT_CLTS_DIR. `pyclts` is a dev dependency (pip install -e ".[interop]")
and is imported by this script only -- never by the library.

Each subcommand asserts the shape of what it read, so a run over a truncated
or wrongly-pathed copy fails loudly instead of reporting a clean, empty
result. See docs/reviewing.md for why, and docs/design/interop.md for what
the numbers turned out to be and what they do and do not ground.
"""

from __future__ import annotations

import argparse
import collections
import csv
import itertools
import os
import statistics
import sys
import unicodedata
import warnings
from pathlib import Path
from typing import Any

# Make the package importable when run from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit import (  # noqa: E402
    add_ties,
    distance,
    features,
    from_cmu,
    load_ipa_features,
    natural_class,
    normalize_lookalikes,
    phones_matching,
    segment_distance,
    segments,
    to_cmu,
    to_phone,
)

#: Environment variable naming a clone of cldf-clts/clts. No default path is
#: baked in: the repository is a separate 54 MB checkout under its own
#: license, and a path from one machine is noise in this one.
CLTS_ENV = "IPAKIT_CLTS_DIR"

#: BIPA's own sound table, which is what "BIPA's segment set" means here: the
#: graphemes CLTS ships as resolved sounds, generated and explicit alike.
#: `pkg/transcriptionsystems/bipa/*.tsv` is the source those are built from
#: and `data/graphemes.tsv` is every spelling any source dataset used, which
#: is a different and much noisier question.
SOUNDS_TSV = ("data", "sounds.tsv")
FEATURES_TSV = ("data", "features.tsv")

#: A floor, not an expected value: CLTS grows. Below this the clone is
#: truncated or the path is wrong, and every count downstream is meaningless.
MIN_SOUNDS = 8000
MIN_FEATURE_VALUES = 150


# ---------------------------------------------------------------------------
# The two normalizations, named once
# ---------------------------------------------------------------------------
def house(grapheme: str) -> str:
    """BIPA spelling read as house style.

    Two steps, both already in the library and neither invented here:
    `normalize_lookalikes` for the keyboard characters BIPA canonicalizes the
    other way (its `g` is ipakit's `ɡ`), and `add_ties` because BIPA strips
    both tie bars and ipakit requires one to read a unit as a single segment.
    Measuring without these measures the spelling conventions; measuring with
    them measures the models.
    """
    return add_ties(normalize_lookalikes(grapheme))


def bucket(grapheme: str) -> tuple[str, int]:
    """Bucket one grapheme: does ipakit read it as CLTS reads it?

    `agree` -- exactly one ipakit segment, as CLTS says one sound.
    `differ` -- ipakit reads two or more where CLTS reads one.
    `refuse` -- ipakit will not read it at all.

    The three are exhaustive by construction, so a segment cannot fall out of
    the count silently.
    """
    try:
        segs = segments(grapheme, strict=True)
    except (ValueError, KeyError):
        return "refuse", 0
    return ("agree" if len(segs) == 1 else "differ"), len(segs)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
class Clts:
    """The CLTS clone, with the shape of what was read asserted."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sounds = _read_tsv(root.joinpath(*SOUNDS_TSV))
        self.feature_values = _read_tsv(root.joinpath(*FEATURES_TSV))
        assert len(self.sounds) >= MIN_SOUNDS, (
            f"read {len(self.sounds)} sounds from {root}, expected at least "
            f"{MIN_SOUNDS}: the clone is truncated or --clts points elsewhere"
        )
        assert len(self.feature_values) >= MIN_FEATURE_VALUES, (
            f"read {len(self.feature_values)} feature values from {root}, "
            f"expected at least {MIN_FEATURE_VALUES}"
        )

    def bipa(self) -> Any:
        """The live BIPA transcription system, or exit with guidance."""
        try:
            from pyclts import CLTS
        except ImportError:
            sys.exit(
                "pyclts is required (dev dependency). Install with:\n"
                '    pip install -e ".[interop]"'
            )
        return CLTS(self.root).bipa

    def api(self) -> Any:
        from pyclts import CLTS

        return CLTS(self.root)

    def segmental(self) -> list[dict[str, str]]:
        """Consonants and vowels: the sounds both systems claim to describe.

        Tones are excluded because BIPA spells them as Chao digits and ipakit
        as tone bars, which is a notation difference measured in
        `segmentation` rather than a disagreement about a sound. Diphthongs
        and clusters are excluded because whether they are one segment is
        exactly what `segmentation` is measuring, so counting them here would
        report the same finding twice under a different name.
        """
        return [r for r in self.sounds if r["TYPE"] in ("consonant", "vowel")]

    def value_of(self) -> dict[str, str]:
        """Feature id -> the value it states, from CLTS's own features table.

        A sound's FEATURES column holds ids like
        `consonant_tongue_root_advanced-tongue-root`, and two of CLTS's
        feature names contain an underscore themselves -- so splitting the id
        recovers the wrong value for exactly those. Reading the mapping off
        the table that declares it cannot drift the way a split can.
        """
        return {r["ID"]: r["VALUE"] for r in self.feature_values}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def open_clts(args: argparse.Namespace) -> Clts | None:
    """The CLTS clone, or None with a message when it is not there."""
    if not args.clts:
        print(
            f"CLTS not mounted: pass --clts or set {CLTS_ENV}.\n"
            "    git clone --depth 1 https://github.com/cldf-clts/clts"
        )
        return None
    root = Path(args.clts).expanduser()
    if not root.joinpath(*SOUNDS_TSV).exists():
        print(f"CLTS not mounted: {root} has no {'/'.join(SOUNDS_TSV)}.")
        return None
    return Clts(root)


# ---------------------------------------------------------------------------
# The correspondence between two vocabularies
# ---------------------------------------------------------------------------
# CLTS names a sound with a bag of feature values; so does ipakit. The two
# vocabularies overlap by about a quarter, so most of this table is
# translation rather than identity, and it is curated for the same reason
# xsampa_table.OVERRIDES is: no rule derives one project's word for a thing
# from another project's word for it.
#
# What is NOT curated is either side's *values*. Every ipakit target below is
# checked against the declarations at load, so a rename in ipa.xml breaks this
# table loudly rather than quietly scoring every segment as a disagreement.
#
# `None` means ipakit declares nothing that says this. That is a finding, not
# an omission, and `features` counts those separately from disagreements.
# A CLTS value in neither this table nor UNCOMPARED is an error: without that
# check, a value CLTS adds later drops out of the comparison silently and the
# agreement rate goes up for the wrong reason.
CORRESPONDENCE: dict[str, tuple[str, str] | None] = {
    # phonation
    "voiced": ("voiced", "+"),
    "voiceless": ("voiced", "-"),
    "devoiced": ("phonation", "devoiced"),
    "breathy": ("phonation", "breathy"),
    "creaky": ("phonation", "creaky"),
    "unspecified-voice": None,
    "revoiced": None,
    # manner
    "stop": ("manner", "plosive"),
    "affricate": ("manner", "affricate"),
    "fricative": ("manner", "fricative"),
    "nasal": ("manner", "nasal"),
    "trill": ("manner", "trill"),
    "tap": ("manner", "tap"),
    "approximant": ("manner", "approximant"),
    "vowel": ("manner", "vowel"),
    "implosive": ("airstream", "implosive"),
    "click": ("airstream", "velaric"),
    "nasal-click": ("airstream", "velaric"),
    "ejective": ("airstream", "ejective"),
    "unspecified-manner": None,
    # place
    "bilabial": ("place", "bilabial"),
    "labial": ("place", "bilabial"),
    "labio-dental": ("place", "labiodental"),
    "dental": ("place", "dental"),
    "alveolar": ("place", "alveolar"),
    "post-alveolar": ("place", "postalveolar"),
    "alveolo-palatal": ("place", "alveolo-palatal"),
    "palatal": ("place", "palatal"),
    "velar": ("place", "velar"),
    "uvular": ("place", "uvular"),
    "pharyngeal": ("place", "pharyngeal"),
    "epiglottal": ("place", "epiglottal"),
    "glottal": ("place", "glottal"),
    "retroflex": ("retroflex", "+"),
    "labio-velar": ("place", "bilabial^velar"),
    "labio-palatal": ("place", "bilabial^palatal"),
    # co-articulated places ipakit spells with `^`, in the one order it
    # declares; CLTS spells both orders and ipakit declares neither of these.
    "linguolabial": None,
    "palatal-velar": None,
    "unspecified-place": None,
    "alveolar-and-bilabial": None,
    "alveolar-and-velar": None,
    "bilabial-and-alveolar": None,
    "bilabial-and-velar": None,
    "velar-and-alveolar": None,
    "velar-and-bilabial": None,
    "velar-and-uvular": None,
    # vowel quality
    "close": ("height", "close"),
    "near-close": ("height", "near-close"),
    "close-mid": ("height", "close-mid"),
    "mid": ("height", "mid"),
    "open-mid": ("height", "open-mid"),
    "near-open": ("height", "near-open"),
    "open": ("height", "open"),
    "front": ("backness", "front"),
    "near-front": ("backness", "near-front"),
    "central": ("backness", "central"),
    "near-back": ("backness", "near-back"),
    "back": ("backness", "back"),
    "rounded": ("rounded", "+"),
    "unrounded": ("rounded", "-"),
    "less-rounded": ("rounding", "less"),
    "more-rounded": ("rounding", "more"),
    # CLTS calls this `airstream`; ipakit's `airstream` is the initiator and
    # this is its `channel`. The one outright name collision between the two
    # feature systems, and it is worth stating rather than silently resolving.
    "lateral": ("channel", "lateral"),
    "sibilant": ("channel", "grooved"),
    "whistled-sibilant": None,
    # secondary articulation
    "aspirated": ("release", "aspirated"),
    "labialized": ("labialized", "+"),
    "palatalized": ("palatalized", "+"),
    "labio-palatalized": ("labio-palatized", "+"),
    "velarized": ("velarized", "+"),
    "pharyngealized": ("pharyngealized", "+"),
    "nasalized": ("nasalized", "+"),
    "rhotacized": ("rhotacized", "+"),
    "syllabic": ("syllabic", "+"),
    "non-syllabic": ("syllabic", "-"),
    "glottalized": ("release", "glottal"),
    "advanced-tongue-root": ("tongue-root", "+"),
    "retracted-tongue-root": ("tongue-root", "-"),
    "centralized": ("centralized", "+"),
    "mid-centralized": ("mid-centralized", "+"),
    "advanced": ("fronting", "+"),
    "retracted": ("fronting", "-"),
    "raised": ("height-mod", "+"),
    "lowered": ("height-mod", "-"),
    # duration and prominence
    "long": ("length", "long"),
    "mid-long": ("length", "half-long"),
    "ultra-short": ("length", "extra-short"),
    "ultra-long": None,
    "primary-stress": ("stress", "primary"),
    "secondary-stress": ("stress", "secondary"),
    # release
    "unreleased": ("release", "no-audible"),
    "with-lateral-release": ("release", "lateral"),
    "with-nasal-release": ("release", "nasal"),
    "with-mid-central-vowel-release": ("release", "schwa"),
    "with-uvular-release": None,
    "with-sibilant-release": None,
    "with-trilled-release": None,
    # articulatory detail ipakit declares nothing for
    "with-friction": None,
    "strong": None,
    "weak": None,
    "apical": None,
    "laminal": None,
    # CLTS records a modifier that PRECEDES the base as a feature of the base;
    # ipakit has no pre-modifier position at all, which `segmentation`
    # measures directly.
    "pre-aspirated": None,
    "pre-breathy-aspirated": None,
    "pre-glottalized": None,
    "pre-labialized": None,
    "pre-nasalized": None,
    "pre-palatalized": None,
    "pre-glottalized-and-nasalized": None,
}

#: CLTS values deliberately outside the comparison, with the reason. Tone is
#: a tier both systems model and neither spells the other's way, so comparing
#: the vocabularies would measure the notation; `segmentation` reports what
#: happens to a BIPA tone grapheme, which is the answer that matters.
UNCOMPARED_PREFIXES = ("from-", "to-", "via-", "with-")
UNCOMPARED = frozenset({"neutral", "contour", "falling", "flat", "rising", "short"})


def check_correspondence(clts: Clts) -> list[str]:
    """Every CLTS value is accounted for, and every ipakit target is declared.

    Two directions, both of which have to hold for a rate to mean anything:
    an unlisted CLTS value would be dropped from the comparison and inflate
    agreement, and an ipakit target that no longer exists would score every
    segment carrying it as a disagreement.
    """
    ipa = load_ipa_features()
    problems = []
    for row in clts.feature_values:
        value = row["VALUE"]
        if value in UNCOMPARED or value.startswith(UNCOMPARED_PREFIXES):
            continue
        if value not in CORRESPONDENCE:
            problems.append(
                f"CLTS declares {value!r} ({row['TYPE']} {row['FEATURE']}) and "
                "CORRESPONDENCE does not name it: add a target if ipakit "
                "declares one, None if it does not, or UNCOMPARED with a "
                "reason. Leaving it out drops it from the comparison silently."
            )
    for value, target in CORRESPONDENCE.items():
        if target is None:
            continue
        name, val = target
        feature = ipa.features.get(name)
        if feature is None:
            problems.append(f"{value!r} -> undeclared ipakit feature {name!r}")
        elif val not in feature.values:
            problems.append(
                f"{value!r} -> {name}={val!r}, which {name} does not declare "
                f"(it declares {feature.values})"
            )
    return problems


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
def cmd_segmentation(clts: Clts, args: argparse.Namespace) -> int:
    """Do the two systems agree about where a segment begins?

    Nothing downstream matters if they do not, so this is measured first and
    at three levels: BIPA's spelling as it ships, then under each of the two
    normalizations ipakit already has for reading foreign conventions.
    """
    stages = (
        ("raw BIPA spelling", lambda s: s),
        ("+ normalize_lookalikes", normalize_lookalikes),
        ("+ add_ties (both)", house),
    )
    print(f"BIPA sounds: {len(clts.sounds)}\n")
    print(f"{'':24s} {'agree':>7s} {'differ':>7s} {'refuse':>7s}")
    last: dict[str, list[dict[str, str]]] = {}
    for label, norm in stages:
        got: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
        for row in clts.sounds:
            got[bucket(norm(row["GRAPHEME"]))[0]].append(row)
        print(
            f"{label:24s} {len(got['agree']):7d} {len(got['differ']):7d} "
            f"{len(got['refuse']):7d}"
        )
        last = got
    total = sum(len(v) for v in last.values())
    assert total == len(clts.sounds), "a sound fell out of the buckets"

    print("\nunder both normalizations, by CLTS type:")
    by_type: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for name, rows in last.items():
        for row in rows:
            by_type[row["TYPE"]][name] += 1
    for kind in sorted(by_type, key=lambda k: -sum(by_type[k].values())):
        counts = by_type[kind]
        print(
            f"  {kind:11s} agree {counts['agree']:5d}  differ {counts['differ']:4d}"
            f"  refuse {counts['refuse']:4d}"
        )

    print("\nrefusals, by the symbol ipakit does not know:")
    for symbol, n in _refusal_classes(last["refuse"]).most_common(args.top):
        print(f"  {n:5d}  {symbol}")

    print("\nresegmentations (CLTS one sound, ipakit more than one):")
    for kind, n in collections.Counter(r["TYPE"] for r in last["differ"]).most_common():
        sample = [r["GRAPHEME"] for r in last["differ"] if r["TYPE"] == kind][:6]
        print(f"  {n:5d}  {kind:11s} e.g. {' '.join(sample)}")
    return 0


def _refusal_classes(rows: list[dict[str, str]]) -> collections.Counter[str]:
    """Name each refusal by the symbols ipakit does not have.

    Counted per unknown *symbol* rather than per refused sound, so a sound
    missing two of them appears under both. That is what turns a long tail
    into a short list of classes -- 132 refusals is a verdict, but "132
    refusals spelled with five Chao tone digits" is one decision -- and the
    column therefore sums to more than the refusal count, deliberately.
    """
    counts: collections.Counter[str] = collections.Counter()
    ipa = load_ipa_features()
    known = {
        c
        for g in (set(ipa.phones) | set(ipa.diacritics) | set(ipa.tie_bars))
        for c in unicodedata.normalize("NFD", g)
    }
    for row in rows:
        unknown = sorted(
            set(unicodedata.normalize("NFD", house(row["GRAPHEME"]))) - known
        )
        if not unknown:
            counts["(every symbol known; refused for structure)"] += 1
            continue
        for symbol in unknown:
            counts[
                f"{symbol!r} U+{ord(symbol):04X} {unicodedata.name(symbol, '?')}"
            ] += 1
    return counts


def cmd_ties(clts: Clts, args: argparse.Namespace) -> int:
    """What each system does with a tie bar.

    ipakit reads the tie as structure: `t͡s` is one segment and `ts` is two.
    Whether that survives a round trip through BIPA decides whether a BIPA
    map can be a map at all, and it decides what happens to a tokenization
    handed to anything downstream that counts segments.
    """
    bipa = clts.bipa()
    probes = ("ts", "t͡s", "t͜s", "kp", "k͡p", "k͜p", "aɪ", "a͡ɪ", "a͜ɪ")
    print(f"{'string':8s} {'codepoints':22s} {'BIPA reads':10s} {'ipakit reads'}")
    for probe in probes:
        sound = bipa[probe]
        try:
            segs = segments(probe, strict=True)
            read = f"{len(segs)} segment(s) {[s.to_ipa() for s in segs]}"
        except (ValueError, KeyError):
            read = "refused"
        points = " ".join(f"{ord(c):04X}" for c in probe)
        print(f"{probe:8s} {points:22s} {str(sound):10s} {read}")

    tied = [
        r for r in clts.sounds if set(r["GRAPHEME"]) & set(load_ipa_features().tie_bars)
    ]
    print(
        f"\nBIPA graphemes containing either tie bar: {len(tied)} of {len(clts.sounds)}"
    )
    print(
        "  both tie bars normalize to the empty string:"
        f"  U+0361 -> {bipa._normalize.get(chr(0x361), '<absent>')!r}"
        f"  U+035C -> {bipa._normalize.get(chr(0x35C), '<absent>')!r}"
    )
    # segment_distance, not distance: the untied member of each pair is two
    # units, which is the whole point, and `distance` refuses those by design.
    for a, b in (("ts", "t͡s"), ("t͡s", "t͜s"), ("aɪ", "a͜ɪ")):
        print(
            f"  BIPA {a!r} and {b!r} same sound: {bipa[a].name == bipa[b].name}"
            f"   ipakit segment_distance = {segment_distance(a, b):.4f}"
        )

    affricates = sum("affricate" in r["FEATURES"] for r in clts.sounds)
    diphthongs = sum(r["TYPE"] == "diphthong" for r in clts.sounds)
    clusters = sum(r["TYPE"] == "cluster" for r in clts.sounds)
    print(
        f"\nBIPA sounds ipakit reads as more than one segment without add_ties:"
        f" {affricates} affricates + {diphthongs} diphthongs + {clusters} clusters"
    )
    return 0


def cmd_features(clts: Clts, args: argparse.Namespace) -> int:
    """Where the two systems say different things about the same sound."""
    problems = check_correspondence(clts)
    if problems:
        for problem in problems:
            print(f"  {problem}")
        return 1

    ipa = load_ipa_features()
    value_of = clts.value_of()
    agree: collections.Counter[str] = collections.Counter()
    differ: collections.Counter[str] = collections.Counter()
    silent: collections.Counter[str] = collections.Counter()
    absent: collections.Counter[str] = collections.Counter()
    cases: dict[str, list[tuple[str, str, str]]] = collections.defaultdict(list)
    compared = 0

    for row in clts.segmental():
        grapheme = house(row["GRAPHEME"])
        if bucket(grapheme)[0] != "agree":
            continue
        # compose_segments, not features(): it is the read that resolves a
        # prosodic mark onto the unit, and length is a feature CLTS states.
        composed = ipa.compose_segments(grapheme)
        if not composed:
            continue
        got = composed[0][1]
        compared += 1
        for stated in row["FEATURES"].split():
            value = value_of.get(stated, stated)
            if value in UNCOMPARED or value.startswith(UNCOMPARED_PREFIXES):
                continue
            target = CORRESPONDENCE[value]
            if target is None:
                absent[value] += 1
                continue
            name, want = target
            mine = got.get(name)
            if mine == want:
                agree[value] += 1
            elif mine is None:
                silent[value] += 1
            else:
                differ[value] += 1
                if len(cases[value]) < args.top:
                    cases[value].append((row["GRAPHEME"], want, mine))

    assert compared > 5000, f"only {compared} segments compared; the sweep went vacuous"
    stated = sum(agree.values()) + sum(differ.values()) + sum(silent.values())
    print(f"segments both systems read as one: {compared}")
    print(
        f"CLTS assertions ipakit can express: {stated}"
        f"   agree {sum(agree.values())}"
        f"   differ {sum(differ.values())}"
        f"   ipakit silent {sum(silent.values())}"
    )
    print(f"CLTS assertions ipakit declares nothing for: {sum(absent.values())}")

    print("\ndisagreements, worst first:")
    for value, n in differ.most_common(args.top):
        name = CORRESPONDENCE[value][0]  # type: ignore[index]
        shown = "  ".join(f"{g} ipakit {name}={m}" for g, _, m in cases[value][:3])
        print(f"  {n:5d}  CLTS {value:22s} {shown}")

    print("\nCLTS says it, ipakit declares nothing that could:")
    for value, n in absent.most_common(args.top):
        print(f"  {n:5d}  {value}")
    return 0


def cmd_similarity(clts: Clts, args: argparse.Namespace) -> int:
    """CLTS has a similarity. Is it a metric?

    `Sound.similarity` is an unweighted Jaccard over the set of feature-value
    *names*, so two sounds are as similar as the words they share. The
    question worth measuring is not whether CLTS has one -- it does -- but
    whether it resolves an inventory finely enough to rank it.
    """
    bipa = clts.bipa()
    ipa = load_ipa_features()
    shared = []
    for phone in ipa.phones:
        sound = bipa[phone]
        if type(sound).__name__ in ("UnknownSound", "Marker"):
            continue
        shared.append((phone, sound))
    assert len(shared) > 100, f"only {len(shared)} shared phones; check the clone"

    pairs = list(itertools.combinations(shared, 2))
    mine = [distance(a, b) for (a, _), (b, _) in pairs]
    theirs = [1.0 - x.similarity(y) for (_, x), (_, y) in pairs]
    print(f"registered ipakit phones BIPA also resolves: {len(shared)}")
    print(f"pairs: {len(pairs)}")
    print(f"  distinct ipakit distances:      {len(set(mine)):6d}")
    print(f"  distinct CLTS similarities:     {len(set(theirs)):6d}")
    print(f"  Spearman rho:                   {_spearman(mine, theirs):6.4f}")

    agreed = 0
    for phone, sound in shared:
        nearest_mine = min(
            ((p, distance(phone, p)) for p, _ in shared if p != phone),
            key=lambda t: t[1],
        )[0]
        nearest_theirs = max(
            ((p, sound.similarity(s)) for p, s in shared if p != phone),
            key=lambda t: t[1],
        )[0]
        agreed += nearest_mine == nearest_theirs
    print(f"  nearest neighbor agrees on:     {agreed:6d} of {len(shared)}")

    ranks_mine, ranks_theirs = _ranks(mine), _ranks(theirs)
    worst = sorted(
        range(len(pairs)),
        key=lambda i: abs(ranks_mine[i] - ranks_theirs[i]),
        reverse=True,
    )
    print("\nlargest rank disagreements:")
    for i in worst[: args.top]:
        (a, _), (b, _) = pairs[i]
        print(
            f"  {a:4s} {b:4s}  ipakit {mine[i]:.4f} (rank {ranks_mine[i]:5d})"
            f"   CLTS {theirs[i]:.4f} (rank {ranks_theirs[i]:5d})"
        )
    return 0


def _ranks(values: list[float]) -> list[int]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    for position, index in enumerate(order):
        ranks[index] = position
    return ranks


def _spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def cmd_classes(clts: Clts, args: argparse.Namespace) -> int:
    """Are CLTS's sound classes natural classes in ipakit's sense?

    The house rule is that a shipped table is derived from the declarations.
    So the question is not whether the classes are useful -- they are, they
    are what cognate detection runs on -- but whether ipakit could compute
    them. A class is derivable here if the features its members share
    re-extend to exactly its members and no others.
    """
    api = clts.api()
    ipa = load_ipa_features()
    phones = [p for p in ipa.phones]
    for system in ("sca", "dolgo", "asjp", "cv"):
        classes: dict[str, list[str]] = collections.defaultdict(list)
        for phone in phones:
            try:
                classes[api.soundclass(system)[phone]].append(phone)
            except (KeyError, ValueError):
                classes["<unresolved>"].append(phone)
        exact = 0
        checked = 0
        for name, members in sorted(classes.items()):
            if name == "<unresolved>" or len(members) < 2:
                continue
            checked += 1
            shared = natural_class(members)
            extension = set(phones_matching(shared))
            exact += extension == set(members)
            if args.verbose:
                print(
                    f"    {name:3s} n={len(members):3d} extension={len(extension):3d}"
                    f" exact={extension == set(members)}"
                )
        print(
            f"{system:6s} {len(classes):3d} classes over {len(phones)} phones;"
            f" derivable from ipakit's declarations: {exact} of {checked}"
        )
    return 0


def cmd_generate(clts: Clts, args: argparse.Namespace) -> int:
    """Description -> grapheme, in both systems.

    This is the most direct comparison of the two models: both claim to
    generate a spelling from a description rather than look it up, so both
    can be asked to round-trip their own inventory.
    """
    bipa = clts.bipa()
    ipa = load_ipa_features()
    exact = wrong = none = 0
    cases = []
    for phone in ipa.phones:
        got = to_phone(features(phone))
        if got == phone:
            exact += 1
        elif got is None:
            none += 1
        else:
            wrong += 1
            cases.append((phone, got))
    print(
        f"ipakit to_phone(features(p)) over {len(ipa.phones)} registered phones:"
        f" exact {exact}  wrong {wrong}  None {none}"
    )
    for phone, got in cases[: args.top]:
        print(f"    {phone!r} -> {got!r}")

    exact = wrong = failed = 0
    for row in clts.sounds:
        try:
            got = str(bipa[row["NAME"]])
        except (KeyError, ValueError):
            failed += 1
            continue
        if got == row["GRAPHEME"]:
            exact += 1
        else:
            wrong += 1
    print(
        f"CLTS bipa[name] over {len(clts.sounds)} sounds:"
        f" exact {exact}  wrong {wrong}  failed {failed}"
    )
    return 0


def cmd_phonemap(clts: Clts, args: argparse.Namespace) -> int:
    """Would a BIPA map fit the shape data/phonemaps/xsampa.xml has?

    A phonemap is a flat, bijective table between one IPA spelling and one
    foreign spelling. So the question is whether the BIPA relation is one,
    and the answer is a count of the places it is not.
    """
    forward: dict[str, set[str]] = collections.defaultdict(set)
    same = differs = 0
    for row in clts.sounds:
        grapheme = row["GRAPHEME"]
        try:
            segs = segments(house(grapheme), strict=True)
        except (ValueError, KeyError):
            continue
        if len(segs) != 1:
            continue
        spelling = segs[0].to_ipa()
        forward[spelling].add(grapheme)
        if spelling == grapheme:
            same += 1
        else:
            differs += 1
    collisions = {k: v for k, v in forward.items() if len(v) > 1}
    print(f"BIPA sounds ipakit reads as one segment: {same + differs}")
    print(f"  spelled identically:  {same}")
    print(f"  spelled differently:  {differs}   (rows a lexical table would need)")
    print(
        f"  ipakit spellings claimed by more than one BIPA grapheme: "
        f"{len(collisions)}   (each breaks the bijection)"
    )
    for spelling, graphemes in sorted(collisions.items())[: args.top]:
        print(f"    {spelling!r} <- {sorted(graphemes)}")
    return 0


# ---------------------------------------------------------------------------
# PanPhon: 24 fixed ternary features against ipakit's declared attributes
# ---------------------------------------------------------------------------
#: PanPhon's features, in `ipa_all.csv`'s own column order. Asserted against
#: the file's header before anything runs: the order is not documentation, it
#: is the vector layout, and building against a remembered order silently
#: transposes two features into what looks like a model disagreement.
PANPHON_FEATURES: tuple[str, ...] = (
    "syl", "son", "cons", "cont", "delrel", "lat", "nas", "strid", "voi",
    "sg", "cg", "ant", "cor", "distr", "lab", "hi", "lo", "back", "round",
    "velaric", "tense", "long", "hitone", "hireg",
)  # fmt: skip

#: PanPhon features no ipakit declaration can reach at the segment level.
#: Both are tone, which ipakit carries as prosody rather than in the bundle;
#: PanPhon itself states them only on bare tone letters, which ipakit reads as
#: no segment at all. Emitted as `0` and reported apart, so the pair cannot
#: inflate an agreement rate by agreeing vacuously.
UNDERIVABLE = {
    "hitone": "ipakit tone is prosody; it does not enter the feature bundle",
    "hireg": "ipakit tone is prosody; it does not enter the feature bundle",
}


def panphon_rows() -> list[dict[str, str]]:
    """PanPhon's own segment table, with its header checked."""
    try:
        import panphon
    except ImportError:
        sys.exit(
            "panphon is required (dev dependency). Install with:\n"
            '    pip install -e ".[interop]"'
        )
    path = Path(panphon.__file__).parent / "data" / "ipa_all.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    header = tuple(k for k in rows[0] if k != "ipa")
    if header != PANPHON_FEATURES:
        raise ValueError(
            f"ipa_all.csv declares {header!r}, not the feature set this "
            "mapping was written against. Re-derive the mapping rather than "
            "applying it to a different vector layout."
        )
    return rows


class Declared:
    """The pieces of ipa.xml the PanPhon mapping reads, resolved once.

    Nothing here keys on a symbol. Every quantity is a declaration -- a
    place's `arc`, a manner's `offset` and `natural-class`, the organ a place
    names, the place a secondary feature names -- so adding a phone or a place
    to ipa.xml moves the emitted table with nobody editing this file.
    """

    def __init__(self, ipa: Any) -> None:
        place, manner = ipa.features["place"], ipa.features["manner"]
        self.combiner = place.COMBINER
        self.arc = {v: c["arc"] for v, c in place.coordinates.items() if "arc" in c}
        self.articulator = dict(place.articulators)
        self.obstruent = manner.value_classes["obstruent"]
        self.stricture = {
            v: c["offset"] for v, c in manner.coordinates.items() if "offset" in c
        }
        self.height = {
            v: c["offset"] for v, c in ipa.features["height"].coordinates.items()
        }
        self.backness = {
            v: c["arc"] for v, c in ipa.features["backness"].coordinates.items()
        }
        self.secondary = {n: f.place for n, f in ipa.features.items() if f.place}
        self.a_alveolar = self.arc["alveolar"]
        self.a_alv_pal = self.arc["alveolo-palatal"]
        self.a_velar = self.arc["velar"]
        self.a_pharyngeal = self.arc["pharyngeal"]
        self.a_epiglottal = self.arc["epiglottal"]
        self.b_central = self.backness["central"]
        self.h_near_open = self.height["near-open"]
        self.h_open_mid = self.height["open-mid"]
        self.h_mid = self.height["mid"]
        self.h_near_close = self.height["near-close"]
        self._ipa = ipa
        # `length` is prosody in ipakit: it belongs to the unit, not to the
        # bundle, so PanPhon's [long] is read off the unit's marks. Reading it
        # off features() instead scores every long segment as a disagreement.
        self.length_marks = {
            sym: d.features["length"]
            for sym, d in ipa.diacritics.items()
            if "length" in getattr(d, "features", {})
        }

    def length_of(self, unit: str) -> str:
        for mark in self._ipa.segment(unit).prosody:
            if (val := self.length_marks.get(mark)) is not None:
                return val
        return self._ipa.features["length"].default

    def places(self, b: dict[str, str]) -> set[str]:
        """Every place the segment constricts at: primary, secondary, velaric."""
        out: set[str] = set()
        if primary := b.get("place"):
            out |= set(primary.split(self.combiner))
        for name, place in self.secondary.items():
            if b.get(name) == "+":
                out |= set(place.split(self.combiner))
        if b.get("airstream") == "velaric":
            out.add("velar")  # a click's rear closure, by definition
        return out

    def arcs(self, b: dict[str, str]) -> set[float]:
        return {self.arc[p] for p in self.places(b) if p in self.arc}

    def primary_arcs(self, b: dict[str, str]) -> set[float]:
        return {
            self.arc[p]
            for p in b.get("place", "").split(self.combiner)
            if p in self.arc
        }

    def articulators(self, b: dict[str, str]) -> set[str]:
        """The organs that move. A stated `articulator` overrides the default."""
        out = {self.articulator[p] for p in self.places(b) if p in self.articulator}
        if stated := b.get("articulator"):
            out = (out - set(self.articulator.values())) | {stated}
        return out


def emit(
    d: Declared, unit: str, b: dict[str, str], stated: dict[str, str]
) -> dict[str, str]:
    """PanPhon's features, computed from one ipakit bundle.

    `stated` is the same bundle without defaults, because a binary feature
    whose default is `-` cannot otherwise say whether the `-` was declared or
    fell through -- and `syllabic` is exactly that case.
    """

    def t(cond: bool) -> str:
        return "+" if cond else "-"

    manner = b.get("manner")
    if manner is None:
        raise ValueError(
            f"bundle states no manner, so no PanPhon feature follows from it: {b!r}"
        )
    if manner not in d.stricture and manner != "silence":
        raise ValueError(
            f"manner {manner!r} declares no constriction offset; the continuant "
            "rule reads that offset, so a new manner must declare one rather "
            "than fall through to a default"
        )
    vowel = manner == "vowel"
    obstruent = manner in d.obstruent
    arcs, arts = d.arcs(b), d.articulators(b)
    retroflex = b.get("retroflex") == "+"
    primary_arts = {
        d.articulator[p]
        for p in b.get("place", "").split(d.combiner)
        if p in d.articulator
    }
    # Nothing above the glottis is narrowed.
    laryngeal = bool(primary_arts) and primary_arts <= {"vocal-folds"}
    stricture = d.stricture.get(manner, 0.0)
    closed = stricture >= d.stricture["plosive"]
    height = d.height.get(b.get("height", ""))
    backness = d.backness.get(b.get("backness", ""))
    root = b.get("tongue-root", "0")
    coronal = bool(arts & {"tongue-tip", "tongue-blade"}) or retroflex

    if vowel:
        hi = t(height is not None and height >= d.h_near_close)
        lo = t(
            (height is not None and height <= d.h_near_open)
            or any(d.a_pharyngeal <= a <= d.a_epiglottal for a in arcs)
        )
        back = t(backness is not None and backness >= d.b_central)
    else:
        hi = t(any(d.a_alv_pal <= a <= d.a_velar for a in arcs))
        lo = t(any(d.a_pharyngeal <= a <= d.a_epiglottal for a in arcs))
        # The tongue *body* retracted. A pharyngeal is made by the root and an
        # epiglottal by the epiglottis, so neither retracts the body.
        back = t(
            laryngeal
            or any(
                d.articulator.get(p) == "tongue-dorsum" and d.arc[p] >= d.a_velar
                for p in d.places(b)
                if p in d.arc
            )
        )
    if root != "0":
        tense = root
    elif not vowel or height is None:
        tense = "0"
    else:
        tense = t(height not in (d.h_near_close, d.h_mid, d.h_open_mid))

    labial = "lower-lip" in primary_arts or (vowel and b.get("rounded") == "+")
    return {
        "syl": stated.get("syllabic", t(vowel)),
        "son": t(not obstruent or laryngeal),
        "cons": t(
            not (
                vowel
                or laryngeal
                or (
                    stricture <= d.stricture["approximant"]
                    and b.get("channel") != "lateral"
                )
            )
        ),
        "cont": t(not closed and manner != "affricate"),
        "delrel": t(manner == "affricate" or b.get("release") == "lateral"),
        "lat": t(b.get("channel") == "lateral" or b.get("release") == "lateral"),
        "nas": t(
            manner == "nasal"
            or b.get("nasalized") == "+"
            or b.get("release") == "nasal"
        ),
        # The labiodentals' noise comes from the lip/teeth edge, not a groove.
        "strid": t(
            obstruent
            and (b.get("channel") == "grooved" or b.get("place") == "labiodental")
        ),
        "voi": b.get("voiced", "-"),
        "sg": t(b.get("release") == "aspirated" or b.get("phonation") == "breathy"),
        "cg": t(
            b.get("airstream") in ("ejective", "implosive")
            or b.get("phonation") == "creaky"
            or b.get("release") == "glottal"
            or (laryngeal and closed)
        ),
        # [ant] and [distr] are coronal-only: PanPhon carries 0 wherever there
        # is no coronal constriction to place.
        "ant": (
            "0"
            if vowel
            else t(not retroflex and any(a <= d.a_alveolar for a in d.primary_arcs(b)))
        ),
        "cor": t(coronal),
        "distr": "0" if not coronal else t(not retroflex and "tongue-blade" in arts),
        "lab": t(labial),
        "hi": hi,
        "lo": lo,
        "back": back,
        "round": t(
            b.get("rounded") == "+"
            or b.get("labialized") == "+"
            or b.get("labio-palatized") == "+"
        ),
        "velaric": t(b.get("airstream") == "velaric"),
        "tense": tense,
        "long": t(d.length_of(unit) == "long"),
        "hitone": "0",
        "hireg": "0",
    }


def _panphon_overlap() -> tuple[list[str], dict[str, list[str]]]:
    """Split PanPhon's inventory into what ipakit reads and what it refuses."""
    accepted: list[str] = []
    refused: dict[str, list[str]] = collections.defaultdict(list)
    for row in panphon_rows():
        s = row["ipa"]
        try:
            segs = segments(s, strict=True)
        except (ValueError, KeyError) as exc:
            refused[f"raises {type(exc).__name__}"].append(s)
            continue
        if len(segs) != 1:
            refused[f"segments to {len(segs)} units"].append(s)
        elif not features(s):
            refused["one unit, but features() == {}"].append(s)
        else:
            accepted.append(s)
    return accepted, dict(refused)


def cmd_panphon(_: Clts | None, args: argparse.Namespace) -> int:
    """Emit PanPhon's features from ipakit's declarations, and measure the fit."""
    accepted, refused = _panphon_overlap()
    total = len(accepted) + sum(len(v) for v in refused.values())
    assert total > 5000, f"ipa_all.csv collapsed to {total} rows"
    print(f"ipa_all.csv rows: {total}")
    print(f"ipakit accepts:   {len(accepted)} ({len(accepted) / total:.1%})")
    for reason, syms in sorted(refused.items(), key=lambda kv: -len(kv[1])):
        print(f"  refused, {reason}: {len(syms)}   e.g. {' '.join(syms[:12])}")

    d = Declared(load_ipa_features())
    by_ipa = {r["ipa"]: r for r in panphon_rows()}
    ours = {
        s: emit(d, s, features(s), features(s, with_defaults=False)) for s in accepted
    }
    theirs = {s: {f: by_ipa[s][f] for f in PANPHON_FEATURES} for s in accepted}
    for s, row in ours.items():
        if bad := {f: v for f, v in row.items() if v not in ("+", "-", "0")}:
            raise ValueError(f"non-ternary value emitted for {s!r}: {bad!r}")

    n = len(accepted)
    per = {
        f: sum(ours[s][f] == theirs[s][f] for s in accepted) for f in PANPHON_FEATURES
    }
    live = [f for f in PANPHON_FEATURES if f not in UNDERIVABLE]
    print(
        f"\ncell agreement (all {len(PANPHON_FEATURES)}): "
        f"{sum(per.values())}/{n * len(PANPHON_FEATURES)} = "
        f"{sum(per.values()) / (n * len(PANPHON_FEATURES)):.3%}"
    )
    print(
        f"cell agreement ({len(live)} live): {sum(per[f] for f in live)}/{n * len(live)}"
        f" = {sum(per[f] for f in live) / (n * len(live)):.3%}"
    )
    perfect = sum(
        all(ours[s][f] == theirs[s][f] for f in PANPHON_FEATURES) for s in accepted
    )
    print(f"segments agreeing on every feature: {perfect} ({perfect / n:.2%})")

    kinds: collections.Counter[str] = collections.Counter()
    for s in accepted:
        for f in PANPHON_FEATURES:
            if ours[s][f] == theirs[s][f]:
                continue
            kinds[
                (
                    "PanPhon declines to state a value (0)"
                    if theirs[s][f] == "0"
                    else (
                        "ipakit has nothing to state (0)"
                        if ours[s][f] == "0"
                        else "polarity clash (+ vs -)"
                    )
                )
            ] += 1
    print("\ndisagreeing cells by kind:")
    for kind, c in kinds.most_common():
        print(f"  {kind:38s} {c:6d}  ({c / sum(kinds.values()):.1%})")

    print("\nper feature, worst first:")
    for f in sorted(PANPHON_FEATURES, key=lambda f: per[f])[: args.top]:
        note = f"   [vacuous: {UNDERIVABLE[f]}]" if f in UNDERIVABLE else ""
        print(f"  {f:8s} {per[f] / n:7.2%}  disagreeing: {n - per[f]:5d}{note}")

    print("\nPanPhon's own resolution over the overlap:")
    print(
        f"  distinct PanPhon vectors: {len({tuple(theirs[s][f] for f in PANPHON_FEATURES) for s in accepted})}"
        f"   for {n} segments"
    )
    return 0


def cmd_panphon_ties(_: Clts | None, args: argparse.Namespace) -> int:
    """Segment counts either side of a tie bar, ipakit against PanPhon."""
    try:
        import panphon
    except ImportError:
        sys.exit('panphon is required. pip install -e ".[interop]"')
    table = panphon.FeatureTable()
    probes = [
        (base, tie) for base in ("ts", "kp", "aɪ", "ʈʂ", "tʃ") for tie in ("", "͡", "͜")
    ]
    print(f"{'string':10s} {'tie':10s} {'ipakit':>7s} {'panphon':>8s}")
    disagreed = 0
    for base, tie in probes:
        s = base[0] + tie + base[1:]
        try:
            mine = len(segments(s, strict=True))
        except (ValueError, KeyError):
            mine = -1
        theirs = len(table.ipa_segs(s))
        disagreed += mine != theirs
        name = {"": "untied", "͡": "over-tie", "͜": "under-tie"}[tie]
        print(
            f"{s:10s} {name:10s} {mine:7d} {theirs:8d}{'   <-- disagree' if mine != theirs else ''}"
        )
    print(f"\nsegment-count disagreements: {disagreed} of {len(probes)}")
    rows = panphon_rows()
    for point, label in ((0x361, "over-tie"), (0x35C, "under-tie")):
        n = sum(chr(point) in r["ipa"] for r in rows)
        print(f"  ipa_all.csv rows containing U+{point:04X} ({label}): {n}")
    return 0


# ---------------------------------------------------------------------------
# Properties of ipakit that every external source runs into
# ---------------------------------------------------------------------------
def cmd_marks(_: Clts | None, args: argparse.Namespace) -> int:
    """Which registered marks vanish when a source writes them before the base.

    `segments(..., strict=True)` offers itself as the guarantee that
    `to_ipa(segments(x)) == x`. A mark standing before a base is registered,
    so the unknown-symbol guard never sees it; superseded stress and unbound
    ties are reported when they reach no unit, and nothing reports these.

    Swept over the whole diacritic table rather than spot-checked, because
    which marks are affected is the question -- real sources write `ˀb`
    (preglottalized) and `ⁿd` (prenasalized), and a list of two would read
    as a corner rather than as the rule.
    """
    ipa = load_ipa_features()
    dropped: list[tuple[str, str]] = []
    kept: list[str] = []
    reported: list[tuple[str, str]] = []
    for mark in sorted(ipa.diacritics):
        text = mark + "a"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                units = ipa.segments(text, strict=True)
        except (ValueError, Warning) as exc:
            reported.append((mark, type(exc).__name__))
            continue
        back = ipa.to_ipa(units)
        (kept.append(mark) if back == text else dropped.append((mark, back)))
    assert len(ipa.diacritics) > 50, "the diacritic table collapsed; sweep is vacuous"
    print(f"registered diacritics: {len(ipa.diacritics)}")
    print(f"  raise or warn when written before a base: {len(reported)}")
    for mark, kind in reported:
        print(f"    {mark!r} U+{ord(mark):04X} {unicodedata.name(mark, '?')}: {kind}")
    print(f"  carried through:                          {len(kept)}")
    print(f"  SILENTLY DROPPED under strict=True:       {len(dropped)}")
    for mark, back in dropped[: args.top]:
        print(
            f"    {mark!r} U+{ord(mark):04X} {unicodedata.name(mark, '?')}: "
            f"{mark + 'a'!r} -> {back!r}"
        )
    return 0


def cmd_inventory(_: Clts | None, args: argparse.Namespace) -> int:
    """Read an external inventory, and say how it fails rather than how often.

    Two failure kinds, counted apart because they are not equally dangerous:

      refused      -- ipakit raises. Loud, safe, fixable at the boundary.
      resegmented  -- ipakit accepts and returns a different number of units
                      than the source asserts. Silent. An inventory member is
                      one segment by definition, so one becoming two changes
                      every count built on it with nothing raised.

    A refusal count alone reads as good news and hides the second. Point
    --inventory at a file of one segment per line, or at a CSV with
    --column naming the segment column (PHOIBLE's `Phoneme`); repeats are
    counted, so a CSV of inventory rows weights each segment by how many
    inventories carry it.
    """
    if not args.inventory:
        print("no inventory given: pass --inventory PATH (see --help).")
        return 0
    path = Path(args.inventory).expanduser()
    if not path.exists():
        print(f"inventory not mounted: {path} does not exist.")
        return 0
    counts: collections.Counter[str] = collections.Counter()
    if args.column:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if seg := row.get(args.column):
                    counts[seg] += 1
    else:
        counts.update(
            line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        )
        counts.pop("", None)
    assert counts, f"{path} yielded no segments"

    ipa = load_ipa_features()
    buckets: dict[str, list[str]] = collections.defaultdict(list)
    offenders: collections.Counter[str] = collections.Counter()
    known = {
        c
        for g in (set(ipa.phones) | set(ipa.diacritics) | set(ipa.tie_bars))
        for c in unicodedata.normalize("NFD", g)
    }
    for seg in sorted(counts):
        name, n_units = bucket(seg)
        if name == "refuse":
            buckets["refused"].append(seg)
            for ch in set(unicodedata.normalize("NFD", seg)) - known:
                offenders[ch] += counts[seg]
        else:
            buckets["one segment" if n_units == 1 else "RESEGMENTED"].append(seg)

    types = sum(len(v) for v in buckets.values())
    tokens = sum(counts.values())
    print(f"{path.name}: {types} distinct segments, {tokens} memberships")
    print(
        f"  {'bucket':16s} {'types':>7s} {'type%':>7s} {'members':>9s} {'member%':>8s}"
    )
    for name in ("one segment", "RESEGMENTED", "refused"):
        segs = buckets[name]
        w = sum(counts[s] for s in segs)
        print(
            f"  {name:16s} {len(segs):7d} {len(segs) / types:6.1%} "
            f"{w:9d} {w / tokens:7.1%}"
        )
    print("\n  refusals, by the symbol ipakit does not know (weighted by members):")
    for ch, n in offenders.most_common(args.top):
        print(f"    {n:7d}  {ch!r} U+{ord(ch):04X} {unicodedata.name(ch, '?')}")
    print("\n  silent resegmentations (source says one segment, ipakit says more):")
    for seg in buckets["RESEGMENTED"][: args.top]:
        print(f"    {seg!r} -> {[s.to_ipa() for s in segments(seg)]}")

    # add_ties is the nearest thing already in the package to a bridge for
    # the untied conventions every external inventory uses. Whether it is
    # enough is a measurement, not a guess.
    fixed = worse = inert = 0
    for seg in buckets["RESEGMENTED"]:
        tied = add_ties(seg)
        if tied == seg:
            inert += 1
        elif bucket(tied) == ("agree", 1):
            fixed += 1
        else:
            worse += 1
    print(f"\n  add_ties over the {len(buckets['RESEGMENTED'])} resegmented members:")
    print(f"    now read as one segment: {fixed}")
    print(f"    add_ties changed nothing: {inert}")
    print(f"    still not one segment:    {worse}")
    return 0


def cmd_cmudict(_: Clts | None, args: argparse.Namespace) -> int:
    """Round-trip a pronunciation lexicon through ipakit and back.

    The question a lexicon practitioner actually has: if I read CMUdict in
    and write it out, do I get CMUdict back? Measured over the whole file
    rather than a sample, because the failures are a handful of segment
    *sequences* and a sample would miss them or over-weight them.

    Fetch the lexicon and point --lexicon at it; it is another project's
    data and is not bundled:
        https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
    """
    if not args.lexicon:
        print(
            "no lexicon given: pass --lexicon PATH.\n"
            "    curl -O https://raw.githubusercontent.com/cmusphinx/cmudict/"
            "master/cmudict.dict"
        )
        return 0
    path = Path(args.lexicon).expanduser()
    if not path.exists():
        print(f"lexicon not mounted: {path} does not exist.")
        return 0

    entries: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith(";;;"):
            continue
        word, _, rest = line.partition(" ")
        # CMUdict puts a free-text gloss after `#` on 22 lines. Cutting at
        # the marker rather than filtering the token is the difference
        # between 135,113 and 135,135 exact round trips -- the gloss words
        # are not phones, and counting them as phones fails those entries
        # for a reason that has nothing to do with ipakit.
        phones = rest.partition("#")[0].split()
        if phones:
            entries.append((word, phones))
    assert len(entries) > 100_000, (
        f"read {len(entries)} entries from {path}; CMUdict has ~135k, so the "
        "file is truncated or is not the lexicon"
    )

    exact = 0
    failures: list[tuple[str, list[str], list[str], str]] = []
    phones_in = phones_out = 0
    for word, phones in entries:
        ipa = from_cmu(phones)
        try:
            back = to_cmu(ipa, strict=True)
        except (ValueError, KeyError) as exc:
            failures.append((word, phones, [], f"raised: {str(exc)[:40]}"))
            continue
        phones_in += len(phones)
        phones_out += len(back)
        if back == phones:
            exact += 1
        else:
            failures.append((word, phones, back, _merge_class(phones, back)))

    print(f"{path.name}: {len(entries)} entries, {phones_in} ARPABET phones in")
    print(f"  exact round trip: {exact} / {len(entries)} = {exact / len(entries):.3%}")
    print(f"  phones out: {phones_out}  ({phones_out - phones_in:+d})")
    print("\n  failures by class:")
    for kind, n in collections.Counter(f[3] for f in failures).most_common():
        print(f"    {n:5d}  {kind}")
    print("\n  witnesses:")
    seen: set[str] = set()
    for word, phones, back, kind in failures:
        if kind in seen:
            continue
        seen.add(kind)
        print(f"    {word:16s} {' '.join(phones)}")
        print(f"    {'':16s} -> {from_cmu(phones)!r} -> {' '.join(back)}")

    # Which reader is wrong: segments() or to_cmu()? Counted rather than
    # asserted, because "the two disagree" is only a defect if one of them
    # is right, and the unit count is what says so.
    wrong_units = sum(
        1
        for word, phones, back, kind in failures
        if back and len(segments(from_cmu(phones), strict=True)) != len(phones)
    )
    print(
        f"\n  of the {len(failures)} failures, entries whose IPA `segments()` "
        f"also reads at the wrong unit count: {wrong_units}"
    )
    return 0


def _merge_class(before: list[str], after: list[str]) -> str:
    """Name a round-trip failure by the substitution that caused it."""
    if len(after) >= len(before):
        return "not a merge"
    for i in range(min(len(before), len(after))):
        if before[i] != after[i]:
            lost = " ".join(before[i : i + 2])
            return f"{lost} -> {after[i]}"
    return "trailing loss"


COMMANDS = {
    "segmentation": cmd_segmentation,
    "ties": cmd_ties,
    "features": cmd_features,
    "similarity": cmd_similarity,
    "classes": cmd_classes,
    "generate": cmd_generate,
    "phonemap": cmd_phonemap,
}

#: Subcommands that need PanPhon rather than a CLTS clone.
PANPHON_COMMANDS = {
    "panphon": cmd_panphon,
    "panphon-ties": cmd_panphon_ties,
    "marks": cmd_marks,
    "inventory": cmd_inventory,
    "cmudict": cmd_cmudict,
}


def cmd_all(clts: Clts | None, args: argparse.Namespace) -> int:
    """Every measurement, naming any whose data is not mounted."""
    status = 0
    for name, func in {**COMMANDS, **PANPHON_COMMANDS}.items():
        if clts is None and name in COMMANDS:
            print(f"\n{name}: skipped, CLTS is not mounted (see --help)")
            continue
        if name == "inventory" and not args.inventory:
            print(f"\n{name}: skipped, no --inventory given")
            continue
        if name == "cmudict" and not args.lexicon:
            print(f"\n{name}: skipped, no --lexicon given")
            continue
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        status |= func(clts, args)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--clts",
        default=os.environ.get(CLTS_ENV),
        help=f"a clone of cldf-clts/clts (default: ${CLTS_ENV})",
    )
    parser.add_argument(
        "--top", type=int, default=12, help="how many examples to print per class"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, func in {**COMMANDS, **PANPHON_COMMANDS, "all": cmd_all}.items():
        summary = ((func.__doc__ or name).strip().splitlines() or [name])[0]
        cmd = sub.add_parser(name, help=summary)
        cmd.set_defaults(
            func=func, needs_clts=name in COMMANDS, inventory=None, lexicon=None
        )
        if name in ("cmudict", "all"):
            cmd.add_argument("--lexicon", help="a CMUdict-format pronunciation lexicon")
        if name in ("inventory", "all"):
            cmd.add_argument(
                "--inventory",
                help="an external inventory: one segment per line, or a CSV",
            )
            cmd.add_argument(
                "--column", help="for a CSV inventory, the column holding the segment"
            )
    args = parser.parse_args(argv)

    # Only the CLTS measurements need the clone. The PanPhon ones read a
    # dev dependency's own shipped data, so they run wherever it is installed.
    wants_clts = getattr(args, "needs_clts", True) or args.func is cmd_all
    clts = open_clts(args) if wants_clts else None
    if clts is None and getattr(args, "needs_clts", True):
        return 0
    return int(args.func(clts, args))


if __name__ == "__main__":
    raise SystemExit(main())
