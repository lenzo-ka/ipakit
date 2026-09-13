"""CLI selection delegates to the named metric registry over exact tokens."""

import json
import sys

import pytest
from ipakit import cli, feature_models


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["ipakit", "distance", *args])
    return cli.main()


def test_discovery_lists_names(monkeypatch, capsys):
    from ipakit.distance_registry import builtin_registry

    assert invoke(monkeypatch, "metrics", "-j") == 0
    assert json.loads(capsys.readouterr().out) == list(builtin_registry().names)


def test_across_delegates_exact_corpus_and_selection(monkeypatch, capsys, tmp_path):
    from ipakit.distance_registry import DistanceRegistry

    corpus = [["A/B #"], ["p"], []]
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    calls = []

    def spy(self, values, *, metrics, all_pairs):
        calls.append((values, metrics, all_pairs))
        return {"receipt": "delegated"}

    monkeypatch.setattr(DistanceRegistry, "compare_corpus", spy)
    assert (
        invoke(
            monkeypatch,
            "across",
            "--tokens-json",
            str(path),
            "--metric",
            "panphon/symmetric-difference",
            "--all-pairs",
            "-j",
        )
        == 0
    )
    assert calls == [(corpus, ["panphon/symmetric-difference"], True)]
    assert json.loads(capsys.readouterr().out) == {"receipt": "delegated"}


@pytest.mark.parametrize(
    "selection",
    [
        ["missing"],
        ["all", "house/articulatory"],
        ["house/articulatory", "house/articulatory"],
    ],
)
def test_bad_selection_is_an_error(monkeypatch, capsys, tmp_path, selection):
    path = tmp_path / "tokens.json"
    path.write_text('[["p"],["b"]]', encoding="utf-8")
    options = [arg for name in selection for arg in ("--metric", name)]
    assert (
        invoke(monkeypatch, "across", "--tokens-json", str(path), *options, "-j") == 1
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert "Error:" in captured.err


def test_custom_declaration_is_registered(monkeypatch, capsys):
    path = feature_models.resource_path("panphon")
    assert (
        invoke(
            monkeypatch, "metrics", "--metric-declaration", f"custom/table={path}", "-j"
        )
        == 0
    )
    assert "custom/table" in json.loads(capsys.readouterr().out)
