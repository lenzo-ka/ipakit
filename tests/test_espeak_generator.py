"""Pins eSpeak NG's source-level mnemonic-to-IPA rules."""

import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

import pytest
from ipakit.extraction import BuildResult, espeak
from ipakit.extraction.espeak import Phone, default_ipa, spelling, tone_spellings
from scripts import espeak_vocabularies


def test_espeak_source_import_leaves_sys_path_alone() -> None:
    code = (
        "import sys; before = sys.path.copy(); import ipakit.espeak_source; "
        "assert sys.path == before; "
        "assert 'ipakit.extraction.espeak' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_generator_delegates_to_library_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = BuildResult({Path("docs/espeak-vocabularies.md"): b"summary\n"})
    calls: list[Path] = []

    def build(source: Path) -> BuildResult:
        calls.append(source)
        return result

    monkeypatch.setattr(espeak_vocabularies, "build", build)
    assert espeak_vocabularies.generate(tmp_path) == {
        espeak_vocabularies.ROOT / "docs/espeak-vocabularies.md": b"summary\n"
    }
    assert calls == [tmp_path]
    assert espeak_vocabularies.REVISION == espeak.REVISION


def test_library_builder_and_runtime_share_rendered_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phsource = tmp_path / "phsource"
    phsource.mkdir()
    (phsource / "phonemes").write_text("""phoneme p
  vls blb stp
  ipa p
endphoneme
phonemetable consonants
phonemetable xx consonants
include ph_test
""")
    (phsource / "ph_test").write_text("""phoneme a
  vowel
  ipa a
endphoneme
""")
    monkeypatch.setattr(espeak, "require_pin", lambda source: None)

    result = espeak.build(tmp_path)
    assert result.artifacts[espeak.SUMMARY].startswith(
        b"# eSpeak NG vocabulary generation summary\n"
    )
    declared, resolved = espeak.resolve(tmp_path)
    table = next(table for table in declared if table.name == "xx")
    expected, _ = espeak.render(table.name, resolved[table.name])

    from ipakit.espeak_source import declaration_bytes

    assert declaration_bytes(str(tmp_path))["xx"] == expected


def test_fetch_precedes_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        espeak_vocabularies,
        "fetch",
        lambda source: calls.append(("fetch", source)),
    )
    monkeypatch.setattr(
        espeak_vocabularies,
        "build",
        lambda source: calls.append(("build", source)) or BuildResult({}),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "espeak_vocabularies.py",
            "check",
            "--fetch",
            "--source",
            str(tmp_path),
        ],
    )
    assert espeak_vocabularies.main() == 0
    assert calls == [("fetch", tmp_path), ("build", tmp_path)]


def test_default_ipa_matches_pinned_write_ph_mnemonic_rules() -> None:
    assert default_ipa(Phone("O~", ("vwl",))) == "ɔ̃"
    assert default_ipa(Phone("o:", ("vwl",))) == "oː"
    assert default_ipa(Phone("p#", ("vls blb stp",))) == "pʰ"
    assert default_ipa(Phone("I2#", ("vwl",))) == "ɪ"
    assert default_ipa(Phone("l/3", ("liquid",))) == "l"


def test_explicit_ipa_wins_and_embedded_codepoints_decode() -> None:
    assert spelling(Phone("m-", ("ipa mU+0329",))) == ("m̩", None)
    assert spelling(Phone("O~", ("ipa ɒ", "vwl"))) == ("ɒ", None)


def test_dotted_mnemonics_use_inventory_determined_ipa() -> None:
    cases = {
        ("r.", "FMT(r3/@tap_rfx)"): "ɽ",
        ("s.", "WAV(ufric/sh_rfx, 50)"): "ʂ",
        ("ts.", "WAV(ustop/ts_rfx_unasp)"): "ʈ͡ʂ",
        ("ts.h", "WAV(ustop/ts_rfx)"): "ʈ͡ʂʰ",
        ("i.", "FMT(vowel/i#_6)"): "ɨ",
        ("a.", "FMT(vowel/aa_7)"): "ɑ",
        ("i.", "FMT(vowel/ii_5)"): "ɪ",
        ("u.", "FMT(vowel/u_7)"): "ʊ",
    }
    for (mnemonic, instruction), expected in cases.items():
        assert spelling(Phone(mnemonic, ("vwl", instruction))) == (expected, None)


def test_unresolved_dotted_mnemonic_is_not_accepted_as_one_phone() -> None:
    assert spelling(Phone("x.", ("frc",))) == (None, "outside-house-ipa")


def test_non_ipa_source_phonemes_remain_declared_refusals() -> None:
    assert spelling(Phone("#a", ("virtual",))) == (None, "control-or-virtual")
    assert spelling(Phone(";", ("ipa NULL",))) == (None, "conditional-null")


def test_tone_directive_derives_chao_letters_and_word_pause_is_boundary() -> None:
    inventory = OrderedDict(
        (
            ("35", Phone("35", ("stress", "Tone(30, 50, envelope/p_rise, NULL)"))),
            ("214", Phone("214", ("stress", "Tone(18, 42, envelope/p_214, NULL)"))),
            ("51", Phone("51", ("stress", "Tone(50, 10, envelope/p_fall, NULL)"))),
        )
    )
    tones = tone_spellings(inventory)
    assert spelling(inventory["35"], tones) == (
        "˧˥",
        None,
    )
    assert spelling(inventory["214"], tones) == (
        "˨˩˦",
        None,
    )
    assert spelling(Phone("_|", ("pause", "length 1"))) == ("#", None)
    assert spelling(Phone("_:", ("pause", "length 75"))) == (None, "control-or-virtual")


def test_tone_labels_do_not_determine_pitch_and_all_tone_content_maps() -> None:
    inventory = OrderedDict(
        (
            ("1", Phone("1", ("stress", "Tone(50, 50, envelope/p_level, NULL)"))),
            ("4", Phone("4", ("stress", "Tone(20, 10, envelope/p_fall, NULL)"))),
            ("5", Phone("5", ("stress", "Tone(10, 30, envelope/p_rise, NULL)"))),
            ("6", Phone("6", ("stress", "Tone(20, 20, envelope/p_level, NULL)"))),
            ("˥", Phone("˥", ("stress", "Tone(50, 50, envelope/p_level, NULL)"))),
        )
    )
    tones = tone_spellings(inventory)
    levels = dict(zip("˩˨˧˦˥", range(5), strict=True))
    # Chao band boundaries are a transcription judgment.  What the source
    # fixes unequivocally is high-level 1, falling 4, rising 5, and their
    # relative pitch ordering, so assert those relations rather than a
    # particular quantizer's absolute letters.
    assert tones["1"][0] == tones["1"][-1]
    assert levels[tones["1"][0]] > levels[tones["4"][0]] > levels[tones["4"][-1]]
    assert levels[tones["5"][0]] < levels[tones["5"][-1]] < levels[tones["1"][0]]
    assert spelling(inventory["6"], tones)[0] is not None
    assert tones["˥"] == "˥"
