"""Ordering invariant for the clustered inventory comparison example."""

from __future__ import annotations

from dataclasses import replace

import ipakit
import pytest
from scripts._comparison_order import aligned_orders


def test_shared_phones_lead_both_axes_at_the_same_indices() -> None:
    result = ipakit.phoneset_comparison(["p", "t", "k", "a"], ["a", "k", "s", "p"])
    shared = tuple(reversed(result.intersection))
    rows, columns = aligned_orders(
        result.intersection,
        result.only_a,
        result.only_b,
        shared,
        tuple(reversed(result.only_a)),
        tuple(reversed(result.only_b)),
    )

    row_index = {phone: index for index, phone in enumerate(result.a.phones)}
    column_index = {phone: index for index, phone in enumerate(result.b.phones)}
    for phone in result.intersection:
        assert rows.index(phone) == columns.index(phone)
    ordered_matrix = tuple(
        tuple(result.matrix[row_index[left]][column_index[right]] for right in columns)
        for left in rows
    )
    for index in range(len(shared)):
        assert ordered_matrix[index][index] == 1.0


def test_partition_seeding_is_optimal_and_refuses_when_sources_are_too_few() -> None:
    pytest.importorskip("scipy")
    from scripts.compare_inventories import partition_selections

    sources = ("a", "b", "c")
    uncovered_targets = ("x", "y")
    targets = ("x", "y", "z")
    scores = {
        ("a", "x"): 1.0,
        ("a", "y"): 0.9,
        ("b", "x"): 0.95,
        ("b", "y"): 0.0,
        ("c", "x"): 0.8,
        ("c", "y"): 0.7,
        ("a", "z"): 0.0,
        ("b", "z"): 0.0,
        ("c", "z"): 0.85,
    }

    partition = partition_selections(sources, uncovered_targets, targets, scores)
    assert not isinstance(partition, str)
    # Greedy target order would spend a on x and force c onto y.  The global
    # solution gives x to b, y to a, and lets c join z, which was already
    # covered before this side-only partition (for example, by an identity).
    assert {(item.source, item.target) for item in partition} == {
        ("a", "y"),
        ("b", "x"),
        ("c", "z"),
    }

    reverse = partition_selections(
        uncovered_targets,
        sources,
        sources,
        {(target, source): value for (source, target), value in scores.items()},
    )
    assert reverse == (
        "refused: partition has 2 side-only sources and 3 side-only targets; "
        "a surjection requires at least as many sources as targets"
    )


def test_mapping_commentary_handles_a_side_without_exclusive_phones(capsys) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    from ipakit.inventory_comparison import inventory_comparison_report
    from ipakit.inventory_views import InventoryView, InventoryViewMember
    from scripts.compare_inventories import print_mappings

    def view(name: str, phones: tuple[str, ...]) -> InventoryView:
        return InventoryView(
            name,
            "fixture",
            "test fixture",
            "available",
            tuple(
                InventoryViewMember(index, phone, "present", house_form=phone)
                for index, phone in enumerate(phones)
            ),
            style="ipa",
        )

    report = inventory_comparison_report(
        view("subset", ("p",)),
        view("superset", ("p", "t")),
        mapping="nearest",
        detail=True,
    )
    print_mappings(report, 0.75)
    assert "side-only mapping: not applicable" in capsys.readouterr().out


def test_svg_takes_its_matrix_and_metadata_from_the_report(
    tmp_path, monkeypatch
) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("scipy")
    from ipakit.inventory_comparison import inventory_comparison_report
    from ipakit.inventory_views import InventoryView, InventoryViewMember
    from matplotlib.axes import Axes
    from scripts.compare_inventories import write_heatmap

    def view(name: str, provenance: str, refusal: str | None = None) -> InventoryView:
        members = [InventoryViewMember(0, "p", "present", house_form="p")]
        if refusal is not None:
            members.append(InventoryViewMember(1, "X", "refused", reason=refusal))
        return InventoryView(
            name,
            "fixture",
            provenance,
            "available",
            tuple(members),
            style="ipa",
        )

    report = inventory_comparison_report(
        view("left", "left provenance", "left refusal"),
        view("right", "right provenance"),
        mapping="nearest",
        detail=True,
    )
    changed = replace(report, comparison=replace(report.comparison, matrix=((0.375,),)))
    destination = tmp_path / "comparison.svg"
    observed = []
    original_imshow = Axes.imshow

    def observe_imshow(axis, values, *args, **kwargs):
        observed.append(values)
        return original_imshow(axis, values, *args, **kwargs)

    monkeypatch.setattr(Axes, "imshow", observe_imshow)
    write_heatmap(destination, changed, ("p",), ("p",))
    svg = destination.read_text(encoding="utf-8")

    assert observed == [[[0.375]]]
    assert svg.lstrip().startswith("<?xml")
    assert "left provenance" in svg
    assert "left refusal" in svg
