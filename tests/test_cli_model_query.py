"""Finite inventory matching reaches the declared model through its adapter."""

import json
import sys

import pytest
from ipakit import cli, feature_models
from ipakit.finite_model import FiniteModel


def invoke(monkeypatch, features):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ipakit",
            "model",
            "query",
            "--model",
            "panphon",
            "--features-json",
            features,
            "-j",
        ],
    )
    return cli.main()


def test_query_delegates_to_selected_model(monkeypatch, capsys):
    original = FiniteModel.query
    calls = []

    def spy(self, constraints):
        calls.append((self.identity, constraints))
        return original(self, constraints)

    monkeypatch.setattr(FiniteModel, "query", spy)
    monkeypatch.setattr(
        cli.Command, "ipa", property(lambda _: pytest.fail("house admission"))
    )
    assert invoke(monkeypatch, '{"voi":1}') == 0
    data = json.loads(capsys.readouterr().out)
    assert calls == [(data["model_id"], {"voi": 1})]
    assert "b" in data["matches"]
    assert "p" not in data["matches"]
    assert data["operation"] == "phones_matching"


def test_empty_query_returns_all_rows_in_order(monkeypatch, capsys):
    assert invoke(monkeypatch, "{}") == 0
    assert json.loads(capsys.readouterr().out)["matches"] == list(
        feature_models.read("panphon").model.rows
    )


@pytest.mark.parametrize(
    "value",
    [
        '{"voi":true}',
        '{"voi":"1"}',
        '{"voi":2}',
        '{"unknown":1}',
        '{"voi":1,"voi":0}',
        "[]",
        '{"voi":NaN}',
    ],
)
def test_invalid_query_refuses(monkeypatch, capsys, value):
    assert invoke(monkeypatch, value) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Error:" in captured.err
