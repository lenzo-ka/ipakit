"""Draw a declared head, so a change to the geometry can be looked at.

``heads.xml`` is the only part of this library whose output is a picture, and
it was the only part with no way to see one. A diameter is four characters in
a diff; it is a visible pinch in a drawn tract. The change that prompted this
module left a slope of +0.364 between two midline points, which read as an
ordinary number and drew as a flare that belonged to nothing, and a normal
taken per segment drew a wall that crossed itself three times.

This is the *rendering* layer; :mod:`ipakit.tract` is the model. They are two
modules rather than one because ``ipakit.metric`` reads the model, and
nothing that computes a distance should be able to reach a stylesheet.
Nothing here computes geometry: every coordinate comes from ``Head.project``.

What is drawn
-------------

    section   the tract wall at full offset either side of the centerline,
              through ipakit.tract.Head.project -- the same call a renderer
              makes, so the drawing cannot drift from the model
    profile   the declared diameter against arc, where a change to the
              profile is legible rather than merely present

One entry
---------

:func:`drawing` derives everything a figure needs, once, and every caller
reaches a picture through it -- :func:`figure`, ``ipakit tract draw``,
``make figures`` and the property tests. It is written that way because the
command and the tests once derived the posture separately, which is two
chances to disagree about what the picture is.

    >>> figure("t").startswith("<svg ")
    True

Comparing two revisions
-----------------------

    python -m ipakit.tract_svg dump -o /tmp/before.json    # on one revision
    python -m ipakit.tract_svg draw --compare /tmp/before.json -o tract.html

Heads are read only by ``Head.project`` and never by ``ipakit.metric``, so a
change here cannot move a distance. ``scripts/sweep.py diff`` is the check.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .features import IPAFeatures
from .tract import (
    Head,
    Landmarks,
    Posture,
    TractPoint,
    Trajectory,
    blend,
    head,
    heads,
    landmarks,
    posture,
    tract_point,
)
from .tract import (
    trajectory as build_trajectory,
)

SAMPLES = 240
WIDTH = 760
SECTION_HEIGHT = 560
CHART_HEIGHT = 300
PAD = 54
CEILING = 0.20
FRAMES_PER_UNIT = 8  # how finely the ordinal timeline is sampled between units
MS_PER_UNIT = 420  # playback only: maps one ordinal unit to wall-clock ms
NASAL_FLOOR_THICKNESS = 0.012  # bony thickness between the oral roof and nasal floor

Point = tuple[float, float]
Scaler = Callable[[float, float], Point]


def sample(h: Head, samples: int = SAMPLES, close: float = 0.0) -> list[dict[str, Any]]:
    """The three positions the geometry actually declares, at each arc.

    ``offset`` is constriction degree: 0 leaves the articulator at the
    midline and 1 carries it to the wall, so the wall is fixed and the
    articulator sweeps between. Drawing the wall mirrored below the midline
    -- offset -1 -- draws a second tract that does not exist and makes the
    section twice as wide as the aperture it is meant to show.
    """
    rest = h.rest.offset if h.rest is not None else 0.0
    rows: list[dict[str, Any]] = []
    for i in range(samples + 1):
        arc = i / samples
        openp = h.project(TractPoint(arc=arc, offset=0.0))
        restp = h.project(TractPoint(arc=arc, offset=rest))
        wall = h.project(TractPoint(arc=arc, offset=1.0))
        if openp is None or restp is None or wall is None:
            continue
        # The mandible carries the whole lower boundary, not just the teeth.
        # Closing the jaw lifts the floor, and with it the tongue's underside
        # and the lower lip, by the measured fraction at that arc.
        if close:
            openp = h.carried(openp, arc, close)
            restp = h.carried(restp, arc, close)
        rows.append({"arc": arc, "open": openp, "rest": restp, "wall": wall})
    return rows


def tongue_surface(
    name: str,
    control: TractPoint | list[TractPoint],
    close: float = 0.0,
    closures: tuple[TractPoint, ...] = (),
) -> list[tuple[float, float, float]]:
    """The tongue surface for one control, asked of the model at each arc.

    ``Head.tongue_offset`` is where the deformation lives; this only samples
    it and projects. Outside the span the tongue is not the boundary.
    """
    h = head(name)
    controls = [control] if isinstance(control, TractPoint) else list(control)
    # Only a declared apical closure bounds the body's front. The inventory's
    # tongue-tip offsets jump from 0.50 to 0.70, so every threshold strictly
    # between them separates the same classes; heads.xml states 0.60 rather
    # than presenting that convenient separator as a measurement. In
    # particular /l, ɫ, ɭ, ɹ/ use 0.50 and keep the declared anterior
    # attachment. Although phonetic /l/ has central tip contact, this model
    # draws its tip at half height and therefore treats it as a non-closure.
    closure_threshold = h.tongue_closure_threshold
    tip_closures = [
        c
        for c in closures
        if c.articulator == "tongue-tip"
        and c.arc is not None
        and c.offset is not None
        and c.offset >= closure_threshold
    ]
    active_tip = min(tip_closures, key=lambda c: c.arc or 0.0, default=None)
    front = None
    if active_tip is not None:
        assert active_tip.arc is not None and active_tip.offset is not None
        # A static target has the same tip in the deformation controls and the
        # phonetic closures, so it bites at its declared arc (including /s/).
        # During a blend the two differ: ease the edge from the attachment as
        # the closure rises from the declared threshold to the wall.  Thus the
        # semantic guard does not itself introduce an animation step.
        at_target = any(
            c.articulator == "tongue-tip"
            and c.arc == active_tip.arc
            and c.offset == active_tip.offset
            for c in controls
        )
        strength = (
            1.0
            if at_target
            else (active_tip.offset - closure_threshold) / (1.0 - closure_threshold)
        )
        assert h.tongue_span is not None
        front = h.tongue_span[0] + strength * (active_tip.arc - h.tongue_span[0])
    out: list[tuple[float, float, float]] = []
    if h.tongue_span is None:
        return out
    low, high, _, _ = h.tongue_span
    arcs = [low]
    arcs.extend(i / SAMPLES for i in range(SAMPLES + 1) if low < i / SAMPLES < high)
    arcs.append(high)
    for arc in arcs:
        # Clamp leading grid samples to the exact moving-edge point, then emit
        # that coincident run once. The remaining body retains grid alignment
        # without snapping the visible front to whichever cell contains it.
        sample_arc = max(arc, front) if front is not None else arc
        if out and math.isclose(sample_arc, out[-1][0]):
            continue
        point = h.tongue_point(sample_arc, control, close)
        if point is None:
            continue
        # The posterior tongue/floor seam is load-bearing anatomy. Controls
        # may deform the body above it but may not lift this endpoint free of
        # the jaw-carried floor anchor.
        if h.tongue_span is not None and math.isclose(sample_arc, h.tongue_span[1]):
            floor = h.project(TractPoint(arc=sample_arc, offset=0.0))
            if floor is not None:
                point = h.carried(floor, sample_arc, close)
        out.append((sample_arc, point[0], point[1]))
    return out


def geometry(name: str, close: float = 0.0) -> dict[str, Any]:
    h = head(name)
    rest = h.rest
    # The hard palate is one shared boundary: its top is the nasal floor, its
    # underside the oral roof. Over the palate the nasal lower wall therefore
    # rides the measured roof outline (a thin bony thickness above it) rather
    # than floating on the branch's own diameter, which left a hollow gap. In
    # front of the palate the branch's own lower wall carries the external nose.
    roof_xy = sorted(((p.x, p.y) for p in h.roof), key=lambda q: q[0])

    def nasal_floor(narc: float) -> tuple[float, float] | None:
        base = h.project_nasal(narc, -1.0)
        if (
            base is None
            or not roof_xy
            or not (roof_xy[0][0] <= base[0] <= roof_xy[-1][0])
        ):
            return base
        x = base[0]
        for (x0, y0), (x1, y1) in zip(roof_xy, roof_xy[1:], strict=False):
            if x0 <= x <= x1:
                f = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
                return (x, y0 + f * (y1 - y0) + NASAL_FLOOR_THICKNESS)
        return base

    nasal = [
        {
            "arc": i / 60,
            "mid": h.project_nasal(i / 60, 0.0),
            "wall": h.project_nasal(i / 60, 1.0),
            "low": nasal_floor(i / 60),
        }
        for i in range(61)
    ]
    return {
        "rows": sample(h, close=close),
        "nasal": [n for n in nasal if None not in n.values()],
        "port_arc": h.port_arc,
        "velum_hinge_arc": h.velum_hinge_arc,
        "velum_lowered_arc": h.velum_lowered_arc,
        "teeth": [{"name": n, "x": x, "y": y, "carrier": c} for n, x, y, c in h.teeth],
        "hinge": h.hinge,
        "lips_open": h.lips(close=close),
        "lips_body": h.lip_body(close=close),
        "lip_contact": 0.0,
        "rest_arc": None if rest is None else rest.arc,
        "rest_offset": None if rest is None else rest.offset,
        "rest_lips": None if rest is None else rest.lips,
        "midline": [
            {
                "arc": p.arc,
                "x": p.x,
                "y": p.y,
                "diameter": p.diameter,
                "provenance": p.provenance,
            }
            for p in h.midline
        ],
    }


def _pose(p: Posture) -> tuple[float, float, str] | None:
    """The (arc, offset, articulator) a posture holds, or None.

    A placed reading poses at itself; an unplaced one -- silence -- falls back
    to the head's rest, named ``"at rest"``; the reference drawing carries no
    reading and poses nowhere. This is the tuple ``render`` and the property
    tests read, so it is derived here rather than twice.
    """
    reading = p.reading
    if reading is not None and reading.arc is not None and reading.offset is not None:
        return (reading.arc, reading.offset, reading.articulator or "articulator")
    rest = p.rest
    if rest is not None and rest.arc is not None and rest.offset is not None:
        return (rest.arc, rest.offset, "at rest")
    return None


def build_geometry(head: Head, marks: Landmarks, p: Posture) -> dict[str, Any]:
    """Project a :class:`~ipakit.tract.Posture` to the geometry a figure draws.

    The vector -> geometry step. It reads only ``p`` (what the symbol fixed),
    ``head`` (the geometry that projects it) and ``marks`` (the inventory's
    landmarks) -- never a phone or a feature bundle -- so animating a figure is
    interpolating ``p`` and calling this per frame. Jaw close is derived here,
    from the posture's own point, because it is a fact about the head and not
    about the segment.
    """
    pose = _pose(p)
    close = 0.0
    if pose is not None:
        close = head.jaw_close(TractPoint(arc=pose[0], offset=pose[1]))
    if head.rest is not None and head.rest.jaw == "closed":
        close = max(close, p.rest_weight)
    current = geometry(head.name, close)
    velum = head.velum(p.velic)
    if velum is not None:
        current["velum"] = {
            "body": velum.body,
            "oral": velum.oral,
            "tip": velum.tip,
            "wall": velum.wall,
            "aperture": velum.aperture,
        }
    epiglottis = head.epiglottis(p.epiglottal)
    if epiglottis is not None:
        current["epiglottis"] = {
            "body": epiglottis.body,
            "tip": epiglottis.tip,
            "target": epiglottis.target,
            "aperture": epiglottis.aperture,
        }
    current["landmarks"] = marks
    lower_lip = next((q for q in p.constrictions if q.articulator == "lower-lip"), None)
    # Lower-lip place is itself interpolated between the bilabial target at
    # arc 0 and the labiodental target at arc .03.  Convert that continuous
    # place back into the bilabial share of the gesture, and convert degree
    # into activation above the head's declared open baseline.  The latter
    # keeps place and degree consistent at an unplaced vowel target: its
    # implied baseline degree contributes no contact whichever neighbouring
    # gesture supplies the otherwise immaterial fallback place.
    contact = 0.0
    if lower_lip is not None and lower_lip.arc is not None:
        bilabial_share = 1.0 - lower_lip.arc / 0.03
        baseline = 0.0 if head.rest is None else float(head.rest.offset)
        degree = float(lower_lip.offset or 0.0)
        activation = (degree - baseline) / (1.0 - baseline)
        contact = max(0.0, min(1.0, activation)) * max(0.0, min(1.0, bilabial_share))
    if head.rest is not None and head.rest.lips == "closed":
        contact = max(contact, p.rest_weight)
    current["lip_contact"] = max(0.0, min(1.0, contact))
    current["lips_closed_now"] = current["lip_contact"] >= 1.0 - 1e-12
    current["lips_body"] = head.lip_body(current["lip_contact"], close=close)
    current["lips_open"] = head.lips(current["lip_contact"], close=close)
    # A reading is present for every phone and absent only for the reference
    # drawing, so it stands in for "this is a phone": the closures, the marks
    # and the carried teeth belong to a phone and not to the reference.
    if p.reading is not None and pose is not None:
        current["teeth"] = [
            {
                **t,
                **(
                    dict(
                        zip(
                            ("x", "y"),
                            head.rotate_jaw((t["x"], t["y"]), close),
                            strict=True,
                        )
                    )
                    if t["carrier"] == "mandible"
                    else {}
                ),
            }
            for t in current["teeth"]
        ]
        points = list(p.tongue_controls)
        current["tongue"] = tongue_surface(
            head.name, points, close, closures=p.constrictions
        )
        current["extra"] = [
            (q.arc, q.offset, q.articulator or "")
            for q in points[1:]
            if q.arc is not None and q.offset is not None
        ]
    if p.reading is not None:
        current["marks"] = [{"label": m.label, "kind": m.kind} for m in p.unmodelled]
        current["secondary"] = [
            {"arc": m.arc, "offset": m.offset, "label": m.label}
            for m in p.secondary
            if m.placed
        ]
        if p.glottal is not None:
            current["folds"] = [
                {"edges": edges, "shut": p.glottal <= 0.01}
                for arc in sorted(marks.median.values())
                if (edges := head.median_body(arc, p.glottal)) is not None
            ]
    return current


def build_frontal_geometry(head: Head, marks: Landmarks, p: Posture) -> dict[str, Any]:
    """Pose Head's face-on contours from the same view-neutral posture.

    The tongue is a frontal silhouette of the same surface the sagittal view
    samples through :meth:`Head.tongue_offset`. Its near edge is
    ``tongue_span[0]``, the same declared anterior body attachment where the
    unbounded sagittal surface begins. At each lateral ordinate the declared
    tongue planform exposes an arc band: that attachment is nearest the
    aperture and its declared root is deepest at the midline. The highest
    surface in that band is the visible upper edge (the union of structures
    intersecting that sightline).  Offset already means floor-to-roof
    fraction, so it maps directly between the declared lower and upper mouth
    curves; there is no view-specific lift.  Teeth are nearer still and the
    existing arc-ordered paint pass occludes the resulting tongue honestly.

    What this buys is the dorsum: the central band reaches the declared root
    arc, so a dorsal gesture raises the visible edge instead of leaving the
    tip to speak for the whole body.  That is the load-bearing property.  How
    the band narrows away from the midline is not: at the lateral extremes the
    teeth occlude the difference, and a rectangular or linear taper renders
    the same figure.  The chord below is the sightline depth of an ellipsoidal
    body, chosen because it degrades to the tip at the corners without a
    discontinuity -- not because the declared tongue fixes that curve.

    Occlusion remains a read: every contour and every posture coordinate is
    retained here. :func:`frontal_svg` alone clips and paints them.
    ``marks`` is part of the projection contract (and supplies declared arc
    vocabulary); no phone or symbol reaches this path.
    """
    del marks  # declared inventory geometry, reserved for frontal labels
    pose = _pose(p)
    close = head.jaw_close(TractPoint(pose[0], pose[1])) if pose else 0.0
    if head.rest is not None and head.rest.jaw == "closed":
        close = max(close, p.rest_weight)
    # Rest declares closed lips, independently of the neutral tongue-body
    # point that locates the sagittal tract interior.  Ease that frontal seam
    # shut as a blend approaches home; changing the view-neutral posture here
    # would also move the sagittal drawing.
    if (
        pose is not None
        and p.rest is not None
        and p.rest.arc is not None
        and p.rest.offset is not None
    ):
        distance = math.hypot(pose[0] - p.rest.arc, pose[1] - p.rest.offset)
        close = max(close, max(0.0, 1.0 - distance / 0.20))
        if distance <= 0.025:
            close = 1.0
    if pose is not None and pose[0] <= 0.02 and pose[1] >= 0.995:
        close = 1.0
    gap = max(0.0, 0.115 * (1.0 - close))
    width = p.aperture_width
    mouth = head.frontal_mouth(gap * 0.55, width, p.protrusion)

    def edge_y(edge: tuple[Point, ...], x: float) -> float:
        """Piecewise-linear ordinate on a declared mouth parting curve."""
        for left, right in zip(edge, edge[1:], strict=False):
            if left[0] <= x <= right[0]:
                span = right[0] - left[0]
                t = (x - left[0]) / span if span else 0.0
                return left[1] + (right[1] - left[1]) * t
        return min(edge, key=lambda point: abs(point[0] - x))[1]

    def frontal_tongue(
        declared: tuple[Point, ...], controls: list[TractPoint]
    ) -> tuple[Point, ...]:
        """Project the declared tongue planform and sagittal surface."""
        if not controls or head.tongue_span is None or len(declared) < 4:
            return declared
        top = declared[:3]
        left, center, right = top
        front = head.tongue_span[0]
        root = head.tongue_span[1]
        # Density sets the lateral endpoints and the depth band exactly, and
        # the center and closure height only to within the sampling of the
        # raised cosine: a coarse grid can step over the constriction peak.
        # Measured, the drift is sub-pixel at figure scale (center ~7e-5 from
        # SAMPLES 30 to 960, closure height ~4e-3 from samples 6 to 240), far
        # inside the reach pin's tolerance.
        samples = 24
        upper: list[Point] = []
        for index in range(samples + 1):
            x = left[0] + (right[0] - left[0]) * index / samples
            half = max(center[0] - left[0], right[0] - center[0]) or 1.0
            lateral = min(1.0, abs(x - center[0]) / half)
            # A sagittal tongue span projected face-on has an elliptical
            # planform: the available depth is the chord sqrt(1-u^2) at
            # normalized lateral position u.  Thus the band comes entirely
            # from the declared tip, root and frontal width, not a tuned lift.
            deepest = front + (root - front) * math.sqrt(max(0.0, 1.0 - lateral**2))
            offsets: list[float] = []
            for step in range(SAMPLES + 1):
                arc = front + (deepest - front) * step / SAMPLES
                offsets.extend(
                    value
                    for control in controls
                    if (value := head.tongue_offset(arc, control)) is not None
                )
            offset = min(1.0, max(offsets, default=0.0))
            roof = edge_y(mouth["upper_edge"], x)
            floor = edge_y(mouth["lower_edge"], x)
            upper.append((x, floor + (roof - floor) * offset))
        # The declared posterior points remain the tongue/floor closure; only
        # the visible upper edge is derived from the live tongue surface.
        return tuple(upper) + tuple(declared[3:])

    contours: list[dict[str, Any]] = []
    for name, carrier, arc, declared in head.frontal:
        if name in {"upper-lip", "lower-lip"} and name in mouth:
            contours.append(
                {"name": name, "carrier": carrier, "arc": arc, "points": mouth[name]}
            )
            continue
        points = []
        for index, (x, y) in enumerate(declared):
            if name in {
                "upper-lip",
                "lower-lip",
                "upper-teeth",
                "lower-teeth",
                "tongue",
            }:
                x = 0.5 + (x - 0.5) * width
            if carrier == "mandible":
                carry = 0.15 if name == "tongue" else 0.55
                # The lower-face contour begins at the shared mouth corners;
                # its inner menton points ride with the mandible while those
                # soft-tissue endpoints remain sewn to the lip seam.
                if name == "chin" and index in {0, len(declared) - 1}:
                    carry = 0.0
                y += gap * carry
            points.append((x, y))
        if name == "tongue":
            points = list(frontal_tongue(tuple(points), list(p.tongue_controls)))
        contours.append(
            {"name": name, "carrier": carrier, "arc": arc, "points": points}
        )
    return {
        "contours": contours,
        "aperture": mouth.get("aperture", ()),
        "upper_edge": mouth.get("upper_edge", ()),
        "lower_edge": mouth.get("lower_edge", ()),
        "closed": gap <= 0.001,
    }


def _frontal_extent(*sets: dict[str, Any]) -> tuple[float, float, float, float]:
    """Mouth-first extent; deliberately knows no sagittal geometry keys."""
    visible = {"nose", "upper-lip", "lower-lip", "chin"}
    points = [
        point
        for src in sets
        for contour in src["contours"]
        if contour["name"] in visible
        for point in contour["points"]
    ]
    return (
        min(x for x, _ in points),
        max(x for x, _ in points),
        min(y for _, y in points),
        max(y for _, y in points),
    )


def _scaler(
    x0: float, x1: float, y0: float, y1: float, *, flip_y: bool = True
) -> Scaler:
    """Fit chart coordinates into a panel, optionally reversing the y axis."""
    sx = (WIDTH - 2 * PAD) / (x1 - x0) if x1 > x0 else 1.0
    sy = (SECTION_HEIGHT - 2 * PAD) / (y1 - y0) if y1 > y0 else 1.0
    scale = min(sx, sy)
    ox = PAD + ((WIDTH - 2 * PAD) - (x1 - x0) * scale) / 2
    oy = PAD + ((SECTION_HEIGHT - 2 * PAD) - (y1 - y0) * scale) / 2

    def to(px: float, py: float) -> Point:
        y = y1 - py if flip_y else py - y0
        return (ox + (px - x0) * scale, oy + y * scale)

    return to


def _frontal_scaler(x0: float, x1: float, y0: float, y1: float) -> Scaler:
    """Scale face-chart coordinates, whose y axis runs forehead to chin."""
    return _scaler(x0, x1, y0, y1, flip_y=False)


FRONTAL_STYLE = """
.f-nose,.f-chin{fill:none;stroke:#8b6758;stroke-width:2}
.f-upper-lip,.f-lower-lip{fill:#a84f59;stroke:#71343c;stroke-width:2}.f-aperture{fill:#24191a}
.f-upper-teeth,.f-lower-teeth{fill:#f4efe3;stroke:#9c9487;stroke-width:1.5}.f-tongue{fill:#bd6970;stroke:#7b4148;stroke-width:1.5}
.f-label{font:11px ui-monospace,monospace;fill:#8b817d}
"""


def frontal_svg(
    geometry: dict[str, Any],
    extent: tuple[float, float, float, float] | None = None,
) -> str:
    """Project and stroke one frontal geometry with arc-ordered occlusion."""
    to = _frontal_scaler(*(extent if extent is not None else _frontal_extent(geometry)))
    aperture = [to(*point) for point in geometry["aperture"]]
    aperture_path = _path(aperture, True)
    parts = [
        f'<defs><clipPath id="f-mouth"><path d="{aperture_path}"/></clipPath></defs>'
    ]
    by_name = {c["name"]: c for c in geometry["contours"]}
    if not geometry["closed"]:
        parts.append(f'<path d="{aperture_path}" class="f-aperture"/>')
        interiors = [
            c
            for c in geometry["contours"]
            if c["name"] in {"tongue", "upper-teeth", "lower-teeth"}
        ]
        for contour in sorted(interiors, key=lambda c: c["arc"], reverse=True):
            parts.append(
                f'<path d="{_path([to(*p) for p in contour["points"]], True)}" class="f-{contour["name"]}" clip-path="url(#f-mouth)"/>'
            )
    for name in ("chin", "nose", "upper-lip", "lower-lip"):
        contour = by_name.get(name)
        if contour:
            points = [to(*p) for p in contour["points"]]
            if name == "eyes" and len(points) == 4:
                parts.extend(
                    f'<path d="{_path(points[i : i + 2])}" class="f-eyes"/>'
                    for i in (0, 2)
                )
            else:
                parts.append(
                    f'<path d="{_path(points, name in {"nose", "upper-lip", "lower-lip"})}" class="f-{name}"/>'
                )
    return f'<svg viewBox="0 0 {WIDTH} {SECTION_HEIGHT}" role="img" aria-label="Frontal tract view">{"".join(parts)}</svg>'


def standalone_frontal_svg(geometry: dict[str, Any]) -> str:
    svg = frontal_svg(geometry)
    return svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).replace(
        ">", f"><style>{FRONTAL_STYLE}</style>", 1
    )


def drawing(
    name: str, phone: str | None, features: IPAFeatures | None = None
) -> dict[str, Any]:
    """Everything a figure needs, derived once.

    Three steps kept apart: :func:`~ipakit.tract.posture` reads the symbol
    into a number vector, :func:`build_geometry` projects that vector through
    the head, and the caption and ``active`` layer name the symbol itself.
    Every caller reaches a picture through here -- ``cmd_draw`` and the
    property tests once derived the posture separately, which is two chances
    to disagree about what the picture is.
    """
    ipa = features or IPAFeatures()
    # Read off the same inventory as the geometry and the caption. These were
    # once module-level, resolved against the package data at import, so a
    # caller's own ``features`` moved the posture and left the folds, the
    # places and the articulators speaking for a different inventory.
    h = head(name)
    marks = landmarks(ipa, h.name)
    p = posture(ipa, phone, h)
    current = build_geometry(h, marks, p)
    caption: dict[str, Any] | None = None
    active: dict[str, str] | None = None
    if phone is not None:
        stated = ipa.get_features(phone, with_defaults=False)
        caption = {
            "phone": phone,
            # Asked of the inventory this drawing is being made against,
            # not of the package-level default: a caller passing its own
            # ``features`` must get a caption from the same data as the
            # geometry, and the two would otherwise disagree silently.
            "describe": ipa.describe(phone),
            "features": [
                (k, v) for k, v in sorted(stated.items()) if k not in ("href", "class")
            ],
        }
        bundle = ipa.get_features(phone)
        point = tract_point(ipa, bundle)
        # A vowel states backness and height, not place, so its place set is
        # empty rather than absent -- absent would mean "label them all".
        active = {"place": str(bundle.get("place") or "")}
        if point.offset is not None:
            active["degree"] = (
                "closed" if point.offset >= 0.995 else f"{1 - point.offset:.2f} open"
            )
        # The glottal state at the finest granularity the segment spells it,
        # named by the data's own label rather than by a table here.
        for key in ("phonation", "voiced"):
            feature = ipa.features.get(key)
            value = bundle.get(key)
            if feature is not None and value is not None:
                active["glottal"] = feature.labels.get(value) or f"{key} {value}"
                break
        if point.articulator:
            active["articulator"] = str(point.articulator)
    return {
        "head": name,
        "phone": phone,
        "geometry": current,
        "aperture": p.velic,
        "posture": _pose(p),
        "caption": caption,
        "active": active,
    }


def render(
    drawn: dict[str, Any],
    prior: dict[str, Any] | None = None,
    caption: bool = True,
) -> str:
    """A :func:`drawing` as a standalone SVG document.

    The one place a ``drawn`` mapping is unpacked into
    :func:`standalone_svg`. Every caller that writes a figure -- ``make
    figures``, ``ipakit tract draw``, :func:`figure`, the tests -- goes
    through here, so a figure cannot be assembled two ways.
    """
    return standalone_svg(
        drawn["geometry"],
        prior,
        drawn["aperture"],
        drawn["posture"],
        drawn["caption"] if caption else None,
        drawn["active"],
    )


def render_page(
    drawn: dict[str, Any],
    prior: dict[str, Any] | None = None,
    caption: bool = True,
) -> str:
    """A :func:`drawing` as a standalone HTML page.

    :func:`render` for the page route. The mapping was unpacked into
    :func:`page` by hand at two call sites, which is where ``--no-caption``
    was honored at one of them and not at the other.
    """
    return page(
        drawn["head"],
        drawn["geometry"],
        prior,
        drawn["aperture"],
        drawn["phone"],
        drawn["posture"],
        drawn["caption"] if caption else None,
        drawn["active"],
    )


def figure(
    phone: str | None = None,
    head_name: str | None = None,
    features: IPAFeatures | None = None,
    caption: bool = True,
) -> str:
    """One posture, as a standalone SVG document.

    The public way to draw. ``phone`` is a unit -- a phone, or a phone
    with diacritics -- and ``None`` asks for the reference drawing, every
    landmark named at the head's rest posture. ``head_name`` defaults to
    the head ``heads.xml`` declares as default.

    These are the bytes ``make figures`` writes, so a figure obtained here
    and a figure checked into ``docs/figures`` are the same object.

    One posture is the whole contract. A form is a sequence of postures
    and a derivation is a sequence of forms, so neither has a figure --
    see ``docs/tract-figures.md``.
    """
    name = head_name if head_name is not None else head().name
    return render(drawing(name, phone, features), caption=caption)


def frontal_figure(
    phone: str | None = None,
    head_name: str | None = None,
    features: IPAFeatures | None = None,
) -> str:
    """One posture through the face-on projection."""
    ipa = features or IPAFeatures()
    h = head(head_name)
    return standalone_frontal_svg(
        build_frontal_geometry(h, landmarks(ipa, h.name), posture(ipa, phone, h))
    )


def _extent(*sets: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for src in sets:
        for _, tx, ty in src.get("tongue") or []:
            xs.append(tx)
            ys.append(ty)
        for row in src["rows"]:
            for key in ("open", "rest", "wall"):
                xs.append(row[key][0])
                ys.append(row[key][1])
        for row in src.get("nasal") or []:
            for key in ("mid", "wall", "low"):
                point = row.get(key)
                if point is not None:
                    xs.append(point[0])
                    ys.append(point[1])
    return min(xs), max(xs), min(ys), max(ys)


def _path(points: list[Point], close: bool = False) -> str:
    body = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return body + (" Z" if close else "")


def _band(src: dict[str, Any], to: Scaler, a: str, b: str) -> str:
    """Closed region between two offset traces -- the articulator's sweep."""
    top = [to(*row[a]) for row in src["rows"]]
    bottom = [to(*row[b]) for row in src["rows"]]
    return _path(top + list(reversed(bottom)), close=True)


def _inside(src: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows from the lips inward.

    The lips are bodies occupying the tract's open end, so a boundary drawn
    all the way to arc 0 runs through them. It should meet them instead.
    """
    return [row for row in src["rows"] if row["arc"] >= LIP_INSET]


def _lip_seam(src: dict[str, Any], to: Scaler, which: int) -> Point | None:
    """The inner shoulder of a lip, where the tract boundary joins it.

    Trimming the boundary by a fixed arc leaves it short of the lip or
    through it, depending on the head. Starting it on the lip's own shoulder
    makes them meet by construction.
    """
    bodies = src.get("lips_body")
    if not bodies or which >= len(bodies):
        return None
    pts = [to(*q) for q in bodies[which]]
    # Roots are index 0 and 4 and stay in the bone; shoulders travel with the
    # free edge. The boundary meets the lip where it is attached, so a closing
    # lip does not drag the palate down with it.
    return max((pts[0], pts[4]), key=lambda q: q[0])


def _trace(src: dict[str, Any], to: Scaler, key: str) -> str:
    pts = [to(*row[key]) for row in _inside(src)]
    seam = _lip_seam(src, to, 0 if key == "wall" else 1)
    if seam is not None and key in ("wall", "open"):
        pts.insert(0, seam)
    return _path(pts)


CHAR_W = 6.72  # advance of the 10.5px monospace label face, rounded up:
# reserving less than the text occupies lets labels collide
LINE_H = 12.0
LIP_INSET = 0.014  # arc taken off the front, so the boundary meets the lips


def _lips(
    src: dict[str, Any],
    to: Scaler,
    posture: tuple[float, float, str] | None,
    taken: list[tuple[float, ...]],
    named_lip: bool = False,
) -> str:
    """The lips, as the model places them.

    A bilabial closure is the lower lip meeting the upper; ``Head.lips``
    says where both are, open or closed, so nothing is derived here.
    """
    # A bilabial closes the lips; so does rest, which the head declares.
    contact = float(src.get("lip_contact", 0.0))
    closed = contact >= 1.0 - 1e-12
    pair = src.get("lips_open")
    if not pair:
        return ""
    bodies = src.get("lips_body")
    if not bodies:
        return ""
    parts = []
    for i, body in enumerate(bodies):
        pts = [to(*q) for q in body]
        shut = closed and i == 1
        part = "upper-lip" if i == 0 else "lower-lip"
        parts.append(
            f'<path d="M{pts[0][0]:.1f},{pts[0][1]:.1f} '
            f"L{pts[1][0]:.1f},{pts[1][1]:.1f} "
            f"Q{pts[2][0]:.1f},{pts[2][1]:.1f} {pts[3][0]:.1f},{pts[3][1]:.1f} "
            f'L{pts[4][0]:.1f},{pts[4][1]:.1f}" '
            f'class="lip {part}{" shut" if shut else ""}"/>'
        )
    # When a lip is the articulator the label above already names it, with its
    # state; a generic "lips" beside it says the same thing twice.
    if named_lip:
        return "".join(parts)
    anchor = to(*pair[1])
    for text, lx, ly, depth in _place_labels([("lips", anchor)], 16, 13, taken):
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + depth + 10:.1f}" class="lbl lip" '
            f'text-anchor="middle">{text}</text>'
        )
    return "".join(parts)


CHIP = 9.0  # side of an annotation chip
CHIP_GAP = 5.0  # between a chip and its word
ITEM_GAP = 20.0  # between one annotation and the next
STRIP_FOOT = 12.0  # baseline of the lowest annotation row, off the bottom edge


def _folds(src: dict[str, Any], to: Scaler) -> str:
    """The vocal folds, at the aperture the segment's glottal state asks for.

    ``Head.median_body`` is where the shape lives; this only projects it.
    Two bodies, meeting at the tract axis when the folds are shut, so a
    glottal stop closes here rather than against a wall and /t/ and /d/
    stop being the same picture.
    """
    bodies = src.get("folds") or []
    if not bodies:
        return ""
    parts = []
    for pair in bodies:
        shut = bool(pair["shut"])
        for body in pair["edges"]:
            pts = [to(*q) for q in body]
            parts.append(
                f'<path d="{_path(pts, close=True)}" '
                f'class="fold{" shut" if shut else ""}"/>'
            )
    return "".join(parts)


def _secondary(src: dict[str, Any], to: Scaler, taken: list[tuple[float, ...]]) -> str:
    """The lesser constrictions a secondary articulation states.

    Drawn like the primary and lighter: a ring at the place the feature
    declares, and a lead from the open trace to it. ``l`` and ``ɫ`` differ
    here, at the velum, which is exactly where the difference is.
    """
    parts = []
    for item in src.get("secondary") or []:
        row = min(src["rows"], key=lambda r: abs(r["arc"] - item["arc"]), default=None)
        if row is None:
            continue
        openp, wall = to(*row["open"]), to(*row["wall"])
        cx = openp[0] + (wall[0] - openp[0]) * item["offset"]
        cy = openp[1] + (wall[1] - openp[1]) * item["offset"]
        parts.append(
            f'<line x1="{openp[0]:.1f}" y1="{openp[1]:.1f}" x2="{cx:.1f}" '
            f'y2="{cy:.1f}" class="secondreach"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" class="second"/>'
        )
        for text, lx, ly, depth in _place_labels(
            [(str(item["label"]), (cx, cy))], -20, -13, taken
        ):
            parts.append(
                f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{lx:.1f}" '
                f'y2="{ly + depth:.1f}" class="lead second"/>'
                + _text(lx, ly + depth + 10, "lbl second", text)
            )
    return "".join(parts)


def _chip(x: float, y: float, kind: str) -> str:
    """One annotation's token: a shape per reason the plane cannot hold it.

    Shape rather than color alone, because these have to survive a
    rasterizer and a monochrome print. ``kind`` is derived in
    ``ipakit.tract.unmodelled`` from the feature's own declaration.
    """
    cls = kind.replace(" ", "-")
    half = CHIP / 2
    if kind == "out of plane":
        # A circle seen edge-on: the axis this section projects away.
        return f'<circle cx="{x + half:.1f}" cy="{y:.1f}" r="{half:.1f}" class="chip {cls}"/>'
    if kind == "phase":
        # An arrow out of the mouth: the segment's release, which is later.
        return (
            f'<path d="M{x + CHIP:.1f},{y - half:.1f} L{x:.1f},{y:.1f} '
            f'L{x + CHIP:.1f},{y + half:.1f}" class="chip {cls}"/>'
        )
    if kind == "prosodic":
        # A bar along time: it belongs to the unit, not to the posture.
        return (
            f'<path d="M{x:.1f},{y:.1f} L{x + CHIP:.1f},{y:.1f}" class="chip {cls}"/>'
        )
    if kind == "approximate":
        # A tilde. Every other chip says the drawing does not hold this;
        # this one says the drawing holds it with a stand-in, and a square
        # beside the others would read as the opposite of what it means.
        return (
            f'<path d="M{x:.1f},{y + half / 2:.1f} '
            f"Q{x + CHIP / 4:.1f},{y - half:.1f} {x + CHIP / 2:.1f},{y:.1f} "
            f"Q{x + 3 * CHIP / 4:.1f},{y + half:.1f} {x + CHIP:.1f},"
            f'{y - half / 2:.1f}" class="chip {cls}"/>'
        )
    return (
        f'<rect x="{x:.1f}" y="{y - half:.1f}" width="{CHIP:.1f}" '
        f'height="{CHIP:.1f}" class="chip {cls}"/>'
    )


def _strip(marks: list[dict[str, str]], taken: list[tuple[float, ...]]) -> str:
    """The annotation layer, along the foot of the drawing.

    Everything here is stated by the segment and absent from the geometry,
    so it is set apart from it rather than dressed up as a contour. Rows
    fill left to right and stack upward, and their boxes are reserved
    *before* any tract label is placed, so the two layers cannot collide.
    """
    if not marks:
        return ""
    widths = [CHIP + CHIP_GAP + len(m["label"]) * CHAR_W for m in marks]
    rows: list[list[int]] = [[]]
    used = 0.0
    limit = WIDTH - 2 * PAD
    for i, width in enumerate(widths):
        extra = width + (ITEM_GAP if rows[-1] else 0.0)
        if rows[-1] and used + extra > limit:
            rows.append([])
            used = width
        else:
            used += extra
        rows[-1].append(i)
    parts = []
    for depth, row in enumerate(reversed(rows)):
        y = SECTION_HEIGHT - STRIP_FOOT - depth * (LINE_H + 4)
        total = sum(widths[i] for i in row) + ITEM_GAP * (len(row) - 1)
        x = (WIDTH - total) / 2
        for i in row:
            label = marks[i]["label"]
            text_w = len(label) * CHAR_W
            center = x + CHIP + CHIP_GAP + text_w / 2
            parts.append(_chip(x, y - LINE_H / 3, marks[i]["kind"]))
            parts.append(
                f'<text x="{center:.1f}" y="{y:.1f}" class="lbl chiplbl" '
                f'text-anchor="middle">{label}</text>'
            )
            # Reserved a little wide: a box narrower than the text it holds
            # is the mistake this whole layout exists to avoid.
            taken.append((x - 2, y - LINE_H - 2, x + widths[i] + 2, y + 2))
            x += widths[i] + ITEM_GAP
    return "".join(parts)


def _literal_style() -> str:
    """STYLE with every custom property resolved, plus a light-theme block.

    A standalone SVG has to render outside a browser -- a repo view, a
    rasterizer, a slide -- and custom properties are widely unsupported
    there. ``rsvg-convert`` drops ``stroke:var(--x)`` entirely, so a figure
    written that way comes out blank while looking correct in a browser.
    Emitting literals keeps both themes without depending on ``var()``.
    """

    def tokens(block: str) -> dict[str, str]:
        return dict(re.findall(r"--([\w-]+):\s*([^;}]+)", block))

    dark = re.search(r":root\{([^}]*)\}", STYLE)
    light = re.search(r"prefers-color-scheme:light\)\{:root\{([^}]*)\}", STYLE)
    dark_map = tokens(dark.group(1)) if dark else {}
    light_map = tokens(light.group(1)) if light else {}

    body = re.sub(r"@media[^{]*\{.*?\}\s*\}", "", STYLE, flags=re.S)
    body = re.sub(r":root(\[[^\]]*\])?\{[^}]*\}", "", body)

    def resolve(text: str, table: dict[str, str]) -> str:
        return re.sub(
            r"var\(--([\w-]+)\)",
            lambda m: table.get(m.group(1), "currentColor"),
            text,
        )

    out = resolve(body, dark_map)
    if light_map:
        out += "@media (prefers-color-scheme:light){" + resolve(body, light_map) + "}"
    return out


def _caption(caption: dict[str, Any] | None) -> str:
    """The phone, its description and its stated features, inside the SVG.

    The drawing travels on its own -- into a doc, a slide, a bug report --
    and a page heading does not travel with it. ``href`` and ``class`` are
    metadata rather than articulation and are left out.
    """
    if not caption:
        return ""
    right = WIDTH - 26
    parts = [
        f'<text x="{right}" y="44" class="glyph" text-anchor="end">'
        f"{caption['phone']}</text>",
        f'<text x="{right}" y="64" class="lbl caption" text-anchor="end">'
        f"{caption['describe']}</text>",
    ]
    y = 84
    for key, value in caption["features"]:
        parts.append(
            f'<text x="{right}" y="{y}" class="lbl feat" text-anchor="end">'
            f'<tspan class="featkey">{key}</tspan> {value}</text>'
        )
        y += 15
    return "".join(parts)


def _tongue_body(src: dict[str, Any], to: Scaler) -> str | None:
    """Return the closed tongue body used both to paint and to occlude."""
    surface = src.get("tongue") or []
    if len(surface) < 2:
        return None
    top = [to(x, y) for _, x, y in surface]
    lo, hi = surface[0][0], surface[-1][0]
    floor = [to(*row["open"]) for row in src["rows"] if lo <= row["arc"] <= hi]
    if not floor:
        return _path(top)
    floor_rev = list(reversed(floor))
    tx, ty = top[0]
    fx, fy = floor_rev[-1]
    dx, dy = tx - fx, ty - fy
    face = (dx * dx + dy * dy) ** 0.5 or 1.0
    # Curl the tip. Dropping straight from the tip to the floor draws a flat
    # front face; a quadratic from the front-most floor point up to the tip,
    # bulged out perpendicular to that face, rounds the front into a tip.
    # Keep the bulge modest and clamp its control no further forward than the
    # tip, so the curl cannot loop past the contact and double the translucent
    # fill into a darker lobe.
    px, py = -dy / face, dx / face
    if px > 0:
        px, py = -px, -py
    mx, my = (tx + fx) / 2, (ty + fy) / 2
    cx, cy = mx + px * face * 0.32, my + py * face * 0.32
    cx = max(cx, min(tx, fx))
    seg = " L".join(f"{x:.2f},{y:.2f}" for x, y in top + floor_rev)
    return f"M{seg} Q{cx:.2f},{cy:.2f} {tx:.2f},{ty:.2f} Z"


def _tongue(src: dict[str, Any], to: Scaler) -> str:
    """The tongue as a body, not a line.

    Its upper surface is what constricts, but drawn alone it reads as an arc
    from base to tip. The underside runs along the floor of the mouth, which
    is where a fully open articulator sits -- the offset-0 trace -- so
    closing the surface back along that over the same span gives the body.
    """
    surface = src.get("tongue") or []
    body = _tongue_body(src, to)
    if body is None:
        return ""
    top = [to(x, y) for _, x, y in surface]
    return (
        f'<path d="{body}" class="tonguebody"/>'
        f'<path d="{_path(top)}" class="tongue"/>'
    )


def _epiglottis(src: dict[str, Any], to: Scaler) -> str:
    """Paint the already-posed head-owned epiglottal leaf."""
    shape = src.get("epiglottis")
    if not shape:
        return ""
    points = [to(*point) for point in shape["body"]]
    return f'<path d="{_path(points, True)}" class="epiglottis"/>'


def _constriction(
    src: dict[str, Any],
    to: Scaler,
    posture: tuple[float, float, str] | None,
    taken: list[tuple[float, ...]],
) -> str:
    """The oral constriction this phone makes, at its own arc and offset.

    A lowered velum opens the nose; it does not close the mouth. The oral
    closure is the lips for ``m``, the tongue tip for ``n``, the dorsum for
    ``ng`` -- which is why ``b`` and ``m`` differ here only in the velic
    aperture, and why the drawing has to show both to say which is which.
    """
    if posture is None:
        return ""
    arc, offset, articulator = posture
    if articulator in src["landmarks"].median:
        # A median articulator closes about the tract axis, not toward a
        # wall, so `offset` is not its degree: drawing this mark for a
        # glottal stop puts the closure against the pharyngeal wall. The
        # folds carry it instead -- see _folds.
        return ""
    rows = src["rows"]
    row = min(rows, key=lambda r: abs(r["arc"] - arc), default=None)
    if row is None:
        return ""
    wall = to(*row["wall"])
    openp = to(*row["open"])
    # offset carries the articulator from the midline to the wall
    ax = openp[0] + (wall[0] - openp[0]) * offset
    ay = openp[1] + (wall[1] - openp[1]) * offset
    shut = offset >= 0.995
    if arc <= 0.02 and shut:
        return ""  # drawn as the lips meeting, see _lips
    # The dot marks the constriction target on the articulator, with its name
    # and state beside it. The reach line from the midline up to the dot was
    # drawn before the tongue was a body; the body now shows the reach, so the
    # line only read as a stray dash under the tip.
    parts = [
        f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5" '
        f'class="constriction{" shut" if shut else ""}"/>'
    ]
    name = articulator.replace("-", " ")
    label = f"{name}\n{'closed' if shut else f'{1 - offset:.2f} open'}"
    for text, lx, ly, depth in _place_labels([(label, (ax, ay))], -18, -13, taken):
        parts.append(_text(lx, ly + depth + 10, "lbl constriction", text))
    return "".join(parts)


def _wall_with_port(src: dict[str, Any], to: Scaler, aperture: float) -> str:
    """The oral roof, broken where a lowered velum has left it open.

    The velum *is* part of the boundary. Raised, it seals the port and the
    roof is continuous; lowered, the roof is open to the nasopharynx and the
    nasal branch's floor is no longer an obstruction. Drawing an unbroken
    wall with a flap on top says the port is never open, whatever the flap
    is doing.
    """
    rows = _inside(src)
    seam = _lip_seam(src, to, 0)
    if aperture <= 0.01:
        pts = [to(*r["wall"]) for r in rows]
        if seam is not None:
            pts.insert(0, seam)
        return f'<path d="{_path(pts)}" class="wall"/>'
    declared = src.get("port_arc")
    if declared is None:
        return f'<path d="{_path([to(*r["wall"]) for r in rows])}" class="wall"/>'
    port = float(declared)
    hinge = src.get("velum_hinge_arc")
    if hinge is None:
        return f'<path d="{_path([to(*r["wall"]) for r in rows])}" class="wall"/>'
    # The moving velum replaces this exact part of the oral boundary. Its
    # declared hinge, rather than a renderer span, says where the fixed palate
    # ends; the posterior port says where the pharyngeal wall resumes.
    before = [to(*r["wall"]) for r in rows if r["arc"] <= float(hinge)]
    after = [to(*r["wall"]) for r in rows if r["arc"] >= port]
    # The roof meets the lip whether or not the velum has broken it further
    # back; this branch used to skip the seam and leave the front adrift.
    if seam is not None and before:
        before.insert(0, seam)
    out = []
    if len(before) > 1:
        out.append(f'<path d="{_path(before)}" class="wall"/>')
    if len(after) > 1:
        out.append(f'<path d="{_path(after)}" class="wall"/>')
    return "".join(out)


def _at(src: dict[str, Any], arc: float, key: str) -> Point | None:
    best = min(src["rows"], key=lambda r: abs(r["arc"] - arc), default=None)
    return None if best is None else best[key]


def _text(x: float, y: float, cls: str, label: str) -> str:
    """A label, one tspan per line, so a state can sit under its name."""
    lines = label.split("\n")
    spans = "".join(
        f'<tspan x="{x:.1f}" dy="{0 if i == 0 else LINE_H:.0f}">{line}</tspan>'
        for i, line in enumerate(lines)
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="middle">{spans}</text>'


def _place_labels(
    items: list[tuple[str, Point]], base: int, step: int, taken: list[tuple[float, ...]]
) -> list[tuple[str, float, float, float]]:
    """Drop each label to the shallowest depth where it does not collide.

    A fixed stagger cannot work here: the front of the mouth packs six places
    into 0.24 of arc, so any fixed number of rows eventually overlaps. This
    walks the labels in order and pushes each one along until its box is
    clear of every box already placed, which terminates and leaves the
    drawing readable whatever the head's proportions are.

    The stated direction is tried first and then the other one, because a
    label pushed off the bottom of the frame is exactly as unreadable as one
    sitting under another: the three-line glottal label ran past the canvas
    on every head. Clear beats inside only when nothing satisfies both.
    """

    def clear(at: tuple[float, ...]) -> bool:
        return not any(
            at[0] < t[2] and t[0] < at[2] and at[1] < t[3] and t[1] < at[3]
            for t in taken
        )

    out: list[tuple[str, float, float, float]] = []
    depths = [base + step * i for i in range(12)]
    depths += [base - step * i for i in range(1, 12)]
    for name, (x, y) in items:
        lines = name.split("\n")
        half = max(len(line) for line in lines) * CHAR_W / 2
        height = LINE_H * len(lines)
        boxes = [(x - half, y + d, x + half, y + d + height) for d in depths]
        chosen = next(
            (
                i
                for i, at in enumerate(boxes)
                if clear(at) and at[1] >= 0.0 and at[3] <= SECTION_HEIGHT
            ),
            next((i for i, at in enumerate(boxes) if clear(at)), 0),
        )
        taken.append(boxes[chosen])
        out.append((name, x, y, depths[chosen]))
    return out


def _annotate(
    src: dict[str, Any],
    to: Scaler,
    taken: list[tuple[float, ...]],
    active: dict[str, str] | None = None,
    posed: Point | None = None,
) -> str:
    """Places under the roof, articulators under the floor.

    Labels used to sit above the wall, which is where the nasal branch now
    runs, so they collided with it and with each other. Places are read off
    the roof and hang inside the oral cavity; articulators hang below the
    open trace. Both stagger over three depths, because the front of the
    mouth packs six places into 0.24 of arc and two depths is not enough.
    """
    parts: list[str] = []
    # The landmarks the inventory this drawing was made against declares --
    # carried on the geometry by ``drawing`` rather than resolved here, so a
    # caller's own data names its own places.
    marks = src["landmarks"]

    # A reference drawing names every landmark; a phone names only the ones it
    # uses, or the labels crowd out the thing they are labeling.
    want_place = None if active is None else active.get("place")
    want_art = None if active is None else active.get("articulator")

    anchors: list[tuple[str, Point]] = []
    for name, arc in sorted(marks.places.items(), key=lambda kv: kv[1]):
        if want_place is not None and name != want_place:
            continue
        anchor = _at(src, arc, "wall")
        if anchor is not None:
            anchors.append((name, to(*anchor)))
    for name, x, y, depth in _place_labels(anchors, 14, 13, taken):
        cls = "place fric" if name in marks.frication else "place"
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + depth:.1f}" '
            f'class="lead {cls}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" class="mark {cls}"/>'
            f'<text x="{x:.1f}" y="{y + depth + 10:.1f}" class="lbl {cls}" '
            f'text-anchor="middle">{name.replace("-", " ")}</text>'
        )

    # An articulator is labeled where the posture puts it. Anchoring to the
    # fully-open trace points at the floor, which is not where a tongue tip
    # making an alveolar closure is, nor where a lower lip making /m/ is.
    anchors = []
    for name, arc in sorted(marks.articulators.items(), key=lambda kv: kv[1]):
        if want_art is not None and name != want_art:
            continue
        anchor = posed if posed is not None else _at(src, arc, "open")
        if anchor is not None:
            anchors.append((name, to(*anchor) if posed is None else posed))
    for shown, x, y, depth in _place_labels(anchors, 18, 13, taken):
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + depth:.1f}" '
            f'class="lead art"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" class="mark art"/>'
            + _text(x, y + depth + 10, "lbl art", shown)
        )
    voicing = None if active is None else active.get("glottal")
    constricts = None if active is None else active.get("articulator")
    for name, arc in marks.median.items():
        wall = _at(src, arc, "wall")
        openp = _at(src, arc, "open")
        if wall is None or openp is None:
            continue
        wx, wy = to(*wall)
        ox, oy = to(*openp)
        cx, cy = (wx + ox) / 2, (wy + oy) / 2
        parts.append(
            f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{wx:.1f}" y2="{wy:.1f}" '
            f'class="median"/>'
        )
        # The ring stands for the axis these folds close about. Where the
        # folds themselves are drawn it sits in the gap between them and
        # reads as something in the airway, so the bodies replace it.
        if not src.get("folds"):
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" class="medianmark"/>'
            )
        states = []
        if voicing is not None:
            # The word comes from the data's own `label`, at whatever
            # granularity the segment states: "breathy-voiced" when it
            # spells a phonation, "voiceless" when it spells only `voiced`.
            states.append(voicing)
        if name == constricts and active is not None and active.get("degree"):
            states.append(str(active["degree"]))
        shown = "\n".join([name.replace("-", " "), *states]) if states else name
        for label, lx, ly, depth in _place_labels([(shown, (cx, cy))], 14, 13, taken):
            parts.append(
                f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{lx:.1f}" '
                f'y2="{ly + depth:.1f}" class="lead art"/>'
                + _text(lx, ly + depth + 10, "lbl art", label.replace("-", " "))
            )
    teeth = src.get("teeth") or []
    for prefix, tag, base in (
        ("upper-", "upper teeth", -22),
        ("lower-", "lower teeth", 14),
    ):
        row = [t for t in teeth if str(t["name"]).startswith(prefix)]
        if len(row) < 2:
            continue
        # A tooth has extent: crown, incisal edge and arch close into a
        # wedge rather than a bare polyline, so it reads as a body sitting
        # on the jaw it belongs to.
        pts = [to(t["x"], t["y"]) for t in row]
        parts.append(f'<path d="{_path(pts, close=True)}" class="teeth"/>')
        step = 13 if base > 0 else -13
        if active is not None:
            continue
        for label, lx, ly, depth in _place_labels([(tag, pts[0])], base, step, taken):
            parts.append(
                f'<text x="{lx:.1f}" y="{ly + depth + 10:.1f}" class="lbl teeth" '
                f'text-anchor="middle">{label}</text>'
            )
    rest_arc = src.get("rest_arc") if active is None else None
    if rest_arc is not None:
        anchor = _at(src, float(rest_arc), "rest")
        if anchor is not None:
            x, y = to(*anchor)
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="restmark"/>'
            )
            for text, rx, ry, depth in _place_labels(
                [("rest", (x, y))], -16, -13, taken
            ):
                parts.append(
                    f'<text x="{rx:.1f}" y="{ry + depth + 10:.1f}" class="lbl rest" '
                    f'text-anchor="middle">{text}</text>'
                )
    return "".join(parts)


def _nasal(
    src: dict[str, Any],
    to: Scaler,
    aperture: float,
    taken: list[tuple[float, ...]],
) -> str:
    """The nasal branch, and the velum at the aperture this bundle asks for."""
    rows = src.get("nasal") or []
    if not rows:
        return ""
    upper = [to(*r["wall"]) for r in rows]
    lower = [to(*r["low"]) for r in rows]
    # The nasopharynx and the oropharynx are continuous; the port is only
    # where the velum can close between them. So the branch's posterior edge
    # joins the oral wall behind the port instead of stopping in mid-air.
    port = src.get("port_arc")
    join: list[Point] = []
    if port is not None:
        behind = [
            to(*r["wall"])
            for r in src["rows"]
            if float(port) <= r["arc"] <= float(port) + 0.10
        ]
        join = behind
    tube = _path(upper + join[::-1] + list(reversed(lower)), close=True)
    mid = _path([to(*r["mid"]) for r in rows])
    # The floor near the port stops being a boundary once the port is open.
    keep = (
        len(lower)
        if aperture <= 0.01
        else max(2, int(len(lower) * (1 - 0.18 * aperture)))
    )
    parts = [
        f'<path d="{tube}" class="nasalfill"/>',
        f'<path d="{_path(upper + join[::-1])}" class="nasalside"/>',
        f'<path d="{_path(lower[:keep])}" class="nasalside"/>',
        f'<path d="{mid}" class="nasalmid"/>',
    ]
    # The nares: the branch's front is the nostril, not a sealed cap. The two
    # side walls stop at the tip and the opening between them faces down and
    # forward past the lip -- the way the lips open the mouth -- so air leaves
    # here. Name it.
    ntop, nbot = upper[0], lower[0]
    nares = ((ntop[0] + nbot[0]) / 2, (ntop[1] + nbot[1]) / 2)
    for label, nx, ny, depth in _place_labels([("nares", nares)], 16, 13, taken):
        parts.append(
            f'<line x1="{nx:.1f}" y1="{ny:.1f}" x2="{nx:.1f}" '
            f'y2="{ny + depth:.1f}" class="lead nasal"/>'
            + _text(nx, ny + depth + 10, "lbl nasal", label)
        )
    lx, ly = to(*rows[len(rows) // 3]["wall"])
    for label, nx, ny, depth in _place_labels(
        [("nasal cavity", (lx, ly))], -20, -13, taken
    ):
        parts.append(
            f'<text x="{nx:.1f}" y="{ny + depth + 10:.1f}" class="lbl nasal" '
            f'text-anchor="middle">{label.replace("-", " ")}</text>'
        )
    posed = src.get("velum")
    if not posed:
        return "".join(parts)
    body = [to(*point) for point in posed["body"]]
    tx, ty = to(*posed["tip"])
    if aperture <= 0.01:
        state = "sealed"
    elif aperture >= 0.99:
        state = "open"
    else:
        state = "part-open"
    # Shape and thickness are already posed by Head; this layer only paints
    # the supplied polygon.
    parts.append(f'<path d="{_path(body, close=True)}" class="velum"/>')
    for text, vx, vy, depth in _place_labels(
        [(f"velum\nport {state}", (tx, ty))], 14, 13, taken
    ):
        parts.append(
            f'<line x1="{vx:.1f}" y1="{vy:.1f}" x2="{vx:.1f}" '
            f'y2="{vy + depth:.1f}" class="lead art"/>'
            + _text(vx, vy + depth + 10, "lbl velum", text)
        )
    return "".join(parts)


def section_svg(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
    aperture: float = 0.0,
    posture: tuple[float, float, str] | None = None,
    caption: dict[str, Any] | None = None,
    active: dict[str, str] | None = None,
    extent: tuple[float, float, float, float] | None = None,
    mark: bool = True,
) -> str:
    # A single figure fits its own extent; a frame of an animation is handed
    # the whole sequence's extent instead, so the scale is one across frames
    # and the tract does not jump between them. The default is unchanged.
    sets = [current] if prior is None else [current, prior]
    to = _scaler(*(extent if extent is not None else _extent(*sets)))
    parts = []
    if prior is not None:
        parts.append(
            '<path d="' + _band(prior, to, "wall", "open") + '" class="sweep prior"/>'
        )
    # With a posture the shaded region is the airway, so it stops at the
    # articulator. Without one it is the articulator's whole sweep, which is
    # what the reference drawing is for.
    surface = current.get("tongue") or []
    if surface:
        tongue_at = {round(a, 6): (x, y) for a, x, y in surface}
        roof: list[Point] = []
        floor: list[Point] = []
        upper_seam = _lip_seam(current, to, 0)
        lower_seam = _lip_seam(current, to, 1)
        if upper_seam is not None:
            roof.append(upper_seam)
        if lower_seam is not None:
            floor.append(lower_seam)
        for row in _inside(current):
            roof.append(to(*row["wall"]))
            here = tongue_at.get(round(row["arc"], 6))
            floor.append(to(*here) if here else to(*row["open"]))
        parts.append(
            f'<path d="{_path(roof + floor[::-1], close=True)}" class="sweep trace"/>'
        )
    else:
        parts.append(
            '<path d="'
            + _path(
                [q for q in (_lip_seam(current, to, 0),) if q]
                + [to(*r["wall"]) for r in _inside(current)]
                + [to(*r["open"]) for r in reversed(_inside(current))]
                + [q for q in (_lip_seam(current, to, 1),) if q],
                close=True,
            )
            + '" class="sweep trace"/>'
        )
    parts.append(_wall_with_port(current, to, aperture))
    if current.get("hinge") is not None:
        hx, hy = to(*current["hinge"])
        parts.append(
            f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="6.0" class="jawhinge"/>'
            f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="1.8" class="jawhinge-pin"/>'
        )
    parts.append('<path d="' + _trace(current, to, "rest") + '" class="restline"/>')
    parts.append('<path d="' + _trace(current, to, "open") + '" class="openline"/>')
    taken: list[tuple[float, ...]] = []
    posed: Point | None = None
    if active is not None and posture is not None:
        row = min(current["rows"], key=lambda r: abs(r["arc"] - posture[0]))
        wall_pt, open_pt = to(*row["wall"]), to(*row["open"])
        posed = (
            open_pt[0] + (wall_pt[0] - open_pt[0]) * posture[1],
            open_pt[1] + (wall_pt[1] - open_pt[1]) * posture[1],
        )
    # The annotation layer reserves its boxes before any tract label is
    # placed, so the two cannot collide however the head is proportioned.
    strip = _strip([dict(m) for m in current.get("marks") or []], taken)
    parts.append(_annotate(current, to, taken, active, posed))
    parts.append(_nasal(current, to, aperture, taken))
    parts.append(_tongue(current, to))
    parts.append(_epiglottis(current, to))
    if mark:
        # The target knob marks a phone's primary constriction in a still. In an
        # animation frame the primary reading interpolates -- it slides from one
        # place's arc to the next (velar to pharyngeal across `k`->`a`) -- so
        # drawing it there shows a constriction migrating through the tract,
        # while the tongue geometry already carries the real per-articulator
        # motion. So the knob is a still-only aid; frames pass `mark=False`.
        parts.append(_constriction(current, to, posture, taken))
    parts.append(_secondary(current, to, taken))
    parts.append(_folds(current, to))
    parts.append(strip)
    parts.append(
        _lips(
            current,
            to,
            posture,
            taken,
            named_lip=bool(active and "lip" in (active.get("articulator") or "")),
        )
    )
    parts.append(_caption(caption))
    return (
        f'<svg viewBox="0 0 {WIDTH} {SECTION_HEIGHT}" role="img" '
        f'aria-label="Mid-sagittal tract section">{"".join(parts)}</svg>'
    )


def standalone_svg(
    current: dict[str, Any],
    prior: dict[str, Any] | None = None,
    aperture: float = 0.0,
    posture: tuple[float, float, str] | None = None,
    caption: dict[str, Any] | None = None,
    active: dict[str, str] | None = None,
) -> str:
    """A section that travels on its own: namespaced, with literal styles.

    The checked-in figures go through here, so a test can redraw one and
    compare bytes without restating what ``make figures`` does to it.
    """
    svg = section_svg(current, prior, aperture, posture, caption, active)
    return svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).replace(
        ">", f"><style>{_literal_style()}</style>", 1
    )


def profile_svg(current: dict[str, Any], prior: dict[str, Any] | None) -> str:
    left, top = 60, 30
    width, height = WIDTH - 110, CHART_HEIGHT - 90
    parts = []
    for arc in (0.0, 0.25, 0.5, 0.75, 1.0):
        gx = left + arc * width
        parts.append(
            f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" '
            f'y2="{top + height}" class="grid"/>'
            f'<text x="{gx:.1f}" y="{top + height + 17}" class="tick" '
            f'text-anchor="middle">{arc:.2f}</text>'
        )
    for value in (0.05, 0.10, 0.15, 0.20):
        gy = top + height - (value / CEILING) * height
        parts.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left + width}" '
            f'y2="{gy:.1f}" class="grid"/>'
            f'<text x="{left - 8}" y="{gy + 4:.1f}" class="tick" '
            f'text-anchor="end">{value:.2f}</text>'
        )
    series: list[tuple[dict[str, Any], str]] = []
    if prior is not None:
        series.append((prior, "prior"))
    series.append((current, "trace"))
    for src, cls in series:
        pts = [
            (
                left + p["arc"] * width,
                top + height - (p["diameter"] / CEILING) * height,
            )
            for p in src["midline"]
        ]
        parts.append(f'<path d="{_path(pts)}" class="line {cls}"/>')
        for (x, y), point in zip(pts, src["midline"], strict=True):
            kind = "measured" if point.get("provenance") == "measured" else cls
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.9" class="dot {kind}"/>'
            )
    parts.append(
        f'<text x="{WIDTH // 2}" y="{CHART_HEIGHT - 8}" class="axis" '
        f'text-anchor="middle">arc — lips 0.00 to glottis 1.00</text>'
    )
    return (
        f'<svg viewBox="0 0 {WIDTH} {CHART_HEIGHT}" role="img" '
        f'aria-label="Declared diameter against arc">{"".join(parts)}</svg>'
    )


STYLE = """
:root{--ground:#0A0E13;--panel:#111922;--edge:#1E2B36;--text:#CFDAE2;
--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;--velum:#7FD1B9;--velumText:#5E9384;--inkQuiet:#93A3AF;--tongueFill:rgba(223,163,58,.16);--lipFill:rgba(159,198,220,.30);--lipShut:rgba(223,163,58,.45);--toothFill:rgba(207,218,226,.55);
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
@media (prefers-color-scheme:light){:root{--ground:#DFE4E8;--panel:#F1F4F6;
--edge:#C9D2D9;--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;
--signal:#A96F0E;--velum:#1F7A63;--velumText:#4C8375;--inkQuiet:#6B7C88;--tongueFill:rgba(169,111,14,.15);--lipFill:rgba(34,67,92,.22);--lipShut:rgba(169,111,14,.38);--toothFill:rgba(22,32,42,.30);--tubeTrace:rgba(34,67,92,.10);
--tubePrior:rgba(154,169,180,.22)}}
:root[data-theme=dark]{--ground:#0A0E13;--panel:#111922;--edge:#1E2B36;
--text:#CFDAE2;--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;--velum:#7FD1B9;--velumText:#5E9384;--inkQuiet:#93A3AF;--tongueFill:rgba(223,163,58,.16);--lipFill:rgba(159,198,220,.30);--lipShut:rgba(223,163,58,.45);--toothFill:rgba(207,218,226,.55);
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
:root[data-theme=light]{--ground:#DFE4E8;--panel:#F1F4F6;--edge:#C9D2D9;
--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;--signal:#A96F0E;--velum:#1F7A63;--velumText:#4C8375;--inkQuiet:#6B7C88;--tongueFill:rgba(169,111,14,.15);--lipFill:rgba(34,67,92,.22);--lipShut:rgba(169,111,14,.38);--toothFill:rgba(22,32,42,.30);
--tubeTrace:rgba(34,67,92,.10);--tubePrior:rgba(154,169,180,.22)}
body{background:var(--ground);color:var(--text);margin:0;
font:400 16px/1.62 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:52px 24px 88px;
display:flex;flex-direction:column;gap:34px}
.eyebrow{font:500 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
letter-spacing:.18em;text-transform:uppercase;color:var(--signal);margin:0}
h1{font-size:30px;line-height:1.2;font-weight:600;margin:10px 0 0;
text-wrap:balance;letter-spacing:-.012em}
h2{font-size:18px;font-weight:600;margin:0 0 4px}
p{margin:0;max-width:66ch}
section{display:flex;flex-direction:column;gap:12px}
figure{margin:0;background:var(--panel);border:1px solid var(--edge);
border-radius:3px;padding:10px;overflow-x:auto}
figure svg{display:block;width:100%;height:auto;min-width:520px}
figcaption{font:400 13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
color:var(--dim);padding:10px 4px 2px}
.sweep{stroke:none}
.sweep.trace{fill:var(--tubeTrace)}
.sweep.prior{fill:var(--tubePrior)}
.wall{fill:none;stroke:var(--trace);stroke-width:2}
.openline{fill:none;stroke:var(--trace);stroke-width:1;opacity:.55}
.restline{fill:none;stroke:var(--trace);stroke-width:1;
stroke-dasharray:3 4;opacity:.75}
.jawhinge{fill:none;stroke:var(--signal);stroke-width:1.8}
.jawhinge-pin{fill:var(--signal)}
.lead{stroke-width:1;opacity:.5}
.lead.place{stroke:var(--trace)}
.lead.place.fric{stroke:var(--signal)}
.lead.art{stroke:var(--dim)}
.mark.place{fill:var(--trace)}
.mark.art{fill:var(--dim)}
.mark.place.fric{fill:var(--signal)}
.lbl{font:400 10.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.glyph{font:500 24px ui-sans-serif,system-ui,-apple-system,sans-serif;
fill:var(--text)}
.lbl.caption{fill:var(--dim);font-size:12px}
.lbl.feat{fill:var(--dim)}
.featkey{fill:var(--inkQuiet);opacity:.75}
.lbl.place{fill:var(--trace)}
.lbl.place.fric{fill:var(--signal)}
.lbl.art{fill:var(--dim)}
.lbl.rest{fill:var(--text)}
.lbl.nasal{fill:var(--dim);font-style:italic}
.restmark{fill:none;stroke:var(--dim);stroke-width:1}
.nasalfill{fill:var(--tubeTrace);stroke:none}
.nasalside{fill:none;stroke:var(--trace);stroke-width:1.5;opacity:.75}
.nasalmid{fill:none;stroke:var(--trace);stroke-width:.8;
stroke-dasharray:2 4;opacity:.5}
.velum{stroke:var(--velum);stroke-width:1.2;stroke-linejoin:round;fill:var(--velum)}
.velumtip{fill:var(--velum)}
.lbl.velum{fill:var(--velumText);font-weight:400}
.median{stroke:var(--dim);stroke-width:1;stroke-dasharray:1 3}
.fold{fill:var(--lipFill);stroke:var(--trace);stroke-width:1.3;stroke-linejoin:round}
.fold.shut{fill:var(--lipShut);stroke:var(--signal);stroke-width:1.5}
.secondreach{stroke:var(--signal);stroke-width:1;stroke-dasharray:1 3;opacity:.6}
.second{fill:none;stroke:var(--signal);stroke-width:1.5;stroke-dasharray:3 2.5}
.lead.second{stroke:var(--signal);opacity:.4}
.lbl.second{fill:var(--signal);opacity:.85}
.chip{fill:none;stroke:var(--inkQuiet);stroke-width:1.4;stroke-linejoin:round;
stroke-linecap:round}
.chip.out-of-plane{stroke-dasharray:2 2}
.chip.phase{stroke:var(--signal)}
.chip.prosodic{stroke:var(--velum);stroke-width:2.4}
.chip.approximate{stroke:var(--signal);stroke-width:1.6}
.lbl.chiplbl{fill:var(--inkQuiet)}
.lip{fill:var(--lipFill);stroke:var(--trace);stroke-width:1.4;stroke-linejoin:round}
.lipstem{stroke:var(--signal);stroke-width:2;stroke-linecap:round;fill:none;opacity:.55}
.lip.shut{fill:var(--lipShut);stroke:var(--signal);stroke-width:1.6}
.lbl.lip{fill:var(--dim);font-weight:400}
.tonguebody{fill:var(--tongueFill);stroke:none}
.tongue{fill:none;stroke:var(--signal);stroke-width:2;stroke-linejoin:round;
stroke-linecap:round;opacity:.9}
.epiglottis{fill:var(--tongueFill);stroke:var(--signal);stroke-width:2;
stroke-linejoin:round;opacity:.9}
.reach{stroke:var(--signal);stroke-width:1;stroke-dasharray:2 3;opacity:.8}
.constriction{fill:none;stroke:var(--signal);stroke-width:1.5}
.constriction.shut{fill:var(--signal)}
.lbl.constriction{fill:var(--signal);font-weight:400;opacity:.85}
.teeth{fill:var(--toothFill);stroke:var(--inkQuiet);stroke-width:1.2;stroke-linejoin:round}
.teethmark{fill:var(--inkQuiet)}
.lbl.teeth{fill:var(--inkQuiet);font-weight:400}
.medianmark{fill:none;stroke:var(--dim);stroke-width:1.5}
.dot.measured{fill:var(--signal)}
td.measured{color:var(--signal)}
.line{fill:none;stroke-width:2;stroke-linejoin:round}
.line.prior{stroke:var(--prior)}
.line.trace{stroke:var(--trace)}
.dot.prior{fill:var(--prior)}
.dot.trace{fill:var(--trace)}
.grid{stroke:var(--edge);stroke-width:1}
.tick,.axis{font:400 11px ui-monospace,SFMono-Regular,Menlo,monospace;
fill:var(--dim)}
.key{display:flex;flex-wrap:wrap;gap:18px;color:var(--dim);
font:400 13px ui-monospace,SFMono-Regular,Menlo,monospace}
.key span{display:inline-flex;align-items:center;gap:7px}
.key i{width:15px;height:2px;display:inline-block}
table{border-collapse:collapse;width:100%;
font:400 13.5px ui-monospace,SFMono-Regular,Menlo,monospace}
th,td{text-align:left;padding:7px 12px 7px 0;
border-bottom:1px solid var(--edge)}
th{color:var(--dim);font-weight:500;font-size:11px;letter-spacing:.1em;
text-transform:uppercase}
td.num{font-variant-numeric:tabular-nums}
td.moved{color:var(--signal)}
@media (max-width:560px){h1{font-size:24px}.wrap{padding:34px 16px 60px}}
"""


def _table(current: dict[str, Any], prior: dict[str, Any] | None) -> str:
    """Provenance for a release page; the comparison only when one is asked for."""
    before = {p["arc"]: p["diameter"] for p in prior["midline"]} if prior else {}
    out = []
    for point in current["midline"]:
        prov = str(point.get("provenance", "hand-placed"))
        cls = " measured" if prov == "measured" else ""
        prov_attr = ' class="measured"' if cls else ""
        cells = [
            f'<td class="num">{point["arc"]:.2f}</td>',
            f'<td class="num{cls}">{point["diameter"]:.3f}</td>',
            f"<td{prov_attr}>{prov}</td>",
        ]
        if prior is not None:
            was = before.get(point["arc"])
            cells.insert(
                1, f'<td class="num">{"—" if was is None else f"{was:.3f}"}</td>'
            )
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(out)


def page(
    name: str,
    current: dict[str, Any],
    prior: dict[str, Any] | None,
    aperture: float = 0.0,
    phone: str | None = None,
    posture: tuple[float, float, str] | None = None,
    caption: dict[str, Any] | None = None,
    active: dict[str, str] | None = None,
) -> str:
    """The figure in a page that reads along with it.

    What the page carries beyond the figure is decided by ``phone`` and not
    by ``caption``: the reference drawing gets the aperture profile and its
    provenance because it is the reference, and a phone asked for without a
    caption is still a phone.
    """
    key = (
        ""
        if prior is None
        else '<div class="key">'
        '<span><i style="background:var(--prior)"></i>compared</span>'
        '<span><i style="background:var(--trace)"></i>current</span></div>'
    )
    subject = f"{phone} — " if phone else ""
    compared = "<th>compared</th>" if prior else ""
    aperture_section = (
        ""
        if phone is not None
        else f"""<section><h2>Declared aperture</h2>
<p>The tract's cross dimension along its length, from the lips at 0 to the
glottis at 1. Amber points are measured; the rest are extrapolated or
hand-placed, which the table below states for each.</p>
<figure>{profile_svg(current, prior)}</figure></section>"""
    )
    provenance = (
        ""
        if phone is not None
        else f"""<section><h2>Where the numbers come from</h2>
<p><em>Measured</em> is the aperture taken from the X-Ray Microbeam database
over 48 speakers. That corpus has no upper wall forward of arc 0.11 and none
behind arc 0.44, so everything outside that span is extrapolated, and the nasal
branch, the teeth and the child head are hand-placed throughout. See
<code>docs/articulatory-data.md</code>.</p>
<table><thead><tr><th>arc</th>{compared}<th>aperture</th><th>provenance</th></tr>
</thead><tbody>{_table(current, prior)}</tbody></table></section>"""
    )
    lede = (
        "Every landmark the head declares, drawn at the rest posture. A "
        "drawing for a single phone names only the landmarks that phone "
        "uses; this one names them all, so it is the key to those."
        if phone is None
        else "The tract shaped for one phone. Only the landmarks this phone "
        "uses are named — see the reference drawing for the rest."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}mid-sagittal tract</title>
<style>{STYLE}</style></head><body>
<div class="wrap">
<header><p class="eyebrow">ipakit · {name}</p>
<h1>Mid-sagittal tract</h1>
<p style="margin-top:12px;color:var(--dim)">{lede}</p></header>

<section><h2>How to read it</h2>
<p>The <b>wall</b> is fixed — palate, teeth, pharyngeal wall. The
<b>articulator</b> sweeps between fully open, at the midline, and closed
against that wall; the shaded band is that sweep and the dashed line inside
it is the rest position. A constriction is therefore a place along the tract
and a degree of closure, which is exactly what <code>arc</code> and
<code>offset</code> hold.</p>
<p>The tongue is one body, so a constriction deforms its whole surface rather
than marking a point: moving it carries the tip, blade and dorsum along. The
<b>velic port</b> opens when a segment states nasality, and a lowered velum
leaves a gap in the oral roof, because the velum is part of that boundary.
Places in amber host a fricative or affricate somewhere in the inventory.</p>
<figure>{section_svg(current, prior, aperture, posture, caption, active)}</figure>{key}</section>

{aperture_section}

{provenance}
</div></body></html>"""


def _frame_svg(
    geom: dict[str, Any],
    p: Posture,
    extent: tuple[float, float, float, float],
) -> str:
    """One frame, drawn exactly as a still is.

    A frame is a blended :class:`~ipakit.tract.Posture` projected to geometry
    and handed to the same assembly a single figure uses -- ``section_svg``,
    the path ``render`` reaches through ``standalone_svg``. It carries no
    caption and no ``active`` layer because those name the symbol, and a frame
    is a function of the numbers only. The shared ``extent`` fixes the scale
    so nothing jumps between frames.
    """
    return section_svg(
        geom, None, p.velic, _pose(p), None, None, extent=extent, mark=False
    )


PLAYER_CSS = """
.wrap{max-width:900px}
.filmstrip{display:flex;gap:10px;overflow-x:auto;padding:4px 2px 10px}
.filmstrip .cell{flex:0 0 auto;width:190px;background:var(--panel);
border:1px solid var(--edge);border-radius:3px;padding:6px}
.filmstrip .cell svg{display:block;width:100%;height:auto}
.filmstrip .cell .num{font:400 11px ui-monospace,SFMono-Regular,Menlo,monospace;
color:var(--dim);text-align:center;padding-top:4px}
.stage{background:var(--panel);border:1px solid var(--edge);border-radius:3px;
padding:10px;overflow-x:auto}
.stage .frame{display:none}
.stage .frame.on{display:block}
.stage .frame svg{display:block;width:100%;height:auto;min-width:520px}
.twopane{display:grid;grid-template-columns:1fr 1fr;gap:10px}.twopane svg{min-width:0!important}
.controls{display:flex;gap:14px;align-items:center;margin-top:14px;
font:400 13px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--dim)}
.controls button{font:inherit;color:var(--text);background:transparent;
border:1px solid var(--edge);border-radius:3px;padding:6px 14px;cursor:pointer}
.controls button:hover{border-color:var(--dim)}
.controls input[type=range]{flex:1;accent-color:var(--signal)}
.controls .count{font-variant-numeric:tabular-nums;min-width:72px;text-align:right}
.transcript{display:flex;align-items:baseline;justify-content:center;gap:14px;
margin-top:12px;font:400 18px ui-monospace,SFMono-Regular,Menlo,monospace}
.transcript .display-label{color:var(--dim);font:600 14px ui-sans-serif,system-ui,sans-serif}
.transcript .ipa{display:flex;gap:3px;align-items:baseline}
.transcript .unit{display:inline-block;min-width:1.15em;padding:3px 5px;text-align:center;
border-bottom:2px solid transparent;border-radius:3px;color:var(--dim)}
.transcript .unit.active{color:var(--text);background:var(--panel);
border-bottom-color:var(--signal)}
"""

# Player preparation belongs outside the measured trajectory.  The track's
# stamps continue to cover exactly its acoustic window.
TIMED_PLAYER_REST_RAMP_SECONDS = 0.20


def _html_text(value: str, parameter: str) -> str:
    """Escape preserved HTML text, refusing codepoints HTML would rewrite.

    LF is the sole carried control: it permits an intentional multiline label
    and HTML parsing preserves it verbatim. Other C0 controls, DEL, and C1
    controls are not representable under that promise and are refused.
    """
    for character in value:
        codepoint = ord(character)
        if (codepoint < 0x20 and character != "\n") or 0x7F <= codepoint <= 0x9F:
            raise ValueError(
                f"{parameter} contains control character U+{codepoint:04X}"
            )
    return html.escape(value)


def _player_page(
    word: str,
    name: str,
    frames: list[str],
    stills: list[str],
    ms_per_frame: int,
    phases: list[str | None] | None = None,
    *,
    units: tuple[str, ...] = (),
    active_units: list[tuple[int, ...]] | None = None,
    display_label: str | None = None,
) -> str:
    """One self-contained page: a filmstrip of the units, and a player.

    Every frame is the literal output of ``section_svg`` and shares one
    ``<style>`` and one viewBox, so a frame is byte-for-byte what a still
    figure would be. The player is a flipbook -- one frame shown at a time,
    advanced by an inline scrubber and autoplay -- rather than a morph,
    because the frames already differ in full and there is nothing to tween
    in the document itself. Zero runtime dependencies; ``ms_per_frame`` is
    the only place the ordinal clock is mapped to wall-clock time.
    """
    cells = "".join(
        f'<div class="cell">{svg}<div class="num">{i + 1}</div></div>'
        for i, svg in enumerate(stills)
    )
    frame_phases = phases if phases is not None else [None] * len(frames)
    if len(frame_phases) != len(frames):
        raise ValueError("one player phase is required per frame")
    frame_active_units = (
        active_units if active_units is not None else [()] * len(frames)
    )
    if len(frame_active_units) != len(frames):
        raise ValueError("one active-unit set is required per frame")

    def player_frame(
        i: int, svg: str, phase: str | None, active: tuple[int, ...]
    ) -> str:
        phase_attr = f' data-phase="{phase}"' if phase else ""
        active_attr = " ".join(str(index) for index in active)
        return (
            f'<div class="frame{" on" if i == 0 else ""}"{phase_attr}'
            f' data-active-units="{active_attr}">{svg}</div>'
        )

    stage = "".join(
        player_frame(i, svg, phase, active)
        for i, (svg, phase, active) in enumerate(
            zip(frames, frame_phases, frame_active_units, strict=True)
        )
    )
    transcript_units = "".join(
        f'<span class="unit" id="transcript-unit-{index}" data-unit="{index}">'
        f"{html.escape(unit)}</span>"
        for index, unit in enumerate(units)
    )
    label_html = (
        f'<span class="display-label">{_html_text(display_label, "display_label")}</span>'
        if display_label is not None
        else ""
    )
    transcript = (
        f'<div class="transcript" aria-label="IPA transcript">{label_html}'
        f'<span class="ipa">{transcript_units}</span></div>'
    )
    last = max(len(frames) - 1, 0)
    script = (
        "(function(){var s=document.getElementById('stage');"
        "var f=s.querySelectorAll('.frame');var N=f.length;"
        "var r=document.getElementById('scrub');var b=document.getElementById('play');"
        "var c=document.getElementById('count');var i=0,t=null;"
        "var u=document.querySelectorAll('.transcript .unit');"
        "var MS=__MS__;"
        "function show(k){f[i].classList.remove('on');i=((k%N)+N)%N;"
        "f[i].classList.add('on');r.value=i;c.textContent=(i+1)+' / '+N;"
        "var a=f[i].dataset.activeUnits.split(' ');"
        "u.forEach(function(x){x.classList.toggle('active',a.indexOf(x.dataset.unit)>=0);});}"
        "r.addEventListener('input',function(){stop();show(+r.value);});"
        "function start(){if(t)return;t=setInterval(function(){show(i+1);},MS);"
        "b.textContent='Pause';}"
        "function stop(){clearInterval(t);t=null;b.textContent='Play';}"
        "b.addEventListener('click',function(){t?stop():start();});"
        "show(0);start();})();"
    ).replace("__MS__", str(ms_per_frame))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{word} — animated tract</title>
<style>{_literal_style()}{PLAYER_CSS}</style></head><body>
<div class="wrap">
<header><p class="eyebrow">ipakit · {name}</p>
<h1>Mid-sagittal tract, animated</h1>
<p style="margin-top:12px;color:var(--dim)">The word <b>{word}</b> as a
trajectory: {len(stills)} units on an ordinal clock, sampled to
{len(frames)} frames. Each frame is one blended posture projected through the
head — the same drawing a single phone gets, with no symbol read per frame.</p>
</header>

<section><h2>Filmstrip — one still per unit</h2>
<div class="filmstrip">{cells}</div></section>

<section><h2>Play</h2>
<div class="stage" id="stage">{stage}</div>
<div class="controls">
<button id="play" type="button">Play</button>
<input id="scrub" type="range" min="0" max="{last}" value="0" step="1"
aria-label="frame">
<span class="count" id="count">1 / {len(frames)}</span>
</div>
{transcript}
</section>
</div>
<script>{script}</script></body></html>"""


def animate(
    word: str | Trajectory,
    head_name: str | None = None,
    features: IPAFeatures | None = None,
    frames_per_unit: int = FRAMES_PER_UNIT,
    *,
    display_label: str | None = None,
) -> str:
    """A word as a played trajectory, drawn frame by frame.

    ``ipakit.tract.score`` reads the word into one :class:`~ipakit.tract.Posture`
    per segment; the timeline is sampled on a uniform ordinal clock at
    ``frames_per_unit`` frames per unit, so frame ``f`` between units ``i`` and
    ``i+1`` sits at ordinal ``t = i + f/frames_per_unit`` with no notion of
    duration -- one unit is one unit. Each ordinal is blended to a Posture by
    ``ipakit.tract.blend`` and projected through the head, and every frame goes
    through the same ``section_svg`` a still figure does, so a frame cannot
    drift from a drawing. The scale is fixed across frames from the whole
    sequence's extent. Playback maps the ordinal clock to milliseconds and is
    the only place time in seconds appears.

    The result is one self-contained page -- a filmstrip of the units and a
    flipbook player with an inline scrubber and autoplay -- with no runtime
    dependencies, readable in a browser without a rasterizer. The transcript
    highlights the spoken unit with the greatest Gaussian dominance on the
    trajectory's ordinal clock; at an exact transition midpoint both adjacent
    units are active. ``display_label`` may add caller-supplied orthography,
    but no orthographic label is inferred. Printable Unicode and LF are
    carried verbatim through HTML parsing; other C0 controls (including tab
    and CR), DEL, and C1 controls raise :class:`ValueError`.
    """
    ipa = features or IPAFeatures()
    name = (
        word.head_name
        if isinstance(word, Trajectory) and head_name is None
        else head_name if head_name is not None else head().name
    )
    h = head(name)
    marks = landmarks(ipa, h.name)
    track = (
        word
        if isinstance(word, Trajectory)
        else build_trajectory(
            word, head=h, frames_per_unit=frames_per_unit, features=ipa
        )
    )
    if track.head_name != h.name:
        raise ValueError(
            f"trajectory was built for head {track.head_name!r}, not {h.name!r}"
        )
    label = track.source
    word_units = track.postures
    rest_point = h.rest.point if h.rest is not None else None
    frame_postures = track.frames
    still_geoms = [build_geometry(h, marks, u) for u in word_units]
    frame_geoms = [build_geometry(h, marks, p) for p in frame_postures]

    # One extent over every still and every frame, so the scale is stable.
    extent = _extent(*still_geoms, *frame_geoms)
    stills = [
        section_svg(g, None, u.velic, _pose(u), None, None, extent=extent)
        for g, u in zip(still_geoms, word_units, strict=True)
    ]
    frames = [
        _frame_svg(g, p, extent)
        for g, p in zip(frame_geoms, frame_postures, strict=True)
    ]
    active_units = [track.dominant_unit_indices(t) for t in track.ordinals]
    # Hold the rest bookends a moment (one unit's worth of frames) at each end,
    # so the neutral start is unmistakable each time the flipbook loops.
    if rest_point is not None:
        hold = track.frames_per_unit
        frames = [frames[0]] * hold + frames + [frames[-1]] * hold
        active_units = (
            [active_units[0]] * hold + active_units + [active_units[-1]] * hold
        )
    ms = max(1, round(track.display_interval * 1000 / track.rate))
    return _player_page(
        label,
        name,
        frames,
        stills,
        ms,
        units=track.units,
        active_units=active_units,
        display_label=display_label,
    )


def animate_two_pane(
    word: str | Trajectory,
    head_name: str | None = None,
    features: IPAFeatures | None = None,
    frames_per_unit: int = FRAMES_PER_UNIT,
    *,
    display_label: str | None = None,
) -> str:
    """Sagittal and frontal projections of one Trajectory under one scrubber.

    The transcript uses that trajectory's ordinal clock and highlights the
    maximally dominant spoken unit. At an exact midpoint both adjacent units
    are active; synthetic rest ramps activate neither. ``display_label`` is
    shown verbatim as caller-supplied display text and is never inferred.
    Printable Unicode and LF are carried verbatim through HTML parsing; other
    C0 controls (including tab and CR), DEL, and C1 controls raise
    :class:`ValueError`.
    """
    ipa = features or IPAFeatures()
    name = (
        word.head_name
        if isinstance(word, Trajectory) and head_name is None
        else (head_name or head().name)
    )
    h = head(name)
    marks = landmarks(ipa, h.name)
    track = (
        word
        if isinstance(word, Trajectory)
        else build_trajectory(
            word, head=h, frames_per_unit=frames_per_unit, features=ipa
        )
    )
    if track.head_name != h.name:
        raise ValueError(
            f"trajectory was built for head {track.head_name!r}, not {h.name!r}"
        )
    player_postures = list(track.frames)
    phases: list[str | None] = [None] * len(player_postures)
    active_units = [track.dominant_unit_indices(t) for t in track.ordinals]
    if track.fps is not None and h.rest is not None:
        rest_pose = track.play_units[0]
        count = max(1, round(TIMED_PLAYER_REST_RAMP_SECONDS * track.fps))
        lead_in = [rest_pose] + [
            blend((rest_pose, track.frames[0]), k / count) for k in range(1, count)
        ]
        lead_out = [
            blend((track.frames[-1], rest_pose), k / count) for k in range(1, count)
        ] + [rest_pose]
        player_postures = lead_in + player_postures + lead_out
        phases = ["lead-in"] * len(lead_in) + phases + ["lead-out"] * len(lead_out)
        active_units = [()] * len(lead_in) + active_units + [()] * len(lead_out)

    side_stills = [build_geometry(h, marks, p) for p in track.postures]
    side_frames = [build_geometry(h, marks, p) for p in player_postures]
    front_stills = [build_frontal_geometry(h, marks, p) for p in track.postures]
    front_frames = [build_frontal_geometry(h, marks, p) for p in player_postures]
    side_extent = _extent(*side_stills, *side_frames)
    front_extent = _frontal_extent(*front_stills, *front_frames)

    def pair(s: str, f: str) -> str:
        return f'<div class="twopane"><div>{s}</div><div>{f}</div></div>'

    stills = [
        pair(
            section_svg(s, None, p.velic, _pose(p), extent=side_extent),
            frontal_svg(f, front_extent),
        )
        for s, f, p in zip(side_stills, front_stills, track.postures, strict=True)
    ]
    frames = [
        pair(_frame_svg(s, p, side_extent), frontal_svg(f, front_extent))
        for s, f, p in zip(side_frames, front_frames, player_postures, strict=True)
    ]
    if h.rest is not None and track.fps is None:
        hold = track.frames_per_unit
        frames = [frames[0]] * hold + frames + [frames[-1]] * hold
        phases = [phases[0]] * hold + phases + [phases[-1]] * hold
        active_units = (
            [active_units[0]] * hold + active_units + [active_units[-1]] * hold
        )
    ms = max(1, round(track.display_interval * 1000 / track.rate))
    page = _player_page(
        track.source,
        name,
        frames,
        stills,
        ms,
        phases,
        units=track.units,
        active_units=active_units,
        display_label=display_label,
    )
    return page.replace(_literal_style(), _literal_style() + FRONTAL_STYLE, 1).replace(
        "Mid-sagittal tract, animated", "One trajectory, sagittal + frontal"
    )


def cmd_draw(args: argparse.Namespace) -> int:  # noqa: C901
    prior: dict[str, Any] | None = None
    if args.compare:
        loaded = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        if args.head not in loaded:
            print(f"{args.compare} has no head {args.head!r}", file=sys.stderr)
            return 1
        prior = loaded[args.head]
    if args.head not in heads():
        print(
            f"no head {args.head!r}; have {', '.join(sorted(heads()))}", file=sys.stderr
        )
        return 1
    drawn = drawing(args.head, args.phone)
    current = drawn["geometry"]
    if str(args.output).endswith(".svg"):
        Path(args.output).write_text(render(drawn, prior), encoding="utf-8")
    else:
        Path(args.output).write_text(render_page(drawn, prior), encoding="utf-8")
    moved = 0
    if prior is not None:
        before = {p["arc"]: p["diameter"] for p in prior["midline"]}
        moved = sum(
            1
            for p in current["midline"]
            if p["arc"] not in before or abs(before[p["arc"]] - p["diameter"]) > 1e-9
        )
        note = f", {moved} midline point(s) differ"
    else:
        note = ""
    print(f"wrote {args.output}: {args.head}, {len(current['rows'])} samples{note}")
    return 0


def cmd_animate(args: argparse.Namespace) -> int:
    if args.head not in heads():
        print(
            f"no head {args.head!r}; have {', '.join(sorted(heads()))}", file=sys.stderr
        )
        return 1
    text = animate(args.word, args.head, frames_per_unit=args.frames_per_unit)
    Path(args.output).write_text(text, encoding="utf-8")
    print(f"wrote {args.output}: {args.head}, {args.word!r}")
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    out = {name: geometry(name) for name in sorted(heads())}
    Path(args.output).write_text(json.dumps(out), encoding="utf-8")
    print(f"wrote {args.output}: {', '.join(sorted(heads()))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_draw = sub.add_parser("draw", help="render a head to a standalone page")
    p_draw.add_argument("--head", default="adult-male")
    p_draw.add_argument("-o", "--output", default="tract.html")
    p_draw.add_argument("--compare", help="a dump from another revision, overlaid")
    p_draw.add_argument("--phone", help="open the velic port as this phone asks")
    p_draw.set_defaults(func=cmd_draw)

    p_anim = sub.add_parser("animate", help="draw a word as a played trajectory")
    p_anim.add_argument("word", help="the word to animate, in IPA")
    p_anim.add_argument("--head", default="adult-male")
    p_anim.add_argument("-o", "--output", default="tract-animation.html")
    p_anim.add_argument(
        "--frames-per-unit",
        type=int,
        default=FRAMES_PER_UNIT,
        help="how finely the ordinal timeline is sampled between units",
    )
    p_anim.set_defaults(func=cmd_animate)

    p_dump = sub.add_parser("dump", help="project every head to JSON, for --compare")
    p_dump.add_argument("-o", "--output", default="heads.json")
    p_dump.set_defaults(func=cmd_dump)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
