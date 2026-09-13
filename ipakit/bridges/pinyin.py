"""Declared Hanyu Pinyin spelling convention."""

from __future__ import annotations

import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

import tiergraph as tg

from .vocabulary import Atom, VocabularyBridge

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "pinyin" / "pinyin.xml"


def decode_input(value: str, encodings: tuple[tuple[str, str], ...]) -> str:
    """Normalize Unicode and apply declared aliases, retaining letter case."""
    value = unicodedata.normalize("NFC", value)
    for source, target in encodings:
        value = value.replace(source, target).replace(source.upper(), target.upper())
    return unicodedata.normalize("NFC", value)


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

        return decode_input(value, self.inputs)

    def tokenize(self, text: str | Sequence[str]) -> tuple[Atom, ...]:
        """Read explicitly separated simple-vowel symbols.

        Multi-letter finals require contextual analysis; interpreting them as
        adjacent isolated vowels would assign the wrong pronunciation.
        """
        return super().tokenize(text.split() if isinstance(text, str) else text)

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
        self,
        graph: tg.Graph,
        syllable_tier: str | tg.QualifiedName = "syllable",
        tone_tier: str | tg.QualifiedName = "tone",
        *,
        namespace: str | None = None,
    ) -> str:
        """Render one word's ordered syllables using one qualified profile.

        A local syllable name must identify exactly one tier. Its namespace
        binds spelling/value attributes, tone tier and association relations;
        ``namespace`` or a qualified tier name disambiguates a combined graph.
        """

        candidates = [
            tier
            for tier in graph.tiers
            if (
                tier.declaration.name == syllable_tier
                if isinstance(syllable_tier, tg.QualifiedName)
                else tier.declaration.name.local_name == syllable_tier
            )
            and (namespace is None or tier.declaration.name.namespace == namespace)
        ]
        if len(candidates) != 1:
            raise ValueError("Pinyin rendering requires one unambiguous syllable tier")
        syllables = candidates[0]
        namespace = syllables.declaration.name.namespace

        def qname(name: str) -> tg.QualifiedName:
            return tg.QualifiedName(namespace, name)

        selected_tone = (
            tone_tier if isinstance(tone_tier, tg.QualifiedName) else qname(tone_tier)
        )
        if selected_tone.namespace != namespace:
            raise ValueError("Pinyin tone and syllable tiers must share a namespace")
        tiers = {tier.declaration.name: tier for tier in graph.tiers}

        tones: dict[tg.ItemRef, int] = {}
        for relation in graph.polyadic_relations:
            if relation.declaration != qname("associates-with"):
                continue
            if len(relation.sources) != 1 or len(relation.targets) != 1:
                raise ValueError(
                    "Pinyin tone association requires one source and target"
                )
            source = relation.sources[0]
            target = relation.targets[0]
            if (
                not isinstance(source, tg.ItemRef)
                or source.tier != selected_tone
                or not isinstance(target, tg.ItemRef)
                or target.tier != syllables.declaration.name
            ):
                raise ValueError("Pinyin tone association has incompatible endpoints")
            item = tiers[source.tier].items[source.index]
            value = next(
                (value for value in item.attributes if value.name == qname("value")),
                None,
            )
            if value is None or value.value_type != tg.XsdType.INTEGER:
                raise ValueError("Pinyin tone requires a qualified integer value")
            level = int(value.lexical)
            if level not in range(1, 6):
                raise ValueError("Pinyin tone must be an integer from 1 through 5")
            if target in tones:
                raise ValueError("Pinyin syllable has multiple tone associations")
            tones[target] = level

        rendered = []
        for index, item in enumerate(syllables.items):
            attributes = {value.name: value for value in item.attributes}
            spelling_value = attributes.get(qname("spelling"))
            if spelling_value is None or spelling_value.value_type != tg.XsdType.STRING:
                raise ValueError(
                    "Pinyin syllable requires a qualified string spelling attribute"
                )
            spelling = self.decode_input(spelling_value.lexical)
            if not spelling:
                raise ValueError("Pinyin syllable spelling must be nonempty")
            if any(char.lower() in "".join(self.tones.values()) for char in spelling):
                raise ValueError(
                    "Pinyin spelling must be unmarked; supply tone separately"
                )
            if index and spelling[0].lower() in "aeo":
                rendered.append("'")
            selected_level = tones.get(tg.ItemRef(syllables.declaration.name, index))
            if selected_level is not None and selected_level != 5:
                position = self.tone_index(spelling)
                if position < 0:
                    raise ValueError(
                        f"tone {selected_level!r} cannot be placed on {spelling!r}"
                    )
                vowel = spelling[position]
                marked = self.tones[vowel.lower()][selected_level - 1]
                if vowel.isupper():
                    marked = marked.upper()
                spelling = spelling[:position] + marked + spelling[position + 1 :]
            rendered.append(spelling)
        return "".join(rendered)


PINYIN = PinyinBridge()
