"""Render the experimental inventory comparison report without recalculating it."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from .inventories import inventories, inventory
from .inventory_views import InventoryView, InventoryViewMember, registry_inventory_view
from .models import Phoneset
from .phoneset_map import read_inventory_entry

if TYPE_CHECKING:
    from .features import IPAFeatures
    from .inventory_comparison import InventoryComparisonReport

Direction = Literal["a_to_b", "b_to_a"]


def inventory_surface_view(
    value: str | Path,
    *,
    style: str | None = None,
    ipa: IPAFeatures,
    tied: bool = True,
) -> tuple[InventoryView, tuple[tuple[str, str, str], ...]]:
    """Resolve one CLI inventory operand while retaining every source row."""
    if isinstance(value, str) and value in set(inventories()):
        if style is not None:
            raise ValueError(
                f"style cannot be given with inventory {value!r}; "
                "the inventory already declares its style"
            )
        return registry_inventory_view(value), ()

    path = Path(value)
    raw = Phoneset.from_file(path)
    selected = inventory(style or "ipa", ipa=ipa).style
    members: list[InventoryViewMember] = []
    changes: list[tuple[str, str, str]] = []
    for token in raw:
        try:
            if selected.name == "wild":
                house, steps = read_inventory_entry(token, ipa, wild=True, tie=tied)
            else:
                house = selected.read(token)
                house, steps = read_inventory_entry(house, ipa, tie=tied)
            changes.extend(steps)
            if len(ipa.segments(house)) != 1:
                raise ValueError(f"cannot read {token!r} as one phone")
            members.append(
                InventoryViewMember(len(members), token, "present", house_form=house)
            )
        except ValueError as error:
            members.append(
                InventoryViewMember(
                    len(members), token, "unreadable", reason=str(error)
                )
            )
    return (
        InventoryView(
            raw.name,
            "phoneset-file",
            f"phoneset file {path}",
            "available",
            tuple(members),
            selected.name,
        ),
        tuple(changes),
    )


def _document(report: InventoryComparisonReport) -> dict[str, object]:
    """Take the one canonical snapshot every renderer consumes."""
    return report.to_dict()


def render_inventory_json(report: InventoryComparisonReport) -> str:
    """Render the canonical report JSON exactly."""
    return (
        json.dumps(_document(report), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )


def _inputs(document: dict[str, object]) -> dict[str, dict[str, object]]:
    return cast("dict[str, dict[str, object]]", document["inputs"])


def _mapping_rows(
    document: dict[str, object], direction: Direction | None
) -> list[tuple[str, dict[str, object]]]:
    mapping = document.get("mapping")
    if not isinstance(mapping, dict):
        return []
    keys: tuple[Direction, ...] = (
        (direction,) if direction is not None else ("a_to_b", "b_to_a")
    )
    return [(key, cast("dict[str, object]", mapping[key])) for key in keys]


def _input_lines(label: str, item: dict[str, object]) -> list[str]:
    lines = [
        f"{label}: {item['name']} ({item['kind']}; {item['availability']})",
        f"  provenance: {item['provenance']}",
        f"  source: {json.dumps(item.get('source'), ensure_ascii=False, sort_keys=True)}",
        "  statuses: "
        + ", ".join(
            f"{key}={value}"
            for key, value in cast("dict[str, int]", item["status_counts"]).items()
        ),
    ]
    for member in cast("list[dict[str, object]]", item.get("members", [])):
        target = (
            "" if member.get("house_form") is None else f" -> {member['house_form']}"
        )
        reason = "" if member.get("reason") is None else f": {member['reason']}"
        lines.append(f"  [{member['status']}] {member['source_token']}{target}{reason}")
    return lines


def render_inventory_text(
    report: InventoryComparisonReport, *, direction: Direction | None = None
) -> str:
    """Render a human-readable report or one directional mapping slice."""
    document = _document(report)
    options = cast("dict[str, object]", document["options"])
    terms = cast("dict[str, object]", document["terms"])
    lines = [
        f"inventory comparison report: {document['identity']}",
        (
            "terms: raw feature distance (no reference scaling); "
            f"denominator={'applicable features only' if options['applicable_only'] else 'all declared features'}; "
            f"strip={options['strip'] or 'none'}"
        ),
        f"membership term: {terms['membership']}",
        "inputs:",
    ]
    for label, item in _inputs(document).items():
        lines.extend(_input_lines(label.upper(), item))

    membership = cast("dict[str, object]", document["membership"])
    if "union" in membership:
        lines.extend(
            [
                f"union: {' '.join(cast('list[str]', membership['union']))}",
                f"intersection: {' '.join(cast('list[str]', membership['intersection']))}",
                f"only A: {' '.join(cast('list[str]', membership['only_a']))}",
                f"only B: {' '.join(cast('list[str]', membership['only_b']))}",
            ]
        )
    else:
        lines.append(
            "membership counts: "
            + ", ".join(
                f"{key}={value}"
                for key, value in membership.items()
                if key.endswith("_count")
            )
        )

    for key, row in _mapping_rows(document, direction):
        label = "A -> B" if key == "a_to_b" else "B -> A"
        lines.append(
            f"\n{label}: mapped={row['mapped_count']} exact={row['exact_count']} "
            f"unmapped={row['unmapped_count']}"
        )
        if row.get("mean_distance") is not None:
            lines.append(f"mean distance: {cast('float', row['mean_distance']):.4f}")
        for coverage in cast("list[dict[str, object]]", row.get("coverage", [])):
            lines.append(
                f"coverage <= {coverage['max_distance']:g}: "
                f"{coverage['covered']}/{coverage['total']} "
                f"({cast('float', coverage['fraction']):.1%})"
            )
        for target, sources in cast(
            "dict[str, list[str]]", row.get("collapses", {})
        ).items():
            lines.append(f"nearest collapse onto {target}: {' '.join(sources)}")
        correspondences = cast(
            "list[dict[str, object]]", row.get("correspondences", [])
        )
        unmapped = [
            cast("str", item["source"])
            for item in correspondences
            if item.get("target") is None
        ]
        if unmapped:
            lines.append(f"unmapped: {' '.join(unmapped)}")
        for item in correspondences:
            mapped_target = cast("str | None", item.get("target")) or "-"
            distance = item.get("distance")
            shown = "-" if distance is None else f"{cast('float', distance):.4f}"
            reason = "" if item.get("reason") is None else f" ({item['reason']})"
            lines.append(f"{item['source']}\t{mapped_target}\t{shown}{reason}")

    matrices = document.get("matrices")
    if direction is None and isinstance(matrices, dict):
        matrix = cast("dict[str, object]", matrices["a_to_b"])
        lines.append("\nsimilarity matrix:")
        lines.append("\t" + "\t".join(cast("list[str]", matrix["columns"])))
        for phone, values in zip(
            cast("list[str]", matrix["rows"]),
            cast("list[list[float]]", matrix["values"]),
            strict=True,
        ):
            lines.append(phone + "\t" + "\t".join(f"{value:.4f}" for value in values))

    authority = document.get("authority_and_loss")
    if authority is not None:
        lines.append(
            "\nauthority and loss: "
            + json.dumps(authority, ensure_ascii=False, sort_keys=True)
        )
    return "\n".join(lines) + "\n"


def _matrix(document: dict[str, object]) -> dict[str, object]:
    matrices = cast("dict[str, object]", document.get("matrices"))
    if not matrices:
        raise ValueError("TSV and SVG rendering require a detailed pairwise report")
    return cast("dict[str, object]", matrices["a_to_b"])


def render_inventory_tsv(report: InventoryComparisonReport) -> str:
    """Render the legacy matrix first, then complete typed report rows."""
    from io import StringIO

    document = _document(report)
    matrix = _matrix(document)
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(("", *cast("list[str]", matrix["columns"])))
    for phone, values in zip(
        cast("list[str]", matrix["rows"]),
        cast("list[list[float]]", matrix["values"]),
        strict=True,
    ):
        writer.writerow((phone, *(f"{value:.12g}" for value in values)))
    writer.writerow(())
    writer.writerow(
        ("record", "input", "status", "source_token", "house_form", "value")
    )
    for label, item in _inputs(document).items():
        writer.writerow(("input", label, "", item["name"], "", item["provenance"]))
        writer.writerow(
            (
                "source",
                label,
                "",
                "",
                "",
                json.dumps(item.get("source"), ensure_ascii=False, sort_keys=True),
            )
        )
        for member in cast("list[dict[str, object]]", item.get("members", [])):
            writer.writerow(
                (
                    "member",
                    label,
                    member["status"],
                    member["source_token"],
                    member.get("house_form") or "",
                    member.get("reason") or "",
                )
            )
    writer.writerow(
        (
            "report",
            "",
            "",
            "identity",
            "",
            document["identity"],
        )
    )
    if document.get("authority_and_loss") is not None:
        writer.writerow(
            (
                "authority_and_loss",
                "",
                "",
                "",
                "",
                json.dumps(
                    document["authority_and_loss"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
    return stream.getvalue()


def render_inventory_markdown(
    report: InventoryComparisonReport, *, direction: Direction | None = None
) -> str:
    """Render a portable Markdown report from the canonical document."""
    document = _document(report)
    lines = ["# Inventory comparison", "", f"Report: `{document['identity']}`", ""]
    for label, item in _inputs(document).items():
        lines.extend(
            [
                f"## Input {label.upper()}: {item['name']}",
                "",
                f"- Kind: {item['kind']}",
                f"- Availability: {item['availability']}",
                f"- Provenance: {item['provenance']}",
                f"- Source: `{json.dumps(item.get('source'), ensure_ascii=False, sort_keys=True)}`",
                "",
                "| Status | Source token | House form | Reason |",
                "| --- | --- | --- | --- |",
            ]
        )
        for member in cast("list[dict[str, object]]", item.get("members", [])):
            lines.append(
                f"| {member['status']} | {member['source_token']} | "
                f"{member.get('house_form') or ''} | {member.get('reason') or ''} |"
            )
        lines.append("")
    lines.extend(["## Mapping", ""])
    for key, row in _mapping_rows(document, direction):
        label = "A to B" if key == "a_to_b" else "B to A"
        lines.extend(
            [
                f"### {label}",
                "",
                "| Source | Target | Distance | Relation | Reason |",
                "| --- | --- | ---: | --- | --- |",
            ]
        )
        for item in cast("list[dict[str, object]]", row.get("correspondences", [])):
            lines.append(
                f"| {item['source']} | {item.get('target') or ''} | "
                f"{item.get('distance') if item.get('distance') is not None else ''} | "
                f"{item['relation']} | {item.get('reason') or ''} |"
            )
        lines.append("")
    if document.get("authority_and_loss") is not None:
        lines.extend(
            [
                "## Authority and loss",
                "",
                "```json",
                json.dumps(
                    document["authority_and_loss"],
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                ),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
