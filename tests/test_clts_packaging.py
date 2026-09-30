"""CLTS data/credit travel in both distributions; frozen runtime is offline."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import tiergraph
from tests.test_packaging import built_wheel as built_wheel
from tests.test_packaging import package_source as package_source


def test_core_snapshot_and_credit_are_in_actual_wheel(built_wheel: Path) -> None:
    with zipfile.ZipFile(built_wheel) as archive:
        assert {
            "ipakit/data/clts/core.json",
            "ipakit/data/clts/source.json",
            "ipakit/data/clts/manifest.json",
            "ipakit/data/clts/semantic-mapping.json",
            "ipakit/data/clts/import-result.schema.json",
            "ipakit/data/clts/NOTICE.txt",
            "ipakit/data/clts/MAPPING-NOTICE.txt",
        } <= set(archive.namelist())
        notice = archive.read("ipakit/data/clts/NOTICE.txt").decode()
        assert "CC BY 4.0" in notice and "Johann-Mattis List" in notice
        mapping_notice = archive.read("ipakit/data/clts/MAPPING-NOTICE.txt").decode()
        assert "features.json" in mapping_notice and "CC BY 4.0" in mapping_notice
        authority = json.loads(archive.read("ipakit/data/clts/semantic-mapping.json"))
        census = authority["census"]
        assert "catalog" not in census
        assert set(census["sources"]["clts"]) == {
            "pkg/transcriptionsystems/features.json"
        }
        assert all(
            set(row) == {"source", "status", "direction", "targets", "declared"}
            for row in census["clts_to_ipakit"]
        )


def test_actual_sdist_contains_artifact_and_notices_not_untracked(
    package_source: Path, tmp_path: Path
) -> None:
    untracked = package_source / "untracked"
    untracked.mkdir(exist_ok=True)
    (untracked / "must-not-ship.txt").write_text("private sentinel")
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools import build_meta; "
            + f"build_meta.build_sdist({str(tmp_path)!r})",
        ],
        cwd=package_source,
        check=True,
        capture_output=True,
    )
    archives = list(tmp_path.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        names = [member.name.partition("/")[2] for member in archive.getmembers()]
        assert {
            "ipakit/data/clts/core.json",
            "ipakit/data/clts/source.json",
            "ipakit/data/clts/manifest.json",
            "ipakit/data/clts/semantic-mapping.json",
            "ipakit/data/clts/import-result.schema.json",
            "ipakit/data/clts/NOTICE.txt",
            "ipakit/data/clts/MAPPING-NOTICE.txt",
        } <= set(names)
        assert not any(name.startswith("untracked/") for name in names)


def test_isolated_wheel_runtime_has_no_provider_or_checkout(
    built_wheel: Path, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as archive:
        archive.extractall(site)
    # The sole runtime dependency is copied, not the environment's site-packages.
    shutil.copytree(
        Path(tiergraph.__file__).parent,
        site / "tiergraph",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    program = """
import sys, importlib.util, json, socket, io, contextlib
from pathlib import Path
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('pyclts') is None
assert importlib.util.find_spec('panphon') is None
def no_network(*a, **kw):
    raise AssertionError('offline runtime attempted network')
socket.socket = no_network
import ipakit
import ipakit.cli
from ipakit.clts import load_import, read_snapshot
from ipakit.bridges.costmodel import set_feature_pack, compare_tokens, Segmentation
assert Path(ipakit.__file__).resolve().is_relative_to(Path(sys.argv[1]))
envelope_path = Path(sys.argv[2])
saved = load_import(envelope_path.read_text(encoding='utf-8'))
assert saved.status == 'complete'
assert saved.house_form().to_ipa() == 'pb'
tokens_path = Path(sys.argv[3])
tokens_path.write_text('["p","b"]', encoding='utf-8')
sys.argv = ['ipakit', 'clts', 'read', '--tokens-json', str(tokens_path)]
stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    assert ipakit.cli.main() == 0
assert stdout.getvalue() == saved.to_json() + '\\n'
sys.argv = ['ipakit', 'clts', 'emit', '--from-json', str(envelope_path), '--spelling', 'source']
stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    assert ipakit.cli.main() == 0
assert json.loads(stdout.getvalue())['tokens'] == ['p', 'b']
s = read_snapshot()
p = set_feature_pack(s.geometry)
row = compare_tokens(ipakit.load_ipa_features(), p, Segmentation(('a',)), Segmentation(('p',)))
assert s.similarity('ç', 'ç') == 1
print(json.dumps({'cost': row.edit_cost, 'identity': s.identity}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            program,
            str(site),
            str(Path(__file__).parent / "fixtures/clts_import/complete.json"),
            str(tmp_path / "tokens.json"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["cost"] == 1
