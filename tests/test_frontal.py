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
