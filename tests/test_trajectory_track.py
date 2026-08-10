"""The view-free trajectory, its wire, and measured-clock sampling."""

from __future__ import annotations

import hashlib
import math

import pytest
from ipakit.form import FormBuilder
from ipakit.tract import head, trajectory, trajectory_from_track
from ipakit.tract_svg import animate

LEGACY_ANIMATION_SHA256 = {
    "sũn": "a3908e6698eb12bc2a3abbfefcb30bc291cac6aeab3fe5530341192e17906bb1",
    "ˈkæt": "ac707f1dd2e9dc85e234cd42f75a1ccf321167ae96c53ee62b409dda889637e9",
}


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
    assert len(value.frames) == math.ceil(0.9 * 20) + 2
    assert trajectory_from_track(value.to_track()) == value


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
