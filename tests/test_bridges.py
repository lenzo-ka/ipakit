import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit.bridges import Fidelity, VocabularyBridge, VocabularyResidueError
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
    assert MFA.emit(MFA.read("aj"), separator="") == "aj"
    with pytest.raises(VocabularyResidueError, match=r"span \[2:3\]: 'X'"):
        MFA.read("ajX")


def test_segmented_source_emits_its_declared_separator_by_default() -> None:
    form = MFA.read_tokens(("a", "j"))
    assert MFA.emit(form) == "a j"
    assert MFA.read_tokens(MFA.emit(form).split()).to_ipa() == form.to_ipa()
    assert MFA.emit(form, separator="") == "aj"


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
        "declared future mapper loss: ties and simultaneity absent from MFA spellings",
        "declared future mapper loss: narrow detail outside the MFA English inventory",
        "declared future mapper loss: house unit boundaries collapsed by MFA atom grouping",
    )


def test_migrated_declarations_hold_kana_and_pinyin_tables() -> None:
    assert len(KANA.atoms) == 16
    assert PINYIN.inputs == (("u:", "ü"), ("v", "ü"))
    assert PINYIN.tones["ü"] == "ǖǘǚǜ"


@pytest.mark.parametrize(
    ("label", "mutate", "message"),
    [
        (
            "missing",
            lambda atoms: atoms[1].attrib.pop("spelling"),
            r"atom 2 has no spelling",
        ),
        (
            "duplicate",
            lambda atoms: atoms[1].set("spelling", atoms[0].attrib["spelling"]),
            r"atom 2 spelling 'p' duplicates atom 1",
        ),
        (
            "non-IPA",
            lambda atoms: atoms[1].set("spelling", "X"),
            r"atom 2 spelling 'X' is not house IPA",
        ),
    ],
)
def test_vocabulary_load_refuses_bad_atom_with_identity_and_position(
    tmp_path: Path, label: str, mutate, message: str
) -> None:
    declaration = Path(__file__).parent.parent / "ipakit/data/bridges/mfa/mfa.xml"
    root = ET.parse(declaration).getroot()
    mutate(root.findall("atom"))
    bad = tmp_path / f"{label}.xml"
    ET.ElementTree(root).write(bad, encoding="utf-8", xml_declaration=True)
    with pytest.raises(ValueError, match=message):
        VocabularyBridge(bad)
