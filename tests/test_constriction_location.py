"""A vowel may state where it constricts, and sixteen of them do.

`tract_reading` took a vowel's `arc` from `backness` and from nothing
else, so every vowel agreeing on backness sat at one point whatever else
it stated. That was a *capability* gap before it was a values gap, and
this is the capability: `constriction-location` is a declared slot a
nucleus can state, and the vowel branch reads it where it is stated.

**Sixteen vowels state one and twenty-three do not**, which is
[#123](https://github.com/lenzo-ka/ipakit/issues/123) closed as far as
the sources reach. The sixteen are the ones Wood (1979) names in the four
families of his conclusion 2, plus Swedish `ʉː` from his 1982 monograph;
they are read at the arcs `place` already declares for the four locations
under ipakit's own names for them. The rest are not classified by any
source read for `docs/design/vowel-constriction.md`, so they state
nothing, keep the `backness` fallback, and have that fallback *reported*:
`tract_reading` puts `backness` in `approximated` and `unmodelled`
returns it with kind `approximate`. `tests/test_vowel_tract_limit.py` is
what the limit has become.

Three things are worth reading for the argument rather than the
assertion.

`TestTheUnstatedCaseIsReported` is the treatment chosen for the vowels no
source classifies, and the argument for it. They keep the `backness`
fallback and the fallback is reported, rather than being left unplaced.
Unplaced is not silence in this library: `bundle_distance` scores a
coordinate one side has and the other lacks as the maximal difference and
two absences as no difference at all, so dropping schwa's arc would
assert that schwa is as far from `ɛ` as any two vowels can be on that
axis and identical to `ɜ` on it. Both assertions are stronger than the
one being withheld.

`place` was the obvious carrier and is refused on a measurement.
`TestWhyNotThePlaceSlot` is that measurement: the shipped corpus already
states `place` on vowels -- the dental and linguolabial marks -- and
reading that slot as the tongue body's constriction would move every one
of those units, in the direction of saying a dental vowel's tongue *body*
is at the teeth. It also renames the phone, because `describe` reads the
place slot.

The slot borrows `place`'s vocabulary rather than restating it, so where
`velar` is stays one number in one file. `TestOneDeclarationNotTwo` is
that property, asserted by *moving* the source and requiring the borrower
to move with it -- equal by construction, not equal today.
"""

from __future__ import annotations

import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.constants import METADATA_ATTRS
from ipakit.features import Feature
from ipakit.tract import tract_point, tract_reading, unmodelled


def _invariants() -> types.ModuleType:
    """`scripts/invariants.py`, which is not on the path as a package."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import invariants

    return invariants


#: The slot, and the feature it takes its values from.
SLOT = "constriction-location"
SOURCE = "place"

FEATURES = IPAFeatures()


@pytest.fixture
def ipa() -> IPAFeatures:
    return FEATURES


def _vowels(ipa: IPAFeatures) -> list[str]:
    return [
        p for p in sorted(ipa.phones) if ipa.get_features(p).get("manner") == "vowel"
    ]


def _units(ipa: IPAFeatures) -> list[str]:
    """Every phone and every phone-plus-one-mark that spells itself back.

    The corpus `scripts/sweep.py` defines, built here so this file can ask
    a question of it without a capture on disk.
    """
    out = []
    for base in ipa.phones:
        for mark in ("", *ipa.diacritics):
            unit = base + mark
            try:
                if ipa.segment(unit).to_ipa() == unit:
                    out.append(unit)
            except ValueError:
                continue
    return out


def _inventory(ipa: IPAFeatures, tmp_path: Path, *phones: ET.Element) -> IPAFeatures:
    """The shipped inventory with some phones added, loaded from a copy.

    A whole document rather than a supplement, because the point is to
    state a location on a phone the way `ipa.xml` would state one, and to
    keep the shipped file free of any such statement while doing it.
    """
    tree = ET.parse(ipa.xml_path)
    section = tree.getroot().find("phones")
    assert section is not None
    section.extend(phones)
    path = tmp_path / "ipa.xml"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return IPAFeatures(path)


def _inventory_declaring(
    ipa: IPAFeatures, tmp_path: Path, values: dict[str, dict[str, str]], **phones: str
) -> IPAFeatures:
    """The shipped inventory with further `place` values, and vowels stating them.

    `ipa.rng` makes `arc` and `articulator` independently optional on a
    `<value>`, so a value carrying one and not the other is a legal
    declaration and the loader accepts it. Nothing in `ipa.xml` is shaped
    that way -- every place it declares carries both -- which is why the
    two readings below are latent rather than live, and why reaching them
    takes a whole inventory of one's own. That is a supported extension
    point: `load_ipa_features(xml_path=...)` takes any document, and
    `docs/reviewing.md` says outright that `ipa.xml` travels on its own.
    """
    tree = ET.parse(ipa.xml_path)
    root = tree.getroot()
    feature = root.find(f".//feature[@name='{SOURCE}']")
    assert feature is not None
    for name, attrs in values.items():
        ET.SubElement(feature, "value", {"name": name, **attrs})
    section = root.find("phones")
    assert section is not None
    section.extend(_hypothetical(sym, **{SLOT: value}) for sym, value in phones.items())
    path = tmp_path / "ipa.xml"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return IPAFeatures(path)


def _hypothetical(name: str, **attrs: str) -> ET.Element:
    """A vowel that is not in the IPA, so no shipped answer rides on it.

    ``central`` deliberately: its arc is one no ``place`` value declares,
    so an assertion that the location was read cannot be satisfied by the
    fallback happening to land on the same number. ``front`` and
    ``palatal`` are both 0.32, and a test built on that vowel passes
    unchanged with the whole read removed.
    """
    return ET.Element(
        "phone",
        {
            "name": name,
            "manner": "vowel",
            "height": "close",
            "backness": "central",
            "rounded": "-",
            "voiced": "+",
            **attrs,
        },
    )


#: Wood's four families, under ipakit's names for the four locations, and
#: the vowels this inventory declares in each. Written out here rather
#: than read from `ipa.xml` on purpose: a test that derives the expected
#: answer from the file it is checking asserts only that the file equals
#: itself. Wood (1979: 41) conclusion 2 gives "[i-ɛ, y-ø]-like, [u-ʊ,
#: ɨ]-like, [o-ɔ, ɤ]-like and [ɑ-a-æ]-like respectively", read as ranges
#: within a rounding series; `ʉ` is from the 1982 monograph, paper III.
#: Wood (1990: 198) restates the same four at greater length -- "[i-ɛ,
#: y-œ]-like", "[u-ʊ, ɯ]-like" -- which is where `œ` and `ɯ` come from,
#: and his own summary of the 1979 figure gives the third family as
#: "[o ɔ] and [ɤ ʌ]", which is where `ʌ` does.
FAMILIES = {
    "palatal": ("i", "ɪ", "e", "ɛ", "y", "ø", "ʉ", "œ"),
    "velar": ("u", "ʊ", "ɨ", "ɯ"),
    "uvular": ("o", "ɔ", "ɤ", "ʌ"),
    "pharyngeal": ("ɑ", "a", "æ"),
}

#: The monophthongs no source read for `docs/design/vowel-constriction.md`
#: classifies by name. Nine of them are central, which is the assessment's
#: finding -- `ɨ` and `ʉ` are the only central symbols any source places,
#: and it places them in different families with 0.44 in the gap. The
#: other three are peripheral qualities no family names: `ɒ` is named
#: only on Wood's own site and by no published statement of the four,
#: and `ɶ` and `ʏ` are named nowhere at all.
UNSTATED = ("ä", "ɐ", "ɒ", "ɘ", "ə", "ɚ", "ɜ", "ɝ", "ɞ", "ɵ", "ɶ", "ʏ")


class TestWhichVowelsStateOne:
    """The classification, asserted against the source and not the file."""

    def test_the_declared_families_are_woods(self, ipa: IPAFeatures) -> None:
        """Read off the document, so a value added or moved fails here."""
        root = ET.parse(ipa.xml_path).getroot()
        stated = {
            elem.get("name"): elem.get(SLOT)
            for section in root
            for elem in section
            if elem.get(SLOT) is not None
        }
        want = {sym: place for place, syms in FAMILIES.items() for sym in syms}
        assert stated == want

    def test_the_unclassified_vowels_state_nothing(self, ipa: IPAFeatures) -> None:
        """And the two lists together are every vowel there is.

        The partition is asserted total because the interesting mistake is
        a vowel in neither list -- one that quietly acquired a family, or
        one added to the inventory that nobody classified either way.
        """
        vowels = set(_vowels(ipa))
        declared = {sym for syms in FAMILIES.values() for sym in syms}
        atoms = {v for v in vowels if len(ipa.segment(v).constituents) == 1}
        assert declared | set(UNSTATED) == atoms, atoms ^ (declared | set(UNSTATED))
        for phone in UNSTATED:
            assert SLOT not in ipa.get_features(phone), phone

    def test_a_diphthong_takes_the_location_of_its_first_element(
        self, ipa: IPAFeatures
    ) -> None:
        """Not declared on the diphthong: the flat read of an under-tie
        chain is its first constituent, so the location arrives with
        everything else about that constituent and cannot drift from it."""
        tied = [v for v in _vowels(ipa) if len(ipa.segment(v).constituents) > 1]
        assert tied, "no tied vowels: this check is vacuous"
        for unit in tied:
            first = str(ipa.segment(unit).constituents[0])
            assert ipa.get_features(unit).get(SLOT) == ipa.get_features(first).get(SLOT)

    def test_the_arc_of_a_classified_vowel_is_its_familys_place_arc(
        self, ipa: IPAFeatures
    ) -> None:
        """The four locations are read at the arcs `place` declares, which
        is the anchor decision `vowel-constriction.md` 8 makes by
        declining: 35 measured bands cannot separate those from Wood's own
        proportions, and the declared ones move no consonant."""
        arcs = ipa.features[SOURCE].coordinates
        for place, syms in FAMILIES.items():
            for sym in syms:
                reading = tract_reading(ipa, ipa.get_features(sym))
                assert reading.point.arc == arcs[place]["arc"], sym
                assert SLOT in reading.read and "backness" not in reading.read, sym


class TestTheUnstatedCaseIsReported:
    """The treatment chosen for the vowels no source classifies.

    They keep the `backness` fallback and the fallback is annotated. The
    alternative -- no arc at all, the way `rhotacized` declares no
    coordinates -- was refused on what the metric does with a missing
    coordinate, which is asserted here rather than argued.
    """

    def test_the_fallback_is_reported_as_approximate(self, ipa: IPAFeatures) -> None:
        for phone in UNSTATED:
            reading = tract_reading(ipa, ipa.get_features(phone))
            assert reading.approximated == frozenset({"backness"}), phone
            assert reading.point.arc is not None, phone
            stated = ipa.get_features(phone, with_defaults=False)
            assert ("backness", "approximate") in {
                (m.feature, m.kind) for m in unmodelled(ipa, stated)
            }, phone

    def test_an_approximated_feature_is_always_one_the_reading_took(
        self, ipa: IPAFeatures
    ) -> None:
        """`unmodelled` overrides its own skip for a name in `approximated`,
        so a name there that the reading did not take would annotate a
        value nothing drew and label it as the drawing. Swept over every
        unit rather than over the vowels, because the property is about
        the two fields and not about the branch that fills them."""
        units = _units(ipa)
        assert len(units) > 5000, f"only {len(units)} units: the sweep is vacuous"
        seen = 0
        for unit in units:
            reading = tract_reading(ipa, ipa.get_features(unit))
            assert reading.approximated <= reading.read, unit
            seen += bool(reading.approximated)
        assert seen, "nothing is ever approximated: the sweep is vacuous"

    def test_a_stated_location_is_not_approximated(self, ipa: IPAFeatures) -> None:
        """The other side of the same question, so the report is not simply
        on for every vowel."""
        for syms in FAMILIES.values():
            for sym in syms:
                assert not tract_reading(ipa, ipa.get_features(sym)).approximated, sym

    def test_a_missing_coordinate_reads_as_maximally_unlike(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """Why the unclassified vowels keep a number.

        `bundle_distance` has no way to say "unknown". A coordinate one
        bundle has and the other lacks scores 1.0, the largest any term
        can contribute; two absences score nothing at all and are not
        counted. So withholding schwa's arc would not withhold a claim, it
        would make two -- that schwa is maximally unlike every placed
        vowel on the tract axis, and exactly like every other unplaced one
        -- and both are stronger than the claim being declined.

        Measured on a hypothetical that states no `height`, because that
        is the same shape of absence in the same loop and is reachable
        without changing the branch. No shipped vowel is unplaced, which
        is the point.
        """
        from ipakit.metric import _sagittal

        made = _inventory(
            ipa,
            tmp_path,
            ET.Element(
                "phone", {"name": "ⱺ", "manner": "vowel", "rounded": "-", "voiced": "+"}
            ),
            ET.Element(
                "phone", {"name": "ⱻ", "manner": "vowel", "rounded": "-", "voiced": "+"}
            ),
        )
        assert _sagittal(made, made.get_features("ⱺ"))[1] is None
        assert _sagittal(made, made.get_features("ə"))[1] is not None
        # One side has the coordinate and the other does not: the maximum.
        far = made.distance("ⱺ", "ə")
        # Neither side has it: no term at all, so the two are indiscernible
        # on the axis rather than merely close.
        assert made.distance("ⱺ", "ⱻ") == 0.0 < far


class TestTheBranchReadsAStatedLocation:
    """The capability, on a vowel the IPA does not have."""

    def test_the_arc_is_the_stated_locations(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        arcs = ipa.features[SOURCE].coordinates
        neutral = ipa.features["backness"].coordinates["central"]["arc"]
        assert neutral not in {c["arc"] for c in arcs.values()}, (
            "the hypothetical's fallback arc is also a declared place: an "
            "assertion below could be satisfied without the location read"
        )
        located = _inventory(
            ipa,
            tmp_path,
            *(
                _hypothetical(sym, **{SLOT: place})
                for sym, place in (("ⱺ", "palatal"), ("ⱻ", "uvular"), ("ⱸ", "glottal"))
            ),
        )
        for sym, place in (("ⱺ", "palatal"), ("ⱻ", "uvular"), ("ⱸ", "glottal")):
            reading = tract_reading(located, located.get_features(sym))
            assert reading.point.arc == arcs[place]["arc"], sym
            assert SLOT in reading.read, sym

    def test_backness_supplies_nothing_when_a_location_is_stated(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The posture is one arc, so the feature that did not supply it is
        reported the way any unread stated value is -- `unmodelled` says
        `unread`, which is the only honest thing to say about a bundle
        stating two positions at once. The point is that it says something:
        a dropped value that goes unannotated is the failure the annotation
        layer exists for."""
        located = _inventory(ipa, tmp_path, _hypothetical("ⱺ", **{SLOT: "uvular"}))
        stated = located.get_features("ⱺ", with_defaults=False)
        assert "backness" not in tract_reading(located, stated).read
        assert ("backness", "unread") in {
            (m.feature, m.kind) for m in unmodelled(located, stated)
        }

    def test_a_location_that_declares_no_arc_falls_back_to_backness(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """`place` declares two combining values and no arc on either: a
        double articulation is not a point on the continuum. Asking for the
        arc is what decides the branch, so such a value leaves the vowel
        where `backness` puts it rather than unplaced -- and the components
        do have arcs, so the combining value reads as their mean, which is
        the same rule `w` reads by."""
        source = ipa.features[SOURCE]
        combining = [v for v in source.values if source.COMBINER in v]
        assert combining, "no combining place declared: this case is vacuous"
        assert not any(v in source.coordinates for v in combining)
        located = _inventory(ipa, tmp_path, _hypothetical("ⱺ", **{SLOT: combining[0]}))
        want = sum(
            source.coordinates[c]["arc"] for c in source.expand(combining[0])
        ) / len(source.expand(combining[0]))
        assert tract_point(located, located.get_features("ⱺ")).arc == want

    def test_the_shipped_vowels_do_not_move_beside_it(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """A hypothetical in the inventory changes nothing about the rest.
        The guard against a fix that reaches further than its own case."""
        located = _inventory(ipa, tmp_path, _hypothetical("ⱺ", **{SLOT: "pharyngeal"}))
        for phone in _vowels(ipa):
            assert tract_point(located, located.get_features(phone)) == tract_point(
                ipa, ipa.get_features(phone)
            ), phone


class TestTheLocationWinsWholeOrNotAtAll:
    """Two ways the fallback used to be taken half way.

    Both are **latent on the shipped inventory** and were found by review
    rather than by a wrong answer: every `place` value `ipa.xml` declares
    carries an `arc`, and the only two that do not are combining ones
    whose components both do. Neither case can arise from the inventory
    as it stands. Both are reachable through the extension points the
    library documents -- a supplement for the second, a whole inventory
    of one's own for the first -- and a supplement is exactly where the
    next vowel classification would arrive.

    What they had in common is that the *trial* of the stated location
    left marks: asking it for an arc, failing, and still taking its
    articulator, or averaging over the components that answered and
    calling that the stated fusion. The reading now commits one source
    whole -- arc, articulator and the name in `read` together -- so a
    location that cannot place the vowel places nothing about it.
    """

    def test_a_location_with_no_arc_supplies_no_articulator_either(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """`arc` and `articulator` are one statement about one
        constriction. Taking the position from `backness` and the organ
        from a location that could not supply a position makes a point
        that describes no gesture, and reports nothing amiss: `backness`
        is marked `approximate` for the arc and the location is not
        marked at all, because taking its articulator put it in `read`."""
        made = _inventory_declaring(
            ipa,
            tmp_path,
            {"tongue-root-only": {"articulator": "tongue-root"}},
            **{"ⱺ": "tongue-root-only"},
        )
        source = made.features[SOURCE]
        # The constructed case has the shape it is meant to have, and the
        # two organs differ, so an assertion on the organ cannot be
        # satisfied by the fallback happening to supply the same one.
        assert "tongue-root-only" not in source.coordinates
        assert source.articulators["tongue-root-only"] == "tongue-root"
        assert made.features["backness"].articulators["central"] == "tongue-dorsum"

        reading = tract_reading(made, made.get_features("ⱺ"))
        assert (
            reading.point.arc == made.features["backness"].coordinates["central"]["arc"]
        )
        assert reading.point.articulator == "tongue-dorsum"
        assert SLOT not in reading.read
        assert reading.approximated == frozenset({"backness"})
        stated = made.get_features("ⱺ", with_defaults=False)
        marks = {(m.feature, m.kind) for m in unmodelled(made, stated)}
        assert ("backness", "approximate") in marks
        assert (SLOT, "unread") in marks

    def test_a_half_placeable_fusion_falls_back_whole(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """A mean over the components that answered is another value's
        position, not the stated one's: `palatal^X` came back as plain
        `palatal`, and came back unflagged, so nothing downstream could
        tell it from a vowel that stated `palatal`."""
        made = _inventory_declaring(
            ipa,
            tmp_path,
            {"unplaceable": {"articulator": "tongue-root"}},
            **{"ⱻ": f"palatal{Feature.COMBINER}unplaceable"},
        )
        source = made.features[SOURCE]
        placed = source.coordinates["palatal"]["arc"]
        fallback = made.features["backness"].coordinates["central"]["arc"]
        # Non-vacuity: the wrong answer and the right one are different
        # numbers, so the assertion cannot pass with the fix removed.
        assert placed != fallback
        reading = tract_reading(made, made.get_features("ⱻ"))
        assert reading.point.arc == fallback
        assert SLOT not in reading.read
        assert reading.approximated == frozenset({"backness"})

    def test_the_same_case_arrives_through_a_supplement(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The reachable route, and the one a classification would use.

        A supplement declares no feature and no value -- that is the line
        `supplement.rng` holds -- but it states them, and it may state a
        fusion naming a component the inventory has no coordinate for.
        No inventory of one's own is needed for this half."""
        path = tmp_path / "half.xml"
        path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<supplement name="half"><phones>'
            '<phone name="ⱻ" manner="vowel" height="close" backness="central" '
            f'rounded="-" voiced="+" {SLOT}="palatal^nonesuch"/>'
            "</phones></supplement>",
            encoding="utf-8",
        )
        made = IPAFeatures(supplements=[path])
        assert made.get_features("ⱻ")[SLOT] == "palatal^nonesuch"
        assert "nonesuch" not in made.features[SOURCE].coordinates
        reading = tract_reading(made, made.get_features("ⱻ"))
        assert (
            reading.point.arc == made.features["backness"].coordinates["central"]["arc"]
        )
        assert reading.approximated == frozenset({"backness"})

    def test_one_feature_supplies_both_coordinates_of_the_point(
        self, ipa: IPAFeatures
    ) -> None:
        """The property the two cases above are instances of, swept over
        the whole corpus so it holds for the inventory and not only for
        the constructed cases: whichever feature gave the point its arc
        is the one that gave it its articulator, unless the bundle stated
        an articulator outright, which always wins.

        **This one passes with the fix removed**, and is here anyway. The
        three above are the regression, and they need a declaration
        `ipa.xml` does not make; this is the class invariant over the
        inventory that does ship, and it says what the shipped data would
        have to become for those three to stop being hypothetical. A
        `place` value declaring an organ and no position would break it.
        """
        units = _units(ipa)
        assert len(units) > 5000, f"only {len(units)} units: the sweep is vacuous"
        checked = 0
        for unit in units:
            bundle = ipa.get_features(unit)
            reading = tract_reading(ipa, bundle)
            organ = reading.point.articulator
            if organ is None or bundle.get("articulator") is not None:
                continue
            sources = [
                name
                for name in (SLOT, "backness", "place")
                if name in reading.read and bundle.get(name) is not None
            ]
            assert len(sources) == 1, (unit, sources)
            feature = ipa.features[sources[0]]
            want = [
                feature.articulators.get(comp)
                for comp in feature.expand(bundle[sources[0]])
            ]
            assert organ == Feature.COMBINER.join(
                dict.fromkeys(o for o in want if o is not None)
            ), unit
            checked += 1
        assert checked > 5000, f"only {checked} points carried an organ"


class TestItDoesNotRenameThePhone:
    """The other half of why this is not the `place` slot."""

    def test_a_stated_location_adds_no_word(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        both = _inventory(
            ipa,
            tmp_path,
            _hypothetical("ⱺ"),
            _hypothetical("ⱻ", **{SLOT: "velar"}),
            _hypothetical("ⱸ", place="velar"),
        )
        plain = both.describe("ⱺ")
        assert both.describe("ⱻ") == plain, "the location slot reached the sentence"
        # The same value in the place slot does rename it, which is the
        # comparison: the two slots are not interchangeable.
        assert both.describe("ⱸ") == f"velar {plain}"

    def test_the_slot_declares_nothing_a_description_reads(
        self, ipa: IPAFeatures
    ) -> None:
        """Why, rather than that it happens not to. A description reads a
        modifier out because the feature declares a *label*, and reads a
        slot out because `describe` names that slot; this feature does
        neither."""
        from ipakit.analysis import _PRIMARY_SLOTS, _VOWEL_SLOTS

        assert not ipa.features[SLOT].labels
        assert SLOT not in _PRIMARY_SLOTS and SLOT not in _VOWEL_SLOTS


class TestWhyNotThePlaceSlot:
    """The measurement that refused the obvious carrier.

    The slot `place` is not free on a vowel: the dental and linguolabial
    marks put one there, and a vowel wearing one is a vowel whose tongue
    *tip* is at that place while its tongue *body* is where the vowel
    branch reads it. Reading the place slot as the body's constriction
    would move every one of those units, and toward a wrong answer.
    """

    def test_the_shipped_corpus_already_states_place_on_vowels(
        self, ipa: IPAFeatures
    ) -> None:
        units = _units(ipa)
        assert len(units) > 5000, f"only {len(units)} units: the sweep is vacuous"
        placed = [
            u
            for u in units
            if (b := ipa.get_features(u)).get("manner") == "vowel" and b.get("place")
        ]
        assert placed, "no vowel states a place: the argument below is vacuous"
        arcs = ipa.features[SOURCE].coordinates
        backness = ipa.features["backness"].coordinates
        for unit in placed:
            bundle = ipa.get_features(unit)
            here = tract_point(ipa, bundle).arc
            # Wherever the body is, it is not read out of the place slot.
            want = (
                arcs[bundle[SLOT]]["arc"]
                if SLOT in bundle
                else backness[bundle["backness"]]["arc"]
            )
            assert here == want, unit
            # And the place slot says somewhere else, so reading it would
            # have been a mover rather than a no-op.
            assert here != arcs[bundle["place"]]["arc"], unit

    def test_a_dental_vowel_is_named_for_its_place(self, ipa: IPAFeatures) -> None:
        """The rename, pinned as the reason it must not be the carrier: this
        sentence is right, and it is right because the mark is about the
        tongue tip."""
        assert ipa.describe("a̪") == "dental open front unrounded vowel"


class TestOneDeclarationNotTwo:
    """Where `velar` is, is one number in one file.

    The secondary-articulation set was three copies in three modules that
    agreed by habit until one drifted and `l` and `ɫ` came out identical.
    A second feature naming the same tract locations is that hazard again,
    and `vocabulary` is what removes it rather than guarding it.
    """

    def test_the_tables_are_the_sources(self, ipa: IPAFeatures) -> None:
        slot, source = ipa.features[SLOT], ipa.features[SOURCE]
        assert slot.vocabulary == SOURCE
        assert slot.values == source.values
        assert slot.coordinates == source.coordinates
        assert slot.value_aliases == source.value_aliases
        assert slot.articulators == source.articulators
        assert slot.offscale == source.offscale
        assert slot.coordinates, "no coordinates borrowed: the assertions are vacuous"

    def test_the_document_spells_no_value_for_it(self, ipa: IPAFeatures) -> None:
        elem = ET.parse(ipa.xml_path).getroot().find(f".//feature[@name='{SLOT}']")
        assert elem is not None
        assert elem.findall("value") == []

    def test_moving_the_source_moves_the_borrower(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """Equal by construction, not equal today. Without this the two
        tables could be checked equal in a file where the copy never ran.
        """
        tree = ET.parse(ipa.xml_path)
        velar = tree.getroot().find(
            f".//feature[@name='{SOURCE}']/value[@name='velar']"
        )
        assert velar is not None and velar.get("arc") != "0.99"
        velar.set("arc", "0.99")
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)

        moved = IPAFeatures(path)
        assert moved.features[SOURCE].coordinates["velar"]["arc"] == 0.99
        assert moved.features[SLOT].coordinates["velar"]["arc"] == 0.99

    def test_it_takes_no_short_code_from_the_source(self, ipa: IPAFeatures) -> None:
        """What is deliberately *not* borrowed, so the limit is known.

        A short code is one feature's notation for one of its values, and
        the reader that resolves one is a flat map over the whole
        inventory. Copying `place`'s would put two features on one code and
        the second read would win, silently. So the slot has no short
        spelling for its values, and `plc:velar` still means what it did.
        """
        assert ipa.features_to_shorts({SLOT: "velar"}) == []
        assert ipa.features_to_shorts({SOURCE: "velar"}) == ["vel"]
        assert ipa.shorts_to_features(["vel"]) == {SOURCE: "velar"}


class TestTheLoaderRefusesTheWaysItCouldGoWrong:
    """Each guard, made to fail."""

    def _patched(self, ipa: IPAFeatures, tmp_path: Path, **attrs: str) -> Path:
        tree = ET.parse(ipa.xml_path)
        elem = tree.getroot().find(f".//feature[@name='{SLOT}']")
        assert elem is not None
        for key, value in attrs.items():
            elem.set(key, value)
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def test_a_vocabulary_naming_nothing_is_refused(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        path = self._patched(ipa, tmp_path, vocabulary="nowhere")
        with pytest.raises(ValueError, match="not a feature declared before it"):
            IPAFeatures(path)

    def test_a_forward_reference_is_refused(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """Naming a feature declared *later* is the same failure: the loader
        copies as it goes, so a forward reference would leave the borrower
        with no values at all and nothing would say so."""
        path = self._patched(ipa, tmp_path, vocabulary="phonation")
        with pytest.raises(ValueError, match="not a feature declared before it"):
            IPAFeatures(path)

    def test_borrowing_and_spelling_values_is_refused(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        tree = ET.parse(ipa.xml_path)
        elem = tree.getroot().find(f".//feature[@name='{SLOT}']")
        assert elem is not None
        elem.append(ET.Element("value", {"name": "somewhere", "arc": "0.5"}))
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        with pytest.raises(ValueError, match="declares .* of its own"):
            IPAFeatures(path)

    def test_the_invariant_goes_vacuous_rather_than_quiet(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """A check with nothing to look at reports that, and does not pass.

        Dropping the attribute leaves a feature with no values, which is a
        legal document -- so the failure this catches is the borrowing
        being removed, not a malformed file.
        """
        assert _invariants().check_borrowed_vocabulary(ipa)

        tree = ET.parse(ipa.xml_path)
        elem = tree.getroot().find(f".//feature[@name='{SLOT}']")
        assert elem is not None
        del elem.attrib["vocabulary"]
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        assert not _invariants().check_borrowed_vocabulary(IPAFeatures(path))

    def test_the_invariant_fires_on_two_tables_that_disagree(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The drift it exists for, made to happen.

        The loader copies unconditionally, so no *document* can make the
        two disagree. What can is a change to the loader that stops
        copying a table -- and that is what this stands in for, by taking
        the tables apart on a throwaway instance.
        """
        drifted = IPAFeatures(ipa.xml_path)
        assert _invariants().check_borrowed_vocabulary(drifted)
        drifted.features[SLOT].coordinates["velar"] = {"arc": 0.99}
        assert not _invariants().check_borrowed_vocabulary(drifted)

    def test_the_partition_over_feature_fields_is_total_and_can_fail(
        self, ipa: IPAFeatures
    ) -> None:
        """What the comparison cannot see is a field nobody classified, so
        the classification is asserted total -- and shown to fail when it
        is not."""
        invariants = _invariants()
        assert invariants.check_borrowed_vocabulary_is_total(ipa)
        borrowed = invariants.BORROWED
        try:
            invariants.BORROWED = borrowed - {"coordinates"}
            assert not invariants.check_borrowed_vocabulary_is_total(ipa)
        finally:
            invariants.BORROWED = borrowed
        assert invariants.check_borrowed_vocabulary_is_total(ipa)


class TestTheSlotIsNotAMetadataAttribute:
    """It is a feature, so it lands in a feature bag and in the metric,
    which is what a stated location has to do to mean anything."""

    def test_it_is_a_declared_feature_and_not_metadata(self, ipa: IPAFeatures) -> None:
        assert SLOT in ipa.features
        assert SLOT not in METADATA_ATTRS

    def test_stating_it_moves_the_metric(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """Two hypothetical vowels alike but for where they constrict are
        not the same sound, and the metric has to say so. Without this the
        capability could be inert and every assertion above would still
        pass."""
        located = _inventory(
            ipa,
            tmp_path,
            _hypothetical("ⱺ", **{SLOT: "palatal"}),
            _hypothetical("ⱻ", **{SLOT: "pharyngeal"}),
            _hypothetical("ⱸ"),
        )
        assert located.distance("ⱺ", "ⱻ") > 0
        assert located.distance("ⱺ", "ⱻ") > located.distance("ⱺ", "ⱸ")
