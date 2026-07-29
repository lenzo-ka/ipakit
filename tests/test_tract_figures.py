"""What a drawn tract has to satisfy, whatever the head or the phone.

Both properties here were found by looking at a picture and then chased by
hand for a while. A label that overlaps another, or a cavity that leaks where
it should be sealed, is not something the rest of the suite can see: the
geometry is well-formed, the numbers are fine, and the drawing is wrong.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import tract_svg  # noqa: E402
from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import (
    TractPoint,
    head,
    heads,
    tract_point,
    velic_aperture,
)  # noqa: E402

# Advances rounded up: a box narrower than the text it holds is the bug this
# guards against, so erring wide is the safe direction.
ADVANCE = {"glyph": 24 * 0.62, "caption": 12 * 0.62, "feat": 10.5 * 0.62}
DEFAULT_ADVANCE = 10.5 * 0.64
LINE = 12.0

_TEXT = re.compile(
    r'<text x="([-\d.]+)" y="([-\d.]+)" class="([^"]*)"[^>]*>(.*?)</text>', re.S
)
_TSPAN = re.compile(r"<tspan[^>]*>([^<]*)</tspan>")


def _boxes(svg: str) -> list[tuple[float, float, float, float, str]]:
    out = []
    for match in _TEXT.finditer(svg):
        x, y, cls, body = match.group(1), match.group(2), match.group(3), match.group(4)
        lines = _TSPAN.findall(body) or [re.sub(r"<[^>]*>", "", body)]
        advance = next((v for k, v in ADVANCE.items() if k in cls), DEFAULT_ADVANCE)
        width = max(len(line) for line in lines) * advance
        left = (
            float(x) - width
            if 'text-anchor="end"' in match.group(0)
            else float(x) - width / 2
        )
        top = float(y) - LINE
        out.append((left, top, left + width, top + LINE * len(lines), "/".join(lines)))
    return out


def _section(name: str, phone: str | None) -> str:
    ipa = IPAFeatures()
    aperture, posture, active = 0.0, None, None
    close = 0.0
    if phone is not None:
        bundle = ipa.get_features(phone)
        aperture = velic_aperture(ipa, bundle)
        point = tract_point(ipa, bundle)
        if point.arc is not None and point.offset is not None:
            posture = (point.arc, point.offset, point.articulator or "articulator")
            close = head(name).jaw_close(point)
        active = {"place": str(bundle.get("place") or "")}
        if point.offset is not None:
            active["degree"] = (
                "closed" if point.offset >= 0.995 else f"{1 - point.offset:.2f} open"
            )
        if point.articulator:
            active["articulator"] = str(point.articulator)
        if bundle.get("voiced"):
            active["voiced"] = str(bundle["voiced"])
    geometry = tract_svg.geometry(name, close)
    if posture is not None:
        geometry["tongue"] = tract_svg.tongue_surface(
            name, TractPoint(arc=posture[0], offset=posture[1]), close
        )
        geometry["lips_closed_now"] = posture[0] <= 0.02 and posture[1] >= 0.995
    return tract_svg.section_svg(geometry, None, aperture, posture, None, active)


PHONES = [None, "m", "b", "n", "t", "k", "ɡ", "s", "ʃ", "a", "i", "u", "h", "␣"]


@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", PHONES, ids=lambda p: p or "reference")
def test_no_label_overlaps_another(head_name: str, phone: str | None) -> None:
    """Two labels may not occupy the same space.

    The layout drops each label until its box is clear, so this can only fail
    if a box is reserved for something other than what is drawn -- a narrower
    advance than the face, or a name reserved before a state was appended to
    it. Both of those shipped.
    """
    boxes = _boxes(_section(head_name, phone))
    assert boxes, "a drawing with no labels is not being checked"
    clashes = [
        (a[4], b[4])
        for i, a in enumerate(boxes)
        for b in boxes[i + 1 :]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    ]
    assert not clashes, f"{head_name} {phone!r}: {clashes}"


def _pts(d: str) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in re.findall(r"([-\d.]+),([-\d.]+)", d)]


@pytest.mark.parametrize("phone", ["b", "p", "m"])
def test_a_shut_mouth_leaks_only_at_the_glottis(phone: str) -> None:
    """With the lips together the oral boundary closes, glottis apart.

    The tract is drawn from several declarations -- wall, floor, two lip
    bodies -- that have to meet. They met by luck before they met by
    construction, and the seams were invisible until something was rasterised.
    """
    svg = _section("adult-male", phone)
    walls = [_pts(d) for d in re.findall(r'<path d="([^"]*)" class="wall"/>', svg)]
    floor = re.search(r'<path d="([^"]*)" class="openline"/>', svg)
    lips = [_pts(d) for d in re.findall(r'<path d="([^"]*)" class="lip[^"]*"/>', svg)]
    assert walls and floor and len(lips) == 2

    def gap(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    assert gap(lips[0][2], lips[1][2]) < 0.5, "the lips do not meet"
    assert (
        min(gap(v, walls[0][0]) for v in lips[0]) < 0.5
    ), "roof adrift of the upper lip"
    floor_pts = _pts(floor.group(1))
    assert (
        min(gap(v, floor_pts[0]) for v in lips[1]) < 0.5
    ), "floor adrift of the lower lip"
    if velic_aperture(IPAFeatures(), IPAFeatures().get_features(phone)) <= 0.01:
        assert len(walls) == 1, "a sealed velum must leave the roof unbroken"
