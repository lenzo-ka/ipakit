"""The flat projection of a unit is one computation, swept exhaustively.

`features()`/`get_features()`, `compose()` and `Segment.scalar()` are all
documented as one read of one unit. They were three implementations of
it, and they diverged wherever a tie chain carried a mark on a
constituent other than the last: `t̪͡s` was alveolar to the flat side and
dental to the structured one, `a͜ɪ̃` nasalized to two of them and not to
the third.

Round after round of targeted tests missed it because every case they
named put an *additive* mark on the leading constituent -- a key the
trailing constituent does not state, so the clobbering path was never
taken. The guard against the next one is not a longer list of cases: it
is the sweep below, over every well-formed base + mark + tie + base
string the inventory can spell, in both mark positions, comparing whole
bundles rather than one named key.
"""

import warnings

import pytest
from ipakit import IPAFeatures, Segment
from ipakit.constants import METADATA_ATTRS, SEQ_TIE, TIE_BAR

TAILS = ("p", "a", "s", "d")


@pytest.fixture(scope="module")
def units(ipa: IPAFeatures) -> list[tuple[str, Segment]]:
    """Every well-formed tie chain of base + mark + base, both positions.

    Well-formed means the string parses strictly and re-emits itself, so
    nothing here is a unit the parse quietly shortened.
    """
    out: list[tuple[str, Segment]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for base in ipa.phones:
            for mark in ipa.diacritics:
                for tie in (TIE_BAR, SEQ_TIE):
                    for tail in TAILS:
                        for text in (
                            base + mark + tie + tail,
                            base + tie + tail + mark,
                        ):
                            try:
                                unit = ipa.segment(text, strict=True)
                            except ValueError:
                                continue
                            if unit.to_ipa() == text:
                                out.append((text, unit))
    return out


def _phonetic(feats: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in feats.items() if k not in METADATA_ATTRS}


class TestTheSweep:
    def test_the_sweep_is_wide(self, units: list[tuple[str, Segment]]) -> None:
        # A silent collapse of the corpus would make every assertion below
        # vacuous, so the size is asserted, not assumed.
        assert len(units) > 50_000

    def test_the_flat_and_structured_reads_are_one(
        self, ipa: IPAFeatures, units: list[tuple[str, Segment]]
    ) -> None:
        for text, unit in units:
            flat = ipa.get_features(text)
            if not flat:
                continue
            assert _phonetic(flat) == _phonetic(unit.scalar()), text

    def test_compose_is_the_same_read_off_prosody(
        self, ipa: IPAFeatures, units: list[tuple[str, Segment]]
    ) -> None:
        # compose() returns one flat bundle per token and has nowhere but
        # that bundle to put a prosodic mark, so it reports length on
        # "eː" where scalar() carries the mark in prosody. That is the one
        # documented divergence, and it stays exactly that one thing: any
        # key it differs on must be a key the unit's own prosody states.
        for text, unit in units:
            composed = ipa.compose(text)
            if not composed:
                continue
            scalar = unit.scalar()
            prosodic_keys = {
                key
                for mark in unit.prosody
                if (entry := ipa.diacritics.get(mark)) is not None
                for key in entry.features
            }
            differing = {
                k
                for k in set(composed[0]) | set(scalar)
                if k not in METADATA_ATTRS and composed[0].get(k) != scalar.get(k)
            }
            assert differing <= prosodic_keys, (text, differing)

    def test_no_value_is_invented(
        self, ipa: IPAFeatures, units: list[tuple[str, Segment]]
    ) -> None:
        # A value in the projection is one some constituent holds, except
        # where fusion derives it (differing manners collapse to affricate
        # and differing places combine).
        derived = {"manner", "place"}
        for text, unit in units:
            bag = unit.bag()
            for key, value in unit.scalar().items():
                if key in derived or key in METADATA_ATTRS or key not in bag:
                    continue
                assert value in bag[key], (text, key, value, bag[key])


class TestTheDocumentedDivergenceSurvives:
    def test_compose_carries_length_where_scalar_carries_prosody(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.compose("eː")[0]["length"] == "long"
        assert ipa.segment("eː").scalar()["length"] == "normal"
        assert ipa.segment("eː").prosody == ("ː",)


class TestAnUnboundTieDoesNotCrashTheFlatRead:
    """`_resolves_part` tolerates a trailing tie, so the read must too.

    `_is_composable` accepted a SEQ chain whose block ended in an
    over-tie, because `_parse_constituent` tolerates the dangling glyph.
    The fused merge then split that block on the tie and raised on the
    empty part it had manufactured -- the two halves of one path
    disagreeing about whether the same string resolves.
    """

    UNBOUND = ["a͜ɪ͡", "s͜p͡", "a͜t͡", "t͡s͜a͡", "ʃ͜k͡", "͡s", "a͡"]

    @pytest.mark.parametrize("unit", UNBOUND)
    def test_it_reads_rather_than_raising(self, ipa: IPAFeatures, unit: str) -> None:
        # get_features documents "{} when nothing resolves"; raising is
        # neither that nor an answer.
        ipa.get_features(unit)

    @pytest.mark.parametrize("unit", UNBOUND)
    def test_it_agrees_with_compose(self, ipa: IPAFeatures, unit: str) -> None:
        # parse treats a tie that binds nothing as no juncture at all, so
        # the flat read composes it away and lands where compose does.
        flat = ipa.get_features(unit)
        composed = ipa.compose(unit)
        if not composed or not flat:
            return
        for key, value in composed[0].items():
            if key in ("class", "href", "xsampa"):
                continue
            assert flat.get(key) == value, (unit, key)

    def test_the_marks_that_do_bind_are_unaffected(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("t͡s")["manner"] == "affricate"
        assert ipa.get_features("a͜ɪ")["manner"] == "vowel"
        assert ipa.get_features("kʷ͡p")["labialized"] == "+"
