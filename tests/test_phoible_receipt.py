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
    "LICENSE": "fe3eea6c599e23a00c08c5f5cb2320c30adc8f8687db5fcec9b79a662c53ff6b",
    "data/LICENSE": "1fd7aa5b633e044a8d9ca473a281d5e495a7186703b8c3b576344b20b910860e",
    "data/phoible-references.bib": "29da90c2b2b71ecc30cf8fab5fc6d194ada179909a57b3c65abc8e887c4d62f1",
    "data/phoible.csv": "395e0977c3a5402af9cd5effd4ffdf0e47396336241fac534a4706e3cd8a7ecf",
    "mappings/InventoryID-Bibtex.csv": "fa4cf302b0c5df23c76849b70ec8719042709a2dec8c5715cf5f69469cb04f39",
    "mappings/InventoryID-LanguageCodes.csv": "0b8bd77e1f8e84be4096a8c8c0332d6bc69b058a364664335440b910ac39fc06",
}
ARTIFACT_HASHES = {
    "GPL-3.0.txt": "fe3eea6c599e23a00c08c5f5cb2320c30adc8f8687db5fcec9b79a662c53ff6b",
    "MIT-upstream.txt": "1fd7aa5b633e044a8d9ca473a281d5e495a7186703b8c3b576344b20b910860e",
    "data/phoible-references.bib.gz": "7bb1ca2c6c0b1f82ab400bf1d738c274b7b25e5fed0124db63953da682169f33",
    "data/phoible.csv.gz": "30b6620e3d3ca67bd67341dda029cc7685b9e5a2e3ddb281032e1fc06fd36a16",
    "mappings/InventoryID-Bibtex.csv.gz": "fac4715a8cd78d4f3f59163ab6b30701e0127b8613671be96d6a8f100c61814a",
    "mappings/InventoryID-LanguageCodes.csv.gz": "c0d7f616c408410b71005e71e0689b807cd06cd0127dda27df3da13efe1fb8da",
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
        "artifact": "separately licensed source-data aggregate",
        "kind": "inventory-catalog-source",
        "license": "LicenseRef-PHOIBLE-Source-Aggregate",
        "upstream": "PHOIBLE (Moran, McCloy and contributors)",
        "upstream-url": "https://github.com/phoible/dev/tree/b92abff4f4ca2544eece4d9eff5c707f8d508d0c",
        "version": "b92abff4f4ca2544eece4d9eff5c707f8d508d0c",
    }
    assert receipt["source-policy"]["inputs"] == SOURCE_INPUTS
    assert {
        name: artifact["sha256"] for name, artifact in receipt["artifacts"].items()
    } == ARTIFACT_HASHES
    assert receipt["fingerprint"] == (
        "sha256:4cbbc5b5d27e1eef2770284a547059f1644546904bc3c74ea6c9b591c688b076"
    )


def test_receipt_verifies_and_old_authorities_are_gone() -> None:
    assert phoible_source.verify_manifest() == (
        "sha256:4cbbc5b5d27e1eef2770284a547059f1644546904bc3c74ea6c9b591c688b076"
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


@pytest.mark.parametrize("name", ["NOTICE.txt", "GPL-3.0.txt"])
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
