"""Pins for the mandible's declared rigid hinge."""

from __future__ import annotations

import math

import pytest
from ipakit.features import IPAFeatures
from ipakit.tract import TractPoint, head, heads, landmarks, posture
from ipakit.tract_svg import build_geometry, figure

TOLERANCE = 1e-12


def _mandibular_landmarks(close: float) -> dict[str, tuple[float, float]]:
    shape = head("adult-male")
    points = {
        name: (x, y) for name, x, y, carrier in shape.teeth if carrier == "mandible"
    }
    attachment = shape.project(TractPoint(shape.tongue_attachment_arc, 0.0))
    assert attachment is not None
    points["tongue-attachment"] = attachment
    return {name: shape.rotate_jaw(point, close) for name, point in points.items()}


def test_mandibular_distances_are_invariant_across_the_full_rotation() -> None:
    baseline = _mandibular_landmarks(0.0)
    for close in (0.25, 0.5, 0.75, 1.0):
        moved = _mandibular_landmarks(close)
        for left, a in baseline.items():
            for right, b in baseline.items():
                assert math.dist(moved[left], moved[right]) == pytest.approx(
                    math.dist(a, b), abs=TOLERANCE
                )


def test_legacy_per_arc_lift_breaks_tooth_to_attachment_rigidity() -> None:
    """Keep the old mechanism as the discriminating negative control."""
    shape = head("adult-male")
    attachment = shape.project(TractPoint(shape.tongue_attachment_arc, 0.0))
    assert attachment is not None
    tooth = next(
        (x, y)
        for name, x, y, carrier in shape.teeth
        if name == "lower-arch" and carrier == "mandible"
    )

    def legacy(point: tuple[float, float], arc: float) -> tuple[float, float]:
        roof = shape.project(TractPoint(arc, 1.0))
        floor = shape.project(TractPoint(arc, 0.0))
        assert roof is not None and floor is not None
        share = shape.jaw_carriage(arc)
        return (
            point[0] + (roof[0] - floor[0]) * share,
            point[1] + (roof[1] - floor[1]) * share,
        )

    open_distance = math.dist(tooth, attachment)
    legacy_closed = math.dist(legacy(tooth, 0.045), legacy(attachment, 0.08))
    assert open_distance == pytest.approx(0.039293652, abs=5e-10)
    assert legacy_closed == pytest.approx(0.031374227, abs=5e-10)
    assert abs(legacy_closed - open_distance) > 0.007


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
    shape = head("adult-male")
    ipa = IPAFeatures()
    geometry = build_geometry(shape, landmarks(ipa), posture(ipa, "a", shape))
    assert geometry["hinge"] == shape.hinge
    assert 'class="jawhinge"' in figure("a", shape.name)
