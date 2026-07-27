"""Phase 4: the linking tier's tokenization and the agreement read.

Structural marks (the linking undertie, breaks) stand alone between
units instead of gluing onto the preceding token; disagreements() is a
diagnostic read over the union bag -- composition reports, never
referees.
"""

import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestStructuralMarksStandAlone:
    def test_linking_mark_separates_cleanly(self, ipa: IPAFeatures) -> None:
        # French liaison marking: the units around ‿ stay intact.
        assert ipa.tokenize("lez‿ami") == ["l", "e", "z", "‿", "a", "m", "i"]

    def test_breaks_separate_cleanly(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize("a|b") == ["a", "|", "b"]
        assert ipa.tokenize("a‖b") == ["a", "‖", "b"]

    def test_structural_marks_never_enter_segments(self, ipa: IPAFeatures) -> None:
        segs = ipa.segments("lez‿ami")
        assert [s.to_ipa() for s in segs] == ["l", "e", "z", "a", "m", "i"]
        assert all(not s.prosody for s in segs)

    def test_structural_marks_are_transparent_to_distance(
        self, ipa: IPAFeatures
    ) -> None:
        # A boundary relation must never cost alignment: liaison-marked
        # and unmarked spellings are the same word, at both distance layers.
        import ipakit

        assert ipa.word_distance("lez‿ami", "lezami").distance == 0.0
        assert ipa.word_distance("a|b", "ab").distance == 0.0
        model = ipakit.distance_model()
        assert model.word_distance("lez‿ami", "lezami").distance == 0.0

    def test_prosodic_marks_still_attach(self, ipa: IPAFeatures) -> None:
        # The fix is scoped to structural marks; stress/length keep their
        # attachment behavior.
        segs = ipa.segments("ˈaː")
        assert len(segs) == 1
        assert set(segs[0].prosody) == {"ˈ", "ː"}


class TestDisagreements:
    def test_voicing_disagreeing_tie_is_reported_not_rejected(
        self, ipa: IPAFeatures
    ) -> None:
        d = ipa.segment("t͡ɮ").disagreements()
        assert d["voiced"] == ("-", "+")
        assert d["manner"] == ("plosive", "fricative")
        # Still fully composable: reporting, never refereeing.
        assert ipa.get_features("t͡ɮ")

    def test_double_articulation_disagrees_in_place_by_structure(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.segment("k͡p").disagreements() == {"place": ("velar", "bilabial")}

    def test_sequential_trajectory_disagrees_in_targets(self, ipa: IPAFeatures) -> None:
        d = ipa.segment("u͜i").disagreements()
        assert d["backness"] == ("back", "front")
        assert d["rounded"] == ("+", "-")

    def test_atomic_unit_has_none(self, ipa: IPAFeatures) -> None:
        assert ipa.segment("a").disagreements() == {}
        assert ipa.segment("tʲ").disagreements() == {}

    def test_agreeing_fusion_reports_only_its_phase_differences(
        self, ipa: IPAFeatures
    ) -> None:
        # t͡s agrees on everything except what its two phases differ in:
        # the manner, and the channel (a stop has no groove, /s/ does).
        d = ipa.segment("t͡s").disagreements()
        assert set(d) == {"manner", "channel"}
