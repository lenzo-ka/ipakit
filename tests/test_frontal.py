from __future__ import annotations

import dataclasses
import inspect
import random
import re
from pathlib import Path

import pytest
from ipakit.features import IPAFeatures
from ipakit.form import FormBuilder
from ipakit.tract import head, heads, landmarks, posture, trajectory
from ipakit.tract_svg import (
    Point,
    _frontal_extent,
    _frontal_scaler,
    _scaler,
    animate_two_pane,
    build_frontal_geometry,
    build_geometry,
    frontal_figure,
    frontal_svg,
    standalone_frontal_svg,
)

from tests._renderers import needs_renderer
from tests.test_tract_figures import _differing, _pixels

FIGURES = Path(__file__).resolve().parent.parent / "docs" / "figures"


def test_frontal_and_sagittal_scalers_share_one_fit() -> None:
    """Reflecting the input is the only difference between the projections."""
    generator = random.Random(0)
    for _ in range(2_000):
        x0 = generator.uniform(-3, 3)
        x1 = x0 + generator.uniform(0, 5)
        y0 = generator.uniform(-3, 3)
        y1 = y0 + generator.uniform(0, 5)
        px = generator.uniform(x0, x1)
        py = generator.uniform(y0, y1)
        assert _frontal_scaler(x0, x1, y0, y1)(px, py) == pytest.approx(
            _scaler(x0, x1, y0, y1)(px, y0 + y1 - py), abs=1e-9
        )


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_frontal_builder_has_no_symbol_channel() -> None:
    assert set(inspect.signature(build_frontal_geometry).parameters) == {
        "head",
        "marks",
        "p",
    }


@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", [None, "m", "a", "i", "u", "t", "k"])
def test_every_frontal_frame_is_pure_in_the_posture(
    head_name: str, phone: str | None, ipa: IPAFeatures
) -> None:
    h = head(head_name)
    marks = landmarks(ipa)
    p = posture(ipa, phone, h)
    assert build_frontal_geometry(h, marks, p) == build_frontal_geometry(
        h, marks, dataclasses.replace(p)
    )


def test_shut_mouth_leaks_no_interior(ipa: IPAFeatures) -> None:
    h = head()
    g = build_frontal_geometry(h, landmarks(ipa), posture(ipa, "m", h))
    svg = frontal_svg(g)
    assert g["closed"]
    assert "f-aperture" not in svg
    assert "f-tongue" not in svg
    assert "f-upper-teeth" not in svg


def test_declared_rest_seals_untimed_animation_bookends(ipa: IPAFeatures) -> None:
    h = head()
    marks = landmarks(ipa)
    track = trajectory("kat", head=h, frames_per_unit=4)
    for frame in (track.frames[0], track.frames[-1]):
        geometry = build_frontal_geometry(h, marks, frame)
        assert geometry["closed"]
        assert "f-aperture" not in frontal_svg(geometry)


def test_open_vowel_exposes_carried_interior(ipa: IPAFeatures) -> None:
    h = head()
    svg = frontal_svg(build_frontal_geometry(h, landmarks(ipa), posture(ipa, "a", h)))
    assert "f-aperture" in svg
    assert "f-tongue" in svg
    assert "f-upper-teeth" in svg


@pytest.mark.parametrize("phone", ["m", "i", "a", "u"])
def test_lips_and_aperture_share_the_parting_curves(
    phone: str, ipa: IPAFeatures
) -> None:
    """Closed, mid, open and rounded mouths have one exact boundary."""
    h = head()
    g = build_frontal_geometry(h, landmarks(ipa), posture(ipa, phone, h))
    by_name = {contour["name"]: contour for contour in g["contours"]}
    upper, lower = g["upper_edge"], g["lower_edge"]

    assert g["aperture"][:3] == upper
    assert tuple(reversed(g["aperture"][3:])) == lower
    assert tuple(reversed(by_name["upper-lip"]["points"][-3:])) == upper
    assert by_name["lower-lip"]["points"][:3] == lower
    # These are not independently recomputed equal coordinates: all three
    # bodies retain the Head curve's actual corner and edge point objects.
    assert all(g["aperture"][i] is upper[i] for i in range(3))
    assert all(by_name["lower-lip"]["points"][i] is lower[i] for i in range(3))
    assert upper[0] is lower[0] and upper[-1] is lower[-1]


@needs_renderer("rsvg-convert", "rsvg-convert absent")
def test_open_a_has_no_face_pixels_inside_the_lip_parting_line(
    ipa: IPAFeatures, tmp_path: Path
) -> None:
    h = head()
    g = build_frontal_geometry(h, landmarks(ipa), posture(ipa, "a", h))
    to = _frontal_scaler(*_frontal_extent(g))
    polygon = [to(*point) for point in g["aperture"]]
    width, rows = _pixels(standalone_frontal_svg(g), tmp_path / "a.svg", width=760)
    assert width == 760
    face = bytes.fromhex("d9b29aff")

    def inside(px: float, py: float) -> bool:
        hit = False
        prior = polygon[-1]
        for point in polygon:
            (x0, y0), (x1, y1) = prior, point
            if (y0 > py) != (y1 > py):
                cross = (x1 - x0) * (py - y0) / (y1 - y0) + x0
                if px < cross:
                    hit = not hit
            prior = point
        return hit

    xmin, xmax = int(min(x for x, _ in polygon)), int(max(x for x, _ in polygon))
    ymin, ymax = int(min(y for _, y in polygon)), int(max(y for _, y in polygon))
    skin = [
        (x, y)
        for y in range(ymin, ymax + 1)
        for x in range(xmin, xmax + 1)
        if inside(x + 0.5, y + 0.5) and rows[y][x * 4 : x * 4 + 4] == face
    ]
    assert not skin


@needs_renderer("rsvg-convert", "rsvg-convert absent")
@pytest.mark.parametrize(
    ("phone", "layer", "minimum"),
    [
        ("m", "tongue", 0),
        ("a", "tongue", 100),
        ("m", "upper-teeth", 0),
        ("a", "upper-teeth", 100),
    ],
)
def test_frontal_occlusion_by_changed_pixels(
    phone: str, layer: str, minimum: int, tmp_path: Path
) -> None:
    svg = frontal_figure(phone)
    without = re.sub(rf'<path\b[^>]*class="f-{re.escape(layer)}"[^>]*/>', "", svg)
    width, before = _pixels(svg, tmp_path / "with.svg", width=760)
    _, after = _pixels(without, tmp_path / "without.svg", width=760)
    changed = len(_differing(width, before, after))
    assert changed == 0 if minimum == 0 else changed >= minimum


@needs_renderer("rsvg-convert", "rsvg-convert absent")
def test_kaet_frontal_tongue_occludes_cavity_and_reaches_velar_target(
    ipa: IPAFeatures, tmp_path: Path
) -> None:
    h, marks = head(), landmarks(ipa)
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)

    def at(ordinal: float):
        index = min(
            range(len(track.frames)), key=lambda i: abs(track.ordinals[i] - ordinal)
        )
        return build_frontal_geometry(h, marks, track.frames[index])

    def dark_cavity(name: str, geometry) -> int:
        _width, rows = _pixels(
            standalone_frontal_svg(geometry), tmp_path / f"{name}.svg", width=800
        )
        cavity = bytes.fromhex("24191aff")
        return sum(
            row[x : x + 4] == cavity for row in rows for x in range(0, len(row), 4)
        )

    velar, open_vowel, apical = at(1.0), at(2.0), at(3.0)
    k_dark = dark_cavity("k", velar)
    ash_dark = dark_cavity("ash", open_vowel)
    t_dark = dark_cavity("t", apical)
    # No cavity survives a closure.  The 16-pixel allowance covers librsvg
    # antialiasing where clipped strokes meet the curved parting boundary; the
    # two pixels actually left at /t/ are the two mouth corners.  This catches
    # a tongue that fails to occlude, but it cannot on its own certify that
    # the tongue *reached* the parting curve: the visible aperture band is far
    # narrower than the band the tongue crosses, so the teeth mask a partial
    # under-reach.  test_closure_reaches_the_parting_curve pins the reach.
    assert t_dark <= 16
    assert ash_dark >= 5_000
    assert k_dark + 5_000 < ash_dark

    approach = [
        build_frontal_geometry(h, marks, frame)
        for ordinal, frame in zip(track.ordinals, track.frames, strict=True)
        if 0.5 <= ordinal <= 1.0
    ]
    centre_edges = [
        min(
            next(c for c in geometry["contours"] if c["name"] == "tongue")["points"],
            key=lambda point: abs(point[0] - 0.5),
        )[1]
        for geometry in approach
    ]
    # Face coordinates increase downward: strict decrease is a strict rise.
    assert all(
        after < before
        for before, after in zip(centre_edges, centre_edges[1:], strict=False)
    )


def test_closure_reaches_the_parting_curve(ipa: IPAFeatures) -> None:
    """A closure seats the visible tongue on the roof, an open vowel does not.

    Counting cavity pixels cannot tell reaching from nearly reaching, because
    the teeth occlude most of the band the tongue crosses: a tongue stopping a
    third of the way short still leaves the same two corner pixels.  Reach is
    a geometric claim, so it is measured on the geometry -- how far the visible
    center edge sits below the declared parting curve, as a fraction of the
    local floor-to-roof band, which is the same fraction ``offset`` means.
    """
    h, marks = head(), landmarks(ipa)
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)

    def centre_reach(ordinal: float) -> float:
        index = min(
            range(len(track.frames)), key=lambda i: abs(track.ordinals[i] - ordinal)
        )
        geometry = build_frontal_geometry(h, marks, track.frames[index])
        points = next(c for c in geometry["contours"] if c["name"] == "tongue")[
            "points"
        ]
        upper, lower = geometry["upper_edge"], geometry["lower_edge"]
        center = (upper[0][0] + upper[-1][0]) / 2.0

        def edge_y(edge: tuple[Point, ...], x: float) -> float:
            for left, right in zip(edge, edge[1:], strict=False):
                if left[0] <= x <= right[0]:
                    span = right[0] - left[0]
                    t = (x - left[0]) / span if span else 0.0
                    return left[1] + (right[1] - left[1]) * t
            return min(edge, key=lambda point: abs(point[0] - x))[1]

        x, y = min(points, key=lambda point: abs(point[0] - center))
        roof, floor = edge_y(upper, x), edge_y(lower, x)
        return (y - roof) / (floor - roof)

    # Measured: 0.030 at /t/ and 0.029 at /k/, a residue of sampling the raised
    # cosine on a finite grid and under a pixel at figure scale.  A tenth of
    # the band is a wide berth over that and still bites well before an
    # under-reach becomes visible -- a third of the band renders identically.
    assert centre_reach(3.0) <= 0.10, "apical closure does not reach the roof"
    assert centre_reach(1.0) <= 0.10, "velar closure does not reach the roof"
    # The other direction: an open vowel must keep the tongue off the roof, so
    # the pin cannot be satisfied by a mouth that is simply always full.
    assert centre_reach(2.0) >= 0.50, "open vowel seats the tongue on the roof"


def test_chin_is_declared_shallow_and_mandible_carried() -> None:
    for head_name in heads():
        h = head(head_name)
        name, carrier, _arc, points = next(c for c in h.frontal if c[0] == "chin")
        assert name == "chin" and carrier == "mandible"
        assert len(points) >= 5
        assert points[0] == (0.243, 0.62) and points[-1] == (0.757, 0.62)
        rise = points[2][1] - min(points[1][1], points[3][1])
        assert 0.0 < rise <= 0.02


def test_frontal_css_vocabulary_is_scoped() -> None:
    svg = frontal_figure("a")
    classes = [
        token
        for value in svg.split('class="')[1:]
        for token in value.split('"', 1)[0].split()
    ]
    assert classes
    assert all(token.startswith("f-") for token in classes)


def test_two_pane_page_is_one_self_contained_trajectory() -> None:
    page = animate_two_pane("kat", frames_per_unit=2)
    assert page.count('id="scrub"') == 1
    assert ".f-face{" not in page and "f-eyes" not in page
    assert "http://" not in page and "https://" not in page
    assert "Mid-sagittal tract section" in page
    assert "Frontal tract view" in page


def test_timed_player_adds_marked_rest_ramps_without_touching_track() -> None:
    builder = FormBuilder()
    handles = builder.append_ipa("a")
    builder.attach_timing(handles[0], 0.1, 0.4)
    track = trajectory(builder.build(), head=head(), fps=20)
    encoded = track.to_track()
    page = animate_two_pane(track)
    assert track.to_track() == encoded
    assert page.count('data-phase="lead-in"') == 4
    assert page.count('data-phase="lead-out"') == 4
    starts = [match.start() for match in re.finditer(r'<div class="frame', page)]
    first = page[starts[0] : starts[1]]
    lead = page[starts[0] : starts[4]]
    assert "f-aperture" not in first
    assert "f-aperture" in lead


@pytest.mark.parametrize(
    ("filename", "phone"),
    [
        ("frontal-reference.svg", None),
        ("frontal-rest.svg", "␣"),
        ("frontal-t.svg", "t"),
        ("frontal-a.svg", "a"),
        ("frontal-i.svg", "i"),
        ("frontal-m.svg", "m"),
        ("frontal-u.svg", "u"),
    ],
)
def test_checked_in_frontal_figure_is_current(filename: str, phone: str | None) -> None:
    assert (FIGURES / filename).read_text(encoding="utf-8") == frontal_figure(
        phone
    ) + "\n"


def test_checked_in_timed_two_pane_player_is_current() -> None:
    builder = FormBuilder()
    handles = builder.append_ipa("a")
    for handle, (start, duration) in zip(handles, ((0.0, 0.20),), strict=True):
        builder.attach_timing(handle, start, duration)
    timed = dataclasses.replace(
        trajectory(builder.build(), head=head(), fps=5), frames_per_unit=1
    )
    assert (FIGURES / "two-pane-timed.html").read_text(
        encoding="utf-8"
    ) == animate_two_pane(timed) + "\n"


def test_the_two_views_agree_that_there_is_a_tongue() -> None:
    """Neither view may draw a tongue the other one omits.

    The sagittal surface and the frontal planform read the same
    ``p.tongue_controls`` and then diverge into geometry that shares no
    key: the sagittal answers with ``tongue`` and the frontal with a
    ``tongue`` entry among its named ``contours``. Nothing connected the
    two, so one could stop producing a tongue while the other carried on
    and every figure that draws only one view would still look right.

    It asks whether the contour has POINTS, not whether it is named. The
    name survives an empty projection, so a gate reading the name alone
    passes while the frontal draws nothing -- which is what the first
    version of this test did, and an injection emptying the frontal
    points did not fire it.

    This asserts presence rather than shape, which is the honest limit:
    the two are projections of one surface into different planes and
    their point sets are not comparable. What it catches is a view going
    silent, which is the divergence that would return no error.

    The sweep is asserted against a floor so it cannot pass by covering
    nothing -- the frontal early return for empty controls is unreachable
    across the shipped inventory, so a run that found no tongues at all
    would mean the sweep stopped working rather than that the views
    agreed.
    """
    ipa = IPAFeatures()
    marks = landmarks(ipa)
    disagreed: list[tuple[str, str, bool, bool]] = []
    drawn = 0
    for head_name in heads():
        shape = head(head_name)
        for phone in ipa.phones:
            pose = posture(ipa, phone, shape)
            sagittal = bool(build_geometry(shape, marks, pose).get("tongue"))
            frontal = any(
                contour["name"] == "tongue" and contour["points"]
                for contour in build_frontal_geometry(shape, marks, pose)["contours"]
            )
            drawn += 1 if sagittal else 0
            if sagittal != frontal:
                disagreed.append((head_name, phone, sagittal, frontal))
    assert drawn > 300, f"the sweep drew only {drawn} tongues; it is not covering"
    assert disagreed == [], disagreed
