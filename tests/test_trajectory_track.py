"""The view-free trajectory, its wire, and measured-clock sampling."""

from __future__ import annotations

import hashlib
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from ipakit.form import FormBuilder
from ipakit.tract import TRACK_VERSION, head, trajectory, trajectory_from_track
from ipakit.tract_svg import animate, animate_two_pane

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
    3: (
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
        "epiglottal",
    ),
}

ANIMATION_SHA256 = json.loads(
    (Path(__file__).parent / "fixtures" / "animation_sha256.json").read_text()
)


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


@pytest.mark.parametrize("other_version", [None, 1, 2, 4, "3"])
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
    assert hashlib.sha256(animate(word).encode()).hexdigest() == ANIMATION_SHA256[word]


def _transcript_units(page: str) -> list[str]:
    return re.findall(r'<span class="unit"[^>]*>(.*?)</span>', page)


def _active_units(page: str) -> list[tuple[int, ...]]:
    return [
        tuple(int(index) for index in value.split())
        for value in re.findall(r'data-active-units="([^"]*)"', page)
    ]


class _DisplayLabelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_label = False
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "span" and ("class", "display-label") in attrs:
            self.in_label = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.in_label:
            self.in_label = False

    def handle_data(self, data: str) -> None:
        if self.in_label:
            self.text.append(data)


@pytest.mark.parametrize("renderer", [animate, animate_two_pane])
def test_transcript_has_exact_units_and_optional_display_label(renderer) -> None:
    value = trajectory("ˈkæt", head=head(), frames_per_unit=2)
    plain = renderer(value)
    labeled = renderer(value, display_label="cat & kitten")

    assert _transcript_units(plain) == list(value.units)
    assert _transcript_units(labeled) == list(value.units)
    assert 'class="display-label"' not in plain
    assert '<span class="display-label">cat &amp; kitten</span>' in labeled
    assert re.findall(r'<path\b[^>]*\bd="[^"]*"', plain) == re.findall(
        r'<path\b[^>]*\bd="[^"]*"', labeled
    )


@pytest.mark.parametrize("renderer", [animate, animate_two_pane])
def test_display_label_printable_text_and_lf_survive_html_parsing(renderer) -> None:
    label = 'A <tag> & "quotes"\nnaïve ɪ̯'
    parser = _DisplayLabelParser()

    parser.feed(renderer("a", display_label=label))

    assert "".join(parser.text) == label


@pytest.mark.parametrize("renderer", [animate, animate_two_pane])
@pytest.mark.parametrize(
    ("label", "codepoint"),
    [
        ("A\x00B\rC", "0000"),
        ("A\tB", "0009"),
        ("A\rB", "000D"),
        ("A\x1fB", "001F"),
        ("A\x7fB", "007F"),
        ("A\x80B", "0080"),
        ("A\x9fB", "009F"),
    ],
)
def test_display_label_refuses_controls_instead_of_rewriting(
    renderer, label: str, codepoint: str
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"display_label contains control character U\+{codepoint}",
    ):
        renderer("a", display_label=label)


@pytest.mark.parametrize("renderer", [animate, animate_two_pane])
def test_transcript_highlights_follow_trajectory_dominance(renderer) -> None:
    value = trajectory("kat", head=head(), frames_per_unit=2)
    hold = value.frames_per_unit
    expected = (
        [value.dominant_unit_indices(value.ordinals[0])] * hold
        + [value.dominant_unit_indices(t) for t in value.ordinals]
        + [value.dominant_unit_indices(value.ordinals[-1])] * hold
    )

    assert _active_units(renderer(value)) == expected
    midpoint = value.ordinals.index(1.5)
    assert value.dominant_unit_indices(value.ordinals[midpoint]) == (0, 1)
    assert value.unit_extents == ((0.5, 1.5), (1.5, 2.5), (2.5, 3.5))


def test_timed_two_pane_transcript_uses_sampled_ordinals_and_silent_ramps() -> None:
    value = trajectory(
        _timed_form((0.0, 0.2), (0.2, 0.4), (0.6, 0.2)),
        head=head(),
        fps=20,
    )
    ramp_frames = round(0.20 * value.fps)
    rendered = _active_units(animate_two_pane(value))

    assert rendered[:ramp_frames] == [()] * ramp_frames
    assert rendered[-ramp_frames:] == [()] * ramp_frames
    assert rendered[ramp_frames:-ramp_frames] == [
        value.dominant_unit_indices(t) for t in value.ordinals
    ]
    boundary = next(
        index for index, stamp in enumerate(value.stamps) if math.isclose(stamp, 0.2)
    )
    assert rendered[ramp_frames + boundary] == (0, 1)


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
