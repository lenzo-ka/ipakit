"""What two marks stating one feature mean, on the way in and on the way out.

The write side and the read side answered this differently, and neither
half of the disagreement was the interesting one.

``compose_unit`` will not spell a unit whose mark stack states one feature
twice: a mark already on the base gives way to the mark writing the same
key rather than standing beside it, so ``aʱ`` asked for an aspirated
release is ``aʰ`` and never ``aʰʱ``. The flat read accepted such a stack
in silence and assigned a value off the order the marks happened to be
written in -- ``compose("ɛ̥̤")`` was breathy and ``compose("ɛ̤̥")``
devoiced, from two marks the writer would not put on one segment at all.

But "the write side refuses it" was only ever true of *single-valued*
features. ``ipa.xml`` declares ``sequence="+"`` on ``tone`` and
``contour``, and the prosody writer emits exactly the stack in question:
``rewrite("ka", "[vowel] -> [tone=top>bottom]")`` is ``ka˥˩``, two marks
stating one feature, because a contour *is* a run of levels. So the
composition rule is not a choice to be made here -- it is declared, it has
two branches, and :func:`~ipakit.form._asserted_prosody` was already
reading both while the segmental read had neither. The one that hurt was
the sequence branch: ``units("a˧˦")[0].prosody`` said
``tone="mid>high"`` and ``compose("a˧˦")`` said ``tone="mid"``, two reads
of one token disagreeing about the same key, with ``ipa.xml``'s own
comment asserting the equivalence they broke.

Both are :func:`~ipakit.segment.state_mark_value` now, called by the
segmental read and the prosodic one, so they cannot come apart again.

The sweeps below are over the extent that reaches the question: a base
plus **two** marks. The canonical corpus of ``scripts/sweep.py`` is a base
plus one, and one mark cannot state a feature twice -- captured before and
after this change it moves 0 of 9450 units, which is a true measurement of
nothing. Over the two-mark extent 30024 of 382130 units move.
"""

from __future__ import annotations

import warnings

import pytest
from ipakit import IPAFeatures
from ipakit.constants import DATA_DIR, METADATA_ATTRS
from ipakit.form import units
from ipakit.segment import phase_keys

FEATURES = IPAFeatures()

#: How much of the two-mark extent to sweep: one base in this many. The
#: whole of it is 382130 units and minutes of runtime; what interacts here
#: is a pair of *marks*, and every pair is tried against every sampled
#: base, so the base enters only through Unicode recomposition. Same
#: reasoning, and the same shape, as ``tests.corpus.prosody_bearing_units``.
BASE_STRIDE = 11


def _spells(unit: str) -> bool:
    try:
        return FEATURES.segment(unit).to_ipa() == unit
    except Exception:  # noqa: BLE001 - not self-spelling either way
        return False


def sequence_features() -> set[str]:
    """The features whose values are trajectories, read off the data.

    Nothing in this file names ``tone``: which features compose rather
    than contradict is ``ipa.xml``'s to say, and a test that pasted the
    answer would agree with a read that had stopped asking.
    """
    return {name for name, feat in FEATURES.features.items() if feat.sequence}


def stack_statements(unit: str) -> list[tuple[str, str, str, bool]]:
    """Every ``(glyph, key, value, approach)`` the marks of ``unit`` state.

    Read off the declarations and the placement, exactly as the reader
    does, so what a mark says *where it stands* is what is compared:
    ``ʰ`` before a base states an approach and after it a release, and
    those are not one key stated twice.
    """
    seg = FEATURES.segment(unit)
    out: list[tuple[str, str, str, bool]] = []
    for part in seg.constituents:
        for glyphs, approach in ((part.approach, True), (part.modifiers, False)):
            for glyph in glyphs:
                mark = FEATURES.diacritics.get(glyph)
                for key in sorted(phase_keys(FEATURES, glyph, approach)):
                    if key in METADATA_ATTRS or mark is None:
                        continue
                    out.append((glyph, key, mark.features[key], approach))
    for glyph in seg.prosody:
        mark = FEATURES.diacritics.get(glyph)
        for key, value in (getattr(mark, "features", None) or {}).items():
            if key not in METADATA_ATTRS:
                out.append((glyph, key, value, False))
    return out


def restated(unit: str) -> dict[str, list[str]]:
    """The keys two marks of one stack both state, and what each said.

    Keyed by feature; only the keys stated more than once appear.
    """
    seen: dict[tuple[str, bool], list[str]] = {}
    for _glyph, key, value, approach in stack_statements(unit):
        seen.setdefault((key, approach), []).append(value)
    return {key: vals for (key, _ap), vals in seen.items() if len(vals) > 1}


@pytest.fixture(scope="module")
def two_mark_units() -> list[str]:
    """Self-spelling base + two trailing marks, one base in ``BASE_STRIDE``."""
    phones = [p for p in FEATURES.phones if _spells(p)]
    out: list[str] = []
    for index, base in enumerate(phones):
        if index % BASE_STRIDE:
            continue
        for first in FEATURES.diacritics:
            if not _spells(base + first):
                continue
            out.extend(
                base + first + second
                for second in FEATURES.diacritics
                if _spells(base + first + second)
            )
    return out


@pytest.fixture(scope="module")
def restating_units(two_mark_units: list[str]) -> dict[str, dict[str, list[str]]]:
    """Those of them whose two marks state one feature twice."""
    return {unit: found for unit in two_mark_units if (found := restated(unit))}


class TestTheExtentIsTheOneThatReachesTheQuestion:
    def test_the_sweep_ran_and_holds_both_classes(self, restating_units) -> None:
        """A floor cannot tell that one branch of the rule went missing.

        Both are asserted separately, because the whole finding is that
        they are two different answers to one question: a stack restating
        a sequence-valued feature composes, one restating any other
        contradicts.
        """
        assert len(restating_units) > 2000, f"sweep did not run: {len(restating_units)}"
        sequenced = sequence_features()
        composing = [u for u, r in restating_units.items() if set(r) & sequenced]
        conflicting = [u for u, r in restating_units.items() if set(r) - sequenced]
        assert len(composing) > 1000, f"no composing stacks: {len(composing)}"
        assert len(conflicting) > 500, f"no conflicting stacks: {len(conflicting)}"

    def test_one_mark_cannot_reach_it(self) -> None:
        """Why the canonical corpus measures nothing here, said out loud.

        ``scripts/sweep.py``'s corpus is a base plus one mark. If a mark
        ever declared one feature twice this would fail, and the sweep in
        this file would no longer be the only one that sees the question.
        """
        singles = [
            base + mark
            for base in list(FEATURES.phones)[::BASE_STRIDE]
            for mark in FEATURES.diacritics
            if _spells(base + mark)
        ]
        assert len(singles) > 500, f"sweep did not run: {len(singles)}"
        assert not [u for u in singles if restated(u)]


class TestASequenceValuedFeatureComposes:
    """Declared ``sequence="+"``, so a run of marks states a trajectory."""

    @pytest.mark.parametrize(
        ("form", "value"),
        [("a˧˦", "mid>high"), ("a˥˩", "top>bottom"), ("a˧˩˧", "mid>bottom>mid")],
    )
    def test_the_flat_read_keeps_the_whole_run(self, form: str, value: str) -> None:
        assert FEATURES.compose(form, with_defaults=False)[0]["tone"] == value

    def test_the_two_spellings_of_one_contour_read_alike_flat_too(self) -> None:
        """``ipa.xml`` asserts ``a᷄ == a˧˦``; this is the read that broke it."""
        assert (
            FEATURES.compose("a᷄", with_defaults=False)[0]["tone"]
            == FEATURES.compose("a˧˦", with_defaults=False)[0]["tone"]
        )

    def test_the_flat_read_and_the_unit_read_agree_over_the_sweep(
        self, restating_units
    ) -> None:
        """The two reads of one token, on every key both of them state.

        ``compose()`` and ``Unit.prosody`` diverge by design on *where* a
        prosodic value is reported (docs/ties.md). They may not diverge on
        what it is.
        """
        sequenced = sequence_features()
        checked, disagreed = 0, []
        for unit, found in restating_units.items():
            if not set(found) & sequenced:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                flat = FEATURES.compose(unit, with_defaults=False)[0]
                prosody = units(unit, FEATURES)[0].prosody
            for key in set(found) & sequenced:
                checked += 1
                if flat.get(key) != prosody.get(key):
                    disagreed.append((unit, key, flat.get(key), prosody.get(key)))
        assert checked > 1000, f"sweep did not run: {checked}"
        assert not disagreed, f"{len(disagreed)} disagreed, first: {disagreed[:3]}"

    def test_every_composing_stack_keeps_every_step(self, restating_units) -> None:
        """The predicate, not the three named runs: the value a stack reads
        back with is the concatenation of what its marks declare, in the
        order they stand."""
        sequenced = sequence_features()
        checked, dropped = 0, []
        for unit, found in restating_units.items():
            for key in set(found) & sequenced:
                feature = FEATURES.features[key]
                want = [step for value in found[key] for step in feature.steps(value)]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    got = FEATURES.compose(unit, with_defaults=False)[0].get(key)
                checked += 1
                if got is None or list(feature.steps(got)) != want:
                    dropped.append((unit, key, got, want))
        assert checked > 1000, f"sweep did not run: {checked}"
        assert not dropped, f"{len(dropped)} dropped a step, first: {dropped[:3]}"


class TestASingleValuedFeatureContradicts:
    """Not declared ``sequence``, so a second statement is not a stack."""

    def test_the_reported_case(self) -> None:
        with pytest.warns(UserWarning, match="two marks state 'phonation'"):
            FEATURES.compose("ɛ̥̤", with_defaults=False)

    def test_the_report_names_what_contradicts_what(self) -> None:
        """A diagnostic that does not say which two values collided leaves
        the caller no better off than the silent answer did."""
        with pytest.warns(UserWarning) as caught:
            FEATURES.compose("ɛ̥̤", with_defaults=False)
        text = " ".join(str(w.message) for w in caught)
        assert "'devoiced' then 'breathy'" in text
        assert "single-valued" in text
        assert "'ɛ̥̤'" in text

    def test_the_write_side_will_not_spell_what_this_reports(self) -> None:
        """The asymmetry the finding was about, pinned from the other end.

        Asked for a breathy phonation, ``compose_unit`` evicts the
        devoicing ring instead of standing a second mark beside it, so no
        composition can produce a unit this read has to report.
        """
        assert FEATURES.compose_unit("ɛ̥", phonation="breathy") == "ɛ̤"
        assert not restated("ɛ̤")

    def test_every_conflicting_stack_is_reported(self, restating_units) -> None:
        """Swept, and over the shape: every stack whose marks state one
        single-valued feature with two values warns, naming that feature."""
        sequenced = sequence_features()
        checked, silent = 0, []
        for unit, found in restating_units.items():
            contested = {
                key: vals
                for key, vals in found.items()
                if key not in sequenced and len(set(vals)) > 1
            }
            if not contested:
                continue
            checked += 1
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                FEATURES.compose(unit, with_defaults=False)
            said = " ".join(str(w.message) for w in caught)
            missing = [key for key in contested if repr(key) not in said]
            if missing:
                silent.append((unit, missing))
        assert checked > 500, f"sweep did not run: {checked}"
        assert not silent, f"{len(silent)} silent, first: {silent[:3]}"

    def test_a_restatement_that_agrees_is_not_a_contradiction(
        self, restating_units
    ) -> None:
        """``ɪ̃̃`` says nasalized twice and says the same thing twice.

        A misspelling (``validate_ipa`` calls it ``duplicate_diacritic``)
        but not a contradiction, so this read has nothing to report about
        it. Without this the guard above would pass just as well on a
        predicate that warned about every repeated key.
        """
        sequenced = sequence_features()
        checked, noisy = 0, []
        for unit, found in restating_units.items():
            if any(
                key in sequenced or len(set(vals)) > 1 for key, vals in found.items()
            ):
                continue
            checked += 1
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                FEATURES.compose(unit, with_defaults=False)
            if caught:
                noisy.append((unit, str(caught[0].message)))
        assert checked > 200, f"sweep did not run: {checked}"
        assert not noisy, f"{len(noisy)} reported a non-contradiction: {noisy[:3]}"


class TestWhichBranchAppliesIsDeclaredAndNotKnown:
    """The rule follows ``sequence="+"`` wherever the data puts it.

    A read that had the answer written into it would agree with the
    shipped file and disagree with any other, which is the shape
    ``tests/test_declared_not_hardcoded.py`` exists to reject. So the
    declaration is moved and the read is required to move with it -- in
    both directions, because a check that only removes a declaration would
    pass on code that had simply stopped composing anything.
    """

    TONE = '<feature name="tone" axis="+f0" short="ton" mode="prosodic" sequence="+"'
    RELEASE = '<feature name="release" type="categorical" short="rel" mode="release"'

    def _load(self, tmp_path, old: str, new: str) -> IPAFeatures:
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        assert text.count(old) == 1, f"{old!r} moved; fix this test"
        path = tmp_path / "ipa.xml"
        path.write_text(text.replace(old, new), encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_the_unmodified_data_composes(self, tmp_path) -> None:
        """So a failure below is the edit and not the harness."""
        ipa = self._load(tmp_path, self.TONE, self.TONE)
        assert ipa.compose("a˧˦", with_defaults=False)[0]["tone"] == "mid>high"

    def test_undeclaring_the_sequence_makes_the_run_a_contradiction(
        self, tmp_path
    ) -> None:
        ipa = self._load(tmp_path, self.TONE, self.TONE.replace(' sequence="+"', ""))
        with pytest.warns(UserWarning, match="two marks state 'tone'"):
            assert ipa.compose("a˧˦", with_defaults=False)[0]["tone"] == "mid"

    def test_declaring_it_elsewhere_makes_that_run_compose(self, tmp_path) -> None:
        """``release`` is single-valued in the shipped file, so ``tʰ̚``
        contradicts. Declared a sequence, the same two marks compose, with
        nothing in the reader edited."""
        ipa = self._load(tmp_path, self.RELEASE, self.RELEASE + ' sequence="+"')
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            got = ipa.compose("tʰ̚", with_defaults=False)[0]["release"]
        assert got == "aspirated>no-audible"


class TestTheTwoReadsAreOneImplementation:
    def test_the_prosodic_read_and_the_segmental_one_are_one_function(self) -> None:
        """Made equal by construction rather than checked to agree.

        If these ever become two functions again, ``docs/reviewing.md``
        records what happens next.
        """
        # By ``sys.modules`` because ``ipakit.form`` names a function on
        # the package as well as the module under it.
        import sys

        form = sys.modules["ipakit.form"]
        segment = sys.modules["ipakit.segment"]
        assert form.state_mark_value is segment.state_mark_value

    def test_the_metric_does_not_see_this(self) -> None:
        """Pin the escape. No registered phone's spelling states one
        feature twice, so nothing in this change can move a distance, and
        a sweep over the matrix would be a measurement of nothing."""
        doubled = [p for p in FEATURES.phones if _spells(p) and restated(p)]
        assert not doubled, doubled[:5]
        assert len(FEATURES.phones) > 100, "the inventory went empty"
