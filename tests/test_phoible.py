"""PHOIBLE remains testable without mounting the separately licensed data."""

from pathlib import Path

import pytest
from ipakit.bridges.phoible import (
    PHOIBLE_ENV,
    PhoibleBridge,
    PhoibleDataUnavailable,
)
from ipakit.models import Phoneset

from .test_cli import run

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


def test_cli_language_shows_spread_with_sources_and_keys(monkeypatch, capsys) -> None:
    status, out, _ = run(
        monkeypatch, capsys, "phoible", "language", "eng", "--phoible", str(FIXTURE)
    )
    assert status == 0
    assert "160\tstan1293\tspa\tOConner1973\tEnglish" in out
    assert "2175\tstan1293\tuz\teng_ladefoged1989\tEnglish (American)" in out


def test_cli_inventory_is_a_phoneset_file_and_refusals_exit_three(
    tmp_path, monkeypatch, capsys
) -> None:
    output = tmp_path / "english.txt"
    status, _, error = run(
        monkeypatch,
        capsys,
        "phoible",
        "inventory",
        "160",
        "--phoible",
        str(FIXTURE),
        "-o",
        str(output),
    )
    assert status == 3
    assert Phoneset.from_file(output).phones == ["b"]
    assert "PHOIBLE row 3 Phoneme 'k͈'" in error


def test_cli_without_mount_exits_cleanly(monkeypatch, capsys) -> None:
    monkeypatch.delenv(PHOIBLE_ENV, raising=False)
    status, _, error = run(monkeypatch, capsys, "phoible", "language", "eng")
    assert status == 1
    assert "PHOIBLE data is unavailable" in error
