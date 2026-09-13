"""Pinyin rendering witnesses independent of the one-syllable constructor."""

from __future__ import annotations

import unicodedata

import pytest
from ipakit._codecs import render_pinyin
from ipakit._pinyin_graph import build
from ipakit.bridges.pinyin import PINYIN
from tiergraph.build import document, item

import tiergraph as tg


def word_graph(
    spellings=("ma",),
    levels=(1,),
    targets=(0,),
    *,
    namespace="urn:ipakit:pinyin",
    foreign_spelling=False,
    foreign_relation=False,
    foreign_tier=False,
):
    builder = document(namespace, prefix="pinyin")
    builder.namespace("urn:other", prefix="other")
    spelling = builder.qname("spelling")
    other = builder.qname("spelling", namespace="urn:other")
    builder.attribute(spelling, tg.XsdType.STRING)
    builder.attribute(other, tg.XsdType.STRING)
    builder.attribute("value", tg.XsdType.INTEGER)
    syllables = builder.tier(
        "syllable",
        tuple(
            item(attrs={spelling: text, **({other: "sha"} if foreign_spelling else {})})
            for text in spellings
        ),
        item_type="syllable",
        membership="syllables",
    )
    if foreign_tier:
        builder.tier(
            builder.qname("syllable", namespace="urn:other"),
            (item(attrs={other: "sha"}),),
            item_type="other-syllable",
            membership="other-syllables",
        )
    tones = builder.tier(
        "tone",
        tuple(item(value=level) for level in levels),
        item_type="tone",
        membership="tones",
    )
    relation = builder.qname(
        "associates-with", namespace="urn:other" if foreign_relation else namespace
    )
    side = (tg.RelationEndpointKind.ITEM,)
    builder.declare(
        tg.PolyadicRelationDeclaration(
            relation,
            tg.RelationSideDeclaration(side, (tones.name,), maximum=1),
            tg.RelationSideDeclaration(side, (syllables.name,), maximum=1),
        )
    )
    for index, target in enumerate(targets):
        builder.relate(
            tg.PolyadicRelationInstance(
                relation,
                (tones.ref(index),),
                (syllables.ref(target),),
            )
        )
    graph = builder.build()
    assert tg.wire.loads(tg.wire.dumps(graph)) == graph
    return graph


@pytest.mark.parametrize(
    ("spelling", "level", "expected"),
    [
        ("Ai", 4, "Ài"),
        ("MA", 1, "MĀ"),
        ("LU:", 4, "LǛ"),
        ("LV", 4, "LǛ"),
        ("lu\u0308", 3, "lǚ"),
        ("lü", 3, "lǚ"),
        ("shui", 3, "shuǐ"),
        ("liu", 2, "liú"),
        ("ou", 3, "ǒu"),
        ("GUI", 4, "GUÌ"),
        ("ma", 5, "ma"),
    ],
)
def test_tone_spelling_preserves_case_and_canonical_vowels(spelling, level, expected):
    # Test both the constructor boundary and externally supplied graph facts.
    for graph in (
        build(spelling, "", spelling, level),
        word_graph((spelling,), (level,)),
    ):
        before = tg.wire.dumps(graph)
        assert render_pinyin(graph) == expected
        assert unicodedata.is_normalized("NFC", PINYIN.render(graph))
        assert tg.wire.dumps(graph) == before


@pytest.mark.parametrize("levels", [(1, 4), (4, 1), (1, 1)])
def test_multiple_tones_require_explicit_selection(levels):
    with pytest.raises(ValueError, match="multiple tone associations"):
        render_pinyin(word_graph(levels=levels, targets=(0, 0)))


@pytest.mark.parametrize("level", [0, 6, True, 1.0])
def test_constructor_checks_internal_tone_category(level):
    with pytest.raises(ValueError, match="integer from 1 through 5"):
        build("ma", "m", "a", level)


@pytest.mark.parametrize("level", [0, 6])
def test_external_graph_tone_category_is_checked(level):
    with pytest.raises(ValueError, match="integer from 1 through 5"):
        render_pinyin(word_graph(levels=(level,)))


def test_unrelated_namespaces_cannot_supply_spelling_or_tone():
    assert render_pinyin(word_graph(foreign_spelling=True)) == "mā"
    assert render_pinyin(word_graph(levels=(4,), foreign_relation=True)) == "ma"


def test_namespace_selection_is_explicit_when_local_names_collide():
    graph = word_graph(foreign_tier=True)
    with pytest.raises(ValueError, match="unambiguous syllable tier"):
        render_pinyin(graph)
    assert render_pinyin(graph, namespace="urn:ipakit:pinyin") == "mā"
    assert (
        render_pinyin(
            graph, syllable_tier=tg.QualifiedName("urn:ipakit:pinyin", "syllable")
        )
        == "mā"
    )


def test_custom_namespace_binds_attributes_and_relations_together():
    assert render_pinyin(word_graph(namespace="urn:test:custom")) == "mā"


@pytest.mark.parametrize(
    ("spellings", "levels", "expected"),
    [
        (("xi", "an"), (1, 1), "xī'ān"),
        (("Xi", "an"), (1, 1), "Xī'ān"),
        (("tian", "e"), (1, 2), "tiān'é"),
        (("hai", "ou"), (3, 1), "hǎi'ōu"),
        (("liu", "shui"), (2, 3), "liúshuǐ"),
    ],
)
def test_word_rendering_preserves_syllable_boundaries(spellings, levels, expected):
    assert render_pinyin(word_graph(spellings, levels, (0, 1))) == expected


def test_premarked_input_requires_an_explicit_retone_operation():
    for level in (1, 5):
        with pytest.raises(ValueError, match="unmarked"):
            render_pinyin(word_graph(("mǎ",), (level,)))


def test_declared_vocabulary_atoms_preserve_grouping_and_spelling():
    # These six symbol atoms are distinct from the IPA syllable membership list.
    for atom in PINYIN.atoms:
        form = PINYIN.read(atom.output)
        assert form.to_ipa() == atom.spelling
        assert PINYIN.emit(form) == atom.output
        declarations = form.__dict__["_tiergraph_index"].containment_input.declarations
        assert (
            len([tier for tier in declarations.tiers if tier.name == "syllable"]) == 1
        )
        assert tg.wire.loads(tg.wire.dumps(form._graph)) == form._graph
