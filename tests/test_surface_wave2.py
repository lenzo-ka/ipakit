from __future__ import annotations

import ipakit
import pytest
from ipakit import _corpus
from ipakit import corpus as corpus_api
from ipakit._pinyin_graph import build as build_pinyin
from ipakit._pinyin_graph import render as render_pinyin
from ipakit.features import IPAFeatures


def test_space_is_word_boundary_with_exact_spelling_and_run_collapse(tmp_path):
    spaced = ipakit.read("kat   dɒɡ")
    marked = ipakit.read("kat#dɒɡ")
    assert spaced == marked
    assert spaced.to_ipa() == "kat   dɒɡ"
    assert marked.to_ipa() == "kat#dɒɡ"
    assert [unit.text for unit in spaced.units].count("#") == 1
    assert list(corpus_api.find(spaced, "t / _ #"))
    assert list(corpus_api.find(marked, "t / _ #"))

    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("dog", {}, {"cited": spaced})
    assert _corpus.open(tmp_path / "corpus").read("dog").forms["cited"] == spaced
    assert (
        _corpus.open(tmp_path / "corpus").read("dog").forms["cited"].to_ipa()
        == "kat   dɒɡ"
    )


def test_edge_space_has_the_same_explicit_boundary_structure_as_hash():
    assert ipakit.read(" kat ") == ipakit.read("#kat#")
    assert ipakit.read(" kat ").to_ipa() == " kat "


def test_segmented_style_is_explicit_and_token_preserving():
    assert ipakit.read("k æ t", segmented=True) == ipakit.read("kæt")
    assert ipakit.read("t s", segmented=True) != ipakit.read("t͡s")
    assert len(ipakit.read("t s", segmented=True).units) == 2
    assert ipakit.read("k æ t\nd ɒ ɡ", segmented=True) == ipakit.read("kæt#dɒɡ")
    assert ipakit.read("k æ t#d ɒ ɡ", segmented=True) == ipakit.read("kæt#dɒɡ")
    assert ipakit.read("a i").to_ipa() == "a i"
    assert ipakit.read("g a", segmented=True, wild=True).to_ipa() == "ɡa"
    with pytest.raises(ValueError, match="segmented token 'Q'"):
        ipakit.read("k Q t", segmented=True)


def test_form_at_dereferences_match_paths_and_names_bad_path():
    form = ipakit.read("kat#dɒɡ")
    match = next(corpus_api.find(form, "t / _ #"))
    assert form.at(match.paths[0]).features["value"].to_ipa() == "t"
    with pytest.raises(ValueError, match=r"/clock/2/missing/0"):
        form.at("/clock/2/missing/0")


@pytest.mark.parametrize("written", ["lv", "lu:"])
def test_pinyin_ascii_u_umlaut_encodings_are_declared_inputs(written):
    assert render_pinyin(build_pinyin(written, "l", written[1:], 4)) == "lǜ"


def test_derived_read_cache_drop_cannot_serve_the_populated_value():
    features = IPAFeatures()
    populated = features.tie_marks
    assert "tie_marks" in features.__dict__
    features._invalidate_derived_reads()
    assert "tie_marks" not in features.__dict__
    assert features.tie_marks == populated
    assert features.tie_marks is not populated
