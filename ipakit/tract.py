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
from .models import Feature

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures

HEADS_FILE = PHONEMAPS_DIR.parent / "heads.xml"


@dataclass(frozen=True)
class TractPoint:
    """Where a constriction is, and what makes it.

    ``arc`` and ``offset`` locate the constriction; ``articulator`` names
    the organ that travels there. Place names the target, not the mover:
    the two coincide by convention for most sounds, but not for
    linguolabials (tongue to the upper lip) or apical/laminal contrasts.
    A renderer needs the articulator to animate at all.
    """

    arc: float | None  # 0 lips .. 1 glottis, None if unplaced
    offset: float | None  # 0 open midline .. 1 full closure, None if unplaced
    articulator: str | None = None  # the organ that moves, None if unknown

    @property
    def placed(self) -> bool:
        return self.arc is not None and self.offset is not None


@dataclass(frozen=True)
class RestPosture:
    """Where the articulators sit when not speaking.

    Rendering geometry, not features: silence is featurally null, but it
    still has to be drawn somewhere, and an utterance starts and ends
    here -- which is the home position for animated trajectories.
    """

    arc: float
    offset: float
    lips: str = "closed"
    jaw: str = "closed"
    velum: str = "lowered"

    @property
    def point(self) -> TractPoint:
        return TractPoint(arc=self.arc, offset=self.offset)


@dataclass(frozen=True)
class MidlinePoint:
    arc: float
    x: float
    y: float
    diameter: float
    provenance: str = "hand-placed"


@dataclass(frozen=True)
class Head:
    """A mid-sagittal geometry that projects tract space to 2D."""

    name: str
    midline: tuple[MidlinePoint, ...]
    rest: RestPosture | None = None
    desc: str | None = None
    length_cm: float | None = None

    def _tangents(self) -> list[tuple[float, float]]:
        """Unit tangent at each midline vertex, averaged across the joint.

        Taking the normal from the containing segment makes it jump at every
        joint -- by 33 degrees at the oropharyngeal bend in the adult male
        head -- which draws as a corner on both walls and, on the inside of
        the bend, as a wall that crosses itself: three self-intersections
        before this averaged the joints. A vertex tangent is the mean of the
        directions either side of it, and ``project`` interpolates between
        two vertex tangents rather than reusing one segment's, so the normal
        turns continuously along the whole midline.

        This is rendering geometry. ``ipakit.metric`` reads ``tract_point``,
        never ``project``, so nothing here can reach a distance.
        """
        pts = self.midline
        segments: list[tuple[float, float]] = []
        for i in range(len(pts) - 1):
            dx, dy = pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y
            norm = (dx * dx + dy * dy) ** 0.5 or 1.0
            segments.append((dx / norm, dy / norm))
        if not segments:
            return [(1.0, 0.0)]
        out: list[tuple[float, float]] = []
        for i in range(len(pts)):
            if i == 0:
                tx, ty = segments[0]
            elif i == len(pts) - 1:
                tx, ty = segments[-1]
            else:
                ax, ay = segments[i - 1]
                bx, by = segments[i]
                tx, ty = ax + bx, ay + by
            norm = (tx * tx + ty * ty) ** 0.5 or 1.0
            out.append((tx / norm, ty / norm))
        return out

    def project(
        self, point: TractPoint, at_rest: bool = False
    ) -> tuple[float, float] | None:
        """(x, y) for a tract point in this head.

        Returns None for an unplaced point (silence has no articulatory
        position) unless ``at_rest``, which draws it at the head's rest
        posture -- what a renderer wants for silence and for the start
        and end of an utterance.

        The midline is interpolated at the point's arc; the offset then
        carries the position from the midline toward the wall, scaled by
        the local tract diameter. Offset lifts toward the palate over the
        oral run and toward the pharyngeal wall behind it, following the
        midline's own direction.
        """
        if not point.placed:
            if not (at_rest and self.rest is not None):
                return None
            point = self.rest.point
        arc = min(max(point.arc or 0.0, 0.0), 1.0)
        before = self.midline[0]
        after = self.midline[-1]
        index = 0
        for i in range(len(self.midline) - 1):
            if self.midline[i].arc <= arc <= self.midline[i + 1].arc:
                before, after, index = self.midline[i], self.midline[i + 1], i
                break
        else:
            index = len(self.midline) - 2
        span = after.arc - before.arc
        t = (arc - before.arc) / span if span else 0.0
        x = before.x + (after.x - before.x) * t
        y = before.y + (after.y - before.y) * t
        diameter = before.diameter + (after.diameter - before.diameter) * t
        # Normal to the midline, pointing toward the constricting wall. The
        # tangent is interpolated between the two vertices rather than taken
        # from the segment, so it turns continuously -- see _tangents.
        tangents = self._tangents()
        tx0, ty0 = tangents[index]
        tx1, ty1 = tangents[index + 1]
        tx, ty = tx0 + (tx1 - tx0) * t, ty0 + (ty1 - ty0) * t
        norm = (tx * tx + ty * ty) ** 0.5 or 1.0
        nx, ny = -ty / norm, tx / norm
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
                        provenance=pt.get("provenance", "hand-placed"),
                    )
                )
        length = elem.get("length-cm")
        rest_elem = elem.find("rest")
        rest = None
        if rest_elem is not None:
            rest = RestPosture(
                arc=float(rest_elem.get("arc", 0.0)),
                offset=float(rest_elem.get("offset", 0.0)),
                lips=rest_elem.get("lips", "closed"),
                jaw=rest_elem.get("jaw", "closed"),
                velum=rest_elem.get("velum", "lowered"),
            )
        heads[name] = Head(
            name=name,
            midline=tuple(sorted(points, key=lambda p: p.arc)),
            rest=rest,
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
    arc from backness and offset from height. The articulator comes from
    the bundle when a phone or diacritic states one (a linguolabial says
    tongue-tip explicitly), otherwise from the place's declared default.
    Unplaceable bundles (no manner, an off-scale manner like silence)
    yield an unplaced point.
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

    articulator = bundle.get("articulator")

    def articulator_for(feature: str, value: str | None) -> str | None:
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        return feat.articulators.get(feat.value_aliases.get(value, value))

    if manner == "vowel":
        arc = value_attr("backness", bundle.get("backness"), "arc")
        offset = value_attr("height", bundle.get("height"), "offset")
        articulator = articulator or articulator_for("backness", bundle.get("backness"))
    else:
        place = bundle.get("place")
        if place is not None:
            feat = features.features.get("place")
            if feat is not None:
                # A combining place (bilabial^velar) sits at the mean of
                # its components' positions -- the fusion's centre of
                # gravity in the tract.
                arcs = [
                    a
                    for comp in feat.expand(place)
                    if (a := value_attr("place", comp, "arc")) is not None
                ]
                if arcs:
                    arc = sum(arcs) / len(arcs)
            if articulator is None and feat is not None:
                # A combining place combines its articulators: a
                # labial-velar moves the lower lip AND the dorsum. (The
                # gestural model makes these two gestures; see
                # docs/gestural-model.md.)
                organs = [
                    organ
                    for comp in feat.expand(place)
                    if (organ := feat.articulators.get(comp)) is not None
                ]
                if organs:
                    seen: list[str] = []
                    for organ in organs:
                        if organ not in seen:
                            seen.append(organ)
                    # The combiner, not a literal "+": this spelling is
                    # read back through Feature.expand.
                    articulator = Feature.COMBINER.join(seen)
        offset = value_attr("manner", manner, "offset")
    return TractPoint(arc=arc, offset=offset, articulator=articulator)
