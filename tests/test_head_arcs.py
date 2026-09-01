"""``arc`` is stated in two files, and until now nothing held them together.

``ipa.xml`` declares an ``arc`` on the values of ``place``, ``backness``
and ``articulator`` -- proportional position along the tract midline, 0
at the lips to 1 at the glottis. ``heads.xml`` states one again on every
polyline vertex and hand-places an ``(x, y)`` beside it. That is one
quantity written down three times, against the standing preference:
*make two things equal by construction rather than by vigilance, and pin
what a guard cannot see.*

Nothing is a wrong answer today, because ``ipakit.metric`` imports only
``tract_point`` from ``ipakit.tract`` and never reaches a head. The cost
is to the drawing and to the one external check the geometry has --
declared arcs compared against measured area functions -- which is only
meaningful while the two readings agree.

Three relationships, checked here on their own terms rather than folded
into one number:

* **A midline vertex names a declared arc.** Nine of the ten adult-male
  vertices are exactly values ``ipa.xml`` owns. Change ``place=velar``
  from 0.45 to 0.47 and the head keeps its 0.45 vertex: the drawing
  silently interpolates a spot that no longer means what it says, and
  nothing fails. This is the drift the issue predicted.
* **The arc column agrees with the coordinates.** It does not, by up to
  0.064. There is no useful bound to assert -- the smallest tolerance
  that passes is wider than the gap between adjacent declared places, so
  it would permit a vertex to sit where the next place over lives. The
  six numbers are pinned instead, which is the "pin the escapes" pattern
  and lets the disagreement move only on purpose.
* **Both readings ascend.** ``Head.project`` locates a point by scanning
  for the bracketing pair and interpolates the diameter across it, so a
  polyline that doubles back returns a position off the wall it is
  measured against.

The nasal branches are checked on the same footing as the midlines: same
attributes, same interpolation, same claim about their own arc. Leaving
them out would have reported a clean 0.062 over a file whose worst point
is 0.064 -- the largest disagreement in the shipped data is a nasal one,
on the child head, and neither the issue nor the assessment that raised
it had looked there.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.tract import TractPoint, heads

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import (
    ARCLENGTH_GAPS,
    UNDECLARED_VERTEX_ARCS,
    check_head_arcs,
)

FEATURES = IPAFeatures()


@pytest.fixture
def ipa() -> IPAFeatures:
    return FEATURES


def test_the_invariant_holds_over_the_shipped_heads(ipa: IPAFeatures) -> None:
    assert check_head_arcs(ipa)


def test_every_shipped_polyline_is_pinned() -> None:
    """A new head, or a new branch on one, must state its own gap.

    The pin is per polyline rather than a global maximum, so adding a
    head cannot hide behind an existing head's worse number.
    """
    shipped = {
        (name, label)
        for name, shape in heads().items()
        for label, points in (("midline", shape.midline), ("nasal", shape.nasal))
        if len(points) >= 2
    }
    assert shipped == set(ARCLENGTH_GAPS), sorted(shipped ^ set(ARCLENGTH_GAPS))
    assert len(shipped) >= 6, "sweep did not run"


def _patched(monkeypatch: pytest.MonkeyPatch, name: str, points: tuple) -> None:
    """Replace one head's midline, through the module the check reads."""
    import ipakit.tract as tract

    shapes = {k: v for k, v in heads().items()}
    shapes[name] = dataclasses.replace(shapes[name], midline=points)
    monkeypatch.setattr(tract, "heads", lambda: shapes)


def test_a_vertex_at_an_undeclared_arc_fails(
    ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cross-file half: an arc the head states and ipa.xml does not.

    This is what an edit to ``ipa.xml`` that the head does not follow
    looks like from the head's side, and it is the case that used to
    pass silently.
    """
    shape = heads()["adult-male"]
    moved = tuple(
        dataclasses.replace(p, arc=0.47) if p.arc == 0.45 else p for p in shape.midline
    )
    _patched(monkeypatch, "adult-male", moved)
    assert not check_head_arcs(ipa)


def test_a_moved_vertex_fails_the_pinned_gap(
    ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The internal half: coordinates edited, arc column left behind.

    The vertex keeps a declared arc, so the cross-file check still
    passes; only the arclength reading moves. A tolerance wide enough to
    ship would not have noticed this.
    """
    shape = heads()["adult-male"]
    moved = tuple(
        dataclasses.replace(p, x=p.x + 0.04) if p.arc == 0.32 else p
        for p in shape.midline
    )
    _patched(monkeypatch, "adult-male", moved)
    assert not check_head_arcs(ipa)


def test_a_polyline_that_doubles_back_fails(
    ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``project`` assumes both readings ascend; assert that they do."""
    shape = heads()["adult-male"]
    points = list(shape.midline)
    points[3] = dataclasses.replace(points[3], x=points[1].x, y=points[1].y)
    _patched(monkeypatch, "adult-male", tuple(points))
    assert not check_head_arcs(ipa)


def test_the_undeclared_vertices_are_the_ones_the_data_explains() -> None:
    """The stated escapes, and each is stated for a reason.

    ``heads.xml`` inserts them to carry the X-Ray Microbeam diameter run
    between declared anchors: 0.40 between the palatal and velar, and 0.11
    (the palate outline's front edge), 0.15, 0.17 and 0.21 across the front,
    where the measured arch needs samples no phonetic place sits on. If
    another such vertex appears, this fails and the reason has to be
    written down rather than absorbed.
    """
    assert UNDECLARED_VERTEX_ARCS == frozenset({0.11, 0.15, 0.17, 0.21, 0.40})
    carrying = {
        name
        for name, shape in heads().items()
        if any(p.arc in UNDECLARED_VERTEX_ARCS for p in shape.midline)
    }
    assert carrying == {"adult-male", "adult-female"}, sorted(carrying)


def test_adult_palates_project_to_the_declared_roof() -> None:
    """The wall is the roof outline, not midline plus aperture."""
    for shape in (heads()["adult-male"], heads()["adult-female"]):
        assert shape.roof
        for point in shape.roof:
            assert shape.project(
                TractPoint(arc=point.arc, offset=1.0)
            ) == pytest.approx((point.x, point.y))


def test_the_roof_apex_is_behind_the_aperture_peak() -> None:
    """The distinction that a diameter-only wall could not express."""
    for shape in (heads()["adult-male"], heads()["adult-female"]):
        roof_apex = max(shape.roof, key=lambda point: point.y)
        aperture_peak = max(shape.midline, key=lambda point: point.diameter)
        assert roof_apex.arc == pytest.approx(0.30)
        assert aperture_peak.arc == pytest.approx(0.24)
