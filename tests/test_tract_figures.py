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
    constrictions,
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


@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", ["b", "p", "m"])
def test_a_shut_mouth_leaks_only_at_the_glottis(phone: str, head_name: str) -> None:
    """With the lips together the oral boundary closes, glottis apart.

    The tract is drawn from several declarations -- wall, floor, two lip
    bodies -- that have to meet. They met by luck before they met by
    construction, and the seams were invisible until something was rasterised.
    """
    svg = _section(head_name, phone)
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


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_the_tongue_stays_inside_the_tract(head_name: str) -> None:
    """No tongue surface may pass the roof or the floor, for any phone.

    ``offset`` is a fraction from the floor to the wall, so the jaw has to
    move the floor rather than displace the result. Displacing it instead
    pushes a closure that already touches the wall straight through it, which
    needs a front closure and a half-closed jaw together to show up -- a
    click. A closed jaw or an open one both hide it.
    """
    ipa = IPAFeatures()
    h = head(head_name)
    escapes = []
    for phone in sorted(ipa.phones):
        point = tract_point(ipa, ipa.get_features(phone))
        if point.arc is None or point.offset is None:
            continue
        close = h.jaw_close(point)
        geometry = tract_svg.geometry(head_name, close)
        surface = tract_svg.tongue_surface(
            head_name, TractPoint(arc=point.arc, offset=point.offset), close
        )
        at = {round(a, 4): (x, y) for a, x, y in surface}
        for row in geometry["rows"]:
            here = at.get(round(row["arc"], 4))
            if here is None:
                continue
            if here[1] > row["wall"][1] + 1e-9 or here[1] < row["open"][1] - 1e-9:
                escapes.append((phone, round(row["arc"], 3)))
                break
    assert not escapes, f"{head_name}: tongue outside the tract for {escapes[:6]}"


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_an_articulator_reaches_its_target(head_name: str) -> None:
    """Where a segment states a constriction, the tongue gets there.

    The taper that brings the tongue to a point at each end of its span was
    scaling constrictions inside that band, so a tip closing near the front
    stopped short of the ridge it was supposed to touch -- visible on a click,
    whose front closure sits well inside the taper.
    """
    ipa = IPAFeatures()
    h = head(head_name)
    short = []
    for phone in sorted(ipa.phones):
        for point in constrictions(ipa, ipa.get_features(phone)):
            if point.arc is None or point.offset is None:
                continue
            reached = h.tongue_offset(point.arc, point)
            if reached is None:  # outside the tongue's span, e.g. the lips
                continue
            if abs(reached - point.offset) > 1e-9:
                short.append(
                    (phone, round(point.arc, 3), round(point.offset - reached, 4))
                )
    assert not short, f"{head_name}: articulator short of target for {short[:6]}"


def test_a_click_closes_twice() -> None:
    """A click holds a front closure and a velar one at the same time.

    Drawn with only the place it names it is an ordinary stop wearing a
    velaric label: the pocket that makes the sound is the space between the
    two closures, so one of them is not optional.
    """
    ipa = IPAFeatures()
    clicks = [
        p for p in ipa.phones if ipa.get_features(p).get("airstream") == "velaric"
    ]
    assert clicks, "no clicks in the inventory to check"
    for phone in clicks:
        points = constrictions(ipa, ipa.get_features(phone))
        arcs = sorted(q.arc for q in points if q.arc is not None)
        assert len(points) >= 2, f"{phone}: only {len(points)} constriction(s)"
        assert arcs[-1] >= 0.45 - 1e-9, f"{phone}: no velar closure, arcs {arcs}"
        assert all(
            q.offset is not None and q.offset >= 0.995 for q in points
        ), f"{phone}: a click's closures must be complete"
