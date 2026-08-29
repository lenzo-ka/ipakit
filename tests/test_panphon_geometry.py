"""The checked panphon declaration is complete, faithful, and dev-only."""

from __future__ import annotations

import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from ipakit.bridges.costmodel import pack_from_declaration

DECLARATION = Path(__file__).parent / "panphon" / "panphon.xml"


def _root() -> ET.Element:
    return ET.parse(DECLARATION).getroot()


def test_declaration_has_the_full_ternary_table_and_provenance() -> None:
    root = _root()
    features = [item.get("name") for item in root.findall("features/feature")]
    segments = root.findall("segments/segment")
    assert len(features) == 24
    assert len(segments) == 6367
    assert root.get("version") == "0.22.2"
    assert len(root.get("ipa-all-sha256", "")) == 64
    assert len(root.get("feature-weights-sha256", "")) == 64
    assert all(
        item.get(name) in {"-", "0", "+"} for item in segments for name in features
    )
    assert all("applies" not in item.attrib for item in root.iter())


def test_segment_keys_are_unique_nfd_spellings() -> None:
    names = [item.get("name", "") for item in _root().findall("segments/segment")]
    assert len(set(names)) == 6367
    assert all(name == unicodedata.normalize("NFD", name) for name in names)


def test_weight_order_remains_distinct_from_feature_order() -> None:
    root = _root()
    features = [item.get("name") for item in root.findall("features/feature")]
    weights = [item.get("name") for item in root.findall("weights/weight")]
    assert len(weights) == 22
    assert features[19:22] == ["velaric", "tense", "long"]
    assert weights[19:22] == ["tense", "long", "velaric"]


def test_generic_loader_reports_unknown_material_and_reads_zero_verbatim() -> None:
    pack = pack_from_declaration(DECLARATION)
    assert pack.geometry == "panphon/0.22.2"
    assert pack.tokenize("bɚd").dropped == ("ɚ",)
    assert pack.insert_cost("˧") == 0.5
