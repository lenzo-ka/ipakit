"""Minimal syllable-primary Pinyin model and orthographic codec."""

from __future__ import annotations

from ._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ._tiergraph_builder import GraphBuilder


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
) -> Graph:
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
    marks = {
        "a": "āáǎà",
        "e": "ēéěè",
        "i": "īíǐì",
        "o": "ōóǒò",
        "u": "ūúǔù",
        "ü": "ǖǘǚǜ",
    }
    lowered = spelling.lower()
    for vowel in "ae":
        if vowel in lowered:
            return lowered.index(vowel)
    if "ou" in lowered:
        return lowered.index("o")
    # In iu/ui the mark belongs to the second written vowel, not the last-vowel
    # shortcut's accidental choice among the whole vowel alphabet.
    if "iu" in lowered or "ui" in lowered:
        pair = max(lowered.rfind("iu"), lowered.rfind("ui"))
        return pair + 1
    return max(lowered.rfind(v) for v in marks)


def render(graph: Graph) -> str:
    marks = {
        "a": "āáǎà",
        "e": "ēéěè",
        "i": "īíǐì",
        "o": "ōóǒò",
        "u": "ūúǔù",
        "ü": "ǖǘǚǜ",
    }
    syllable = next(
        event
        for node in graph.clock
        for group in node.groups
        if group.tier == "syllable"
        for event in group.events
    )
    tone = next(
        event
        for node in graph.clock
        for group in node.groups
        if group.tier == "tone"
        for event in group.events
    )
    spelling = str(syllable.features["spelling"])
    raw_level = tone.features["value"]
    if not isinstance(raw_level, int):
        raise ValueError("Pinyin tone value must be an integer")
    level = raw_level
    if level == 5:
        return spelling
    index = tone_index(spelling)
    vowel = spelling[index].lower()
    return spelling[:index] + marks[vowel][level - 1] + spelling[index + 1 :]
