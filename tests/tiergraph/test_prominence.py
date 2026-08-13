from __future__ import annotations

import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import ipakit
import pytest


def _events(form: ipakit.Form, tier: str):
    graph = form._graph
    return [
        graph.resolve(reference).event
        for reference in graph.event_references()
        if graph.resolve(reference).tier == tier
    ]


def test_upward_prominence_round_trips_and_raises_to_the_word() -> None:
    form = ipakit.read("^am", strict=True)
    assert form.to_ipa() == "^am"
    (word,) = _events(form, "word")
    assert word is not None and word.features["prominence"] == "emphatic"
    assert all(
        "prominence" not in event.features
        for tier in ("segment", "boundary")
        for event in _events(form, tier)
        if event is not None
    )


def test_repetition_walks_the_declaration_and_unmarked_is_the_norm() -> None:
    inventory = ipakit.IPAFeatures()
    feature = inventory.features["prominence"]
    assert feature.values == ["reduced", "norm", "emphatic", "strong"]
    assert feature.default is None
    assert feature.centre == "norm"
    (raised,) = _events(inventory.read("^^am", strict=True), "word")
    assert raised is not None and raised.features["prominence"] == "strong"
    assert _events(inventory.read("am", strict=True), "word") == []
    assert inventory.read("am", strict=True).to_ipa() == "am"


def test_one_more_repetition_is_an_unregistered_symbol_refusal() -> None:
    with pytest.raises(ValueError, match="unregistered symbol.*no declared prominence"):
        ipakit.read("^^^am", strict=True)


def test_a_mark_reaching_no_unit_warns_and_strict_read_raises() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert ipakit.read("^").to_ipa() == "^"
    assert any("unbound prominence mark" in str(item.message) for item in caught)
    with pytest.raises(ValueError, match="unbound prominence mark"):
        ipakit.read("^", strict=True)


@pytest.mark.parametrize("text", ["ba^d", "a^m", "b^ad"])
def test_a_mark_inside_a_word_is_refused_instead_of_silently_lost(text: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert ipakit.read(text).to_ipa() == text
    assert any(
        "misplaced prominence mark" in str(item.message)
        and "['^']" in str(item.message)
        for item in caught
    )
    with pytest.raises(ValueError, match=r"misplaced prominence mark.*\['\^'\]"):
        ipakit.read(text, strict=True)


@pytest.mark.parametrize(
    "text",
    [
        "^am",
        "^^am",
        "^əm",
        "^ˈam",
        "ˈ^am",
        "^bad",
        "  ^am",
        "^am ^bad",
        "^am#^bad",
        "^am|^bad",
        "^am‖^bad",
    ],
)
def test_well_formed_prominence_positions_keep_their_reading(text: str) -> None:
    form = ipakit.read(text, strict=True)
    assert form.to_ipa() == text
    assert _events(form, "word")


@pytest.mark.parametrize("edit", ["rename", "remove"])
def test_the_named_prominence_declaration_is_a_load_time_contract(
    tmp_path: Path, edit: str
) -> None:
    tree = ET.parse(ipakit.DATA_DIR / "ipa.xml")
    features = tree.getroot().find("features")
    assert features is not None
    declaration = features.find("feature[@name='prominence']")
    assert declaration is not None
    if edit == "rename":
        declaration.set("name", "renamed-prominence")
    else:
        features.remove(declaration)
    path = tmp_path / "ipa.xml"
    tree.write(path, encoding="unicode")
    with pytest.raises(
        ValueError,
        match="requires a declared 'prominence' feature.*missing or renamed",
    ):
        ipakit.IPAFeatures(path)


@pytest.mark.parametrize("text", ["^", "am^"])
def test_a_mark_reaching_no_unit_keeps_its_existing_refusal(text: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert ipakit.read(text).to_ipa() == text
    assert any("unbound prominence mark" in str(item.message) for item in caught)
    with pytest.raises(ValueError, match="unbound prominence mark"):
        ipakit.read(text, strict=True)


def test_an_undeclared_repetition_keeps_its_existing_refusal() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert ipakit.read("^^^am").to_ipa() == "^^^am"
    assert any("no declared prominence level" in str(item.message) for item in caught)
    with pytest.raises(ValueError, match="no declared prominence level"):
        ipakit.read("^^^am", strict=True)


def test_emphasis_and_reduced_vowel_are_independent_assertions() -> None:
    form = ipakit.read("^əm", strict=True)
    (word,) = _events(form, "word")
    vowel, consonant = _events(form, "segment")
    assert word is not None and word.features["prominence"] == "emphatic"
    assert vowel is not None and vowel.features["spelling"] == "ə"
    assert consonant is not None and consonant.features["spelling"] == "m"
    assert form.to_ipa() == "^əm"
