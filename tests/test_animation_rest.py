"""Regression pins for the closed-rest, target-to-target kæt player."""

from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

from ipakit.features import IPAFeatures
from ipakit.tract import constrictions, head, landmarks, posture, trajectory
from ipakit.tract_svg import (
    SAMPLES,
    _pose,
    build_frontal_geometry,
    build_geometry,
    figure,
    frontal_svg,
    section_svg,
)

from tests.test_tract_figures import _differing, _pixels


def _offset(frame, articulator: str) -> float:
    return next(q.offset for q in frame.constrictions if q.articulator == articulator)  # type: ignore[return-value]


def test_declared_rest_is_exactly_closed_and_velically_lowered() -> None:
    ipa, h = IPAFeatures(), head("adult-male")
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
    marks = landmarks(ipa)
    for frame in (track.frames[0], track.frames[-1]):
        assert frame.rest_weight == 1.0
        assert frame.velic == 1.0
        front = build_frontal_geometry(h, marks, frame)
        assert front["closed"]
        assert "f-aperture" not in frontal_svg(front)
        side = build_geometry(h, marks, frame)
        assert side["lips_closed_now"]
        assert "lower-lip shut" in section_svg(side, None, frame.velic, _pose(frame))


def test_k_to_ash_has_no_global_rest_trough() -> None:
    track = trajectory("kæt", head=head(), frames_per_unit=12)
    # Ordinals 1 and 2 are /k/ and /æ/. The dorsum must remain between those
    # posture targets throughout; 0.002 admits only float/sampling noise.
    span = [f for o, f in zip(track.ordinals, track.frames, strict=True) if 1 <= o <= 2]
    targets = (_offset(span[0], "tongue-dorsum"), _offset(span[-1], "tongue-dorsum"))
    lo, hi = min(targets), max(targets)
    assert all(
        lo - 0.002 <= _offset(frame, "tongue-dorsum") <= hi + 0.002 for frame in span
    )
    readings = [frame.reading.offset for frame in span if frame.reading is not None]
    assert readings == sorted(readings, reverse=True)


def test_ash_spreads_beyond_neutral_i_by_declaration() -> None:
    ipa, h = IPAFeatures(), head()
    ash = posture(ipa, "æ", h)
    neutral = posture(ipa, "i", h)
    assert ash.aperture_width == 1.14
    assert neutral.aperture_width == 1.0
    assert math.isclose(ash.aperture_width - neutral.aperture_width, 0.14)


def test_sagittal_upper_lip_is_a_painted_named_body() -> None:
    svg = figure("a")
    assert svg.count("upper-lip") == 1
    assert re.search(r'<path[^>]+class="lip upper-lip"', svg)


def test_sagittal_upper_lip_contributes_raster_pixels(tmp_path: Path) -> None:
    if shutil.which("rsvg-convert") is None:
        return
    svg = figure("a")
    without, removed = re.subn(r'<path[^>]+class="lip upper-lip"/>', "", svg, count=1)
    assert removed == 1
    width, painted = _pixels(svg, tmp_path / "upper-lip.svg", width=760)
    _, absent = _pixels(without, tmp_path / "without-upper-lip.svg", width=760)
    assert len(_differing(width, painted, absent)) > 20


def test_every_kaet_frame_keeps_root_anchor_and_respects_active_tip() -> None:
    ipa, h = IPAFeatures(), head()
    marks = landmarks(ipa)
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
    tolerance = 1.0 / 240
    for frame in track.frames:
        geometry = build_geometry(h, marks, frame)
        surface = geometry["tongue"]
        assert surface
        active_tip = min(
            (
                q.arc
                for q in frame.constrictions
                if q.articulator == "tongue-tip" and q.arc is not None
            ),
            default=None,
        )
        expected = h.tongue_span[0] if active_tip is None else active_tip
        assert surface[0][0] >= expected - tolerance - 1e-12
        # The posterior taper is the sewn floor/root anchor in the same live
        # jaw-carried geometry; it must coincide in every frame.
        root = surface[-1]
        floor = min(geometry["rows"], key=lambda row: abs(row["arc"] - root[0]))["open"]
        assert abs(root[1] - floor[0]) <= 1e-9
        assert abs(root[2] - floor[1]) <= 1e-9


def test_closed_rest_seats_declared_tip_at_declared_ridge() -> None:
    ipa, h = IPAFeatures(), head()
    assert h.rest is not None
    ridge = next(point for point in h.midline if point.provenance == "measured")
    assert h.rest.tip_arc == ridge.arc
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
    for frame in (track.frames[0], track.frames[-1]):
        geometry = build_geometry(h, landmarks(ipa), frame)
        front = geometry["tongue"][0]
        assert h.rest.tip_arc - 1.0 / SAMPLES <= front[0] <= h.rest.tip_arc
        row = min(geometry["rows"], key=lambda item: abs(item["arc"] - front[0]))
        assert math.hypot(front[1] - row["wall"][0], front[2] - row["wall"][1]) < 1e-4


def test_static_and_animated_rest_draw_the_same_declared_tongue() -> None:
    ipa, h = IPAFeatures(), head()
    static = posture(ipa, "␣", h)
    animated = trajectory("kæt", head=h, frames_per_unit=12, features=ipa).frames[0]
    assert static.tongue_controls == animated.tongue_controls
    assert (
        build_geometry(h, landmarks(ipa), static)["tongue"]
        == build_geometry(h, landmarks(ipa), animated)["tongue"]
    )
    assert static.tongue_controls
    assert 'class="tongue"' in figure("␣")


def test_silence_keeps_rest_controls_out_of_phonetic_constrictions() -> None:
    ipa, h = IPAFeatures(), head()
    assert h.rest is not None
    silence = posture(ipa, "␣", h)
    bundle = ipa.get_features("␣")
    assert silence.constrictions == ()
    assert not any(point.placed for point in constrictions(ipa, bundle))
    assert silence.tongue_controls == h.rest.tongue_controls


def test_k_target_is_legible_without_a_new_plateau() -> None:
    track = trajectory("kæt", head=head(), frames_per_unit=12)
    near_k = [
        _offset(frame, "tongue-dorsum")
        for ordinal, frame in zip(track.ordinals, track.frames, strict=True)
        if abs(ordinal - 1.0) <= 1 / 12 + 1e-12
    ]
    # Three consecutive frames (105 ms at the declared 420 ms/unit playback)
    # retain at least 96% closure after the target-to-target change.
    assert len(near_k) == 3
    assert min(near_k) >= 0.96
