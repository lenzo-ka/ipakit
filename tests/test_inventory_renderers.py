"""Report-owned command-line and renderer surfaces."""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from ipakit.inventory_comparison import inventory_comparison_report
from ipakit.inventory_renderers import (
    render_inventory_json,
    render_inventory_markdown,
    render_inventory_text,
    render_inventory_tsv,
)
from ipakit.inventory_views import InventoryView, InventoryViewMember


def _view(name: str, provenance: str, *, refusal: str | None = None) -> InventoryView:
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


def _report(provenance: str = "left provenance", refusal: str = "left refusal"):
    return inventory_comparison_report(
        _view("left", provenance, refusal=refusal),
        _view("right", "right provenance"),
        mapping="nearest",
        detail=True,
    )


def _run(monkeypatch, capsys, *arguments: str):
    import ipakit.cli

    monkeypatch.setattr(sys, "argv", ["ipakit", *arguments])
    status = ipakit.cli.main()
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def test_json_renderer_is_the_canonical_report_document() -> None:
    report = _report()
    assert json.loads(render_inventory_json(report)) == report.to_dict()


@pytest.mark.parametrize(
    "renderer",
    [render_inventory_text, render_inventory_tsv, render_inventory_markdown],
)
def test_every_renderer_reads_mutated_provenance_and_refusal_from_one_report(
    renderer,
) -> None:
    baseline = renderer(_report())
    changed = renderer(_report("fault injected provenance", "fault injected refusal"))

    assert "left provenance" in baseline
    assert "left refusal" in baseline
    assert "fault injected provenance" in changed
    assert "fault injected refusal" in changed
    assert "fault injected provenance" not in baseline


def test_inventory_compare_is_an_alias_of_the_distance_report_route(
    monkeypatch, capsys
) -> None:
    status, distance, error = _run(
        monkeypatch, capsys, "distance", "compare", "cmudict", "timit", "-f", "json"
    )
    assert (status, error) == (0, "")
    status, inventory, error = _run(
        monkeypatch,
        capsys,
        "inventory",
        "compare",
        "cmudict",
        "timit",
        "-f",
        "json",
    )
    assert (status, error) == (0, "")
    assert json.loads(inventory) == json.loads(distance)


def test_mapping_flags_select_the_report_strategy_and_threshold(
    tmp_path, monkeypatch, capsys
) -> None:
    source = tmp_path / "source.phones"
    target = tmp_path / "target.phones"
    source.write_text("p\nb\n", encoding="utf-8")
    target.write_text("p\n", encoding="utf-8")

    status, output, error = _run(
        monkeypatch,
        capsys,
        "distance",
        "map",
        str(source),
        str(target),
        "--one-to-one",
        "--max-distance",
        "0.25",
        "-f",
        "json",
    )
    assert (status, error) == (0, "")
    document = json.loads(output)
    assert document["options"]["mapping"] == "one-to-one"
    assert document["options"]["max_distance"] == 0.25
    assert document["mapping"]["a_to_b"]["unmapped_count"] == 1


def test_tsv_takes_its_matrix_from_the_report() -> None:
    report = _report()
    changed_comparison = replace(report.comparison, matrix=((0.375,),))
    changed = replace(report, comparison=changed_comparison)

    assert "0.375" in render_inventory_tsv(changed).splitlines()[1]


def _scientific_imports(source: str) -> set[str]:
    forbidden = {"matplotlib", "numpy", "scipy"}
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(
                name.name.split(".", 1)[0]
                for name in node.names
                if name.name.split(".", 1)[0] in forbidden
            )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            root = node.module.split(".", 1)[0]
            if root in forbidden:
                found.add(root)
    return found


def test_library_modules_do_not_import_comparison_extras() -> None:
    package = Path(__file__).parents[1] / "ipakit"
    offenders = {}
    for path in package.rglob("*.py"):
        imports = _scientific_imports(path.read_text(encoding="utf-8"))
        if imports:
            offenders[path.relative_to(package)] = imports
    assert offenders == {}

    restored_import = (
        package.joinpath("inventory_renderers.py").read_text(encoding="utf-8")
        + "\nimport matplotlib\n"
    )
    assert _scientific_imports(restored_import) == {"matplotlib"}
