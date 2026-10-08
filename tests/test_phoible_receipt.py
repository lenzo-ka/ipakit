"""PHOIBLE's shared-schema receipt is literal, reproducible and falsifiable."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from ipakit import phoible_source
from ipakit._identity import identity_fingerprint
from ipakit.extraction import SourceContentError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipakit/data/phoible"
MANIFEST = DATA / "manifest.json"
SOURCE_INPUTS = {
    "LICENSE-DATA": "9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94",
    "data/phoible.csv": "0816e698563b68ec6a309bab404a06dfb221d4334aa5ffcbc0c18f2bd01844b8",
    "mappings/InventoryID-Bibtex.csv": "5b5f57f615a7f8cbe47f1784e2928ce786088f95d833f6a6f4ea28ad7cffaf5e",
    "mappings/InventoryID-Filenames.csv": "330b3e5af9412a9d4d228c11eece31de30c7fa953d650679d0077fe695fac250",
    "mappings/InventoryID-LanguageCodes.csv": "69406ad7738b064ff7a9e133695aa7b66ce407d2f973c47ebd3aca371fbbdfff",
    "mappings/phoible-references.bib": "52e175fde9973d4ed7a5283ba77bd53e9ec2384c08833c46bae076c37c9ed7a3",
}
ARTIFACT_HASHES = {
    "CC-BY-4.0.txt": "9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94",
    "data/phoible.csv.gz": "ac00c157904d2cc75420732878fc3fb5a9d0b23565389ac80df036b0df621c70",
    "mappings/InventoryID-Bibtex.csv.gz": "57a9c28f420c7fb6a26fb29e4a07c01b0f8a66cc0c0d081ad016cf4f1d38c435",
    "mappings/InventoryID-Filenames.csv.gz": "350cac5f51c6ec3cd469f969ce3bfdad9c0cbe7ea189f7e75343c2b73f84b578",
    "mappings/InventoryID-LanguageCodes.csv.gz": "216de5852564cb2bea169f4d3e1717506ed454c35613be8a3faab9aa993ea929",
    "mappings/phoible-references.bib.gz": "3aab8ac82307df4951c4e0cb5c7b99bd9b2d7c653032e717de2605dd58c1ebf9",
}


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "phoible"
    shutil.copytree(DATA, target)
    return target


def _reseal(path: Path, data: dict[str, object]) -> None:
    material = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = identity_fingerprint(material)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def test_receipt_fields_are_literal_and_complete() -> None:
    receipt = json.loads(MANIFEST.read_bytes())
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
    assert receipt["domain"] == "phoible-source-aggregate"
    assert receipt["source-policy"]["source"] == {
        "artifact": "PHOIBLE dataset, mapping tables and reference bibliography",
        "kind": "inventory-catalog-source",
        "license": "CC-BY-4.0",
        "upstream": "PHOIBLE (Moran, McCloy and contributors)",
        "upstream-url": "https://github.com/phoible/dev/tree/5f82b9c3fbb0b5c630de20e254c5fdad645e3e56",
        "version": "5f82b9c3fbb0b5c630de20e254c5fdad645e3e56",
    }
    assert receipt["source-policy"]["inputs"] == SOURCE_INPUTS
    assert {
        name: artifact["sha256"] for name, artifact in receipt["artifacts"].items()
    } == ARTIFACT_HASHES
    assert receipt["fingerprint"] == (
        "sha256:02a0e38f6f9de359c597f88fe89d05626cc018ebea9ceef3e35452e73776adf2"
    )


def test_receipt_verifies_and_old_authorities_are_gone() -> None:
    assert phoible_source.verify_manifest() == (
        "sha256:02a0e38f6f9de359c597f88fe89d05626cc018ebea9ceef3e35452e73776adf2"
    )
    receipt = phoible_source.source_receipt()
    assert not (ROOT / "ipakit/data/phoible-policy.json").exists()
    assert not {"source", "source-sha256", "transport", "transport-sha256"} & set(
        receipt
    )
    with pytest.raises(KeyError):
        _ = receipt["source"]  # a consumer of the retired shape must fail


def test_resealed_transport_edit_is_stale_by_source_policy(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    artifact = data_dir / "data/phoible.csv.gz"
    artifact.write_bytes(gzip.compress(b"fault-injected source bytes"))
    receipt = json.loads((data_dir / "manifest.json").read_bytes())
    receipt["artifacts"]["data/phoible.csv.gz"]["sha256"] = hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    _reseal(data_dir / "manifest.json", receipt)
    with pytest.raises(
        SourceContentError, match="stale PHOIBLE manifest field: source-policy"
    ):
        phoible_source.verify_manifest(data_dir)


@pytest.mark.parametrize("name", ["NOTICE.txt", "CC-BY-4.0.txt"])
def test_notice_or_license_edit_is_refused(tmp_path: Path, name: str) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / name
    path.write_bytes(path.read_bytes() + b"fault\n")
    with pytest.raises(SourceContentError, match="stale PHOIBLE manifest field"):
        phoible_source.verify_manifest(data_dir)


def test_unknown_top_level_field_is_refused(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "manifest.json"
    receipt = json.loads(path.read_bytes())
    receipt["fault"] = True
    _reseal(path, receipt)
    with pytest.raises(SourceContentError, match="unexpected receipt fields"):
        phoible_source.verify_manifest(data_dir)


def test_duplicate_json_key_is_refused(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "manifest.json"
    content = path.read_text()
    path.write_text(content.replace("{\n", '{\n  "kind": "final",\n', 1))
    with pytest.raises(SourceContentError, match="duplicate JSON key: kind"):
        phoible_source.verify_manifest(data_dir)
