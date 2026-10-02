"""Authority and loss adapters for experimental inventory views."""

from __future__ import annotations

from dataclasses import replace

import pytest
from ipakit import Phoneset
from ipakit.bridges.mfa import MFA
from ipakit.bridges.phoible import (
    PhoibleEntry,
    PhoibleInventory,
    PhoibleProvenance,
    PhoibleRefusal,
)
from ipakit.bridges.zipa import ZIPA
from ipakit.clts import read_snapshot
from ipakit.clts_mapping import read_authority
from ipakit.form import Form
from ipakit.inventory_comparison import inventory_comparison_report
from ipakit.inventory_views import (
    InventoryMemberMapping,
    InventoryMemberPosition,
    InventoryView,
    InventoryViewMember,
    clts_inventory_view,
    clts_inventory_view_from_artifacts,
    clts_inventory_view_from_source,
    phoible_inventory_view,
    phoible_inventory_view_from_source,
    vocabulary_inventory_view,
)


def _view(name: str, phones: tuple[str, ...]) -> InventoryView:
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


def test_declared_bridge_losses_are_not_exercised_losses() -> None:
    view = vocabulary_inventory_view(ZIPA)
    assert sum(member.status == "present" for member in view.members) == 108
    report = inventory_comparison_report(view, _view("target", ("p",))).to_dict()
    losses = report["authority_and_loss"]["losses"]
    assert {row["name"] for row in losses["declared"]} == set(
        ZIPA.round_trip.house_to_external.drops
    )
    assert losses["exercised"] == []
    assert view.bridge is not None
    changed = replace(
        view,
        bridge=replace(
            view.bridge,
            house_to_external_drops=view.bridge.house_to_external_drops[:-1],
        ),
    )
    assert changed.identity != view.identity


def test_selected_mfa_reduction_exercises_one_declared_loss() -> None:
    projection = MFA.map_to_mfa(Form.parse("n̪", strict=True))
    view = vocabulary_inventory_view(MFA, projections=(projection,))
    report = inventory_comparison_report(view, _view("target", ("n",))).to_dict()
    losses = report["authority_and_loss"]["losses"]
    assert [row["name"] for row in losses["declared"]] == [
        "narrow detail outside the MFA inventory"
    ]
    assert losses["exercised"][0] == {
        "input": "a",
        "direction": "house-to-external",
        "name": "narrow detail outside the MFA inventory",
        "span": [0, 1],
        "content": "n̪",
        "output": "n",
        "projection": 0,
    }
    assert view.bridge is not None
    loss = view.bridge.exercised_losses[0]
    with pytest.raises(ValueError, match="is not declared"):
        replace(view.bridge, exercised_losses=(replace(loss, name="invented"),))


def _phoible(inventory_id: str) -> PhoibleInventory:
    provenance = PhoibleProvenance(
        inventory_id,
        "test1234",
        "tst",
        "Test language",
        "Test source",
        ("Test2026",),
    )
    return PhoibleInventory(
        provenance,
        Phoneset.from_list(["p"], f"phoible-{inventory_id}"),
        (PhoibleEntry("p", (), False, 12),),
        (PhoibleRefusal(13, "Phoneme", "?", "unknown symbol"),),
    )


def test_positioned_phoible_refusal_and_inventory_identity_survive() -> None:
    first = phoible_inventory_view(_phoible("1"))
    second = phoible_inventory_view(_phoible("2"))
    refusal = first.members[1]
    assert refusal.status == "refused"
    assert refusal.position == InventoryMemberPosition(13, "Phoneme")
    assert refusal.to_dict()["position"] == {"row": 13, "field": "Phoneme"}
    assert first.name != second.name
    assert first.identity != second.identity
    with pytest.raises(ValueError, match="positive integer"):
        InventoryMemberPosition(0, "Phoneme")


def test_clts_reviewed_and_unresolved_members_use_only_authority() -> None:
    view = clts_inventory_view(read_snapshot(), read_authority())
    reviewed = [member for member in view.members if member.status == "present"]
    unresolved = [member for member in view.members if member.status == "unresolved"]
    assert [(member.source_token, member.house_form) for member in reviewed] == [
        ("b", "b"),
        ("d", "d"),
        ("p", "p"),
        ("t", "t"),
    ]
    assert len(unresolved) == 1207
    assert all(member.house_form is None for member in unresolved)

    report = inventory_comparison_report(
        view, _view("one", ("p",)), _view("two", ("p",))
    ).to_dict()
    measure = next(
        item for item in report["coverage"] if item["name"] == "reviewed-mapped"
    )
    assert (measure["numerator"], measure["denominator"]) == (4, 1211)
    assert measure["status_buckets"]["denominator"] == ["present", "unresolved"]

    mapping = reviewed[0].mapping
    assert mapping is not None
    assert view.mapping_authority is not None
    with pytest.raises(ValueError, match="target must equal"):
        replace(reviewed[0], mapping=replace(mapping, target="p"))
    with pytest.raises(ValueError, match="only a present member"):
        replace(
            unresolved[0],
            mapping=InventoryMemberMapping("p", "reviewed", view.mapping_authority),
        )


def test_absent_optional_sources_are_deterministically_unavailable(tmp_path) -> None:
    left = phoible_inventory_view_from_source("7", path=tmp_path / "left")
    right = phoible_inventory_view_from_source("7", path=tmp_path / "right")
    assert left.to_dict() == right.to_dict()
    assert left.members[0].status == "unavailable"
    live = clts_inventory_view_from_source(None)
    assert live.members[0].reason == "live CLTS source is unavailable"

    missing = clts_inventory_view_from_artifacts(
        snapshot_path=tmp_path / "missing-snapshot.json",
        authority_path=tmp_path / "missing-authority.json",
    )
    assert missing.availability == "unavailable"
    assert missing.members[0].reason == (
        "CLTS snapshot or mapping authority is unavailable"
    )
