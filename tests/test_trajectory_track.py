"""The view-free trajectory, its wire, and measured-clock sampling."""

from __future__ import annotations

import hashlib
import json
import math

import pytest
from ipakit.form import FormBuilder
from ipakit.tract import TRACK_VERSION, head, trajectory, trajectory_from_track
from ipakit.tract_svg import animate

TRACK_PARAMETERS_BY_VERSION = {
    2: (
        "reading",
        "rest",
        "constrictions",
        "velic",
        "glottal",
        "secondary",
        "unmodelled",
        "aperture_width",
        "protrusion",
        "implied",
        "rest_weight",
        "tongue_controls",
    ),
}

LEGACY_ANIMATION_SHA256 = {
    # The velum-carried tongue occlusion changes with every posture; track
    # round trips must retain the complete rendered result byte-for-byte.
    "sũn": "4b0e6e09c880cc706fc2cf068c7ea8ee222a8f10421efe01ab3a3a280847e529",
    "ˈkæt": "846fddb6b9e66b6cd4e7ced6d1ff83bf9b4ab66ba66958555d88c417da386566",
}


def test_track_parameters_belong_to_the_current_wire_version() -> None:
    """Make every serialized parameter change move the track version.

    The table records each parameter list against the stamp that identifies
    it: changing the live list under an existing stamp fails, while a new
    stamp has to gain its own entry.  A bare snapshot of today's list would
    not provide that coupling because it could be refreshed without moving
    the version.
    """
    document = json.loads(trajectory("kat", head=head()).to_track())

    assert document["v"] == TRACK_VERSION
    assert tuple(document["parameters"]) == TRACK_PARAMETERS_BY_VERSION[TRACK_VERSION]


@pytest.mark.parametrize("other_version", [None, 1, 3, "2"])
def test_track_reader_refuses_every_other_version(other_version: object) -> None:
    document = json.loads(trajectory("kat", head=head()).to_track())
    document["v"] = other_version

    with pytest.raises(ValueError, match="unsupported track version"):
        trajectory_from_track(json.dumps(document))


@pytest.mark.parametrize("word", ["sũn", "ˈkæt"])
def test_track_round_trip_and_render_identity(word: str) -> None:
    live = trajectory(word, head=head())
    loaded = trajectory_from_track(live.to_track())
    assert loaded == live
    assert loaded.to_track() == live.to_track()
    assert animate(loaded) == animate(word)
    assert (
        hashlib.sha256(animate(word).encode()).hexdigest()
        == LEGACY_ANIMATION_SHA256[word]
    )


def _timed_form(*spans: tuple[float, float]):
    builder = FormBuilder()
    handles = builder.append_ipa("kat")
    for handle, (start, duration) in zip(handles, spans, strict=True):
        builder.attach_timing(handle, start, duration)
    return builder.build()


def test_measured_boundaries_are_samples_and_count_tracks_fps() -> None:
    form = _timed_form((0.1, 0.2), (0.3, 0.4), (0.7, 0.3))
    value = trajectory(form, head=head(), fps=20)
    for boundary in (0.1, 0.3, 0.7, 1.0):
        assert any(math.isclose(stamp, boundary) for stamp in value.stamps)
    assert len(value.frames) == math.ceil(0.9 * 20) + 1
    assert trajectory_from_track(value.to_track()) == value


@pytest.mark.parametrize("anchor", ["center", "onset"])
def test_timed_trajectory_covers_exactly_the_measured_window(anchor: str) -> None:
    value = trajectory(
        _timed_form((0.1, 0.2), (0.3, 0.4), (0.7, 0.3)),
        head=head(),
        fps=20,
        anchor=anchor,
    )
    assert len(value.stamps) == len(value.ordinals) == len(value.frames)
    assert math.isclose(value.stamps[0], 0.1)
    assert math.isclose(value.stamps[-1], 1.0)
    assert not any(
        math.isclose(left, right)
        for left, right in zip(value.stamps, value.stamps[1:], strict=False)
    )
    assert all(
        left < right
        for left, right in zip(value.ordinals, value.ordinals[1:], strict=False)
    )
    assert len(dict(zip(value.stamps, value.ordinals, strict=True))) == len(
        value.stamps
    )


@pytest.mark.parametrize("fps", [10, 20, 30])
@pytest.mark.parametrize("anchor", ["center", "onset"])
def test_grid_sample_is_deduplicated_against_measured_end(
    fps: int, anchor: str
) -> None:
    form = _timed_form((0.0, 0.1), (0.1, 0.1), (0.2, 0.1))
    value = trajectory(form, head=head(), fps=fps, anchor=anchor)
    end = form.units[-1].timing.end
    assert value.stamps[-1] == end
    assert not any(
        math.isclose(left, right)
        for left, right in zip(value.stamps, value.stamps[1:], strict=False)
    )
    assert all(
        left < right
        for left, right in zip(value.ordinals, value.ordinals[1:], strict=False)
    )


def _ordinal_at(value, stamp: float) -> float:
    return next(
        ordinal
        for ordinal, sampled in zip(value.ordinals, value.stamps, strict=True)
        if math.isclose(sampled, stamp)
    )


def test_center_anchor_puts_centers_on_units_and_boundaries_between() -> None:
    form = _timed_form((0.1, 0.2), (0.3, 0.4), (0.7, 0.3))
    value = trajectory(form, head=head(), fps=20)
    for ordinal, center in ((1.0, 0.2), (2.0, 0.5), (3.0, 0.85)):
        assert math.isclose(_ordinal_at(value, center), ordinal)
    for ordinal, boundary in ((1.5, 0.3), (2.5, 0.7)):
        assert math.isclose(_ordinal_at(value, boundary), ordinal)
    assert value.anchor == "center"


def test_onset_anchor_reproduces_original_timed_warp() -> None:
    spans = ((0.1, 0.2), (0.3, 0.4), (0.7, 0.3))
    value = trajectory(_timed_form(*spans), head=head(), fps=20, anchor="onset")
    for ordinal, stamp in zip(value.ordinals, value.stamps, strict=True):
        index = next(
            i
            for i, (start, duration) in enumerate(spans)
            if stamp <= start + duration or i == len(spans) - 1
        )
        start, duration = spans[index]
        assert math.isclose(ordinal, 1.0 + index + (stamp - start) / duration)
    assert trajectory_from_track(value.to_track()).anchor == "onset"


def test_anchor_refusals_are_explicit() -> None:
    with pytest.raises(ValueError, match="only valid for a timed Form"):
        trajectory("kat", head=head(), anchor="center")
    with pytest.raises(ValueError, match="'center' or 'onset'"):
        trajectory(
            _timed_form((0.0, 0.2), (0.2, 0.2), (0.4, 0.2)),
            head=head(),
            fps=20,
            anchor="coda",
        )


@pytest.mark.parametrize(
    "spans, message",
    [
        (((0.0, 0.2), (0.2, 0.0), (0.2, 0.2)), "zero duration"),
        (((0.0, 0.3), (0.2, 0.2), (0.4, 0.2)), "overlaps"),
    ],
)
def test_degenerate_measured_timing_refuses(spans, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        trajectory(_timed_form(*spans), head=head(), fps=20)


def test_track_missing_key_uses_codec_refusal() -> None:
    document = json.loads(trajectory("kat", head=head()).to_track())
    del document["provenance"]["source"]
    with pytest.raises(ValueError, match="missing required key 'source'"):
        trajectory_from_track(json.dumps(document))


def test_track_posture_requires_tongue_controls() -> None:
    document = json.loads(trajectory("kat", head=head()).to_track())
    del document["frames"][0]["posture"]["tongue_controls"]
    with pytest.raises(ValueError, match="missing required key 'tongue_controls'"):
        trajectory_from_track(json.dumps(document))
