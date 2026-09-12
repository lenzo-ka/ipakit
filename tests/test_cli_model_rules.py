"""Finite rule commands delegate, preserve occurrences, and retain refusals."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from ipakit import cli
from ipakit.rules import Rule, RuleSet


@pytest.fixture
def declaration(tmp_path: Path) -> Path:
    path = tmp_path / "model.xml"
    path.write_text(
        '<model name="opaque" upstream="fixture" upstream-url="https://example.org" '
        'artifact="table" version="1" license="MIT" kind="features">'
        '<round-trip><external-to-house fidelity="lossy-with-report"/>'
        '<house-to-external fidelity="lossy-with-report"/></round-trip>'
        '<features><feature name="f"/><feature name="g"/></features><segments>'
        '<s name="A" f="-" g="0"/><s name="B" f="+" g="0"/>'
        '<s name="G" f="0" g="+"/><s name="A/B #" f="-" g="+"/>'
        '<s name="C" f="+" g="+"/><s name="C*" f="+" g="+"/>'
        '<s name="help" f="0" g="0"/><s name="?" g="0"/>'
        "</segments></model>",
        encoding="utf-8",
    )
    return path


def invoke(monkeypatch, capsys, declaration, operation, rows, *args):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(rows)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ipakit",
            "rules",
            operation,
            "--model-declaration",
            str(declaration),
            "--tokens-json",
            "-",
            "-j",
            *args,
        ],
    )
    result = cli.main()
    captured = capsys.readouterr()
    return result, json.loads(captured.out) if captured.out else None, captured.err


def test_feeding_trace_and_original_recognition_delegate(
    monkeypatch, capsys, declaration
):
    derive = RuleSet.derive_tokens
    recognize = Rule.recognize_tokens
    seen = []

    def derived(self, tokens, **kwargs):
        seen.append(("derive", tokens))
        return derive(self, tokens, **kwargs)

    def recognized(self, tokens, **kwargs):
        seen.append(("recognize", tokens))
        return recognize(self, tokens, **kwargs)

    monkeypatch.setattr(RuleSet, "derive_tokens", derived)
    monkeypatch.setattr(Rule, "recognize_tokens", recognized)
    monkeypatch.setattr(
        cli.Command, "ipa", property(lambda self: pytest.fail("native IPA"))
    )
    import ipakit.rules as rules_module

    monkeypatch.setattr(
        rules_module, "_default", lambda *a: pytest.fail("native default")
    )
    args = ("-r", "A -> B / _ G", "-r", "G -> help / B _")
    code, data, error = invoke(
        monkeypatch, capsys, declaration, "trace", [["A", "G", "A"]], *args
    )
    assert code == 0 and not error, error or data
    row = data[0]
    assert row["input"] == ["A", "G", "A"]
    assert row["tokens"] == ["B", "help", "A"]
    assert row["model_id"] and row["status"] == "ok"
    assert row["steps"][0] == {
        "rule": "A -> B / _ G",
        "fired": True,
        "before_tokens": ["A", "G", "A"],
        "after_tokens": ["B", "G", "A"],
        "edits": [
            {
                "rule": "A -> B / _ G",
                "start": 0,
                "end": 1,
                "replacement_tokens": ["B"],
                "deletion": False,
            }
        ],
    }
    assert row["steps"][1]["before_tokens"] == ["B", "G", "A"]
    code, data, _ = invoke(
        monkeypatch, capsys, declaration, "recognize", [["A", "G", "A"]], *args
    )
    assert code == 0
    assert data[0]["rules"] == [
        {
            "rule": "A -> B / _ G",
            "sites": [
                {"start": 0, "end": 1, "target_tokens": ["A"], "left": [], "right": [1]}
            ],
        },
        {"rule": "G -> help / B _", "sites": []},
    ]
    assert seen == [
        ("derive", ["A", "G", "A"]),
        ("recognize", ["A", "G", "A"]),
        ("recognize", ["A", "G", "A"]),
    ]


def test_batch_ambiguity_unknown_and_empty_are_not_dropped(
    monkeypatch, capsys, declaration
):
    code, rows, error = invoke(
        monkeypatch,
        capsys,
        declaration,
        "apply",
        [["A"], ["A/B #"], ["UNKNOWN"], []],
        "-r",
        "[f=-1] -> [f=1]",
        "--lax",
    )
    assert code == 1 and not error
    assert [row["input"] for row in rows] == [["A"], ["A/B #"], ["UNKNOWN"], []]
    assert [row["status"] for row in rows] == ["ok", "error", "error", "ok"]
    assert rows[0]["tokens"] == ["B"]
    assert rows[1]["error"]["code"] == "ambiguous"
    assert rows[1]["error"]["candidates"] == ["C", "C*"]
    assert rows[2]["error"]["type"] == "MissingToken"
    assert rows[3]["tokens"] == []


def test_deletion_opaque_tokens_and_missing_cells(monkeypatch, capsys, declaration):
    code, rows, _ = invoke(
        monkeypatch,
        capsys,
        declaration,
        "trace",
        [["A/B #", "?", "A"]],
        "-r",
        "[f=-1] -> ∅",
    )
    assert code == 0
    assert rows[0]["tokens"] == ["?"]
    assert rows[0]["steps"][0]["before_tokens"] == ["A/B #", "?", "A"]
    assert [edit["replacement_tokens"] for edit in rows[0]["steps"][0]["edits"]] == [
        [],
        [],
    ]
    assert all(edit["deletion"] for edit in rows[0]["steps"][0]["edits"])


def test_no_match_all_steps_and_empty_corpus(monkeypatch, capsys, declaration):
    code, rows, _ = invoke(
        monkeypatch, capsys, declaration, "trace", [["G"]], "-r", "A -> B", "--all"
    )
    assert code == 0 and rows[0]["tokens"] == ["G"]
    assert rows[0]["steps"][0]["fired"] is False
    code, rows, _ = invoke(
        monkeypatch, capsys, declaration, "apply", [], "-r", "A -> B"
    )
    assert code == 0 and rows == []


@pytest.mark.parametrize("operation", ["recognize", "apply", "trace"])
def test_empty_rule_file_still_validates_tokens(
    monkeypatch, capsys, declaration, tmp_path, operation
):
    path = tmp_path / "empty.rules"
    path.write_text("# comment only\n", encoding="utf-8")
    code, rows, _ = invoke(
        monkeypatch,
        capsys,
        declaration,
        operation,
        [["UNKNOWN"], []],
        "--file",
        str(path),
    )
    assert code == 1
    assert rows[0]["error"]["type"] == "MissingToken"
    assert rows[1]["status"] == "ok"


def test_literal_help_file_and_stdin_file_parity(
    monkeypatch, capsys, declaration, tmp_path
):
    monkeypatch.chdir(tmp_path)
    Path("help").write_text(
        "# a comment\nA -> B / _ G\nG -> help / B _\n", encoding="utf-8"
    )
    code, rows, _ = invoke(
        monkeypatch, capsys, declaration, "apply", [["A", "G"]], "--file", "help"
    )
    assert code == 0 and rows[0]["tokens"] == ["B", "help"]
    Path("tokens.json").write_text('[["A","G"]]', encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ipakit",
            "rules",
            "apply",
            "--model-declaration",
            str(declaration),
            "--tokens-json",
            "tokens.json",
            "--file",
            "help",
            "-j",
        ],
    )
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == rows


@pytest.mark.parametrize("data", [None, "A", 1, ["A"], [[1]], [[None]], [[""]], {}])
def test_invalid_token_documents(monkeypatch, capsys, declaration, data):
    code, rows, error = invoke(
        monkeypatch, capsys, declaration, "apply", data, "-r", "A -> B"
    )
    assert code == 1 and rows is None and "Error:" in error


@pytest.mark.parametrize(
    "args",
    [
        ("--keep-zeros",),
        ("A",),
        ("--set", "american-english"),
        ("-r", "A ~> B"),
        ("-r", "∅ -> A"),
        ("-r", "[f=α] -> [f=α]"),
    ],
)
def test_unsupported_modes_refuse(monkeypatch, capsys, declaration, args):
    code, rows, error = invoke(
        monkeypatch, capsys, declaration, "apply", [["A"]], *args
    )
    assert code == 1 and rows is None and "Error:" in error


def test_native_literal_help_file_is_not_a_help_request(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path("help").write_text("t -> ʔ / _ #", encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["ipakit", "rules", "apply", "--file", "help", "kæt"]
    )
    assert cli.main() == 0
    assert capsys.readouterr().out == "kæʔ\n"


@pytest.mark.parametrize(
    "args",
    [
        ["help", "rules", "apply"],
        ["rules", "help", "apply"],
        ["rules", "apply", "help"],
        ["rules", "apply", "kæt", "help"],
    ],
)
def test_genuine_help_forms_remain(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["ipakit", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "Without --model/--model-declaration" in output
    assert "exact token arrays" in output


def test_missing_selector_or_document_is_configuration_error(
    monkeypatch, capsys, declaration
):
    for args in [
        ["--tokens-json", "-"],
        ["--model-declaration", str(declaration)],
    ]:
        monkeypatch.setattr(
            sys, "argv", ["ipakit", "rules", "apply", *args, "-r", "A -> B"]
        )
        assert cli.main() == 1
        assert "Error:" in capsys.readouterr().err


def test_mixed_selectors_and_unsupported_commands_are_usage_errors(
    monkeypatch, declaration
):
    for args in [
        ["apply", "--model", "panphon", "--model-declaration", str(declaration)],
        ["variants", "--model", "panphon"],
        ["apply", "--from-json", "graph.json"],
    ]:
        monkeypatch.setattr(sys, "argv", ["ipakit", "rules", *args])
        with pytest.raises(SystemExit) as error:
            cli.main()
        assert error.value.code == 2


def test_finite_mode_refuses_native_xml(monkeypatch, capsys, declaration):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ipakit",
            "--ipa-xml",
            "native.xml",
            "rules",
            "apply",
            "--model-declaration",
            str(declaration),
            "--tokens-json",
            "-",
            "-r",
            "A -> B",
        ],
    )
    assert cli.main() == 1
    assert "native --ipa-xml" in capsys.readouterr().err


def test_comparison_and_rules_share_shape_admission(monkeypatch, capsys, declaration):
    from ipakit._token_corpus import validate_token_corpus
    from ipakit.bridges import costmodel
    from ipakit.cli import rules as command_module

    seen = []

    def spy(value):
        seen.append(value)
        return validate_token_corpus(value)

    monkeypatch.setattr(command_module, "validate_token_corpus", spy)
    code, rows, _ = invoke(
        monkeypatch, capsys, declaration, "apply", [[]], "-r", "A -> B"
    )
    assert code == 0 and rows[0]["tokens"] == []
    assert seen == [[[]]]
    seen.clear()
    monkeypatch.setattr(costmodel, "validate_token_corpus", spy)
    # The admitted shape is shared; comparison still owns its >=2-row policy.
    with pytest.raises(ValueError, match="nonempty token strings"):
        costmodel.compare_token_corpus(None, [None], [["A"], [1]])
    assert seen == [[["A"], [1]]]
    with pytest.raises(ValueError, match="at least two"):
        costmodel.compare_token_corpus(None, [None], [[]])


def test_unknown_and_named_suffix_refuse_without_dropping(
    monkeypatch, capsys, declaration
):
    code, rows, error = invoke(
        monkeypatch, capsys, declaration, "apply", [["A"]], "-r", "A -> B ; named"
    )
    assert code == 1 and rows is None and "named suffix" in error
    code, rows, error = invoke(
        monkeypatch, capsys, declaration, "trace", [["A"]], "-r", "A -> [f=0 g=-1]"
    )
    assert code == 1 and not error
    assert rows[0]["error"]["code"] == "unrealizable"
    assert rows[0]["error"]["candidates"] == []
