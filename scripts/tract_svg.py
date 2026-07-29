#!/usr/bin/env python3
"""Draw a declared head, so a change to the geometry can be looked at.

``heads.xml`` is the only part of this library whose output is a picture, and
it was the only part with no way to see one. A diameter is four characters in
a diff; it is a visible pinch in a drawn tract. The change that prompted this
script left a slope of +0.364 between two midline points, which read as an
ordinary number and drew as a flare that belonged to nothing, and a normal
taken per segment drew a wall that crossed itself three times.

What is drawn
-------------

    section   the tract wall at full offset either side of the centreline,
              through ipakit.tract.Head.project -- the same call a renderer
              makes, so the drawing cannot drift from the model
    profile   the declared diameter against arc, where a change to the
              profile is legible rather than merely present

Nothing here computes geometry. Every coordinate comes from ``project``.

Comparing two revisions
-----------------------

    python scripts/tract_svg.py dump -o /tmp/before.json    # on one revision
    python scripts/tract_svg.py draw --compare /tmp/before.json -o tract.html

Heads are read only by ``Head.project`` and never by ``ipakit.metric``, so a
change here cannot move a distance. ``scripts/sweep.py diff`` is the check.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import (  # noqa: E402
    Head,
    TractPoint,
    head,
    heads,
    landmarks,
    tract_point,
    velic_aperture,
)

SAMPLES = 240
WIDTH = 760
SECTION_HEIGHT = 560
CHART_HEIGHT = 300
PAD = 54
CEILING = 0.20

Point = tuple[float, float]
Scaler = Callable[[float, float], Point]


def sample(h: Head, samples: int = SAMPLES) -> list[dict[str, Any]]:
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
        rows.append({"arc": arc, "open": openp, "rest": restp, "wall": wall})
    return rows


def geometry(name: str) -> dict[str, Any]:
    h = head(name)
    rest = h.rest
    nasal = [
        {
            "arc": i / 60,
            "mid": h.project_nasal(i / 60, 0.0),
            "wall": h.project_nasal(i / 60, 1.0),
            "low": h.project_nasal(i / 60, -1.0),
        }
        for i in range(61)
    ]
    return {
        "rows": sample(h),
        "nasal": [n for n in nasal if None not in n.values()],
        "port_arc": h.port_arc,
        "teeth": [{"name": n, "x": x, "y": y} for n, x, y in h.teeth],
        "rest_arc": None if rest is None else rest.arc,
        "rest_offset": None if rest is None else rest.offset,
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


def _extent(*sets: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for src in sets:
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


def _scaler(x0: float, x1: float, y0: float, y1: float) -> Scaler:
    sx = (WIDTH - 2 * PAD) / (x1 - x0) if x1 > x0 else 1.0
    sy = (SECTION_HEIGHT - 2 * PAD) / (y1 - y0) if y1 > y0 else 1.0
    scale = min(sx, sy)
    ox = PAD + ((WIDTH - 2 * PAD) - (x1 - x0) * scale) / 2
    oy = PAD + ((SECTION_HEIGHT - 2 * PAD) - (y1 - y0) * scale) / 2

    def to(px: float, py: float) -> Point:
        return (ox + (px - x0) * scale, oy + (y1 - py) * scale)

    return to


def _path(points: list[Point], close: bool = False) -> str:
    body = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return body + (" Z" if close else "")


def _band(src: dict[str, Any], to: Scaler, a: str, b: str) -> str:
    """Closed region between two offset traces -- the articulator's sweep."""
    top = [to(*row[a]) for row in src["rows"]]
    bottom = [to(*row[b]) for row in src["rows"]]
    return _path(top + list(reversed(bottom)), close=True)


def _trace(src: dict[str, Any], to: Scaler, key: str) -> str:
    return _path([to(*row[key]) for row in src["rows"]])


CHAR_W = 6.0  # advance of the 10.5px monospace label face
LINE_H = 12.0
PORT_SPAN = 0.055  # arc either side of the port at a fully lowered velum


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
    parts = [
        f'<line x1="{openp[0]:.1f}" y1="{openp[1]:.1f}" x2="{ax:.1f}" '
        f'y2="{ay:.1f}" class="reach"/>',
        f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5" '
        f'class="constriction{" shut" if shut else ""}"/>',
    ]
    name = articulator.replace("-", " ")
    label = f"{name} · {'closed' if shut else f'{1 - offset:.2f} open'}"
    for text, lx, ly, depth in _place_labels([(label, (ax, ay))], -18, -13, taken):
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + depth:.1f}" class="lbl constriction" '
            f'text-anchor="middle">{text}</text>'
        )
    return "".join(parts)


def _wall_with_port(src: dict[str, Any], to: Scaler, aperture: float) -> str:
    """The oral roof, broken where a lowered velum has left it open.

    The velum *is* part of the boundary. Raised, it seals the port and the
    roof is continuous; lowered, the roof is open to the nasopharynx and the
    nasal branch's floor is no longer an obstruction. Drawing an unbroken
    wall with a flap on top says the port is never open, whatever the flap
    is doing.
    """
    rows = src["rows"]
    if aperture <= 0.01:
        return f'<path d="{_path([to(*r["wall"]) for r in rows])}" class="wall"/>'
    declared = src.get("port_arc")
    if declared is None:
        return f'<path d="{_path([to(*r["wall"]) for r in rows])}" class="wall"/>'
    port = float(declared)
    half = PORT_SPAN * aperture
    before = [to(*r["wall"]) for r in rows if r["arc"] <= port - half]
    after = [to(*r["wall"]) for r in rows if r["arc"] >= port + half]
    out = []
    if len(before) > 1:
        out.append(f'<path d="{_path(before)}" class="wall"/>')
    if len(after) > 1:
        out.append(f'<path d="{_path(after)}" class="wall"/>')
    return "".join(out)


_MARKS = landmarks(IPAFeatures())
PLACES = _MARKS.places
ARTICULATORS = _MARKS.articulators
MEDIAN = _MARKS.median
FRICATIVE_PLACES = _MARKS.frication


def _at(src: dict[str, Any], arc: float, key: str) -> Point | None:
    best = min(src["rows"], key=lambda r: abs(r["arc"] - arc), default=None)
    return None if best is None else best[key]


def _place_labels(
    items: list[tuple[str, Point]], base: int, step: int, taken: list[tuple[float, ...]]
) -> list[tuple[str, float, float, float]]:
    """Drop each label to the shallowest depth where it does not collide.

    A fixed stagger cannot work here: the front of the mouth packs six places
    into 0.24 of arc, so any fixed number of rows eventually overlaps. This
    walks the labels in order and pushes each one down until its box is
    clear of every box already placed, which terminates and leaves the
    drawing readable whatever the head's proportions are.
    """
    out: list[tuple[str, float, float, float]] = []
    for name, (x, y) in items:
        half = len(name) * CHAR_W / 2
        depth = base
        for _ in range(12):
            top = y + depth
            box = (x - half, top, x + half, top + LINE_H)
            if not any(
                box[0] < t[2] and t[0] < box[2] and box[1] < t[3] and t[1] < box[3]
                for t in taken
            ):
                break
            depth += step
        top = y + depth
        taken.append((x - half, top, x + half, top + LINE_H))
        out.append((name, x, y, depth))
    return out


def _annotate(src: dict[str, Any], to: Scaler, taken: list[tuple[float, ...]]) -> str:
    """Places under the roof, articulators under the floor.

    Labels used to sit above the wall, which is where the nasal branch now
    runs, so they collided with it and with each other. Places are read off
    the roof and hang inside the oral cavity; articulators hang below the
    open trace. Both stagger over three depths, because the front of the
    mouth packs six places into 0.24 of arc and two depths is not enough.
    """
    parts: list[str] = []

    anchors: list[tuple[str, Point]] = []
    for name, arc in sorted(PLACES.items(), key=lambda kv: kv[1]):
        anchor = _at(src, arc, "wall")
        if anchor is not None:
            anchors.append((name, to(*anchor)))
    for name, x, y, depth in _place_labels(anchors, 14, 13, taken):
        cls = "place fric" if name in FRICATIVE_PLACES else "place"
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + depth:.1f}" '
            f'class="lead {cls}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" class="mark {cls}"/>'
            f'<text x="{x:.1f}" y="{y + depth + 10:.1f}" class="lbl {cls}" '
            f'text-anchor="middle">{name.replace("-", " ")}</text>'
        )

    anchors = []
    for name, arc in sorted(ARTICULATORS.items(), key=lambda kv: kv[1]):
        anchor = _at(src, arc, "open")
        if anchor is not None:
            anchors.append((name, to(*anchor)))
    for name, x, y, depth in _place_labels(anchors, 18, 13, taken):
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + depth:.1f}" '
            f'class="lead art"/>'
            f'<text x="{x:.1f}" y="{y + depth + 10:.1f}" class="lbl art" '
            f'text-anchor="middle">{name.replace("-", " ")}</text>'
        )
    for name, arc in MEDIAN.items():
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
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" class="medianmark"/>'
        )
        for label, lx, ly, depth in _place_labels([(name, (cx, cy))], 14, 13, taken):
            parts.append(
                f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{lx:.1f}" '
                f'y2="{ly + depth:.1f}" class="lead art"/>'
                f'<text x="{lx:.1f}" y="{ly + depth + 10:.1f}" class="lbl art" '
                f'text-anchor="middle">{label.replace("-", " ")}</text>'
            )
    teeth = src.get("teeth") or []
    if len(teeth) >= 2:
        ex, ey = to(teeth[0]["x"], teeth[0]["y"])
        ax, ay = to(teeth[1]["x"], teeth[1]["y"])
        parts.append(
            f'<path d="M{ex:.1f},{ey:.1f} L{ax:.1f},{ay:.1f}" class="teeth"/>'
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.6" class="teethmark"/>'
        )
        for label, lx, ly, depth in _place_labels([("teeth", (ex, ey))], 12, 13, taken):
            parts.append(
                f'<text x="{lx:.1f}" y="{ly - depth:.1f}" class="lbl teeth" '
                f'text-anchor="middle">{label.replace("-", " ")}</text>'
            )
    rest_arc = src.get("rest_arc")
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
                    f'<text x="{rx:.1f}" y="{ry + depth:.1f}" class="lbl rest" '
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
    tube = _path(upper + list(reversed(lower)), close=True)
    mid = _path([to(*r["mid"]) for r in rows])
    # The floor near the port stops being a boundary once the port is open.
    keep = (
        len(lower)
        if aperture <= 0.01
        else max(2, int(len(lower) * (1 - 0.18 * aperture)))
    )
    parts = [
        f'<path d="{tube}" class="nasalfill"/>',
        f'<path d="{_path(upper)}" class="nasalside"/>',
        f'<path d="{_path(lower[:keep])}" class="nasalside"/>',
        f'<path d="{mid}" class="nasalmid"/>',
    ]
    lx, ly = to(*rows[len(rows) // 3]["wall"])
    for label, nx, ny, depth in _place_labels(
        [("nasal cavity", (lx, ly))], -20, -13, taken
    ):
        parts.append(
            f'<text x="{nx:.1f}" y="{ny + depth:.1f}" class="lbl nasal" '
            f'text-anchor="middle">{label.replace("-", " ")}</text>'
        )
    declared_port = src.get("port_arc")
    if declared_port is None:
        return "".join(parts)
    port_arc = float(declared_port)
    hinge = _at(src, max(port_arc - 0.08, 0.0), "wall")
    lowered_to = _at(src, port_arc, "open")
    if hinge is None or lowered_to is None:
        return "".join(parts)
    hx, hy = to(*hinge)
    sealed = to(*rows[-1]["mid"])
    lowered = to(*lowered_to)
    tx = sealed[0] + (lowered[0] - sealed[0]) * aperture
    ty = sealed[1] + (lowered[1] - sealed[1]) * aperture
    if aperture <= 0.01:
        state = "sealed"
    elif aperture >= 0.99:
        state = "open"
    else:
        state = "part-open"
    parts.append(
        f'<path d="M{hx:.1f},{hy:.1f} Q{hx:.1f},{ty:.1f} {tx:.1f},{ty:.1f}" '
        f'class="velum"/>'
        f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3" class="velumtip"/>'
    )
    for text, vx, vy, depth in _place_labels(
        [(f"velum · port {state}", (tx, ty))], 14, 13, taken
    ):
        parts.append(
            f'<line x1="{vx:.1f}" y1="{vy:.1f}" x2="{vx:.1f}" '
            f'y2="{vy + depth:.1f}" class="lead art"/>'
            f'<text x="{vx:.1f}" y="{vy + depth + 10:.1f}" class="lbl velum" '
            f'text-anchor="middle">{text}</text>'
        )
    return "".join(parts)


def section_svg(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
    aperture: float = 0.0,
    posture: tuple[float, float, str] | None = None,
) -> str:
    sets = [current] if prior is None else [current, prior]
    to = _scaler(*_extent(*sets))
    parts = []
    if prior is not None:
        parts.append(
            '<path d="' + _band(prior, to, "wall", "open") + '" class="sweep prior"/>'
        )
    parts.append(
        '<path d="' + _band(current, to, "wall", "open") + '" class="sweep trace"/>'
    )
    parts.append(_wall_with_port(current, to, aperture))
    parts.append('<path d="' + _trace(current, to, "rest") + '" class="restline"/>')
    parts.append('<path d="' + _trace(current, to, "open") + '" class="openline"/>')
    taken: list[tuple[float, ...]] = []
    parts.append(_annotate(current, to, taken))
    parts.append(_nasal(current, to, aperture, taken))
    parts.append(_constriction(current, to, posture, taken))
    return (
        f'<svg viewBox="0 0 {WIDTH} {SECTION_HEIGHT}" role="img" '
        f'aria-label="Mid-sagittal tract section">{"".join(parts)}</svg>'
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
--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;--velum:#7FD1B9;--velumText:#5E9384;
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
@media (prefers-color-scheme:light){:root{--ground:#DFE4E8;--panel:#F1F4F6;
--edge:#C9D2D9;--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;
--signal:#A96F0E;--velum:#1F7A63;--velumText:#4C8375;--tubeTrace:rgba(34,67,92,.10);
--tubePrior:rgba(154,169,180,.22)}}
:root[data-theme=dark]{--ground:#0A0E13;--panel:#111922;--edge:#1E2B36;
--text:#CFDAE2;--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;--velum:#7FD1B9;--velumText:#5E9384;
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
:root[data-theme=light]{--ground:#DFE4E8;--panel:#F1F4F6;--edge:#C9D2D9;
--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;--signal:#A96F0E;--velum:#1F7A63;--velumText:#4C8375;
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
.wall{fill:none;stroke:var(--trace);stroke-width:1.8}
.openline{fill:none;stroke:var(--trace);stroke-width:1;opacity:.55}
.restline{fill:none;stroke:var(--trace);stroke-width:1;
stroke-dasharray:3 4;opacity:.75}
.lead{stroke-width:1;opacity:.5}
.lead.place{stroke:var(--trace)}
.lead.place.fric{stroke:var(--signal)}
.lead.art{stroke:var(--dim)}
.mark.place{fill:var(--trace)}
.mark.place.fric{fill:var(--signal)}
.lbl{font:400 10.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.lbl.place{fill:var(--trace)}
.lbl.place.fric{fill:var(--signal)}
.lbl.art{fill:var(--dim)}
.lbl.rest{fill:var(--text)}
.lbl.nasal{fill:var(--dim);font-style:italic}
.restmark{fill:none;stroke:var(--text);stroke-width:1.4}
.nasalfill{fill:var(--tubeTrace);stroke:none}
.nasalside{fill:none;stroke:var(--trace);stroke-width:1;opacity:.8}
.nasalmid{fill:none;stroke:var(--trace);stroke-width:.8;
stroke-dasharray:2 4;opacity:.5}
.velum{stroke:var(--velum);stroke-width:2;stroke-linecap:round;fill:none}
.velumtip{fill:var(--velum)}
.lbl.velum{fill:var(--velumText);font-weight:400}
.median{stroke:var(--dim);stroke-width:1;stroke-dasharray:1 3}
.reach{stroke:var(--signal);stroke-width:1.4;stroke-dasharray:2 3;opacity:.8}
.constriction{fill:none;stroke:var(--signal);stroke-width:2}
.constriction.shut{fill:var(--signal)}
.lbl.constriction{fill:var(--signal)}
.teeth{stroke:var(--text);stroke-width:2.2;stroke-linecap:round;fill:none}
.teethmark{fill:var(--text)}
.lbl.teeth{fill:var(--text)}
.medianmark{fill:none;stroke:var(--dim);stroke-width:1.6}
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
) -> str:
    key = (
        ""
        if prior is None
        else '<div class="key">'
        '<span><i style="background:var(--prior)"></i>compared</span>'
        '<span><i style="background:var(--trace)"></i>current</span></div>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — mid-sagittal tract</title>
<style>{STYLE}</style></head><body>
<div class="wrap">
<header><p class="eyebrow">ipakit · heads.xml · {name}</p>
<h1>Mid-sagittal tract</h1>
{f'<p class="eyebrow" style="color:var(--dim);margin-top:8px">posture: {phone} · velic port {aperture:.2f}</p>' if phone else ''}
<p style="margin-top:12px;color:var(--dim)">Drawn through
<code>Head.project</code>, the same call a renderer makes, so this cannot
drift from the model. Heads are read only for rendering and never by
<code>ipakit.metric</code>.</p></header>
<section><h2>Section</h2>
<p>The wall is fixed; the articulator sweeps between fully open and closed
against it. Shaded is that sweep, with the open and rest positions drawn
inside it. Places are labelled on the wall, articulators on the open trace;
those in amber host a fricative or affricate somewhere in the inventory.</p>
<figure>{section_svg(current, prior, aperture, posture)}</figure>{key}</section>
<section><h2>Declared diameter</h2>
<p>Where a change to the profile is legible.</p>
<figure>{profile_svg(current, prior)}</figure>
<figcaption>Points are the declared midline; the line between them is what
<code>project</code> interpolates.</figcaption></section>
<section><h2>Midline points</h2>
<p>Where each declared diameter comes from. <em>Measured</em> is the shape
taken from the X-Ray Microbeam database over 48 speakers; the corpus has no
upper wall forward of arc 0.11 and none behind arc 0.44, so everything
outside that span is extrapolated. See <code>docs/articulatory-data.md</code>.</p>
<table><thead><tr><th>arc</th>{"<th>compared</th>" if prior else ""}
<th>diameter</th><th>provenance</th></tr></thead>
<tbody>{_table(current, prior)}</tbody></table></section>
</div></body></html>"""


def cmd_draw(args: argparse.Namespace) -> int:
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
    aperture = 0.0
    posture: tuple[float, float, str] | None = None
    if args.phone:
        ipa = IPAFeatures()
        bundle = ipa.get_features(args.phone)
        aperture = velic_aperture(ipa, bundle)
        point = tract_point(ipa, bundle)
        if point.arc is not None and point.offset is not None:
            posture = (point.arc, point.offset, point.articulator or "articulator")
    current = geometry(args.head)
    Path(args.output).write_text(
        page(args.head, current, prior, aperture, args.phone, posture),
        encoding="utf-8",
    )
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

    p_dump = sub.add_parser("dump", help="project every head to JSON, for --compare")
    p_dump.add_argument("-o", "--output", default="heads.json")
    p_dump.set_defaults(func=cmd_dump)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
