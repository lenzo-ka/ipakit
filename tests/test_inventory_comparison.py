"""Versioned pairwise reports over existing inventory comparison engines."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace

import ipakit
import pytest
from ipakit.inventory_comparison import (
    INVENTORY_COMPARISON_SCHEMA_ID,
    INVENTORY_COMPARISON_SCHEMA_VERSION,
    inventory_comparison_report,
)
from ipakit.inventory_views import (
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


def test_registry_pair_preserves_current_set_mapping_and_strip_results() -> None:
    left = registry_inventory_view("cmudict")
    right = registry_inventory_view("timit")
    expected = ipakit.phoneset_comparison("cmudict", "timit")
    report = inventory_comparison_report(left, right, mapping="nearest", detail=True)

    actual = report.comparison
    assert actual.a.phones == expected.a.phones
    assert actual.b.phones == expected.b.phones
    assert actual.union == expected.union
    assert actual.intersection == expected.intersection
    assert actual.only_a == expected.only_a
    assert actual.only_b == expected.only_b
    assert actual.matrix == expected.matrix
    assert actual.stripped == expected.stripped
    assert report.forward is not None and report.backward is not None
    assert report.forward.correspondences == expected.forward.correspondences
    assert report.backward.correspondences == expected.backward.correspondences
    assert report.forward.collapses == expected.forward.collapses
    assert report.backward.collapses == expected.backward.collapses

    malformed = replace(actual, matrix=actual.matrix[:-1])
    with pytest.raises(ValueError, match="matrix dimensions"):
        replace(report, comparison=malformed)


def test_detailed_matrices_name_both_transposed_orientations() -> None:
    report = inventory_comparison_report(
        _view("left", ["p", "a"]),
        _view("right", ["b", "i", "t"]),
        detail=True,
    ).to_dict()
    matrices = report["matrices"]
    forward = matrices["a_to_b"]
    backward = matrices["b_to_a"]
    assert forward["rows"] == backward["columns"]
    assert forward["columns"] == backward["rows"]
    assert backward["values"] == [
        list(row) for row in zip(*forward["values"], strict=True)
    ]


def test_directional_mapping_states_relation_without_a_hidden_threshold() -> None:
    report = inventory_comparison_report(
        _view("large", ["s", "ʃ", "z"]),
        _view("small", ["s"]),
        mapping="nearest",
    )
    document = report.to_dict()
    mapping = document["mapping"]
    assert mapping["max_distance"] is None
    assert mapping["a_to_b"]["collapse_count"] == 1
    assert mapping["b_to_a"]["collapse_count"] == 0
    assert document["terms"]["directionality"] == (
        "A -> B and B -> A are independent directional results"
    )

    assert report.forward is not None
    with pytest.raises(ValueError, match="both directions"):
        replace(report, backward=None)
    with pytest.raises(ValueError, match="finite nonnegative"):
        inventory_comparison_report(
            _view("a", ["p"]),
            _view("b", ["b"]),
            mapping="nearest",
            max_distance=-1.0,
        )


def test_feature_terms_reconstruct_the_mapped_house_distance() -> None:
    report = inventory_comparison_report(
        _view("left", ["p"]),
        _view("right", ["b"]),
        mapping="nearest",
        detail=True,
        include_feature_terms=True,
    ).to_dict()
    row = report["mapping"]["a_to_b"]["correspondences"][0]
    explanation = row["feature_explanation"]
    terms = explanation["terms"]
    reconstructed = sum(term["cost"] * term.get("weight", 1.0) for term in terms) / sum(
        term.get("weight", 1.0) for term in terms
    )
    assert reconstructed == pytest.approx(row["distance"])
    assert explanation["distance"] == pytest.approx(row["distance"])

    changed = json.loads(json.dumps(report))
    changed_terms = changed["mapping"]["a_to_b"]["correspondences"][0][
        "feature_explanation"
    ]["terms"]
    next(term for term in changed_terms if term["cost"])["cost"] += 1.0
    changed_value = sum(
        term["cost"] * term.get("weight", 1.0) for term in changed_terms
    ) / sum(term.get("weight", 1.0) for term in changed_terms)
    assert changed_value != pytest.approx(row["distance"])

    with pytest.raises(ValueError, match="detail=True"):
        inventory_comparison_report(
            _view("left", ["p"]),
            _view("right", ["b"]),
            mapping="nearest",
            include_feature_terms=True,
        )


def test_summary_and_detail_keep_the_same_accounting() -> None:
    left = InventoryView(
        "left",
        "fixture",
        "test fixture",
        "available",
        (
            InventoryViewMember(0, "p", "present", house_form="p"),
            InventoryViewMember(1, "X", "refused", reason="fixture refusal"),
        ),
        style="ipa",
    )
    right = _view("right", ["b", "p"])
    summary = inventory_comparison_report(left, right, mapping="nearest").to_dict()
    detail = inventory_comparison_report(
        left, right, mapping="nearest", detail=True
    ).to_dict()

    for side in ("a", "b"):
        assert (
            summary["inputs"][side]["status_counts"]
            == detail["inputs"][side]["status_counts"]
        )
        assert "members" not in summary["inputs"][side]
        assert "members" in detail["inputs"][side]
    for key in (
        "a_count",
        "b_count",
        "union_count",
        "intersection_count",
        "only_a_count",
        "only_b_count",
    ):
        assert summary["membership"][key] == detail["membership"][key]
    assert "rows" not in summary["membership"]
    assert "matrices" not in summary
    assert "correspondences" not in summary["mapping"]["a_to_b"]
    assert "rows" in detail["membership"]
    assert "matrices" in detail
    assert "correspondences" in detail["mapping"]["a_to_b"]


def test_one_to_one_uses_the_existing_strategy_and_explicit_threshold() -> None:
    left = _view("left", ["s", "z", "ʃ"])
    right = _view("right", ["s", "z"])
    report = inventory_comparison_report(left, right, mapping="one-to-one")
    expected = ipakit.phoneset_mapping(
        report.comparison.a, report.comparison.b, one_to_one=True
    )
    assert report.forward is not None
    assert report.forward.correspondences == expected.correspondences
    assert report.max_distance is None

    distance = ipakit.segment_distance("ʔ", "i")
    bounded = inventory_comparison_report(
        _view("source", ["ʔ"]),
        _view("target", ["i"]),
        mapping="one-to-one",
        max_distance=distance / 2,
    )
    assert bounded.forward is not None
    assert bounded.forward.unmapped == ("ʔ",)


def test_schema_and_order_are_stable_across_hash_seeds() -> None:
    script = """
import hashlib
from ipakit.inventory_comparison import inventory_comparison_report
from ipakit.inventory_views import registry_inventory_view
report = inventory_comparison_report(
    registry_inventory_view("cmudict"),
    registry_inventory_view("timit"),
    mapping="nearest",
    detail=True,
)
text = report.to_json()
print(report.identity)
print(hashlib.sha256(text.encode()).hexdigest())
"""
    outputs = []
    for seed in ("1", "927"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
        )
    assert outputs[0] == outputs[1]

    report = inventory_comparison_report(_view("a", ["p"]), _view("b", ["b"]))
    assert report.to_dict()["schema"] == {
        "id": INVENTORY_COMPARISON_SCHEMA_ID,
        "version": INVENTORY_COMPARISON_SCHEMA_VERSION,
        "stability": "experimental",
    }
    json.loads(report.to_json())


def test_report_dispatches_the_current_comparison_and_mapping_engines(
    monkeypatch,
) -> None:
    import ipakit.inventory_comparison as module

    calls = {"comparison": 0, "mapping": 0}
    compare = module.phoneset_comparison
    map_phones = module.phoneset_mapping

    def observe_comparison(*args, **kwargs):
        calls["comparison"] += 1
        return compare(*args, **kwargs)

    def observe_mapping(*args, **kwargs):
        calls["mapping"] += 1
        return map_phones(*args, **kwargs)

    monkeypatch.setattr(module, "phoneset_comparison", observe_comparison)
    monkeypatch.setattr(module, "phoneset_mapping", observe_mapping)
    inventory_comparison_report(
        _view("a", ["p", "b"]),
        _view("b", ["t"]),
        mapping="one-to-one",
    )
    assert calls == {"comparison": 1, "mapping": 2}


def test_exact_membership_does_not_imply_mapping_or_empty_availability() -> None:
    report = inventory_comparison_report(
        _view("a", ["p", "b"]), _view("b", ["p"])
    ).to_dict()
    assert report["membership"]["intersection_count"] == 1
    assert report["membership"]["only_a_count"] == 1
    assert report["mapping"] is None

    with pytest.raises(ValueError, match="available finite view"):
        inventory_comparison_report(registry_inventory_view("wild"), _view("b", ["p"]))
