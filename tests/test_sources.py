"""Managed eSpeak builds are offline, inspectable, and receipt-backed."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from ipakit import cli, sources
from ipakit._identity import identity_fingerprint
from ipakit.bridges import EspeakBridge
from ipakit.extraction import (
    SourceContentError,
    SourceMissingError,
    SourceVersionError,
    espeak,
)


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
assert 'ipakit.extraction.acquire' not in sys.modules
assert 'ipakit.extraction.espeak' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", program], check=True)


def test_fetch_uses_the_installed_pin_and_never_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire

    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)
    cache = tmp_path / "cache"
    calls: list[tuple[Path, dict[str, object]]] = []
    validations: list[Path] = []

    def validate(path: Path) -> SimpleNamespace:
        validations.append(path)
        return SimpleNamespace(digests={})

    def acquire_git(path: Path, **kwargs: object) -> None:
        calls.append((path, kwargs))
        path.mkdir(parents=True)
        (path / "phsource").mkdir()
        (path / "COPYING").write_text("fixture notice\n")
        validator = kwargs["validate"]
        assert callable(validator)
        validator(path)

    monkeypatch.setattr(espeak, "validate_source", validate)
    monkeypatch.setattr(acquire, "acquire_git", acquire_git)
    monkeypatch.setattr(espeak, "build", lambda path: pytest.fail("fetch built tables"))

    result = sources.fetch("espeak", cache_dir=cache)

    expected = cache / "sources" / "espeak" / espeak.REVISION
    assert result.state == "source-only"
    assert result.selected_by == "cache"
    assert calls[0][0] == expected
    assert calls[0][1]["revision"] == espeak.REVISION
    assert calls[0][1]["origin"] == espeak.ORIGIN
    assert calls[0][1]["sparse_paths"] == ("/phsource/", "/COPYING")
    assert validations == [expected, expected]
    assert not (cache / "tables").exists()


def test_failed_fetch_leaves_no_destination_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire

    destination = tmp_path / "cache" / "source"
    attempts = 0

    def run(source: Path | None, *arguments: str) -> str:
        nonlocal attempts
        if "fetch" in arguments:
            attempts += 1
            if attempts == 1:
                raise ValueError("controlled fetch failure")
        return ""

    monkeypatch.setattr(acquire, "git", run)
    with pytest.raises(ValueError, match="controlled fetch failure"):
        acquire.acquire_git(
            destination,
            revision="revision",
            origin="https://example.invalid/source.git",
            sparse_paths=("/data/",),
            validate=lambda path: {},
        )
    assert not destination.exists()
    assert not list(destination.parent.glob(f".{destination.name}.tmp-*"))

    acquire.acquire_git(
        destination,
        revision="revision",
        origin="https://example.invalid/source.git",
        sparse_paths=("/data/",),
        validate=lambda path: {},
    )
    assert destination.is_dir()


def test_fetch_allows_a_linked_cache_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire

    real_cache = tmp_path / "real-cache"
    real_cache.mkdir()
    linked_cache = tmp_path / "linked-cache"
    linked_cache.symlink_to(real_cache, target_is_directory=True)
    destination = linked_cache / "source"
    monkeypatch.setattr(acquire, "git", lambda *args: "")

    acquire.acquire_git(
        destination,
        revision="revision",
        origin="https://example.invalid/source.git",
        sparse_paths=("/data/",),
        validate=lambda path: {},
    )

    assert destination.is_dir()


def test_fetch_refuses_symlinks_and_never_repairs_existing_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire
    from ipakit.source_cache import source_dir

    cache = tmp_path / "cache"
    destination = source_dir("espeak", espeak.REVISION, cache)
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "user-work.txt"
    marker.write_text("preserve me")
    destination.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        acquire, "git", lambda *args: pytest.fail("fetch mutated a symlink")
    )

    with pytest.raises(SourceContentError, match="refusing acquisition into"):
        sources.fetch("espeak", cache_dir=cache)
    assert marker.read_text() == "preserve me"

    destination.unlink()
    destination.mkdir()
    marker = destination / "user-work.txt"
    marker.write_text("preserve me")
    monkeypatch.setattr(
        espeak,
        "validate_source",
        lambda path: (_ for _ in ()).throw(SourceContentError("changed input")),
    )
    with pytest.raises(
        SourceContentError,
        match=r"cached espeak source .* is invalid: changed input; it was not modified",
    ):
        sources.fetch("espeak", cache_dir=cache)
    assert marker.read_text() == "preserve me"


def test_fetch_reports_missing_git_and_git_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("controlled missing executable")

    monkeypatch.setattr(subprocess, "run", missing_git)
    with pytest.raises(SourceMissingError) as missing:
        sources.fetch("espeak", cache_dir=tmp_path / "missing-git")
    assert str(missing.value) == (
        "'ipakit source fetch' needs git on PATH; or clone "
        f"{espeak.ORIGIN} at {espeak.TAG} yourself and pass --source"
    )

    failed = subprocess.CompletedProcess(
        ["git"], returncode=1, stdout="", stderr="controlled git failure"
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: failed)
    with pytest.raises(
        ValueError,
        match=(
            rf"could not fetch espeak {espeak.REVISION} from "
            rf"{espeak.ORIGIN}: controlled git failure"
        ),
    ):
        sources.fetch("espeak", cache_dir=tmp_path / "failed-git")


def test_fetch_reports_the_managed_source_when_environment_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire

    cache = tmp_path / "cache"
    monkeypatch.setenv("IPAKIT_ESPEAK_NG", str(tmp_path / "invalid-environment"))

    def acquire_git(path: Path, **kwargs: object) -> None:
        path.mkdir(parents=True)
        (path / "phsource").mkdir()
        (path / "COPYING").write_text("fixture notice\n")

    monkeypatch.setattr(acquire, "acquire_git", acquire_git)
    monkeypatch.setattr(
        espeak,
        "validate_source",
        lambda path: SimpleNamespace(digests={}),
    )

    result = sources.fetch("espeak", cache_dir=cache)

    assert result.state == "source-only"
    assert result.selected_by == "cache"


def test_non_fetch_source_operations_never_acquire(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.extraction import acquire

    source, cache = pinned_source
    monkeypatch.setattr(
        acquire,
        "fetch",
        lambda *args, **kwargs: pytest.fail("non-fetch operation acquired a source"),
    )

    assert sources.status("espeak", cache_dir=cache).state == "missing"
    built = sources.build("espeak", source=source, cache_dir=cache)
    assert sources.receipt("espeak", cache_dir=cache) == built


def test_build_uses_a_fetched_source_after_argument_and_environment(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    managed = cache / "sources" / "espeak" / espeak.REVISION
    managed.parent.mkdir(parents=True)
    source.rename(managed)
    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)

    result = sources.build("espeak", cache_dir=cache)

    assert set(result["artifacts"]) == {"xx.xml", "yy.xml"}
    assert sources.status("espeak", cache_dir=cache).state == "ready"


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


def test_runtime_selection_uses_argument_then_environment_then_cache(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import ipakit
    from ipakit.espeak_source import supplied_source
    from ipakit.source_cache import tables_dir

    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    expected_cache = tables_dir("espeak", espeak.REVISION, espeak.FORMAT, cache)
    monkeypatch.setenv("IPAKIT_SOURCE_CACHE", str(cache))
    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)
    assert supplied_source() == expected_cache

    missing_environment = source.parent / "missing-environment"
    monkeypatch.setenv("IPAKIT_ESPEAK_NG", str(missing_environment))
    with pytest.raises(FileNotFoundError, match=str(missing_environment)):
        supplied_source()
    with pytest.raises(FileNotFoundError, match=str(missing_environment)):
        ipakit.inventories()

    missing_argument = source.parent / "missing-argument"
    with pytest.raises(FileNotFoundError, match=str(missing_argument)):
        supplied_source(missing_argument)

    monkeypatch.setenv("IPAKIT_ESPEAK_NG", str(missing_environment))
    assert supplied_source(source) == source


def test_cached_languages_read_the_receipt_without_reading_tables(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipakit.espeak_source import languages

    source, cache = pinned_source
    phonemes = source / "phsource" / "phonemes"
    content = phonemes.read_text()
    phonemes.write_text(
        content.replace(
            "phonemetable xx consonants\ninclude ph_xx\n"
            "phonemetable yy consonants\ninclude ph_yy\n",
            "phonemetable yy consonants\ninclude ph_yy\n"
            "phonemetable xx consonants\ninclude ph_xx\n",
        )
    )
    assert languages(source) == ("xx", "yy")
    sources.build("espeak", source=source, cache_dir=cache)
    original = Path.read_bytes
    read: list[str] = []

    def recording(path: Path) -> bytes:
        read.append(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", recording)
    assert languages(cache_dir=cache) == ("xx", "yy")
    assert read == ["receipt.json"]


def test_cached_bridge_reads_and_verifies_only_the_requested_table(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    original = Path.read_bytes
    read: list[str] = []

    def recording(path: Path) -> bytes:
        read.append(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", recording)
    assert EspeakBridge("xx", cache_dir=cache).language == "xx"
    assert "xx.xml" in read
    assert "yy.xml" not in read


def test_cached_bridge_refuses_a_tampered_requested_table(
    pinned_source: tuple[Path, Path],
) -> None:
    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    table = cache / "tables" / "espeak" / espeak.REVISION / "format-1" / "xx.xml"
    table.write_bytes(b"tampered\n")

    with pytest.raises(SourceContentError, match="xx.xml does not match its receipt"):
        EspeakBridge("xx", cache_dir=cache)


def test_cached_runtime_refuses_stale_builds_without_writing(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import ipakit
    from ipakit.espeak_source import languages

    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    monkeypatch.setenv("IPAKIT_SOURCE_CACHE", str(cache))
    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)
    build_root = cache / "tables" / "espeak"
    before = _tree_state(build_root)

    monkeypatch.setattr(espeak, "FORMAT", 2)
    with pytest.raises(SourceVersionError, match="format 1.*Nothing was rebuilt"):
        languages(cache_dir=cache)
    assert "espeak" not in ipakit.inventories()
    assert ipakit.inventory("ipa").name == "ipa"
    with pytest.raises(SourceVersionError, match="format 1.*Nothing was rebuilt"):
        ipakit.inventory("espeak:xx")
    assert _tree_state(build_root) == before

    monkeypatch.setattr(espeak, "FORMAT", 1)
    monkeypatch.setattr(espeak, "REVISION", "9" * 40)
    with pytest.raises(SourceVersionError, match="built from 4870adfa"):
        languages(cache_dir=cache)
    assert _tree_state(build_root) == before


def test_ordinary_inventory_does_not_select_optional_espeak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ipakit import espeak_source, inventory

    def unexpected_selection(*args: object, **kwargs: object) -> None:
        raise AssertionError("ordinary inventory selected optional eSpeak data")

    monkeypatch.setattr(espeak_source, "_selection", unexpected_selection)
    assert inventory("ipa").name == "ipa"


def test_inventory_registry_uses_cached_receipt_languages(
    pinned_source: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import ipakit
    from ipakit.inventories import _registry_for

    source, cache = pinned_source
    sources.build("espeak", source=source, cache_dir=cache)
    monkeypatch.delenv("IPAKIT_ESPEAK_NG", raising=False)
    monkeypatch.setenv("IPAKIT_SOURCE_CACHE", str(cache))
    _registry_for.cache_clear()

    names = ipakit.inventories()
    assert "espeak" in names
    assert "espeak:xx" in names
    assert "espeak:yy" in names
    assert ipakit.inventory("espeak:xx").name == "espeak:xx"


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


def test_cli_fetch_reports_status_and_failures_with_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ipakit.source_cache import SourceStatus

    item = SourceStatus(
        "espeak",
        "source-only",
        "cache",
        espeak.TAG,
        espeak.REVISION,
        espeak.REVISION,
        espeak.FORMAT,
        None,
        None,
        None,
    )
    monkeypatch.setattr(sources, "fetch", lambda provider, **kwargs: item)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "fetch", "espeak", "--cache", str(tmp_path)],
    )
    assert cli.main() == 0
    output = capsys.readouterr()
    assert "espeak" in output.out and "source-only" in output.out
    assert output.err == ""

    def fail(provider: str, **kwargs: object) -> SourceStatus:
        raise SourceMissingError("controlled fetch failure")

    monkeypatch.setattr(sources, "fetch", fail)
    assert cli.main() == 1
    assert capsys.readouterr().err == "Error: controlled fetch failure\n"


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
    assert "'ipakit source fetch espeak'" in error
    monkeypatch.setattr(
        sys,
        "argv",
        ["ipakit", "source", "receipt", "espeak", "--cache", str(tmp_path)],
    )
    assert cli.main() == 1
    assert "Error: eSpeak NG source receipt is unavailable" in capsys.readouterr().err
