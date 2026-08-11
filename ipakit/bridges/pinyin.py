"""Declared Hanyu Pinyin spelling convention."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .._codecs import RenderLane, RenderProfile, render_graph
from .._tiergraph import Event, Graph
from .vocabulary import VocabularyBridge

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "pinyin" / "pinyin.xml"


class PinyinBridge(VocabularyBridge):
    def __init__(self) -> None:
        super().__init__(_PATH)
        root = ET.parse(_PATH).getroot()
        self.inputs = tuple(
            (e.attrib["source"], e.attrib["target"]) for e in root.findall("input")
        )
        self.tones = {
            e.attrib["vowel"]: e.attrib["marks"] for e in root.findall("tone")
        }

    def decode_input(self, value: str) -> str:
        for source, target in self.inputs:
            value = value.replace(source, target)
        return value

    def tone_index(self, spelling: str) -> int:
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
        self, graph: Graph, syllable_tier: str = "syllable", tone_tier: str = "tone"
    ) -> str:
        tones: dict[str, int] = {}
        for relation in graph.relations:
            if relation.name != "associates-with" or len(relation.sources) != 1:
                continue
            source = graph.resolve(relation.sources[0])
            if source.tier == tone_tier and source.event is not None:
                level = source.event.features.get("value")
                if isinstance(level, int):
                    tones.update({target: level for target in relation.targets})

        def syllable(event: Event) -> str:
            spelling = str(
                event.features.get("spelling", event.features.get("value", ""))
            )
            # Compatibility indices identify the same event paths used by associations.
            level = next(
                (tones.get(ref) for ref in tones if graph.resolve(ref).event is event),
                None,
            )
            if level is None or level == 5:
                return spelling
            position = self.tone_index(spelling)
            if position < 0 or not 1 <= level <= 4:
                raise ValueError(f"tone {level!r} cannot be placed on {spelling!r}")
            vowel = spelling[position].lower()
            return (
                spelling[:position]
                + self.tones[vowel][level - 1]
                + spelling[position + 1 :]
            )

        return render_graph(
            graph, RenderProfile((RenderLane(syllable_tier, "spelling", syllable),))
        )


PINYIN = PinyinBridge()
