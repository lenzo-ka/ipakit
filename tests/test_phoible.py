"""PHOIBLE remains testable without mounting the separately licensed data."""

from pathlib import Path

import pytest
from ipakit.bridges.phoible import (
    PHOIBLE_ENV,
    PhoibleBridge,
    PhoibleDataUnavailable,
)
from ipakit.models import Phoneset

FIXTURE = Path(__file__).parent / "fixtures" / "phoible"


def test_absent_checkout_has_one_clean_actionable_refusal(monkeypatch) -> None:
    monkeypatch.delenv(PHOIBLE_ENV, raising=False)
    with pytest.raises(PhoibleDataUnavailable, match=PHOIBLE_ENV):
        PhoibleBridge()


def test_environment_variable_and_csv_path_are_both_supported(monkeypatch) -> None:
    monkeypatch.setenv(PHOIBLE_ENV, str(FIXTURE))
    assert PhoibleBridge().root == FIXTURE
    csv_path = FIXTURE / "data" / "phoible.csv"
    assert PhoibleBridge(csv_path).root == FIXTURE


def test_language_query_returns_the_spread_and_never_an_inventory() -> None:
    spread = PhoibleBridge(FIXTURE).language("eng")
    assert [item.inventory_id for item in spread.inventories] == ["160", "2175"]
    assert [item.source for item in spread.inventories] == ["spa", "uz"]
    assert spread.inventories[0].bibtex_keys == ("OConner1973",)
    assert PhoibleBridge(FIXTURE).language("stan1293") == spread.__class__(
        "stan1293", spread.inventories
    )


def test_inventory_id_returns_phoneset_annotations_and_positioned_refusal() -> None:
    inventory = PhoibleBridge(FIXTURE).inventory(160)
    assert inventory.phoneset == Phoneset("phoible-160", ["b"])
    assert inventory.entries[0].allophones == ("b", "p")
    assert inventory.entries[0].marginal is None
    assert inventory.refusals[0].row == 3
    assert inventory.refusals[0].field == "Phoneme"
    assert inventory.refusals[0].value == "k͈"
    assert "unknown symbols" in inventory.refusals[0].reason


def test_false_marginal_is_carried_on_bridge_record() -> None:
    inventory = PhoibleBridge(FIXTURE).inventory("2175")
    assert inventory.phoneset.phones == ["a"]
    assert inventory.entries[0].marginal is False


def test_fixture_audit_counts_rows_inventories_and_reasons() -> None:
    audit = PhoibleBridge(FIXTURE).audit()
    assert (audit.rows, audit.accepted_rows, audit.refused_rows) == (3, 2, 1)
    assert (audit.inventories, audit.accepted_inventories) == (2, 1)
    assert audit.refused_inventories == 1
    assert audit.refusal_reasons[0][1] == 1
