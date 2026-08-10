"""Katakana rendering of attested gairaigo adaptations on the mora tier.

This codec describes forms Japanese licenses; it is not an accent simulator.
"""

from __future__ import annotations

from ._tiergraph import Graph


def render(graph: Graph) -> str:
    ordinary = {
        "pe": "ペ",
        "ho": "ホ",
        "to": "ト",
        "be": "ベ",
        "do": "ド",
        "t͡ɕi": "チ",
        "zu": "ズ",
        "bi": "ビ",
        "ɾu": "ル",
        "su": "ス",
        "ɾa": "ラ",
        "ɾi": "リ",
        "i": "イ",
        "ku": "ク",
        "ɾo": "ロ",
        "ma": "マ",
    }
    glyphs = []
    for node in graph.clock:
        for group in node.groups:
            if group.tier != "mora":
                continue
            for event in group.events:
                kind = event.features.get("mora-kind", "ordinary")
                spelling = str(event.features["value"])
                if kind == "geminate-half":
                    glyphs.append("ッ")
                elif kind == "nasal":
                    glyphs.append("ン")
                elif kind == "long-vowel-second":
                    glyphs.append("ー")
                else:
                    try:
                        glyphs.append(ordinary[spelling])
                    except KeyError as error:
                        raise ValueError(
                            f"no attested gairaigo mora spelling: {spelling!r}"
                        ) from error
    return "".join(glyphs)
