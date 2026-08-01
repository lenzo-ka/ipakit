"""Where a mark sits decides what it reaches, and both levels say so.

`Segment.scalar` overlaid `constituents[-1].modifiers` alone, so a
diacritic written on an earlier part of a composed unit vanished from the
flat projection while every structured read carried it. Reachable through
`build_segment` all along, and through ordinary strings once a tie could
follow a diacritic.

Applying every constituent's marks *after* composing the bare chain then
overshot in the other direction: the overlay ran after the merge, so an
earlier constituent's overriding mark beat a later constituent's own
value and `t̪͡s` came back dental where `get_features` said alveolar. A
mark belongs to its constituent's bundle and goes into the merge with it,
which is what `flat_projection` now does for both levels at once. The
additive cases below are the ones the old parametrization covered; the
overriding and under-tie ones are the ones it did not.
"""

import warnings

import pytest
from ipakit import IPAFeatures, Sense
from ipakit.constants import METADATA_ATTRS


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# (string, feature, expected) -- an *additive* mark on the first
# constituent, naming a key the trailing constituent does not state, so
# the merge preserves it. These are the cases PR #34 fixed.
LEADING_MARK = [
    ("kʷ͡p", "labialized", "+"),
    ("ã͜i", "nasalized", "+"),
    ("tʰ͡s", "release", "aspirated"),
    ("tʲ͡s", "palatalized", "+"),
    ("d̥͡s", "voiced", "-"),  # overriding, but "s" states no voicing
]

# (string, feature, expected) -- an *overriding* mark on the first
# constituent, naming a key the trailing constituent states itself. The
# merge is left to right, last constituent wins, so the mark loses: an
# affricate takes the place of its release, and "t͡ʃ" is postalveolar for
# exactly the same reason. Every one of these came back with the leading
# constituent's value before the two levels became one computation.
OVERRIDING_MARK = [
    ("t̪͡s", "place", "alveolar"),
    ("t̪͡ʃ", "place", "postalveolar"),
    ("n̥͡d", "voiced", "+"),
    ("d̥͡z", "voiced", "+"),
    ("t̪͡s͜a", "place", "alveolar"),  # ... and through a mixed chain
]

# (string, feature, expected) -- a mark on a constituent *past* the first
# under-tie block. A sequential chain projects its first block, so the
# mark does not reach the flat read at all; it stays visible in bag().
# The old sweep only ever wrote marks on the leading constituent, so this
# whole family went unexercised.
UNDER_TIE_TRAILING = [
    ("a͜ɪ̃", "nasalized", "-"),
    ("a͜ɪʷ", "labialized", "-"),
    ("a͜ɪ̥", "voiced", "+"),  # the devoicing ring, an overriding mark
    ("t͡s͜ã", "nasalized", "-"),
    ("t͡s͜aʷ", "labialized", "-"),
]

ALL_MARKED = LEADING_MARK + OVERRIDING_MARK + UNDER_TIE_TRAILING


class TestLeadingConstituentMarks:
    @pytest.mark.parametrize(("unit", "feature", "expected"), LEADING_MARK)
    def test_the_flat_read_carries_it(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.segment(unit).scalar()[feature] == expected

    @pytest.mark.parametrize(("unit", "feature", "expected"), ALL_MARKED)
    def test_both_levels_agree(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.get_features(unit)[feature] == ipa.segment(unit).scalar()[feature]

    @pytest.mark.parametrize(("unit", "feature", "expected"), ALL_MARKED)
    def test_the_third_read_agrees_too(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.compose(unit)[0][feature] == expected


class TestAnOverridingMarkDoesNotWinBackwards:
    """The merge is left to right; a mark cannot reach past its own
    constituent to overrule a later one's stated value."""

    @pytest.mark.parametrize(("unit", "feature", "expected"), OVERRIDING_MARK)
    def test_the_release_decides(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.segment(unit).scalar()[feature] == expected

    def test_the_leading_value_is_still_recoverable(self, ipa: IPAFeatures) -> None:
        # Lost from the flat projection is not lost from the unit: the
        # dental t̪ is right there in the bag, which is the read that
        # answers "what does this unit hold".
        assert ipa.segment("t̪͡s").bag()["place"] == ("dental", "alveolar")

    def test_the_convention_this_protects(self, ipa: IPAFeatures) -> None:
        # An affricate has the place of its release. Letting an earlier
        # constituent's mark win would break this, which is how the two
        # levels were told apart in the first place.
        assert ipa.get_features("t͡ʃ")["place"] == "postalveolar"
        assert ipa.segment("t͡ʃ").scalar()["place"] == "postalveolar"


class TestASequentialChainProjectsItsFirstBlock:
    """A mark past the first under-tie block is not in the flat read."""

    @pytest.mark.parametrize(("unit", "feature", "expected"), UNDER_TIE_TRAILING)
    def test_the_trailing_mark_does_not_reach_it(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert ipa.segment(unit).scalar()[feature] == expected

    @pytest.mark.parametrize(("unit", "feature", "expected"), UNDER_TIE_TRAILING)
    def test_the_unit_still_holds_it(
        self, ipa: IPAFeatures, unit: str, feature: str, expected: str
    ) -> None:
        assert expected in ipa.segment(unit).bag()[feature]
        assert len(ipa.segment(unit).bag()[feature]) > 1

    def test_a_mark_inside_the_first_block_does_reach_it(
        self, ipa: IPAFeatures
    ) -> None:
        # The rule is the block boundary, not the position in the string:
        # the affricate's own marks project, "a"'s do not.
        assert ipa.segment("t͡sʷ͜a").scalar()["labialized"] == "+"
        assert ipa.segment("tʷ͡s͜a").scalar()["labialized"] == "+"
        assert ipa.segment("t͡s͜aʷ").scalar()["labialized"] == "-"

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
        """Over the whole inventory, and over the ties the data declares.

        It used to run ``phones[:40]`` by ``diacritics[:15]``: a
        positional slice of declaration order, chosen by nothing,
        reshuffled by any reordering of ipa.xml, and holding not one
        tie-bar base in a test about tied units. The metadata keys were
        a third inline copy of ``METADATA_ATTRS``, written from it and
        already missing ``name``; the tie glyphs were pasted rather than
        read off ``tie_bars``.

        This is not the sweep in ``test_one_composition.py``, which
        compares the flat read against the structured one over the same
        strings. Here the claim is about one read on its own: a value
        the flat projection reports is a value some constituent holds,
        so the two would agree on an invented value and this would not.
        """
        # manner and place are excluded because fusion derives them --
        # differing manners collapse to affricate and places combine, so
        # neither is a constituent value by design (docs/ties.md).
        derived = {"manner", "place"}
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for base in ipa.phones:
                for mark in ipa.diacritics:
                    for tail in ("p", "a"):
                        for tie in sorted(ipa.tie_bars):
                            try:
                                unit = ipa.segment(base + mark + tie + tail)
                            except ValueError:
                                continue
                            checked += 1
                            bag = unit.bag()
                            for key, value in unit.scalar().items():
                                if key in derived or key in METADATA_ATTRS:
                                    continue
                                if key in bag:
                                    assert value in bag[key], (
                                        base + mark + tie + tail,
                                        key,
                                        value,
                                        bag[key],
                                    )
        assert checked > 30_000, "sweep did not run"


class TestNucleusFeatures:
    """`rhotacized` is a nucleus feature, not a vowel feature.

    A syllabic liquid is a nucleus with consonantal manner, so keying
    r-coloring to manner lost it on exactly the segment American English
    uses most: the second syllable of "butter".
    """

    def test_a_syllabic_consonant_reads_its_r_coloring(self, ipa: IPAFeatures) -> None:
        assert "r-colored" in ipa.describe("ɹ̩˞")
        assert "r-colored" in ipa.describe("l̩˞")

    def test_a_vowel_nucleus_is_unchanged(self, ipa: IPAFeatures) -> None:
        assert ipa.describe("ɚ") == "r-colored mid central unrounded vowel"

    def test_a_stated_feature_is_read_out_even_off_its_class(
        self, ipa: IPAFeatures
    ) -> None:
        # This asserted the opposite when `applies` first landed, on the
        # view that a rhotic mark on a non-nucleus is redundant notation
        # not worth naming. That view made `describe` and the metric
        # disagree: the metric charges the feature (d(ɹ, ɹ˞) > 0) while
        # the description hid it, giving two distinct units one name --
        # the failure this path exists to avoid. `applies` says where a
        # feature is expected, not where it may be reported.
        assert "r-colored" in ipa.describe("ɹ˞")
        assert ipa.describe("ɹ˞") != ipa.describe("ɹ")
        assert ipa.distance("ɹ", "ɹ˞") > 0.0

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
