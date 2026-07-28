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
    """A tie that binds nothing is read, not raised on.

    `_is_composable` once accepted a SEQ chain whose block ended in an
    over-tie, because `_parse_constituent` took the dangling glyph as a
    modifier. The fused merge then split that block on the tie and raised
    on the empty part it had manufactured -- the two halves of one path
    disagreeing about whether the same string resolves.

    `_parse_constituent` no longer takes a tie as a modifier, so these now
    resolve the other way: the composed path declines them and the
    structured one reads them, dropping the unbound glyph as parse does.
    What is asserted here is the answer, not the route to it.
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


@pytest.fixture(scope="module")
def marked(ipa: IPAFeatures) -> list[tuple[str, str, str]]:
    """``(unit, base, mark)`` for every phone carrying every diacritic.

    Deliberately *not* filtered to what parses or re-emits: the question
    here is what the flat read does with a string it cannot fully place,
    and filtering those out would remove the whole subject.
    """
    return [(base + mark, base, mark) for base in ipa.phones for mark in ipa.diacritics]


def _is_tied(base: str) -> bool:
    """True if ``base`` is a tie composition rather than an atomic phone."""
    return TIE_BAR in base or SEQ_TIE in base


class TestAMarkIsTakenTheSameWhateverTheBaseIsMadeOf:
    """A trailing stress mark was refused on an atomic base and taken on
    a tied one.

    ``get_features("tˈ")`` was ``{}`` and warned that the mark binds the
    unit *after* it; ``get_features("t͡sˈ")`` and ``get_features("a͜sˈ")``
    returned full bundles and said nothing, and ``describe("a͜sˈ")`` read
    the string as if the mark were not written. The two answers came from
    two pieces of code: the atomic base went through the structured parse,
    while a tie composition went through ``_parse_constituent``, which took
    any registered diacritic as a modifier of its base -- including the
    stress marks that ``_modifier_run``, the parse's own rule for how far a
    unit extends, exists to stop at.

    The guard is not the 46 registered strings that showed it. It is the
    two predicates they broke, swept over bases of both shapes.
    """

    def test_the_sweep_is_wide(self, marked: list[tuple[str, str, str]]) -> None:
        # Vacuous-sweep guard, and both shapes have to be in it: an
        # inventory that lost its tie compositions would make the
        # comparison below true by having nothing to compare.
        assert len(marked) > 5_000
        shapes = {_is_tied(base) for _, base, _ in marked}
        assert shapes == {True, False}

    def test_a_mark_is_taken_or_refused_by_shape_alone(
        self, ipa: IPAFeatures, marked: list[tuple[str, str, str]]
    ) -> None:
        """Whether ``base + mark`` reads is a property of the mark, not of
        whether ``base`` happens to be a tie composition."""
        taken: dict[tuple[str, bool], set[bool]] = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for unit, base, mark in marked:
                key = (mark, _is_tied(base))
                taken.setdefault(key, set()).add(bool(ipa.get_features(unit)))
        for mark in ipa.diacritics:
            atomic, tied = taken[(mark, False)], taken[(mark, True)]
            assert atomic == tied, (mark, atomic, tied)

    def test_a_bundle_accounts_for_the_whole_string(
        self, ipa: IPAFeatures, marked: list[tuple[str, str, str]]
    ) -> None:
        """The flat read answers with a bundle exactly when the unit's
        parse can place every substantive character it was given.

        The converse matters as much as the direction: a mark the parse
        drops must not come back as an answer, and a mark it does place
        must not be turned away.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for unit, _, _ in marked:
                assert bool(ipa.get_features(unit)) == _accounted(ipa, unit), unit

    def test_it_holds_for_chains_the_inventory_does_not_register(
        self, ipa: IPAFeatures
    ) -> None:
        """``a͜sˈ`` is not a registered phone, and the defect reached every
        chain like it -- a far wider surface than the 46 registered
        strings. Sampled rather than exhaustive, for run time."""
        atomic = [p for p in ipa.phones if not _is_tied(p)]
        sample = atomic[::4]
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for head in sample:
                for tail in sample:
                    for tie in (TIE_BAR, SEQ_TIE):
                        for mark in ("", *ipa.stress_markers, "ː", "̃", "ʰ", "|"):
                            unit = head + tie + tail + mark
                            assert bool(ipa.get_features(unit)) == _accounted(
                                ipa, unit
                            ), unit
                            checked += 1
        assert checked > 5_000, "sweep did not run"

    def test_the_refusal_is_reported_whatever_the_base(self, ipa: IPAFeatures) -> None:
        """Silence was half the defect: the tied read dropped the mark
        without the warning the atomic read gives."""
        for unit in ("tˈ", "t͡sˈ", "a͜sˈ", "aˌ", "a͜ɪˌ"):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assert ipa.get_features(unit) == {}, unit
            assert caught, unit
            assert "stress mark" in str(caught[0].message), unit
            assert ipa.describe(unit) == f"unknown phone: {unit}"


def _accounted(ipa: IPAFeatures, text: str) -> bool:
    """True if the unit ``text`` parses to one that re-emits every
    substantive character of it.

    The same comparison ``_modified_features`` makes, by character
    multiset and with structural marks excluded on both sides: a unit
    emits its marks in its own order, and the linking undertie belongs to
    no unit at all, so what is asked is that nothing was lost, not that
    nothing moved. Unicode is canonicalized first because ``to_ipa``
    emits composed forms and the caller may have written decomposed ones.
    """
    text = ipa.canonicalize_unicode(text)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            emitted = ipa.segment(text).to_ipa()
        except ValueError:
            return False

    def substantive(s: str) -> list[str]:
        return sorted(ch for ch in s if not ipa.is_structural_token(ch))

    return substantive(emitted) == substantive(text)
