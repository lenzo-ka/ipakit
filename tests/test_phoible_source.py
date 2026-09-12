"""Source-byte preservation is separate from house admission/refusal."""

import csv
import gzip
import hashlib
import io
import json
import subprocess
from pathlib import Path

import pytest
from ipakit import phoible_source
from ipakit.bridges.phoible import PHOIBLE_ENV, PhoibleBridge, PhoibleDataUnavailable
from ipakit.extraction import (
    SourceContentError,
    SourceMissingError,
    SourceVersionError,
    phoible,
)
from scripts import dev_sources


def test_shipped_source_census_and_refusals(monkeypatch):
    monkeypatch.delenv(PHOIBLE_ENV, raising=False)
    source = PhoibleBridge()
    assert source.root is None
    assert len(source._metadata) == 3020
    assert len(source.language("eng").inventories) == 9
    first = source.inventory(160)
    second = source.inventory(2175)
    assert (len(first.entries), len(first.refusals)) == (40, 9)
    assert (len(second.entries), len(second.refusals)) == (39, 0)
    assert first.provenance.bibtex_keys == (
        "OConner1973",
        "Gimson1962",
        "Halle1973",
        "Fudge1975",
        "Trnka1968",
    )
    rows = csv.DictReader(
        io.StringIO(phoible_source.read_source("data/phoible.csv").decode())
    )
    assert len(rows.fieldnames) == 49 and "lenis" in rows.fieldnames
    values = list(rows)
    assert len(values) == 105484
    assert {row["InventoryID"] for row in values} == set(source._metadata)
    assert {row["Marginal"] for row in values} == {"TRUE", "FALSE", "NA"}
    with pytest.raises(KeyError):
        source.inventory("not-an-id")
    with pytest.raises(ValueError):
        phoible_source.read_source("../LICENSE")


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "archive"
    resource = Path(phoible_source.__file__).parent / "data/phoible"
    for name in phoible_source.source_files():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(phoible_source.read_source(name))
    (root / "LICENSE").write_bytes((resource / "GPL-3.0.txt").read_bytes())
    (root / "data/LICENSE").write_bytes((resource / "MIT-upstream.txt").read_bytes())
    return root


def test_same_source_reader_parity_explicit_precedence_and_no_network(
    archive, monkeypatch
):
    monkeypatch.delenv(PHOIBLE_ENV, raising=False)
    shipped = PhoibleBridge()
    external = PhoibleBridge(archive)
    assert shipped._metadata == external._metadata
    assert shipped._bibtex == external._bibtex
    assert shipped.language("eng") == external.language("eng")
    for key in (160, 2175):
        assert shipped.inventory(key) == external.inventory(key)
    monkeypatch.setenv(PHOIBLE_ENV, str(archive / "missing"))
    with pytest.raises(PhoibleDataUnavailable):
        PhoibleBridge()
    assert PhoibleBridge(archive / "data/phoible.csv").root == archive


def test_builder_is_shared_deterministic_and_dirty_input_refuses(archive):
    result = phoible.build(archive)
    assert result.source.digests == phoible_source.source_policy()["inputs"]
    assert result.artifacts == phoible.build(archive).artifacts
    assert result.stale(Path(__file__).resolve().parents[1]) == []
    for name in phoible_source.source_files():
        assert (
            gzip.decompress(result.artifacts[phoible.OUT / (name + ".gz")])
            == (archive / name).read_bytes()
        )
    (archive / "data/phoible.csv").write_bytes(b"dirty")
    with pytest.raises(SourceContentError):
        phoible.build(archive)
    (archive / "data/phoible.csv").unlink()
    with pytest.raises(SourceMissingError):
        phoible.validate_source(archive)


def test_existing_source_lifecycle_is_read_only(archive, monkeypatch, tmp_path):
    def forbidden(*args):
        pytest.fail("existing checkout acquisition must not mutate Git")

    monkeypatch.setattr(dev_sources, "git", forbidden)
    result = dev_sources.run("fetch", "phoible", archive, tmp_path)
    assert result["state"] == "available"
    assert dev_sources.run("build", "phoible", archive, tmp_path)["state"] == "changed"
    assert (
        dev_sources.run("check", "phoible", archive, tmp_path)["state"] == "unchanged"
    )


def test_checkout_revision_refuses_even_when_consumed_bytes_match(archive, monkeypatch):
    (archive / ".git").mkdir()
    monkeypatch.setattr(
        phoible.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "0" * 40),
    )
    with pytest.raises(SourceVersionError):
        phoible.validate_source(archive)


def test_fresh_fetch_uses_declared_pin_and_all_consumed_paths(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(dev_sources, "git", lambda *args: calls.append(args) or "")
    monkeypatch.setattr(
        phoible, "validate_source", lambda path: type("Identity", (), {"digests": {}})()
    )
    producer = dev_sources._phoible_producer()
    dev_sources._acquire(tmp_path / "new-source", producer)
    assert any(call[-1] == phoible_source.source_policy()["revision"] for call in calls)
    sparse = next(call for call in calls if "sparse-checkout" in call)
    assert set(sparse[4:]) == {
        "/" + name for name in phoible_source.source_policy()["inputs"]
    }


@pytest.mark.parametrize("failure", ["missing", "corrupt", "manifest", "content"])
def test_resource_integrity_refuses(failure, tmp_path, monkeypatch):
    root = tmp_path / "data/phoible"
    root.mkdir(parents=True)
    real = Path(phoible_source.__file__).parent / "data/phoible"
    manifest = json.loads((real / "manifest.json").read_text())
    name = "data/phoible.csv.gz"
    packed = (real / name).read_bytes()
    if failure == "corrupt":
        packed = b"broken gzip"
        manifest["transport-sha256"][name] = hashlib.sha256(packed).hexdigest()
    if failure == "content":
        packed = gzip.compress(b"modified")
        manifest["transport-sha256"][name] = hashlib.sha256(packed).hexdigest()
    if failure == "manifest":
        manifest["source-sha256"] = {}
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "data").mkdir()
    if failure != "missing":
        (root / name).write_bytes(packed)
    monkeypatch.setattr(phoible_source, "files", lambda package: tmp_path)
    # Keep policy itself fixed: the manipulated resource is not its own oracle.
    policy = json.loads((real.parent / "phoible-policy.json").read_text())
    monkeypatch.setattr(phoible_source, "source_policy", lambda: policy)
    with pytest.raises(
        SourceMissingError if failure == "missing" else SourceContentError
    ):
        phoible_source.read_source("data/phoible.csv")
