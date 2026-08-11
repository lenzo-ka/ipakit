from pathlib import Path

import pytest
from ipakit.bridges import Fidelity, VocabularyResidueError
from ipakit.bridges.kana import KANA
from ipakit.bridges.mfa import MFA
from ipakit.bridges.pinyin import PINYIN
from ipakit.form import Form

FIXTURE = Path(__file__).parent / "fixtures" / "mfa_english_us_v3_1_0.dict"


def test_mfa_inventory_is_pinned_and_parses_under_base_ipa() -> None:
    assert MFA.version == "english_mfa-v3.1.0"
    assert len(MFA.atoms) == 101
    assert all(Form.parse(atom.spelling, strict=True) for atom in MFA.atoms)


def test_mfa_atoms_are_grouping_tier_over_house_units() -> None:
    form = MFA.read_tokens(("aj", "pʰ", "tʃ"))
    assert form.to_ipa() == "ajpʰtʃ"
    groups = [
        event
        for node in form._graph.clock
        for group in node.groups
        if group.tier == "mfa"
        for event in group.events
    ]
    assert [event.features["atom"] for event in groups] == ["aj", "pʰ", "tʃ"]
    assert [event.structural_duration for event in groups] == [2, 1, 2]


def test_segmented_stream_refuses_unvocabularied_token_by_name() -> None:
    with pytest.raises(VocabularyResidueError, match=r"token 1: 'NOPE'"):
        MFA.read_tokens(("m", "NOPE"))


def test_unsegmented_stream_uses_longest_match_and_names_residue_span() -> None:
    assert MFA.emit(MFA.read("aj")) == "aj"
    with pytest.raises(VocabularyResidueError, match=r"span \[2:3\]: 'X'"):
        MFA.read("ajX")


def test_dictionary_fixture_round_trips_byte_exact() -> None:
    lines = [
        line for line in FIXTURE.read_text().splitlines() if not line.startswith("#")
    ]
    assert len(lines) == 26
    assert [
        MFA.emit_dictionary_line(MFA.read_dictionary_line(line)) for line in lines
    ] == lines


def test_mfa_round_trip_classification_names_house_drops() -> None:
    assert MFA.round_trip.external_to_house.fidelity is Fidelity.LOSSLESS
    ours = MFA.round_trip.house_to_external
    assert ours.fidelity is Fidelity.LOSSY_WITH_REPORT
    assert ours.drops == (
        "ties and simultaneity absent from MFA spellings",
        "narrow detail outside the MFA English inventory",
        "house unit boundaries collapsed by MFA atom grouping",
    )


def test_migrated_declarations_hold_kana_and_pinyin_tables() -> None:
    assert len(KANA.atoms) == 16
    assert PINYIN.inputs == (("u:", "ü"), ("v", "ü"))
    assert PINYIN.tones["ü"] == "ǖǘǚǜ"
