"""Minimal syllable-primary Pinyin model and orthographic codec."""

from __future__ import annotations

import json
from dataclasses import dataclass

from tiergraph.build import document
from tiergraph.build import item as graph_item

import tiergraph as tg

from .bridges.pinyin import PINYIN


@dataclass(frozen=True)
class PinyinDialect:
    """Declared spellings accepted at the Pinyin input boundary."""

    input_encodings: tuple[tuple[str, str], ...] = PINYIN.inputs


BASE_PINYIN = PinyinDialect()
_NAMESPACE = "urn:ipakit:pinyin"


def _decode_input(value: str, dialect: PinyinDialect) -> str:
    for source, target in dialect.input_encodings:
        value = value.replace(source, target)
    return value


def declarations() -> tuple[tg.AttributeDeclaration, ...]:
    """Return native declarations for authoritative Pinyin item facts."""
    return tuple(
        tg.AttributeDeclaration(
            tg.QualifiedName(_NAMESPACE, name),
            tg.AttributeDomain.ITEM,
            value_type,
        )
        for name, value_type in (
            ("spelling", tg.XsdType.STRING),
            ("value", tg.XsdType.INTEGER),
            ("role", tg.XsdType.STRING),
            ("ipa", tg.XsdType.STRING),
        )
    )


def _relation_side(
    tier: tg.QualifiedName, *, minimum: int = 1, maximum: int | None = 1
) -> tg.RelationSideDeclaration:
    return tg.RelationSideDeclaration(
        (tg.RelationEndpointKind.ITEM,),
        (tier,),
        minimum=minimum,
        maximum=maximum,
    )


def build(
    spelling: str,
    onset: str,
    rhyme: str,
    tone: int,
    *,
    ipa: object | None = None,
    referenced: bool = False,
    dialect: PinyinDialect = BASE_PINYIN,
) -> tg.Graph:
    """Build the native four-tier Pinyin graph and its declared relations."""
    spelling = _decode_input(spelling, dialect)
    onset = _decode_input(onset, dialect)
    rhyme = _decode_input(rhyme, dialect)
    builder = document(_NAMESPACE, prefix="pinyin")
    for declaration in declarations():
        builder.attribute(
            declaration.name,
            declaration.value_type,
            domain=declaration.domain,
        )

    syllable = builder.tier(
        "syllable",
        (
            graph_item(
                attrs={
                    "spelling": spelling,
                    **(
                        {
                            "ipa": json.dumps(
                                ipa, ensure_ascii=False, separators=(",", ":")
                            )
                        }
                        if ipa is not None and not referenced
                        else {}
                    ),
                }
            ),
        ),
        item_type="syllable",
        membership="syllable-members",
    )
    constituent_values: tuple[tuple[str, str], ...] = (
        ((onset, "onset"),) if onset else ()
    )
    constituent_values += ((rhyme, "rhyme-nucleus"),)
    constituent = builder.tier(
        "constituent",
        (graph_item(spelling=value, role=role) for value, role in constituent_values),
        item_type="constituent",
        membership="constituent-members",
    )
    tone_tier = builder.tier(
        "tone",
        (graph_item(value=tone),),
        item_type="tone",
        membership="tone-members",
    )
    phonetic = builder.tier(
        "phonetic",
        (
            (
                graph_item(
                    ipa=json.dumps(ipa, ensure_ascii=False, separators=(",", ":"))
                ),
            )
            if ipa is not None and referenced
            else ()
        ),
        item_type="phonetic",
        membership="phonetic-members",
    )

    contains = builder.qname("contains")
    associates = builder.qname("associates-with")
    realized = builder.qname("realized-by")
    builder.declare(
        tg.PolyadicRelationDeclaration(
            contains,
            _relation_side(syllable.name),
            _relation_side(constituent.name, maximum=None),
            unique_sources=True,
            acyclic=True,
        )
    )
    builder.declare(
        tg.PolyadicRelationDeclaration(
            associates,
            _relation_side(tone_tier.name),
            _relation_side(syllable.name),
        )
    )
    builder.declare(
        tg.PolyadicRelationDeclaration(
            realized,
            _relation_side(syllable.name),
            _relation_side(phonetic.name),
        )
    )
    builder.relate(
        tg.PolyadicRelationInstance(
            contains,
            (syllable.ref(0),),
            tuple(constituent.ref(index) for index in range(len(constituent_values))),
        )
    )
    builder.relate(
        tg.PolyadicRelationInstance(associates, (tone_tier.ref(0),), (syllable.ref(0),))
    )
    if ipa is not None and referenced:
        builder.relate(
            tg.PolyadicRelationInstance(
                realized, (syllable.ref(0),), (phonetic.ref(0),)
            )
        )
    return builder.build()


def tone_index(spelling: str) -> int:
    return PINYIN.tone_index(spelling)


def render(graph: tg.Graph) -> str:
    return PINYIN.render(graph)
