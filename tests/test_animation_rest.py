"""Regression pins for the closed-rest, target-to-target kæt player."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from ipakit.features import IPAFeatures
from ipakit.form import FormBuilder
from ipakit.tract import constrictions, head, landmarks, posture, trajectory
from ipakit.tract_svg import (
    _pose,
    build_frontal_geometry,
    build_geometry,
    figure,
    frontal_svg,
    section_svg,
)

from tests._renderers import require_renderer
from tests.test_tract_figures import _alpha_pixels, _differing, _pixels


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


def test_static_silence_and_animation_bookends_share_declared_velic_rest() -> None:
    ipa, h = IPAFeatures(), head("adult-male")
    silence = posture(ipa, "␣", h)
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
    assert silence.velic == track.frames[0].velic == track.frames[-1].velic == 1.0


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
    require_renderer("rsvg-convert", "the raster claim is unmeasured here")
    svg = figure("a")
    without, removed = re.subn(r'<path[^>]+class="lip upper-lip"/>', "", svg, count=1)
    assert removed == 1
    width, painted = _pixels(svg, tmp_path / "upper-lip.svg", width=760)
    _, absent = _pixels(without, tmp_path / "without-upper-lip.svg", width=760)
    assert len(_differing(width, painted, absent)) > 20


def _raster_lip_gap(frame, tmp_path: Path, stem: str) -> int:
    """Transparent pixels on the shortest 8-connected route between lips."""
    h, marks = head(), landmarks(IPAFeatures())
    rendered = section_svg(
        build_geometry(h, marks, frame), None, frame.velic, _pose(frame)
    )
    paths = re.findall(
        r'<path d="([^"]+)" class="lip (?:upper|lower)-lip(?: shut)?"/>', rendered
    )
    assert len(paths) == 2
    pixels = []
    for index, path in enumerate(paths):
        isolated = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 560">'
            "<style>.lip{fill:#fff;stroke:#fff;stroke-width:1.4;"
            "stroke-linejoin:round}</style>"
            f'<path d="{path}" class="lip"/></svg>'
        )
        width, rows = _pixels(isolated, tmp_path / f"{stem}-{index}.svg", width=760)
        pixels.append(_alpha_pixels(width, rows, threshold=127))
    upper, lower = pixels
    distance = min(
        max(abs(ax - bx), abs(ay - by)) for ax, ay in upper for bx, by in lower
    )
    return max(0, distance - 1)


@pytest.mark.parametrize("phone", ["b", "p", "m"])
@pytest.mark.parametrize("fps", [3, 5, 12, 20])
@pytest.mark.parametrize("duration", [0.15, 0.20, 0.30, 0.40])
def test_timed_bilabial_reaches_continuous_raster_contact(
    phone: str, fps: int, duration: float, tmp_path: Path
) -> None:
    """Even an off-grid timed target reaches contact, without a body swap."""
    require_renderer("rsvg-convert", "the raster claim is unmeasured here")
    builder = FormBuilder()
    handles = builder.append_ipa(f"a{phone}a")
    for index, handle in enumerate(handles):
        builder.attach_timing(handle, index * duration, duration)
    track = trajectory(builder.build(), head=head(), fps=fps)
    span = [
        (ordinal, frame)
        for ordinal, frame in zip(track.ordinals, track.frames, strict=True)
        if 1.5 <= ordinal <= 2.5
    ]
    gaps = [
        _raster_lip_gap(frame, tmp_path, f"{phone}-{index}")
        for index, (_, frame) in enumerate(span)
    ]
    center = next(index for index, (ordinal, _) in enumerate(span) if ordinal == 2.0)
    static_contact = _raster_lip_gap(
        posture(IPAFeatures(), phone, head()), tmp_path, f"{phone}-static"
    )
    assert span[center][1].reading == track.postures[1].reading
    assert gaps[center] == static_contact
    assert gaps[: center + 1] == sorted(gaps[: center + 1], reverse=True)
    assert gaps[center:] == sorted(gaps[center:])
    if fps == 20 and duration == 0.40:
        assert all(a - b <= 16 for a, b in zip(gaps, gaps[1:], strict=False))


def test_timed_bilabial_center_survives_a_large_absolute_start(
    tmp_path: Path,
) -> None:
    """Candidate deduplication cannot discard a target center by clock scale."""
    require_renderer("rsvg-convert", "the raster claim is unmeasured here")
    builder = FormBuilder()
    handles = builder.append_ipa("aba")
    start = 1e9
    duration = 0.20
    for index, handle in enumerate(handles):
        builder.attach_timing(handle, start + index * duration, duration)
    track = trajectory(builder.build(), head=head(), fps=5)
    center = min(range(len(track.ordinals)), key=lambda i: abs(track.ordinals[i] - 2.0))
    assert track.stamps[center] == start + duration + duration / 2.0
    assert _raster_lip_gap(track.frames[center], tmp_path, "large-start-b") == 0


@pytest.mark.parametrize(
    ("word", "bilabial_index"),
    [
        ("amfa", 1),
        ("maf", 0),
        ("fam", 2),
        ("mɱ", 0),
        ("ɱm", 1),
        ("abva", 1),
        ("avba", 2),
    ],
)
def test_labiodental_context_cannot_move_bilabial_contact_place(
    word: str, bilabial_index: int, tmp_path: Path
) -> None:
    """A distant or adjacent lower-lip place cannot dilute a bilabial target."""
    require_renderer("rsvg-convert", "the raster claim is unmeasured here")
    ipa, h = IPAFeatures(), head()
    frames_per_unit = 100
    track = trajectory(word, head=h, frames_per_unit=frames_per_unit, features=ipa)
    frame = track.frames[(bilabial_index + 1) * frames_per_unit]
    static = track.postures[bilabial_index]
    assert _raster_lip_gap(frame, tmp_path, f"{word}-bilabial") == _raster_lip_gap(
        static, tmp_path, f"{word}-static"
    )
    lower = next(q for q in frame.constrictions if q.articulator == "lower-lip")
    assert lower.arc == 0.0
    centers = range(
        frames_per_unit, len(track.frames) - frames_per_unit, frames_per_unit
    )
    neighborhoods = [
        [
            _raster_lip_gap(track.frames[index], tmp_path, f"{word}-curve-{index}")
            for index in (center - 1, center, center + 1)
        ]
        for center in centers
    ]
    assert (
        max(
            abs(a - b)
            for gaps in neighborhoods
            for a, b in zip(gaps, gaps[1:], strict=False)
        )
        <= 3
    )


@pytest.mark.parametrize("phone", ["f", "v", "ɱ", "ʋ"])
def test_labiodental_target_remains_apart_in_bilabial_context(
    phone: str, tmp_path: Path
) -> None:
    """Fixing the bilabial target does not turn labiodentals into contact."""
    require_renderer("rsvg-convert", "the raster claim is unmeasured here")
    ipa, h = IPAFeatures(), head()
    frame = trajectory(f"m{phone}", head=h, frames_per_unit=8, features=ipa).frames[16]
    # Measured gaps f/v/ɱ/ʋ = 25/25/21/31 px under centered rests; contact is 0.
    assert _raster_lip_gap(frame, tmp_path, f"{phone}-context") > 12


def test_every_kaet_frame_keeps_declared_front_until_a_tip_closure() -> None:
    ipa, h = IPAFeatures(), head()
    marks = landmarks(ipa)
    track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
    closure_threshold = h.tongue_closure_threshold
    for frame in track.frames:
        geometry = build_geometry(h, marks, frame)
        surface = geometry["tongue"]
        assert surface
        tip = next(
            (q for q in frame.constrictions if q.articulator == "tongue-tip"),
            None,
        )
        assert h.tongue_span is not None
        if tip is None or tip.offset is None or tip.offset < closure_threshold:
            assert surface[0][0] == h.tongue_span[0]
        # The posterior taper is the sewn floor/root anchor in the same live
        # jaw-carried geometry; it must coincide in every frame.
        root = surface[-1]
        floor = min(geometry["rows"], key=lambda row: abs(row["arc"] - root[0]))["open"]
        assert abs(root[1] - floor[0]) <= 1e-9
        assert abs(root[2] - floor[1]) <= 1e-9


def test_every_head_declares_the_tip_closure_separator() -> None:
    assert {
        name: head(name).tongue_closure_threshold
        for name in ("adult-male", "adult-female", "child")
    } == {"adult-male": 0.60, "adult-female": 0.60, "child": 0.60}


def test_closed_rest_seats_declared_tip_at_declared_ridge() -> None:
    ipa = IPAFeatures()
    for name in ("adult-male", "adult-female", "child"):
        h = head(name)
        assert h.rest is not None
        # The adults use their measured palate front/alveolar-ridge point.
        # The child has no measurements: its rest tip uses its frontmost
        # declared palate landmark, which is hand-placed at arc 0.13.
        declared_front = h.midline[1]
        assert h.rest.tip_arc == declared_front.arc
        if name == "child":
            assert declared_front.provenance == "hand-placed"
        else:
            assert declared_front.provenance == "measured"
        track = trajectory("kæt", head=h, frames_per_unit=12, features=ipa)
        for frame in (track.frames[0], track.frames[-1]):
            geometry = build_geometry(h, landmarks(ipa), frame)
            front = geometry["tongue"][0]
            assert front[0] == h.tongue_span[0]
            tip = min(
                geometry["tongue"], key=lambda item: abs(item[0] - h.rest.tip_arc)
            )
            row = min(geometry["rows"], key=lambda item: abs(item["arc"] - tip[0]))
            assert math.hypot(tip[1] - row["wall"][0], tip[2] - row["wall"][1]) < 1e-4


def _front_steps(track, h) -> list[float]:
    marks = landmarks(IPAFeatures())
    fronts = []
    for frame in track.frames:
        surface = build_geometry(h, marks, frame)["tongue"]
        fronts.append(surface[0][0])
    return [abs(b - a) for a, b in zip(fronts, fronts[1:], strict=False)]


def test_kaet_tongue_front_step_shrinks_with_frame_spacing() -> None:
    """Rate refinement, not a fitted absolute bound, characterizes continuity."""
    h = head("adult-male")
    rates = (1, 4, 8, 12, 24)
    steps = [
        max(_front_steps(trajectory("kæt", head=h, frames_per_unit=rate), h))
        for rate in rates
    ]
    assert all(
        finer < coarser for coarser, finer in zip(steps, steps[1:], strict=False)
    )
    assert all(step <= 0.21 / rate for rate, step in zip(rates, steps, strict=True))


def test_timed_tongue_front_step_shrinks_with_frame_spacing() -> None:
    builder = FormBuilder()
    handles = builder.append_ipa("kat")
    for handle, start in zip(handles, (0.0, 0.42, 0.84), strict=True):
        builder.attach_timing(handle, start, 0.42)
    form, h = builder.build(), head("adult-male")
    rates = (20, 30, 60)
    steps = [max(_front_steps(trajectory(form, head=h, fps=rate), h)) for rate in rates]
    assert all(
        finer < coarser for coarser, finer in zip(steps, steps[1:], strict=False)
    )
    assert all(step <= 1.0 / rate for rate, step in zip(rates, steps, strict=True))


def test_tip_closure_emits_the_coincident_front_once() -> None:
    h = head("adult-male")
    surface = build_geometry(
        h, landmarks(IPAFeatures()), posture(IPAFeatures(), "t", h)
    )["tongue"]
    assert all(a[0] < b[0] for a, b in zip(surface, surface[1:], strict=False))


def test_k_onset_opening_frames_have_no_phantom_tip_closure() -> None:
    track = trajectory("kæt", head="adult-male", frames_per_unit=12)
    opening = [
        frame
        for ordinal, frame in zip(track.ordinals, track.frames, strict=True)
        if ordinal <= 1.0
    ]
    assert opening
    tips = [
        point
        for frame in opening
        for point in frame.constrictions
        if point.articulator == "tongue-tip"
    ]
    # The later /t/ may contribute its open, implied tip target this early; the
    # resting drawing tip must not turn that phonetic field into a closure.
    assert all(point.offset is not None and point.offset < 0.2 for point in tips)


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
