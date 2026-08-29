"""Checks against the optional live panphon installation."""

from __future__ import annotations

import csv
import importlib.util
import re
import unicodedata
from importlib.resources import files
from itertools import combinations_with_replacement
from pathlib import Path

import pytest
from ipakit.bridges.costmodel import compare, pack_from_declaration
from ipakit.features import IPAFeatures

panphon = pytest.importorskip("panphon")
panphon_distance = pytest.importorskip("panphon.distance")

ROOT = Path(__file__).parent.parent
DECLARATION = Path(__file__).parent / "panphon" / "panphon.xml"


def _generator():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "panphon_geometry", ROOT / "scripts" / "panphon_geometry.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_declaration_round_trips_from_the_live_library() -> None:
    assert DECLARATION.read_text(encoding="utf-8") == _generator().render()


def _raw_and_normalized_spellings() -> tuple[list[str], list[str]]:
    inventory = files("panphon").joinpath("data/ipa_all.csv")
    with inventory.open(newline="") as source:
        raw = [row["ipa"] for row in csv.DictReader(source)]
    normalized = [unicodedata.normalize("NFD", item) for item in raw]
    return raw, normalized


def test_exactly_90_inventory_spellings_change_when_normalized_to_nfd() -> None:
    raw, normalized = _raw_and_normalized_spellings()
    assert sum(left != right for left, right in zip(raw, normalized, strict=True)) == 90


def test_inventory_spelling_corpus_has_90_raw_key_and_0_nfd_key_mismatches() -> None:
    raw, normalized = _raw_and_normalized_spellings()
    live = panphon.FeatureTable()

    def tokenizer(keys: list[str]):  # type: ignore[no-untyped-def]
        longest_first = sorted(keys, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(key) for key in longest_first))

        def tokenize(word: str) -> list[str]:
            remaining = unicodedata.normalize("NFD", word)
            result: list[str] = []
            while remaining:
                match = pattern.match(remaining)
                if match is None:
                    remaining = remaining[1:]
                else:
                    result.append(match.group())
                    remaining = remaining[len(match.group()) :]
            return result

        return tokenize

    raw_tokenize = tokenizer(raw)
    nfd_tokenize = tokenizer(normalized)
    expected = [live.ipa_segs(spelling) for spelling in raw]
    raw_mismatches = sum(
        raw_tokenize(spelling) != value
        for spelling, value in zip(raw, expected, strict=True)
    )
    nfd_mismatches = sum(
        nfd_tokenize(spelling) != value
        for spelling, value in zip(raw, expected, strict=True)
    )
    # These 90 mismatches are tokenizer results over the inventory corpus;
    # the separate 90 above counts source spellings changed by normalization.
    assert raw_mismatches == 90
    assert nfd_mismatches == 0


def test_declared_pack_matches_panphon_feature_edit_distance() -> None:
    pack = pack_from_declaration(DECLARATION)
    ipa = IPAFeatures()
    oracle = panphon_distance.Distance()
    words = ["", "kat", "kot", "kʰat", "mbanda", "banda"]
    for source, target in combinations_with_replacement(words, 2):
        actual = compare(ipa, pack, source, target).edit_cost
        assert actual == oracle.feature_edit_distance(source, target)
