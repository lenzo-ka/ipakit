"""Characterizations of panphon 0.22.2 behavior used by the bridge."""

import csv
import unicodedata
from importlib.resources import files

import pytest

panphon = pytest.importorskip("panphon")
panphon_distance = pytest.importorskip("panphon.distance")
FeatureTable = panphon.FeatureTable
Distance = panphon_distance.Distance


def test_panphon_substitution_is_symmetric_difference_over_twice_the_vector_length() -> (
    None
):
    distance = Distance()
    segments = [segment.numeric() for _, segment in distance.fm.segments[:140]]
    mismatches = 0
    checked = 0
    for index, left in enumerate(segments):
        for right in segments[index + 1 :]:
            expected = sum(abs(a - b) for a, b in zip(left, right, strict=True)) / (
                2 * len(left)
            )
            measured = distance.unweighted_substitution_cost(left, right)
            mismatches += (
                measured != expected
                or measured != distance.unweighted_substitution_cost(right, left)
            )
            checked += 1
    assert checked == 9730
    assert mismatches == 0


def test_panphon_prices_a_substitution_at_half_an_indel_pair() -> None:
    distance = Distance()
    k = distance.fm.fts("k").numeric()
    a = distance.fm.fts("a").numeric()
    assert distance.unweighted_substitution_cost(k, a) == 0.3333333333333333
    assert (
        distance.unweighted_deletion_cost(k) + distance.unweighted_insertion_cost(a)
        == 1.8333333333333333
    )


def test_panphon_weight_vector_is_two_shorter_than_its_feature_vector() -> None:
    fm = FeatureTable()
    assert len(fm.weights) == 22
    assert len(fm.names) == 24


def test_panphon_weight_columns_are_permuted_against_the_feature_columns() -> None:
    fm = FeatureTable()
    weights = files("panphon").joinpath("data/feature_weights.csv")
    with weights.open(newline="") as source:
        columns = next(csv.reader(source))
    assert columns[19:22] == ["tense", "long", "velaric"]
    assert fm.names[19:22] == ["velaric", "tense", "long"]


def test_panphon_normalizes_its_spelling_column_to_nfd() -> None:
    fm = FeatureTable()
    inventory = files("panphon").joinpath("data/ipa_all.csv")
    with inventory.open(newline="") as source:
        raw = [row["ipa"] for row in csv.DictReader(source)]
    normalized = {unicodedata.normalize("NFD", spelling) for spelling in raw}
    assert (
        sum(spelling != unicodedata.normalize("NFD", spelling) for spelling in raw)
        == 90
    )
    assert set(fm.seg_dict) == normalized
    assert len(fm.seg_dict) == 6367


def test_panphon_deletes_unknown_segments_without_saying_so() -> None:
    fm = FeatureTable()
    assert fm.ipa_segs("bɚd") == ["b", "d"]
    assert fm.ipa_segs("ɚ") == []
    assert fm.validate_word("bɚd") is False
    assert Distance().feature_edit_distance("ɚ", "ɝ") == 0


def test_word_to_vector_list_standardizes_tones_and_ipa_segs_does_not() -> None:
    fm = FeatureTable()
    assert len(fm.word_to_vector_list("¹")) == 1
    assert fm.ipa_segs("¹") == []
