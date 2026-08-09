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
    traveled.

Distance uses these coordinates directly. A :class:`Head` projects them
to 2D for rendering only: phone identity does not depend on whose head
you imagine, and the shipped matrix must stay reproducible.

Two coordinates against the nine a posture takes (``docs/tract-anatomy.md``
7), so most of what a segment states is not in them. Rather than bend
``arc`` and ``offset`` to carry things they do not mean, three readers say
what *else* a drawing has to show, and each decides from the declarations
in ``ipa.xml`` rather than from a list here:

:func:`glottal_aperture`
    Voicing is glottal state, and the folds are declared to close about
    the tract axis, so ``offset`` cannot reach them. Read off the feature
    declared on the glottal-aperture axis, and off the projections onto
    it, which is how a coarser spelling still gets a position.
:func:`secondary_marks`
    A secondary articulation declares its own place, so it is a second
    constriction and genuinely drawable.
:func:`unmodelled`
    Everything else a segment states that this plane does not carry, with
    the reason it does not, so a renderer annotates instead of inventing.

None of them is read by ``ipakit.metric``, and none moves a distance.
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

#: The axis the vocal folds open along, and the one declaration
#: :func:`glottal_scale` reads. A quantity this module draws, named the
#: way ``+z`` is in :func:`unmodelled`; which feature measures it stays
#: the data's call.
GLOTTAL_AXIS = "+glottal-aperture"

#: The glottal aperture a unit that fixes no glottal state contributes to a
#: :func:`blend`. ``glottal`` is ``None`` where a bundle commits to nothing
#: about the folds, and a dominance mean cannot average a ``None``, so it is
#: resolved first to the neutral rest -- the folds standing open, the way a
#: tract sits between voiced gestures. 1.0 is fully abducted on the scale
#: :func:`glottal_aperture` reads (0 shut .. 1 as wide as the tract).
GLOTTAL_REST = 1.0


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
class Reading:
    """A posture, and which of the bundle's features went into it.

    ``read`` names the features whose stated value this call actually
    consumed -- not the features that *could* be postural. The two are not
    the same, and the difference is the whole reason this type exists:
    ``height`` declares tract coordinates, but a bundle stating a
    consonantal manner is read from ``place`` and ``manner`` and never
    looks at ``height``, so a stated height reaches nothing.

    :func:`unmodelled` asks this rather than asking whether a feature
    carries coordinates, so that what a drawing claims to show is what it
    was given.

    ``approximated`` names the features in ``read`` that supplied a
    coordinate they do not state. There is exactly one such reading and
    it is a vowel's: ``backness`` says where the tongue body *is*, and
    the branch takes it for the ``arc`` -- where the tongue body
    *constricts* -- when the segment states no
    ``constriction-location``. That stand-in is the whole of what
    [#123](https://github.com/lenzo-ka/ipakit/issues/123) is about, so
    a caller has to be able to tell a stated location from it without
    reading a source, and this is where the answer is. A stated location
    is in ``read`` and not in ``approximated``.
    """

    point: TractPoint
    read: frozenset[str]
    approximated: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Mark:
    """One thing a segment states that a sagittal posture cannot express.

    Voicing is glottal state, not posture; a release is a phase of the
    segment rather than a shape of it; laterality is the axis this plane
    projects away. Forcing any of them into ``arc`` and ``offset`` would
    misreport what the geometry means, so they are annotated instead --
    and ``kind`` records *why* the posture cannot carry it, read from the
    feature's own declaration rather than decided here.

    ``arc`` and ``offset`` are set only where the declaration puts the
    mark somewhere: a secondary articulation names its own place.
    """

    feature: str
    value: str
    label: str
    kind: str
    arc: float | None = None
    offset: float | None = None

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


def _pchip_slopes(ts: list[float], ys: list[float]) -> list[float]:
    """Fritsch-Carlson monotone-cubic tangents at each control point.

    A curve drawn with these tangents passes through every point and never
    overshoots between them -- the smooth-but-not-bulging read a hand- or
    measurement-placed outline wants. Used only for drawing.
    """
    n = len(ys)
    if n < 2:
        return [0.0] * n
    h = [ts[i + 1] - ts[i] for i in range(n - 1)]
    delta = [(ys[i + 1] - ys[i]) / h[i] if h[i] else 0.0 for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = delta[0], delta[-1]
    for i in range(1, n - 1):
        if delta[i - 1] * delta[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
    return m


@dataclass(frozen=True)
class Head:
    """A mid-sagittal geometry that projects tract space to 2D.

    ``midline`` and its diameters define tract aperture.  ``roof`` may
    independently declare the measured hard-palate outline: a palate vault
    apex is not necessarily the place where aperture is widest.
    """

    name: str
    midline: tuple[MidlinePoint, ...]
    roof: tuple[MidlinePoint, ...] = ()
    rest: RestPosture | None = None
    desc: str | None = None
    length_cm: float | None = None
    nasal: tuple[MidlinePoint, ...] = ()
    port_arc: float | None = None
    velum_thickness: float = 0.018
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
        # Monotone-cubic interpolation of the declared control points, so a
        # measured dip -- the alveolar ridge -- draws as an arc *through* the
        # points rather than straight segments meeting at a corner. Monotone
        # (Fritsch-Carlson) so it never overshoots a point, which would bulge a
        # wall past what was measured. Linear stays only where there is nothing
        # to curve (two points). Rendering only: distance reads arc/offset, not
        # this projection.
        arcs = [p.arc for p in pts]
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2

        def _cubic(values: list[float]) -> float:
            m = _pchip_slopes(arcs, values)
            return (
                h00 * values[index]
                + h10 * span * m[index]
                + h01 * values[index + 1]
                + h11 * span * m[index + 1]
            )

        x = _cubic([p.x for p in pts])
        y = _cubic([p.y for p in pts])
        diameter = _cubic([p.diameter for p in pts])
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
        than marking a point. The deformation is a raised cosine centered on
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
        # The taper brings the *resting* tongue to a point at each end, so the
        # body has a tip in front and an anchor behind. It must not pull down a
        # constriction: a tongue tip closing near the front of its span is
        # inside the taper, and scaling it there stops the articulator short of
        # the target it is supposed to be touching.
        if taper > 0.0:
            edge = min(arc - low, high - arc)
            rest *= min(1.0, max(edge, 0.0) / taper)
        distance = abs(arc - control.arc)
        if distance >= falloff:
            return rest
        weight = 0.5 * (1.0 + math.cos(math.pi * distance / falloff))
        return rest + (control.offset - rest) * weight

    def lip_body(
        self, closed: bool = False, close: float = 0.0
    ) -> tuple[tuple[tuple[float, float], ...], ...] | None:
        """Each lip as a body: root, shoulders and free edge.

        A lip is articulatory shape, not drawing style, so its form belongs
        here rather than in whatever draws it. Each is rooted in the bone
        that carries it -- maxilla above, mandible below -- and only the free
        edge travels, so a closing lip stretches from a fixed base. The two
        free edges meet at a point and do not pass it.

        Returns one tuple per lip, upper first, each ``(root_a, shoulder_a,
        tip, shoulder_b, root_b)`` in tract coordinates.
        """
        pair = self.lips(closed=closed, close=close)
        seats = self.lips(close=close)
        if pair is None or seats is None:
            return None
        (ux, uy), (lx, ly) = seats
        dx, dy = lx - ux, ly - uy
        span = math.hypot(dx, dy) or 1.0
        ax, ay = dx / span, dy / span  # down the aperture
        wx, wy = -ay, ax  # along the tract

        # Size the lip flesh from the *resting* aperture, a constant for the head,
        # so a raised jaw carries the lower lip without shrinking it -- only the
        # seat travels. Sizing off the live aperture made the lip shrink as the
        # mouth closed. Scaled per head, so any head keeps the proportions.
        resting = self.lips(close=0.0) or seats
        (rux, ruy), (rlx, rly) = resting
        ref = math.hypot(rlx - rux, rly - ruy) or 1.0
        reach, half, shoulder = ref * 0.18, ref * 0.10, ref * 0.09

        def one(
            seat: tuple[float, float], tip: tuple[float, float], out: float
        ) -> tuple[tuple[float, float], ...]:
            ox, oy = ax * out, ay * out
            root = (seat[0] + ox * reach, seat[1] + oy * reach)
            sh = (tip[0] + ox * shoulder, tip[1] + oy * shoulder)
            return (
                (root[0] - wx * half, root[1] - wy * half),
                (sh[0] - wx * half, sh[1] - wy * half),
                tip,
                (sh[0] + wx * half, sh[1] + wy * half),
                (root[0] + wx * half, root[1] + wy * half),
            )

        return (one(seats[0], pair[0], -1.0), one(seats[1], pair[1], 1.0))

    def median_body(
        self, arc: float, aperture: float
    ) -> tuple[tuple[tuple[float, float], ...], ...] | None:
        """The two edges of a median articulator, as bodies.

        ``ipa.xml`` declares the vocal folds ``aperture="median"``: they
        close toward each other about the tract axis rather than toward a
        wall the way a tongue closes toward a palate. ``offset`` measures
        travel from the midline to the wall and so cannot say where they
        are -- which is why the drawing had nothing to show for voicing.

        Both edges travel, symmetrically, and meet at the axis when the
        aperture is 0. They keep a body of their own at every aperture,
        because they are tissue and not a gap: an edge drawn flush with its
        wall at full abduction reads as a thicker wall and says nothing.
        What the aperture scales is the space *between* them. Like the
        lips, this is shape rather than style, so the form belongs here.

        Returns one tuple per edge, each ``(root_a, tip, root_b)`` in tract
        coordinates.
        """
        near = self.project(TractPoint(arc=arc, offset=0.0))
        far = self.project(TractPoint(arc=arc, offset=1.0))
        if near is None or far is None:
            return None
        dx, dy = far[0] - near[0], far[1] - near[1]
        span = math.hypot(dx, dy)
        if not span:
            return None
        ax, ay = dx / span, dy / span  # across the tract, near wall to far
        wx, wy = -ay, ax  # along the tract
        # Proportions of the tract's own span, so a head of any size keeps
        # them: each fold seats a fixed depth, and the aperture opens the
        # gap that is left between the two.
        seat, half = 0.16, span * 0.28
        gap = (1.0 - 2 * seat) * max(0.0, min(1.0, aperture))
        travel = span * (1.0 - gap) / 2

        def one(
            root: tuple[float, float], sign: float
        ) -> tuple[tuple[float, float], ...]:
            tip = (root[0] + ax * travel * sign, root[1] + ay * travel * sign)
            return (
                (root[0] - wx * half, root[1] - wy * half),
                tip,
                (root[0] + wx * half, root[1] + wy * half),
            )

        return (one(near, 1.0), one(far, -1.0))

    def tongue_point(
        self,
        arc: float,
        control: TractPoint | Sequence[TractPoint],
        close: float = 0.0,
    ) -> tuple[float, float] | None:
        """Where the tongue surface sits at ``arc``, jaw included.

        ``offset`` is a fraction from the floor to the wall, so the jaw moves
        the floor it is measured from rather than displacing the result. Added
        to an absolute position instead, a closure already touching the wall
        is pushed through it -- which is how the tongue escaped the roof on a
        click, where a front closure comes with a half-closed jaw.
        """
        controls = [control] if isinstance(control, TractPoint) else list(control)
        # A segment may hold more than one constriction -- a click closes at
        # the front and at the velum -- so the surface takes whichever reaches
        # highest at this arc, giving it a hump per closure.
        offsets = [
            value
            for value in (self.tongue_offset(arc, one) for one in controls)
            if value is not None
        ]
        if not offsets:
            return None
        offset = max(offsets)
        floor = self.project(TractPoint(arc=arc, offset=0.0))
        wall = self.project(TractPoint(arc=arc, offset=1.0))
        if floor is None or wall is None:
            return None
        floor = self.carried(floor, arc, close)
        return (
            floor[0] + (wall[0] - floor[0]) * offset,
            floor[1] + (wall[1] - floor[1]) * offset,
        )

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
        traveling the whole way alone.
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
        # They meet at the occlusal line rather than at a fraction someone
        # chose: with the jaw shut the incisal edges are close to meeting, and
        # the lips close across that level. Taking the teeth as the anchor
        # keeps the closure where the anatomy puts it for any head.
        edges = [
            self.carried((x, y), 0.03, close if carrier == "mandible" else 0.0)
            for name, x, y, carrier in self.teeth
            if name.endswith("incisal-edge")
        ]
        along = 0.72
        if len(edges) == 2:
            mid = ((edges[0][0] + edges[1][0]) / 2, (edges[0][1] + edges[1][1]) / 2)
            ax, ay = upper[0] - lower[0], upper[1] - lower[1]
            length = ax * ax + ay * ay
            if length:
                along = ((mid[0] - lower[0]) * ax + (mid[1] - lower[1]) * ay) / length
                along = max(0.0, min(1.0, along))
        meet = (
            lower[0] + (upper[0] - lower[0]) * along,
            lower[1] + (upper[1] - lower[1]) * along,
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
        carries the position from the midline toward the wall.  Along a
        declared hard-palate roof it interpolates directly to that measured
        outline. Elsewhere local diameter scales travel along the midline's
        normal. This keeps aperture and roof shape distinct: their peaks are
        different anatomical landmarks.
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
        offset = point.offset or 0.0
        if self.roof and self.roof[0].arc <= arc <= self.roof[-1].arc:
            roof = self._project_along(self.roof, arc, 0.0)
            if roof is not None:
                return (x + (roof[0] - x) * offset, y + (roof[1] - y) * offset)
        travel = offset * diameter
        return (x + nx * travel, y + ny * travel)

    # -- notebook display -----------------------------------------------------

    def _repr_svg_(self) -> str:
        """The reference drawing, when a notebook shows this head.

        Every landmark this head declares, at its rest posture -- one
        posture, so one figure, which is the rule the display hooks in
        this library follow. ``heads.xml`` was the only part of the
        library whose output is a picture and the only part with no way
        to see one; this is the shortest way to see one.

        The import is deferred so that the dependency runs one way only:
        the renderer reads this module, this module never reads the
        renderer, and ``ipakit.metric`` -- which reads this module --
        cannot reach a stylesheet through it.
        """
        from .tract_svg import figure

        return figure(None, self.name)


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
        roof_elem = elem.find("roof")
        roof_points: tuple[MidlinePoint, ...] = ()
        if roof_elem is not None:
            roof_points = tuple(
                MidlinePoint(
                    arc=float(pt.get("arc", 0.0)),
                    x=float(pt.get("x", 0.0)),
                    y=float(pt.get("y", 0.0)),
                    diameter=0.0,
                    provenance=pt.get("provenance", "hand-placed"),
                )
                for pt in roof_elem.findall("point")
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
        velum_elem = elem.find("velum")
        velum_thickness = (
            float(velum_elem.get("thickness", 0.018))
            if velum_elem is not None
            else 0.018
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
            roof=tuple(sorted(roof_points, key=lambda p: p.arc)),
            rest=rest,
            desc=elem.get("desc"),
            length_cm=float(length) if length else None,
            nasal=nasal_points,
            port_arc=port_arc,
            velum_thickness=velum_thickness,
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
    caller. The renderer (now ``ipakit.tract_svg``) did restate it and
    drifted while it lived under ``scripts/`` -- it marked
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


@dataclass(frozen=True)
class Posture:
    """What one phone contributes to a drawing, before any head projects it.

    A figure is symbol -> vector -> geometry. This is the vector: everything
    :func:`ipakit.tract_svg.build_geometry` needs that the *symbol* fixes
    rather than the head -- the primary reading, the closures the segment is
    made of, the velic and glottal apertures, and the marks a sagittal
    posture cannot carry. Separating it out is what lets animation be
    interpolation of the numbers, projected per frame.

    ``reading`` is ``None`` for the reference drawing, which poses nothing and
    names every landmark; a phone always has one, and an unplaced reading
    (silence) falls back to ``rest``, the head's home posture. ``velic`` and
    ``glottal`` keep the shapes the readers return -- a float and a
    ``float | None`` -- so nothing about what counts as nasal or voiced moves
    here.
    """

    reading: TractPoint | None
    rest: TractPoint | None
    constrictions: tuple[TractPoint, ...]
    velic: float
    glottal: float | None
    secondary: tuple[Mark, ...]
    unmodelled: tuple[Mark, ...]


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


def constrictions(
    features: IPAFeatures, bundle: dict[str, str]
) -> tuple[TractPoint, ...]:
    """Every constriction the segment makes, not only its named one.

    ``tract_point`` answers with one place because that is what a per-feature
    comparison needs, and the metric reads it. Some segments make two at
    once, and a drawing that shows one of them shows the wrong sound:

    * a **click** closes at its named place *and* at the velum, and rarefies
      the pocket between. Drawn with the front closure alone it is an
      ordinary stop wearing a velaric label.
    * a **combining place** is two places by definition. ``bilabial^velar``
      declares no arc of its own precisely because its position is its
      components', so ``w`` had nowhere to be drawn at all.

    Returned front to back, and every element is a constriction the segment
    actually makes. That is not ``tract_point``'s answer with company added.
    A segment naming one place constricts there, so the metric's point is the
    front-most element; a combining place declares no arc of its own and the
    metric answers with the mean of its components, which lies strictly
    between them and so is a constriction at neither. ``w`` is drawn closing
    at the lips and at the velum, and compared at 0.225, where nothing closes.

    Ask ``tract_point`` for the summary the metric uses and this for the
    closures a drawing owes. They answer different questions, and only a
    single named place makes them agree.
    """
    primary = tract_point(features, bundle)
    place = features.features.get("place")
    if place is None or primary.arc is None:
        return (primary,)

    def at(value: str, offset: float) -> TractPoint | None:
        arc = place.coordinates.get(value, {}).get("arc")
        if arc is None:
            return None
        return TractPoint(
            arc=arc,
            offset=offset,
            articulator=place.articulators.get(value),
        )

    named = bundle.get("place") or ""
    extra: list[TractPoint] = []

    # A combining place is its components, each making the constriction.
    if Feature.COMBINER in named:
        parts = [at(v, primary.offset or 1.0) for v in named.split(Feature.COMBINER)]
        found = [q for q in parts if q is not None]
        if found:
            return tuple(sorted(found, key=lambda q: q.arc or 0.0))

    # A click holds a velar closure behind whatever it names.
    if bundle.get("airstream") == "velaric":
        back = at("velar", 1.0)
        if back is not None and abs((back.arc or 0.0) - primary.arc) > 1e-9:
            extra.append(back)

    return tuple(sorted((primary, *extra), key=lambda q: q.arc or 0.0))


def glottal_scale(features: IPAFeatures) -> Feature | None:
    """The feature that measures how far the folds stand apart.

    Asked of the axis, because that is where the answer is written:
    ``phonation`` declares ``axis="+glottal-aperture"`` in ``ipa.xml``,
    and an inventory that measures the folds with some other feature says
    so the same way. The axis is spelled here for the reason
    :func:`unmodelled` spells ``+z``: it names the quantity this module
    computes, not a phonetic fact the data owns.

    One feature declares it, or none. Two would leave the choice between
    them to this function, which is the whole defect an axis avoids, so
    two is refused rather than resolved. An axis nothing declares, or one
    declared by a feature whose values are not an ordinal scale, leaves
    nothing to read a position off: the folds are then drawn with no
    state, the same way an inventory declaring no median aperture draws
    no folds at all.
    """
    on_axis = sorted(
        (f for f in features.features.values() if f.axis == GLOTTAL_AXIS),
        key=lambda f: f.name,
    )
    if len(on_axis) > 1:
        raise ValueError(
            f"features {[f.name for f in on_axis]} all declare "
            f"axis={GLOTTAL_AXIS!r}; the folds stand at one aperture, so one "
            "feature measures it and a second makes the choice arbitrary"
        )
    scale = on_axis[0] if on_axis else None
    if scale is None or not scale.is_ordinal or len(scale.values) < 2:
        return None
    return scale


def glottal_aperture(features: IPAFeatures, bundle: dict[str, str]) -> float | None:
    """How far the vocal folds stand apart -- 0 shut, 1 as wide as the tract.

    The one candidate the posture cannot reach even in principle. The folds
    are declared ``aperture="median"``, so they close about the tract axis
    and ``offset`` -- travel from the midline toward a wall -- has nothing
    to say about them. Voicing was therefore a word in the margin and not
    a difference in the picture.

    What can say it is already declared. The scale is
    :func:`glottal_scale`, the feature on the glottal-aperture axis, and
    its values ascend along that axis from creaky to devoiced, so a bundle
    stating one sits where that value sits. ``voiced`` is the same axis
    read two ways instead of four, which is what the ``<projection>`` in
    ``ipa.xml`` says, so a bundle stating only ``voiced`` sits at the
    center of the values that read that way -- as far as the coarse
    spelling commits. Only projections onto the scale are read: a
    projection between two other features says nothing about the folds.

    A complete closure at the folds overrides both: a glottal stop shuts
    them whatever the phonation says, and it is the one segment whose own
    constriction is theirs. Returns None when the bundle fixes no glottal
    state at all.
    """
    scale = glottal_scale(features)
    if scale is None:
        return None
    order = list(scale.values)

    def position(value: str) -> float:
        return order.index(value) / (len(order) - 1)

    point = tract_point(features, bundle)
    organ = features.features.get("articulator")
    apertures = organ.apertures if organ is not None else {}
    if (
        point.offset is not None
        and point.offset >= 0.995
        and apertures.get(point.articulator or "") == "median"
    ):
        return 0.0
    stated = bundle.get(scale.name)
    if stated in order:
        return position(str(stated))
    narrows = [
        position(value)
        for (fine, value), (coarse, reads) in features.projections.items()
        if fine == scale.name and bundle.get(coarse) == reads
    ]
    return sum(narrows) / len(narrows) if narrows else None


def secondary_marks(features: IPAFeatures, bundle: dict[str, str]) -> tuple[Mark, ...]:
    """The lesser constrictions a segment states, front to back.

    A secondary articulation adds a constriction and keeps the primary, and
    it declares where: ``velarized`` carries ``place="velar"``, and
    ``IPAFeatures.secondary_places`` is that declaration read back -- the
    same one the mode partition and the metric's place table read, so none
    of them can disagree about what a secondary is or where it sits.

    Its degree is not declared, because it is not free: a secondary
    articulation is of approximant degree, or it would be the primary. That
    number is read off the manner scale rather than chosen here.

    This is the one candidate on the annotation list that is genuinely
    drawable in this plane -- it has a place and a degree like any other
    constriction -- so it is drawn rather than annotated. It is drawn
    lighter than the primary because it is lesser, not because it is less
    certain. It stays out of :func:`constrictions`, whose members are the
    closures the segment is *made of*: putting it there would deform the
    tongue body identically to a primary constriction of the same degree,
    which claims more than the phone declares.
    """
    place = features.features.get("place")
    manner = features.features.get("manner")
    if place is None or manner is None:
        return ()
    degree = manner.coordinates.get("approximant", {}).get("offset")
    if degree is None:
        return ()
    out: list[Mark] = []
    for name, target in features.secondary_places.items():
        if bundle.get(name) != "+":
            continue
        feat = features.features.get(name)
        label = (feat.labels.get("+") if feat is not None else None) or name
        # A combining place is two places by definition, so a labial-palatal
        # states one feature and makes two constrictions.
        for component in place.expand(target):
            arc = place.coordinates.get(component, {}).get("arc")
            if arc is not None:
                out.append(
                    Mark(
                        feature=name,
                        value="+",
                        label=label,
                        kind="secondary",
                        arc=arc,
                        offset=degree,
                    )
                )
    return tuple(sorted(out, key=lambda m: m.arc or 0.0))


def unmodelled(features: IPAFeatures, stated: dict[str, str]) -> tuple[Mark, ...]:
    """What a segment states that this plane's posture does not carry.

    ``stated`` is what the segment itself says -- ``get_features`` with
    ``with_defaults=False`` -- because a default is what an unmarked
    segment already reports and annotating it would say nothing.

    Which features are already drawn is derived, not listed, so a feature
    added to ``ipa.xml`` is annotated without a code change here:

    * a feature :func:`tract_reading` **read for this bundle** is the
      drawing already, *unless* it was read for a coordinate it does not
      state. The question is what this call consumed, not what the
      feature could have supplied: ``height`` declares coordinates and is
      the offset of a vowel, and beside a consonantal manner it is read
      by nothing. Asking whether the *feature* carries coordinates
      answered for every bundle at once, so a posture that dropped a
      stated value reported nothing missing and certified itself
      complete;
    * a ``(feature, value)`` a bridge gives a ``port`` to is drawn as the
      velum, by :func:`velic_aperture`;
    * glottal state is drawn as the folds, by :func:`glottal_aperture`;
    * a ``mode="secondary"`` feature is drawn as a lesser constriction, by
      :func:`secondary_points`;
    * a ``mode="structural"`` feature is not a property of a sound at all
      -- a tie joins two units, it does not shape one.

    What is left is stated and invisible, and the same declarations say
    *why*, which is what ``Mark.kind`` carries: ``offscale`` is a value
    declared to hold no position on its own axis (silence is not a degree
    of constriction), a postural feature the reading did not take is
    ``unread`` -- the posture went to another feature for that
    coordinate, which is the only honest thing to say about a bundle
    stating two postures at once -- ``axis="+z"`` is the axis a
    mid-sagittal section projects away (the feature's own ``desc`` says
    so), ``mode="release"`` is a phase of the segment rather than a posture
    of it, ``mode="prosodic"`` belongs to the unit rather than to the
    articulation, and ``approximate`` is a coordinate taken from a
    feature that states something else. Anything else is simply not in
    the model -- rounding is lip protrusion, which
    ``docs/tract-anatomy.md`` 4.4 specifies and this geometry does not
    implement. None of them gets a contour invented for it.

    ``approximate`` is the one kind that names a feature the posture
    *did* draw, and it is the reason this call has to ask the reading
    rather than the declaration twice over. A vowel stating no
    ``constriction-location`` still gets an ``arc``, from ``backness``,
    which says where the tongue body is and not where it constricts. A
    mark naming ``backness`` is what lets a caller tell that arc from a
    stated one, and it is a mark rather than a note beside the figure
    because ``docs/design/tract-validation.md`` 4 measured the note and
    found it insufficient: the rhotic is drawn 0.22 of a tract from
    where it was measured, with an annotation saying that something is
    missing, and a reader has no way to know which number the annotation
    is about.
    """
    scale = glottal_scale(features)
    glottal: set[str] = set()
    if scale is not None:
        glottal = {scale.name} | {
            coarse
            for (fine, _), (coarse, _) in features.projections.items()
            if fine == scale.name
        }
    ported = {pair for ports in features.bridge_apertures.values() for pair in ports}
    reading = tract_reading(features, stated)
    read, approximated = reading.read, reading.approximated
    out: list[Mark] = []
    for name, feat in features.features.items():
        value = stated.get(name)
        if value is None or value == feat.default:
            continue
        if name not in approximated and (
            name in read or name in glottal or name in features.secondary_places
        ):
            continue
        if (name, value) in ported or feat.mode == "structural":
            continue
        if name in approximated:
            kind = "approximate"
        elif feat.value_aliases.get(value, value) in feat.offscale:
            kind = "off scale"
        elif feat.coordinates:
            kind = "unread"
        elif feat.axis == "+z":
            kind = "out of plane"
        elif feat.mode == "release":
            kind = "phase"
        elif feat.mode == "prosodic":
            kind = "prosodic"
        else:
            kind = "unmodelled"
        out.append(
            Mark(
                feature=name,
                value=value,
                label=feat.labels.get(value) or f"{name} {value}",
                kind=kind,
            )
        )
    return tuple(out)


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
    arc from the constriction location they state, or from backness where
    they state none, and offset from height. The articulator comes from
    the bundle when a phone or diacritic states one (a linguolabial says
    tongue-tip explicitly), otherwise from the place's declared default.
    Unplaceable bundles (no manner, an off-scale manner like silence)
    yield an unplaced point.

    The point alone does not say which of the bundle's features it came
    from, and a bundle may state more than this reading takes: see
    :func:`tract_reading`, which answers both.
    """
    return tract_reading(features, bundle).point


def tract_reading(features: IPAFeatures, bundle: dict[str, str]) -> Reading:
    """:func:`tract_point`, and the features it read to get there.

    The posture is one arc and one offset, so at most one feature
    supplies each -- and which one depends on the bundle. A stated
    ``height`` is the offset of a vowel and nothing at all beside a
    consonantal manner; a stated ``place`` is the arc of a consonant and
    nothing at all beside ``manner="vowel"``. Both are reachable: a rule
    setting ``manner`` over a vowel produces exactly such a bundle.

    A vowel has two features that can supply its arc, and takes the more
    specific one. ``constriction-location`` says where the tongue body
    constricts, and ``backness`` says where the tongue body is, which the
    vowel branch read *as* the constriction for want of anything else --
    so every vowel agreeing on ``backness`` sat at one point whatever
    else it stated. A segment stating a location is read at that
    location, and ``backness`` is then not read at all: the posture is
    one arc, so the feature that did not supply it is reported as
    ``unread`` like any other value the picture did not take.

    Where no location is stated the fallback still runs, and the arc it
    produces is reported in ``approximated``. Some of the shipped vowels
    state a location and the rest do not, so both readings are
    live and a caller cannot tell them apart from the number: the arc is
    a float either way. The alternative -- leaving an unclassified vowel
    unplaced -- is not silence in this library, because
    :func:`ipakit.metric.bundle_distance` scores a coordinate one side
    has against one the other lacks as the maximal difference and two
    absences as no difference at all. Dropping schwa's arc would
    therefore assert that schwa is as far from ``ɛ`` as any two vowels
    can be on that axis, and identical to ``ɜ`` on it. Reporting the
    approximation withholds the claim the number does not support;
    withholding the number makes two claims the sources do not support
    either.

    A name lands in ``read`` where this call took its stated value and
    got something back -- an arc, an offset, an articulator, or the
    branch itself. Recording it here rather than restating the branch in
    :func:`unmodelled` is what keeps the two from disagreeing about what
    the picture holds.

    Whichever feature supplies the ``arc`` is the one asked for the
    ``articulator``, and the only one. They are two halves of one
    statement about one constriction -- where it is, and what makes it --
    so a point taking its position from ``backness`` and its organ from a
    location that could not supply a position would describe no gesture,
    and would report nothing amiss, because taking the organ is what puts
    a name in ``read``. A stated ``articulator`` is the exception and
    wins over both.
    """
    arc: float | None = None
    offset: float | None = None
    read: set[str] = set()
    approximated: set[str] = set()

    def resolve(feature: str) -> str | None:
        """The value the bundle states, under the name the data declares."""
        feat = features.features.get(feature)
        value = bundle.get(feature)
        if feat is None or value is None:
            return value
        return feat.value_aliases.get(value, value)

    # None of the four lookups below touches ``read``. They are asked
    # speculatively -- the vowel branch asks the stated location for an arc
    # and takes ``backness`` when it has none -- and a lookup that records
    # the asking cannot tell a source that won from one that was tried and
    # rejected. Each branch commits the names of the sources it took.
    def value_attr(feature: str, value: str | None, attr: str) -> float | None:
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        return feat.coordinates.get(feat.value_aliases.get(value, value), {}).get(attr)

    articulator = bundle.get("articulator")
    if articulator is not None:
        # A stated articulator wins over the derived one on either branch,
        # so stating it is always reading it.
        read.add("articulator")

    def articulator_for(feature: str, value: str | None) -> str | None:
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        return feat.articulators.get(feat.value_aliases.get(value, value))

    # Resolved through the aliases the same way every other value is: the
    # branch is a read of the manner the bundle states, and an inventory
    # spelling that manner by an alias takes the same branch.
    manner = resolve("manner")

    def combined_attr(feature: str, value: str | None, attr: str) -> float | None:
        """The mean of the components' positions.

        A combining value sits at its components' center of gravity --
        the fusion's balance point in the tract, where ``w`` falls
        between the lips and the velum. A single value expands to itself,
        so this is the ordinary read as well as the combined one, and
        every axis takes it: a simultaneous fusion spells a combination
        on whichever feature its constituents disagree about, so
        ``front^back`` is a position for the same reason
        ``bilabial^velar`` is.

        All the components or none. A mean over the subset that happens
        to carry the coordinate is not the stated value's position, it is
        another value's -- ``palatal^X`` with ``X`` unplaceable would come
        back as plain ``palatal``, and come back as a *complete* answer,
        so nothing downstream could tell it from a vowel that stated
        ``palatal``. A fusion the model can only half place is one it
        cannot place, and returning None here is what lets the caller
        fall back and say so.
        """
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        found = [value_attr(feature, comp, attr) for comp in feat.expand(value)]
        if not found or any(a is None for a in found):
            return None
        return sum(found) / len(found)  # type: ignore[arg-type]

    def combined_articulator(feature: str, value: str | None) -> str | None:
        """Every organ the components move, in the combining spelling.

        A labial-velar moves the lower lip AND the dorsum. (The gestural
        model makes these two gestures; see docs/gestural-model.md.)
        """
        if value is None:
            return None
        feat = features.features.get(feature)
        if feat is None:
            return None
        organs: list[str] = []
        for comp in feat.expand(value):
            organ = articulator_for(feature, comp)
            if organ is not None and organ not in organs:
                organs.append(organ)
        # The combiner, not a literal "+": this spelling is read back
        # through Feature.expand.
        return Feature.COMBINER.join(organs) if organs else None

    def place_the_point(*candidates: tuple[str, str | None]) -> str | None:
        """The first candidate that supplies the arc, committed whole.

        ``arc`` and ``articulator`` are one statement about one
        constriction -- where it is and what makes it -- so they come
        from one feature or the point is a chimera: a position from
        ``backness`` wearing the organ of a location that could not
        supply a position. Whichever candidate answers first is the one
        put in ``read`` and the only one asked for an organ; the rest
        were tried and are unread like any other stated value the
        picture did not take.
        """
        nonlocal arc, articulator
        for feature, value in candidates:
            arc = combined_attr(feature, value, "arc")
            if arc is None:
                continue
            read.add(feature)
            if articulator is None:
                articulator = combined_articulator(feature, value)
            return feature
        return None

    if manner == "vowel":
        read.add("manner")
        # The stated constriction first, `backness` where none is stated.
        # Asking for the arc is what decides it: a location the data gives
        # no `arc` supplies nothing, and the fallback is then the same read
        # a vowel has always had, rather than an unplaced point.
        took = place_the_point(
            ("constriction-location", bundle.get("constriction-location")),
            ("backness", bundle.get("backness")),
        )
        if took == "backness":
            approximated.add("backness")
        offset = combined_attr("height", bundle.get("height"), "offset")
        if offset is not None:
            read.add("height")
    else:
        place_the_point(("place", bundle.get("place")))
        offset = value_attr("manner", manner, "offset")
        if offset is not None:
            read.add("manner")
    return Reading(
        point=TractPoint(arc=arc, offset=offset, articulator=articulator),
        read=frozenset(read),
        approximated=frozenset(approximated),
    )


def posture(
    features: IPAFeatures, phone: str | None, head_shape: Head | None = None
) -> Posture:
    """The symbol -> vector step of a drawing: read a phone into a Posture.

    Everything a figure needs from the segment, computed once and in one
    place: the primary reading, the closures, the two apertures and the
    marks. Projecting the vector to geometry is the head's job and stays in
    :func:`ipakit.tract_svg.build_geometry`, so this may read the symbol and
    that may not.

    ``phone`` is ``None`` for the reference drawing, whose reading is ``None``
    and which carries no closures. A phone whose bundle places nowhere
    (silence) still has a reading -- an unplaced one -- and takes ``rest``, the
    home posture ``head_shape`` declares, so the fallback follows the head the
    figure is drawn on rather than a default. ``head_shape`` defaults to the
    shipped default head.
    """
    if phone is None:
        return Posture(
            reading=None,
            rest=None,
            constrictions=(),
            velic=0.0,
            glottal=None,
            secondary=(),
            unmodelled=(),
        )
    h = head_shape if head_shape is not None else head()
    bundle = features.get_features(phone)
    stated = features.get_features(phone, with_defaults=False)
    return Posture(
        reading=tract_point(features, bundle),
        rest=h.rest.point if h.rest is not None else None,
        constrictions=constrictions(features, bundle),
        velic=velic_aperture(features, bundle),
        glottal=glottal_aperture(features, bundle),
        secondary=secondary_marks(features, bundle),
        unmodelled=unmodelled(features, stated),
    )


def score(features: IPAFeatures, word: str) -> tuple[Posture, ...]:
    """A word as one :class:`Posture` per segment, in order.

    The symbol -> vector step over a whole transcription: tokenize with the
    inventory's own tokenizer -- the same split :func:`ipakit.tokenize` and
    the metric use, so ties and diacritics bind into single units the way
    they do everywhere else -- and read each unit through :func:`posture`. A
    dictionary pronunciation in plain IPA (``"kat"``, ``"aki"``) goes
    straight through as its segments.

    The result is what :func:`blend` interpolates. Every posture is read on
    the shipped default head, because that is the head :func:`posture`
    poses on; a caller drawing on another head reads its rest through
    :func:`blend`'s own output, which carries a ``rest`` for silence.
    """
    return tuple(posture(features, unit) for unit in features.tokenize(word))


def blend(units: Sequence[Posture], t: float, falloff: float = 0.5) -> Posture:
    """The interpolated posture at ordinal time ``t`` across ``units``.

    ``t`` runs 0..N-1 over N units, one integer per unit. The blend is by
    dominance functions (Cohen & Massaro 1993), **per articulator**: each
    articulator keeps its own fixed place and only its constriction *degree*
    is interpolated, so nothing slides a closure through the palate. Sliding
    one primary point from alveolar 0.13 to velar 0.45 would draw a tract no
    tongue makes -- a closure travelling across the hard palate -- which is
    exactly the trap this avoids.

    The dominance of unit ``i`` at ``t`` is a peaked Gaussian,
    ``w_i = exp(-((t - i) / falloff) ** 2)``: 1 at its own moment and falling
    away on either side, so a smaller ``falloff`` makes each unit reign more
    sharply over its own instant. At an integer ``t`` the owning unit's weight
    is 1 and its neighbours' is ``exp(-(1/falloff)**2)`` -- with the default
    ``falloff`` a couple of percent -- so ``blend(units, i)`` is unit ``i``
    to within that leak.

    Every articulator any unit constricts is collected. A unit closes the
    articulators it names (its ``constrictions``) and leaves the rest at the
    head's resting offset -- the tongue at the floor, not constricting. Each
    articulator's degree at ``t`` is the dominance-weighted mean of those
    per-unit targets, taken at the articulator's OWN arc (itself the
    dominance-weighted mean of the arcs the constricting units place it at, so
    a place shared by two units settles between them and never leaves the
    articulator). An articulator whose blended degree remains imperceptibly
    close to rest is not emitted; a below-rest gesture such as a lowered
    vowel root remains a real control. The survivors are the blended
    ``constrictions``, each ``(fixed arc, blended offset, articulator)`` --
    which :func:`ipakit.tract_svg.build_geometry` renders as-is, because
    ``Head.tongue_point`` already takes the max over controls and so draws a
    hump per active articulator.

    ``velic`` and ``glottal`` blend as scalars. ``glottal`` is resolved to
    :data:`GLOTTAL_REST` wherever a unit fixed none, so the mean never runs
    through ``None``; ``velic`` is already a float resting at 0 (sealed).
    ``reading`` -- the primary point the renderer derives jaw close from --
    is the dominance-weighted mean of the units' readings; it drives no
    tongue closure, so blending its arc is jaw motion, not a sliding
    constriction. The annotations (``secondary``, ``unmodelled``) and the
    silence ``rest`` follow the single dominant unit rather than
    interpolating, being labels on a frame and not quantities of it.
    """
    if not units:
        raise ValueError("blend needs at least one unit")
    if falloff <= 0.0:
        raise ValueError("falloff must be positive")

    weights = [math.exp(-(((t - i) / falloff) ** 2)) for i in range(len(units))]
    total = sum(weights) or 1.0
    dominant = units[max(range(len(units)), key=lambda i: weights[i])]

    rest_offset = next(
        (
            u.rest.offset
            for u in units
            if u.rest is not None and u.rest.offset is not None
        ),
        0.0,
    )

    def weighted(values: Sequence[tuple[float, float]]) -> float | None:
        """Dominance-weighted mean of (weight, value) pairs, or None if empty."""
        denom = sum(w for w, _ in values)
        if denom <= 0.0:
            return None
        return sum(w * v for w, v in values) / denom

    # Each unit's per-articulator target: the offset it constricts that
    # articulator to (max where a unit closes one twice, as a click does),
    # keyed by name so a place travels only between a unit's own closures.
    names: list[str] = []
    per_unit: list[dict[str, TractPoint]] = []
    for u in units:
        closed: dict[str, TractPoint] = {}
        for q in u.constrictions:
            if q.articulator is None or q.arc is None or q.offset is None:
                continue
            prior = closed.get(q.articulator)
            if prior is None or (prior.offset or 0.0) < q.offset:
                closed[q.articulator] = q
            if q.articulator not in names:
                names.append(q.articulator)
        per_unit.append(closed)

    blended: list[TractPoint] = []
    for name in names:
        arc = weighted(
            [
                (weights[i], closed[name].arc)  # type: ignore[misc]
                for i, closed in enumerate(per_unit)
                if name in closed
            ]
        )
        # Degree is dominance *activation* away from rest, not a mean that counts
        # every non-constricting unit as a vote for rest. Each constricting
        # unit lifts the degree toward its own target by its dominance weight,
        # so at a unit's own moment (weight 1) its closure is reached in full --
        # a stop reads as closed, not as a near-closure ring -- while away from
        # it the lift decays and the articulator relaxes to rest. Overlapping
        # closures on one articulator sum, capped at full closure.
        # A Gaussian is positive at every finite distance.  Treating that
        # mathematical tail as an active gesture emitted near-rest controls
        # from segments several units away.  Besides drawing a flash at a
        # rest bookend, a ghost tongue-tip changes the surface's anterior
        # clamp.  Below this activation the gesture is geometrically absent.
        active = [
            i
            for i, closed in enumerate(per_unit)
            if name in closed and weights[i] >= 1e-6
        ]
        lift = sum(
            weights[i] * ((per_unit[i][name].offset or 0.0) - rest_offset)
            for i in active
        )
        offset = max(0.0, min(1.0, rest_offset + lift))
        # Below-rest vowel gestures are real too (for example /a/'s lowered
        # tongue root). Keep either direction, while discarding the tiny
        # remote tail which has no visible or articulatory meaning.
        if arc is None or abs(offset - rest_offset) < 0.02:
            continue
        blended.append(TractPoint(arc=arc, offset=offset, articulator=name))
    blended.sort(key=lambda q: q.arc or 0.0)

    reading_arc = weighted(
        [
            (weights[i], u.reading.arc)
            for i, u in enumerate(units)
            if u.reading is not None and u.reading.arc is not None
        ]
    )
    reading_offset = weighted(
        [
            (weights[i], u.reading.offset)
            for i, u in enumerate(units)
            if u.reading is not None and u.reading.offset is not None
        ]
    )
    reading = (
        TractPoint(
            arc=reading_arc,
            offset=reading_offset,
            articulator=(
                dominant.reading.articulator if dominant.reading is not None else None
            ),
        )
        if reading_arc is not None or reading_offset is not None
        else dominant.reading
    )

    velic = sum(weights[i] * u.velic for i, u in enumerate(units)) / total
    glottal = (
        sum(
            weights[i] * (GLOTTAL_REST if u.glottal is None else u.glottal)
            for i, u in enumerate(units)
        )
        / total
    )

    return Posture(
        reading=reading,
        rest=dominant.rest,
        constrictions=tuple(blended),
        velic=velic,
        glottal=glottal,
        secondary=dominant.secondary,
        unmodelled=dominant.unmodelled,
    )
