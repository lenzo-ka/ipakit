"""Emit representative serialization bytes for the consolidation DRY pass."""

from __future__ import annotations

import json

from ipakit import FormBuilder, IPAFeatures
from ipakit._cmu_graph import declarations as cmu_declarations
from ipakit._cmu_graph import read as read_cmu
from ipakit._mora_graph import build as build_mora
from ipakit._mora_graph import declarations as mora_declarations
from ipakit._panphon_graph import declaration as panphon_declaration
from ipakit._panphon_graph import fingerprint as panphon_fingerprint
from ipakit._pinyin_graph import build as build_pinyin
from ipakit._tiergraph import Graph
from ipakit._tiergraph_builder import GraphBuilder
from ipakit._tiergraph_json import Model, dumps, loads


def _wire(graph: Graph, model: Model) -> str:
    wire = dumps(graph, model)
    assert dumps(loads(wire, model), model) == wire
    return wire


def main() -> None:
    inventory = IPAFeatures()
    parsed = inventory.read("k\u00e6t..\u02c8d\u0252\u0261")
    parsed_wire = parsed.to_json(self_contained=True)
    assert type(parsed).from_json(parsed_wire, inventory).to_json(True) == parsed_wire

    builder = FormBuilder(inventory)
    utterance = builder.begin("utterance")
    segments = builder.append_ipa("t\u0361sa\u026a")
    builder.end(utterance)
    builder.contain(utterance, segments)
    builder.add_root(utterance)
    built = builder.build()
    built_wire = built.to_json(self_contained=True)
    assert type(built).from_json(built_wire, inventory).to_json(True) == built_wire

    cmu = read_cmu(("K", "AE1", "T"))
    pinyin = build_pinyin(
        "shui",
        "sh",
        "ui",
        3,
        ipa={"segments": ["\u0282", "w", "e\u026a"]},
        referenced=True,
    )
    mora = build_mora(("to", "o"), "high")
    panphon_names = ("syl", "son", "cons")
    panphon_declarations = panphon_declaration(panphon_names)
    panphon_builder = GraphBuilder(panphon_declarations)
    panphon_builder.append_input_atom(
        "segment", {"spelling": "p", "syl": -1, "son": -1, "cons": 1}
    )
    panphon = panphon_builder.build()

    payload = {
        "build": built_wire,
        "cmu": _wire(cmu, Model("cmudict", "base-1", cmu_declarations())),
        "mora": _wire(mora, Model("moraic-gairaigo", "1", mora_declarations())),
        "panphon": _wire(
            panphon,
            Model("panphon", panphon_fingerprint(panphon_names), panphon_declarations),
        ),
        "parse": parsed_wire,
        "pinyin": json.dumps(
            pinyin.to_data(), ensure_ascii=False, separators=(",", ":")
        ),
    }
    restored_pinyin = Graph.from_data(
        pinyin.declarations, json.loads(payload["pinyin"])
    )
    assert restored_pinyin == pinyin
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
