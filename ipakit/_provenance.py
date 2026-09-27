"""Structured source identity shared by inventory declarations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from xml.etree.ElementTree import Element

from ._source_receipt import loads_receipt

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
        """Read source fields or the declaration's sole receipt pointer.

        Existing declaration families keep their inline source attributes.  A
        generated declaration may instead point at one adjacent source receipt;
        mixing the two would restore the duplicate authority the pointer removes.
        """
        where = str(declaration)
        if "provenance" in root.attrib:
            raise ValueError(
                f"{where} stores `provenance`; derive it from the source attributes"
            )
        if receipt_name := root.get("source-receipt"):
            duplicated = [name for name in SOURCE_ATTRIBUTES if name in root.attrib]
            if duplicated:
                raise ValueError(
                    f"{where} mixes source-receipt with source attributes: "
                    f"{', '.join(duplicated)}"
                )
            relative = Path(receipt_name)
            if relative.name != receipt_name or relative.is_absolute():
                raise ValueError(f"{where} has an invalid source-receipt pointer")
            declaration_path = Path(declaration)
            receipt_path = declaration_path.parent / relative
            try:
                receipt = loads_receipt(receipt_path.read_bytes())
                artifact = receipt["artifacts"][declaration_path.name]
                digest = hashlib.sha256(declaration_path.read_bytes()).hexdigest()
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"{where} has an invalid source receipt: {error}"
                ) from error
            if artifact["sha256"] != digest:
                raise ValueError(f"{where} has a stale source receipt field: artifacts")
            source = receipt["source-policy"]["source"]
            return cls(
                source["upstream"],
                source["upstream-url"],
                source["artifact"],
                source["version"],
                source["license"],
                source["kind"],
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
