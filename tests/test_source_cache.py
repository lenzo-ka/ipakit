"""The managed source cache publishes only complete, validated builds."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from ipakit._identity import identity_fingerprint
from ipakit.source_cache import (
    CACHE_ENV,
    SourceStatus,
    cache_root,
    publish_build,
    read_receipt,
    receipt_path,
    source_dir,
    tables_dir,
)


def _receipt(artifacts: dict[str, bytes]) -> dict[str, Any]:
    digest = "2" * 64
    receipt: dict[str, Any] = {
        "schema": {"id": "ipakit-source-receipt", "version": 1},
        "kind": "user-build",
        "domain": "test-source",
        "source-policy": {
            "version": 1,
            "source": {
                "upstream": "Test source",
                "upstream-url": "https://example.invalid/source.git",
                "artifact": "Test source data",
                "version": "test-source@1",
                "license": "LicenseRef-Test",
                "kind": "test-data",
            },
            "revision": {"commit": "1" * 40},
            "inputs": {"input.txt": digest},
        },
        "extractor": {"id": "ipakit.test.build", "version": "1"},
        "artifacts": {
            name: {"sha256": hashlib.sha256(content).hexdigest()}
            for name, content in artifacts.items()
        },
        "license": {"id": "LicenseRef-Test", "notices": {"LICENSE": digest}},
        "build": {
            "tool": "ipakit",
            "tool-version": "0.5.0",
            "format": 1,
            "built-at": "2026-10-08T14:32:05Z",
        },
    }
    receipt["fingerprint"] = identity_fingerprint(receipt)
    return receipt


def test_cache_root_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    configured = tmp_path / "configured"
    xdg = tmp_path / "xdg"
    home = tmp_path / "home"
    monkeypatch.setenv(CACHE_ENV, str(configured))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))
    monkeypatch.setenv("HOME", str(home))
    assert cache_root(explicit) == explicit
    assert cache_root() == configured
    monkeypatch.delenv(CACHE_ENV)
    assert cache_root() == xdg / "ipakit"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert cache_root() == home / ".cache" / "ipakit"


def test_cache_layout_is_revision_and_format_scoped(tmp_path: Path) -> None:
    revision = "1" * 40
    assert source_dir("espeak", revision, tmp_path) == (
        tmp_path / "sources" / "espeak" / revision
    )
    assert tables_dir("espeak", revision, 2, tmp_path) == (
        tmp_path / "tables" / "espeak" / revision / "format-2"
    )
    assert receipt_path("espeak", revision, 2, tmp_path) == (
        tmp_path / "tables" / "espeak" / revision / "format-2" / "receipt.json"
    )


@pytest.mark.parametrize("value", ["", ".", "..", "a/b", r"a\b", "/absolute"])
def test_cache_layout_refuses_non_components(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError, match="path component"):
        source_dir(value, "revision", tmp_path)
    with pytest.raises(ValueError, match="path component"):
        tables_dir("provider", value, 1, tmp_path)


@pytest.mark.parametrize("format", [0, -1, True, 1.0, "1"])
def test_cache_layout_refuses_invalid_formats(tmp_path: Path, format: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        tables_dir("provider", "revision", format, tmp_path)


def test_source_status_has_stable_json_shape() -> None:
    status = SourceStatus(
        provider="espeak",
        state="ready",
        selected_by="cache",
        expected_tag="1.52.0",
        expected_revision="1" * 40,
        observed_revision="1" * 40,
        expected_format=1,
        observed_format=1,
        built_at="2026-10-08T14:32:05Z",
        detail=None,
    )
    assert status.to_dict() == {
        "provider": "espeak",
        "state": "ready",
        "selected_by": "cache",
        "expected_tag": "1.52.0",
        "expected_revision": "1" * 40,
        "observed_revision": "1" * 40,
        "expected_format": 1,
        "observed_format": 1,
        "built_at": "2026-10-08T14:32:05Z",
        "detail": None,
    }


def test_build_publishes_atomically(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n", "nested/af.xml": b"afrikaans\n"}
    target = tmp_path / "tables/espeak/revision/format-1"
    assert publish_build(target, artifacts, _receipt(artifacts)) == target
    assert (target / "en.xml").read_bytes() == b"english\n"
    assert (target / "nested/af.xml").read_bytes() == b"afrikaans\n"
    assert read_receipt(target / "receipt.json") == _receipt(artifacts)
    assert not list(target.parent.glob(".tmp-*"))


def test_build_accepts_a_read_only_receipt_mapping(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n"}
    receipt = MappingProxyType(_receipt(artifacts))
    target = tmp_path / "format-1"
    publish_build(target, artifacts, receipt)
    assert read_receipt(target / "receipt.json") == receipt


@pytest.mark.parametrize("path", ["", ".", "..", "a/../b", r"a\b", "/absolute"])
def test_build_refuses_unsafe_artifact_paths(tmp_path: Path, path: str) -> None:
    artifacts = {"en.xml": b"english\n"}
    with pytest.raises(ValueError, match="relative and contained"):
        publish_build(tmp_path / "format-1", {path: b"content"}, _receipt(artifacts))
    assert not (tmp_path / "format-1").exists()


def test_build_refuses_reserved_and_duplicate_artifact_paths(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n"}
    target = tmp_path / "format-1"
    with pytest.raises(ValueError, match="reserved"):
        publish_build(target, {"receipt.json": b"content"}, _receipt(artifacts))
    with pytest.raises(ValueError, match="duplicate artifact path"):
        publish_build(
            target,
            {"nested/en.xml": b"one", Path("nested/en.xml"): b"two"},
            _receipt(artifacts),
        )
    assert not target.exists()


def test_build_refuses_nonbyte_artifacts(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n"}
    invalid_artifacts: Any = {"en.xml": "english\n"}
    target = tmp_path / "format-1"
    with pytest.raises(TypeError, match="content must be bytes"):
        publish_build(target, invalid_artifacts, _receipt(artifacts))
    assert not target.exists()


def test_invalid_build_never_becomes_visible(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n"}
    receipt = _receipt(artifacts)
    receipt["artifacts"]["en.xml"]["sha256"] = "0" * 64
    receipt["fingerprint"] = identity_fingerprint(
        {key: value for key, value in receipt.items() if key != "fingerprint"}
    )
    target = tmp_path / "tables/espeak/revision/format-1"
    with pytest.raises(ValueError, match="does not match its receipt"):
        publish_build(target, artifacts, receipt)
    assert not target.exists()
    assert not target.parent.exists()


def test_fault_mid_build_cleans_staging_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifacts = {"en.xml": b"english\n", "nested/af.xml": b"afrikaans\n"}
    target = tmp_path / "format-1"
    write_bytes = Path.write_bytes

    def fail_on_second_artifact(path: Path, content: bytes) -> int:
        if path.name == "af.xml":
            raise OSError("injected write failure")
        return write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail_on_second_artifact)
    with pytest.raises(OSError, match="injected write failure"):
        publish_build(target, artifacts, _receipt(artifacts))
    assert not target.exists()
    assert not list(tmp_path.glob(".tmp-*"))


def test_publish_never_replaces_an_existing_build(tmp_path: Path) -> None:
    artifacts = {"en.xml": b"english\n"}
    target = tmp_path / "format-1"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("original")
    with pytest.raises(FileExistsError, match="already exists"):
        publish_build(target, artifacts, _receipt(artifacts))
    assert marker.read_text() == "original"


def test_publish_refuses_symbolic_links(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    target = linked / "format-1"
    artifacts = {"en.xml": b"english\n"}
    with pytest.raises(ValueError, match="symbolic link"):
        publish_build(target, artifacts, _receipt(artifacts))
    assert not target.exists()


def test_read_receipt_rejects_malformed_content(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    receipt = _receipt({"en.xml": b"english\n"})
    changed = copy.deepcopy(receipt)
    changed["domain"] = "changed-without-refingerprinting"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        read_receipt(path)
