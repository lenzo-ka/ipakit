"""Managed eSpeak builds are offline, inspectable, and receipt-backed."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from ipakit import cli, sources
from ipakit._identity import identity_fingerprint
from ipakit.extraction import SourceContentError, SourceMissingError, espeak


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "espeak-source"
    phsource = source / "phsource"
    phsource.mkdir(parents=True)
    (phsource / "phonemes").write_text("""phoneme p
  vls blb stp
  ipa p
endphoneme
phonemetable consonants
phonemetable xx consonants
include ph_xx
phonemetable yy consonants
include ph_yy
""")
    (phsource / "ph_xx").write_text("""phoneme a
  vowel
  ipa a
endphoneme
""")
    (phsource / "ph_yy").write_text("""phoneme i
  vowel
  ipa i
endphoneme
""")
    (source / "COPYING").write_text("fixture notice\n")
    return source


def _phsource_digest(source: Path) -> str:
    digest = hashlib.sha256()
    phsource = source / "phsource"
    for path in sorted(item for item in phsource.rglob("*") if item.is_file()):
        digest.update(path.relative_to(phsource).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _tree_state(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def pinned_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source = _source(tmp_path)
    cache = tmp_path / "cache"
    monkeypatch.setattr(
        espeak,
        "source_revision",
        lambda path: {"tag": espeak.TAG, "commit": espeak.REVISION},
    )
    return source, cache


def test_import_and_parser_touch_no_cache_network_or_producer() -> None:
    program = r"""
import os, pathlib, socket, sys
import ipakit
sentinel = pathlib.Path('/cache-must-not-be-read')
os.environ['IPAKIT_SOURCE_CACHE'] = str(sentinel)
original_stat = pathlib.Path.stat
def checked_stat(path, *args, **kwargs):
    if str(path).startswith(str(sentinel)):
        raise AssertionError('parser inspected the source cache')
    return original_stat(path, *args, **kwargs)
pathlib.Path.stat = checked_stat
socket.socket = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network'))
import ipakit.cli
ipakit.cli.create_parser()
assert 'ipakit.sources' not in sys.modules
assert 'ipakit.source_cache' not in sys.modules
assert 'ipakit.extraction.espeak' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", program], check=True)


def test_build_records_provenance_without_local_paths_and_publishes_tables(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    monkeypatch.setattr(sources, "_built_at", lambda: "2026-10-08T14:32:05Z")

    result = sources.build("espeak", source=source, cache_dir=cache)

    assert set(result["artifacts"]) == {"xx.xml", "yy.xml"}
    assert result["source-policy"]["revision"] == {
        "tag": "1.52.0",
        "commit": espeak.REVISION,
    }
    assert result["source-policy"]["version"] == 1
    assert result["source-policy"]["source"] == {
        "upstream": espeak.UPSTREAM,
        "upstream-url": espeak.ORIGIN,
        "artifact": f"eSpeak NG {espeak.TAG} phsource phoneme tables",
        "version": espeak.PIN,
        "license": espeak.LICENSE,
        "kind": espeak.KIND,
    }
    assert result["source-policy"]["inputs"] == {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in ("phsource/phonemes", "phsource/ph_xx", "phsource/ph_yy")
    }
    assert result["extractor"] == {
        "id": "ipakit.extraction.espeak.build",
        "version": "1",
    }
    assert result["license"] == {
        "id": espeak.LICENSE,
        "notices": {
            espeak.NOTICE: hashlib.sha256(
                (source / espeak.NOTICE).read_bytes()
            ).hexdigest()
        },
    }
    assert all(
        record["schema"] == {"id": "ipakit-vocabulary", "version": 1}
        for record in result["artifacts"].values()
    )
    assert result["build"] == {
        "tool": "ipakit",
        "tool-version": "0.5.0",
        "format": 1,
        "built-at": "2026-10-08T14:32:05Z",
    }
    encoded = json.dumps(result)
    assert str(source) not in encoded
    assert str(cache) not in encoded
    build_dir = cache / "tables" / "espeak" / espeak.REVISION / "format-1"
    assert (build_dir / "xx.xml").is_file()
    assert (build_dir / "yy.xml").is_file()
    assert (build_dir / "receipt.json").is_file()
    assert not (build_dir / "COPYING").exists()
    assert result["fingerprint"] == identity_fingerprint(
        {key: value for key, value in result.items() if key != "fingerprint"}
    )


def test_distinct_build_times_change_receipt_fingerprint(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    times = iter(("2026-10-08T14:32:05Z", "2026-10-08T14:32:06Z"))
    monkeypatch.setattr(sources, "_built_at", lambda: next(times))
    first = sources.build("espeak", source=source, cache_dir=cache / "one")
    second = sources.build("espeak", source=source, cache_dir=cache / "two")
    assert first["artifacts"] == second["artifacts"]
    assert first["fingerprint"] != second["fingerprint"]


def test_default_build_time_includes_fractional_seconds() -> None:
    assert "." in sources._built_at()


def test_build_refuses_source_changed_during_build(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    original = espeak._resolve_inputs

    def changing(inputs: dict[str, bytes]):
        result = original(inputs)
        (root / "phsource" / "ph_xx").write_text("changed during build\n")
        return result

    root = source
    monkeypatch.setattr(espeak, "_resolve_inputs", changing)
    with pytest.raises(
        SourceContentError, match="phsource/ph_xx; nothing was published"
    ):
        sources.build("espeak", source=source, cache_dir=cache)
    assert not (cache / "tables").exists()


def test_build_renders_only_the_captured_input_snapshot(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    clean = sources.build("espeak", source=source, cache_dir=cache / "clean")
    input_path = source / "phsource" / "ph_xx"
    original_content = input_path.read_bytes()
    original_resolve = espeak._resolve_inputs

    def racing(inputs: dict[str, bytes]):
        input_path.write_text("phoneme a\n  vowel\n  ipa ɑ\nendphoneme\n")
        try:
            return original_resolve(inputs)
        finally:
            input_path.write_bytes(original_content)

    monkeypatch.setattr(espeak, "_resolve_inputs", racing)
    raced = sources.build("espeak", source=source, cache_dir=cache / "raced")

    assert raced["artifacts"] == clean["artifacts"]
    assert raced["source-policy"]["inputs"] == clean["source-policy"]["inputs"]


def test_existing_build_must_match_selected_source(
    pinned_source: tuple[Path, Path],
) -> None:
    source, cache = pinned_source
    receipt = sources.build("espeak", source=source, cache_dir=cache)
    build_dir = cache / "tables" / "espeak" / espeak.REVISION / "format-1"
    before = _tree_state(build_dir)
    (source / "phsource" / "ph_xx").write_text(
        "phoneme a\n  vowel\n  ipa ɑ\nendphoneme\n"
    )

    state = sources.status("espeak", source=source, cache_dir=cache)
    assert state.state == "invalid"
    assert state.selected_by == "argument"
    with pytest.raises(SourceContentError, match="does not match"):
        sources.build("espeak", source=source, cache_dir=cache)

    assert sources.receipt("espeak", cache_dir=cache) == receipt
    assert _tree_state(build_dir) == before


def test_existing_build_must_match_selected_source_notice(
    pinned_source: tuple[Path, Path],
) -> None:
    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    build_dir = cache / "tables" / "espeak" / espeak.REVISION / "format-1"
    before = _tree_state(build_dir)
    (source / espeak.NOTICE).write_text("different fixture notice\n")

    with pytest.raises(SourceContentError, match="does not match"):
        sources.build("espeak", source=source, cache_dir=cache)

    assert _tree_state(build_dir) == before


def test_dirty_git_checkout_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "espeak"

    def fake_run(root: Path, *args: str) -> str:
        assert root == source
        if args == ("rev-parse", "--show-toplevel"):
            return str(source)
        if args == ("rev-parse", "HEAD"):
            return espeak.REVISION
        if args[:2] == ("status", "--porcelain"):
            return " M phsource/ph_afrikaans"
        raise AssertionError(args)

    monkeypatch.setattr(espeak, "_run", fake_run)
    with pytest.raises(SourceContentError, match="changes under phsource or COPYING"):
        espeak.source_revision(source)


def test_archive_nested_under_unrelated_git_checkout_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    monkeypatch.setattr(espeak, "PHSOURCE_SHA256", _phsource_digest(source))
    monkeypatch.setattr(
        espeak,
        "_run",
        lambda root, *args: (
            str(tmp_path) if args == ("rev-parse", "--show-toplevel") else "outer-head"
        ),
    )

    assert espeak.source_revision(source) == {
        "tag": espeak.TAG,
        "sha256": espeak.PHSOURCE_SHA256,
    }


def test_status_reports_missing_ready_stale_and_invalid_without_writing(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    assert sources.status("espeak", cache_dir=cache).state == "missing"
    assert not cache.exists()

    sources.build("espeak", source=source, cache_dir=cache)
    ready = sources.status("espeak", cache_dir=cache)
    assert ready.state == "ready"
    assert ready.selected_by == "cache"

    build_root = cache / "tables" / "espeak" / espeak.REVISION
    before = _tree_state(build_root)
    monkeypatch.setattr(espeak, "FORMAT", 2)
    stale = sources.status("espeak", cache_dir=cache)
    assert stale.state == "stale-format"
    assert stale.observed_format == 1
    assert "Nothing was rebuilt" in (stale.detail or "")
    selected_stale = sources.status("espeak", source=source, cache_dir=cache)
    assert selected_stale.selected_by == "argument"
    assert _tree_state(build_root) == before
    monkeypatch.setattr(espeak, "FORMAT", 1)

    invalid_source = source.parent / "absent"
    invalid = sources.status("espeak", source=invalid_source, cache_dir=cache)
    assert invalid.state == "invalid"
    assert invalid.selected_by == "argument"
    with pytest.raises(SourceMissingError, match="unavailable"):
        sources.build("espeak", source=invalid_source, cache_dir=cache)

    precedence_cache = cache / "precedence"
    managed = precedence_cache / "sources" / "espeak" / espeak.REVISION
    managed.mkdir(parents=True)
    selected = sources.status("espeak", source=source, cache_dir=precedence_cache)
    assert selected.state == "source-only"
    assert selected.selected_by == "argument"


def test_stale_pin_is_reported_and_not_deleted(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    old_build = cache / "tables" / "espeak" / espeak.REVISION
    before = _tree_state(old_build)
    monkeypatch.setattr(espeak, "REVISION", "9" * 40)
    stale = sources.status("espeak", cache_dir=cache)
    assert stale.state == "stale-pin"
    assert stale.observed_revision == "4870adfa25b1a32b4361592f1be8a40337c58d6c"
    assert old_build.is_dir()
    assert _tree_state(old_build) == before


@pytest.mark.parametrize(
    "mutation",
    (
        lambda receipt: receipt["source-policy"].__setitem__("version", 999),
        lambda receipt: receipt["source-policy"]["inputs"].pop("phsource/phonemes"),
    ),
)
def test_receipt_rejects_invalid_espeak_policy(
    pinned_source: tuple[Path, Path], mutation
) -> None:
    source, cache = pinned_source
    receipt = sources.build("espeak", source=source, cache_dir=cache)
    mutation(receipt)
    material = {key: value for key, value in receipt.items() if key != "fingerprint"}
    receipt["fingerprint"] = identity_fingerprint(material)
    path = cache / "tables" / "espeak" / espeak.REVISION / "format-1" / "receipt.json"
    path.write_text(json.dumps(receipt))

    with pytest.raises(SourceContentError, match="invalid eSpeak NG source receipt"):
        sources.receipt("espeak", cache_dir=cache)


def test_source_inputs_and_managed_receipts_must_not_be_symlinks(
    pinned_source: tuple[Path, Path], tmp_path: Path
) -> None:
    source, cache = pinned_source
    input_path = source / "phsource" / "ph_xx"
    external = tmp_path / "external-input"
    external.write_bytes(input_path.read_bytes())
    input_path.unlink()
    input_path.symlink_to(external)
    with pytest.raises(SourceContentError, match="symbolic link"):
        sources.build("espeak", source=source, cache_dir=cache)

    input_path.unlink()
    input_path.write_bytes(external.read_bytes())
    sources.build("espeak", source=source, cache_dir=cache)
    receipt = (
        cache / "tables" / "espeak" / espeak.REVISION / "format-1" / "receipt.json"
    )
    saved = tmp_path / "saved-receipt.json"
    receipt.rename(saved)
    receipt.symlink_to(saved)
    with pytest.raises(SourceContentError, match="must not be symbolic links"):
        sources.receipt("espeak", cache_dir=cache)

    directory_cache = tmp_path / "directory-cache"
    sources.build("espeak", source=source, cache_dir=directory_cache)
    directory = directory_cache / "tables" / "espeak" / espeak.REVISION / "format-1"
    saved_directory = tmp_path / "saved-build"
    directory.rename(saved_directory)
    directory.symlink_to(saved_directory, target_is_directory=True)
    with pytest.raises(SourceContentError, match="must not be symbolic links"):
        sources.receipt("espeak", cache_dir=directory_cache)


def test_tampered_table_is_invalid_and_build_does_not_repair_it(
    pinned_source: tuple[Path, Path],
) -> None:
    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    table = cache / "tables" / "espeak" / espeak.REVISION / "format-1" / "xx.xml"
    table.write_bytes(b"tampered\n")
    state = sources.status("espeak", cache_dir=cache)
    assert state.state == "invalid"
    with pytest.raises(SourceContentError, match="does not match its receipt"):
        sources.build("espeak", source=source, cache_dir=cache)
    assert table.read_bytes() == b"tampered\n"


def test_cli_receipt_json_equals_api_receipt(
    pinned_source: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, cache = pinned_source
    expected = sources.build("espeak", source=source, cache_dir=cache)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "receipt", "espeak", "--cache", str(cache), "-j"],
    )
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_cli_status_reports_missing_and_stale_with_zero(
    pinned_source: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, cache = pinned_source
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "status", "espeak", "--cache", str(cache), "-j"],
    )
    assert cli.main() == 0
    missing = json.loads(capsys.readouterr().out)
    assert missing["complete"] is False
    assert missing["results"][0]["state"] == "missing"

    sources.build("espeak", source=source, cache_dir=cache)
    monkeypatch.setattr(espeak, "FORMAT", 2)
    assert cli.main() == 0
    stale = json.loads(capsys.readouterr().out)
    assert stale["complete"] is False
    assert stale["results"][0]["state"] == "stale-format"


def test_cli_build_and_receipt_failures_exit_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "build", "espeak", "--cache", str(tmp_path)],
    )
    assert cli.main() == 1
    error = capsys.readouterr().err
    assert "Error: espeak source is unavailable" in error
    assert "local checkout of the pinned source" in error
    assert "source fetch" not in error
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "receipt", "espeak", "--cache", str(tmp_path)],
    )
    assert cli.main() == 1
    assert "Error: eSpeak NG source receipt is unavailable" in capsys.readouterr().err
