"""The shared receipt accepts strict optional build provenance."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from ipakit._identity import identity_fingerprint
from ipakit._source_receipt import loads_receipt

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "1" * 40
SHA256 = "2" * 64


def _receipt() -> dict[str, Any]:
    return {
        "schema": {"id": "ipakit-source-receipt", "version": 1},
        "kind": "user-build",
        "domain": "test-source",
        "source-policy": {
            "version": 1,
            "source": {
                "upstream": "Test source",
                "upstream-url": "https://example.invalid/test-source.git",
                "artifact": "Test source data",
                "version": "test-source@1",
                "license": "LicenseRef-Test",
                "kind": "test-data",
            },
            "revision": {"tag": "1.0", "commit": COMMIT},
            "inputs": {"source.txt": SHA256},
        },
        "extractor": {"id": "ipakit.test.build", "version": "1"},
        "artifacts": {"output.txt": {"sha256": SHA256}},
        "license": {"id": "LicenseRef-Test", "notices": {"LICENSE": SHA256}},
        "build": {
            "tool": "ipakit",
            "tool-version": "0.5.0",
            "format": 1,
            "built-at": "2026-10-08T14:32:05Z",
        },
    }


def _content(receipt: dict[str, Any]) -> str:
    receipt = copy.deepcopy(receipt)
    receipt["fingerprint"] = identity_fingerprint(receipt)
    return json.dumps(receipt, sort_keys=True, indent=2) + "\n"


def _set_build(receipt: dict[str, Any], value: object) -> None:
    receipt["build"] = value


def _set_revision(receipt: dict[str, Any], value: object) -> None:
    receipt["source-policy"]["revision"] = value


@pytest.mark.parametrize(
    "revision",
    [
        {"commit": COMMIT},
        {"commit": COMMIT, "tag": "1.0"},
        {"sha256": SHA256},
        {"sha256": SHA256, "tag": "archive-1.0"},
    ],
)
def test_receipt_accepts_revision_forms(revision: dict[str, object]) -> None:
    receipt = _receipt()
    _set_revision(receipt, revision)
    assert loads_receipt(_content(receipt))["source-policy"]["revision"] == revision


def test_receipt_accepts_fractional_build_time() -> None:
    receipt = _receipt()
    receipt["build"]["built-at"] = "2026-10-08T14:32:05.123456Z"
    assert loads_receipt(_content(receipt))["build"] == receipt["build"]


@pytest.mark.parametrize(
    ("mutate", "value", "message"),
    [
        (_set_build, None, "build must contain exactly"),
        (
            _set_build,
            {"tool": "ipakit", "tool-version": "0.5.0", "format": 1},
            "build must contain exactly",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "0.5.0",
                "format": 1,
                "built-at": "2026-10-08T14:32:05Z",
                "extra": True,
            },
            "build must contain exactly",
        ),
        (
            _set_build,
            {
                "tool": "",
                "tool-version": "0.5.0",
                "format": 1,
                "built-at": "2026-10-08T14:32:05Z",
            },
            "build tool must be a nonempty string",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "",
                "format": 1,
                "built-at": "2026-10-08T14:32:05Z",
            },
            "build tool version must be a nonempty string",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "0.5.0",
                "format": True,
                "built-at": "2026-10-08T14:32:05Z",
            },
            "build format must be a positive integer",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "0.5.0",
                "format": 0,
                "built-at": "2026-10-08T14:32:05Z",
            },
            "build format must be a positive integer",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "0.5.0",
                "format": 1,
                "built-at": "2026-02-30T14:32:05Z",
            },
            "build time must be an RFC 3339 UTC string ending in Z",
        ),
        (
            _set_build,
            {
                "tool": "ipakit",
                "tool-version": "0.5.0",
                "format": 1,
                "built-at": "2026-10-08T14:32:05+00:00",
            },
            "build time must be an RFC 3339 UTC string ending in Z",
        ),
        (_set_revision, None, "source-policy revision must be an object"),
        (
            _set_revision,
            {},
            "source-policy revision must contain exactly one of commit or sha256",
        ),
        (
            _set_revision,
            {"commit": COMMIT, "sha256": SHA256},
            "source-policy revision must contain exactly one of commit or sha256",
        ),
        (
            _set_revision,
            {"commit": COMMIT, "extra": True},
            "source-policy revision must contain exactly one of commit or sha256",
        ),
        (
            _set_revision,
            {"commit": "1" * 39},
            "source-policy revision commit must be 40 hexadecimal digits",
        ),
        (
            _set_revision,
            {"sha256": "2" * 63},
            "source-policy revision sha256 must be 64 hexadecimal digits",
        ),
        (
            _set_revision,
            {"commit": COMMIT, "tag": ""},
            "source-policy revision tag must be a nonempty string",
        ),
    ],
)
def test_receipt_optional_fields_validate_strictly(
    mutate: Callable[[dict[str, Any], object], None],
    value: object,
    message: str,
) -> None:
    receipt = _receipt()
    mutate(receipt, value)
    with pytest.raises(ValueError, match=message):
        loads_receipt(_content(receipt))


@pytest.mark.parametrize(
    "path",
    [
        "ipakit/data/clts/manifest.json",
        "ipakit/data/feature-models/panphon-receipt.json",
        "ipakit/data/phoible/manifest.json",
    ],
)
def test_existing_receipts_still_validate(path: str) -> None:
    loads_receipt(ROOT.joinpath(path).read_bytes())


@pytest.mark.parametrize(
    ("field", "duplicate"),
    [
        ("build", '"tool": "duplicate",'),
        ("revision", f'"commit": "{COMMIT}",'),
    ],
)
def test_optional_fields_refuse_duplicate_keys(field: str, duplicate: str) -> None:
    content = _content(_receipt())
    content = content.replace(f'"{field}": {{', f'"{field}": {{{duplicate}', 1)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        loads_receipt(content)
