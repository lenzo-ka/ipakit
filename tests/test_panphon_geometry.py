"""The checked panphon declaration is complete, faithful, and dev-only."""

from __future__ import annotations

import inspect
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit.bridges.base import Fidelity
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


def test_declaration_names_both_lossy_legs_and_the_silent_drop() -> None:
    pack = pack_from_declaration(DECLARATION)
    assert pack.bridge is not None
    report = pack.bridge.round_trip
    assert report.external_to_house.fidelity is Fidelity.LOSSY_WITH_REPORT
    assert report.house_to_external.fidelity is Fidelity.LOSSY_WITH_REPORT
    assert "silent segment deletion" in report.external_to_house.drops
    assert any("silently dropped" in loss for loss in report.house_to_external.drops)


def test_declaration_without_round_trip_legs_is_refused(tmp_path: Path) -> None:
    declaration = tmp_path / "unclassified.xml"
    declaration.write_text(
        """<feature-table name="unclassified">
  <features><feature name="f"/></features>
  <segments><segment name="a" f="+"/></segments>
</feature-table>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="round-trip classification"):
        pack_from_declaration(declaration)


def test_the_reader_takes_no_branch_on_a_foreign_system() -> None:
    """The loader reads whatever declaration it is handed, so it must not
    know whose declaration that is. Scoped to the loader deliberately --
    the module-wide half is the test below, and the two say different
    things."""
    source = inspect.getsource(pack_from_declaration).lower()
    assert "panphon" not in source


def test_the_module_names_a_foreign_system_only_as_a_policy_preset() -> None:
    """The wider half, which a single-function check cannot see.

    ``PANPHON_CONSERVING`` is a named ``CostPolicy`` -- a preset a caller
    may pick, calibrated against a system whose name it carries. That is
    not the reader branching on that system, so it is allowed and pinned
    by its exact text rather than waved past by a substring search.

    Pinned as the whole line so a second mention anywhere in the module
    fails here, including one added inside the preset's own statement.
    """
    import ipakit.bridges.costmodel as costmodel

    mentions = [
        line.strip()
        for line in inspect.getsource(costmodel).splitlines()
        if "panphon" in line.lower()
    ]
    assert mentions == ["PANPHON_CONSERVING = CostPolicy(substitution_scale=2.0)"]
