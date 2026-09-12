import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ipakit.extraction import (
    BuildResult,
    SourceContentError,
    SourceMissingError,
    SourceVersionError,
    mfa,
)
from scripts import dev_sources, mfa_vocabularies


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A deliberately small accepted *test* source, never a release pin."""
    path = tmp_path / "source"
    meta = path / "dictionary/test/mfa/v1/meta.json"
    meta.parent.mkdir(parents=True)
    meta.write_text('{"phones": ["a"]}')
    dictionary = path / mfa.DICTIONARY
    dictionary.parent.mkdir(parents=True)
    dictionary.write_text("example\ta\n")
    monkeypatch.setattr(mfa, "META_SHA256", mfa._meta_digest(path))
    monkeypatch.setattr(
        mfa, "DICTIONARY_SHA256", hashlib.sha256(dictionary.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(mfa, "_run", lambda *args: mfa.REVISION)
    return path


def test_revision_metadata_and_dictionary_have_separate_witnesses(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mfa.require_pin(source, dictionary=True)
    dictionary = source / mfa.DICTIONARY
    original = dictionary.read_bytes()
    dictionary.write_bytes(original + b"dirty")
    # Metadata-only generation remains valid; card input validation must fail.
    mfa.require_pin(source)
    with pytest.raises(SourceContentError, match="MFA dictionary has"):
        mfa.require_pin(source, dictionary=True)
    dictionary.write_bytes(original)
    meta = next(source.glob("dictionary/**/meta.json"))
    meta.write_bytes(meta.read_bytes() + b" ")
    with pytest.raises(SourceContentError, match="metadata has"):
        mfa.require_pin(source)
    monkeypatch.setattr(mfa, "_run", lambda *args: "0" * 40)
    with pytest.raises(SourceVersionError):
        mfa.require_pin(source)


def test_archive_is_content_checked_and_missing_is_typed(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_git(*args: object) -> str:
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(mfa, "_run", no_git)
    mfa.require_pin(source, dictionary=True)
    (source / mfa.DICTIONARY).unlink()
    with pytest.raises(SourceMissingError, match="dictionary is absent"):
        mfa.require_pin(source, dictionary=True)
    with pytest.raises(SourceMissingError, match="unreadable"):
        mfa.require_pin(source / "absent")


def test_existing_acquisition_never_runs_mutating_git(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object) -> str:
        pytest.fail("attempted to mutate an existing source")

    monkeypatch.setattr(dev_sources, "git", forbidden)
    dev_sources.acquire_mfa(source)
    (source / mfa.DICTIONARY).write_bytes(b"uncommitted work")
    with pytest.raises(SourceContentError):
        dev_sources.acquire_mfa(source)
    assert (source / mfa.DICTIONARY).read_bytes() == b"uncommitted work"


def test_acquisition_refuses_symlink_and_preexisting_incomplete(tmp_path: Path) -> None:
    source = tmp_path / "existing"
    source.mkdir()
    link = tmp_path / "link"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        dev_sources.acquire_mfa(link)
    with pytest.raises(SourceMissingError):
        dev_sources.acquire_mfa(source)
    assert list(source.iterdir()) == []


def test_fresh_acquisition_uses_one_pin_and_validates_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "cache" / "mfa" / mfa.REVISION
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(dev_sources, "git", lambda *args: calls.append(args) or "")
    monkeypatch.setattr(
        mfa,
        "require_pin",
        lambda path, **kwargs: calls.append(("validate", path, kwargs)),
    )
    dev_sources.acquire_mfa(source)
    assert source.is_dir()
    assert calls[0] == (None, "init", "-q", str(source))
    assert any(call[-1] == mfa.REVISION for call in calls)
    assert calls[-1] == ("validate", source, {"dictionary": True})


def test_candidate_is_discovery_not_repin(monkeypatch: pytest.MonkeyPatch) -> None:
    original = (mfa.PIN, mfa.REVISION, mfa.META_SHA256, mfa.DICTIONARY_SHA256)
    calls = []
    monkeypatch.setattr(
        dev_sources, "git", lambda *args: calls.append(args) or ("a" * 40 + "\tHEAD")
    )
    assert dev_sources.candidate() == {
        "candidate": "a" * 40,
        "state": "candidate",
        "relationship": "unverified",
    }
    assert calls == [(None, "ls-remote", mfa.ORIGIN, "HEAD")]
    assert original == (mfa.PIN, mfa.REVISION, mfa.META_SHA256, mfa.DICTIONARY_SHA256)
    monkeypatch.setattr(dev_sources, "git", lambda *args: "truncated")
    with pytest.raises(ValueError, match="valid HEAD"):
        dev_sources.candidate()


def test_status_missing_succeeds_without_claiming_readiness(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dev_sources.main(["status", "all", "--cache", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["complete"] is False
    assert report["results"][0]["state"] == "missing-data"
    assert {row["source"] for row in report["results"]} == {"mfa", *dev_sources.PENDING}
    assert all(row["state"] == "unsupported" for row in report["results"][1:])


@pytest.mark.parametrize("operation", ["fetch", "build", "check", "discover"])
def test_requested_unsupported_cannot_succeed(
    operation: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dev_sources.main([operation, "clts"]) == 1
    assert json.loads(capsys.readouterr().out)["complete"] is False


def test_runner_build_check_and_legacy_wrapper_share_builder(
    source: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = BuildResult({Path("artifact.txt"): b"derived"})
    calls = []

    def build(path: Path) -> BuildResult:
        calls.append(path)
        return result

    monkeypatch.setattr(mfa, "build", build)
    output = tmp_path / "output"
    output.mkdir()
    argv = ["mfa", "--source", str(source), "--output", str(output)]
    assert dev_sources.main(["check", *argv]) == 1
    assert dev_sources.main(["build", *argv]) == 0
    assert dev_sources.main(["check", *argv]) == 0
    assert (output / "artifact.txt").read_bytes() == b"derived"
    monkeypatch.setattr(mfa_vocabularies, "build", build)
    monkeypatch.setattr(mfa_vocabularies, "ROOT", output)
    assert mfa_vocabularies.generate(source) == {output / "artifact.txt": b"derived"}
    monkeypatch.setattr(
        sys, "argv", ["mfa_vocabularies.py", "check", "--source", str(source)]
    )
    assert mfa_vocabularies.main() == 0
    assert calls == [source] * 5
    capsys.readouterr()


def test_publication_refuses_symlinks_and_preserves_unowned(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"work")
    root = tmp_path / "output"
    root.mkdir()
    (root / "a.xml").symlink_to(outside)
    result = BuildResult({Path("a.xml"): b"new"}, (Path("*.xml"),))
    with pytest.raises(ValueError, match="symbolic link"):
        dev_sources.publish(result, root)
    assert outside.read_bytes() == b"work"
    (root / "a.xml").unlink()
    (root / "stray.xml").write_bytes(b"old")
    (root / "keep.txt").write_bytes(b"keep")
    dev_sources.publish(result, root)
    assert result.stale(root) == []
    assert (root / "keep.txt").read_bytes() == b"keep"


def test_library_import_does_not_require_dev_packages() -> None:
    code = """
import builtins
original = builtins.__import__
blocked = {"pyclts", "panphon", "icu", "pocketsphinx", "packaging", "numpy"}
def guarded(name, *args, **kwargs):
    if name.split(".")[0] in blocked:
        raise AssertionError("optional provider imported: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from ipakit.extraction import mfa
assert mfa.PIN
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(dev_sources.ROOT)},
    )
    assert result.returncode == 0, result.stderr


def test_inventory_cards_uses_dictionary_validator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.inventory_cards import _mfa_metrics

    def reject(path: Path, *, dictionary: bool = False) -> None:
        assert path == tmp_path and dictionary is True
        raise SourceContentError("dictionary control")

    monkeypatch.setattr(mfa, "require_pin", reject)
    with pytest.raises(SourceContentError, match="dictionary control"):
        _mfa_metrics(tmp_path)
