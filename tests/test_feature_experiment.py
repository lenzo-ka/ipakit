"""Literal experiment contracts through the public library and real script."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from ipakit import load_ipa_features
from ipakit.bridges.costmodel import (
    CostPolicy,
    pack_from_declaration,
    pack_from_ternary_declaration,
)
from ipakit.feature_experiment import compare_declaration_encodings
from ipakit.feature_transform import BinaryEncoding
from ipakit.finite_declaration import read_ternary_declaration
from ipakit.finite_model import FeatureSchema, FiniteModel

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "tests/panphon/panphon.xml"


@pytest.fixture(scope="module")
def declaration():
    return read_ternary_declaration(SOURCE)


def experiment(declaration, corpus, **kwargs):
    return compare_declaration_encodings(
        load_ipa_features(),
        declaration,
        corpus,
        encodings=(BinaryEncoding.TWO_PREDICATE, BinaryEncoding.POSITIVE_ONLY),
        binary_gap=kwargs.pop("binary_gap", 1.0),
        policies=(CostPolicy(),),
        **kwargs,
    )


def test_literal_vectors_and_report_gaps(declaration):
    assert declaration.model.read("p").values == (
        -1,
        -1,
        1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        1,
        -1,
        0,
        1,
        -1,
        -1,
        -1,
        -1,
        -1,
        0,
        -1,
        0,
        0,
    )
    assert declaration.model.read("a").values == (
        1,
        1,
        -1,
        1,
        -1,
        -1,
        -1,
        -1,
        1,
        -1,
        -1,
        0,
        -1,
        0,
        -1,
        -1,
        1,
        1,
        -1,
        -1,
        1,
        -1,
        0,
        0,
    )
    report = experiment(
        declaration, [["p"], ["b"], ["a"], [], ["UNKNOWN"]], all_pairs=True
    )
    arms = report["experiment"]["arms"]
    assert len(report["rows"]) == 60 and report["ordered_pairs_per_pack"] == 20
    assert sum(row["status"] == "refused" for row in report["rows"]) == 24
    gaps = [
        row["edit_cost"]
        for row in report["rows"]
        if row["source_index"] == 2 and row["target_index"] == 3
    ]
    assert gaps == [44 / 48, 1.0, 1.0]
    assert [arm.get("bit_count") for arm in arms] == [None, 48, 24]
    assert arms[1]["loss"]["domain_injective"] is True
    assert arms[2]["loss"]["observed_collision_groups"] == 214
    assert report["experiment"]["declaration"]["weights_applied"] is False
    assert len(report["experiment"]["declaration"]["declared_weights"]) == 22


def test_foreign_only_never_uses_house_or_retokenizes(declaration, monkeypatch):

    ipa = load_ipa_features()

    def refuse(*args, **kwargs):
        raise AssertionError("house semantics or tokenization used")

    monkeypatch.setattr(ipa, "read", refuse)
    monkeypatch.setattr(ipa, "segment_distance", refuse)
    # The engine consumes explicit Segmentation; callbacks remain model-owned.
    import ipakit.feature_experiment as module

    original = module.pack_from_ternary_declaration
    monkeypatch.setattr(
        module,
        "pack_from_ternary_declaration",
        lambda *a, **k: replace(original(*a, **k), tokenize=refuse),
    )
    original_binary = module.binary_pack
    monkeypatch.setattr(
        module,
        "binary_pack",
        lambda *a, **k: replace(original_binary(*a, **k), tokenize=refuse),
    )
    engine = module.compare_token_corpus
    calls = []

    def once(*args, **kwargs):
        calls.append(1)
        return engine(*args, **kwargs)

    monkeypatch.setattr(module, "compare_token_corpus", once)
    report = compare_declaration_encodings(
        ipa,
        declaration,
        [["UNKNOWN"], ["UNKNOWN"], []],
        encodings=(BinaryEncoding.TWO_PREDICATE,),
        binary_gap=1,
        policies=(CostPolicy(),),
    )
    assert len(report["rows"]) == 4
    assert all(row["status"] == "refused" for row in report["rows"])
    assert all(row["pack"] != "ipakit/house" for row in report["rows"])
    assert calls == [1]


def test_zero_negative_loss_aliases_and_identity_separation(declaration):
    model = FiniteModel(
        declaration.model.name,
        FeatureSchema({"f": (-1, 0, 1)}),
        {"NEG": (-1,), "ZERO": (0,), "ALIAS": (0,), "POS": (1,)},
        declaration.model.source,
    )
    custom = replace(declaration, model=model, weights=(), weight_names=())
    first = experiment(custom, [["NEG"], ["ZERO"]])
    second = experiment(custom, [["NEG"], ["ZERO"]], binary_gap=2)
    assert [row["edit_cost"] for row in first["rows"]] == [0.5, 0.5, 0]
    a, b = first["experiment"], second["experiment"]
    assert a["declaration"] == b["declaration"]
    assert a["arms"][1]["target_model"] == b["arms"][1]["target_model"]
    assert a["arms"][1]["identity"] != b["arms"][1]["identity"]
    assert a["arms"][2]["loss"]["observed_collision_groups"] == 1
    changed = replace(
        custom,
        model=FiniteModel(
            model.name, model.schema, {**model.rows, "EXTRA": (1,)}, model.source
        ),
    )
    third = experiment(changed, [["NEG"], ["ZERO"]])["experiment"]
    assert a["declaration"]["model"] != third["declaration"]["model"]
    assert a["arms"][1]["operation"] != third["arms"][1]["operation"]


@pytest.mark.parametrize("domain", [(False, 0, 1), ("-", "0", "+"), (-1, 0, 2)])
def test_object_factory_refuses_wrong_typed_domains(declaration, domain):
    model = FiniteModel(
        declaration.model.name,
        FeatureSchema({"f": domain}),
        {"X": (domain[0],)},
        declaration.model.source,
    )
    with pytest.raises(ValueError, match="ternary domains"):
        pack_from_ternary_declaration(replace(declaration, model=model))


@pytest.mark.parametrize("weight", [True, -1, float("nan"), float("inf")])
def test_object_factory_refuses_invalid_weights(declaration, weight):
    with pytest.raises(ValueError, match="weights"):
        pack_from_ternary_declaration(
            replace(declaration, weights=(weight,), weight_names=("f",))
        )


def test_object_factory_receipts_and_existing_path_parity(declaration):
    for changed in (
        replace(declaration, bridge=replace(declaration.bridge, source=None)),
        replace(declaration, bridge=replace(declaration.bridge, version="wrong")),
        replace(declaration, model=replace(declaration.model, source=None)),
    ):
        with pytest.raises(ValueError):
            pack_from_ternary_declaration(changed)
    original, shared = pack_from_declaration(SOURCE), pack_from_ternary_declaration(
        declaration
    )
    assert original.sub_cost("p", "b") == shared.sub_cost("p", "b")
    assert original.insert_cost("a") == shared.insert_cost("a")


def test_object_factory_refuses_complete_but_blank_source_and_mutable_notes(
    declaration,
):
    source = replace(declaration.model.source, license="")
    invalid = replace(
        declaration,
        model=replace(declaration.model, source=source),
        bridge=replace(declaration.bridge, source=source, provenance=source.provenance),
    )
    with pytest.raises(ValueError, match="complete source"):
        pack_from_ternary_declaration(invalid)
    leg = replace(declaration.bridge.round_trip.external_to_house, drops=["mutable"])
    invalid = replace(
        declaration,
        bridge=replace(
            declaration.bridge,
            round_trip=replace(declaration.bridge.round_trip, external_to_house=leg),
        ),
    )
    with pytest.raises(ValueError, match="immutable"):
        pack_from_ternary_declaration(invalid)


def test_duplicate_selections_refuse(declaration):
    with pytest.raises(ValueError, match="duplicate encoding"):
        compare_declaration_encodings(
            load_ipa_features(),
            declaration,
            [[], []],
            encodings=(BinaryEncoding.TWO_PREDICATE,) * 2,
            binary_gap=1,
            policies=(CostPolicy(),),
        )
    with pytest.raises(ValueError, match="duplicate policy"):
        compare_declaration_encodings(
            load_ipa_features(),
            declaration,
            [[], []],
            encodings=(BinaryEncoding.TWO_PREDICATE,),
            binary_gap=1,
            policies=(CostPolicy(),) * 2,
        )


def test_actual_script_binary_and_legacy_modes(tmp_path):
    corpus = tmp_path / "tokens.json"
    corpus.write_text('[["a"],[]]')
    command = [
        sys.executable,
        str(ROOT / "scripts/costmodel_compare.py"),
        "--tokens-json",
        str(corpus),
        "--format",
        "json",
        "--policy",
        "faithful",
    ]
    binary = [
        "--binary-encoding",
        "two-predicate",
        "--binary-gap",
        "1",
        "--foreign-only",
    ]
    result = subprocess.run(command + binary, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert [row["edit_cost"] for row in report["rows"]] == [44 / 48, 1]
    for suffix, count in (([], 2), (["--clts-snapshot"], 3)):
        result = subprocess.run(command + suffix, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert len(json.loads(result.stdout)["rows"]) == count
    result = subprocess.run(
        command + binary + ["--clts-snapshot"], text=True, capture_output=True
    )
    assert result.returncode != 0 and "combined binary and CLTS" in result.stderr
    for suffix in (
        ["--binary-encoding", "two-predicate"],
        ["--binary-gap", "1"],
        binary + ["--binary-encoding", "two-predicate"],
    ):
        assert subprocess.run(command + suffix, capture_output=True).returncode != 0
    text = tmp_path / "corpus.txt"
    text.write_text("p\nb\n")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/costmodel_compare.py"),
            "--corpus",
            str(text),
            "--format",
            "tsv",
            "--policy",
            "faithful",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 3
