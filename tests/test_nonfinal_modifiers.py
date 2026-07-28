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
