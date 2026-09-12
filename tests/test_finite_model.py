"""Finite model operations do not require house phonetic spellings or domains."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from ipakit.bridges.costmodel import pack_from_declaration
from ipakit.feature_models import resource_path
from ipakit.finite_declaration import read_ternary_declaration
from ipakit.finite_model import (
    FeatureBundle,
    FeatureSchema,
    FiniteModel,
    InvalidFeature,
    MissingToken,
    ModelMismatch,
)

DECLARATION = resource_path("panphon")


def fixture_model() -> FiniteModel:
    return FiniteModel(
        "opaque",
        FeatureSchema({"register": ("low", "high"), "beat": (0, 1)}),
        {
            "TOKEN-1": ("low", 0),
            "TOKEN-2": ("high", 0),
            "ALIAS": ("high", 0),
            "MISSING": ("low", None),
        },
    )


def test_opaque_read_query_edit_and_relation() -> None:
    model = fixture_model()
    assert model.schema.features == ("register", "beat")
    assert model.read("TOKEN-1").values == ("low", 0)
    assert model.query({"beat": 0}) == ("TOKEN-1", "TOKEN-2", "ALIAS")
    assert model.query({"beat": None}) == ("MISSING",)
    assert model.query({}) == tuple(model.rows)
    edited = model.respell("TOKEN-1", {"register": "high"})
    assert edited.candidates == ("TOKEN-2", "ALIAS")
    assert edited.status == "ambiguous"
    assert model.respell("TOKEN-1", {}).status == "unique"
    assert model.respell("TOKEN-1", {"beat": 1}).status == "none"
    assert model.read("TOKEN-1").values == ("low", 0)


@pytest.mark.parametrize("changes", [{"unknown": 0}, {"beat": 2}, {"beat": False}])
def test_invalid_queries_and_edits_are_not_empty_relations(changes: dict) -> None:
    model = fixture_model()
    with pytest.raises(InvalidFeature):
        model.query(changes)
    with pytest.raises(InvalidFeature):
        model.respell("TOKEN-1", changes)


def test_missing_input_and_cross_model_bundles_are_distinct() -> None:
    model = fixture_model()
    with pytest.raises(MissingToken):
        model.read("p")
    other = FiniteModel("other", model.schema, model.rows)
    with pytest.raises(ModelMismatch):
        model.realize(other.read("TOKEN-1"))
    with pytest.raises(InvalidFeature, match="width"):
        model.realize(FeatureBundle(model.identity, ()))
    with pytest.raises(InvalidFeature, match="invalid value"):
        model.realize(FeatureBundle(model.identity, ("invalid", 0)))


def test_input_mutation_cannot_change_model_or_identity() -> None:
    domains = {"f": (0, 1)}
    rows = {"A": (0,)}
    schema = FeatureSchema(domains)
    model = FiniteModel("fixture", schema, rows)
    identity = model.identity
    rows["A"] = (1,)
    domains["f"] = (2,)
    assert model.read("A").values == (0,)
    assert model.identity == identity
    assert schema.domains["f"] == (0, 1)
    with pytest.raises(TypeError):
        model.rows["A"] = (1,)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        model.name = "changed"  # type: ignore[misc]
    assert FiniteModel("fixture", schema, {"A": (1,)}).identity != identity
    assert (
        FiniteModel("fixture", FeatureSchema({"f": (0, 1, 2)}), {"A": (0,)}).identity
        != identity
    )


@pytest.mark.parametrize(
    "domains", [{}, {"": (0,)}, {"f": ()}, {"f": (0, 0)}, {"f": (None,)}]
)
def test_invalid_schema(domains: dict) -> None:
    with pytest.raises(InvalidFeature):
        FeatureSchema(domains)


def test_boolean_domain_is_distinct_from_integer_domain() -> None:
    model = FiniteModel(
        "typed", FeatureSchema({"f": (False, 0)}), {"BOOL": (False,), "INT": (0,)}
    )
    assert model.query({"f": False}) == ("BOOL",)
    assert model.query({"f": 0}) == ("INT",)


def test_typed_bundles_remain_distinct_dictionary_and_set_keys() -> None:
    model = FiniteModel(
        "typed",
        FeatureSchema({"f": (False, 0)}),
        {"BOOL": (False,), "INT": (0,)},
    )
    boolean, integer = model.read("BOOL"), model.read("INT")
    assert boolean != integer
    assert len({boolean, integer}) == 2
    lookup = {boolean: "BOOL", integer: "INT"}
    assert lookup[boolean] == "BOOL"
    assert lookup[integer] == "INT"
    assert model.read("BOOL") == boolean
    assert hash(model.read("BOOL")) == hash(boolean)


def test_schema_equality_hashing_preserve_types_and_order() -> None:
    boolean = FeatureSchema({"f": (False,)})
    integer = FeatureSchema({"f": (0,)})
    assert boolean != integer
    assert len({boolean, integer}) == 2
    assert {boolean: "BOOL", integer: "INT"}[boolean] == "BOOL"
    assert FeatureSchema({"f": (False,)}) == boolean
    assert hash(FeatureSchema({"f": (False,)})) == hash(boolean)
    assert FeatureSchema({"a": (0,), "b": (0,)}) != FeatureSchema(
        {"b": (0,), "a": (0,)}
    )
    assert FeatureSchema({"f": (0, 1)}) != FeatureSchema({"f": (1, 0)})


def test_related_value_objects_are_hashable_and_preserve_model_order() -> None:
    first = fixture_model()
    same = fixture_model()
    reversed_rows = FiniteModel(
        first.name, first.schema, dict(reversed(tuple(first.rows.items())))
    )
    assert first == same
    assert first != reversed_rows
    assert len({first, same, reversed_rows}) == 2
    one, two = first.respell("TOKEN-1", {}), same.respell("TOKEN-1", {})
    assert one == two
    assert hash(one) == hash(two)
    declaration = read_ternary_declaration(DECLARATION)
    duplicate = read_ternary_declaration(DECLARATION)
    assert declaration == duplicate
    assert hash(declaration) == hash(duplicate)


def test_row_and_domain_sequences_are_defensively_copied() -> None:
    domain = [0, 1]
    row = [0]
    schema = FeatureSchema({"f": domain})  # type: ignore[dict-item]
    model = FiniteModel("copied", schema, {"TOKEN": row})  # type: ignore[dict-item]
    identity = model.identity
    domain.append(2)
    row[0] = 1
    assert model.schema.domains["f"] == (0, 1)
    assert model.read("TOKEN").values == (0,)
    assert model.identity == identity


def test_codec_normalizes_input_but_direct_model_does_not(tmp_path: Path) -> None:
    root = ET.parse(DECLARATION).getroot()
    segments = root.find("segments")
    assert segments is not None
    segments.clear()
    ET.SubElement(segments, "segment", {"name": "e\u0301"})
    ET.SubElement(segments, "segment", {"name": "e"})
    path = tmp_path / "normalization.xml"
    ET.ElementTree(root).write(path)
    declaration = read_ternary_declaration(path)
    assert declaration.tokenize("é?") == (("e\u0301",), ("?",))
    assert pack_from_declaration(path).tokenize("é?").tokens == ("e\u0301",)
    with pytest.raises(MissingToken):
        declaration.model.read("é")
    direct = FiniteModel("exact", FeatureSchema({"f": (0,)}), {"é": (0,)})
    assert direct.read("é").values == (0,)
    segments[0].set("name", "é")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="not NFD"):
        read_ternary_declaration(path)


def test_frozen_declaration_parity_and_ambiguous_realization() -> None:
    declaration = read_ternary_declaration(DECLARATION)
    model = declaration.model
    root = ET.parse(DECLARATION).getroot()
    segments = root.find("segments")
    assert segments is not None
    assert len(model.rows) == 6367
    assert len(model.schema.features) == 24
    assert len(declaration.weights) == 22
    values = {"-": -1, "0": 0, "+": 1}
    for row in segments:
        assert model.read(row.attrib["name"]).values == tuple(
            values[row.attrib[feature]] if feature in row.attrib else None
            for feature in model.schema.features
        )
    edited = model.respell("p", {"voi": 1})
    assert edited.candidates == ("b", "b̟", "b̠")
    assert edited.source == model.source == declaration.bridge.source
    assert edited.bundle.model_id == model.identity
    assert declaration.tokenize("p?") == (("p",), ("?",))
    assert pack_from_declaration(DECLARATION).bridge == declaration.bridge


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("duplicate", "duplicate feature"),
        ("empty", "requires a name"),
        ("undeclared", "undeclared row features"),
    ],
)
def test_malformed_declarations_refused_by_both_consumers(
    tmp_path: Path, mutation: str, match: str
) -> None:
    root = ET.parse(DECLARATION).getroot()
    features, segments = root.find("features"), root.find("segments")
    assert features is not None and segments is not None
    if mutation == "duplicate":
        features.append(ET.Element("feature", {"name": features[0].attrib["name"]}))
    elif mutation == "empty":
        segments[0].set("name", "")
    else:
        segments[0].set("not-declared", "-")
    path = tmp_path / "bad.xml"
    ET.ElementTree(root).write(path)
    for consumer in (read_ternary_declaration, pack_from_declaration):
        with pytest.raises(ValueError, match=match):
            consumer(path)
