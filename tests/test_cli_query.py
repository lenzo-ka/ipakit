"""Binary-level gates for the form and directory-corpus CLI doors."""

import json
import os
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest

ROOT = Path(__file__).resolve().parent.parent


def invoke(*args, input=None, seed="0"):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": seed}
    return subprocess.run(
        [sys.executable, "-m", "ipakit.cli", *map(str, args)],
        cwd=ROOT,
        env=env,
        input=input,
        text=True,
        capture_output=True,
        check=False,
    )


def test_wild_and_exact_spellings_agree_and_echo_once():
    wild = invoke("query", "'a", "ˈa")
    exact = invoke("query", "find", "--exact", "ˈa", "ˈa")
    assert wild.returncode == exact.returncode == 0
    assert wild.stdout == exact.stdout
    assert wild.stderr == "query read as: ˈa\n"
    assert exact.stderr == "query read as: ˈa\n"


def test_exact_takes_the_literal_codepoints():
    result = invoke("query", "find", "--exact", "g", "ɡ")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.count("query read as:") == 1
    assert "spells nothing" in result.stderr


def test_wild_echo_normalizes_literals_only():
    result = invoke("query", "g{+voiced}", "ɡ")
    assert result.returncode == 0
    assert result.stderr == "query read as: ɡ{+voiced}\n"


def test_wild_feature_error_preserves_the_users_spelling():
    result = invoke("query", "[+high]", "ki")
    assert result.returncode == 1
    assert "'high'" in result.stderr
    assert "'hiɡh'" not in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ("query", "match", "plosive", "bilabial"),
        ("query", "list", "manner=plosive"),
        ("query", "features", "manner"),
        ("query", "classes"),
        ("query", "shorts", "plo"),
    ],
)
def test_every_inventory_query_subcommand_runs_through_the_binary(args):
    result = invoke(*args)
    assert result.returncode == 0
    assert result.stdout


def test_statuses_for_matches_empty_error_and_usage():
    assert invoke("query", "[nasal]", "an").returncode == 0
    empty = invoke("query", "[nasal]", "ata")
    assert (empty.returncode, empty.stdout) == (0, "")
    assert invoke("query", "*", "ata").returncode == 1
    assert invoke("query", "find").returncode == 2


def test_stdin_repeatable_files_and_columns_preserve_csv(tmp_path: Path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("an\n", encoding="utf-8")
    second.write_text("at\n", encoding="utf-8")
    repeated = invoke("query", "[nasal]", "-f", first, "-f", second)
    assert repeated.returncode == 0
    assert repeated.stdout.splitlines() == ["an\t/clock/1/segment/0\tn\t"]

    stdin = invoke("query", "[nasal]", input="an\nat\n")
    assert stdin.returncode == 0
    assert stdin.stdout.startswith("an\t")

    table = tmp_path / "forms.csv"
    raw = 'id,ipa,note\n1,an,"kept, verbatim"\n2,at,plain\n'
    table.write_text(raw, encoding="utf-8", newline="")
    by_name = invoke("query", "[nasal]", "-f", table, "--column", "ipa")
    by_number = invoke("query", "[nasal]", "-f", table, "--column", "2")
    assert by_name.stdout == by_number.stdout == "an\t/clock/1/segment/0\tn\t\n"
    filtered = invoke("query", "[nasal]", "-f", table, "--column", "ipa", "--filter")
    assert filtered.stdout == '1,an,"kept, verbatim"\n'


def test_filter_is_deduplicated_identity_and_pipes_compose():
    rows = "anna\nata\nana\n"
    records = invoke("query", "[nasal]", input=rows)
    identities = list(
        dict.fromkeys(line.split("\t", 1)[0] for line in records.stdout.splitlines())
    )
    filtered = invoke("query", "[nasal]", "--filter", input=rows)
    assert filtered.stdout.splitlines() == identities
    stage_one = invoke("query", "[nasal]", "--filter", input=rows)
    stage_two = invoke("query", "a / * _ #", "--filter", input=stage_one.stdout)
    assert stage_two.stdout == "anna\nana\n"


def test_formatter_is_byte_stable_across_hash_seeds():
    one = invoke("query", "n{place=α}", "nm", seed="0")
    two = invoke("query", "n{place=α}", "nm", seed="8675309")
    assert (one.returncode, one.stdout, one.stderr) == (
        two.returncode,
        two.stdout,
        two.stderr,
    )


def test_every_corpus_subcommand_runs_through_the_binary(tmp_path: Path):
    location = tmp_path / "speech"
    assert invoke("corpus", "init", location).returncode == 0
    assert (
        invoke("corpus", "add", "one", "anp", "-r", "broad", "-C", location).returncode
        == 0
    )
    assert (
        invoke("corpus", "add", "two", "amp", "-r", "narrow", "-C", location).returncode
        == 0
    )
    assert invoke("corpus", "validate", "-C", location).stdout == "valid\t2\n"
    assert invoke("corpus", "ids", "-C", location).stdout == "one\ntwo\n"
    assert invoke("corpus", "show", "one", "-C", location).stdout == "one\tbroad\tanp\n"
    queried = invoke("corpus", "query", "[nasal]", "-r", "broad", "-C", location)
    assert queried.returncode == 0 and queried.stdout.startswith("one\tbroad\t")
    derived = invoke(
        "corpus",
        "derives",
        "--rules",
        "american-english",
        "--source",
        "broad",
        "--target",
        "narrow",
        "-C",
        location,
    )
    assert derived.returncode == 0
    assert derived.stdout.startswith("summary\t")


def test_ingest_cmudict_reports_refusal_and_default_cited_query(tmp_path: Path):
    location = tmp_path / "cmudict"
    fixture = ROOT / "tests" / "fixtures" / "cmudict_excerpt.dict"
    assert invoke("corpus", "init", location).returncode == 0
    ingested = invoke("corpus", "ingest-cmudict", location, fixture)
    assert ingested.returncode == 1
    assert ingested.stdout == "summary\tadded=101\trefused=1\n"
    assert "refusal\t106\tunmappable\t" in ingested.stderr
    assert "ZZZ" in ingested.stderr

    queried = invoke("corpus", "query", "[+nasal] / _ #", "-C", location)
    assert queried.returncode == 0
    assert queried.stderr == "query read as: [+nasal] / _ #\n"
    assert any(line.startswith("tom\tcited\t") for line in queried.stdout.splitlines())

    derived = invoke(
        "corpus",
        "derives",
        "--rules",
        "american-english",
        "--source",
        "cited",
        "--target",
        "cited",
        "-C",
        location,
    )
    assert derived.returncode == 0
    assert derived.stdout.endswith("\n")


def test_rules_derives_writes_full_report_and_prints_summary(tmp_path: Path):
    location = tmp_path / "speech"
    report = tmp_path / "report.json"
    assert invoke("corpus", "init", location).returncode == 0
    assert (
        invoke("corpus", "add", "one", "anp", "-r", "broad", "-C", location).returncode
        == 0
    )
    assert (
        invoke("corpus", "add", "two", "amp", "-r", "narrow", "-C", location).returncode
        == 0
    )
    # Add replaces neither entry nor role, so make the pair through the API.
    stored = ipakit.corpus.open(location)
    stored.put_form("one", "narrow", ipakit.read("amp"))
    result = invoke(
        "rules",
        "derives",
        "-s",
        "experiment-demo",
        "--corpus",
        location,
        "--source",
        "broad",
        "--target",
        "narrow",
        "--report",
        report,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("coverage\t1/2\tderivable=1")
    assert json.loads(report.read_text())["type"] == "ipakit.experiment.report"
