from __future__ import annotations

import json
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit._cmu_graph import (
    BASE_CMUDICT,
    IPA_PROJECTION_LOSSES,
    POCKETSPHINX,
    corpus_entries,
    projection_losses,
    read,
    render,
)
from ipakit._codecs import render_pinyin as render_generic_pinyin
from ipakit._katakana_codec import render as render_katakana
from ipakit._mora_graph import build as build_mora_tone
from ipakit._mora_graph import declarations as mora_declarations
from ipakit._pinyin_graph import build as build_pinyin
from ipakit._pinyin_graph import render as render_pinyin
from ipakit._pinyin_graph import tone_index
from ipakit._rewrite_graph import japanese_moraic_fixture, japanese_moraic_fixtures
from ipakit._tiergraph import Graph
from ipakit._tiergraph_json import Model, dumps, loads

HERE = Path(__file__).parent
CMUDICT = HERE / "cmudict"


def test_cmu_family_capabilities_and_stress_projection_are_declared():
    assert (BASE_CMUDICT.purpose, BASE_CMUDICT.preserves_stress) == ("tts", True)
    assert (POCKETSPHINX.purpose, POCKETSPHINX.preserves_stress) == ("asr", False)
    assert render(read(("<s>", "SIL", "</s>"), POCKETSPHINX), POCKETSPHINX) == (
        "<s>",
        "SIL",
        "</s>",
    )
    assert {loss.feature for loss in IPA_PROJECTION_LOSSES} == {
        "vowel-quality",
        "rhotic-vowel-quality",
    }
    graph = read(("IY0", "IY1", "IY2"))
    assert render(graph) == ("IY0", "IY1", "IY2")
    before = graph.to_data()
    assert render(graph, POCKETSPHINX) == ("IY", "IY", "IY")
    assert graph.to_data() == before
    assert projection_losses(graph, POCKETSPHINX)[0].feature == "stress"
    stressless = read(("IY",), POCKETSPHINX)
    item = stressless.tiers[0].items[0]
    assert all(attribute.name.local_name != "stress" for attribute in item.attributes)


def test_cmu_stress_digit_requires_a_declared_phone_policy():
    with pytest.raises(ValueError, match=r"B1$"):
        read(("B1",))
    assert render(read(("B",))) == ("B",)
    assert render(read(("AH1",))) == ("AH1",)


def test_pinned_upstream_oracle_fixture_is_offline_and_matches_codec():
    metadata = json.loads((CMUDICT / "upstream.json").read_text())
    assert metadata["repository"] == "https://github.com/cmusphinx/cmudict.git"
    assert len(metadata["commit"]) == 40 and not metadata["network_required"]
    rows = [
        line.split("\t")
        for line in (CMUDICT / metadata["fixture"]).read_text().splitlines()
        if line and not line.startswith(";;;")
    ]
    for _, source, expected in rows:
        assert render(read(tuple(source.split())), POCKETSPHINX) == tuple(
            expected.split()
        )


def test_development_corpus_adapter_reads_only_a_local_checkout(tmp_path):
    (tmp_path / "cmudict.dict").write_text(
        "WORD  W ER1 D\nWORD(2)  W ER0 D\n", encoding="latin-1"
    )
    assert list(corpus_entries(tmp_path)) == [
        ("WORD", ("W", "ER1", "D")),
        ("WORD", ("W", "ER0", "D")),
    ]


@pytest.mark.parametrize(
    ("plain", "tone", "marked", "index"), [("shui", 3, "shuǐ", 3), ("liu", 2, "liú", 2)]
)
def test_pinyin_tone_is_syllable_hosted_but_codec_placed(plain, tone, marked, index):
    graph = build_pinyin(
        plain, plain[:2], plain[2:], tone, ipa={"spelling": "placeholder"}
    )
    assert tone_index(plain) == index
    assert render_pinyin(graph) == marked
    assert render_generic_pinyin(graph) == marked
    relation = next(r for r in graph.relations if r.name == "associates-with")
    assert relation.targets == ("/clock/0/syllable/0",)
    restored = Graph.from_data(
        graph.declarations, json.loads(json.dumps(graph.to_data()))
    )
    assert restored == graph


def test_pinyin_renderers_share_a_priority_for_synthetic_both_vowels():
    graph = build_pinyin("ea", "", "ea", 1)
    assert tone_index("ea") == 1
    assert render_pinyin(graph) == render_generic_pinyin(graph) == "eā"


def test_pinyin_referenced_phonetic_realization_is_optional():
    graph = build_pinyin(
        "ma", "m", "a", 1, ipa={"segments": ["m", "a"]}, referenced=True
    )
    assert any(r.name == "realized-by" for r in graph.relations)


def test_tone_associates_with_multiple_morae_and_round_trips():
    graph = build_mora_tone(("to", "o"), "high")
    model = Model("moraic-gairaigo", "1", mora_declarations())
    restored = loads(dumps(graph, model), model)
    assert restored == graph
    association = restored.relations[0]
    assert association.targets == ("/clock/0/mora/0", "/clock/1/mora/0")


EXPECTED_KANA = {
    "pen": "ペン",
    "hot": "ホット",
    "bed": "ベッド",
    "cheese": "チーズ",
    "beer": "ビール",
    "strike": "ストライク",
    "London": "ロンドン",
    "Christmas": "クリスマス",
}


@pytest.mark.parametrize("name", EXPECTED_KANA)
def test_katakana_is_rendered_only_from_derived_morae(name):
    inventory = IPAFeatures()
    form = japanese_moraic_fixture(name, inventory)
    assert render_katakana(form) == EXPECTED_KANA[name]
    special = {"ッ", "ン", "ー"}
    segment_surface = "".join(
        str(event.features.get("spelling", ""))
        for node in form.__dict__["_tiergraph_index"].clock
        for group in node.groups
        if group.tier != "mora"
        for event in group.events
    )
    assert special.isdisjoint(segment_surface)


def test_gairaigo_fixture_set_is_exact_and_excludes_palatalization_guesswork():
    assert set(japanese_moraic_fixtures()) == set(EXPECTED_KANA)
    assert (
        "camera" not in japanese_moraic_fixtures()
    )  # kya-class mismatch: exclude, do not invent
