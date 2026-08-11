import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit.bridges import (
    ESPEAK_EN,
    EspeakBridge,
    Fidelity,
    ProjectionDrop,
    VocabularyBridge,
    VocabularyResidueError,
)
from ipakit.bridges.kana import KANA
from ipakit.bridges.mfa import MFA
from ipakit.bridges.pinyin import PINYIN
from ipakit.form import Form

FIXTURE = Path(__file__).parent / "fixtures" / "mfa_english_us_v3_1_0.dict"
ESPEAK_FIXTURE = Path(__file__).parent / "fixtures" / "espeak_en_1_52_0.txt"
ESPEAK_CMN_FIXTURE = Path(__file__).parent / "fixtures" / "espeak_cmn_1_52_0.txt"


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


def test_read_accepts_the_default_emission_and_keeps_segmentation() -> None:
    form = MFA.read_tokens(("a", "j"))
    assert MFA.emit(MFA.read(MFA.emit(form))) == "a j"
    assert MFA.emit(MFA.read("m aj s")) == "m aj s"
    assert MFA.emit(MFA.read("aj")) == "aj"


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


@pytest.mark.parametrize(
    ("house", "emitted", "name", "span"),
    [
        (
            "t͡ʃ",
            "tʃ",
            "ties and simultaneity absent from MFA spellings",
            (0, 1),
        ),
        (
            "n̪",
            "n",
            "narrow detail outside the MFA English inventory",
            (0, 1),
        ),
        (
            "aj",
            "aj",
            "house unit boundaries collapsed by MFA atom grouping",
            (0, 2),
        ),
    ],
)
def test_mfa_mapper_exercises_each_declared_drop(
    house: str, emitted: str, name: str, span: tuple[int, int]
) -> None:
    mapped = MFA.map_to_mfa(Form.parse(house, strict=True))
    assert MFA.emit(mapped) == emitted
    assert mapped.form.to_ipa() == house
    assert mapped.report.drops == (ProjectionDrop(name, span, house, emitted),)


def test_mfa_mapper_refuses_word_boundaries_positioned() -> None:
    for house, message in [
        ("#pat", r"span \[0:1\]: '#'"),
        ("paj#", r"span \[3:4\]: '#'"),
        ("a b", r"span \[1:2\]: '#'"),
    ]:
        with pytest.raises(VocabularyResidueError, match=message):
            MFA.map_to_mfa(Form.parse(house, strict=True))


def test_mfa_mapper_reports_the_same_drop_once_per_site() -> None:
    mapped = MFA.map_to_mfa(Form.parse("ajaj", strict=True))
    assert MFA.emit(mapped) == "aj aj"
    name = "house unit boundaries collapsed by MFA atom grouping"
    assert mapped.report.drops == (
        ProjectionDrop(name, (0, 2), "aj", "aj"),
        ProjectionDrop(name, (2, 4), "aj", "aj"),
    )


def test_mfa_mapper_reports_untied_affricate_as_boundary_collapse() -> None:
    mapped = MFA.map_to_mfa(Form.parse("tʃa", strict=True))
    assert MFA.emit(mapped) == "tʃ a"
    name = "house unit boundaries collapsed by MFA atom grouping"
    assert mapped.report.drops == (ProjectionDrop(name, (0, 2), "tʃ", "tʃ"),)


def test_mfa_mapper_no_drop_form_has_empty_serializable_report() -> None:
    mapped = MFA.map_to_mfa(Form.parse("pat", strict=True))
    assert MFA.emit(mapped) == "p a t"
    assert mapped.report.drops == ()
    encoded = json.loads(mapped.to_json())
    assert encoded["report"] == {"drops": []}
    assert [unit["text"] for unit in encoded["form"]["units"]] == ["p", "a", "t"]


@pytest.mark.parametrize(
    ("house", "message"),
    [
        ("n̥", r"span \[0:1\]: 'n̥'"),
        ("x", r"span \[0:1\]: 'x'"),
        ("", r"span \[0:0\]: ''"),
    ],
)
def test_mfa_mapper_refuses_undeclared_or_empty_residue_positioned(
    house: str, message: str
) -> None:
    with pytest.raises(VocabularyResidueError, match=message):
        MFA.map_to_mfa(Form.parse(house, strict=True))


def test_espeak_en_inventory_is_language_scoped_and_pinned() -> None:
    assert ESPEAK_EN.language == "en"
    assert ESPEAK_EN.name == "espeak-en"
    assert ESPEAK_EN.version == "espeak-ng-1.52.0"
    assert ESPEAK_EN.source_style == "text"
    assert ESPEAK_EN.separator == ""
    assert len(ESPEAK_EN.atoms) == 67


def test_espeak_native_text_fixture_round_trips_byte_exact() -> None:
    samples = [
        line
        for line in ESPEAK_FIXTURE.read_text().splitlines()
        if not line.startswith("#")
    ]
    assert len(samples) == 3
    assert [ESPEAK_EN.emit(ESPEAK_EN.read(sample)) for sample in samples] == samples
    assert ESPEAK_EN.read(samples[0]).to_ipa() == "həlˈəʊ wˈɜːld"


def test_espeak_external_distinctions_survive_on_the_grouping_tier() -> None:
    form = ESPEAK_EN.read("@3I2")
    assert form.to_ipa() == "əəɪ"
    assert ESPEAK_EN.emit(form) == "@3I2"


def test_espeak_en_round_trip_classification_names_unimplemented_mapper() -> None:
    assert ESPEAK_EN.round_trip.external_to_house.fidelity is Fidelity.LOSSLESS
    ours = ESPEAK_EN.round_trip.house_to_external
    assert ours.fidelity is Fidelity.LOSSY_WITH_REPORT
    assert ours.drops[0] == (
        "the house-to-eSpeak leg awaits a mapper; emit requires an existing "
        "espeak-en grouping tier"
    )
    with pytest.raises(ValueError, match="undeclared tiers: \\['espeak-en'\\]"):
        ESPEAK_EN.emit(Form.parse("həloʊ", strict=True))


def test_espeak_refuses_undeclared_language_and_native_residue() -> None:
    with pytest.raises(
        ValueError, match="no declared eSpeak NG vocabulary for 'zz-absent'"
    ):
        EspeakBridge("zz-absent")
    with pytest.raises(VocabularyResidueError, match=r"span \[1:2\]: '\$'"):
        ESPEAK_EN.read("h$")


def test_every_generated_espeak_declaration_loads() -> None:
    """Sweep the generated set so no language can ship as unloadable XML."""
    declarations = sorted(
        (Path(__file__).parent.parent / "ipakit/data/bridges/espeak").glob("*.xml")
    )
    assert len(declarations) == 129
    assert all(EspeakBridge(path.stem).atoms for path in declarations)


def test_espeak_declared_refusal_names_mnemonic_and_position() -> None:
    bridge = EspeakBridge("fr")
    refused = bridge.refusals[0]
    with pytest.raises(
        VocabularyResidueError,
        match=rf"mnemonic {refused.spelling!r} at span \[1:{1 + len(refused.spelling)}\]",
    ):
        bridge.read("p" + refused.spelling)


def test_espeak_tone_fixture_reaches_declared_positioned_refusal() -> None:
    """A real Mandarin line exercises a tone the house does not declare."""
    sample = next(
        line
        for line in ESPEAK_CMN_FIXTURE.read_text().splitlines()
        if not line.startswith("#")
    )
    with pytest.raises(
        VocabularyResidueError,
        match=r"mnemonic '35' at span \[2:4\]: control-or-virtual",
    ):
        EspeakBridge("cmn").read(sample)


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
            lambda atoms: atoms[1].set("output", atoms[0].attrib["spelling"]),
            r"atom 2 output 'p' duplicates atom 1",
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
