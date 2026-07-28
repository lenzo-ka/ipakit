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

from ipakit.tract import Head, TractPoint, head, heads  # noqa: E402

SAMPLES = 240
WIDTH = 760
SECTION_HEIGHT = 560
CHART_HEIGHT = 300
PAD = 44
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
    return {
        "rows": sample(h),
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


PLACES = {
    "bilabial": 0.00,
    "labiodental": 0.03,
    "dental": 0.08,
    "alveolar": 0.13,
    "postalveolar": 0.19,
    "alveolo-palatal": 0.24,
    "palatal": 0.32,
    "velar": 0.45,
    "uvular": 0.56,
    "pharyngeal": 0.74,
    "epiglottal": 0.87,
    "glottal": 1.00,
}
ARTICULATORS = {
    "lower lip": 0.00,
    "tongue tip": 0.13,
    "tongue blade": 0.19,
    "tongue front": 0.32,
    "tongue dorsum": 0.45,
    "tongue root": 0.74,
    "epiglottis": 0.87,
    "vocal folds": 1.00,
}
FRICATIVE_PLACES = {
    "labiodental",
    "dental",
    "alveolar",
    "postalveolar",
    "alveolo-palatal",
    "palatal",
    "velar",
    "uvular",
    "pharyngeal",
    "epiglottal",
    "glottal",
}
VELUM_ARC = 0.50


def _at(src: dict[str, Any], arc: float, key: str) -> Point | None:
    best = min(src["rows"], key=lambda r: abs(r["arc"] - arc), default=None)
    return None if best is None else best[key]


def _annotate(src: dict[str, Any], to: Scaler) -> str:
    """Places on the wall, articulators on the open trace."""
    parts: list[str] = []
    for i, (name, arc) in enumerate(sorted(PLACES.items(), key=lambda kv: kv[1])):
        anchor = _at(src, arc, "wall")
        if anchor is None:
            continue
        x, y = to(*anchor)
        fric = name in FRICATIVE_PLACES
        cls = "place fric" if fric else "place"
        lift = 15 + (i % 2) * 15
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y - lift:.1f}" '
            f'class="lead {cls}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" class="mark {cls}"/>'
            f'<text x="{x:.1f}" y="{y - lift - 4:.1f}" class="lbl {cls}" '
            f'text-anchor="middle">{name}</text>'
        )
    for i, (name, arc) in enumerate(sorted(ARTICULATORS.items(), key=lambda kv: kv[1])):
        anchor = _at(src, arc, "open")
        if anchor is None:
            continue
        x, y = to(*anchor)
        drop = 14 + (i % 2) * 14
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + drop:.1f}" '
            f'class="lead art"/>'
            f'<text x="{x:.1f}" y="{y + drop + 11:.1f}" class="lbl art" '
            f'text-anchor="middle">{name}</text>'
        )
    rest_arc = src.get("rest_arc")
    if rest_arc is not None:
        anchor = _at(src, float(rest_arc), "rest")
        if anchor is not None:
            x, y = to(*anchor)
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="restmark"/>'
                f'<text x="{x + 9:.1f}" y="{y + 4:.1f}" class="lbl rest">rest</text>'
            )
    nasal = _at(src, VELUM_ARC, "wall")
    if nasal is not None:
        x, y = to(*nasal)
        parts.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + 26:.1f}" y2="{y - 54:.1f}" '
            f'class="nasal"/>'
            f'<text x="{x + 30:.1f}" y="{y - 58:.1f}" class="lbl nasal">'
            f"nasal cavity — not modelled</text>"
        )
    return "".join(parts)


def section_svg(current: dict[str, Any], prior: dict[str, Any] | None) -> str:
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
    parts.append('<path d="' + _trace(current, to, "wall") + '" class="wall"/>')
    parts.append('<path d="' + _trace(current, to, "rest") + '" class="restline"/>')
    parts.append('<path d="' + _trace(current, to, "open") + '" class="openline"/>')
    parts.append(_annotate(current, to))
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
--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
@media (prefers-color-scheme:light){:root{--ground:#DFE4E8;--panel:#F1F4F6;
--edge:#C9D2D9;--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;
--signal:#A96F0E;--tubeTrace:rgba(34,67,92,.10);
--tubePrior:rgba(154,169,180,.22)}}
:root[data-theme=dark]{--ground:#0A0E13;--panel:#111922;--edge:#1E2B36;
--text:#CFDAE2;--dim:#7A8B98;--trace:#9FC6DC;--prior:#46596A;--signal:#DFA33A;
--tubeTrace:rgba(159,198,220,.13);--tubePrior:rgba(70,89,106,.20)}
:root[data-theme=light]{--ground:#DFE4E8;--panel:#F1F4F6;--edge:#C9D2D9;
--text:#16202A;--dim:#5C6E7C;--trace:#22435C;--prior:#9AA9B4;--signal:#A96F0E;
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
.nasal{stroke:var(--dim);stroke-width:1;stroke-dasharray:2 4;opacity:.7}
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


def page(name: str, current: dict[str, Any], prior: dict[str, Any] | None) -> str:
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
<p style="margin-top:12px;color:var(--dim)">Drawn through
<code>Head.project</code>, the same call a renderer makes, so this cannot
drift from the model. Heads are read only for rendering and never by
<code>ipakit.metric</code>.</p></header>
<section><h2>Section</h2>
<p>The wall is fixed; the articulator sweeps between fully open and closed
against it. Shaded is that sweep, with the open and rest positions drawn
inside it. Places are labelled on the wall, articulators on the open trace;
those in amber host a fricative or affricate somewhere in the inventory.</p>
<figure>{section_svg(current, prior)}</figure>{key}</section>
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
    current = geometry(args.head)
    Path(args.output).write_text(page(args.head, current, prior), encoding="utf-8")
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
    p_draw.set_defaults(func=cmd_draw)

    p_dump = sub.add_parser("dump", help="project every head to JSON, for --compare")
    p_dump.add_argument("-o", "--output", default="heads.json")
    p_dump.set_defaults(func=cmd_dump)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
