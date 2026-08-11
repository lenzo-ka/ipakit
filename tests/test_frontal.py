from __future__ import annotations

import dataclasses
import inspect
import re
import shutil
from pathlib import Path

import pytest
from ipakit.features import IPAFeatures
from ipakit.form import FormBuilder
from ipakit.tract import head, heads, landmarks, posture, trajectory
from ipakit.tract_svg import (
    _frontal_extent,
    _frontal_scaler,
    animate_two_pane,
    build_frontal_geometry,
    frontal_figure,
    frontal_svg,
)

from tests.test_tract_figures import _differing, _pixels

FIGURES = Path(__file__).resolve().parent.parent / "docs" / "figures"


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


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
def test_open_a_has_no_face_pixels_inside_the_lip_parting_line(
    ipa: IPAFeatures, tmp_path: Path
) -> None:
    h = head()
    g = build_frontal_geometry(h, landmarks(ipa), posture(ipa, "a", h))
    to = _frontal_scaler(*_frontal_extent(g))
    polygon = [to(*point) for point in g["aperture"]]
    width, rows = _pixels(frontal_svg(g), tmp_path / "a.svg", width=760)
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


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
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
    assert page.count(".f-face{") == 1
    assert "http://" not in page and "https://" not in page
    assert "Mid-sagittal tract section" in page
    assert "Frontal tract view" in page


@pytest.mark.parametrize(
    ("filename", "phone"),
    [
        ("frontal-reference.svg", None),
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
