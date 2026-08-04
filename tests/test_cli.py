"""Integration tests for the ipakit CLI (ipakit.cli.main).

Each command group has at least a happy path, a JSON path (where supported,
asserting the output parses), and a failure path asserting exit code 1. Also
covers the top-level dispatch: no command, unknown command, and a bare group.
"""

import ast
import inspect
import io
import json
import re
import shlex
import sys
import warnings
from pathlib import Path

import ipakit
import ipakit.cli
import pytest
from ipakit.cli.policy import LOSSY, input_reports

ROOT = Path(__file__).resolve().parent.parent


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

    def test_stress_names_each_marker_as_the_data_does(self, monkeypatch, capsys):
        """The answer, rather than that something was printed.

        The name used to be ``"primary" if level == 1 else "secondary"``:
        the ``{"ˈ": 1, "ˌ": 2}`` table this package removed, reintroduced
        as a comparison. A third declared level printed "secondary" and
        the assertion above stayed green, which is the failure mode. The
        name is read off the marker's own ``stress`` value now, so this
        sweeps every marker the data declares instead of naming two.
        """
        rc, out, _ = run(monkeypatch, capsys, "info", "stress")
        assert rc == 0
        features = ipakit.load_ipa_features()
        markers = features.stress_markers
        assert markers, "no stress marker is declared: the sweep would be vacuous"
        for marker, level in markers.items():
            declared = features.diacritics[marker].features["stress"]
            lines = [ln for ln in out.splitlines() if ln.startswith(f"  {marker} ")]
            assert len(lines) == 1, marker
            assert declared in lines[0], (marker, lines[0])
            assert f"level {level}" in lines[0], (marker, lines[0])


# --------------------------------------------------------------------------
# The rewrite-rule group (ipakit rules ...)
# --------------------------------------------------------------------------


TAP = "t -> ɾ / [vowel stress=primary] _ [vowel] ; tapping"
GLOTTAL = "t -> ʔ / _ # ; glottalling"


class TestTheRulesGroupIsWiredIntoTheCommandTree:
    def test_the_top_level_help_names_it(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys)
        assert rc == 0
        assert "rules" in out

    def test_the_bare_group_shows_its_help(self, monkeypatch, capsys):
        with pytest.raises(SystemExit):
            run(monkeypatch, capsys, "rules")

    def test_the_group_alias_reaches_the_same_command(self, monkeypatch, capsys):
        long = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL, "kæt")
        short = run(monkeypatch, capsys, "r", "a", "-r", GLOTTAL, "kæt")
        assert long == short == (0, "kæʔ\n", "")

    def test_help_anywhere_reaches_a_subcommand(self, monkeypatch, capsys):
        with pytest.raises(SystemExit):
            run(monkeypatch, capsys, "rules", "trace", "help")


class TestApplyRewritesAndComposes:
    def test_the_shipped_set_takes_broad_to_narrow(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "apply", "-s", "american-english", "pˈɪn"
        )
        assert rc == 0
        assert out == "pʰˈɪ̃n\n"

    def test_one_line_of_output_per_form_in_order(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "apply",
            "-s",
            "american-english",
            "pˈɪn",
            "bˈʌtɚ",
            "kˈæt",
        )
        assert rc == 0
        assert out.splitlines() == ["pʰˈɪ̃n", "bˈʌɾɚ", "kʰˈæt̚"]

    def test_a_rule_written_on_the_command_line(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL, "kæt")
        assert rc == 0
        assert out == "kæʔ\n"

    def test_repeating_the_rule_flag_is_an_ordered_cascade(self, monkeypatch, capsys):
        """The CLI must not lose the ordering the engine's semantics live in."""
        fed = run(
            monkeypatch,
            capsys,
            "rules",
            "apply",
            "-r",
            "a -> i / _ t ; raising",
            "-r",
            "t -> ʔ / i _ ; glottalling",
            "at",
        )
        starved = run(
            monkeypatch,
            capsys,
            "rules",
            "apply",
            "-r",
            "t -> ʔ / i _ ; glottalling",
            "-r",
            "a -> i / _ t ; raising",
            "at",
        )
        assert fed[1] == "iʔ\n"
        assert starved[1] == "it\n"

    def test_forms_arrive_on_stdin_when_none_are_given(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("pˈɪn\n\nbˈʌtɚ\n"))
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "apply", "-s", "american-english"
        )
        assert rc == 0
        assert out.splitlines() == ["pʰˈɪ̃n", "bˈʌɾɚ"]

    def test_a_rule_file_and_the_same_rule_inline_agree(
        self, monkeypatch, capsys, tmp_path
    ):
        path = tmp_path / "glottal.rules"
        # A comment line, to pin that '#' at line start is not read as a
        # word boundary when the file is loaded through the CLI.
        path.write_text(f"# glottalling only\n{GLOTTAL}\n", encoding="utf-8")
        from_file = run(
            monkeypatch, capsys, "rules", "apply", "--file", str(path), "kæt"
        )
        inline = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL, "kæt")
        assert from_file == inline == (0, "kæʔ\n", "")

    def test_json_is_a_row_per_form(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "apply",
            "-s",
            "american-english",
            "pˈɪn",
            "-j",
        )
        assert rc == 0
        assert json.loads(out) == [{"form": "pˈɪn", "derived": "pʰˈɪ̃n"}]

    def test_output_goes_to_a_file_when_asked(self, monkeypatch, capsys, tmp_path):
        out_path = tmp_path / "derived.txt"
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "apply",
            "-s",
            "american-english",
            "pˈɪn",
            "-o",
            str(out_path),
        )
        assert rc == 0
        assert out == ""
        assert out_path.read_text(encoding="utf-8") == "pʰˈɪ̃n\n"


class TestTheTraceSaysWhichRuleFiredWhere:
    def test_it_names_the_rule_and_the_edit(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "trace", "-s", "american-english", "bˈʌtɚ"
        )
        assert rc == 0
        assert out.splitlines() == [
            "bˈʌtɚ",
            "  tapping",
            "      tapping: t -> ɾ @2",
            "  = bˈʌɾɚ",
        ]

    def test_by_default_only_the_rules_that_fired_appear(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "trace", "-s", "american-english", "pˈɪn"
        )
        assert rc == 0
        assert "aspiration" in out
        assert "tapping" not in out
        assert "(no change)" not in out

    def test_all_shows_the_rules_that_did_nothing(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "trace",
            "-s",
            "american-english",
            "pˈɪn",
            "--all",
        )
        assert rc == 0
        # The marker follows the name; it used to precede it, which put
        # the names at two columns. See the alignment tests below.
        assert "tapping  (no change)" in out
        assert "aspiration: p -> pʰ @0" in out

    def test_every_rule_name_sits_at_the_same_column_under_all(
        self, monkeypatch, capsys
    ):
        """The defect: '  tapping' printed under '  (no change) tapping'.

        A trace is read by scanning down the names, so the one column a
        reader follows was the one that moved. The whole listing is
        pinned, because "the names line up" is a claim about the bytes.
        """
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "trace",
            "-r",
            TAP,
            "-r",
            GLOTTAL,
            "bˈʌtɚ",
            "--all",
        )
        assert rc == 0
        assert out.splitlines() == [
            "bˈʌtɚ",
            "  tapping",
            "      tapping: t -> ɾ @2",
            "  = bˈʌɾɚ",
            "  glottalling  (no change)",
            "      -",
            "  = bˈʌɾɚ",
        ]

    def test_the_default_trace_is_unchanged_by_the_marker_moving(
        self, monkeypatch, capsys
    ):
        """Without ``--all`` every step shown fired, so no marker is
        written and the line is the indent and the name, byte for byte
        what it was before the marker moved. The same listing under
        ``--all`` differs only by the steps that did nothing."""
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "trace", "-r", TAP, "-r", GLOTTAL, "bˈʌtɚ"
        )
        assert rc == 0
        assert out.splitlines() == [
            "bˈʌtɚ",
            "  tapping",
            "      tapping: t -> ɾ @2",
            "  = bˈʌɾɚ",
        ]
        assert "(no change)" not in out
        rc, everything, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "trace",
            "-r",
            TAP,
            "-r",
            GLOTTAL,
            "bˈʌtɚ",
            "--all",
        )
        assert rc == 0
        assert [line for line in everything.splitlines() if "(no change)" not in line][
            :4
        ] == out.splitlines()

    def test_a_derivation_that_fires_nothing_says_so(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "trace", "-r", GLOTTAL, "æ")
        assert rc == 0
        assert out.splitlines() == ["æ", "  (no rule fired)"]

    def test_several_forms_are_separated_by_a_blank_line(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "trace", "-r", TAP, "bˈʌtɚ", "æ")
        assert rc == 0
        assert out == (
            "bˈʌtɚ\n  tapping\n      tapping: t -> ɾ @2\n  = bˈʌɾɚ\n"
            "\næ\n  (no rule fired)\n"
        )

    def test_json_carries_the_step_and_its_edits(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "trace",
            "-s",
            "american-english",
            "bˈʌtɚ",
            "-j",
        )
        assert rc == 0
        assert json.loads(out) == [
            {
                "form": "bˈʌtɚ",
                "derived": "bˈʌɾɚ",
                "steps": [
                    {
                        "rule": "tapping",
                        "before": "bˈʌtɚ",
                        "after": "bˈʌɾɚ",
                        "fired": True,
                        "edits": [
                            {
                                "rule": "tapping",
                                "start": 2,
                                "end": 3,
                                "before": "t",
                                "after": "ɾ",
                                "insertion": False,
                                "deletion": False,
                            }
                        ],
                    }
                ],
            }
        ]

    def test_json_all_includes_the_steps_that_did_nothing(self, monkeypatch, capsys):
        quiet = json.loads(
            run(
                monkeypatch,
                capsys,
                "rules",
                "trace",
                "-s",
                "american-english",
                "pˈɪn",
                "-j",
            )[1]
        )
        every = json.loads(
            run(
                monkeypatch,
                capsys,
                "rules",
                "trace",
                "-s",
                "american-english",
                "pˈɪn",
                "-j",
                "--all",
            )[1]
        )
        assert len(quiet[0]["steps"]) == 2  # aspiration, then nasalization
        assert len(every[0]["steps"]) > len(quiet[0]["steps"])
        assert not all(s["fired"] for s in every[0]["steps"])


class TestRecognitionIsSeparateFromRewriting:
    def test_it_answers_where_without_rewriting(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "recognize", "-r", GLOTTAL, "kæt"
        )
        assert rc == 0
        assert out.splitlines() == ["kæt: 1 site", "  glottalling  @2  t  _ #"]
        assert "ʔ" not in out

    def test_it_names_which_neighbors_licensed_the_site(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "recognize",
            "-r",
            "[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing",
            "atapa",
        )
        assert rc == 0
        assert out.splitlines() == [
            "atapa: 2 sites",
            "  voicing  @1  t  a _ a",
            "  voicing  @3  p  a _ a",
        ]

    def test_the_forms_own_edge_reads_as_a_word_boundary(self, monkeypatch, capsys):
        """'_ #' fires at the end of a form without a '#' having been typed,
        and the environment column must say '#' rather than name the last
        unit of the form as its own licensor."""
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "recognize", "-r", GLOTTAL, "kæt", "-j"
        )
        assert rc == 0
        site = json.loads(out)[0]["sites"][0]
        assert site["right"] == [None]
        assert site["environment"] == "_ #"

    def test_no_site_is_reported_and_is_not_an_error(self, monkeypatch, capsys):
        rc, out, err = run(
            monkeypatch, capsys, "rules", "recognize", "-r", GLOTTAL, "bˈʌtɚ"
        )
        assert rc == 0
        assert err == ""
        assert out == "bˈʌtɚ: 0 sites\n"

    def test_an_insertion_site_shows_an_empty_target(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "recognize",
            "-r",
            "∅ -> ə / [manner=plosive] _ [manner=plosive] ; epenthesis",
            "ptk",
        )
        assert rc == 0
        assert out.splitlines() == [
            "ptk: 2 sites",
            "  epenthesis  @1  ∅  p _ t",
            "  epenthesis  @2  ∅  t _ k",
        ]

    def test_every_rule_of_a_set_is_asked_of_the_form_as_given(
        self, monkeypatch, capsys
    ):
        """Recognition applies no rewrite, so a rule that only fires on an
        earlier rule's output recognizes nothing. Aspiration reaches 'pɪn'
        as written; nasalization reaches it too, since '[vowel] _ [nasal]'
        holds on the input. Tapping does not, and must not be reported."""
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "recognize",
            "-s",
            "american-english",
            "pˈɪn",
            "-j",
        )
        assert rc == 0
        fired = [s["rule"] for s in json.loads(out)[0]["sites"]]
        assert fired == ["aspiration", "nasalization"]

    def test_json_reports_the_units_the_indices_count(self, monkeypatch, capsys):
        rc, out, _ = run(
            monkeypatch, capsys, "rules", "recognize", "-r", TAP, "bˈʌ.tɚ", "-j"
        )
        assert rc == 0
        row = json.loads(out)[0]
        assert row["units"] == ["b", "ˈʌ", ".", "t", "ɚ"]
        assert row["sites"] == [
            {
                "rule": "tapping",
                "start": 3,
                "end": 4,
                "target": "t",
                "environment": "ˈʌ _ ɚ",
                "left": [1],
                "right": [4],
                "insertion": False,
                # Present on every row, not only where a rule names an
                # agreement variable, so a consumer reads one shape either
                # way and cannot mistake an absent key for "bound nothing".
                "bindings": {},
            }
        ]

    def test_json_carries_what_an_agreement_variable_bound(self, monkeypatch, capsys):
        """The other half: a rule that does name one reports it.

        Two sites, two different bindings, which is the whole point of
        the variable -- a rule whose report said only "these two sites
        matched" would have dropped what it did there.
        """
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "recognize",
            "-r",
            "n -> [place=α] / _ [place=α] ; assim",
            "anpanka",
            "-j",
        )
        assert rc == 0
        sites = json.loads(out)[0]["sites"]
        assert [s["bindings"] for s in sites] == [
            {"α": "bilabial"},
            {"α": "velar"},
        ]

    def test_the_text_report_names_the_binding_beside_the_environment(
        self, monkeypatch, capsys
    ):
        rc, out, _ = run(
            monkeypatch,
            capsys,
            "rules",
            "recognize",
            "-r",
            "n -> [place=α] / _ [place=α] ; assim",
            "anka",
        )
        assert rc == 0
        assert out.splitlines() == ["anka: 1 site", "  assim  @1  n  _ k  α=velar"]


class TestRuleUnitsKeepTheBoundariesTokenizeDrops:
    def test_the_syllable_dot_survives_here_and_not_in_tokenize(
        self, monkeypatch, capsys
    ):
        """Two differences, both load-bearing for a rule: `tokenize` drops
        the boundary a rule may name, and splits the stress mark off the
        nucleus it belongs to. A rule unit carries its own prosody."""
        units = run(monkeypatch, capsys, "rules", "units", "bˈʌ.tɚ")
        tokens = run(monkeypatch, capsys, "convert", "tokenize", "bˈʌ.tɚ")
        assert units[1] == "b ˈʌ . t ɚ\n"
        assert tokens[1] == "b ˈ ʌ t ɚ\n"

    def test_a_word_mark_is_a_unit_too(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "units", "kæt#dɒɡ")
        assert rc == 0
        assert out == "k æ t # d ɒ ɡ\n"

    def test_json_says_which_boundary_is_transparent(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "units", "kæt.#dɒɡ", "-j")
        assert rc == 0
        marks = {
            u["text"]: (u["level"], u["transparent"])
            for u in json.loads(out)[0]["units"]
            if u["boundary"]
        }
        # The dot is optional annotation and stepped over; the word mark is
        # a real edge and blocks a context.
        assert marks == {".": ("syllable", True), "#": ("word", False)}

    def test_one_line_per_form(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "units", "kæt", "bˈʌ.tɚ")
        assert rc == 0
        assert out.splitlines() == ["k æ t", "b ˈʌ . t ɚ"]


class TestListingTheShippedRuleSets:
    def test_it_names_the_shipped_sets(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "list")
        assert rc == 0
        assert out.splitlines() == [
            "american-english",
            "french-liaison",
            "german-final-devoicing",
            "japanese-moraic",
            "spanish-accented-english",
        ]

    def test_naming_a_set_lists_its_rules_in_order(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "list", "american-english")
        assert rc == 0
        lines = out.splitlines()
        assert lines[0].startswith("american-english: ")
        assert lines[0].endswith(" rules")
        assert "; tapping" in lines[1]
        assert "; aspiration" in lines[2]

    def test_every_listed_line_is_what_apply_takes_back(self, monkeypatch, capsys):
        """The listing is advertised as copy-pasteable, so every line of it
        must parse as a rule on its own."""
        listing = json.loads(
            run(monkeypatch, capsys, "rules", "list", "american-english", "-j")[1]
        )
        assert len(listing["rules"]) > 5, "listing did not run"
        for rule in listing["rules"]:
            rc, _, err = run(
                monkeypatch, capsys, "rules", "apply", "-r", rule["source"], "kæt"
            )
            assert rc == 0, f"{rule['source']!r}: {err}"

    def test_a_file_is_listed_by_its_stem(self, monkeypatch, capsys, tmp_path):
        path = tmp_path / "mine.rules"
        path.write_text(f"{GLOTTAL}\n", encoding="utf-8")
        rc, out, _ = run(monkeypatch, capsys, "rules", "list", "--file", str(path))
        assert rc == 0
        assert out.splitlines() == ["mine: 1 rule", f"  1  {GLOTTAL}"]

    def test_json_is_the_names(self, monkeypatch, capsys):
        rc, out, _ = run(monkeypatch, capsys, "rules", "list", "-j")
        assert rc == 0
        assert json.loads(out) == [
            "american-english",
            "french-liaison",
            "german-final-devoicing",
            "japanese-moraic",
            "spanish-accented-english",
        ]


class TestAMalformedRuleIsAnErrorNotATraceback:
    @pytest.mark.parametrize(
        "spec, because",
        [
            ("oops", "arrow"),
            ("-> ʔ", "left of the arrow"),
            ("t ->", "right of the arrow"),
            ("t -> ʔ / #", "'_'"),
            ("# -> ʔ / a _", "boundary"),
            ("[mannr=plosive] -> ʔ", "undeclared"),
        ],
    )
    def test_it_says_what_is_wrong(self, monkeypatch, capsys, spec, because):
        rc, out, err = run(monkeypatch, capsys, "rules", "apply", "-r", spec, "kæt")
        assert rc == 1
        assert err.startswith("Error: ")
        assert because in err
        assert "Traceback" not in err
        assert out == ""

    def test_a_rule_beginning_with_a_hash_is_refused_not_silently_dropped(
        self, monkeypatch, capsys
    ):
        """A rule file treats a leading '#' as a comment. A rule handed to
        -r must not be swallowed the same way: it is a rule that cannot
        work, and saying so beats applying nothing and reporting success."""
        rc, out, err = run(
            monkeypatch, capsys, "rules", "apply", "-r", "# -> ʔ / a _", "kæt"
        )
        assert rc == 1
        assert "boundary" in err
        assert out == ""

    def test_an_unknown_shipped_set_names_the_ones_there_are(self, monkeypatch, capsys):
        rc, _, err = run(monkeypatch, capsys, "rules", "apply", "-s", "klingon", "kæt")
        assert rc == 1
        assert "klingon" in err and "american-english" in err

    def test_a_missing_rule_file_reads_like_a_rule_problem(
        self, monkeypatch, capsys, tmp_path
    ):
        missing = tmp_path / "absent.rules"
        rc, _, err = run(
            monkeypatch, capsys, "rules", "apply", "--file", str(missing), "kæt"
        )
        assert rc == 1
        assert err.startswith("Error: no rule file")
        assert "Errno" not in err

    @pytest.mark.parametrize(
        "argv",
        [
            ("rules", "apply", "kæt"),
            ("rules", "apply", "-r", "t -> ʔ", "-s", "american-english", "kæt"),
            ("rules", "trace", "kæt"),
            ("rules", "recognize", "kæt"),
        ],
    )
    def test_exactly_one_source_of_rules_is_required(self, monkeypatch, capsys, argv):
        rc, _, err = run(monkeypatch, capsys, *argv)
        assert rc == 1
        assert "exactly one source of rules" in err

    def test_no_forms_and_empty_stdin_is_an_error(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        rc, _, err = run(
            monkeypatch, capsys, "rules", "apply", "-s", "american-english"
        )
        assert rc == 1
        assert "no forms" in err

    def test_a_set_and_a_file_together_is_refused_in_list(self, monkeypatch, capsys):
        rc, _, err = run(
            monkeypatch,
            capsys,
            "rules",
            "list",
            "american-english",
            "--file",
            "/nonexistent.rules",
        )
        assert rc == 1
        assert "not both" in err


# --------------------------------------------------------------------------
# Input that could not be read in full (ipakit.cli.policy)
# --------------------------------------------------------------------------


#: One invocation per surface that soft-reads IPA, found by running every
#: leaf command against input holding an unregistered symbol. These are the
#: ones that drop it, print an answer derived from the remainder, and used
#: to report success. The list is the survey, kept here so a new soft-read
#: path added to the CLI without a line here is a visible omission.
LOSSY_INVOCATIONS = [
    ("features", "k@t"),
    ("describe", "@"),
    ("convert", "tokenize", "k@t"),
    ("rules", "apply", "-r", GLOTTAL, "k@t"),
    ("rules", "trace", "-r", GLOTTAL, "k@t"),
    ("rules", "recognize", "-r", GLOTTAL, "k@t"),
    ("rules", "units", "k@t"),
    ("distance", "segment", "k@t", "kæt"),
    ("distance", "matrix", "p", "@"),
    ("distance", "word", "k@t", "kæd"),
    ("distance", "word", "k@t", "kæd", "--raw"),
    # The converters. They collected what they could not convert and spoke
    # about it only under their own --strict, so every one of these printed
    # a well-formed answer short of a symbol and exited 0 -- the defect the
    # parser's warning exists to prevent, one module over. They report now
    # (ipakit._convert.report_unconvertible) and so reach this policy with
    # no change to the command line.
    ("convert", "to-cmu", "k@t"),
    ("convert", "to-xsampa", "k@t"),
    ("convert", "to-timit", "k@t"),
    ("convert", "to-kirshenbaum", "k@t"),
    ("convert", "to-ipa", "K", "AE1", "QQ", "T"),
    ("convert", "from-timit", "k", "q9", "t"),
]

#: The counterparts with nothing dropped. Same commands, house-style input.
CLEAN_INVOCATIONS = [
    ("features", "kæt"),
    ("describe", "p"),
    ("convert", "tokenize", "kæt"),
    ("rules", "apply", "-r", GLOTTAL, "kæt"),
    ("rules", "trace", "-r", GLOTTAL, "kæt"),
    ("rules", "recognize", "-r", GLOTTAL, "kæt"),
    ("rules", "units", "kæt"),
    ("distance", "segment", "kæt", "kæt"),
    ("distance", "matrix", "p", "b"),
    ("distance", "word", "kæt", "kæd"),
    ("distance", "word", "kæt", "kæd", "--raw"),
    ("convert", "to-cmu", "kæt"),
    ("convert", "to-xsampa", "kæt"),
    ("convert", "to-timit", "kæt"),
    ("convert", "to-kirshenbaum", "kæt"),
    ("convert", "to-ipa", "K", "AE1", "T"),
    ("convert", "from-timit", "k", "ae", "t"),
]


class TestInputThatWasNotReadInFullReachesTheExitStatus:
    """A warning is audible to a person and invisible to a build.

    The library drops what it cannot register and says so, which is
    settled policy (docs/ties.md). What was missing is that the CLI
    called it a success, so nothing downstream of stdout could tell an
    answer derived from the input from one derived from part of it.
    """

    def test_the_briefed_case_no_longer_reports_success(self, monkeypatch, capsys):
        rc, out, err = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL, "k@t")
        assert out == "kʔ\n", "the derived form must not change"
        assert rc == LOSSY == 3
        lines = err.splitlines()
        # The first line is the library's own message, quoted rather than
        # rewritten: it names what was lost, which is the load-bearing part.
        assert lines[0].startswith(
            "ipakit: warning: dropped 1 unregistered symbol(s) ['@']"
        )
        assert lines[1] == (
            "ipakit: input was not read in full; exiting 3. Rerun as "
            "'ipakit --lax ...' to accept the lossy read and exit 0."
        )
        assert len(lines) == 2

    def test_the_sweep_covers_more_than_the_group_it_was_reported_against(self):
        """The policy is the whole CLI, so the evidence has to be too."""
        groups = {argv[0] for argv in LOSSY_INVOCATIONS}
        assert len(LOSSY_INVOCATIONS) >= 10, "sweep did not run"
        assert groups >= {"features", "describe", "convert", "rules", "distance"}
        assert len(LOSSY_INVOCATIONS) == len(CLEAN_INVOCATIONS)

    def test_the_sweep_covers_every_converter_that_reads_and_drops(self):
        """The six that used to be silent, named so a regression to
        silence is a failing test rather than a missing line."""
        converters = {argv[1] for argv in LOSSY_INVOCATIONS if argv[0] == "convert"}
        assert converters >= {
            "to-cmu",
            "to-xsampa",
            "to-timit",
            "to-kirshenbaum",
            "to-ipa",
            "from-timit",
        }

    @pytest.mark.parametrize(
        "argv", LOSSY_INVOCATIONS, ids=[" ".join(a) for a in LOSSY_INVOCATIONS]
    )
    def test_every_soft_read_surface_answers_the_same_way(
        self, monkeypatch, capsys, argv
    ):
        rc, out, err = run(monkeypatch, capsys, *argv)
        assert rc == LOSSY
        assert out.strip(), "the answer is still printed; only the status moved"
        # Two wordings, one shape: the parser drops what it cannot
        # *register*, the converters drop what they cannot *convert*.
        # Both name the symbols and say the result is short.
        assert "unregistered symbol" in err or "unconvertible symbol" in err

    @pytest.mark.parametrize(
        "argv", CLEAN_INVOCATIONS, ids=[" ".join(a) for a in CLEAN_INVOCATIONS]
    )
    def test_house_style_input_is_untouched_by_the_policy(
        self, monkeypatch, capsys, argv
    ):
        rc, _, err = run(monkeypatch, capsys, *argv)
        assert rc == 0
        assert err == ""

    @pytest.mark.parametrize(
        "argv",
        [
            ("--lax", "rules", "apply", "-r", GLOTTAL, "k@t"),
            ("rules", "apply", "-r", GLOTTAL, "k@t", "--lax"),
        ],
        ids=["before the subcommand", "on the leaf"],
    )
    def test_lax_accepts_the_lossy_read_wherever_it_is_written(
        self, monkeypatch, capsys, argv
    ):
        """A reader of the hint types the flag where it falls naturally,
        and a subparser default must not silently undo the global one."""
        rc, out, err = run(monkeypatch, capsys, *argv)
        assert (rc, out) == (0, "kʔ\n")
        assert "unregistered symbol" in err, "--lax quiets the status, not the report"
        assert "exiting 3" not in err

    def test_a_command_that_failed_keeps_its_own_status(self, monkeypatch, capsys):
        """'@' alone is both lossy and unknown. The specific failure wins:
        promoting 1 to 3 would tell the caller the run merely lost input."""
        rc, _, err = run(monkeypatch, capsys, "features", "@")
        assert rc == 1
        assert err.startswith("Error: Unknown phone: @")

    def test_the_status_is_written_down_where_a_caller_will_look(
        self, monkeypatch, capsys
    ):
        """A status nobody documents is a status nobody checks, and a number
        quoted in prose goes stale in silence. The help text is compared
        against the constant rather than trusted to still agree with it."""
        with pytest.raises(SystemExit):
            run(monkeypatch, capsys, "--help")
        out = capsys.readouterr().out
        assert f"  {LOSSY}  ran, but part of the input could not be read" in out
        assert "--lax reports 0 instead" in out

    def test_repeated_losses_are_folded_with_their_count(self, monkeypatch, capsys):
        """Python's warning registry deduplicates by source line, so three
        malformed lines used to report the first and stay silent about the
        rest -- 'audible' was not true per form. The count restores it
        without printing one line per form of a long pipeline."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("k@t\nk@t\nk@t\n"))
        rc, out, err = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL)
        assert rc == LOSSY
        assert out.splitlines() == ["kʔ", "kʔ", "kʔ"]
        warned = [line for line in err.splitlines() if "warning:" in line]
        assert len(warned) == 1
        assert warned[0].endswith("[3 times]")

    def test_the_report_names_the_input_and_not_the_install(self, monkeypatch, capsys):
        """The interpreter's handler writes an absolute path, a line number
        and the source line of features.py -- three things that vary by
        install and none of which name what was dropped."""
        _, _, err = run(monkeypatch, capsys, "rules", "apply", "-r", GLOTTAL, "k@t")
        assert all(line.startswith("ipakit: ") for line in err.splitlines())
        assert "features.py" not in err
        assert "UserWarning" not in err

    def test_the_converters_no_longer_drop_in_silence(self, monkeypatch, capsys):
        """This assertion used to run the other way.

        It pinned ``convert to-cmu k@t`` at ``(0, 'K T\\n', '')`` and said
        so deliberately: the converters collected what they could not
        convert and spoke only under their own --strict, so there was no
        report for the exit status to be derived from. Its docstring named
        the condition for promotion -- "if this starts failing, that path
        grew a report and belongs in LOSSY_INVOCATIONS" -- which is what
        happened. Kept as the same case, inverted, so the history of the
        gap stays attached to the thing that closed it.
        """
        rc, out, err = run(monkeypatch, capsys, "convert", "to-cmu", "k@t")
        assert out == "K T\n", "the conversion itself must not change"
        assert rc == LOSSY
        # In the tokenizer's voice rather than the converter's: `to-cmu`
        # reads its input through `segments`, so a character the
        # inventory does not register is reported by the layer that
        # could not read it, and the converter speaks only for what the
        # ARPABET table has no row for. Either way it is audible and
        # either way it reaches the exit status, which is the claim.
        assert "unregistered symbol(s) ['@']" in err

    def test_the_guard_states_what_it_cannot_see(self, monkeypatch, capsys):
        """A symbol the *target* notation has is not a loss.

        ``@`` is X-SAMPA and Kirshenbaum for schwa, so reading it in that
        direction converts rather than drops, and these stay 0. The
        policy sees losses, not unusual characters; if one of these
        starts exiting 3, a conversion that used to succeed has stopped.
        """
        for argv in [
            ("convert", "from-xsampa", "k@t"),
            ("convert", "from-kirshenbaum", "k@t"),
        ]:
            rc, out, err = run(monkeypatch, capsys, *argv)
            assert (rc, out, err) == (0, "kət\n", ""), argv


# --------------------------------------------------------------------------
# What the library offers and the command line does not
# --------------------------------------------------------------------------

#: Names the CLI reaches a read through, rather than by its public name.
_SINGLETON_ACCESSORS = {"_get_ipa", "_get_cmu", "_get_default_model"}


def _delegates(node):
    """The names a top-level function hands the actual work to.

    Almost every function in ``ipakit/__init__.py`` is a one-line
    delegation -- ``_get_ipa().describe(...)``, ``_get_cmu().ipa_to_cmu(...)``,
    ``RuleSet.parse(...)`` -- and the CLI calls those same methods on its
    own ``self.ipa`` / ``self.cmu``. The delegate is therefore the token
    the two surfaces share, and comparing delegates is what lets this be
    computed instead of listed.
    """
    found = set()
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Call)
            and isinstance(sub.value.func, ast.Name)
            and sub.value.func.id in _SINGLETON_ACCESSORS
        ):
            found.add(sub.attr)
        elif isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name):
                found.add(sub.func.id)
            elif isinstance(sub.func, ast.Attribute) and isinstance(
                sub.func.value, ast.Name
            ):
                found.add(sub.func.attr)
    return found


def _cli_vocabulary():
    """Every identifier the CLI package actually references.

    Read from the AST, not the text: a name occurring only in a docstring
    or a help string is prose *about* the library, not a call into it.
    ``ipakit/cli/distance.py`` names ``ipakit.word_similarity()`` in its
    help exactly so a reader knows what --raw computes, and that must not
    make the function count as spelled.
    """
    vocabulary = set()
    for path in sorted((ROOT / "ipakit" / "cli").glob("*.py")):
        for sub in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(sub, ast.Attribute):
                vocabulary.add(sub.attr)
            elif isinstance(sub, ast.Name):
                vocabulary.add(sub.id)
            elif isinstance(sub, ast.alias):
                vocabulary.add(sub.name.split(".")[-1])
                if sub.asname:
                    vocabulary.add(sub.asname)
    return vocabulary


def _library_only_functions():
    """Public functions no CLI command calls, by the predicate above."""
    tree = ast.parse((ROOT / "ipakit" / "__init__.py").read_text(encoding="utf-8"))
    defined = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    vocabulary = _cli_vocabulary()
    unreachable = set()
    for name in ipakit.__all__:
        obj = getattr(ipakit, name)
        if not inspect.isfunction(obj):
            continue
        # The public name, the object's own name (they differ whenever a
        # public name is bound to a function defined under another), and
        # whatever it delegates to.
        spellings = {name, obj.__name__}
        if name in defined:
            spellings |= _delegates(defined[name])
        if not spellings & vocabulary:
            unreachable.add(name)
    return unreachable


#: Public functions that are deliberately library-only, each with the
#: reason it has no command-line spelling. Asserted as an exact set: a new
#: public function is either reachable from the CLI or named here, so
#: adding one forces the decision instead of quietly widening the gap that
#: this lane was opened to close.
LIBRARY_ONLY = {
    # Take or return Python objects a command line cannot hold.
    "to_ipa": "takes a list of Segment objects",
    "import_phoneset": "takes and returns a Phoneset",
    "levels": "returns the boundary ladder, outermost first",
    "tier_names": "the vocabulary an Interval is checked against; 'features' prints it",
    "rebase": "takes Interval and Edit objects; an interval is not spelled",
    "feature_values": "returns per-feature value tuples, not a flat bundle",
    "feature_bundles": "returns one dict per segment; 'features' prints that",
    # Generic over a phonemap name; the CLI ships a subcommand per map
    # instead (to-timit, to-kirshenbaum, from-timit, ...).
    "ipa_to_phonemap": "generic; the CLI spells one subcommand per map",
    "phonemap_to_ipa": "generic; the CLI spells one subcommand per map",
    # A second spelling of a number the CLI already prints another way.
    "word_similarity": "'distance word --raw' prints this value via word_distance",
    "sequence_similarity": "the similarity of sequence_distance, which 'distance seq' spells",
    "rank_sequences": "the n-best over a set of pre-tokenized sequences; the CLI compares one sequence to one, not a set",
    # Exists to take a per-phone cost schedule, which is a mapping a
    # command line cannot hold; with flat costs it is 'distance word'.
    "directional_word_distance": "takes a CostSchedule; flat, it is 'distance word'",
    "is_valid_ipa": "'analysis validate' prints the issues, not the boolean",
    "is_pure_ipa": "the yes/no over extensions_in; neither is on the CLI",
    "extensions_in": "no CLI surface for the IPA-chart/extension split",
    "segmented": "'convert tokenize' prints the same units",
    # Supplements are a Python-level facility by design: the command line
    # reads the shipped inventory only, so neither the names nor the paths
    # of the shipped supplements have anything to say there.
    "available_supplements": "the CLI reads the shipped inventory only",
    "supplement_path": "the CLI reads the shipped inventory only",
    # Reads with no command yet. Not defended -- recorded, so the absence
    # is a known gap rather than an unnoticed one.
    "find": "no command runs a feature query over a transcription",
    "respell": "no command applies a feature change to a phone",
    "to_phone": "no command realizes a feature bundle as a symbol",
    "from_wild": "no command imports wild-convention text",
}


class TestEveryPublicReadIsEitherOnTheCommandLineOrDeclaredLibraryOnly:
    """The guard this lane exists to leave behind.

    Eight API/CLI divergences were found by hand. Finding them by hand
    again next release is the failure mode; so the question is asked as a
    predicate over the code -- which public functions does no CLI command
    call? -- and only the *answer* is written down. A hand-maintained
    list of today's offenders would document the present
    (docs/reviewing.md); this describes the shape and lets the set be the
    assertion.

    Equality, not containment, is what makes it work in both directions:
    a new public function with no CLI spelling fails until it is either
    given one or declared here, and giving a declared name a CLI spelling
    fails until it is removed from the declaration.
    """

    def test_the_sweep_is_not_vacuous(self):
        public = [n for n in ipakit.__all__ if inspect.isfunction(getattr(ipakit, n))]
        assert len(public) > 50, f"only {len(public)} public functions found"
        assert _cli_vocabulary() > {"describe", "distance", "tokenize"}

    def test_the_library_only_set_is_exactly_what_is_declared(self):
        measured = _library_only_functions()
        declared = set(LIBRARY_ONLY)
        assert measured == declared, (
            f"no longer library-only: {sorted(declared - measured)}; "
            f"newly library-only: {sorted(measured - declared)}. "
            "Either give it a CLI spelling or declare it in LIBRARY_ONLY "
            "with the reason."
        )

    def test_every_declared_reason_says_something(self):
        """A set with empty reasons is a list again."""
        assert all(len(reason) > 20 for reason in LIBRARY_ONLY.values())

    def test_the_flagship_reads_are_on_both_surfaces(self):
        """The named entry points from the audit, asserted by the same
        predicate rather than by trusting the set above to be complete."""
        for name in ("ruleset", "shipped", "available", "units", "hierarchy"):
            assert name in ipakit.__all__, name
            assert name not in LIBRARY_ONLY, name

    def test_the_guard_states_what_it_cannot_see(self):
        """Functions only.

        Classes (Segment, Phoneset), constants (DATA_DIR) and re-exported
        types are exports of the *representation*, not reads with an
        answer a command could print, so the reachability question does
        not apply to them and they are outside this guard. If that ever
        stops being true -- if a class gains a CLI spelling that ought to
        track -- this states the limit that has to be revisited.
        """
        nonfunctions = {
            n for n in ipakit.__all__ if not inspect.isfunction(getattr(ipakit, n))
        }
        assert nonfunctions & {"Segment", "Phoneset", "DATA_DIR", "RuleSet"}
        assert not (nonfunctions & set(LIBRARY_ONLY))

    def test_the_guard_tracks_the_read_and_not_the_name(self):
        """The second limit, measured rather than assumed.

        Reachability is asked of what a function *delegates to*, so a new
        public name wrapping a method some command already calls counts
        as reachable and does not force a decision. That is the intended
        reading -- the read is on both surfaces, only the spelling is new
        -- but it means this guard does not catch a divergence in
        *naming*, only one in coverage: a second public name for a read
        the CLI already spells would pass without comment.
        """
        assert "units" not in LIBRARY_ONLY
        # A wrapper around an already-spelled delegate is reachable.
        wrapper = ast.parse("def w(x):\n    return _get_ipa().normalize(x)\n").body[0]
        assert _delegates(wrapper) & _cli_vocabulary()


class TestTheDeliberateApiCliDifferences:
    """Two places the two surfaces answer differently on purpose.

    Both were audited as candidate defects and kept. A difference that is
    deliberate still goes stale, and an undefended one is indistinguishable
    from a bug next time somebody looks, so each is pinned with the reason
    it survives.
    """

    def test_the_features_default_is_inverted_and_documented(self, monkeypatch, capsys):
        """The CLI shows stated features and --all adds the defaults; the
        API returns everything and with_defaults=False strips it.

        Kept because the two surfaces are for different things: a terminal
        read of /p/ wants the four lines that say something, and a caller
        comparing bundles wants the full vector with no key missing.
        docs/tutorial.md states it in those words and quotes both counts,
        so this asserts the numbers the page quotes, not numbers of its own.
        """
        assert len(ipakit.features("p")) == 23
        assert len(ipakit.features("p", with_defaults=False)) == 4

        # The CLI's line counts are not the API's key counts and are not
        # asserted as if they were: it prints 'name', prints 'class', and
        # drops 'href' (metadata, not a declared feature), so the default
        # read is name + class + the two stated features, and --all adds
        # the 19 defaults. That --all lands on 23 lines as well is a
        # coincidence of two different compositions, not the same 23.
        rc, out, _ = run(monkeypatch, capsys, "features", "p")
        assert rc == 0
        assert out.strip().splitlines() == [
            "name: p",
            "class: phone",
            "manner: plosive",
            "place: bilabial",
        ]
        rc, out_all, _ = run(monkeypatch, capsys, "features", "p", "--all")
        assert rc == 0
        assert len(out_all.strip().splitlines()) == 23
        assert "href" not in out_all
        assert set(out.strip().splitlines()) < set(out_all.strip().splitlines())

        page = (ROOT / "docs" / "tutorial.md").read_text(encoding="utf-8")
        assert "give 4 keys and 23 keys respectively" in page, (
            "the tutorial no longer states the inversion this pins; either "
            "the difference stopped being deliberate or the page went stale"
        )

    def test_the_class_the_cli_prints_is_the_class_the_data_declares(
        self, monkeypatch, capsys
    ):
        """This one was a defect, and is fixed; the assertion stays.

        'class' is set from the name of the element that declared the
        symbol, so its values are phone / diacritic / suprasegmental /
        separator. The CLI used to overwrite it with 'composed' -- a value
        nothing in the data can produce -- for any token that was not
        itself a registry key, so the two surfaces disagreed about a
        declared metadata field. Composedness is a property of the
        spelling, and now prints under its own key.
        """
        declared = {"phone", "diacritic", "suprasegmental", "separator"}
        rc, out, _ = run(monkeypatch, capsys, "features", "pʰ", "-j")
        assert rc == 0
        entry = json.loads(out)
        assert entry["class"] == ipakit.features("pʰ")["class"] == "phone"
        assert entry["class"] in declared
        assert entry["composed"] is True
        # A registered symbol is not composed, and says nothing about it.
        rc, out, _ = run(monkeypatch, capsys, "features", "t͡ʃ", "-j")
        assert "composed" not in json.loads(out)

    def test_both_word_measures_have_a_command_line_spelling(self, monkeypatch, capsys):
        """'distance word' is the inventory-relative measure and 'pair' is
        the raw one, which left the API's word_distance with no CLI
        spelling at all -- so the two surfaces looked like they disagreed
        (0.9864 against 0.9833) where they were computing different
        things. --raw is the missing spelling.

        The model figure is a percentile in the shipped distribution and
        moves when that distribution does, so both figures are derived
        rather than written out here. It was written out, and it moved:
        declaring a constriction location on three vowels shifted the
        distribution enough to take it from 0.9864 to 0.9863 without any
        pair in this word moving at all. What the test is for is that the
        two spellings exist and stay distinguishable, and a literal was
        never part of that.
        """
        rc, model_out, _ = run(monkeypatch, capsys, "distance", "word", "kæt", "kæd")
        modelled = ipakit.distance_model().word_distance("kæt", "kæd")
        assert rc == 0 and f"{modelled.similarity:.4f}" in model_out

        rc, raw_out, _ = run(
            monkeypatch, capsys, "distance", "word", "kæt", "kæd", "--raw"
        )
        assert rc == 0
        expected = ipakit.word_similarity("kæt", "kæd")
        assert f"{expected:.4f}" in raw_out
        assert model_out != raw_out, "the two measures must stay distinguishable"

    def test_the_docs_claim_about_strict_word_measures_does_not_cover_the_model(self):
        """A documented invariant that does not hold. Pinned, not fixed.

        docs/ties.md says word_distance/word_similarity "already reject
        lossy input at the measurement layer with strict=True as *their*
        default". That is true of ipakit.word_distance and of
        IPAFeatures.word_distance -- and not of
        DistanceModel.word_distance, which is the one 'ipakit distance
        word' calls and which has no strict parameter at all. It reads
        softly, warns, and answers.

        The CLI is covered either way: the warning reaches the exit status
        as 3 (see LOSSY_INVOCATIONS). What is not covered is a caller
        using DistanceModel directly on the strength of that sentence.
        Changing the default is a DistanceModel decision, not this lane's,
        so the state of affairs is asserted instead of assumed -- when the
        method grows a strict= this fails, and the doc becomes true.
        """
        import inspect as _inspect

        from ipakit.distance_model import DistanceModel

        model_sig = _inspect.signature(DistanceModel.word_distance)
        assert "strict" not in model_sig.parameters, (
            "DistanceModel.word_distance grew a strict parameter; "
            "docs/ties.md's claim may now hold -- check its default and "
            "update this test and the doc together"
        )
        assert ipakit.word_distance.__defaults__ is not None
        flat_sig = _inspect.signature(ipakit.word_distance)
        assert flat_sig.parameters["strict"].default is True

        # The measurable consequence: the model measures over what
        # survived tokenization; the flat function refuses to measure.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            assert ipakit.distance_model().word_distance("k@t", "kæt").similarity > 0
        with pytest.raises(ValueError):
            ipakit.word_distance("k@t", "kæt")

        claim = "reject lossy input at the measurement layer"
        assert claim in (ROOT / "docs" / "ties.md").read_text(encoding="utf-8"), (
            "docs/ties.md no longer makes the claim this test scopes; "
            "if it was corrected, this test can go"
        )


class TestTheLossyReadGuardIsWrittenAsAPredicate:
    """It asks what a warning *is*, not whether it is one of today's four.

    A fifth report added to the library is covered without this lane
    being touched, and a warning that says nothing about the input
    cannot move the exit status.
    """

    @staticmethod
    def _entry(filename, category=UserWarning, text="dropped something"):
        return warnings.WarningMessage(category(text), category, filename, 1)

    def test_a_report_from_inside_the_package_counts(self):
        inside = ipakit.__file__
        assert input_reports([self._entry(inside)]) == ["dropped something"]

    def test_a_warning_from_outside_the_package_does_not(self):
        """A DeprecationWarning-shaped UserWarning from a dependency is not
        the caller's transcription being wrong."""
        assert input_reports([self._entry("/usr/lib/python3/site.py")]) == []

    def test_a_category_that_is_not_a_user_warning_does_not(self):
        assert input_reports([self._entry(ipakit.__file__, DeprecationWarning)]) == []

    def test_distinct_messages_are_all_kept(self):
        inside = ipakit.__file__
        assert input_reports(
            [self._entry(inside, text="a"), self._entry(inside, text="b")]
        ) == ["a", "b"]


# --------------------------------------------------------------------------
# Documented examples
# --------------------------------------------------------------------------


def _example_argv(line):
    """The argv of one 'ipakit rules ...' line, or None if it is not one.

    Tokenized with '#' left un-special, because a rule contains a quoted
    '#' as the word boundary; the trailing comment is the first token that
    *is* a bare '#'.
    """
    line = line.strip()
    if line.startswith("$ "):  # a console block in the docs
        line = line[2:]
    if not line.startswith(("ipakit rules ", "ipakit r ")):
        return None
    if "my.rules" in line:  # a placeholder path, not a file that exists
        return None
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    if "#" in tokens:
        tokens = tokens[: tokens.index("#")]
    argv = tokens[1:]
    if "..." in argv:  # a shape in a group listing, not a runnable example
        return None
    return argv


def _documented_examples():
    """Every CLI example this lane writes down, from the docs and the help."""
    from ipakit.cli import rules as rules_cli

    texts = [
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "docs" / "rules.md").read_text(encoding="utf-8"),
        ipakit.cli.__doc__ or "",
        rules_cli.__doc__ or "",
    ]
    texts += [
        obj.__doc__ or ""
        for obj in vars(rules_cli).values()
        if isinstance(obj, type) and obj.__module__ == rules_cli.__name__
    ]
    found = []
    for text in texts:
        for line in text.splitlines():
            argv = _example_argv(line)
            if argv:
                found.append(argv)
    return found


DOCUMENTED_EXAMPLES = _documented_examples()


class TestEveryDocumentedRulesExampleRuns:
    """A documented command that does not work is worse than none.

    This sweep asserts only that each example exits 0 and prints something
    -- it does not read the '#' comment beside it as an expected value.
    The drift-prone values (pˈɪn -> pʰˈɪ̃n, the trace layout, the unit
    split) are pinned exactly in the classes above instead.
    """

    def test_the_sweep_is_not_vacuous(self):
        assert len(DOCUMENTED_EXAMPLES) >= 20, (
            f"only {len(DOCUMENTED_EXAMPLES)} examples harvested; the "
            "docs or the help text moved and this sweep stopped covering them"
        )

    @pytest.mark.parametrize(
        "argv", DOCUMENTED_EXAMPLES, ids=[" ".join(a) for a in DOCUMENTED_EXAMPLES]
    )
    def test_the_example_runs(self, monkeypatch, capsys, argv):
        rc, out, err = run(monkeypatch, capsys, *argv)
        assert rc == 0, err
        assert out.strip(), "an example that prints nothing documents nothing"


def _console_blocks(path):
    """Every ``$ command`` / output pair in a document's console blocks."""
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```console\n(.*?)```", text, re.S):
        lines = block.splitlines()
        index = 0
        while index < len(lines):
            assert lines[index].startswith("$ "), lines[index]
            command = lines[index][2:]
            index += 1
            expected = []
            while index < len(lines) and not lines[index].startswith("$ "):
                expected.append(lines[index])
                index += 1
            yield command, expected


#: Every ``$ ipakit ...`` block in every document, not just the rules page.
#: Scoped to one file it only ever guarded the page the lane that wrote it
#: happened to own; the same staleness is possible on any page, and a
#: document added later is covered without this line being touched.
#:
#: ``docs/tutorial.md`` is skipped: it is a *derived* artifact, rebuilt by
#: ``scripts/tutorial.py build`` and already compared byte for byte by
#: ``scripts/tutorial.py check`` in ``make check``. Replaying it here would
#: be a second, weaker check of the same thing, and one that disagrees when
#: the generator's normalization differs from ``run()``'s capture.
DOC_CONSOLE = [
    (command, expected)
    for path in sorted(ROOT.glob("docs/*.md"))
    if path.name != "tutorial.md"
    for command, expected in _console_blocks(path)
    if command.startswith(("ipakit ", "printf "))
]


class TestTheDocsQuoteRealOutput:
    """The docs show output, and quoted output goes stale in silence.

    Every console block under docs/ is replayed and compared line for
    line, so a change in what the CLI prints fails the suite instead of
    leaving the document wrong.
    """

    def test_the_sweep_is_not_vacuous(self):
        assert len(DOC_CONSOLE) >= 7, f"only {len(DOC_CONSOLE)} blocks found"

    def test_the_guard_states_what_it_cannot_see(self):
        """The glob is wider than the docs are, today.

        It was rules.md alone, and the breadth this sweep gained over the
        hardcoded path was then covered by construction rather than by a
        page it presently caught. calculus.md is that second page, so the
        breadth is now demonstrated rather than argued: a stale console
        block on it fails here, and would not have before this widened.
        (tutorial.md is derived and compared byte for byte by
        ``scripts/tutorial.py check`` instead.)

        The same response holds for a third page: note that the sweep
        demonstrably reaches it, and widen.
        """
        pages = {
            path.name
            for path in sorted(ROOT.glob("docs/*.md"))
            if path.name != "tutorial.md"
            and any(
                command.startswith(("ipakit ", "printf "))
                for command, _ in _console_blocks(path)
            )
        }
        assert pages == {
            "rules.md",
            "calculus.md",
        }, f"{pages} now contribute console blocks"

    @pytest.mark.parametrize(
        "command, expected", DOC_CONSOLE, ids=[c for c, _ in DOC_CONSOLE]
    )
    def test_the_block_prints_what_it_says(
        self, monkeypatch, capsys, command, expected
    ):
        if command.startswith("printf "):
            producer, _, invocation = command.partition(" | ")
            piped = shlex.split(producer)[1].replace("\\n", "\n")
            monkeypatch.setattr(sys, "stdin", io.StringIO(piped))
        else:
            invocation = command
        rc, out, err = run(monkeypatch, capsys, *shlex.split(invocation)[1:])
        assert rc == 0, err
        assert out.splitlines() == expected
