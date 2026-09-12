"""Finite CLI dispatch preserves typed edits and opaque token identities."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from ipakit import cli
from ipakit.finite_model import FiniteModel


@pytest.fixture
def declaration(tmp_path: Path) -> Path:
    path = tmp_path / "opaque.xml"
    path.write_text(
        '<model name="opaque" upstream="fixture" upstream-url="https://example.org" '
        'artifact="table" version="1" license="MIT" kind="features">'
        '<round-trip><external-to-house fidelity="lossy-with-report"/>'
        '<house-to-external fidelity="lossy-with-report"/></round-trip>'
        '<features><feature name="f"/><feature name="g"/></features>'
        '<segments><s name="A/B #" f="-" g="0"/>'
        '<s name="help" f="+" g="0"/><s name="∅" f="+" g="0"/>'
        '<s name="?" g="0"/></segments></model>',
        encoding="utf-8",
    )
    return path


def invoke(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["ipakit", "model", *args])
    return cli.main()


def test_inspect_ordered_schema_and_exact_rows(monkeypatch, capsys, declaration):
    assert (
        invoke(
            monkeypatch,
            "inspect",
            "--model-declaration",
            str(declaration),
            "--rows",
            "-j",
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["schema"] == [
        {"feature": "f", "domain": [-1, 0, 1]},
        {"feature": "g", "domain": [-1, 0, 1]},
    ]
    assert data["rows"] == [
        {"token": "A/B #", "values": [-1, 0]},
        {"token": "help", "values": [1, 0]},
        {"token": "∅", "values": [1, 0]},
        {"token": "?", "values": [None, 0]},
    ]
    assert data["token_count"] == 4
    assert data["codec"]["input_tokens"] == "exact; no normalization or segmentation"
    assert data["source"]["version"] == "1"
    assert data["model_id"]


@pytest.mark.parametrize(
    "changes,status,candidates",
    [
        ('{"f":1}', "ambiguous", ["help", "∅"]),
        ('{"g":1}', "none", []),
        ('{"f":null}', "unique", ["?"]),
    ],
)
def test_respelling_calls_public_method(
    monkeypatch, capsys, declaration, changes, status, candidates
):
    original = FiniteModel.respell
    calls = []

    def spy(self, token, edits):
        calls.append((token, edits))
        return original(self, token, edits)

    monkeypatch.setattr(FiniteModel, "respell", spy)
    monkeypatch.setattr(
        cli.Command, "ipa", property(lambda self: pytest.fail("house parsing"))
    )
    assert (
        invoke(
            monkeypatch,
            "respell",
            "--model-declaration",
            str(declaration),
            "--token",
            "A/B #",
            "--changes-json",
            changes,
            "-j",
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert calls == [("A/B #", json.loads(changes))]
    assert data["status"] == status
    assert data["candidates"] == candidates
    assert data["input"] == "A/B #"
    assert data["model_id"]


@pytest.mark.parametrize(
    "changes",
    [
        '{"f":true}',
        '{"f":"1"}',
        '{"f":2}',
        '{"other":0}',
        '{"f":1,"f":0}',
        "[]",
        "null",
        '{"f":NaN}',
    ],
)
def test_invalid_edits_are_errors_even_lax(monkeypatch, capsys, declaration, changes):
    assert (
        invoke(
            monkeypatch,
            "respell",
            "--model-declaration",
            str(declaration),
            "--token",
            "A/B #",
            "--changes-json",
            changes,
            "--lax",
            "-j",
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert not captured.out


def test_help_is_an_opaque_token(monkeypatch, capsys, declaration):
    assert (
        invoke(
            monkeypatch,
            "respell",
            "--model-declaration",
            str(declaration),
            "--token",
            "help",
            "--changes-json",
            "{}",
            "-j",
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["input"] == "help"


@pytest.mark.parametrize(
    "args", [["inspect"], ["inspect", "--model", "panphon", "--model-declaration", "x"]]
)
def test_exactly_one_selector(monkeypatch, args):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *args)
    assert error.value.code == 2


def test_shipped_list_and_real_panphon(monkeypatch, capsys):
    assert invoke(monkeypatch, "list", "-j") == 0
    assert "panphon" in json.loads(capsys.readouterr().out)
    assert (
        invoke(
            monkeypatch,
            "respell",
            "--model",
            "panphon",
            "--token",
            "p",
            "--changes-json",
            '{"voi":1}',
            "-j",
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["candidates"] == ["b", "b̟", "b̠"]


@pytest.mark.parametrize(
    "args",
    [
        ["help", "model"],
        ["model", "help"],
        ["model", "help", "respell"],
        ["model", "respell", "help"],
    ],
)
def test_command_help_remains_available(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["ipakit", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_literal_help_declaration_path(monkeypatch, capsys, declaration):
    literal = declaration.with_name("help")
    declaration.rename(literal)
    monkeypatch.chdir(literal.parent)
    assert invoke(monkeypatch, "inspect", "--model-declaration", "help", "-j") == 0
    assert json.loads(capsys.readouterr().out)["name"] == "opaque"


@pytest.mark.parametrize(
    "args",
    [
        ["inspect", "--model", "missing"],
        ["inspect", "--model-declaration", "missing.xml"],
        [
            "respell",
            "--model",
            "panphon",
            "--token",
            "not a token",
            "--changes-json",
            "{}",
        ],
    ],
)
def test_admission_failures(monkeypatch, capsys, args):
    assert invoke(monkeypatch, *args) == 1
    assert "Error:" in capsys.readouterr().err


def test_receiver_guard_distinguishes_native_and_finite():
    import ast

    from tests.test_cli import _finite_receiver_attribute

    tree = ast.parse("""
def native(model: IPAFeatures):
    return model.respell("p", {})
def foreign(model: Alias):
    return model.respell("p", {})
def local():
    model: FiniteModel = declared.model
    return model.respell("p", {})
""")
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "respell"
    ]
    assert [
        _finite_receiver_attribute(node, parents, {"FiniteModel", "Alias"})
        for node in calls
    ] == [False, True, True]


def test_receiver_guard_does_not_borrow_nested_annotations():
    import ast

    from tests.test_cli import _finite_receiver_attribute

    tree = ast.parse("""
def outer(model: IPAFeatures):
    def inner():
        model: FiniteModel = declaration.model
        return model.respell("p", {})
    return model.respell("p", {})
""")
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    calls = {
        node.lineno: _finite_receiver_attribute(node, parents, {"FiniteModel"})
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "respell"
    }
    assert calls == {5: True, 6: False}
