"""Generate and check representative serialization bytes for consolidation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import tiergraph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ipakit import FormBuilder, IPAFeatures  # noqa: E402
from ipakit._cmu_graph import read as read_cmu  # noqa: E402
from ipakit._mora_graph import build as build_mora  # noqa: E402
from ipakit._pinyin_graph import build as build_pinyin  # noqa: E402

DIGEST = ROOT / "scripts" / "consolidation_parity.sha256"


def _wire(graph: tiergraph.Graph) -> str:
    wire = tiergraph.wire.dumps(graph)
    assert tiergraph.wire.loads(wire) == graph
    assert tiergraph.wire.dumps(tiergraph.wire.loads(wire)) == wire
    return wire


def corpus_bytes() -> bytes:
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

    escaped_tier = "custom~/tier"
    escaped_feature = "feature~/key"
    escaped_builder = tiergraph.build.document(
        "urn:ipakit:escaped-pointer", prefix="escaped"
    )
    escaped_builder.attribute(escaped_feature, tiergraph.XsdType.STRING)
    escaped_builder.tier(
        escaped_tier,
        (tiergraph.build.item(**{escaped_feature: "pointer oracle"}),),
        item_type="escaped-item",
        membership="escaped-members",
    )
    escaped_wire = _wire(escaped_builder.build())

    payload = {
        "build": built_wire,
        "cmu": _wire(cmu),
        "escaped": escaped_wire,
        "mora": _wire(mora),
        "parse": parsed_wire,
        "pinyin": _wire(pinyin),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def digest() -> str:
    return hashlib.sha256(corpus_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("emit", "generate", "check"), nargs="?", default="emit"
    )
    command = parser.parse_args().command
    if command == "emit":
        print(corpus_bytes().decode())
    elif command == "generate":
        DIGEST.write_text(f"{digest()}\n", encoding="ascii")
        print(DIGEST.relative_to(ROOT))
    else:
        expected = DIGEST.read_text(encoding="ascii")
        actual = f"{digest()}\n"
        if actual != expected:
            raise SystemExit(
                f"DRIFT: {DIGEST.relative_to(ROOT)}; run "
                "python scripts/consolidation_parity.py generate"
            )
        print(f"OK: {DIGEST.relative_to(ROOT)} matches derived corpus")


if __name__ == "__main__":
    main()
