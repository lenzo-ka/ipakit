"""Relating one phoneset to another, by nearest phone and one-to-one.

The two operations answer different questions, so the tests that matter
are the ones that would pass if they had been conflated -- and those are
the greedy-versus-optimal witness and the collapse report.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit.models import Phoneset
from ipakit.phoneset_map import (
    _assign,
    nearest_mapping,
    one_to_one_mapping,
)


class TestGreedyIsNotOptimal:
    """The reason one-to-one solves an assignment instead of sorting.

    A greedy pass takes each row's best column in turn. It is cheaper to
    write, gives a different answer, and nothing in the output says so --
    which is why the optimal solver is worth its O(n^3).
    """

    #: Row 0 prefers column 0 by a hair. Taking it forces row 1 onto a
    #: column that costs 9.0, where letting row 0 settle for second best
    #: costs 0.9 more and saves 7.9.
    COST = ((1.0, 2.0), (1.1, 9.0))

    def test_the_assignment_is_the_one_greedy_would_not_choose(self) -> None:
        assignment = _assign(self.COST, 2)
        assert assignment == [1, 0]

    def test_and_its_total_beats_the_greedy_total(self) -> None:
        assignment = _assign(self.COST, 2)
        optimal = sum(self.COST[row][col] for row, col in enumerate(assignment))

        greedy_total, taken = 0.0, set()
        for row in self.COST:
            best = min((cost, col) for col, cost in enumerate(row) if col not in taken)
            greedy_total += best[0]
            taken.add(best[1])

        assert optimal == pytest.approx(3.1)
        assert greedy_total == pytest.approx(10.0)
        assert optimal < greedy_total


class TestTheTwoOperationsDiffer:
    """Nearest and one-to-one are not two spellings of one thing."""

    SOURCE = ["s", "z", "ʃ", "ʒ"]
    TARGET = ["s", "z"]

    def test_nearest_maps_every_source_phone(self) -> None:
        mapping = nearest_mapping(self.SOURCE, self.TARGET)
        assert all(c.mapped for c in mapping)
        assert len(mapping) == len(self.SOURCE)

    def test_one_to_one_leaves_the_surplus_unmapped(self) -> None:
        mapping = one_to_one_mapping(self.SOURCE, self.TARGET)
        assert len(mapping.mapped) == len(self.TARGET)
        assert set(mapping.unmapped) == {"ʃ", "ʒ"}

    def test_only_the_nearest_mapping_collapses(self) -> None:
        assert nearest_mapping(self.SOURCE, self.TARGET).collapses()
        assert one_to_one_mapping(self.SOURCE, self.TARGET).collapses() == {}


class TestCollapseIsTheReportWorthReading:
    """A merged contrast is what a many-to-one mapping is for."""

    def test_it_names_the_target_and_every_source_that_landed_on_it(self) -> None:
        mapping = nearest_mapping(["s", "ʃ", "z"], ["s", "z"])
        assert mapping.collapses() == {"s": ("s", "ʃ")}

    def test_a_mapping_that_preserves_every_contrast_collapses_nothing(self) -> None:
        assert nearest_mapping(["p", "t"], ["p", "t"]).collapses() == {}

    def test_an_identical_phoneset_maps_onto_itself_at_zero(self) -> None:
        mapping = nearest_mapping(["p", "t", "k"], ["p", "t", "k"])
        assert [c.target for c in mapping] == ["p", "t", "k"]
        assert mapping.total_distance == 0.0
        assert len(mapping.exact) == 3


class TestDirection:
    """Nearest is directional; asking it the other way is a different question."""

    def test_the_two_directions_give_different_answers(self) -> None:
        big, small = ["s", "ʃ", "z"], ["s"]
        assert len(nearest_mapping(big, small).unused_targets) == 0
        # The other way round, one phone maps and two targets go unused.
        back = nearest_mapping(small, big)
        assert len(back) == 1
        assert set(back.unused_targets) == {"ʃ", "z"}


class TestTiesAreReportedNotResolved:
    """Which of two equidistant targets is 'the' answer is not ours to say."""

    def test_an_equidistant_target_is_named_as_a_tie(self) -> None:
        mapping = nearest_mapping(["t͡ʃ"], ["s", "t"])
        (correspondence,) = mapping.correspondences
        assert correspondence.ties, "the tie against the other target is not reported"
        assert correspondence.target not in correspondence.ties
        distances = {ipakit.segment_distance("t͡ʃ", p) for p in ("s", "t")}
        assert len(distances) == 1, "the fixture is only a tie if these are equal"

    def test_ambiguous_collects_them(self) -> None:
        assert nearest_mapping(["t͡ʃ"], ["s", "t"]).ambiguous()
        assert not nearest_mapping(["p"], ["p"]).ambiguous()


class TestMaxDistanceRefusesRatherThanForcing:
    """Without a threshold every phone is paired, however badly."""

    def test_a_distant_phone_maps_when_nothing_bounds_it(self) -> None:
        mapping = nearest_mapping(["ʔ"], ["i"])
        assert mapping.mapped, "with no threshold, the least bad target is still taken"

    def test_and_is_refused_when_the_threshold_excludes_it(self) -> None:
        distance = ipakit.segment_distance("ʔ", "i")
        mapping = nearest_mapping(["ʔ"], ["i"], max_distance=distance / 2)
        assert mapping.unmapped == ("ʔ",)

    def test_the_threshold_applies_to_one_to_one_too(self) -> None:
        distance = ipakit.segment_distance("ʔ", "i")
        mapping = one_to_one_mapping(["ʔ"], ["i"], max_distance=distance / 2)
        assert mapping.unmapped == ("ʔ",)


class TestEdges:
    def test_an_empty_target_leaves_everything_unmapped(self) -> None:
        mapping = nearest_mapping(["p", "t"], [])
        assert mapping.unmapped == ("p", "t")
        assert mapping.total_distance == 0.0

    def test_an_empty_source_maps_nothing(self) -> None:
        assert len(nearest_mapping([], ["p"])) == 0

    def test_a_phoneset_and_a_bare_list_are_accepted_alike(self) -> None:
        as_list = nearest_mapping(["p"], ["t"])
        as_phoneset = nearest_mapping(
            Phoneset.from_list(["p"]), Phoneset.from_list(["t"])
        )
        assert [c.target for c in as_list] == [c.target for c in as_phoneset]

    def test_more_targets_than_sources_matches_every_source(self) -> None:
        mapping = one_to_one_mapping(["p"], ["p", "t", "k"])
        assert len(mapping.mapped) == 1
        assert len(mapping.unused_targets) == 2

    def test_the_kind_says_which_question_was_asked(self) -> None:
        assert nearest_mapping(["p"], ["t"]).kind == "nearest"
        assert one_to_one_mapping(["p"], ["t"]).kind == "one-to-one"


class TestThePublicEntryPoint:
    def test_it_reaches_both_operations(self) -> None:
        assert ipakit.phoneset_mapping(["p"], ["t"]).kind == "nearest"
        assert (
            ipakit.phoneset_mapping(["p"], ["t"], one_to_one=True).kind == "one-to-one"
        )

    def test_it_is_exported(self) -> None:
        assert "phoneset_mapping" in ipakit.__all__


class TestTheCliRoute:
    """`distance map` reads its phonesets from files.

    The orthography sweep in ``tests/test_cli_hygiene.py`` drives routes
    with a bare word on the command line and so cannot reach this one --
    it is listed in ``NEEDS_FILES_ON_DISK`` there. The hazard is real
    anyway, because a phoneset file may hold English spelling as readily
    as an argument may, so the witness that sweep would have produced is
    supplied here instead of the route simply being exempted.
    """

    @staticmethod
    def _run(monkeypatch, capsys, *argv: str):
        """Invoke the CLI as tests/test_cli.py does; return (rc, out, err)."""
        import sys

        import ipakit.cli

        monkeypatch.setattr(sys, "argv", ["ipakit", "distance", "map", *argv])
        rc = ipakit.cli.main()
        captured = capsys.readouterr()
        return rc, captured.out, captured.err

    def test_a_phoneset_file_of_orthography_is_refused(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        ortho = tmp_path / "ortho.txt"
        ortho.write_text("cat\ndog\n", encoding="utf-8")
        ipa = tmp_path / "ipa.txt"
        ipa.write_text("k\na\nt\n", encoding="utf-8")

        rc, out, err = self._run(monkeypatch, capsys, str(ortho), str(ipa))

        assert rc != 0, "English spelling in a phoneset file must not map quietly"
        assert "unit" in (out + err).lower()

    def test_a_phoneset_file_of_ipa_maps(self, tmp_path, monkeypatch, capsys) -> None:
        ipa = tmp_path / "ipa.txt"
        ipa.write_text("k\na\nt\n", encoding="utf-8")

        rc, out, _ = self._run(monkeypatch, capsys, str(ipa), str(ipa))

        assert rc == 0
        assert "0.0000" in out

    def test_a_missing_file_is_refused_rather_than_read_as_empty(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        ipa = tmp_path / "ipa.txt"
        ipa.write_text("k\n", encoding="utf-8")

        rc, _, _ = self._run(
            monkeypatch, capsys, str(tmp_path / "absent.txt"), str(ipa)
        )

        assert rc != 0

    def test_one_to_one_is_reachable_from_the_command_line(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        source = tmp_path / "source.txt"
        source.write_text("s\nz\n\u0283\n", encoding="utf-8")
        target = tmp_path / "target.txt"
        target.write_text("s\nz\n", encoding="utf-8")

        rc, out, _ = self._run(
            monkeypatch, capsys, str(source), str(target), "--one-to-one"
        )

        assert rc == 0
        assert "unmapped" in out, "the surplus phone is reported, not dropped"
