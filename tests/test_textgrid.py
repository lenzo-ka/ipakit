import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path

import ipakit.textgrid as textgrid
import pytest
from ipakit.cli.textgrid import TextGridWriteCommand
from ipakit.form import Form, Interval, Timing
from ipakit.inventories import Style
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
    actual = read(document, tier_map=mapping, face="physical")
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


def test_mfa_style_round_trips_both_hand_written_goldens() -> None:
    for name in ("mfa_two_words.TextGrid", "mfa_untied.TextGrid"):
        document = (FIXTURES / name).read_text(encoding="utf-8")
        assert (
            write(read(document, profile="mfa", style="mfa"), "mfa", style="mfa")
            == document
        )


def test_cmudict_style_reads_stress_and_writes_its_declared_collapse() -> None:
    document = (FIXTURES / "cmudict.TextGrid").read_text(encoding="utf-8")
    form = read(document, profile="mfa", style="cmudict")
    assert [unit.text for unit in form.units] == ["ə", "k", "t"]
    canonical = document.replace('text = "AH0 K T"', 'text = "AH K T"').replace(
        'text = "AH0"', 'text = "AH"'
    )
    assert write(form, "mfa", style="cmudict") == canonical
    collapsed = dataclasses.replace(form.units[0], text="ʌ")
    assert (
        write(
            Form.of((collapsed, *form.units[1:]), form.intervals),
            "mfa",
            style="cmudict",
        )
        == canonical
    )


def test_cmudict_hand_written_stress_and_affricate_round_trip() -> None:
    document = (FIXTURES / "cmudict_stress.TextGrid").read_text(encoding="utf-8")
    form = read(document, profile="mfa", style="cmudict")
    assert [unit.text for unit in form.units] == ["ˈʌ", "ˌʌ", "d͡ʒ"]
    assert write(form, "mfa", style="cmudict") == document


@pytest.mark.parametrize(("tier", "mark"), [("stress", "ˈ"), ("tone", "˥˩")])
def test_styled_prosody_point_is_not_duplicated_in_intervals(
    tier: str, mark: str
) -> None:
    base = write(Form.parse("a"), "prosody")
    document = base.replace(
        f'name = "{tier}" \n        xmin = 0 \n        xmax = 1 \n        points: size = 0',
        f'name = "{tier}" \n        xmin = 0 \n        xmax = 1 \n        points: size = 1 \n        points [1]:\n            number = 0 \n            mark = "{mark}"',
    )
    form = read(document, profile="prosody", style="mfa")
    assert write(form, "prosody", style="mfa") == document
    assert all(
        line.strip() == 'text = "a"'
        for line in document.splitlines()
        if "text =" in line and 'text = ""' not in line
    )


def test_cmudict_stress_lives_in_label_or_point_by_profile() -> None:
    parsed = Form.parse("ˈʌkt")
    timed = Form.of(
        tuple(
            dataclasses.replace(unit, timing=Timing(index, 1))
            for index, unit in enumerate(parsed.units)
        )
    )
    mfa = write(timed, "mfa", style="cmudict")
    assert ["AH1", "K", "T"] == [
        line.split('"')[1] for line in mfa.splitlines() if "text =" in line
    ][1:]
    reread = read(mfa, profile="mfa", style="cmudict")
    assert reread.to_ipa() == timed.to_ipa()
    assert [unit.timing for unit in reread.units] == [
        unit.timing for unit in timed.units
    ]

    prosody = write(parsed, "prosody", style="cmudict")
    assert 'text = "AH"' in prosody
    assert 'mark = "ˈ"' in prosody
    assert read(prosody, profile="prosody", style="cmudict") == parsed


def test_unspellable_marked_unit_recommends_its_point_profile() -> None:
    with pytest.raises(
        ValueError,
        match=r"segments.*segment.*label 'ˈa'.*stress point tier, e.g. prosody",
    ):
        write(Form.parse("ˈa"), "segments", style="mfa")


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


@pytest.mark.parametrize(
    "transcription",
    [
        "ka.#ta",
        "ka#.ta",
        "ka##ta",
        "ka.‖ta",
        "ka‿ta",
        "ka‿",
        "ka‖ta",
        "lez‿ami",
        "ka.ta‖pa.ta‖",
        "ˌkæt",
        "a˥˩",
        "ka˥",
    ],
)
def test_prosody_carries_boundary_marks(transcription: str) -> None:
    expected = Form.parse(transcription, strict=True)
    assert read(write(expected, "prosody"), profile="prosody") == expected


def test_boundary_point_must_land_on_a_segment_start_or_final_boundary() -> None:
    document = write(Form.parse("a"), "prosody").replace(
        'name = "boundary" \n        xmin = 0 \n        xmax = 1 \n        points: size = 0',
        'name = "boundary" \n        xmin = 0 \n        xmax = 1 \n        points: size = 1 \n        points [1]:\n            number = 0.5 \n            mark = "."',
    )
    with pytest.raises(ValueError, match="boundary.*point 1.*0.5.*final boundary"):
        read(document, profile="prosody")


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


def test_profile_refuses_roles_on_the_wrong_tier_classes(tmp_path, monkeypatch) -> None:
    shutil.copytree(TEXTGRID_DIR, tmp_path / "textgrid")
    path = tmp_path / "textgrid" / "prosody.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tier_map"]["word"], data["tier_map"]["stress"] = (
        data["tier_map"]["stress"],
        data["tier_map"]["word"],
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(textgrid, "TEXTGRID_DIR", tmp_path / "textgrid")
    with pytest.raises(ValueError, match="tier 'word'.*role 'stress'"):
        profile("prosody")


def test_bad_span_view_refusal_names_profile_and_file(tmp_path, monkeypatch) -> None:
    shutil.copytree(TEXTGRID_DIR, tmp_path / "textgrid")
    path = tmp_path / "textgrid" / "prosody.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["span_view"]["clock_face"] = "sideways"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(textgrid, "TEXTGRID_DIR", tmp_path / "textgrid")
    with pytest.raises(ValueError, match=r"prosody.*prosody\.json.*span_view"):
        profile("prosody")


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
        read(document, tier_map={"words": "word"}, face="physical")
    with pytest.raises(ValueError, match="unknown.*accepted roles"):
        read(
            document,
            tier_map={"words": "word", "phones": "unknown"},
            face="physical",
        )


def test_explicit_tier_map_requires_an_explicit_clock_face() -> None:
    document = write(Form.parse("kæt"))
    mapping = {"segment": "segment"}
    with pytest.raises(ValueError, match="physical.*tick"):
        read(document, tier_map=mapping)
    with pytest.raises(ValueError, match="segments.*tick"):
        read(document, profile="segments", face="tick")
    with pytest.raises(ValueError, match="physical.*tick"):
        read(document, tier_map=mapping, face="ordinal")
    actual = read(document, tier_map=mapping, face="tick")
    assert [unit.text for unit in actual.units] == list("kæt")
    assert all(unit.timing is None for unit in actual.units)


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
            "boundary": "boundary",
        },
        face="physical",
    )
    assert sum(interval.tier == "word" for interval in actual.intervals) == 2


def test_write_refuses_overlapping_intervals_on_one_role() -> None:
    parsed = Form.parse("kæt")
    form = Form.of(
        parsed.units,
        (Interval("word", 0, 2), Interval("word", 1, 3)),
    )
    with pytest.raises(
        ValueError,
        match=r"word.*Interval\('word', 0, 2\).*Interval\('word', 1, 3\).*one ordered, non-overlapping cover",
    ):
        write(form, "words")


@pytest.mark.parametrize(
    ("tier", "mark", "expected"),
    [("stress", "ˈ", "ˈa"), ("tone", "˥", "a˥")],
)
def test_point_mark_placement_is_decided_by_the_inventory(
    tier: str, mark: str, expected: str
) -> None:
    document = write(Form.parse("a"), "prosody").replace(
        f'name = "{tier}" \n        xmin = 0 \n        xmax = 1 \n        points: size = 0',
        f'name = "{tier}" \n        xmin = 0 \n        xmax = 1 \n        points: size = 1 \n        points [1]:\n            number = 0 \n            mark = "{mark}"',
    )
    assert read(document, profile="prosody").to_ipa() == expected


def test_unreadable_point_mark_has_a_textgrid_diagnostic() -> None:
    document = write(Form.parse("a"), "prosody").replace(
        'name = "tone" \n        xmin = 0 \n        xmax = 1 \n        points: size = 0',
        'name = "tone" \n        xmin = 0 \n        xmax = 1 \n        points: size = 1 \n        points [1]:\n            number = 0 \n            mark = "ˈ"',
    )
    with pytest.raises(ValueError, match="tone.*point 1.*mark 'ˈ'.*cannot apply"):
        read(document, profile="prosody")


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
        for unit in read(
            upper,
            tier_map={"segment": "segment"},
            face="physical",
            read=str.lower,
        ).units
    ] == list("kæt")


def test_named_style_refusals_and_exclusivity() -> None:
    def spell_small(value: str) -> str:
        if value != "k":
            raise ValueError(f"cannot spell {value!r}")
        return "K"

    refusing = Style("small", lambda value: value.lower(), spell_small)
    with pytest.raises(ValueError, match="segments.*segment.*interval 2.*label 'æ'"):
        write(Form.parse("kæt"), style=refusing)
    document = write(Form.parse("kæt")).replace('text = "æ"', 'text = "Q"')
    with pytest.raises(ValueError, match="segment.*interval 2.*label 'Q'"):
        read(document, profile="segments", style="mfa")
    with pytest.raises(ValueError, match="style and spell.*one or the other"):
        write(Form.parse("k"), style="ipa", spell=str.upper)
    with pytest.raises(ValueError, match="style and read.*one or the other"):
        read(write(Form.parse("k")), profile="segments", style="ipa", read=str.lower)


def test_wild_style_reads_a_wild_segment() -> None:
    document = write(Form.parse("ɡ")).replace('text = "ɡ"', 'text = "g"')
    assert read(document, profile="segments", style="wild").to_ipa() == "ɡ"


def test_style_cli_text_and_json(tmp_path: Path) -> None:
    document = FIXTURES / "cmudict.TextGrid"
    text = subprocess.run(
        [
            sys.executable,
            "-m",
            "ipakit",
            "textgrid",
            "read",
            str(document),
            "--profile",
            "mfa",
            "--style",
            "cmudict",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert text.stdout.splitlines()[0] == "əkt"
    structured = subprocess.run(
        [
            sys.executable,
            "-m",
            "ipakit",
            "textgrid",
            "read",
            str(document),
            "--profile",
            "mfa",
            "--style",
            "cmudict",
            "-f",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(structured.stdout)["units"][0]["text"] == "ə"
    unknown = subprocess.run(
        [
            sys.executable,
            "-m",
            "ipakit",
            "textgrid",
            "read",
            str(document),
            "--profile",
            "mfa",
            "--style",
            "nope",
        ],
        capture_output=True,
        text=True,
    )
    assert unknown.returncode == 1
    assert "ipakit inventory list" in unknown.stderr
