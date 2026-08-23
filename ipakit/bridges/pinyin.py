"""Declared Hanyu Pinyin spelling convention."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import tiergraph as tg

from .vocabulary import VocabularyBridge

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "pinyin" / "pinyin.xml"


class PinyinBridge(VocabularyBridge):
    """The declared Hanyu Pinyin inputs, vowels, and tone-mark renderer."""

    def __init__(self) -> None:
        """Load the shipped Hanyu Pinyin declaration."""

        super().__init__(_PATH)
        root = ET.parse(_PATH).getroot()
        self.inputs = tuple(
            (e.attrib["source"], e.attrib["target"]) for e in root.findall("input")
        )
        self.tones = {
            e.attrib["vowel"]: e.attrib["marks"] for e in root.findall("tone")
        }

    def decode_input(self, value: str) -> str:
        """Replace each declared keyboard spelling with its Pinyin spelling."""

        for source, target in self.inputs:
            value = value.replace(source, target)
        return value

    def tone_index(self, spelling: str) -> int:
        """Return the vowel position that Pinyin's tone-placement rules select."""

        lowered = spelling.lower()
        for vowel in "ae":
            if vowel in lowered:
                return lowered.index(vowel)
        if "ou" in lowered:
            return lowered.index("o")
        if "iu" in lowered or "ui" in lowered:
            return max(lowered.rfind("iu"), lowered.rfind("ui")) + 1
        return max(lowered.rfind(vowel) for vowel in self.tones)

    def render(
        self, graph: tg.Graph, syllable_tier: str = "syllable", tone_tier: str = "tone"
    ) -> str:
        """Render syllable events with their associated tone marks."""

        tones: dict[tg.ItemRef, int] = {}
        for relation in graph.polyadic_relations:
            if (
                relation.declaration.local_name != "associates-with"
                or len(relation.sources) != 1
            ):
                continue
            source = relation.sources[0]
            if not isinstance(source, tg.ItemRef):
                continue
            if source.tier.local_name != tone_tier:
                continue
            source_tier = next(
                tier for tier in graph.tiers if tier.declaration.name == source.tier
            )
            item = source_tier.items[source.index]
            level = next(
                (
                    int(value.lexical)
                    for value in item.attributes
                    if value.name.local_name == "value"
                ),
                None,
            )
            if level is not None:
                tones.update(
                    {
                        target: level
                        for target in relation.targets
                        if isinstance(target, tg.ItemRef)
                    }
                )

        rendered = []
        for tier in graph.tiers:
            if tier.declaration.name.local_name != syllable_tier:
                continue
            for index, item in enumerate(tier.items):
                attributes = {
                    value.name.local_name: value.lexical for value in item.attributes
                }
                spelling = attributes.get("spelling", attributes.get("value", ""))
                level = tones.get(tg.ItemRef(tier.declaration.name, index))
                if level is None or level == 5:
                    rendered.append(spelling)
                    continue
                position = self.tone_index(spelling)
                if position < 0 or not 1 <= level <= 4:
                    raise ValueError(f"tone {level!r} cannot be placed on {spelling!r}")
                vowel = spelling[position].lower()
                rendered.append(
                    spelling[:position]
                    + self.tones[vowel][level - 1]
                    + spelling[position + 1 :]
                )
        return "".join(rendered)


PINYIN = PinyinBridge()
