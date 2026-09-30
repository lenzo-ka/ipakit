"""CLI parity for structured CLTS import and token emission."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ipakit.cli
import pytest
from ipakit import _clts_import
from ipakit.clts import emit_tokens, import_document, import_tokens


def _run(monkeypatch, capsys, *argv: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["ipakit", *argv])
    status = ipakit.cli.main()
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_token_read_uses_the_library_encoder_and_status(tmp_path, monkeypatch, capsys):
    source = _write(tmp_path / "tokens.json", ["p", "b"])
    expected = import_tokens(["p", "b"])

    status, stdout, stderr = _run(
        monkeypatch, capsys, "clts", "read", "--tokens-json", str(source)
    )

    assert status == 0
    assert stdout == expected.to_json() + "\n"
    assert stderr == ""


def test_strict_refusal_is_complete_json_and_nonzero(tmp_path, monkeypatch, capsys):
    source = _write(tmp_path / "tokens.json", ["p", "a"])
    expected = import_tokens(["p", "a"])

    status, stdout, stderr = _run(
        monkeypatch, capsys, "clts", "read", "--tokens-json", str(source)
    )

    assert status == 1
    assert stdout == expected.to_json() + "\n"
    assert json.loads(stdout)["report"]["occurrences"][0]["raw"] == "p"
    assert stderr == ""


def test_structured_preserve_round_trips_timing_and_relation(
    tmp_path, monkeypatch, capsys
):
    document = {
        "format": "ipakit-clts-input",
        "version": 1,
        "tokens": [
            {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
            {"raw": "⁵"},
        ],
        "relations": [
            {
                "type": "clts:source-tone-host",
                "source": "/tokens/1",
                "target": "/tokens/0",
            }
        ],
    }
    source = _write(tmp_path / "input.json", document)
    expected = import_document(document, unsupported="preserve")

    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "read",
        "--input-json",
        str(source),
        "--unsupported",
        "preserve",
    )

    assert status == 0
    assert stdout == expected.to_json() + "\n"
    result = json.loads(stdout)
    assert result["report"]["occurrences"][0]["time"] == document["tokens"][0]["time"]
    assert result["report"]["relations"] == document["relations"]
    assert stderr == ""


def test_operation_error_is_machine_readable_and_nonzero(tmp_path, monkeypatch, capsys):
    source = _write(tmp_path / "tokens.json", "unsegmented")

    status, stdout, stderr = _run(
        monkeypatch, capsys, "clts", "read", "--tokens-json", str(source)
    )

    assert status == 1
    assert json.loads(stdout) == {
        "error": {
            "code": "segmentation-required",
            "message": "supply explicit tokens",
            "path": "",
        },
        "form": None,
    }
    assert stderr == ""


def test_read_inputs_are_mutually_exclusive(tmp_path, monkeypatch, capsys):
    source = _write(tmp_path / "input.json", [])
    with pytest.raises(SystemExit) as caught:
        _run(
            monkeypatch,
            capsys,
            "clts",
            "read",
            "--tokens-json",
            str(source),
            "--input-json",
            str(source),
        )
    assert caught.value.code == 2


def test_structured_input_rejects_duplicate_json_keys(tmp_path, monkeypatch, capsys):
    source = tmp_path / "input.json"
    source.write_text(
        '{"format":"ipakit-clts-input","format":"changed","version":1,"tokens":[]}',
        encoding="utf-8",
    )

    status, stdout, stderr = _run(
        monkeypatch, capsys, "clts", "read", "--input-json", str(source)
    )

    assert status == 1
    assert json.loads(stdout)["error"]["code"] == "invalid-input"
    assert "duplicate JSON key: format" in stdout
    assert stderr == ""


def test_emission_uses_the_library_encoder_and_exit_status(
    tmp_path, monkeypatch, capsys
):
    held = import_tokens(["t͜s"], unsupported="preserve")
    source = tmp_path / "import.json"
    source.write_text(held.to_json(), encoding="utf-8")

    refused = emit_tokens(held, spelling="bipa")
    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "emit",
        "--from-json",
        str(source),
        "--spelling",
        "bipa",
    )
    assert status == 1
    assert stdout == refused.to_json() + "\n"
    assert stderr == ""

    allowed = emit_tokens(held, spelling="bipa", allow_loss=True)
    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "emit",
        "--from-json",
        str(source),
        "--spelling",
        "bipa",
        "--allow-loss",
    )
    assert status == 0
    assert stdout == allowed.to_json() + "\n"
    assert stderr == ""


def test_source_emission_accepts_the_native_form_document(
    tmp_path, monkeypatch, capsys
):
    held = import_tokens(["p"])
    source = tmp_path / "form.json"
    source.write_text(json.dumps(held.to_data()["form"]), encoding="utf-8")

    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "emit",
        "--from-json",
        str(source),
        "--spelling",
        "source",
    )

    assert status == 0
    assert stdout == emit_tokens(held, spelling="source").to_json() + "\n"
    assert stderr == ""


def test_explicit_source_selection_reaches_the_validated_binding(
    tmp_path, monkeypatch, capsys
):
    tokens = _write(tmp_path / "tokens.json", ["p"])
    source = tmp_path / "source"
    source.mkdir()
    manifest = _write(tmp_path / "manifest.json", {})
    seen = []

    def selected(clts_path: Path, manifest_path: Path):
        seen.append((clts_path, manifest_path))
        return _clts_import._verified_binding()

    monkeypatch.setattr(_clts_import, "_live_binding", selected)
    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "read",
        "--tokens-json",
        str(tokens),
        "--clts",
        str(source),
        "--manifest",
        str(manifest),
    )

    assert status == 0
    assert json.loads(stdout)["report"]["provenance"]["domain"] == "core-bipa"
    assert seen == [(source.resolve(), manifest.resolve())]
    assert stderr == ""


def test_source_and_manifest_must_be_selected_together(tmp_path, monkeypatch, capsys):
    tokens = _write(tmp_path / "tokens.json", ["p"])
    source = tmp_path / "source"
    source.mkdir()

    status, stdout, stderr = _run(
        monkeypatch,
        capsys,
        "clts",
        "read",
        "--tokens-json",
        str(tokens),
        "--clts",
        str(source),
    )

    assert status == 1
    assert json.loads(stdout)["error"]["code"] == "invalid-option"
    assert stderr == ""
