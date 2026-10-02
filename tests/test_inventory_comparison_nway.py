"""N-way membership and named coverage for inventory comparison reports."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest
from ipakit.inventory_comparison import inventory_comparison_report
from ipakit.inventory_views import (
    InventoryMemberCounts,
    InventoryView,
    InventoryViewMember,
    registry_inventory_view,
)


def _view(name: str, phones: list[str]) -> InventoryView:
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


def test_nway_membership_is_permutation_invariant_and_deterministic() -> None:
    views = (
        _view("first", ["p", "b", "t"]),
        _view("second", ["p", "b", "k"]),
        _view("third", ["p", "k", "m"]),
    )
    documents = [
        inventory_comparison_report(*order, detail=True).to_json()
        for order in permutations(views)
    ]
    assert len(set(documents)) == 1

    membership = json.loads(documents[0])["membership"]
    assert membership["union_count"] == 5
    assert membership["shared_by_all"] == ["p"]
    assert membership["shared_by_subset_count"] == 2
    assert membership["unique_to_one_count"] == 2
    assert all(
        row["inputs"]
        == [
            f"input-{index}"
            for index, present in enumerate(row["membership"])
            if present
        ]
        for row in membership["rows"]
    )


def test_empty_and_single_reports_have_defined_membership() -> None:
    empty = inventory_comparison_report().to_dict()
    assert empty["membership"]["input_count"] == 0
    assert empty["membership"]["union_count"] == 0
    assert empty["membership"]["shared_by_all_count"] == 0

    single = inventory_comparison_report(_view("single", ["p", "b"])).to_dict()
    assert single["membership"]["input_count"] == 1
    assert single["membership"]["shared_by_all_count"] == 2
    assert single["membership"]["unique_to_one_count"] == 2


def test_nway_report_keeps_symbol_rows_behind_detail() -> None:
    views = (
        _view("one", ["p", "b"]),
        _view("two", ["p", "t"]),
        _view("three", ["p", "k"]),
    )
    summary = inventory_comparison_report(*views).to_dict()
    detail = inventory_comparison_report(*views, detail=True).to_dict()
    assert summary["membership"]["union_count"] == detail["membership"]["union_count"]
    assert summary["coverage"] == detail["coverage"]
    assert "rows" not in summary["membership"]
    assert "union" not in summary["membership"]
    assert "members" not in next(iter(summary["inputs"].values()))
    assert "rows" in detail["membership"]
    assert "union" in detail["membership"]
    assert "members" in next(iter(detail["inputs"].values()))


def test_two_input_serialization_remains_byte_identical_to_pairwise_v1() -> None:
    left = _view("left", ["p", "a"])
    right = _view("right", ["p", "b"])
    summary = inventory_comparison_report(left, right).to_json()
    detail = inventory_comparison_report(
        left, right, mapping="nearest", detail=True
    ).to_json()

    assert hashlib.sha256(summary.encode()).hexdigest() == (
        "fd6ee7031b8c03390aa880d6491ebdc6f58d189d709977432a695cef9abace7f"
    )
    assert hashlib.sha256(detail.encode()).hexdigest() == (
        "0989745fe7b34b0f2095cd7455b457c8c87a4c2b9fd039300a7e0d456da18979"
    )


def _accounted_view() -> InventoryView:
    members = (
        InventoryViewMember(0, "p", "present", house_form="p"),
        InventoryViewMember(1, "b", "filtered", house_form="b"),
        InventoryViewMember(
            2,
            "t",
            "dropped",
            house_form="t",
            counts=InventoryMemberCounts(1, 1),
        ),
        InventoryViewMember(3, "bad", "unreadable", reason="fixture"),
        InventoryViewMember(4, "ref", "refused", reason="fixture"),
        InventoryViewMember(5, "todo", "unresolved", reason="fixture"),
    )
    return InventoryView(
        "accounted", "fixture", "test fixture", "available", members, style="ipa"
    )


def test_named_coverage_states_denominators_and_status_buckets() -> None:
    views = (
        _accounted_view(),
        _view("target", ["p", "k"]),
        _view("other", ["p"]),
    )
    document = inventory_comparison_report(*views).to_dict()
    measures = {measure["name"]: measure for measure in document["coverage"]}
    assert tuple(measures) == (
        "overlap",
        "readable/admitted",
        "reviewed-mapped",
        "exact representability",
        "thresholded-nearest",
    )
    assert all(
        {"numerator", "denominator", "definition", "status_buckets"} <= measure.keys()
        for measure in measures.values()
    )
    readable = measures["readable/admitted"]
    assert readable["numerator"] == 4
    assert readable["denominator"] == 9
    assert readable["status_buckets"]["numerator"] == ["present"]
    assert readable["status_buckets"]["denominator"] == [
        "present",
        "filtered",
        "dropped",
        "unreadable",
        "refused",
        "unavailable",
        "unresolved",
    ]
    assert measures["reviewed-mapped"]["applicable"] is False
    assert measures["reviewed-mapped"]["denominator"] == 0
    assert measures["thresholded-nearest"]["applicable"] is False

    def assert_status_accounting(candidate) -> None:
        expected_numerator = sum(
            view["status_counts"]["present"] for view in candidate["inputs"].values()
        )
        expected_denominator = sum(
            sum(view["status_counts"].values()) for view in candidate["inputs"].values()
        )
        measure = next(
            item
            for item in candidate["coverage"]
            if item["name"] == "readable/admitted"
        )
        assert measure["numerator"] == expected_numerator
        assert measure["denominator"] == expected_denominator

    assert_status_accounting(document)
    mutated = deepcopy(document)
    measure = next(
        item for item in mutated["coverage"] if item["name"] == "readable/admitted"
    )
    accounted = next(
        view for view in mutated["inputs"].values() if view["name"] == "accounted"
    )
    measure["numerator"] += accounted["status_counts"]["dropped"]
    with pytest.raises(AssertionError):
        assert_status_accounting(mutated)


def test_thresholded_nearest_coverage_reuses_directional_mapping() -> None:
    views = (
        _view("one", ["p", "b"]),
        _view("two", ["p", "t"]),
        _view("three", ["p"]),
    )
    report = inventory_comparison_report(*views, mapping="nearest", max_distance=0.0)
    measures = {item["name"]: item for item in report.to_dict()["coverage"]}
    thresholded = measures["thresholded-nearest"]
    exact = measures["exact representability"]
    assert thresholded["applicable"] is True
    assert thresholded["numerator"] == exact["numerator"] == 6
    assert thresholded["denominator"] == exact["denominator"] == 10
    with pytest.raises(ValueError, match="invalid thresholded-nearest"):
        replace(report, thresholded_nearest_numerator=11)


def test_mfa_union_and_scoped_views_share_expected_membership() -> None:
    report = inventory_comparison_report(
        registry_inventory_view("mfa"),
        registry_inventory_view("mfa:english"),
        registry_inventory_view("mfa:french"),
        detail=True,
    ).to_dict()
    names = {input_key: view["name"] for input_key, view in report["inputs"].items()}
    union_key = next(key for key, name in names.items() if name == "mfa")
    for row in report["membership"]["rows"]:
        if any(names[key] != "mfa" for key in row["inputs"]):
            assert union_key in row["inputs"]
