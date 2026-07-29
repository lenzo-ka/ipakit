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
import math
import xml.etree.ElementTree as ET
from collections.abc import Sequence
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
    nasal: tuple[MidlinePoint, ...] = ()
    port_arc: float | None = None
    teeth: tuple[tuple[str, float, float, str], ...] = ()
    carriage: tuple[tuple[float, float], ...] = ()
    tongue_span: tuple[float, float, float, float] | None = None

    @staticmethod
    def _tangents_of(pts: Sequence[MidlinePoint]) -> list[tuple[float, float]]:
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

    def _project_along(
        self, pts: Sequence[MidlinePoint], arc: float, offset: float
    ) -> tuple[float, float] | None:
        """Project onto any declared polyline -- the midline or a branch."""
        if len(pts) < 2:
            return None
        arc = min(max(arc, pts[0].arc), pts[-1].arc)
        index = len(pts) - 2
        for i in range(len(pts) - 1):
            if pts[i].arc <= arc <= pts[i + 1].arc:
                index = i
                break
        before, after = pts[index], pts[index + 1]
        span = after.arc - before.arc
        t = (arc - before.arc) / span if span else 0.0
        x = before.x + (after.x - before.x) * t
        y = before.y + (after.y - before.y) * t
        diameter = before.diameter + (after.diameter - before.diameter) * t
        tangents = self._tangents_of(pts)
        tx0, ty0 = tangents[index]
        tx1, ty1 = tangents[index + 1]
        tx, ty = tx0 + (tx1 - tx0) * t, ty0 + (ty1 - ty0) * t
        norm = (tx * tx + ty * ty) ** 0.5 or 1.0
        nx, ny = -ty / norm, tx / norm
        travel = offset * diameter
        return (x + nx * travel, y + ny * travel)

    def tongue_offset(self, arc: float, control: TractPoint) -> float | None:
        """The offset the tongue surface takes at ``arc`` for one control.

        The tongue is a single body: a constriction somewhere carries the
        tip, blade and dorsum with it, so one control deforms a span rather
        than marking a point. The deformation is a raised cosine centred on
        the control and falling to the resting offset at ``falloff`` away,
        which is the shape Pink Trombone uses for the same reason.

        Returns None outside the span the tongue bounds -- in front of it the
        boundary is the teeth and lips, behind it the pharyngeal wall.
        """
        if self.tongue_span is None or control.arc is None or control.offset is None:
            return None
        low, high, falloff, taper = self.tongue_span
        if not low <= arc <= high:
            return None
        rest = self.rest.offset if self.rest is not None else 0.0
        distance = abs(arc - control.arc)
        if distance >= falloff:
            offset = rest
        else:
            weight = 0.5 * (1.0 + math.cos(math.pi * distance / falloff))
            offset = rest + (control.offset - rest) * weight
        # Descend to the floor near each end, so the body comes to a tip in
        # front and an anchor behind rather than stopping flat at the resting
        # offset. This applies whatever the control is doing, including where
        # the control is too far away to raise the surface at all.
        if taper > 0.0:
            edge = min(arc - low, high - arc)
            if edge < taper:
                offset *= max(edge, 0.0) / taper
        return offset

    def jaw_carriage(self, arc: float) -> float:
        """How much of what sits at ``arc`` the jaw carries, 0 to 1.

        The mandible constricts nothing, so it is not an articulator. It is a
        carrier: the lower lip, the lower teeth and the tongue's anterior
        attachment ride on it, and its position therefore sets how open that
        part of the tract can be. A posture that opens the jaw widens the
        anterior aperture in proportion to this, which is what contrastive
        emphasis does.
        """
        if not self.carriage:
            return 0.0
        pts = self.carriage
        if arc <= pts[0][0]:
            return pts[0][1]
        for i in range(len(pts) - 1):
            a0, v0 = pts[i]
            a1, v1 = pts[i + 1]
            if a0 <= arc <= a1:
                span = a1 - a0
                t = (arc - a0) / span if span else 0.0
                return v0 + (v1 - v0) * t
        return pts[-1][1]

    def jaw_close(self, control: TractPoint) -> float:
        """How far the jaw is closed for this posture, 0 open to 1 shut.

        The jaw is not stated by any feature -- it makes no constriction, so
        it is not an articulator -- but it is not free either: a segment that
        closes at the lips closes the jaw with it, and an open vowel opens
        it. Taking the constriction's own degree is the honest approximation
        available from what a phone declares.
        """
        if control.offset is None or control.arc is None:
            return 0.0
        # Only a constriction the jaw carries closes the jaw. A glottal or
        # pharyngeal one does not: `jaw_carriage` is ~0 back there, and
        # deriving a closed jaw from /h/ would be reading the mandible off a
        # constriction it takes no part in.
        front = self.jaw_carriage(0.0)
        share = (self.jaw_carriage(control.arc) / front) if front else 0.0
        return max(0.0, min(1.0, control.offset * share))

    def carried(
        self, point: tuple[float, float], arc: float, close: float
    ) -> tuple[float, float]:
        """Move a point the way the jaw carries it, for a given closure.

        The mandible constricts nothing but carries the lower lip, the lower
        teeth and the tongue's anterior attachment, by the measured fraction
        in `jaw_carriage`. Closing the jaw lifts them toward the palate in
        that proportion, which is why a bilabial closure is the lips meeting
        somewhere between their open positions rather than the lower one
        travelling the whole way alone.
        """
        share = self.jaw_carriage(arc) * close
        if share <= 0.0:
            return point
        roof = self.project(TractPoint(arc=arc, offset=1.0))
        floor = self.project(TractPoint(arc=arc, offset=0.0))
        if roof is None or floor is None:
            return point
        return (
            point[0] + (roof[0] - floor[0]) * share,
            point[1] + (roof[1] - floor[1]) * share,
        )

    def lips(
        self, closed: bool = False, close: float = 0.0
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """Upper and lower lip, as the tract's two boundaries at arc 0.

        A bilabial closure is these two meeting, which is why it is the model
        that has to say where they are: a renderer deriving them from the
        tube ends is re-deriving geometry the head already fixes.
        """
        upper = self.project(TractPoint(arc=0.0, offset=1.0))
        lower = self.project(TractPoint(arc=0.0, offset=0.0))
        if upper is None or lower is None:
            return None
        # The jaw carries the lower lip most of the way; the rest is the lip's
        # own. Closing the jaw therefore moves the lower lip even for a phone
        # that is not a closure.
        lower = self.carried(lower, 0.0, close)
        if not closed:
            return (upper, lower)
        # They meet between: the upper lip comes down about a quarter of what
        # is left, the lower lip rises the rest.
        meet = (
            lower[0] + (upper[0] - lower[0]) * 0.72,
            lower[1] + (upper[1] - lower[1]) * 0.72,
        )
        return (meet, meet)

    def project_nasal(
        self, arc: float, offset: float = 0.0
    ) -> tuple[float, float] | None:
        """A point on the nasal branch, or None if the head declares none.

        The branch has its own arc: 0 at the nostrils, 1 at the velopharyngeal
        port. It couples to the oral tract only through that port, which the
        velum seals when raised (docs/tract-anatomy.md 4.3), so nothing here
        depends on the oral arc.
        """
        if not self.nasal:
            return None
        return self._project_along(self.nasal, arc, offset)

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
        tangents = self._tangents_of(self.midline)
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
        nasal_elem = elem.find("nasal")
        nasal_points: tuple[MidlinePoint, ...] = ()
        port_arc: float | None = None
        if nasal_elem is not None:
            raw_port = nasal_elem.get("port")
            port_arc = float(raw_port) if raw_port else None
            nasal_points = tuple(
                MidlinePoint(
                    arc=float(pt.get("arc", 0.0)),
                    x=float(pt.get("x", 0.0)),
                    y=float(pt.get("y", 0.0)),
                    diameter=float(pt.get("diameter", 0.0)),
                    provenance=pt.get("provenance", "hand-placed"),
                )
                for pt in nasal_elem.findall("point")
            )
        teeth_elem = elem.find("teeth")
        teeth: tuple[tuple[str, float, float, str], ...] = ()
        if teeth_elem is not None:
            teeth = tuple(
                (
                    pt.get("name", ""),
                    float(pt.get("x", 0.0)),
                    float(pt.get("y", 0.0)),
                    pt.get("carrier", "skull"),
                )
                for pt in teeth_elem.findall("point")
            )
        carriage_elem = elem.find("carriage")
        carriage: tuple[tuple[float, float], ...] = ()
        if carriage_elem is not None:
            carriage = tuple(
                (float(pt.get("arc", 0.0)), float(pt.get("jaw", 0.0)))
                for pt in carriage_elem.findall("point")
            )
        tongue_elem = elem.find("tongue")
        tongue_span: tuple[float, float, float, float] | None = None
        if tongue_elem is not None:
            tongue_span = (
                float(tongue_elem.get("from", 0.0)),
                float(tongue_elem.get("to", 1.0)),
                float(tongue_elem.get("falloff", 0.3)),
                float(tongue_elem.get("taper", 0.0)),
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
            nasal=nasal_points,
            port_arc=port_arc,
            teeth=teeth,
            carriage=carriage,
            tongue_span=tongue_span,
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


@dataclass(frozen=True)
class Landmarks:
    """Where the named parts of the tract sit, derived from the data.

    A renderer needs the drawable places, the articulators that reach them,
    and which of those close about the tract axis rather than toward a wall.
    All of it is declared in ``ipa.xml``; none of it should be restated by a
    caller. ``scripts/tract_svg.py`` did restate it and drifted -- it marked
    eleven frication sites where the inventory has twelve, because
    ``bilabial`` hosts two fricatives and had been forgotten.

    A value is drawable when it declares an ``arc``. The combining places
    (``bilabial^velar``, ``bilabial^palatal``) declare none: their position
    is their components' and not a point of their own.
    """

    places: dict[str, float]
    articulators: dict[str, float]
    median: dict[str, float]
    frication: frozenset[str]


def landmarks(features: IPAFeatures) -> Landmarks:
    """Read the drawable landmarks out of the declared data."""

    def arcs(name: str) -> dict[str, float]:
        feature = features.features.get(name)
        if feature is None:
            return {}
        return {
            value: coords["arc"]
            for value, coords in feature.coordinates.items()
            if coords.get("arc") is not None
        }

    articulator = features.features.get("articulator")
    apertures = articulator.apertures if articulator is not None else {}
    every = arcs("articulator")
    median = {v: a for v, a in every.items() if apertures.get(v) == "median"}
    frication = {
        features.get_features(phone).get("place")
        for phone in features.phones
        if features.get_features(phone).get("manner") in ("fricative", "affricate")
    }
    return Landmarks(
        places=arcs("place"),
        articulators={v: a for v, a in every.items() if v not in median},
        median=median,
        frication=frozenset(p for p in frication if p),
    )


def velic_aperture(features: IPAFeatures, bundle: dict[str, str]) -> float:
    """How far the velum lowers for this bundle -- 0 sealed, 1 fully open.

    Read from the ``nasality`` bridge, which already declares that a nasal
    manner, a nasalized segment and a nasal release are one dimension spelled
    three ways. The bridge exists so per-feature comparison can see that; the
    same declaration says how far each spelling opens the port, so the
    geometry and the metric cannot disagree about what counts as nasal.

    A bundle spelling nasality more than one way takes the widest.
    """
    apertures = features.bridge_apertures.get("nasality", {})
    open_to = [
        aperture
        for (feature, value), aperture in apertures.items()
        if bundle.get(feature) == value
    ]
    return max(open_to) if open_to else 0.0


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
