"""Binary-level gates for the form and directory-corpus CLI doors."""

import os
import subprocess
import sys
from pathlib import Path

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
