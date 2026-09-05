"""Paired phoneset set, mapping, matrix, and CLI reports."""

from __future__ import annotations

import json
import sys

import ipakit
import pytest


def test_small_comparison_preserves_order_strips_prosody_and_measures() -> None:
    result = ipakit.phoneset_comparison(["ˈa", "p", "t"], ["a", "t", "k"])
    assert result.a.phones == ["a", "p", "t"]
    assert result.b.phones == ["a", "t", "k"]
    assert result.union == ("a", "p", "t", "k")
    assert result.intersection == ("a", "t")
    assert result.only_a == ("p",)
    assert result.only_b == ("k",)
    assert result.stripped == (("ˈa", "a"),)
    assert result.forward.source is result.a
    for i, left in enumerate(result.a):
        for j, right in enumerate(result.b):
            assert result.matrix[i][j] == pytest.approx(
                1.0 - ipakit.distance(left, right)
            )


def test_strip_selects_stress_all_prosody_or_nothing() -> None:
    phones = ["ˈiː", "ˌa˥"]
    stress = ipakit.phoneset_comparison(phones, phones)
    prosodic = ipakit.phoneset_comparison(phones, phones, strip="prosodic")
    nothing = ipakit.phoneset_comparison(phones, phones, strip=None)
    assert stress.a.phones == ["iː", "a˥"]
    assert stress.stripped == (
        ("ˈiː", "iː"),
        ("ˌa˥", "a˥"),
        ("ˈiː", "iː"),
        ("ˌa˥", "a˥"),
    )
    assert prosodic.a.phones == ["i", "a"]
    assert nothing.a.phones == phones
    assert nothing.stripped == ()


def test_reverse_matrix_is_the_transpose() -> None:
    forward = ipakit.phoneset_comparison(["p", "a"], ["b", "i", "t"])
    reverse = ipakit.phoneset_comparison(["b", "i", "t"], ["p", "a"])
    assert forward.matrix == tuple(zip(*reverse.matrix, strict=True))


def test_english_us_pair_invariants() -> None:
    result = ipakit.phoneset_comparison("pocketsphinx", "mfa:english_us")
    assert (len(result.a), len(result.b)) == (41, 78)
    assert (len(result.union), len(result.intersection), len(result.only_b)) == (
        86,
        33,
        45,
    )
    assert result.stripped == ()
    assert result.backward.collapses["i"] == ("i", "iː")
    assert result.backward.collapses["ɑ"] == ("ɑ", "ɑː")
    assert result.backward.collapses["ɔ"] == ("ɒ", "ɒː")
    assert result.backward.collapses["ʊ"] == ("ʉ", "ʉː", "ʊ")
    assert set(result.intersection) <= set(result.union)
    assert set(result.only_a).isdisjoint(result.only_b)
    assert result.forward.source is result.a
    assert all(0.0 <= value <= 1.0 for row in result.matrix for value in row)
    union = ipakit.phoneset_comparison(result.union, result.union)
    for i in range(len(union.union)):
        for j in range(len(union.union)):
            assert union.matrix[i][j] == pytest.approx(union.matrix[j][i])


def _run(monkeypatch, capsys, *args: str):
    import ipakit.cli

    monkeypatch.setattr(sys, "argv", ["ipakit", "distance", "compare", *args])
    status = ipakit.cli.main()
    captured = capsys.readouterr()
    return status, captured.out, captured.err


@pytest.mark.parametrize("format_", ["text", "json", "tsv"])
def test_cli_formats(tmp_path, monkeypatch, capsys, format_: str) -> None:
    a = tmp_path / "a.phones"
    b = tmp_path / "b.phones"
    a.write_text("ˈa\np\n", encoding="utf-8")
    b.write_text("a\nb\n", encoding="utf-8")
    status, output, _ = _run(monkeypatch, capsys, str(a), str(b), "-f", format_)
    assert status == 0
    if format_ == "json":
        assert json.loads(output)["stripped"] == [["ˈa", "a"]]
    elif format_ == "tsv":
        assert output.startswith("\ta\tb\n")
        assert "union:" not in output
    else:
        assert "union:" in output
        assert "A -> B:" in output
        assert "similarity matrix:" in output


def test_cli_refuses_name_file_collision(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mfa").write_text("p\n", encoding="utf-8")
    status, _, error = _run(monkeypatch, capsys, "mfa", "pocketsphinx")
    assert status != 0
    assert "both an inventory and a file" in error


@pytest.mark.parametrize(
    "option, expected",
    [("stress", ["iː"]), ("prosodic", ["i"]), ("none", ["ˈiː"])],
)
def test_cli_strip_modes(tmp_path, monkeypatch, capsys, option, expected) -> None:
    phones = tmp_path / "phones"
    phones.write_text("ˈiː\n", encoding="utf-8")
    status, output, _ = _run(
        monkeypatch, capsys, str(phones), str(phones), "--strip", option, "-f", "json"
    )
    assert status == 0
    assert json.loads(output)["a"] == expected
