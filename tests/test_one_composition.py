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
from unittest import mock

import pytest
from ipakit import IPAFeatures, Phone, Segment
from ipakit.analysis import _VOWEL_SLOTS as VOWEL_SLOTS
from ipakit.constants import METADATA_ATTRS

from tests.corpus import TIES

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
                for tie in sorted(TIES):
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

    @pytest.mark.slow
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
        # A value in the projection is built out of values some
        # constituent holds -- compared by components, because a
        # simultaneous fusion spells a disagreement as the combination of
        # the two, on any feature and not only on place. `manner` is the
        # exception: a differing pair collapses there to a name for the
        # whole unit (`affricate`) rather than to a combination of parts.
        derived = {"manner"}

        def components(key: str, value: str) -> tuple[str, ...]:
            feature = ipa.features.get(key)
            return feature.expand(value) if feature is not None else (value,)

        for text, unit in units:
            bag = unit.bag()
            for key, value in unit.scalar().items():
                if key in derived or key in METADATA_ATTRS or key not in bag:
                    continue
                held = {c for v in bag[key] for c in components(key, v)}
                assert set(components(key, value)) <= held, (
                    text,
                    key,
                    value,
                    bag[key],
                )


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
    return bool(TIES & set(base))


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
                    for tie in sorted(TIES):
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


def _vowel_letters(ipa: IPAFeatures) -> list[str]:
    """Every registered vowel that is one constituent and spells itself
    back: the atoms a fused pair is built from."""
    return [
        symbol
        for symbol, phone in ipa.phones.items()
        if phone.features.get("manner") == "vowel"
        and not ipa.tie_bars & set(symbol)
        and ipa.segment(symbol).to_ipa() == symbol
    ]


class TestAPrimarySlotCannotLeakAcrossTheMerge:
    """A constituent that *states* nothing leaves the other's value
    standing. That is the wanted rule for a modifier feature (``kʷ͡p``
    keeps ``labialized='+'``, ``ɚ͡ɜ`` stays r-colored), and it is a wrong
    answer for a slot the phone's own name is built from.

    Fourteen of the vowel letters declared no roundedness at all,
    leaning on the binary default, so the merge read their silence as
    "no opinion": ``features("u͡i")`` came out close, front and
    *rounded*, and ``to_phone`` of it was ``y`` -- a phone neither
    constituent is, and one nothing in the string spells. The fix is in
    the data (every vowel now states its own roundedness), and the
    guard is the sweep below rather than the case: a slot that goes
    unstated later fails here, not in whichever tie chain a caller
    happens to write.

    Two vowels fused are one manner and one phase, so since #155 the
    merge takes no value from either end in particular: it combines
    them. The mixture the defect produced cannot be spelled by a
    combination, which is why nothing here names a stranger any more.
    """

    def test_every_vowel_states_every_slot_of_its_own_name(
        self, ipa: IPAFeatures
    ) -> None:
        vowels = [
            symbol
            for symbol, phone in ipa.phones.items()
            if phone.features.get("manner") == "vowel"
        ]
        for symbol in vowels:
            declared = ipa.phones[symbol].features
            missing = [slot for slot in VOWEL_SLOTS if slot not in declared]
            assert not missing, f"{symbol!r} states no {missing}"
        assert len(vowels) > 30, "the vowel inventory collapsed; sweep is vacuous"

    def test_validate_reports_a_vowel_that_does_not(self, ipa: IPAFeatures) -> None:
        """The check above is the inventory's; this is the library's, so a
        caller's own ``ipa.xml`` is held to it too."""
        assert ipa.validate() == []
        for slot in VOWEL_SLOTS:
            stated = dict(ipa.phones["i"].features)
            stated.pop(slot)
            doctored = Phone(symbol="i", features=stated)
            with mock.patch.dict(ipa.phones, {"i": doctored}):
                assert f"Missing '{slot}' for vowel 'i'" in ipa.validate()

    def test_a_fused_vowel_pair_states_every_slot_from_both_vowels(
        self, ipa: IPAFeatures
    ) -> None:
        """Over every fused pair of vowel letters, not a sample.

        Every slot of a vowel's name is stated by the flat read, and
        what it states is what both constituents hold -- never one slot
        taken from one vowel while the next is taken from the other,
        which is the mixture that named ``y``. On a slot whose values are
        positions the claim is exact: the projection spells the
        combination of the two. ``rounded`` is binary, so a disagreement
        there has no combination to spell and resolves to the declared
        default; that its two values reach the merge at all is what
        ``test_every_vowel_states_every_slot_of_its_own_name`` above
        holds.

        Letters rather than every registered vowel: a chain holding a
        *sequential* juncture projects its first block instead of
        merging the whole of itself, so ``a͡a͜ɪ`` reads ``a͡a`` by rule
        and has no business being asked what its constituents say.
        """
        vowels = _vowel_letters(ipa)
        checked = combined = 0
        for first in vowels:
            for second in vowels:
                unit = first + ipa.tie_bar + second
                segment = ipa.segment(unit)
                if segment.to_ipa() != unit:
                    continue
                flat = ipa.get_features(unit, with_defaults=False)
                bag = segment.bag()
                for slot in VOWEL_SLOTS:
                    feature = ipa.features[slot]
                    assert slot in flat, (unit, slot)
                    held = {c for v in bag[slot] for c in feature.expand(v)}
                    stated = set(feature.expand(flat[slot]))
                    assert stated <= held, (unit, slot, flat[slot], bag[slot])
                    if not feature.is_binary:
                        assert stated == held, (unit, slot, flat[slot], bag[slot])
                        combined += len(stated) > 1
                checked += 1
        assert checked > 900, f"sweep covered only {checked} pairs"
        assert combined > 900, "no pair ever combined; the claim is vacuous"

    def test_the_flat_read_names_a_vowel_the_unit_spells(
        self, ipa: IPAFeatures
    ) -> None:
        """The consequence, and the shape of the reported defect: whatever
        ``to_phone`` answers for a fused vowel pair, it is one of the
        vowels written in it."""
        vowels = _vowel_letters(ipa)
        strangers = []
        for first in vowels:
            for second in vowels:
                unit = first + ipa.tie_bar + second
                segment = ipa.segment(unit)
                if segment.to_ipa() != unit:
                    continue
                named = ipa.to_phone(ipa.get_features(unit))
                spelled = {c.base for c in segment.constituents} | {unit}
                if named is not None and named not in spelled:
                    strangers.append((unit, named))
        assert strangers == []

    def test_a_modifier_feature_still_crosses_the_merge(self, ipa: IPAFeatures) -> None:
        """The rule the two remaining strangers used to demonstrate.

        ``rhotacized`` is a modifier feature, not a slot of a vowel's
        name, and a fused unit inheriting it from the one constituent
        that states it is the documented merge working. It used to make
        ``ɚ͡ɜ`` answer ``ɝ`` -- the registered r-colored open-mid central
        vowel -- because the height came whole from the last constituent;
        the two heights combine now, so the unit names no registered
        vowel while the r-coloring still reaches it.
        """
        flat = ipa.get_features("ɚ͡ɜ", with_defaults=False)
        assert flat["rhotacized"] == "+"
        assert "rhotacized" not in ipa.phones["ɜ"].features
        assert set(ipa.features["height"].expand(flat["height"])) == {"mid", "open-mid"}

    def test_the_reported_case_and_the_one_next_to_it(self, ipa: IPAFeatures) -> None:
        # Both reversals answer alike, and neither names a vowel: a fusion
        # of a front and a back vowel is in two places on the arc at once,
        # and no registered vowel is (#155). They answered `i` and `u`,
        # which is the last constituent on a unit that has no last.
        assert ipa.to_phone(ipa.get_features("u͡i")) is None
        assert ipa.to_phone(ipa.get_features("i͡u")) is None
        # Rule 3, and not a defect: a sequential chain projects its first
        # block, so its flat bundle is one constituent's and never
        # outranks the atom matching it equally well. An assessment
        # refuted the claim that this one is broken; it is pinned here so
        # the fix above cannot be widened onto it by mistake.
        assert ipa.to_phone(ipa.get_features("a͜ɪ")) == "a"
