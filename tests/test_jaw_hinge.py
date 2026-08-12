"""Pins for the mandible's declared rigid hinge."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from ipakit.features import IPAFeatures
from ipakit.tract import Head, TractPoint, head, heads, landmarks, posture
from ipakit.tract_svg import build_geometry, figure

TOLERANCE = 1e-12


def _attachment_to_tooth_spread(shape: Head, *, graded: bool = False) -> float:
    """Measure rendered attachment rigidity while holding tongue pose fixed."""
    control = TractPoint(arc=0.50, offset=0.55, articulator="tongue-body")
    tooth_arc = 0.045
    tooth = shape.project(TractPoint(arc=tooth_arc, offset=0.0))
    assert tooth is not None
    distances = []
    for step in range(101):
        close = step / 100
        if graded:
            attachment = shape.tongue_point(shape.tongue_attachment_arc, control, close)
            assert attachment is not None
            moved_tooth = shape.carried(tooth, tooth_arc, close)
        else:
            attachment = shape.tongue_point(shape.tongue_attachment_arc, control, close)
            assert attachment is not None
            moved_tooth = shape.rotate_jaw(tooth, close)
        distances.append(math.dist(moved_tooth, attachment))
    return max(distances) - min(distances)


def test_attachment_is_rigid_with_mandible_across_closure_sweep() -> None:
    assert _attachment_to_tooth_spread(head("adult-male")) <= TOLERANCE


def test_rigidity_pin_rejects_graded_attachment_membership() -> None:
    """Revert full carriage in memory and prove the rigidity pin fails."""
    shape = head("adult-male")
    graded = replace(shape, tongue_attachment_carrier="soft-tissue")
    assert shape.jaw_carriage(shape.tongue_attachment_arc) == pytest.approx(
        0.42615384615384616
    )
    assert _attachment_to_tooth_spread(graded, graded=True) == pytest.approx(
        4.291e-4, abs=5e-8
    )


def test_fixed_points_do_not_move_and_membership_still_grades() -> None:
    shape = head("adult-male")
    point = (0.45, 0.50)
    assert shape.jaw_carriage(1.0) == 0.0
    assert shape.carried(point, 1.0, 1.0) == point
    full = math.dist(point, shape.rotate_jaw(point, 1.0))
    partial = math.dist(point, shape.carried(point, 0.32, 1.0))
    assert 0.0 < partial < full
    assert partial == pytest.approx(full * shape.jaw_carriage(0.32), abs=TOLERANCE)


def test_hinge_and_tongue_attachment_are_declared_and_drawn() -> None:
    for shape in heads().values():
        assert shape.hinge is not None
        assert shape.hinge_provenance is not None
        assert (
            "provisional AABB proxy, not a measured condyle" in shape.hinge_provenance
        )
        assert shape.tongue_attachment_arc == pytest.approx(0.08)
        assert shape.tongue_attachment_carrier == "mandible"
    shape = head("adult-male")
    ipa = IPAFeatures()
    geometry = build_geometry(shape, landmarks(ipa), posture(ipa, "a", shape))
    assert geometry["hinge"] == shape.hinge
    assert 'class="jawhinge"' in figure("a", shape.name)
