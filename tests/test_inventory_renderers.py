"""Report-owned command-line and renderer surfaces."""

from __future__ import annotations

import ast
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import ipakit
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


def _legacy_mapping_lines(mapping) -> list[str]:
    lines = []
    for item in mapping:
        if item.target is None:
            reason = f": {item.reason}" if item.reason else ""
            lines.append(f"{item.source_spelling or '-'}\t-\t(unmapped{reason})")
            continue
        house = ""
        if item.source_spelling != item.source or item.target_spelling != item.target:
            house = f"  [{item.source} → {item.target}]"
        ties = f"  ties: {' '.join(item.ties)}" if item.ties else ""
        lines.append(
            f"{item.source_spelling or '-'}\t{item.target_spelling or '-'}\t"
            f"{item.distance:.4f}{house}{ties}"
        )
    if mapping.unused_targets:
        lines.append(
            "unused targets: "
            + " ".join(
                mapping.target_style.spell(phone) for phone in mapping.unused_targets
            )
        )
    lines.append(f"total distance: {mapping.total_distance:.4f}")
    return lines


def _legacy_compare_lines(comparison) -> list[str]:
    def show(values, side=None):
        shown = []
        for phone in values:
            forms = comparison.spellings[phone]
            sides = range(2) if side is None else (side,)
            external = [
                f"{'AB'[index]}: {forms[index]}"
                for index in sides
                if forms[index] not in {None, phone}
            ]
            shown.append(f"{phone} [{'; '.join(external)}]" if external else phone)
        return " ".join(shown)

    lines = [
        "terms: raw feature distance (no reference scaling); "
        f"denominator={'applicable features only' if comparison.applicable_only else 'all declared features'}; "
        f"strip={comparison.strip or 'none'}"
    ]
    for label, selected in (
        ("A", comparison.forward.source_inventory),
        ("B", comparison.forward.target_inventory),
    ):
        if selected is not None and selected.source is not None:
            source = selected.source
            lines.append(
                f"{label}: {selected.name} — {source.kind}; "
                f"{source.artifact}; {source.version}"
            )
    lines.extend(
        [
            f"union: {show(comparison.union)}",
            f"intersection: {show(comparison.intersection)}",
            f"only A: {show(comparison.only_a, 0)}",
            f"only B: {show(comparison.only_b, 1)}",
        ]
    )
    if comparison.asymmetry is not None:
        lines.append(
            "asymmetry (B->A mean / A->B mean): " f"{comparison.asymmetry:.4f}"
        )
    for label, mapping in (
        ("A -> B", comparison.forward),
        ("B -> A", comparison.backward),
    ):
        lines.append(
            f"{label}: mapped={len(mapping.mapped)} exact={len(mapping.exact)} "
            f"unmapped={len(mapping.unmapped)}"
        )
        if mapping.mean_distance is not None:
            lines.append(f"mean distance: {mapping.mean_distance:.4f}")
        if mapping.worst is not None:
            lines.append(
                f"worst: {mapping.worst.source} -> {mapping.worst.target} "
                f"({mapping.worst.distance:.4f})"
            )
        lines.extend(
            f"nearest collapse onto {target}: {' '.join(sources)}"
            for target, sources in mapping.collapses.items()
        )
    lines.append("similarity matrix:")
    lines.append("\t" + "\t".join(comparison.b.phones))
    lines.extend(
        phone + "\t" + "\t".join(f"{value:.4f}" for value in row)
        for phone, row in zip(comparison.a, comparison.matrix, strict=True)
    )
    if comparison.stripped:
        lines.append(
            "stripped: "
            + " ".join(f"{source}->{target}" for source, target in comparison.stripped)
        )
    return lines


def _assert_lines_present(expected: list[str], actual: str) -> None:
    actual_lines = actual.splitlines()
    missing = [line for line in expected if line not in actual_lines]
    assert missing == []


def _assert_established_json_fields(document: dict[str, object]) -> None:
    assert "asymmetry" in document
    assert {"union", "intersection", "only_a", "only_b", "rows"} <= set(
        document["membership"]
    )
    assert {"mode", "changed"} <= set(document["stripping"])
    assert "values" in document["matrices"]["a_to_b"]
    for direction in ("a_to_b", "b_to_a"):
        row = document["mapping"][direction]
        assert {
            "mapped_count",
            "exact_count",
            "unmapped",
            "collapses",
            "mean_distance",
            "worst",
            "correspondences",
        } <= set(row)
        assert {
            "source",
            "target",
            "distance",
            "source_spelling",
            "target_spelling",
            "relation",
        } <= set(row["correspondences"][0])


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


def test_named_inventory_text_contains_the_established_map_and_compare_lines(
    monkeypatch, capsys
) -> None:
    mapping = ipakit.phoneset_mapping("cmudict", "timit")
    status, output, error = _run(
        monkeypatch, capsys, "distance", "map", "cmudict", "timit"
    )
    assert (status, error) == (0, "")
    _assert_lines_present(_legacy_mapping_lines(mapping), output)

    comparison = ipakit.phoneset_comparison("cmudict", "timit")
    status, output, error = _run(
        monkeypatch, capsys, "distance", "compare", "cmudict", "timit"
    )
    assert (status, error) == (0, "")
    _assert_lines_present(_legacy_compare_lines(comparison), output)


def test_file_pair_contains_established_text_and_json_fields(
    tmp_path, monkeypatch, capsys
) -> None:
    left = tmp_path / "a.phones"
    right = tmp_path / "b.phones"
    left.write_text("p\n", encoding="utf-8")
    right.write_text("b\n", encoding="utf-8")

    mapping = ipakit.phoneset_mapping(left, right)
    status, output, error = _run(
        monkeypatch, capsys, "distance", "map", str(left), str(right)
    )
    assert (status, error) == (0, "")
    _assert_lines_present(_legacy_mapping_lines(mapping), output)

    comparison = ipakit.phoneset_comparison(left, right)
    status, output, error = _run(
        monkeypatch, capsys, "distance", "compare", str(left), str(right)
    )
    assert (status, error) == (0, "")
    _assert_lines_present(_legacy_compare_lines(comparison), output)

    for command in ("map", "compare"):
        status, output, error = _run(
            monkeypatch,
            capsys,
            "distance",
            command,
            str(left),
            str(right),
            "-f",
            "json",
        )
        assert (status, error) == (0, "")
        document = json.loads(output)
        assert document["mapping"]["a_to_b"]["total_distance"] == pytest.approx(
            mapping.total_distance
        )
        if command == "compare":
            _assert_established_json_fields(document)
            without_asymmetry = copy.deepcopy(document)
            without_asymmetry.pop("asymmetry")
            with pytest.raises(AssertionError):
                _assert_established_json_fields(without_asymmetry)


def test_named_inventory_json_keeps_native_spellings_and_asymmetry(
    monkeypatch, capsys
) -> None:
    status, output, error = _run(
        monkeypatch,
        capsys,
        "distance",
        "map",
        "cmudict",
        "timit",
        "-f",
        "json",
    )
    assert (status, error) == (0, "")
    document = json.loads(output)
    first = document["mapping"]["a_to_b"]["correspondences"][0]
    assert (first["source_spelling"], first["target_spelling"]) == ("IY", "iy")
    assert document["mapping"]["a_to_b"]["unused_targets"]
    assert "total_distance" in document["mapping"]["a_to_b"]

    status, output, error = _run(
        monkeypatch,
        capsys,
        "distance",
        "compare",
        "cmudict",
        "timit",
        "-f",
        "json",
    )
    assert (status, error) == (0, "")
    _assert_established_json_fields(json.loads(output))


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
