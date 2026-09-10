"""Inventory cards have declared inputs rather than hand-maintained facts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit._provenance import SOURCE_ATTRIBUTES, SourceMetadata
from ipakit.inventories import _registry
from scripts.inventory_cards import cards, validate_spdx

ROOT = Path(__file__).resolve().parent.parent


def test_every_registry_entry_has_structured_source_metadata() -> None:
    registry = _registry()
    assert len(registry) == 175
    for name, (_, source) in registry.items():
        assert source.version, name
        assert all(source.to_dict().values()), name


def test_every_inventory_vocabulary_derives_provenance_from_fields() -> None:
    declarations = sorted((ROOT / "ipakit/data/bridges").glob("*/*.xml"))
    assert len(declarations) == 171
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
    assert validate_spdx() > 170


def test_cards_cover_registry_families_and_the_dev_comparison() -> None:
    families = {name.partition(":")[0] for name in _registry()}
    declared = cards()
    assert {card.family for card in declared} == families | {"panphon"}
    assert all(card.notes for card in declared)
