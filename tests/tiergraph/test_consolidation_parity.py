from __future__ import annotations

import ipakit._tiergraph as tiergraph
import ipakit._tiergraph_builder as tiergraph_builder
from scripts.consolidation_parity import corpus_bytes


def test_parity_corpus_detects_broken_pointer_escaping(monkeypatch) -> None:
    canonical = corpus_bytes()
    monkeypatch.setattr(tiergraph, "_escape", lambda value: value)
    monkeypatch.setattr(tiergraph_builder, "_escape", lambda value: value)
    assert corpus_bytes() != canonical
