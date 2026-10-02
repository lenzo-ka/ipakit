"""Inventory cards have declared inputs rather than hand-maintained facts."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit._identity import identity_fingerprint
from ipakit._provenance import SOURCE_ATTRIBUTES, SourceMetadata
from ipakit.inventories import _registry
from ipakit.inventory_comparison import (
    INVENTORY_COMPARISON_SCHEMA_ID,
    INVENTORY_COMPARISON_SCHEMA_VERSION,
)
from scripts.inventory_cards import (
    COMPARISON_EXAMPLES_MARKER,
    cards,
    validate_spdx,
)

ROOT = Path(__file__).resolve().parent.parent


def test_every_registry_entry_has_structured_source_metadata() -> None:
    registry = _registry()
    assert registry
    for name, (_, source) in registry.items():
        assert source.version, name
        assert all(source.to_dict().values()), name


def test_every_inventory_vocabulary_derives_provenance_from_fields() -> None:
    declarations = sorted((ROOT / "ipakit/data/bridges").glob("*/*.xml"))
    assert declarations
    for path in declarations:
        root = ET.parse(path).getroot()
        assert "provenance" not in root.attrib, path
        source = SourceMetadata.from_root(root, path)
        assert source.upstream in source.provenance
        assert source.artifact in source.provenance
        assert source.version in source.provenance or source.version == "unpinned"


def test_stored_provenance_is_refused_as_a_second_spelling() -> None:
    root = ET.fromstring(
        '<vocabulary upstream="u" upstream-url="https://example.test" '
        'artifact="a" version="unpinned" license="MIT" kind="k" '
        'provenance="duplicate" />'
    )
    with pytest.raises(ValueError, match="stores `provenance`"):
        SourceMetadata.from_root(root, "fixture")


def test_missing_source_field_is_refused_by_name() -> None:
    attributes = {name: "value" for name in SOURCE_ATTRIBUTES}
    attributes.pop("upstream-url")
    root = ET.Element("vocabulary", attributes)
    with pytest.raises(ValueError, match="`upstream-url`"):
        SourceMetadata.from_root(root, "fixture")


def test_every_declared_license_is_canonical_spdx() -> None:
    assert validate_spdx()


def test_cards_cover_registry_families_and_the_shipped_feature_model() -> None:
    families = {name.partition(":")[0] for name in _registry()}
    declared = cards()
    assert {card.family for card in declared} == families | {"espeak", "panphon"}
    assert all(card.notes for card in declared)


def test_generated_comparison_examples_are_canonical_experimental_reports() -> None:
    source = (ROOT / "docs/inventories.src.md").read_text(encoding="utf-8")
    generated = (ROOT / "docs/inventories.md").read_text(encoding="utf-8")
    assert source.count(COMPARISON_EXAMPLES_MARKER) == 1
    assert '"union_count"' not in source

    blocks = re.findall(
        r"<!-- inventory-comparison-example: ([^ ]+) -->\n" r"```json\n(.*?)\n```",
        generated,
        re.DOTALL,
    )
    assert [label for label, _ in blocks] == ["pairwise", "n-way"]
    documents = [json.loads(block) for _, block in blocks]
    for document in documents:
        assert document["schema"] == {
            "id": INVENTORY_COMPARISON_SCHEMA_ID,
            "version": INVENTORY_COMPARISON_SCHEMA_VERSION,
            "stability": "experimental",
        }
        identity = document.pop("identity")
        assert identity == identity_fingerprint(document)

    pairwise, nway = documents
    assert [item["name"] for item in pairwise["inputs"].values()] == [
        "cmudict",
        "timit",
    ]
    assert {item["name"] for item in nway["inputs"].values()} == {
        "cmudict",
        "timit",
        "mfa:english_us",
    }
    assert [measure["name"] for measure in nway["coverage"]] == [
        "overlap",
        "readable/admitted",
        "reviewed-mapped",
        "exact representability",
        "thresholded-nearest",
    ]
    assert all(
        {"numerator", "denominator", "definition", "status_buckets"} <= measure.keys()
        for measure in nway["coverage"]
    )
