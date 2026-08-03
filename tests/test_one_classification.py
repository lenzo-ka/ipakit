"""What a unit is gets decided once, and every read is that decision.

Three defects filed separately were one defect wearing three faces --
two reads of one question, kept in step by vigilance instead of by
construction:

    describe("n͡d") == describe("d͡n") == 'voiced alveolar affricate'
    segment("n͡d").kind.value                      # 'prenasalized'

    segment("t͡d").kind.value                      # 'double-articulation'
    segment("t͡d").scalar()["place"]               # 'alveolar' -- one place

    takes_defaults(ipa, bundle)                    # False
    fill_defaults(ipa, bundle) is bundle           # filled it anyway

In each pair the two answers were computed by different code from
different inputs, and they agreed on the cases anyone had looked at. The
fix in each was to delete one of the two answers rather than correct it,
so the tests here are not a list of the units that used to be wrong.
They are the shapes:

* nothing is *projected* as an affricate that is not *classified* one;
* nothing is *classified* a double articulation that is not *spelled*
  with two places;
* nothing is filled with defaults that the public decision refuses.

The sweep is every over-tie pair the inventory can spell, which is what
makes these claims rather than hopes -- a named case would have passed on
the pre-fix tree for every one of the three. What it cannot see is
deliberately narrow and stated in ``test_the_sweep_states_what_it_misses``.
"""

from __future__ import annotations

import warnings

import pytest
from ipakit import IPAFeatures, Kind, Segment
from ipakit.segment import (
    Constituent,
    combining_place,
    fill_defaults,
    part_bundle,
    takes_defaults,
)

# Floors, not pins: the inventory has moved three times in this repo's
# history. They exist so a sweep that has quietly stopped composing fails
# loudly instead of reporting a clean run over nothing.
MIN_FUSIONS = 5000
MIN_PER_KIND = 20


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


@pytest.fixture(scope="module")
def fusions(ipa: IPAFeatures) -> list[tuple[str, Segment]]:
    """Every ``a͡b`` over the inventory that parses and re-emits itself.

    The over-tie because that is where the classification does its work:
    a sequential chain projects its first block and is read no further.
    Re-emission rather than strict parsing, for the reason
    ``scripts/sweep.py`` gives -- a strict-parse corpus measures the
    parser's error policy as much as the inventory.
    """
    out: list[tuple[str, Segment]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for first in ipa.phones:
            for second in ipa.phones:
                text = first + ipa.tie_bar + second
                try:
                    unit = ipa.segment(text)
                except ValueError:
                    continue
                if unit.to_ipa() != text or len(unit.constituents) != 2:
                    continue
                out.append((text, unit))
    return out


def _places(ipa: IPAFeatures, unit: Segment) -> set[str]:
    """The places this unit's constituents state, each on its own."""
    return {
        bundle["place"]
        for c in unit.constituents
        if "place" in (bundle := part_bundle(ipa, c))
    }


class TestTheSweepIsNotVacuous:
    def test_the_corpus_holds(self, fusions: list[tuple[str, Segment]]) -> None:
        assert len(fusions) > MIN_FUSIONS

    def test_every_reading_is_exercised(
        self, fusions: list[tuple[str, Segment]]
    ) -> None:
        """Each thing the classification can say, said by something here.

        Without this the three predicates below could all hold by there
        being no prenasalized stop and no double articulation in the
        sweep at all, which is exactly how an instrument reads zero.
        """
        seen = [unit.kind for _, unit in fusions]
        for kind in (
            Kind.AFFRICATE,
            Kind.PRENASALIZED,
            Kind.PRE_STOPPED,
            Kind.LATERAL_RELEASE,
            Kind.CLICK_ACCOMPANIMENT,
            Kind.DOUBLE_ARTICULATION,
            Kind.OVERLAY,
        ):
            assert seen.count(kind) > MIN_PER_KIND, kind

    def test_the_sweep_states_what_it_misses(
        self, fusions: list[tuple[str, Segment]]
    ) -> None:
        """The limits, asserted so they stay known rather than assumed shut.

        Two constituents and no marks: an n-ary fusion and a marked
        constituent reach the same functions by the same route, and the
        cases that need those are named in ``test_segment.py`` and
        ``test_one_composition.py``. If either starts appearing here, the
        sweep got wider and this is the place that says so.
        """
        assert all(len(unit.constituents) == 2 for _, unit in fusions)
        assert not [
            text
            for text, unit in fusions
            if any(c.modifiers or c.approach for c in unit.constituents)
        ]


class TestTheProjectionSaysWhatTheClassificationSays:
    """#130: a prenasalized stop was projected ``manner="affricate"``
    while ``kind`` called it prenasalized, so ``describe`` gave two
    distinct units one name.

    Not the metric, though the issue says so: ``segment_metric``
    compares constituents and never reads the flat projection, and the
    measurement bears that out -- 9901 units changed their projected
    manner here and not one of their distances moved with it. What the
    flat manner does reach is every read built on ``get_features``:
    ``describe``, ``compose``, the natural-class terms a rule matches on
    (``n͡d`` answered to ``[obstruent]``), and ``to_phone``.
    """

    def test_only_an_affricate_is_projected_as_one(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        offenders = []
        for text, unit in fusions:
            if unit.scalar(with_defaults=False).get("manner") != "affricate":
                continue
            if unit.kind is Kind.AFFRICATE:
                continue
            # A constituent that is itself an affricate carries the value
            # into the merge on its own account; that is the merge
            # working, not the collapse.
            if any(
                part_bundle(ipa, c).get("manner") == "affricate"
                for c in unit.constituents
            ):
                continue
            offenders.append((text, unit.kind.value))
        assert offenders == []

    def test_an_affricate_is_projected_as_one(
        self, fusions: list[tuple[str, Segment]]
    ) -> None:
        assert [
            text
            for text, unit in fusions
            if unit.kind is Kind.AFFRICATE
            and unit.scalar(with_defaults=False).get("manner") != "affricate"
        ] == []

    def test_a_phase_is_not_a_manner(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        """A unit read as a phase keeps the manner its parts state.

        The named consequence: `n͡d` is a stop and `d͡n` is a nasal, and
        the two no longer describe alike.
        """
        phased = {
            text: unit.scalar(with_defaults=False).get("manner")
            for text, unit in fusions
            if unit.kind in (Kind.PRENASALIZED, Kind.PRE_STOPPED)
        }
        assert "affricate" not in phased.values()
        assert ipa.describe("n͡d") != ipa.describe("d͡n")


class TestADoubleArticulationIsTwoPlaces:
    """#142: ``kind`` called every single-block fusion a double
    articulation without asking whether its constituents differ in place,
    while the projection beside it used differing place as its
    criterion."""

    def test_the_name_needs_the_places(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        assert [
            text
            for text, unit in fusions
            if unit.kind is Kind.DOUBLE_ARTICULATION and len(_places(ipa, unit)) < 2
        ] == []

    def test_the_spelling_needs_the_places(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        """No unit is spelled with a combining place its parts do not have."""
        place = ipa.features["place"]
        offenders = []
        for text, unit in fusions:
            projected = unit.scalar(with_defaults=False).get("place")
            if projected is None or len(place.expand(projected)) < 2:
                continue
            stated = _places(ipa, unit)
            if len(stated) > 1 or any(len(place.expand(p)) > 1 for p in stated):
                continue
            offenders.append(text)
        assert offenders == []

    def test_the_name_and_the_spelling_are_one_decision(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        """Wherever a combining place is spelled, something says so.

        The construction, stated: a fusion is named a double articulation
        exactly where the projection has a combining place to write, and
        a click accompaniment is the one reading that carries the
        spelling under another name (a click *has* a double articulation;
        it is classified by its airstream first).
        """
        for text, unit in fusions:
            bundles = [part_bundle(ipa, c) for c in unit.constituents]
            combined = combining_place(ipa, bundles) is not None
            named = unit.kind in (Kind.DOUBLE_ARTICULATION, Kind.CLICK_ACCOMPANIMENT)
            assert combined <= named, text
            if unit.kind is Kind.DOUBLE_ARTICULATION:
                assert combined, text


class TestAlignmentModeIsAskedOfTheStructure:
    """The metric aligns ordered where part order is meaning. It read
    that off a list of ``Kind`` names, which held only while every
    single-block fusion was called a double articulation: renaming one
    for having a single place would have changed how it aligns, silently.
    """

    def test_one_timing_slot_at_one_manner_reverses_for_free(
        self, ipa: IPAFeatures, fusions: list[tuple[str, Segment]]
    ) -> None:
        """Two constituents of one manner fused into one slot have no
        phase between them, so writing them the other way round is the
        same unit and costs nothing; two manners are a phase order, and
        reversing it is a different unit.

        Stated over the constituents' declared manners rather than over
        :attr:`Segment.phased`, because the metric asks ``phased`` and a
        test that asked it too would agree with the metric however wrong
        both were.
        """
        checked = both = 0
        for text, unit in fusions:
            first, second = (c.base for c in unit.constituents)
            if first == second:
                continue
            reverse = second + ipa.tie_bar + first
            if ipa.segment(reverse).to_ipa() != reverse:
                continue
            manners = {
                phone.features.get("manner")
                for c in unit.constituents
                if (phone := ipa.get_phone(c.base)) is not None
            }
            simultaneous = len(manners) == 1
            both += simultaneous
            checked += 1
            assert (ipa.distance(text, reverse) == 0.0) is simultaneous, (
                text,
                unit.kind.value,
            )
        assert checked > MIN_FUSIONS and both > MIN_PER_KIND


class TestDefaultsAreOneDecision:
    """#144: ``fill_defaults`` filled a bundle that ``takes_defaults``
    says takes none, in place, so a structural zero acquired an airstream
    and a channel."""

    @pytest.fixture(scope="class")
    def bundles(self, ipa: IPAFeatures) -> list[dict[str, str]]:
        """Bundles from every direction a caller can reach these with.

        Including the ones with no manner in them, which is the whole
        case: a declared zero's ``class`` is dropped from a feature bag
        and what is left states nothing to constrict with.
        """
        out: list[dict[str, str]] = [{}, {"class": "phone"}]
        for name in [*ipa.phones, *ipa.zeros]:
            constituent = Constituent(base=name)
            for metadata in (False, True):
                out.append(
                    constituent.bundle(ipa, with_defaults=False, metadata=metadata)
                )
        return out

    def test_a_refused_bundle_is_left_alone(
        self, ipa: IPAFeatures, bundles: list[dict[str, str]]
    ) -> None:
        for bundle in bundles:
            if takes_defaults(ipa, bundle):
                continue
            assert fill_defaults(ipa, dict(bundle)) == bundle

    def test_the_refusal_is_reachable_and_the_filling_still_happens(
        self, ipa: IPAFeatures, bundles: list[dict[str, str]]
    ) -> None:
        """Both sides exercised, so neither test above can pass vacuously."""
        refused = [b for b in bundles if not takes_defaults(ipa, b)]
        taken = [b for b in bundles if takes_defaults(ipa, b)]
        assert len(refused) > 2 and len(taken) > 100
        assert any(fill_defaults(ipa, dict(b)) != b for b in taken)

    def test_a_declared_zero_stays_empty(self, ipa: IPAFeatures) -> None:
        """The case that named the defect, as a case."""
        for name in ipa.zeros:
            assert Constituent(base=name).bundle(ipa, with_defaults=True) == {}
