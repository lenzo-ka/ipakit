"""The single source receipt for the shipped Panphon feature declaration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ._identity import identity_fingerprint
from ._provenance import SourceMetadata
from ._source_receipt import (
    RECEIPT_SCHEMA_ID,
    RECEIPT_SCHEMA_VERSION,
    loads_receipt,
    validate_receipt,
)
from .constants import DATA_DIR
from .extraction import SourceContentError

DATA = DATA_DIR / "feature-models"
RECEIPT_NAME = "panphon-receipt.json"
ARTIFACT_NAME = "panphon.xml"
RECEIPT_KIND = "final"
RECEIPT_DOMAIN = "panphon-feature-table"
EXTRACTOR = {"id": "scripts.panphon_geometry.render", "version": "1"}
NOTICE_FILES = ("NOTICE.md", "PANPHON-LICENSE.txt")
INPUT_FILES = ("feature_weights.csv", "ipa_all.csv")
_RECEIPT_FIELDS = (
    "schema",
    "kind",
    "domain",
    "source-policy",
    "extractor",
    "artifacts",
    "license",
    "fingerprint",
)


def source_receipt(data_dir: Path = DATA) -> dict[str, Any]:
    """Decode and validate the one Panphon provenance authority."""
    try:
        return loads_receipt((data_dir / RECEIPT_NAME).read_bytes())
    except (OSError, ValueError) as error:
        raise SourceContentError(f"invalid Panphon source receipt: {error}") from error


def source_policy(data_dir: Path = DATA) -> dict[str, Any]:
    """Return the source policy stored in the Panphon receipt."""
    return dict(source_receipt(data_dir)["source-policy"])


def source_metadata(data_dir: Path = DATA) -> SourceMetadata:
    """Expose Panphon's source identity from the receipt, never from XML."""
    source = source_policy(data_dir)["source"]
    return SourceMetadata(
        source["upstream"],
        source["upstream-url"],
        source["artifact"],
        source["version"],
        source["license"],
        source["kind"],
    )


def receipt_metadata(
    policy: dict[str, Any], xml: bytes, notices: dict[str, bytes]
) -> dict[str, Any]:
    """Build Panphon's deterministic receipt from its source and shipped bytes."""
    material = {
        "schema": {"id": RECEIPT_SCHEMA_ID, "version": RECEIPT_SCHEMA_VERSION},
        "kind": RECEIPT_KIND,
        "domain": RECEIPT_DOMAIN,
        "source-policy": policy,
        "extractor": dict(EXTRACTOR),
        "artifacts": {ARTIFACT_NAME: {"sha256": hashlib.sha256(xml).hexdigest()}},
        "license": {
            "id": policy["source"]["license"],
            "notices": {
                name: hashlib.sha256(notices[name]).hexdigest() for name in NOTICE_FILES
            },
        },
    }
    receipt = {**material, "fingerprint": identity_fingerprint(material)}
    validate_receipt(receipt)
    return receipt


def verify_manifest(data_dir: Path = DATA) -> str:
    """Recompute the Panphon receipt and refuse the first stale field by name."""
    try:
        actual = source_receipt(data_dir)
        policy = actual["source-policy"]
        if set(policy["inputs"]) != set(INPUT_FILES):
            raise SourceContentError("stale Panphon manifest field: source-policy")
        xml = (data_dir / ARTIFACT_NAME).read_bytes()
        root = ET.fromstring(xml)
        if root.attrib != {
            "name": "panphon",
            "source-receipt": RECEIPT_NAME,
        }:
            raise SourceContentError("stale Panphon manifest field: artifacts")
        notices = {name: (data_dir / name).read_bytes() for name in NOTICE_FILES}
        expected = receipt_metadata(policy, xml, notices)
        for field in _RECEIPT_FIELDS:
            if actual[field] != expected[field]:
                raise SourceContentError(f"stale Panphon manifest field: {field}")
        return str(actual["fingerprint"])
    except SourceContentError:
        raise
    except (ET.ParseError, KeyError, OSError, TypeError, ValueError) as error:
        raise SourceContentError(f"invalid Panphon source receipt: {error}") from error
