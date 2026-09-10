"""Structured source identity shared by inventory declarations."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from xml.etree.ElementTree import Element

SOURCE_ATTRIBUTES = (
    "upstream",
    "upstream-url",
    "artifact",
    "version",
    "license",
    "kind",
)
"""The source fields every card-bearing declaration states."""


@dataclass(frozen=True)
class SourceMetadata:
    """Machine-readable source identity from one declaration root."""

    upstream: str
    upstream_url: str
    artifact: str
    version: str
    license: str
    kind: str

    @classmethod
    def from_root(
        cls, root: Element, declaration: str | PathLike[str]
    ) -> SourceMetadata:
        """Read required source attributes and refuse a stored prose duplicate."""
        where = str(declaration)
        if "provenance" in root.attrib:
            raise ValueError(
                f"{where} stores `provenance`; derive it from the source attributes"
            )
        missing = [name for name in SOURCE_ATTRIBUTES if not root.get(name, "").strip()]
        if missing:
            names = ", ".join(f"`{name}`" for name in missing)
            raise ValueError(f"{where} has no declared {names}")
        return cls(
            root.attrib["upstream"],
            root.attrib["upstream-url"],
            root.attrib["artifact"],
            root.attrib["version"],
            root.attrib["license"],
            root.attrib["kind"],
        )

    @property
    def provenance(self) -> str:
        """Render the one human sentence; no declaration stores a second copy."""
        pin = (
            "explicitly unpinned"
            if self.version == "unpinned"
            else f"pinned at {self.version}"
        )
        return f"{self.upstream} {self.artifact}, {pin} ({self.license})"

    def to_dict(self) -> dict[str, str]:
        """Return the declared fields as JSON-serializable metadata."""
        return {
            "upstream": self.upstream,
            "upstream-url": self.upstream_url,
            "artifact": self.artifact,
            "version": self.version,
            "license": self.license,
            "kind": self.kind,
        }
