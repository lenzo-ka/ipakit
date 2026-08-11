"""Attested-only kana vocabulary bridge."""

from __future__ import annotations

from pathlib import Path

from .._codecs import RenderLane, RenderProfile, render_graph
from .._tiergraph import Event, Graph
from .vocabulary import VocabularyBridge

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "kana" / "kana.xml"


class KanaBridge(VocabularyBridge):
    """Katakana rendering of attested gairaigo adaptations on the mora tier.

    This codec describes forms Japanese licenses; it is not an accent simulator.
    """

    def __init__(self) -> None:
        super().__init__(_PATH)

    def render(self, graph: Graph) -> str:
        outputs = {atom.spelling: atom.output for atom in self.atoms}

        def glyph(event: Event) -> str:
            kind = event.features.get("mora-kind", "ordinary")
            if kind == "geminate-half":
                return "ッ"
            if kind == "nasal":
                return "ン"
            if kind == "long-vowel-second":
                return "ー"
            spelling = str(event.features["value"])
            try:
                return outputs[spelling]
            except KeyError as error:
                raise ValueError(
                    f"no attested gairaigo mora spelling: {spelling!r}"
                ) from error

        return render_graph(graph, RenderProfile((RenderLane("mora", "value", glyph),)))


KANA = KanaBridge()
