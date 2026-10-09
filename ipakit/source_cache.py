"""Offline cache geometry and atomic publication for external sources.

This module is deliberately provider-neutral.  Provider policy supplies the
revision, format, artifacts, and receipt; the cache layer only gives them a
stable location and refuses to expose an incomplete build.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ._source_receipt import loads_receipt

CACHE_ENV = "IPAKIT_SOURCE_CACHE"

SourceState = Literal[
    "missing",
    "source-only",
    "ready",
    "stale-pin",
    "stale-format",
    "invalid",
]
Selection = Literal["argument", "environment", "cache"]


def cache_root(cache_dir: str | Path | None = None) -> Path:
    """Return the selected cache root without touching the filesystem."""
    if cache_dir is not None:
        return Path(cache_dir).expanduser()
    if configured := os.environ.get(CACHE_ENV):
        return Path(configured).expanduser()
    if xdg := os.environ.get("XDG_CACHE_HOME"):
        return Path(xdg).expanduser() / "ipakit"
    return Path.home() / ".cache" / "ipakit"


def _component(value: str, label: str) -> str:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or len(path.parts) != 1
        or value in {".", ".."}
        or "\\" in value
    ):
        raise ValueError(f"{label} must be one nonempty path component")
    return value


def source_dir(
    provider: str,
    revision: str,
    cache_dir: str | Path | None = None,
) -> Path:
    """Return the managed source-checkout directory for one revision."""
    return (
        cache_root(cache_dir)
        / "sources"
        / _component(provider, "provider")
        / _component(revision, "revision")
    )


def tables_dir(
    provider: str,
    revision: str,
    format: int,
    cache_dir: str | Path | None = None,
) -> Path:
    """Return the complete table-build directory for one format."""
    if type(format) is not int or format < 1:
        raise ValueError("format must be a positive integer")
    return (
        cache_root(cache_dir)
        / "tables"
        / _component(provider, "provider")
        / _component(revision, "revision")
        / f"format-{format}"
    )


def receipt_path(
    provider: str,
    revision: str,
    format: int,
    cache_dir: str | Path | None = None,
) -> Path:
    """Return the receipt file for one complete table build."""
    return tables_dir(provider, revision, format, cache_dir) / "receipt.json"


@dataclass(frozen=True)
class SourceStatus:
    """One provider's source and managed-build state."""

    provider: Literal["espeak", "phoible"]
    state: SourceState
    selected_by: Selection | None
    expected_tag: str | None
    expected_revision: str
    observed_revision: str | None
    expected_format: int
    observed_format: int | None
    built_at: str | None
    detail: str | None

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-ready representation."""
        return {
            "provider": self.provider,
            "state": self.state,
            "selected_by": self.selected_by,
            "expected_tag": self.expected_tag,
            "expected_revision": self.expected_revision,
            "observed_revision": self.observed_revision,
            "expected_format": self.expected_format,
            "observed_format": self.observed_format,
            "built_at": self.built_at,
            "detail": self.detail,
        }


def read_receipt(path: str | Path) -> dict[str, Any]:
    """Read one receipt file through the shared strict validator."""
    return loads_receipt(Path(path).read_bytes())


def _relative_artifact(path: str | Path) -> tuple[Path, str]:
    text = str(path)
    relative = Path(text)
    if (
        not text
        or relative.is_absolute()
        or relative == Path(".")
        or ".." in relative.parts
        or "\\" in text
    ):
        raise ValueError(f"artifact path must be relative and contained: {text}")
    return relative, relative.as_posix()


def _artifact_map(artifacts: Mapping[str | Path, bytes]) -> dict[str, bytes]:
    normalized: dict[str, bytes] = {}
    for path, content in artifacts.items():
        _, name = _relative_artifact(path)
        if name == "receipt.json":
            raise ValueError("receipt.json is reserved for the build receipt")
        if name in normalized:
            raise ValueError(f"duplicate artifact path: {name}")
        if not isinstance(content, bytes):
            raise TypeError(f"artifact content must be bytes: {name}")
        normalized[name] = content
    return normalized


def _receipt_bytes(receipt: Mapping[str, Any]) -> tuple[bytes, dict[str, Any]]:
    content = (json.dumps(dict(receipt), indent=2, sort_keys=True) + "\n").encode()
    return content, loads_receipt(content)


def _verify_artifacts(
    artifacts: Mapping[str, bytes], receipt: Mapping[str, Any]
) -> None:
    recorded = receipt["artifacts"]
    if not isinstance(recorded, Mapping) or set(recorded) != set(artifacts):
        raise ValueError("receipt artifacts do not match the published artifacts")
    for name, content in artifacts.items():
        expected = recorded[name]["sha256"]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"artifact {name} does not match its receipt")


def _verify_staged(directory: Path, receipt: Mapping[str, Any]) -> None:
    for name, record in receipt["artifacts"].items():
        relative, _ = _relative_artifact(name)
        path = directory / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"published artifact is not a regular file: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"published artifact {name} does not match its receipt")


def _symlink_on_path(path: Path) -> Path | None:
    absolute = path.absolute()
    for candidate in reversed((absolute, *absolute.parents)):
        if candidate.is_symlink():
            return candidate
    return None


def publish_build(
    directory: str | Path,
    artifacts: Mapping[str | Path, bytes],
    receipt: Mapping[str, Any],
) -> Path:
    """Validate and atomically publish a new, complete table build.

    The destination must not exist.  Failed validation or publication removes
    only the private staging directory; it never alters an existing build.
    """
    target = Path(directory).absolute()
    if target == target.parent:
        raise ValueError("build destination must not be a filesystem root")
    if linked := _symlink_on_path(target):
        raise ValueError(f"refusing publication through a symbolic link: {linked}")
    if target.exists():
        raise FileExistsError(f"build destination already exists: {target}")

    normalized = _artifact_map(artifacts)
    receipt_content, validated = _receipt_bytes(receipt)
    _verify_artifacts(normalized, validated)

    target.parent.mkdir(parents=True, exist_ok=True)
    if linked := _symlink_on_path(target):
        raise ValueError(f"refusing publication through a symbolic link: {linked}")

    staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=target.parent))
    try:
        for name, content in normalized.items():
            relative, _ = _relative_artifact(name)
            artifact = staging / relative
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(content)
        (staging / "receipt.json").write_bytes(receipt_content)

        staged_receipt = read_receipt(staging / "receipt.json")
        _verify_staged(staging, staged_receipt)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"build destination already exists: {target}")
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target
