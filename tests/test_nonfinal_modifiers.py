"""A mark on any constituent reaches the flat read, not only the last.

`Segment.scalar` overlaid `constituents[-1].modifiers` alone, so a
diacritic written on an earlier part of a composed unit vanished from the
flat projection while every structured read carried it. Reachable through
`build_segment` all along, and through ordinary strings once a tie could
follow a diacritic.
"""

import pytest
from ipakit import IPAFeatures, Sense


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# (string, feature, expected) -- the mark sits on the *first* constituent.
LEADING_MARK = [
    ("kʷ͡p", "labialized", "+"),
    ("ã͜i", "nasalized", "+"),
    ("tʰ͡s", "release", "aspirated"),
    ("tʲ͡s", "palatalized", "+"),
]


class TestLeadingConstituentMarks:
    @pytest.mark.parametrize(("unit", "feature", "expected"), LEADING_MARK)
    def test_the_flat_read_carries_it(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.segment(unit).scalar()[feature] == expected

    @pytest.mark.parametrize(("unit", "feature", "expected"), LEADING_MARK)
    def test_both_levels_agree(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.get_features(unit)[feature] == ipa.segment(unit).scalar()[feature]

    def test_a_trailing_mark_still_works(self, ipa: IPAFeatures) -> None:
        # The case that always worked must not regress.
        assert ipa.segment("t͡sʷ").scalar()["labialized"] == "+"

    def test_marks_on_both_constituents(self, ipa: IPAFeatures) -> None:
        unit = ipa.segment("kʷ͡pʲ")
        assert unit.scalar()["labialized"] == "+"
        assert unit.scalar()["palatalized"] == "+"

    def test_reachable_from_intent_too(self, ipa: IPAFeatures) -> None:
        # build_segment bypasses the string layer, and reached this bug
        # before a tie could follow a diacritic at all.
        built = ipa.build_segment(["kʷ", "p"], Sense.FUSE)
        assert built.scalar()["labialized"] == "+"


class TestScalarNeverInventsAValue:
    """The general invariant: a value in the flat projection is one the
    unit's own constituents hold, except where composition derives it."""

    def test_scalar_values_come_from_the_bag(self, ipa: IPAFeatures) -> None:
        # manner and place are excluded because fusion derives them --
        # differing manners collapse to affricate and places combine, so
        # neither is a constituent value by design (docs/ties.md).
        derived = {"manner", "place"}
        metadata = {"class", "href", "xsampa"}
        checked = 0
        for base in list(ipa.phones)[:40]:
            for mark in list(ipa.diacritics)[:15]:
                for tail in ("p", "a"):
                    for tie in ("͡", "͜"):
                        try:
                            unit = ipa.segment(base + mark + tie + tail)
                        except ValueError:
                            continue
                        checked += 1
                        bag = unit.bag()
                        for key, value in unit.scalar().items():
                            if key in derived or key in metadata:
                                continue
                            if key in bag:
                                assert value in bag[key], (
                                    base + mark + tie + tail,
                                    key,
                                    value,
                                    bag[key],
                                )
        assert checked > 500, "sweep did not run"


class TestNucleusFeatures:
    """`rhotacized` is a nucleus feature, not a vowel feature.

    A syllabic liquid is a nucleus with consonantal manner, so keying
    r-colouring to manner lost it on exactly the segment American English
    uses most: the second syllable of "butter".
    """

    def test_a_syllabic_consonant_reads_its_r_colouring(self, ipa: IPAFeatures) -> None:
        assert "r-colored" in ipa.describe("ɹ̩˞")
        assert "r-colored" in ipa.describe("l̩˞")

    def test_a_vowel_nucleus_is_unchanged(self, ipa: IPAFeatures) -> None:
        assert ipa.describe("ɚ") == "r-colored mid central unrounded vowel"

    def test_a_non_nucleus_does_not_read_it(self, ipa: IPAFeatures) -> None:
        # A rhotic mark on a non-syllabic consonant is redundant notation,
        # and naming it would describe a segment that has no nucleus.
        assert "r-colored" not in ipa.describe("ɹ˞")

    def test_nucleus_is_not_a_manner_class(self, ipa: IPAFeatures) -> None:
        # Fricative and stop nuclei are attested (Tashlhiyt Berber,
        # Miyako, Nuosu Yi), so nucleus-hood cannot be read off manner.
        assert ipa.feature_applies("rhotacized", {"manner": "vowel"})
        assert ipa.feature_applies(
            "rhotacized", {"manner": "fricative", "syllabic": "+"}
        )
        assert not ipa.feature_applies("rhotacized", {"manner": "fricative"})

    def test_articulation_features_stay_manner_based(self, ipa: IPAFeatures) -> None:
        # channel names where a channel sits within a constriction, so a
        # syllabic lateral keeps its "lateral" and a vowel never gets one.
        assert "lateral" in ipa.describe("l̩")
        assert ipa.feature_applies("channel", {"manner": "approximant"})
        assert not ipa.feature_applies("channel", {"manner": "vowel", "syllabic": "+"})
