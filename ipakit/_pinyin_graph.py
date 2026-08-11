"""Minimal syllable-primary Pinyin model and orthographic codec."""

from __future__ import annotations

from dataclasses import dataclass

from ._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ._tiergraph_builder import GraphBuilder
from .bridges.pinyin import PINYIN


@dataclass(frozen=True)
class PinyinDialect:
    """Declared spellings accepted at the Pinyin input boundary."""

    input_encodings: tuple[tuple[str, str], ...] = PINYIN.inputs


BASE_PINYIN = PinyinDialect()


def _decode_input(value: str, dialect: PinyinDialect) -> str:
    for source, target in dialect.input_encodings:
        value = value.replace(source, target)
    return value


def declarations() -> Declarations:
    names = ("spelling", "value", "role", "ipa")
    return Declarations(
        (
            TierDeclaration("syllable", frozenset({"spelling", "ipa"})),
            TierDeclaration("constituent", frozenset({"spelling", "role"})),
            TierDeclaration("tone", frozenset({"value"})),
            TierDeclaration("phonetic", frozenset({"ipa"})),
        ),
        tuple(FeatureDeclaration(n) for n in names),
        (
            RelationDeclaration(
                "contains",
                acyclic=True,
                containment=True,
                source_tiers=frozenset({"syllable"}),
                target_tiers=frozenset({"constituent"}),
            ),
            RelationDeclaration(
                "associates-with",
                source_tiers=frozenset({"tone"}),
                target_tiers=frozenset({"syllable"}),
            ),
            RelationDeclaration(
                "realized-by",
                source_tiers=frozenset({"syllable"}),
                target_tiers=frozenset({"phonetic"}),
            ),
        ),
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
) -> Graph:
    spelling = _decode_input(spelling, dialect)
    onset = _decode_input(onset, dialect)
    rhyme = _decode_input(rhyme, dialect)
    builder = GraphBuilder(declarations())
    syllable = builder.append_input_atom(
        "syllable",
        {
            "spelling": spelling,
            **({"ipa": ipa} if ipa is not None and not referenced else {}),
        },
    )
    parts = []
    if onset:
        parts.append(
            builder.add_event(
                "constituent", 0, {"spelling": onset, "role": "onset"}, duration=0
            )
        )
    parts.append(
        builder.add_event(
            "constituent", 0, {"spelling": rhyme, "role": "rhyme-nucleus"}, duration=0
        )
    )
    builder.contain(syllable, parts)
    mark = builder.add_event("tone", 0, {"value": tone}, duration=0)
    builder.relate((mark,), "associates-with", (syllable,))
    if ipa is not None and referenced:
        realization = builder.add_event("phonetic", 0, {"ipa": ipa}, duration=0)
        builder.relate((syllable,), "realized-by", (realization,))
    return builder.build()


def tone_index(spelling: str) -> int:
    return PINYIN.tone_index(spelling)


def render(graph: Graph) -> str:
    return PINYIN.render(graph)
