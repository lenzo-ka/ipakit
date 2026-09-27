"""Public Form restoration refuses source-only declared-value tiers."""

from __future__ import annotations

import json
from pathlib import Path

import ipakit
import pytest
from ipakit import Form, FormProjectionError, IPAFeatures
from ipakit._clts_profile import SourceProfileSpec, construct, declarations
from ipakit._fact_builder import FactBuilder
from ipakit._graph_facts import (
    Declarations,
    FeatureDeclaration,
    TierDeclaration,
)
from ipakit._provenance import SourceMetadata

import tiergraph as tg

ROOT = Path(__file__).resolve().parents[1]


def _spec() -> SourceProfileSpec:
    return SourceProfileSpec(
        SourceMetadata("fixture", "urn:fixture", "synthetic", "1", "fixture", "test"),
        "fixture-provider",
        "fixture-manifest",
        ("tone", "consonant"),
        (),
    )


def _source_only_json(raw: str) -> str:
    builder = FactBuilder(declarations(_spec()))
    builder.append_input_atom(
        "source-token",
        {
            "raw": raw,
            "resolution": {
                "provider": "fixture-provider",
                "status": "unknown-sound",
            },
        },
    )
    return Form._from_projection_input(builder.build_input()).to_json()


PUBLIC_FORM_READERS = (
    pytest.param(lambda document: Form.from_json(document), id="Form.from_json"),
    pytest.param(
        lambda document: Form.from_dict(json.loads(document)), id="Form.from_dict"
    ),
    pytest.param(
        lambda document: IPAFeatures().read_json(document), id="IPAFeatures.read_json"
    ),
    pytest.param(lambda document: ipakit.read_json(document), id="ipakit.read_json"),
)


@pytest.mark.parametrize("reader", PUBLIC_FORM_READERS)
@pytest.mark.parametrize("raw", ["?", "!"])
def test_public_form_readers_refuse_source_only_declared_values(reader, raw) -> None:
    with pytest.raises(
        FormProjectionError,
        match=r"declared-value codec tier has no house unit: 'source-token'",
    ):
        reader(_source_only_json(raw))


def test_clts_profile_graph_is_still_not_a_form_document() -> None:
    record = {
        "provider": "fixture-provider",
        "status": "unknown-sound",
        "sounds": [],
    }
    graph = construct(["?"], [record], _spec())
    with pytest.raises(ValueError, match="Form profile"):
        Form.from_json(tg.dumps(graph))


def test_declared_value_on_a_tier_with_a_house_unit_still_restores() -> None:
    declared = Declarations(
        (TierDeclaration("token", frozenset({"unit", "unit-index", "input", "fact"})),),
        (
            FeatureDeclaration("unit"),
            FeatureDeclaration("unit-index"),
            FeatureDeclaration("input"),
            FeatureDeclaration("fact", ("urn:test:reader", "fact")),
        ),
        (),
    )
    builder = FactBuilder(declared)
    builder.append_input_atom(
        "token",
        {
            "unit": ipakit.read("a").units[0],
            "unit-index": 0,
            "input": True,
            "fact": {"source": "retained"},
        },
    )
    document = Form._from_projection_input(builder.build_input()).to_json()

    restored = ipakit.read_json(document)

    assert restored.to_ipa() == "a"
    assert restored.at("/clock/0/token/0").features["fact"] == {"source": "retained"}


def test_repository_form_baselines_fixtures_and_goldens_read_unchanged() -> None:
    coordinates = ROOT / "tests/tiergraph/baselines/coordinates.json"
    captured = json.loads(coordinates.read_text(encoding="utf-8"))
    documents = [
        (f"coordinates.json::{row['id']}", row["json"]) for row in captured["forms"]
    ]
    hot = ROOT / "tests/tiergraph/fixtures/hot_bridge_projection.json"
    documents.append((hot.name, hot.read_text(encoding="utf-8")))

    assert [name for name, _ in documents] == [
        "coordinates.json::segments",
        "coordinates.json::boundaries",
        "coordinates.json::zeros",
        "coordinates.json::whitespace",
        "coordinates.json::a-dot-dot-b-mora",
        "coordinates.json::cross-tier-boundaries",
        "hot_bridge_projection.json",
    ]
    for name, document in documents:
        assert ipakit.read_json(document).to_dict() == json.loads(document), name
