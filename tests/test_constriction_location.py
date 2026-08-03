"""A vowel may state where it constricts, and none of them does yet.

`tract_reading` took a vowel's `arc` from `backness` and from nothing
else, so every vowel agreeing on backness sat at one point whatever else
it stated. That is a *capability* gap and not a values gap, and this is
the capability: `constriction-location` is a declared slot a nucleus can
state, and the vowel branch reads it where it is stated.

**No vowel states one.** Which vowel constricts where is
[#123](https://github.com/lenzo-ka/ipakit/issues/123), it is blocked on a
source that classifies the central series and there is none, and choosing
values here would smuggle an unsupported table in behind a mechanical
change. So the demonstration below is a *hypothetical* vowel in a
temporary inventory, and the shipped answers are asserted unchanged
beside it. `tests/test_vowel_tract_limit.py` is the limit as it stands and
every pin in it still holds: the limit has not moved, only what could move
it.

Two things are worth reading for the argument rather than the assertion.

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


class TestNoVowelStatesOne:
    """The boundary this change was built inside, asserted."""

    def test_the_document_states_no_location_on_any_symbol(
        self, ipa: IPAFeatures
    ) -> None:
        """Read off the file, so a value added anywhere fails here.

        Not `get_features`, which would answer for phones alone and would
        also answer for a default; the question is whether any symbol
        element in the document carries the attribute at all.
        """
        root = ET.parse(ipa.xml_path).getroot()
        stated = [
            elem.get("name")
            for section in root
            for elem in section
            if elem.get(SLOT) is not None
        ]
        assert stated == [], f"{SLOT} is stated on {stated}; #123 is not this PR"

    def test_the_slot_reaches_no_shipped_bundle(self, ipa: IPAFeatures) -> None:
        """It declares no default either, so it is in no feature bag.

        This is what keeps the metric still: a key present on every bundle
        is a term in the denominator of every distance even when the two
        values agree.
        """
        assert ipa.features[SLOT].default is None
        units = _units(ipa)
        assert len(units) > 5000, f"only {len(units)} units: the sweep is vacuous"
        assert not [u for u in units if SLOT in ipa.get_features(u)]

    def test_every_vowel_still_reads_its_arc_from_backness(
        self, ipa: IPAFeatures
    ) -> None:
        vowels = _vowels(ipa)
        assert len(vowels) > 20, f"only {len(vowels)} vowels: the sweep is vacuous"
        for phone in vowels:
            read = tract_reading(ipa, ipa.get_features(phone)).read
            assert "backness" in read and SLOT not in read, phone


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
    *tip* is at that place while its tongue *body* is wherever `backness`
    put it. Reading the place slot as the body's constriction would move
    every one of those units, and toward a wrong answer.
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
            assert here == backness[bundle["backness"]]["arc"], unit
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
