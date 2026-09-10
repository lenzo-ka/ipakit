#!/usr/bin/env python3
"""Generate the inventory-family cards from declarations and live counts."""

from __future__ import annotations

import argparse
import difflib
import os
import string
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "inventories.src.md"
TARGET = ROOT / "docs" / "inventories.md"
CARDS = ROOT / "ipakit" / "data" / "inventory-cards.xml"
DEFAULT_MFA_MODELS = Path(
    os.environ.get("MFA_MODELS", Path.home() / ".cache" / "ipakit" / "mfa-models")
)
BANNER = (
    "<!-- Generated from docs/inventories.src.md and "
    "ipakit/data/inventory-cards.xml by scripts/inventory_cards.py. "
    "Do not edit: run `make inventory-cards`. -->"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ipakit._provenance import SourceMetadata  # noqa: E402
from ipakit.inventories import (  # noqa: E402
    inventories,
    inventory,
    inventory_from_dictionary,
)


@dataclass(frozen=True)
class Card:
    """One declared family card before computed values are inserted."""

    family: str
    title: str
    sources: tuple[str, ...]
    purpose: str
    conventions: str
    strengths: str
    limitations: str
    notes: tuple[str, ...]


def _text(root: ET.Element, name: str) -> str:
    item = root.find(name)
    if item is None or not (item.text or "").strip():
        raise ValueError(f"card {root.get('family')!r} has no {name}")
    return (item.text or "").strip()


def cards() -> tuple[Card, ...]:
    """Read every card and reject duplicate or incomplete family metadata."""
    root = ET.parse(CARDS).getroot()
    result = []
    for item in root.findall("card"):
        family = item.get("family", "").strip()
        title = item.get("title", "").strip()
        sources = tuple(
            source.get("path", "").strip() for source in item.findall("source")
        )
        notes = tuple((note.text or "").strip() for note in item.findall("note"))
        if not family or not title or not sources or not all(sources):
            raise ValueError("every inventory card needs a family, title, and source")
        if not notes or not all(notes):
            raise ValueError(f"card {family!r} has no specific note")
        result.append(
            Card(
                family,
                title,
                sources,
                _text(item, "purpose"),
                _text(item, "conventions"),
                _text(item, "strengths"),
                _text(item, "limitations"),
                notes,
            )
        )
    names = [card.family for card in result]
    if len(names) != len(set(names)):
        raise ValueError("inventory card families are not unique")
    return tuple(result)


def _spdx(identifier: str) -> None:
    """Require one canonical SPDX license identifier or LicenseRef."""
    try:
        from packaging.licenses import (
            InvalidLicenseExpression,
            canonicalize_license_expression,
        )
    except ImportError as error:
        raise ValueError(
            "SPDX validation needs the test dependency: install `.[test]`"
        ) from error
    try:
        canonical = canonicalize_license_expression(identifier)
    except InvalidLicenseExpression as error:
        raise ValueError(f"invalid SPDX license identifier {identifier!r}") from error
    if canonical != identifier or any(
        word in identifier for word in (" AND ", " OR ", " WITH ")
    ):
        raise ValueError(
            f"license must be one canonical SPDX identifier, got {identifier!r}"
        )


def validate_spdx() -> int:
    """Validate every license identifier declared by an XML document."""
    checked = 0
    for path in sorted((*ROOT.glob("ipakit/**/*.xml"), *ROOT.glob("tests/**/*.xml"))):
        for element in ET.parse(path).getroot().iter():
            for attribute in ("license", "spdx"):
                if identifier := element.get(attribute):
                    try:
                        _spdx(identifier)
                    except ValueError as error:
                        raise ValueError(
                            f"{path.relative_to(ROOT)}: {error}"
                        ) from error
                    checked += 1
    if not checked:
        raise ValueError("no declared SPDX license identifiers were checked")
    return checked


def _source_paths(card: Card) -> tuple[Path, ...]:
    paths = tuple(
        path for pattern in card.sources for path in sorted(ROOT.glob(pattern))
    )
    if not paths:
        raise ValueError(f"card {card.family!r} source patterns match no declarations")
    return paths


def _sources(card: Card) -> tuple[SourceMetadata, ...]:
    return tuple(
        SourceMetadata.from_root(ET.parse(path).getroot(), path.relative_to(ROOT))
        for path in _source_paths(card)
    )


def _common(card: Card, sources: tuple[SourceMetadata, ...], field: str) -> str:
    values = {getattr(source, field) for source in sources}
    if len(values) != 1:
        raise ValueError(
            f"card {card.family!r} sources disagree on {field}: {sorted(values)!r}"
        )
    return values.pop()


def _family_names() -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for name in inventories():
        grouped[name.partition(":")[0]].append(name)
    return {family: tuple(names) for family, names in grouped.items()}


def _mfa_metrics(source: Path) -> dict[str, object]:
    from scripts.mfa_vocabularies import PIN, require_pin

    require_pin(source)
    dictionary = source / "dictionary" / "english" / "us_mfa" / "english_us_mfa.dict"
    if not dictionary.is_file():
        raise ValueError(f"pinned MFA en-US dictionary is absent: {dictionary}")
    declared = inventory("mfa:english_us")
    if declared.version != PIN:
        raise ValueError(
            f"mfa:english_us declares {declared.version!r}, but the generator uses {PIN!r}"
        )
    item = inventory_from_dictionary(dictionary, "mfa:english_us")
    filtered = inventory_from_dictionary(dictionary, "mfa:english_us", min_entries=50)
    total = sum(count["tokens"] for count in item.counts.values())
    running = 0
    core = 0
    for index, (_, count) in enumerate(
        sorted(item.counts.items(), key=lambda pair: (-pair[1]["tokens"], pair[0])),
        1,
    ):
        running += count["tokens"]
        if running * 100 >= total * 99:
            core = index
            break
    counts = item.counts
    return {
        "mfa_en_us_types": len(counts),
        "mfa_en_us_tokens": total,
        "mfa_en_us_core_99": core,
        "mfa_en_us_placeholders": len(item.refusals),
        "mfa_en_us_placeholder_names": ", ".join(item.refusals),
        "mfa_en_us_min_50_kept": len(filtered.phones or ()),
        "mfa_en_us_min_50_dropped": len(filtered.dropped),
        "p_labialized_entries": counts["pʷ"]["entries"],
        "g_labialized_entries": counts["ɡʷ"]["entries"],
        "labiodental_nasal_entries": counts["ɱ"]["entries"],
        "labiodental_nasal_tokens": counts["ɱ"]["tokens"],
    }


def _panphon_metrics() -> dict[str, object]:
    root = ET.parse(ROOT / "tests" / "panphon" / "panphon.xml").getroot()
    return {
        "panphon_segments": len(root.findall("segments/segment")),
        "panphon_features": len(root.findall("features/feature")),
        "panphon_weights": len(root.findall("weights/weight")),
    }


def _quantitative(
    family: str, names: tuple[str, ...], metrics: dict[str, object]
) -> list[tuple[str, str]]:
    if family == "panphon":
        return [
            ("Shipped registry entries", "0 — development comparison only"),
            ("Declared segment rows", str(metrics["panphon_segments"])),
            ("Declared features", str(metrics["panphon_features"])),
            ("Supplied feature weights", str(metrics["panphon_weights"])),
        ]
    items = [inventory(name) for name in names]
    finite = [item for item in items if item.phones is not None]
    if not finite:
        phones = "Not finite"
    elif len(finite) == 1:
        phones = str(len(finite[0].phones or ()))
    else:
        union = next((item for item in finite if item.name == family), None)
        scoped = [item for item in finite if item.name != family]
        sizes = [len(item.phones or ()) for item in scoped]
        parts = []
        if union is not None:
            parts.append(f"{len(union.phones or ())} in `{family}` union")
        if sizes:
            parts.append(
                f"{min(sizes)}–{max(sizes)} across {len(scoped)} scoped members"
            )
        phones = "; ".join(parts)
    rows = [
        ("Registry entries", str(len(names))),
        ("Finite inventories", str(len(finite))),
        ("Phone counts", phones),
    ]
    if family == "mfa":
        rows.extend(
            [
                (
                    "Pinned en-US dictionary phone types",
                    str(metrics["mfa_en_us_types"]),
                ),
                (
                    "Pinned en-US dictionary phone tokens",
                    f"{int(metrics['mfa_en_us_tokens']):,}",
                ),
                (
                    "Pinned en-US dictionary at `min_entries=50`",
                    f"{metrics['mfa_en_us_min_50_kept']} kept; "
                    f"{metrics['mfa_en_us_min_50_dropped']} dropped",
                ),
                (
                    "Pinned en-US marker-only entries",
                    str(metrics["mfa_en_us_placeholders"]),
                ),
            ]
        )
    return rows


def _format_note(text: str, metrics: dict[str, object], family: str) -> str:
    fields = {name for _, name, _, _ in string.Formatter().parse(text) if name}
    missing = fields - metrics.keys()
    if missing:
        raise ValueError(f"card {family!r} note has unknown fields {sorted(missing)!r}")
    return text.format_map(metrics)


def render(mfa_models: Path) -> str:
    """Render the hand-written introduction and every declared family card."""
    declared_cards = cards()
    family_names = _family_names()
    expected = set(family_names) | {"panphon"}
    found = {card.family for card in declared_cards}
    if found != expected:
        raise ValueError(
            f"card families disagree with registry families: "
            f"missing {sorted(expected - found)!r}, extra {sorted(found - expected)!r}"
        )
    spdx_count = validate_spdx()
    metrics = {**_mfa_metrics(mfa_models), **_panphon_metrics()}
    source_lines = SOURCE.read_text(encoding="utf-8").rstrip().splitlines()
    if not source_lines or not source_lines[0].startswith("# "):
        raise ValueError("inventory source must open with one level-one heading")
    lines = [source_lines[0], "", BANNER, *source_lines[1:]]
    for card in declared_cards:
        sources = _sources(card)
        for source in sources:
            _spdx(source.license)
        upstream = _common(card, sources, "upstream")
        upstream_url = _common(card, sources, "upstream_url")
        version = _common(card, sources, "version")
        license_id = _common(card, sources, "license")
        kind = _common(card, sources, "kind")
        artifacts = sorted({source.artifact for source in sources})
        artifact = (
            artifacts[0]
            if len(artifacts) == 1
            else (
                "; ".join(artifacts)
                if len(artifacts) <= 3
                else (
                    f"{len(artifacts)} declared artifacts across {len(sources)} declarations "
                    f"(from {artifacts[0]} through {artifacts[-1]})"
                )
            )
        )
        paths = ", ".join(f"`{pattern}`" for pattern in card.sources)
        lines.extend(
            [
                "",
                f"## {card.title}",
                "",
                "### Declared source",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Upstream | [{upstream}]({upstream_url}) |",
                f"| Artifact | {artifact} |",
                f"| Pin | `{version}` |",
                f"| License | `{license_id}` |",
                f"| Kind | `{kind}` |",
                f"| Declarations | {paths} ({len(sources)}) |",
                "",
                "### Quantitative",
                "",
                "| Measure | Value |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {measure} | {value} |"
            for measure, value in _quantitative(
                card.family, family_names.get(card.family, ()), metrics
            )
        )
        lines.extend(
            [
                "",
                "### Qualitative",
                "",
                card.purpose,
                "",
                f"**Conventions.** {card.conventions}",
                "",
                f"**Good at.** {card.strengths}",
                "",
                f"**Less good at.** {card.limitations}",
                "",
                "### Notes",
                "",
            ]
        )
        lines.extend(
            f"- {_format_note(note, metrics, card.family)}" for note in card.notes
        )
    lines.extend(["", f"<!-- SPDX identifiers checked: {spdx_count}. -->", ""])
    return "\n".join(lines)


def check(expected: str) -> bool:
    """Compare a fresh rendering with the checked-in page byte for byte."""
    if not TARGET.is_file():
        print("inventory-cards: docs/inventories.md is missing", file=sys.stderr)
        return False
    actual = TARGET.read_text(encoding="utf-8")
    if actual == expected:
        print("inventory-cards: docs/inventories.md is current")
        return True
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile="checked-in docs/inventories.md",
        tofile="freshly generated docs/inventories.md",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "check"))
    parser.add_argument("--mfa-models", type=Path, default=DEFAULT_MFA_MODELS)
    args = parser.parse_args()
    try:
        result = render(args.mfa_models)
    except ValueError as error:
        print(f"inventory-cards: {error}", file=sys.stderr)
        return 2
    if args.mode == "build":
        TARGET.write_text(result, encoding="utf-8")
        print("inventory-cards: wrote docs/inventories.md")
        return 0
    return 0 if check(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
