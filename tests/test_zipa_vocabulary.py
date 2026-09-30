"""The pinned ZIPA vocabulary is a scoped, loss-declaring house bridge."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import ipakit
import pytest
from ipakit.bridges import Fidelity, VocabularyResidueError
from ipakit.bridges.zipa import ZIPA, ZIPABridge
from scripts.zipa_vocabulary import (
    EXTRA_MARK_DROP,
    LOSSES,
    MARKS,
    NON_PHONE_MARKERS,
    OUTPUT,
    SHA256,
    TIE_DROP,
    UNSUPPORTED_MARK_DROP,
    render,
    tokens,
    validate_declaration,
)


def test_declaration_has_the_pinned_token_census_and_fidelity() -> None:
    units = [atom for atom in ZIPA.atoms if atom.kind == "unit"]
    marks = [atom for atom in ZIPA.atoms if atom.kind == "mark"]
    assert len(units) == 109  # 108 phone bases and the word boundary.
    assert len(marks) == 15
    assert {atom.output for atom in marks} == MARKS
    assert {item.spelling for item in ZIPA.refusals} == set(NON_PHONE_MARKERS)
    assert ZIPA.source is not None
    assert ZIPA.source.license == "MIT"
    assert ZIPA.round_trip.external_to_house.fidelity is Fidelity.LOSSLESS
    assert ZIPA.round_trip.house_to_external.fidelity is Fidelity.LOSSY_WITH_REPORT
    assert ZIPA.round_trip.house_to_external.drops == LOSSES
    assert ZIPA.tie_drop == TIE_DROP
    assert EXTRA_MARK_DROP in LOSSES
    assert UNSUPPORTED_MARK_DROP in LOSSES


def test_every_phone_and_boundary_token_round_trips() -> None:
    for atom in ZIPA.atoms:
        if atom.kind != "unit":
            continue
        form = ZIPA.read_tokens((atom.output,))
        assert ZIPA.emit(form) == atom.output


def test_every_mark_token_round_trips_on_a_house_host() -> None:
    for atom in ZIPA.atoms:
        if atom.kind != "mark":
            continue
        form = ZIPA.read_tokens(("a", atom.output))
        assert ZIPA.emit(form) == f"a {atom.output}"


def test_non_phone_markers_are_declared_refusals() -> None:
    for marker in NON_PHONE_MARKERS:
        with pytest.raises(VocabularyResidueError, match="control marker"):
            ZIPA.read_tokens((marker,))


def test_ascii_g_is_scoped_to_zipa_and_round_trips() -> None:
    assert ZIPA.read_tokens(("g",)).to_ipa() == "ɡ"
    assert ZIPA.emit(ZIPA.read_tokens(("g",))) == "g"
    assert ipakit.inventory("zipa").style.read("g") == "ɡ"
    assert ipakit.inventory("zipa").style.spell("ɡ") == "g"
    with pytest.raises(ValueError, match=r"unknown symbols \['g'\]"):
        ipakit.segments("g", strict=True)


def test_retroflex_implosive_and_word_boundary_round_trip() -> None:
    form = ZIPA.read_tokens(("ᶑ", "▁", "a"))
    assert form.to_ipa() == "ᶑ#a"
    assert ZIPA.emit(form) == "ᶑ ▁ a"


@pytest.mark.parametrize(
    ("original", "house"),
    [
        ("t͡ʃa ga", "t͡ʃa ɡa"),
        ("d͡ʒa ᶑa", "d͡ʒa ᶑa"),
        ("n̥a kʰa", "n̥a kʰa"),
    ],
)
def test_ipapack_custom_original_reads_strict_house_forms(
    original: str, house: str
) -> None:
    assert ZIPA.read_original(original).to_ipa() == house


def test_inventory_contains_only_the_108_base_phones() -> None:
    item = ipakit.inventory("zipa")
    assert item.phones is not None
    assert len(item.phones) == 108
    assert item.refusals == {
        marker: "ZIPA control marker does not denote a phone"
        for marker in NON_PHONE_MARKERS
    }
    for phone in item.phones:
        assert item.style.read(item.style.spell(phone)) == phone


def test_fault_injection_dropping_g_is_detected() -> None:
    payload = OUTPUT.read_text(encoding="utf-8")
    root = ET.fromstring(payload)
    values = tuple(
        [
            item.attrib.get("output", item.attrib["spelling"])
            for item in root.findall("atom")
        ]
        + [item.attrib["spelling"] for item in root.findall("refusal")]
    )
    g = next(item for item in root.findall("atom") if item.attrib.get("output") == "g")
    root.remove(g)
    with pytest.raises(ValueError, match=r"missing \['g'\]"):
        validate_declaration(ET.tostring(root, encoding="unicode"), values)


SOURCE = Path(os.environ.get("ZIPA_VOCAB", ""))
needs_source = pytest.mark.skipif(
    not SOURCE.is_file(),
    reason="ZIPA_VOCAB does not name the pinned unigram_127.vocab",
)


@needs_source
def test_generator_reproduces_shipped_declaration() -> None:
    values = tokens(SOURCE)
    assert OUTPUT.read_text(encoding="utf-8") == render(values)
    assert SHA256 in OUTPUT.read_text(encoding="utf-8")


def test_fresh_bridge_loads_the_shipped_declaration() -> None:
    assert ZIPABridge().version == ZIPA.version
