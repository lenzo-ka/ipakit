"""Tract space: where a phone sits in the vocal tract, and how to draw it.

Phones live in a normalized, head-independent space of two coordinates,
declared in ``data/ipa.xml``:

``arc``
    Proportional position along the tract midline, 0 at the lips to 1 at
    the glottis. Consonants take it from their place, vowels from their
    backness (the tongue-body constriction sweeps the palatal..uvular
    span).
``offset``
    Constriction degree, 0 at the open midline to 1 at full closure
    against the wall. Consonants take it from their manner, vowels from
    their height -- one continuum, so an open vowel, a close vowel, an
    approximant and a stop are ordered by how far the articulator has
    travelled.

Distance uses these coordinates directly. A :class:`Head` projects them
to 2D for rendering only: phone identity does not depend on whose head
you imagine, and the shipped matrix must stay reproducible.
"""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import PHONEMAPS_DIR

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures

HEADS_FILE = PHONEMAPS_DIR.parent / "heads.xml"


@dataclass(frozen=True)
class TractPoint:
    """A phone's position in normalized tract space."""

    arc: float | None  # 0 lips .. 1 glottis, None if unplaced
    offset: float | None  # 0 open midline .. 1 full closure, None if unplaced

    @property
    def placed(self) -> bool:
        return self.arc is not None and self.offset is not None


@dataclass(frozen=True)
class MidlinePoint:
    arc: float
    x: float
    y: float
    diameter: float


@dataclass(frozen=True)
class Head:
    """A mid-sagittal geometry that projects tract space to 2D."""

    name: str
    midline: tuple[MidlinePoint, ...]
    desc: str | None = None
    length_cm: float | None = None

    def project(self, point: TractPoint) -> tuple[float, float] | None:
        """(x, y) for a tract point in this head, or None if unplaced.

        The midline is interpolated at the point's arc; the offset then
        carries the position from the midline toward the wall, scaled by
        the local tract diameter. Offset lifts toward the palate over the
        oral run and toward the pharyngeal wall behind it, following the
        midline's own direction.
        """
        if not point.placed:
            return None
        arc = min(max(point.arc or 0.0, 0.0), 1.0)
        before = self.midline[0]
        after = self.midline[-1]
        for i in range(len(self.midline) - 1):
            if self.midline[i].arc <= arc <= self.midline[i + 1].arc:
                before, after = self.midline[i], self.midline[i + 1]
                break
        span = after.arc - before.arc
        t = (arc - before.arc) / span if span else 0.0
        x = before.x + (after.x - before.x) * t
        y = before.y + (after.y - before.y) * t
        diameter = before.diameter + (after.diameter - before.diameter) * t
        # Normal to the midline, pointing toward the constricting wall.
        dx, dy = after.x - before.x, after.y - before.y
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / norm, dx / norm
        travel = (point.offset or 0.0) * diameter
        return (x + nx * travel, y + ny * travel)


@functools.lru_cache(maxsize=1)
def _load_heads() -> tuple[dict[str, Head], str]:
    heads: dict[str, Head] = {}
    default = ""
    path = Path(HEADS_FILE)
    if not path.exists():  # pragma: no cover - data ships with the package
        return heads, default
    root = ET.parse(path).getroot()
    default = root.get("default", "")
    for elem in root.findall("head"):
        name = elem.get("name")
        if not name:
            continue
        points = []
        midline = elem.find("midline")
        if midline is not None:
            for pt in midline.findall("point"):
                points.append(
                    MidlinePoint(
                        arc=float(pt.get("arc", 0.0)),
                        x=float(pt.get("x", 0.0)),
                        y=float(pt.get("y", 0.0)),
                        diameter=float(pt.get("diameter", 0.0)),
                    )
                )
        length = elem.get("length-cm")
        heads[name] = Head(
            name=name,
            midline=tuple(sorted(points, key=lambda p: p.arc)),
            desc=elem.get("desc"),
            length_cm=float(length) if length else None,
        )
    return heads, default


def heads() -> dict[str, Head]:
    """The shipped head shapes, by name."""
    return dict(_load_heads()[0])


def head(name: str | None = None) -> Head:
    """A head shape by name, or the shipped default."""
    loaded, default = _load_heads()
    key = name or default
    if key not in loaded:
        raise KeyError(f"unknown head shape: {key!r}")
    return loaded[key]


def tract_point(features: IPAFeatures, bundle: dict[str, str]) -> TractPoint:
    """Where a feature bundle sits in tract space.

    Consonants read arc from place and offset from manner; vowels read
    arc from backness and offset from height. Unplaceable bundles (no
    manner, an off-scale manner like silence) yield an unplaced point.
    """
    manner = bundle.get("manner")
    arc: float | None = None
    offset: float | None = None

    def value_attr(feature: str, value: str | None, attr: str) -> float | None:
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        raw = feat.coordinates.get(feat.value_aliases.get(value, value), {}).get(attr)
        return raw

    if manner == "vowel":
        arc = value_attr("backness", bundle.get("backness"), "arc")
        offset = value_attr("height", bundle.get("height"), "offset")
    else:
        place = bundle.get("place")
        if place is not None:
            feat = features.features.get("place")
            if feat is not None:
                # A combining place (bilabial+velar) sits at the mean of
                # its components' positions -- the fusion's centre of
                # gravity in the tract.
                arcs = [
                    a
                    for comp in feat.expand(place)
                    if (a := value_attr("place", comp, "arc")) is not None
                ]
                if arcs:
                    arc = sum(arcs) / len(arcs)
        offset = value_attr("manner", manner, "offset")
    return TractPoint(arc=arc, offset=offset)
