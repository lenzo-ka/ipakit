"""Finite transform and comparison commands delegate to the public library."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from ipakit import cli, load_ipa_features
from ipakit.bridges.costmodel import FAITHFUL
from ipakit.feature_experiment import compare_declaration_encodings
from ipakit.feature_transform import BinaryEncoding, ternary_to_binary
from ipakit.finite_declaration import read_ternary_declaration


@pytest.fixture
def declaration(tmp_path: Path) -> Path:
    path = tmp_path / "complete.xml"
    path.write_text(
        '<model name="opaque" upstream="fixture" upstream-url="https://example.org" '
        'artifact="table" version="1" license="MIT" kind="features">'
        '<round-trip><external-to-house fidelity="lossy-with-report"/>'
        '<house-to-external fidelity="lossy-with-report"/></round-trip>'
        '<features><feature name="f"/><feature name="g"/></features><segments>'
        '<s name="NEG" f="-" g="0"/><s name="ZERO" f="0" g="0"/>'
        '<s name="POS" f="+" g="+"/><s name="ALIAS" f="+" g="+"/>'
        "</segments></model>",
        encoding="utf-8",
    )
    return path


def invoke(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["ipakit", "model", *args])
    return cli.main()


def test_transform_round_trips_against_library(monkeypatch, capsys, declaration):
    assert (
        invoke(
            monkeypatch,
            "transform",
            "--model-declaration",
            str(declaration),
            "--token",
            "ZERO",
            "--encoding",
            "positive-only",
            "-j",
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)

    model = read_ternary_declaration(declaration).model
    operation = ternary_to_binary(
        model, BinaryEncoding.POSITIVE_ONLY, missing="require-complete"
    )
    witness = operation.apply(model.read("ZERO"))
    preimage = operation.decode(witness.target)
    assert data["source"]["values"] == list(witness.source.values)
    assert data["target"]["values"] == list(witness.target.values)
    assert data["transform_id"] == operation.identity
    assert data["target_model_id"] == operation.target.identity
    assert data["preimage"]["count"] == preimage.count
    assert data["preimage"]["inventory_candidates"] == list(
        preimage.inventory_candidates
    )
    assert data["loss"]["domain_injective"] is operation.injective
    assert data["loss"]["observed_collision_groups"] == len(operation.collisions())


def test_compare_round_trips_against_library(
    monkeypatch, capsys, declaration, tmp_path
):
    corpus = [["NEG"], ["ZERO"], ["POS"], []]
    tokens = tmp_path / "tokens.json"
    tokens.write_text(json.dumps(corpus), encoding="utf-8")
    assert (
        invoke(
            monkeypatch,
            "compare",
            "--model-declaration",
            str(declaration),
            "--tokens-json",
            str(tokens),
            "--encoding",
            "two-predicate",
            "--binary-gap",
            "1",
            "--policy",
            "faithful",
            "--all-pairs",
            "-j",
        )
        == 0
    )
    actual = json.loads(capsys.readouterr().out)
    expected = compare_declaration_encodings(
        load_ipa_features(),
        read_ternary_declaration(declaration),
        corpus,
        encodings=(BinaryEncoding.TWO_PREDICATE,),
        binary_gap=1.0,
        policies=(FAITHFUL,),
        all_pairs=True,
    )
    assert actual == json.loads(json.dumps(expected))


@pytest.mark.parametrize("operation", ["transform", "compare"])
def test_unknown_model_refuses(monkeypatch, capsys, operation, tmp_path):
    args = [operation, "--model", "missing"]
    if operation == "transform":
        args += ["--token", "p", "--encoding", "two-predicate"]
    else:
        tokens = tmp_path / "tokens.json"
        tokens.write_text('[["p"],["b"]]', encoding="utf-8")
        args += [
            "--tokens-json",
            str(tokens),
            "--encoding",
            "two-predicate",
            "--binary-gap",
            "1",
            "--policy",
            "faithful",
        ]
    assert invoke(monkeypatch, *args) == 1
    captured = capsys.readouterr()
    assert "Error:" in captured.err and not captured.out


def test_invalid_transform_refuses_missing_source_cells(
    monkeypatch, capsys, declaration
):
    incomplete = declaration.with_name("incomplete.xml")
    incomplete.write_text(
        declaration.read_text(encoding="utf-8").replace(
            '<s name="NEG" f="-" g="0"/>', '<s name="NEG" g="0"/>'
        ),
        encoding="utf-8",
    )
    assert (
        invoke(
            monkeypatch,
            "transform",
            "--model-declaration",
            str(incomplete),
            "--token",
            "ZERO",
            "--encoding",
            "two-predicate",
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "require-complete" in captured.err and not captured.out


@pytest.mark.parametrize("operation", ["transform", "compare"])
def test_new_command_help(monkeypatch, capsys, operation):
    monkeypatch.setattr(sys, "argv", ["ipakit", "model", operation, "--help"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "--model" in help_text
    assert "--encoding" in help_text
