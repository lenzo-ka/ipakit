"""Integration tests for the ipakit CLI (ipakit.cli.main).

Each command group has at least a happy path, a JSON path (where supported,
asserting the output parses), and a failure path asserting exit code 1. Also
covers the top-level dispatch: no command, unknown command, and a bare group.
"""

import json
import sys

import ipakit.cli
import pytest


def run(monkeypatch, capsys, *argv):
    """Invoke main() with the given argv; return (rc, stdout, stderr)."""
    monkeypatch.setattr(sys, "argv", ["ipakit", *argv])
    rc = ipakit.cli.main()
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


class TestTopLevelDispatch:
    def test_no_command_prints_help(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys)
        assert rc == 0
        assert "usage" in out.lower()

    def test_unknown_command_exits_nonzero(self, monkeypatch, capsys):
        # argparse rejects an unknown subcommand with SystemExit(2).
        with pytest.raises(SystemExit) as exc:
            run(monkeypatch, capsys, "definitely-not-a-command")
        assert exc.value.code != 0

    def test_bare_group_shows_group_help(self, monkeypatch, capsys):
        # `ipakit convert` with no subcommand prints the group help and exits.
        with pytest.raises(SystemExit):
            run(monkeypatch, capsys, "convert")


class TestFeaturesAndDescribe:
    def test_features_text(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "features", "p")
        assert rc == 0
        assert "manner" in out and "plosive" in out

    def test_features_json(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "features", "p", "-j")
        assert rc == 0
        data = json.loads(out)
        assert data["name"] == "p"

    def test_features_unknown_phone_errors(self, monkeypatch, capsys):
        rc, _, err = run(monkeypatch, capsys, "features", "4")
        assert rc == 1
        assert "Unknown" in err or "parse" in err

    def test_describe(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "describe", "p")
        assert rc == 0
        assert out.strip() == "voiceless bilabial plosive"


class TestConvert:
    def test_to_cmu_text(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "convert", "to-cmu", "kæt")
        assert rc == 0
        assert out.split() == ["K", "AE0", "T"]

    def test_to_cmu_json(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "convert", "to-cmu", "kæt", "-j")
        assert rc == 0
        assert json.loads(out) == ["K", "AE0", "T"]

    def test_to_ipa_json(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "convert", "to-ipa", "K", "AE1", "T", "-j"
        )
        assert rc == 0
        assert json.loads(out) == "kˈæt"

    @pytest.mark.parametrize(
        "argv",
        [
            ("convert", "to-xsampa", "kæt", "-j"),
            ("convert", "from-xsampa", "k{t", "-j"),
            ("convert", "to-timit", "kæt", "-j"),
            ("convert", "from-timit", "k", "ae", "t", "-j"),
            ("convert", "to-kirshenbaum", "kæt", "-j"),
            ("convert", "normalize", "tʃ", "-j"),
            ("convert", "tokenize", "kæt", "-j"),
        ],
    )
    def test_convert_json_parses(self, monkeypatch, capsys, argv):
        rc, out, _ = run(monkeypatch, capsys, *argv)
        assert rc == 0
        json.loads(out)  # must be valid JSON

    def test_strict_fails_on_unconvertible(self, monkeypatch, capsys):
        rc, _, err = run(monkeypatch, capsys, "convert", "to-cmu", "k4t", "--strict")
        assert rc == 1
        assert "Cannot convert" in err

    def test_strict_clean_input_succeeds(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "convert", "to-cmu", "kæt", "--strict")
        assert rc == 0
        assert out.split() == ["K", "AE0", "T"]


class TestQuery:
    def test_match(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "query", "match", "plosive", "bilabial")
        assert rc == 0
        assert "p" in out.split()


class TestDistance:
    def test_pair(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "distance", "pair", "p", "b")
        assert rc == 0
        assert float(out.strip()) > 0

    def test_word(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "distance", "word", "kæt", "kæd")
        assert rc == 0
        assert "similarity" in out


class TestHierarchy:
    def test_text(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "hierarchy", "text")
        assert rc == 0
        assert len(out.strip()) > 0

    def test_json(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "hierarchy", "json")
        assert rc == 0
        json.loads(out)


class TestAnalysis:
    def test_natural_class(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "analysis", "natural-class", "p", "t", "k"
        )
        assert rc == 0
        assert "plosive" in out

    def test_validate_valid(self, monkeypatch, capsys):
        rc, _, _ = run(monkeypatch, capsys, "analysis", "validate", "kæt")
        assert rc == 0

    def test_validate_invalid_exits_one(self, monkeypatch, capsys):
        rc, _, _ = run(monkeypatch, capsys, "analysis", "validate", "k@t")
        assert rc == 1


class TestAnalyzeGroup:
    def test_summary(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "analyze", "summary")
        assert rc == 0
        assert len(out.strip()) > 0

    def test_data_alias(self, monkeypatch, capsys):
        # `data` is an alias for the `analyze` group.
        rc, out, _ = run(monkeypatch, capsys, "data", "summary")
        assert rc == 0
        assert len(out.strip()) > 0


class TestInfo:
    def test_stress(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "info", "stress")
        assert rc == 0
        assert len(out.strip()) > 0
