import argparse
import dataclasses
import json
import shutil
from pathlib import Path

import ipakit.textgrid as textgrid
import pytest
from ipakit.cli.textgrid import TextGridWriteCommand
from ipakit.form import Form, Interval, Timing
from ipakit.textgrid import TEXTGRID_DIR, profile, profiles, read, write

FIXTURES = Path(__file__).parent / "fixtures" / "textgrid"


def test_prosody_golden() -> None:
    expected = (FIXTURES / "prosody_hello.TextGrid").read_text(encoding="utf-8")
    assert write(Form.parse("ˈhɛ.loʊ‖"), "prosody") == expected


def test_prosody_read() -> None:
    document = (FIXTURES / "prosody_hello.TextGrid").read_text(encoding="utf-8")
    actual = read(document, profile="prosody")
    expected = Form.parse("ˈhɛ.loʊ‖")
    assert actual == expected
    assert all(unit.timing is None for unit in actual.units)


def test_mfa_read_and_golden() -> None:
    document = (FIXTURES / "mfa_two_words.TextGrid").read_text(encoding="utf-8")
    mapping = {"words": "word", "phones": "segment"}
    actual = read(document, tier_map=mapping)
    assert [unit.text for unit in actual.units] == list("kætsæt")
    assert actual.intervals == (
        Interval("word", 0, 3, timing=Timing(0, 0.75)),
        Interval("word", 3, 6, timing=Timing(1, 0.75)),
    )
    assert [unit.timing for unit in actual.units] == [
        Timing(0, 0.25),
        Timing(0.25, 0.25),
        Timing(0.5, 0.25),
        Timing(1, 0.25),
        Timing(1.25, 0.25),
        Timing(1.5, 0.25),
    ]
    assert read(document, profile="mfa") == actual
    assert write(actual, "mfa") == document


def test_segment_timing_covers_its_whole_base_span() -> None:
    document = (FIXTURES / "mfa_two_words.TextGrid").read_text(encoding="utf-8")
    document = document.replace(
        'xmax = 0.75 \n            text = "kæt"',
        'xmax = 0.6 \n            text = "kæt"',
        1,
    ).replace(
        'xmin = 0.75 \n            xmax = 1 \n            text = ""',
        'xmin = 0.6 \n            xmax = 1 \n            text = ""',
        1,
    )
    actual = read(document, profile="mfa")
    assert actual.units[2].text == "t"
    assert actual.units[2].timing == Timing(0.5, 0.25)
    assert write(actual, "mfa") == document


@pytest.mark.parametrize(
    ("transcription", "name"),
    [("t͡ʃ", "segments"), ("ˌkæt", "prosody"), ("ka.ta‖pa.ta‖", "prosody")],
)
def test_tick_read_rebuilds_the_form(transcription: str, name: str) -> None:
    expected = Form.parse(transcription, strict=True)
    actual = read(write(expected, name), profile=name)
    assert actual == expected
    assert all(unit.timing is None for unit in actual.units)


def test_strict_reader_refuses_an_unregistered_segment_label() -> None:
    document = (FIXTURES / "mfa_two_words.TextGrid").read_text(encoding="utf-8")
    document = document.replace('text = "k"', 'text = "Q"', 1)
    with pytest.raises(ValueError, match="phones.*interval 1.*label 'Q'"):
        read(document, profile="mfa")


def test_timed_form_with_a_boundary_writes_on_the_physical_face() -> None:
    form = Form.parse("kæ.t")
    index = 0
    timed = []
    for unit in form.units:
        if unit.is_boundary:
            timed.append(unit)
        else:
            timed.append(dataclasses.replace(unit, timing=Timing(index * 0.1, 0.1)))
            index += 1
    document = write(Form.of(timed), "mfa")
    assert 'name = "phones"' in document


def test_profile_directory_is_registry() -> None:
    assert profiles() == tuple(
        sorted(path.stem for path in TEXTGRID_DIR.glob("*.json"))
    )
    assert profiles()
    for name in profiles():
        loaded = profile(name)
        declared = (*loaded.span_view.span_tiers, *loaded.span_view.point_tiers)
        assert set(loaded.tier_map) == {tier.local_name for tier in declared}


def test_profile_refusals_name_choices() -> None:
    with pytest.raises(ValueError, match="mfa.*prosody.*segments.*words"):
        profile("nope")
    with pytest.raises(ValueError, match="mfa.*prosody.*segments.*words"):
        write(Form.parse("kæt"), "nope")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data.update(extra=True), "unknown key 'extra'.*accepted keys"),
        (lambda data: data.pop("summary"), "missing key 'summary'"),
        (
            lambda data: data["tier_map"].__setitem__("segment", "word"),
            "0 segment tiers.*exactly one segment role",
        ),
    ],
)
def test_profile_envelope_refusals(tmp_path, monkeypatch, change, message) -> None:
    shutil.copytree(TEXTGRID_DIR, tmp_path / "textgrid")
    path = tmp_path / "textgrid" / "segments.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(textgrid, "TEXTGRID_DIR", tmp_path / "textgrid")
    with pytest.raises(ValueError, match=message):
        profile("segments")


def test_profile_registry_refuses_a_non_json_file(tmp_path, monkeypatch) -> None:
    shutil.copytree(TEXTGRID_DIR, tmp_path / "textgrid")
    (tmp_path / "textgrid" / "notes.txt").write_text("stray", encoding="utf-8")
    monkeypatch.setattr(textgrid, "TEXTGRID_DIR", tmp_path / "textgrid")
    with pytest.raises(ValueError, match="notes.txt.*profile documents only"):
        profiles()


def test_mapping_refusals() -> None:
    document = (FIXTURES / "mfa_two_words.TextGrid").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="words.*phones.*segment role"):
        read(document)
    with pytest.raises(ValueError, match="phones.*uncovered"):
        read(document, tier_map={"words": "word"})
    with pytest.raises(ValueError, match="unknown.*accepted roles"):
        read(document, tier_map={"words": "word", "phones": "unknown"})


def test_nonsegment_role_may_be_assigned_more_than_once() -> None:
    document = (FIXTURES / "prosody_hello.TextGrid").read_text(encoding="utf-8")
    actual = read(
        document,
        tier_map={
            "utterance": "word",
            "word": "word",
            "syllable": "syllable",
            "segment": "segment",
            "stress": "stress",
            "tone": "tone",
        },
    )
    assert sum(interval.tier == "word" for interval in actual.intervals) == 2


def test_textgrid_cli_has_no_scale_option() -> None:
    parser = argparse.ArgumentParser()
    TextGridWriteCommand.add_arguments(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["kæt", "--scale", "2"])


def test_scale_and_physical_refusals() -> None:
    with pytest.raises(ValueError, match="scale"):
        write(Form.parse("kæt"), "prosody", scale=2)
    with pytest.raises(ValueError, match="mfa.*unit 0.*k"):
        write(Form.parse("kæt"), "mfa")


def test_style_seam() -> None:
    default = write(Form.parse("kæt"))
    upper = write(Form.parse("kæt"), spell=str.upper)
    expected = default.replace('text = "k"', 'text = "K"')
    expected = expected.replace('text = "æ"', 'text = "Æ"')
    expected = expected.replace('text = "t"', 'text = "T"')
    assert upper == expected
    assert [
        unit.text
        for unit in read(upper, tier_map={"segment": "segment"}, read=str.lower).units
    ] == list("kæt")
