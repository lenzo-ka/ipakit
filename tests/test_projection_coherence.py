"""A unit may not contradict a projection its own bundle states.

`ipa.xml` declares `phonation` and `voiced` to be one glottal fact at two
granularities: *"Every phonation already fixes a voicing, so `voiced` is
what `phonation` looks like read two ways instead of four, not a second
dimension that happens to agree."* A bundle stating both, disagreeing,
therefore contradicts the file it was composed from.

Seventy-six composed units did, and it read out loud:

    describe("c̤")  ->  'voiceless breathy-voiced palatal plosive'
    describe("c̰")  ->  'voiceless creaky-voiced palatal plosive'

Neither the projection nor the composer was at fault. Two of the four
phonation marks declared the voicing their phonation fixes -- `̥` says
`voiced="-"`, `̬` says `voiced="+"` -- and two said nothing, so on a
voiceless base the breathy and creaky marks left the base's voicing
standing while adding a voiced phonation on top of it. An asymmetry in
the data, and the data is the place to fix it rather than teaching the
code to be clever. All four marks state it now.

The three candidate fixes, and why this one:

* **Resolve the projection at read time** -- rejected by the declaration
  itself, which says in as many words that nothing does: *"The
  projection is a fact about the phonetics, and it is read by the write
  side only."* It would also put the resolution in every read path
  (`features`, `scalar`, `compose`), which is the three-implementations
  shape this repo has already paid for once.
* **Refuse the composition** -- rejected by docs/ties.md: *"Composition
  is intent-driven ... the library does not judge well-formedness"*, and
  agreement is reported through `disagreements()`, never refereed. It
  would also take 76 units out of the corpus.
* **Let the marks say what they fix** -- what `<projections>` exists to
  license. That block is there precisely so `compose_unit` can tell a
  mark stating one fact twice (the devoicing ring) from one dragging an
  independent dimension along (the linguolabial mark), so a phonation
  mark declaring its own voicing is the shape the data was built for.

`voiced` is `mode="overriding"`, so the mark now replaces the base's
value rather than sitting beside it -- exactly as the devoicing ring
makes `d̥` voiceless rather than both-voiced.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.segment import APPROACH_MODE, modifier_mode, phase_keys

from tests.corpus import self_spelling_phones

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import check_projection_coherence  # noqa: E402

FEATURES = IPAFeatures()


def _corpus(ipa: IPAFeatures) -> list[str]:
    """Every unit the inventory spells back, bare and marked."""
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for phone in ipa.phones:
            for mark in ["", *ipa.diacritics]:
                unit = phone + mark
                try:
                    if ipa.segment(unit).to_ipa() == unit:
                        out.append(unit)
                except ValueError:
                    continue
    return out


class TestNoUnitContradictsAProjection:
    """The invariant, over the whole corpus rather than the two marks."""

    def test_the_shipped_inventory_passes_the_invariant(self) -> None:
        assert check_projection_coherence(FEATURES)

    def test_the_sweep_is_a_predicate_over_the_declaration(self) -> None:
        """Not a list of the 76. Every declared projection, applied to
        every unit the inventory spells, so a fifth phonation value or a
        new mark declaring one is covered the day it is added."""
        corpus = _corpus(FEATURES)
        assert len(corpus) > 5000, "sweep did not run"
        assert FEATURES.projections, "no projection declared; this is vacuous"
        contradicting = []
        checked = 0
        for unit in corpus:
            bundle = FEATURES.get_features(unit)
            for (fine, value), (coarse, reads) in FEATURES.projections.items():
                if bundle.get(fine) != value:
                    continue
                checked += 1
                if bundle.get(coarse, reads) != reads:
                    contradicting.append(unit)
        assert checked > 100, "no unit states a projected value; sweep is vacuous"
        assert contradicting == []

    def test_the_headline_sentences_no_longer_contradict_themselves(self) -> None:
        assert ipakit.describe("c̤") == "voiced breathy-voiced palatal plosive"
        assert ipakit.describe("c̰") == "voiced creaky-voiced palatal plosive"

    def test_every_phonation_mark_states_the_voicing_it_fixes(self) -> None:
        """The symmetry that was missing, as a property of the marks.

        Any mark declaring a value the projection covers must also
        declare what that value reads as -- otherwise the base's value
        survives and the two reads of one fact come apart.
        """
        checked = 0
        for symbol, mark in FEATURES.diacritics.items():
            stated = mark.features or {}
            for (fine, value), (coarse, reads) in FEATURES.projections.items():
                if stated.get(fine) != value:
                    continue
                checked += 1
                assert stated.get(coarse) == reads, (
                    f"{symbol!r} says {fine}={value!r} and does not say "
                    f"{coarse}={reads!r}"
                )
        assert checked == 4, f"{checked} phonation marks, was 4"

    def test_a_mark_that_goes_silent_again_is_caught(self) -> None:
        """The guard against the guard: it must fail on the old data."""
        import dataclasses

        broken = IPAFeatures()
        mark = broken.diacritics["̤"]
        broken.diacritics["̤"] = dataclasses.replace(
            mark,
            features={k: v for k, v in mark.features.items() if k != "voiced"},
        )
        assert not check_projection_coherence(broken)


class TestWhatTheFixDidNotChange:
    """The three things that had to hold, measured rather than assumed."""

    def test_the_devoiced_units_are_untouched(self) -> None:
        # 131 units read a devoiced phonation with voiced="-" and every
        # one of them is right: devoiced *means* voiceless, so the coarse
        # and fine reads already agreed.
        devoiced = [
            unit
            for unit in _corpus(FEATURES)
            if FEATURES.get_features(unit).get("phonation") == "devoiced"
        ]
        assert len(devoiced) == 131
        assert all(FEATURES.get_features(u).get("voiced") == "-" for u in devoiced)
        assert ipakit.describe("d̥") == "voiceless alveolar plosive"
        assert ipakit.describe("ɹ̥") == "voiceless alveolar approximant"

    def test_the_inventory_and_the_shipped_matrix_do_not_move(self) -> None:
        # Not one of the units that moved is a bare phone, so the 139
        # phones the confusion matrix is built over are untouched.
        assert len(self_spelling_phones()) == 139
        moved_marks = ("̤", "̰")
        assert not [p for p in FEATURES.phones if p.endswith(moved_marks)]
        assert ipakit.distance("t", "d") == pytest.approx(0.05)

    def test_composition_still_answers_the_marks_own_request(self) -> None:
        # The projection is what keeps `compose_unit` from calling a mark
        # that says one fact twice incoherent. Adding `voiced` to these
        # two marks leans on that, so it is asserted rather than hoped.
        assert FEATURES.compose_unit("ɹ", phonation="devoiced") == "ɹ̥"
        assert FEATURES.compose_unit("s", phonation="breathy") == "s̤"
        assert FEATURES.compose_unit("s", phonation="creaky") == "s̰"

    def test_the_marks_are_overriding_now_and_that_is_the_point(self) -> None:
        # A mark's mode is read off the features it declares, so stating
        # `voiced` moves these two into the bucket the devoicing ring was
        # always in. That is what makes the mark replace the base's
        # voicing rather than sit beside it.
        for symbol in ("̤", "̰", "̥", "̬"):
            assert modifier_mode(FEATURES, symbol) == "overriding", symbol

    def test_asking_to_voice_a_segment_does_not_make_it_breathy(self) -> None:
        """The consequence the data fix would have had, and does not.

        A projection is many to one: `ipa.xml` says creaky, modal and
        breathy "all read voiced='+' without being interchangeable with
        each other". Once all three rings declare `voiced="+"`, all
        three answer a request for it and all three pass the coherence
        screen, so `declaring_mark` has to choose -- and by declaration
        order it chose the breathy ring, making
        `compose_unit("s", voiced="+")` spell `s̤`. Voicing assimilation
        would have started producing breathy segments.

        The choice is now the data's: a `label` is where `ipa.xml` says
        a value is worth saying out loud, so a surplus carrying one is a
        second fact rather than a restatement. `modal` and `devoiced`
        declare none, `breathy` and `creaky` do.
        """
        assert FEATURES.compose_unit("s", voiced="+") == "s̬"
        assert FEATURES.compose_unit("ɹ", voiced="-") == "ɹ̥"
        # The declaration this rests on, so it fails rather than drifting
        # if a label is added or removed.
        labels = FEATURES.features["phonation"].labels
        assert labels == {"creaky": "creaky-voiced", "breathy": "breathy-voiced"}
        assert FEATURES.declaring_mark("voiced", "+") == (
            list(FEATURES.diacritics).index("̬"),
            "̬",
        )

    def test_the_tiebreak_changes_exactly_one_answer(self) -> None:
        """Swept over every declared value, not sampled.

        Seven declared values have several equally specific marks. Six
        of those are pairs of marks with *identical* declarations, where
        declaration order was already the whole of the choice and the
        new key cannot separate them. `voiced="+"` is the seventh.
        """
        pairs = sorted(
            {
                (key, value)
                for mark in FEATURES.diacritics.values()
                for key, value in (mark.features or {}).items()
                if key not in ("name", "class", "href", "xsampa")
            }
        )
        assert len(pairs) > 50, "sweep did not run"

        def stated(symbol: str, key: str) -> tuple[tuple[str, str], ...]:
            """What a mark says where a request for ``key`` is written.

            Specificity is measured over the placement, not over the whole
            declaration, because that is what `declaring_mark` measures: a
            mark stating one key at each phase says one thing at each end,
            and counting both would make `ʰ` look less specific about an
            aspirated release than `ʻ`, which says the same thing and is
            the spelling nobody writes.
            """
            approach = key in FEATURES.features_by_mode.get(APPROACH_MODE, frozenset())
            here = phase_keys(FEATURES, symbol, approach)
            bundle = FEATURES.diacritics[symbol].features or {}
            return tuple(sorted((k, v) for k, v in bundle.items() if k in here))

        contested = {}
        for key, value in pairs:
            candidates = [
                (len(stated(s, key)), s)
                for s, m in FEATURES.diacritics.items()
                if (m.features or {}).get(key) == value
            ]
            best = min(c[0] for c in candidates)
            tied = [s for size, s in candidates if size == best]
            if len(tied) > 1:
                contested[(key, value)] = tied
        assert len(contested) == 7, sorted(contested)

        separable = {
            pair: tied
            for pair, tied in contested.items()
            if len({stated(s, pair[0]) for s in tied}) > 1
        }
        assert list(separable) == [("voiced", "+")], sorted(separable)

    def test_silence_itself_is_still_not_a_speech_sound(self) -> None:
        # `␣` takes no defaults, so it carries no voicing until a mark
        # puts one there. Bare silence is exactly 1.0 from every speech
        # sound, before and after.
        assert "voiced" not in FEATURES.get_features("␣")
        assert ipakit.distance("␣", "a") == 1.0
        assert ipakit.distance("␣", "t") == 1.0
        # The two marked-silence units are the only movers that *gained*
        # a key rather than changing one, and they are named here so the
        # consequence stays visible rather than buried in a count.
        assert FEATURES.get_features("␣̤").get("voiced") == "+"
        assert FEATURES.get_features("␣̰").get("voiced") == "+"
