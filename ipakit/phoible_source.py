"""Discover the shipped PHOIBLE source bytes, without importing a provider.

The aggregate retains all foreign columns and inventories. Decoding those bytes
as a house inventory is the separate, explicitly lossy bridge operation.
"""

from __future__ import annotations

import gzip
import hashlib
import zlib
from importlib.resources import files
from typing import Any

from ._identity import identity_fingerprint
from ._provenance import SourceMetadata
from ._source_receipt import (
    RECEIPT_SCHEMA_ID,
    RECEIPT_SCHEMA_VERSION,
    loads_receipt,
    validate_receipt,
)
from .extraction import SourceContentError, SourceMissingError

RECEIPT_KIND = "final"
RECEIPT_DOMAIN = "phoible-source-aggregate"
EXTRACTOR = {"id": "ipakit.extraction.phoible.build", "version": "1"}
ARTIFACT_INPUTS = {
    "data/phoible-references.bib.gz": "data/phoible-references.bib",
    "data/phoible.csv.gz": "data/phoible.csv",
    "mappings/InventoryID-Bibtex.csv.gz": "mappings/InventoryID-Bibtex.csv",
    "mappings/InventoryID-LanguageCodes.csv.gz": (
        "mappings/InventoryID-LanguageCodes.csv"
    ),
    "MIT-upstream.txt": "data/LICENSE",
    "GPL-3.0.txt": "LICENSE",
}
NOTICE_FILES = (
    "CC-BY-SA-3.0.txt",
    "GPL-3.0.txt",
    "MIT-upstream.txt",
    "NOTICE.txt",
)
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


def _data_root() -> Any:
    return files("ipakit").joinpath("data/phoible")


def source_receipt(data_dir: Any | None = None) -> dict[str, Any]:
    """Read the one PHOIBLE provenance authority with strict JSON semantics."""
    root = _data_root() if data_dir is None else data_dir
    try:
        return loads_receipt(root.joinpath("manifest.json").read_bytes())
    except (OSError, ValueError) as error:
        raise SourceContentError(f"invalid PHOIBLE source receipt: {error}") from error


def source_policy() -> dict[str, Any]:
    """Return a fresh copy of the accepted source pin and consumed hashes."""
    return dict(source_receipt()["source-policy"])


def source_files() -> tuple[str, ...]:
    """List original upstream data paths available as exact decompressed bytes."""
    return tuple(
        name for name in source_policy()["inputs"] if name.endswith((".csv", ".bib"))
    )


def source_metadata() -> SourceMetadata:
    """Describe the accepted snapshot, not the identity of an external checkout."""
    source = source_policy()["source"]
    return SourceMetadata(
        source["upstream"],
        source["upstream-url"],
        source["artifact"],
        source["version"],
        source["license"],
        source["kind"],
    )


def receipt_metadata(
    policy: dict[str, Any],
    artifacts: dict[str, bytes],
    notices: dict[str, bytes],
) -> dict[str, Any]:
    """Build the deterministic PHOIBLE receipt from source and shipped bytes."""
    material = {
        "schema": {"id": RECEIPT_SCHEMA_ID, "version": RECEIPT_SCHEMA_VERSION},
        "kind": RECEIPT_KIND,
        "domain": RECEIPT_DOMAIN,
        "source-policy": policy,
        "extractor": dict(EXTRACTOR),
        "artifacts": {
            name: {"sha256": hashlib.sha256(artifacts[name]).hexdigest()}
            for name in ARTIFACT_INPUTS
        },
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


def verify_manifest(data_dir: Any | None = None) -> str:
    """Recompute the PHOIBLE receipt and refuse the first stale field by name."""
    root = _data_root() if data_dir is None else data_dir
    try:
        actual = source_receipt(root)
        policy = actual["source-policy"]
        artifacts = {name: root.joinpath(name).read_bytes() for name in ARTIFACT_INPUTS}
        notices = {name: root.joinpath(name).read_bytes() for name in NOTICE_FILES}
        for artifact, source_name in ARTIFACT_INPUTS.items():
            content = artifacts[artifact]
            if artifact.endswith(".gz"):
                content = gzip.decompress(content)
            if hashlib.sha256(content).hexdigest() != policy["inputs"][source_name]:
                raise SourceContentError("stale PHOIBLE manifest field: source-policy")
        expected = receipt_metadata(policy, artifacts, notices)
        for field in _RECEIPT_FIELDS:
            if actual[field] != expected[field]:
                raise SourceContentError(f"stale PHOIBLE manifest field: {field}")
        return str(actual["fingerprint"])
    except SourceContentError:
        raise
    except FileNotFoundError as error:
        raise SourceMissingError(
            f"missing PHOIBLE receipt input: {error.filename}"
        ) from error
    except (EOFError, KeyError, OSError, TypeError, ValueError, zlib.error) as error:
        raise SourceContentError(f"invalid PHOIBLE source receipt: {error}") from error


def read_source(name: str) -> bytes:
    """Read one original source component, verifying its decompressed identity."""
    if name not in source_files():
        raise ValueError(f"unknown shipped PHOIBLE source component: {name!r}")
    root = _data_root()
    resource = root.joinpath(name + ".gz")
    try:
        manifest = source_receipt(root)
        verify_manifest(root)
        packed = resource.read_bytes()
        if (
            hashlib.sha256(packed).hexdigest()
            != manifest["artifacts"][name + ".gz"]["sha256"]
        ):
            raise SourceContentError(f"shipped PHOIBLE transport hash mismatch: {name}")
        content = gzip.decompress(packed)
    except (SourceContentError, SourceMissingError):
        raise
    except FileNotFoundError as error:
        raise SourceMissingError(
            f"shipped PHOIBLE resource is missing: {name}"
        ) from error
    except (OSError, EOFError, zlib.error) as error:
        raise SourceContentError(
            f"shipped PHOIBLE resource is corrupt: {name}"
        ) from error
    except (KeyError, TypeError, ValueError) as error:
        raise SourceContentError("shipped PHOIBLE manifest is invalid") from error
    expected = source_policy()["inputs"][name]
    if hashlib.sha256(content).hexdigest() != expected:
        raise SourceContentError(f"shipped PHOIBLE source hash mismatch: {name}")
    return content
