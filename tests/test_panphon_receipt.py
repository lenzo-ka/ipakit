"""Panphon's shared-schema receipt is literal, reproducible and falsifiable."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from ipakit._identity import identity_fingerprint
from ipakit.extraction import SourceContentError
from ipakit.panphon_source import source_receipt, verify_manifest
from scripts import panphon_geometry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipakit/data/feature-models"
RECEIPT = DATA / "panphon-receipt.json"
SOURCE_INPUTS = {
    "feature_weights.csv": "03e80a6489e4993de6f17e063eaa74eb59c1d9ba9bc0dec9bec6ffce0cb8080d",
    "ipa_all.csv": "0ec0052edf4e58c8c23eda10c0195687eb167ce9bd206cf9a85b9cce8b181f0a",
}


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "feature-models"
    shutil.copytree(DATA, target)
    return target


def _reseal(path: Path, data: dict[str, object]) -> None:
    material = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = identity_fingerprint(material)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def test_receipt_fields_are_literal_and_complete() -> None:
    receipt = json.loads(RECEIPT.read_bytes())
    assert set(receipt) == {
        "schema",
        "kind",
        "domain",
        "source-policy",
        "extractor",
        "artifacts",
        "license",
        "fingerprint",
    }
    assert receipt["schema"] == {"id": "ipakit-source-receipt", "version": 1}
    assert receipt["kind"] == "final"
    assert receipt["domain"] == "panphon-feature-table"
    assert receipt["source-policy"]["source"] == {
        "artifact": "ipa_all.csv and feature_weights.csv",
        "kind": "phonetic-feature-table",
        "license": "MIT",
        "upstream": "Panphon",
        "upstream-url": "https://github.com/dmort27/panphon",
        "version": "0.22.2",
    }
    assert receipt["source-policy"]["inputs"] == SOURCE_INPUTS
    assert receipt["artifacts"] == {
        "panphon.xml": {
            "sha256": "dc782cfbb1fd61cd8845ff0db583bb7095c5f130ec5b06bbc3932bf65375f4da"
        }
    }
    assert receipt["fingerprint"] == (
        "sha256:6866bfbb997e89a26a127b09028abbc2ca754eb2d1a44b62d8a3919a7d37ef0f"
    )


def test_receipt_verifies_and_xml_has_only_a_pointer() -> None:
    assert verify_manifest() == (
        "sha256:6866bfbb997e89a26a127b09028abbc2ca754eb2d1a44b62d8a3919a7d37ef0f"
    )
    assert panphon_geometry.verify_manifest() == source_receipt()["fingerprint"]
    root = ET.parse(DATA / "panphon.xml").getroot()
    assert root.attrib == {
        "name": "panphon",
        "source-receipt": "panphon-receipt.json",
    }
    with pytest.raises(KeyError):
        _ = root.attrib["version"]  # a consumer of the retired shape must fail


def test_resealed_declaration_edit_is_stale_to_live_verifier(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    artifact = data_dir / "panphon.xml"
    content = artifact.read_text()
    artifact.write_text(content.replace('name="p" syl="-"', 'name="p" syl="+"', 1))
    receipt = json.loads((data_dir / "panphon-receipt.json").read_bytes())
    receipt["artifacts"]["panphon.xml"]["sha256"] = hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    _reseal(data_dir / "panphon-receipt.json", receipt)
    with pytest.raises(
        SourceContentError, match="stale Panphon manifest field: artifacts"
    ):
        panphon_geometry.verify_manifest(data_dir)


@pytest.mark.parametrize("name", ["NOTICE.md", "PANPHON-LICENSE.txt"])
def test_notice_or_license_edit_is_refused(tmp_path: Path, name: str) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / name
    path.write_bytes(path.read_bytes() + b"fault\n")
    with pytest.raises(
        SourceContentError, match="stale Panphon manifest field: license"
    ):
        verify_manifest(data_dir)


def test_unknown_top_level_field_is_refused(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "panphon-receipt.json"
    receipt = json.loads(path.read_bytes())
    receipt["fault"] = True
    _reseal(path, receipt)
    with pytest.raises(SourceContentError, match="unexpected receipt fields"):
        verify_manifest(data_dir)


def test_duplicate_json_key_is_refused(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "panphon-receipt.json"
    content = path.read_text()
    path.write_text(content.replace("{\n", '{\n  "kind": "final",\n', 1))
    with pytest.raises(SourceContentError, match="duplicate JSON key: kind"):
        verify_manifest(data_dir)


def test_generator_is_byte_equal_offline() -> None:
    assert panphon_geometry.build().stale(ROOT) == []
