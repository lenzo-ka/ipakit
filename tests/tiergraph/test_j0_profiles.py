"""Pressure-test non-IPA declarations against the generic tier graph."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ipakit import IPAFeatures
from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder

ROOT = Path(__file__).parents[2]
CMU_MAP = ROOT / "ipakit" / "data" / "phonemaps" / "cmu.xml"


def _stress_values() -> dict[str, str]:
    """Read the digit-to-value vocabulary the IPA profile also derives."""
    inventory = IPAFeatures()
    marked = {
        str(level): inventory.diacritics[symbol].features["stress"]
        for symbol, level in inventory.stress_markers.items()
    }
    unmarked = set(inventory.features["stress"].values) - set(marked.values())
    assert len(unmarked) == 1
    return {"0": unmarked.pop(), **marked}


def _base_cmu_vocabulary() -> dict[str, frozenset[str]]:
    """Read base (non-``extras``) symbols and stress policies from cmu.xml."""
    root = ET.parse(CMU_MAP).getroot()
    return {
        symbol: frozenset(element.get("stress", "").split())
        for element in root.findall("map")
        if (symbol := element.get("cmu")) is not None
    }


def _cmu_declarations() -> Declarations:
    features = (FeatureDeclaration("phone"), FeatureDeclaration("stress"))
    return Declarations(
        (TierDeclaration("phone", frozenset(item.name for item in features)),),
        features,
        (),
    )


def _build_cmu(tokens: tuple[str, ...]) -> Graph:
    vocabulary = _base_cmu_vocabulary()
    stress_values = _stress_values()
    builder = GraphBuilder(_cmu_declarations())
    for token in tokens:
        phone, digit = token[:-1], token[-1]
        if phone not in vocabulary or digit not in vocabulary[phone]:
            raise ValueError(f"undeclared base-CMUdict phone: {token}")
        builder.append_input_atom(
            "phone", {"phone": phone, "stress": stress_values[digit]}
        )
    return builder.build()


def _pinyin_declarations() -> Declarations:
    return Declarations(
        (
            TierDeclaration("syllable", frozenset({"spelling"})),
            TierDeclaration("tone", frozenset({"value"})),
        ),
        (FeatureDeclaration("spelling"), FeatureDeclaration("value")),
        (
            RelationDeclaration(
                "associates-with",
                source_tiers=frozenset({"tone"}),
                target_tiers=frozenset({"syllable"}),
            ),
        ),
    )


_TONE_MARKS = {
    "a": "āáǎà",
    "e": "ēéěè",
    "i": "īíǐì",
    "o": "ōóǒò",
    "u": "ūúǔù",
    "ü": "ǖǘǚǜ",
}


def _render_pinyin(graph: Graph) -> str:
    """Render syllable tone using Pinyin placement, not graph attachment."""
    syllable = graph.resolve("/clock/0/syllable/0").event
    tone = graph.resolve("/clock/0/tone/0").event
    assert syllable is not None and tone is not None
    spelling = str(syllable.features["spelling"])
    level = int(tone.features["value"])
    lowered = spelling.lower()
    if "a" in lowered or "e" in lowered:
        index = min(
            position for vowel in "ae" if (position := lowered.find(vowel)) >= 0
        )
    elif "ou" in lowered:
        index = lowered.index("o")
    else:
        index = max(lowered.rfind(vowel) for vowel in _TONE_MARKS)
    vowel = lowered[index]
    return spelling[:index] + _TONE_MARKS[vowel][level - 1] + spelling[index + 1 :]


def test_base_cmudict_stress_values_survive_generic_round_trip() -> None:
    graph = _build_cmu(("IY0", "IY1", "IY2"))

    restored = Graph.from_data(
        graph.declarations, json.loads(json.dumps(graph.to_data()))
    )
    events = tuple(
        restored.resolve(f"/clock/{tick}/phone/0").event for tick in range(3)
    )
    assert all(event is not None for event in events)
    assert tuple(event.features["phone"] for event in events if event) == (
        "IY",
        "IY",
        "IY",
    )
    assert tuple(event.features["stress"] for event in events if event) == (
        "none",
        "primary",
        "secondary",
    )
    assert restored == graph


def test_pinyin_tone_attachment_differs_from_codec_placement() -> None:
    builder = GraphBuilder(_pinyin_declarations())
    syllable = builder.append_input_atom("syllable", {"spelling": "shui"})
    tone = builder.add_event("tone", 0, {"value": 3}, duration=0)
    builder.relate((tone,), "associates-with", (syllable,))
    graph = builder.build()

    restored = Graph.from_data(
        graph.declarations, json.loads(json.dumps(graph.to_data()))
    )
    assert restored == graph
    assert restored.relations[0].sources == ("/clock/0/tone/0",)
    assert restored.relations[0].targets == ("/clock/0/syllable/0",)
    assert _render_pinyin(restored) == "shuǐ"
    assert restored.resolve("/clock/0/syllable/0").event.structural_duration == 1


def test_generic_modules_contain_no_j0_profile_vocabulary() -> None:
    sources = "\n".join(
        (ROOT / "ipakit" / name).read_text()
        for name in ("_tiergraph.py", "_tiergraph_builder.py")
    ).lower()
    forbidden = ("cmudict", "arpabet", "pinyin", "tone mark", "tone-mark")
    assert not any(word in sources for word in forbidden)
