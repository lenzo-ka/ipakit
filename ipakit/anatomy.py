"""Shared anatomical anchors used by inventory and head geometry."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .constants import PHONEMAPS_DIR

ANATOMY_FILE = PHONEMAPS_DIR.parent / "heads.xml"


def landmark_arc(name: str, head: str | None = None) -> float:
    """Return a landmark's default arc, or a declared per-head override."""
    elem = (
        ET.parse(Path(ANATOMY_FILE))
        .getroot()
        .find(f"landmarks/landmark[@name='{name}']")
    )
    if elem is None:
        raise ValueError(f"unknown anatomical landmark: {name!r}")
    if head is not None:
        override = elem.find(f"head[@name='{head}']")
        if override is not None and override.get("arc") is not None:
            return float(override.get("arc", "0"))
    raw = elem.get("arc")
    if raw is None:
        raise ValueError(f"anatomical landmark {name!r} has no default arc")
    return float(raw)
