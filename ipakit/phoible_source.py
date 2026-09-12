"""Discover the shipped PHOIBLE source bytes, without importing a provider.

The aggregate retains all foreign columns and inventories. Decoding those bytes
as a house inventory is the separate, explicitly lossy bridge operation.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import zlib
from importlib.resources import files
from typing import Any

from ._provenance import SourceMetadata
from .extraction import SourceContentError, SourceMissingError


def source_policy() -> dict[str, Any]:
    """Return a fresh copy of the accepted source pin and consumed hashes."""
    policy: dict[str, Any] = json.loads(
        files("ipakit").joinpath("data/phoible-policy.json").read_text(encoding="utf-8")
    )
    return policy


def source_files() -> tuple[str, ...]:
    """List original upstream data paths available as exact decompressed bytes."""
    return tuple(
        name for name in source_policy()["inputs"] if name.endswith((".csv", ".bib"))
    )


def source_metadata() -> SourceMetadata:
    """Describe the accepted snapshot, not the identity of an external checkout."""
    revision = source_policy()["revision"]
    return SourceMetadata(
        "PHOIBLE (Moran, McCloy and contributors)",
        f"https://github.com/phoible/dev/tree/{revision}",
        "separately licensed source-data aggregate",
        revision,
        "LicenseRef-PHOIBLE-Source-Aggregate",
        "inventory-catalog-source",
    )


def read_source(name: str) -> bytes:
    """Read one original source component, verifying its decompressed identity."""
    if name not in source_files():
        raise ValueError(f"unknown shipped PHOIBLE source component: {name!r}")
    root = files("ipakit").joinpath("data/phoible")
    resource = root.joinpath(name + ".gz")
    try:
        manifest = json.loads(root.joinpath("manifest.json").read_text())
        if (
            manifest["source-sha256"] != source_policy()["inputs"]
            or manifest["source"] != source_metadata().to_dict()
        ):
            raise SourceContentError(
                "shipped PHOIBLE manifest disagrees with source policy"
            )
        packed = resource.read_bytes()
        if (
            hashlib.sha256(packed).hexdigest()
            != manifest["transport-sha256"][name + ".gz"]
        ):
            raise SourceContentError(f"shipped PHOIBLE transport hash mismatch: {name}")
        content = gzip.decompress(packed)
    except FileNotFoundError as error:
        raise SourceMissingError(
            f"shipped PHOIBLE resource is missing: {name}"
        ) from error
    except (OSError, EOFError, zlib.error) as error:
        raise SourceContentError(
            f"shipped PHOIBLE resource is corrupt: {name}"
        ) from error
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise SourceContentError("shipped PHOIBLE manifest is invalid") from error
    expected = source_policy()["inputs"][name]
    if hashlib.sha256(content).hexdigest() != expected:
        raise SourceContentError(f"shipped PHOIBLE source hash mismatch: {name}")
    return content
