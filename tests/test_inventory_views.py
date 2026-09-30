"""Experimental inventory views preserve source membership accounting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace

import ipakit
import pytest
from ipakit.inventories import Inventory
from ipakit.inventory_views import (
    INVENTORY_VIEW_SCHEMA_ID,
    INVENTORY_VIEW_SCHEMA_VERSION,
    InventoryMemberCounts,
    InventoryView,
    InventoryViewMember,
    inventory_view,
    inventory_view_from_dictionary,
    registry_inventory_view,
    registry_inventory_views,
)


def test_each_member_has_one_declared_status() -> None:
    counts = InventoryMemberCounts(1, 1)
    rows = (
        InventoryViewMember(0, "p", "present", house_form="p"),
        InventoryViewMember(1, "q", "filtered", house_form="q"),
        InventoryViewMember(2, "r", "dropped", house_form="r", counts=counts),
        InventoryViewMember(3, "s", "unreadable", reason="fixture"),
        InventoryViewMember(4, "t", "refused", reason="fixture"),
        InventoryViewMember(5, "u", "unresolved", reason="fixture"),
    )
    view = InventoryView("fixture", "fixture", "fixture", "available", rows)
    assert [row["status"] for row in view.to_dict()["members"]] == [
        "present",
        "filtered",
        "dropped",
        "unreadable",
        "refused",
        "unresolved",
    ]
    with pytest.raises(ValueError, match="unknown inventory member status"):
        InventoryViewMember(0, "p", "lost")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="available inventory view"):
        InventoryView(
            "fixture",
            "fixture",
            "fixture",
            "available",
            (InventoryViewMember(0, "fixture", "unavailable", reason="fixture"),),
        )
    ipa = ipakit.inventory("ipa")
    assert ipa.phones is not None
    conflicted = replace(ipa, refusals={next(iter(ipa.phones)): "fixture"})
    with pytest.raises(ValueError, match="partition into exactly one status"):
        inventory_view(conflicted)


def test_schema_identity_and_order_are_stable_across_hash_seeds() -> None:
    script = """
import json
from ipakit.inventory_views import registry_inventory_view
view = registry_inventory_view("cmudict")
print(json.dumps({"identity": view.identity, "population": view.declared_population}))
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
    view = registry_inventory_view("cmudict")
    document = view.to_dict()
    assert document["schema"] == {
        "id": INVENTORY_VIEW_SCHEMA_ID,
        "version": INVENTORY_VIEW_SCHEMA_VERSION,
    }
    reversed_rows = tuple(
        replace(row, index=index) for index, row in enumerate(reversed(view.members))
    )
    changed = replace(view, members=reversed_rows)
    assert changed.identity != view.identity
    with pytest.raises(ValueError, match="indices must be contiguous"):
        replace(view, members=(replace(view.members[0], index=1),))


def test_missing_finite_population_is_unavailable_not_empty() -> None:
    view = registry_inventory_view("wild")
    assert view.availability == "unavailable"
    assert len(view.members) == 1
    assert view.members[0].status == "unavailable"
    with pytest.raises(ValueError, match="one unavailable member"):
        InventoryView("missing", "fixture", "fixture", "unavailable", ())


def test_dictionary_counts_and_drops_survive_exactly(tmp_path) -> None:
    dictionary = tmp_path / "fixture.dict"
    dictionary.write_text("one p p\ntwo p\nthree b\n", encoding="utf-8")
    view = inventory_view_from_dictionary(dictionary, "ipa", min_entries=2)
    assert [(member.source_token, member.status) for member in view.members] == [
        ("p", "present"),
        ("b", "dropped"),
    ]
    assert view.members[0].counts == InventoryMemberCounts(entries=2, tokens=3)
    assert view.members[1].counts == InventoryMemberCounts(entries=1, tokens=1)
    assert view.to_dict()["members"][1]["counts"] == {
        "entries": 1,
        "tokens": 1,
    }

    source = Inventory(
        view.name,
        ipakit.inventory("ipa").style,
        ipakit.Phoneset.from_list(["p"], "fixture"),
        "fixture",
        counts={"p": {"entries": 2, "tokens": 3}, "b": {"entries": 1, "tokens": 1}},
        dropped={"b": {"entries": 1, "tokens": 2}},
    )
    with pytest.raises(ValueError, match="do not match counts"):
        inventory_view(source)


def test_registry_adapter_visits_every_registered_name(monkeypatch) -> None:
    import ipakit.inventory_views as module

    expected = tuple(module.inventories())
    actual = registry_inventory_views()
    assert tuple(view.name for view in actual) == expected

    visited = []

    def observe(name: str) -> InventoryView:
        visited.append(name)
        return registry_inventory_view(name)

    monkeypatch.setattr(module, "registry_inventory_view", observe)
    observed = module.registry_inventory_views()
    assert tuple(visited) == expected
    assert tuple(view.name for view in observed) == expected


def test_view_is_a_deeply_immutable_snapshot() -> None:
    counts = {"p": {"entries": 1, "tokens": 1}}
    item = ipakit.inventory("ipa")
    source = replace(item, counts=counts)
    with pytest.raises(ValueError, match="counts must cover exactly"):
        inventory_view(source)
    view = registry_inventory_view("ipa")
    with pytest.raises(AttributeError):
        view.members[0].status = "dropped"  # type: ignore[misc]
    json.dumps(view.to_dict(), ensure_ascii=False)
