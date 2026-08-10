"""PocketSphinx is live only in marked tests; conversion stays core-only."""

from __future__ import annotations

import json
import shutil
import sys
import wave
from pathlib import Path

import pytest
from ipakit import _corpus
from ipakit.align import _form_from_alignment, align, align_entry
from ipakit.form import Form, Timing

HERE = Path(__file__).parent / "fixtures" / "alignment"
RESULT = json.loads((HERE / "hello-world.json").read_text())
try:
    import pocketsphinx as _pocketsphinx  # noqa: F401
except ImportError:
    HAS_POCKETSPHINX = False
else:
    HAS_POCKETSPHINX = True


def _recorded_form() -> Form:
    return _form_from_alignment(RESULT["words"], frame_rate=float(RESULT["frame_rate"]))


def test_recorded_alignment_maps_through_cmu_and_uses_decoder_frame_rate() -> None:
    form = _recorded_form()
    assert form.to_ipa() == "hɛlo͜ʊwɚld"
    assert [unit.timing for unit in form.units[:3]] == [
        Timing(0.0, 0.07),
        Timing(0.07, 0.07),
        Timing(0.14, 0.06),
    ]
    assert [
        (span.tier, span.start, span.end, span.timing) for span in form.intervals
    ] == [
        ("word", 0, 4, Timing(0.0, 0.33)),
        ("word", 4, 8, Timing(0.33, 0.4)),
    ]


def test_stress_digit_uses_the_cmu_stress_path_and_lands_on_nucleus() -> None:
    words = json.loads(json.dumps(RESULT["words"][:1]))
    words[0]["phones"][1]["phone"] = "eh1"
    form = _form_from_alignment(words, frame_rate=100)
    assert form.to_ipa() == "hˈɛlo͜ʊ"
    assert form.units[1].prosody["stress"] == "primary"
    assert form.units[1].timing == Timing(0.07, 0.07)


def test_undeclared_model_phone_is_named_and_never_dropped() -> None:
    words = json.loads(json.dumps(RESULT["words"][:1]))
    words[0]["phones"][2]["phone"] = "zzq"
    with pytest.raises(ValueError, match="undeclared pocketsphinx phone: ZZQ"):
        _form_from_alignment(words, frame_rate=100)


def test_recorded_timed_form_round_trips_through_corpus(tmp_path: Path) -> None:
    corpus = _corpus.create(tmp_path / "corpus")
    form = _recorded_form()
    corpus.add("hello", {}, {"aligned": form})
    restored = _corpus.open(tmp_path / "corpus").read("hello").forms["aligned"]
    assert restored == form
    assert [unit.timing for unit in restored.units] == [
        unit.timing for unit in form.units
    ]
    assert [span.timing for span in restored.intervals] == [
        span.timing for span in form.intervals
    ]


def test_optional_dependency_error_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pocketsphinx", None)
    with pytest.raises(ImportError, match=r"pip install ipakit\[align\]"):
        align(HERE / "hello-world.wav", "hello world")


@pytest.mark.skipif(not HAS_POCKETSPHINX, reason="pocketsphinx is not installed")
def test_live_alignment_is_ordered_mapped_and_inside_audio() -> None:
    form = align(HERE / "hello-world.wav", "hello world")
    assert form.to_ipa()
    words = [
        event.features["spelling"]
        for node in form._graph.clock
        for group in node.groups
        if group.tier == "word"
        for event in group.events
    ]
    assert words == ["hello", "world"]
    timings = [unit.timing for unit in form.units]
    assert all(timing is not None for timing in timings)
    held = [timing for timing in timings if timing is not None]
    assert all(
        a.start + a.duration <= b.start + 1e-12
        for a, b in zip(held, held[1:], strict=False)
    )
    with wave.open(str(HERE / "hello-world.wav"), "rb") as source:
        wav_duration = source.getnframes() / source.getframerate()
    assert held[-1].start + held[-1].duration <= wav_duration


@pytest.mark.skipif(not HAS_POCKETSPHINX, reason="pocketsphinx is not installed")
def test_live_alignment_stores_and_restores_identical_timings(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    corpus = _corpus.create(root)
    corpus.add("hello", {"text": "hello world"}, {})
    (root / "wav").mkdir()
    shutil.copyfile(HERE / "hello-world.wav", root / "wav" / "hello.wav")

    aligned = align_entry(corpus, "hello")
    restored = _corpus.open(root).read("hello").forms["aligned"]
    assert restored == aligned
    assert [unit.timing for unit in restored.units] == [
        unit.timing for unit in aligned.units
    ]
