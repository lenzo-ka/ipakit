"""Reusable, offline source validation and artifact building.

Acquisition and release administration belong to developer scripts. Importing
this package never imports optional providers or contacts an upstream service.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .._provenance import SourceMetadata


class SourceError(ValueError):
    """Catchable failure at an external-source boundary."""

    code = "invalid-source"


class SourceMissingError(SourceError):
    """A required external dataset is unavailable."""

    code = "missing-data"


class SourceVersionError(SourceError):
    """The supplied source is not the accepted revision."""

    code = "version-mismatch"


class SourceContentError(SourceError):
    """Consumed bytes differ from the accepted content pin."""

    code = "content-mismatch"


@dataclass(frozen=True)
class SourceIdentity:
    """Declared attribution together with the exact consumed-input hashes."""

    metadata: SourceMetadata
    digests: Mapping[str, str]


@dataclass(frozen=True)
class BuildResult:
    """Relative artifact bytes and the producer's explicitly owned file globs."""

    artifacts: Mapping[Path, bytes]
    owned_globs: tuple[Path, ...] = ()
    source: SourceIdentity | None = None

    def __post_init__(self) -> None:
        for path in (*self.artifacts, *self.owned_globs):
            if path.is_absolute() or ".." in path.parts or path == Path("."):
                raise ValueError(
                    f"artifact path must be relative and contained: {path}"
                )

    def stale(self, root: Path) -> list[Path]:
        """Find missing, changed and unclaimed producer-owned artifacts."""
        changed = {
            path
            for path, content in self.artifacts.items()
            if not (root / path).is_file() or (root / path).read_bytes() != content
        }
        for pattern in self.owned_globs:
            changed.update(
                path.relative_to(root)
                for path in root.glob(str(pattern))
                if path.relative_to(root) not in self.artifacts
            )
        return sorted(changed)
