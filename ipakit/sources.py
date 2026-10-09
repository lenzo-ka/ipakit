"""Offline inspection and building of user-supplied source tables."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .source_cache import SourceStatus

Provider = Literal["espeak"]


def _provider(provider: str) -> Provider:
    if provider != "espeak":
        raise ValueError(f"unknown source provider: {provider!r}")
    return "espeak"


def _built_at() -> str:
    """Return the receipt build time in RFC 3339 UTC form."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _selected_source(
    source: str | Path | None,
) -> tuple[Path | None, Literal["argument", "environment"] | None]:
    import os

    if source is not None:
        return Path(source).expanduser(), "argument"
    if configured := os.environ.get("IPAKIT_ESPEAK_NG"):
        return Path(configured).expanduser(), "environment"
    return None, None


def _build_source(source: str | Path | None, cache_dir: str | Path | None) -> Path:
    from .extraction import SourceMissingError, espeak
    from .source_cache import source_dir

    selected: Path | None
    selected_by: Literal["argument", "environment", "cache"] | None
    selected, configured_by = _selected_source(source)
    selected_by = configured_by
    if selected is None:
        managed = source_dir("espeak", espeak.REVISION, cache_dir)
        if managed.is_dir():
            selected = managed
            selected_by = "cache"
        else:
            raise SourceMissingError(
                "espeak source is unavailable; pass --source PATH, set "
                "IPAKIT_ESPEAK_NG, or run 'ipakit source fetch espeak'"
            )
    if not (selected / "phsource").is_dir():
        if selected_by == "cache":
            raise SourceMissingError(
                f"managed eSpeak NG source is incomplete at {selected}; move it "
                "aside and run 'ipakit source fetch espeak'"
            )
        raise SourceMissingError(
            f"eSpeak NG source is unavailable at {selected}; "
            "pass source=... or set IPAKIT_ESPEAK_NG"
        )
    return selected


def _revision_value(revision: object) -> str | None:
    if not isinstance(revision, dict):
        return None
    value = revision.get("commit", revision.get("sha256"))
    return value if isinstance(value, str) else None


def _validate_espeak_receipt(
    data: dict[str, Any], *, expected_revision: bool = True
) -> None:
    from .extraction import SourceContentError, espeak

    try:
        policy = data["source-policy"]
        revision = policy["revision"]
        build_record = data["build"]
        if data["kind"] != "user-build":
            raise ValueError("kind is not user-build")
        if data["domain"] != "espeak-ng-vocabulary-tables":
            raise ValueError("domain is not espeak-ng-vocabulary-tables")
        if policy["version"] != 1:
            raise ValueError("source policy version is not 1")
        if policy["source"] != {
            "upstream": espeak.UPSTREAM,
            "upstream-url": espeak.ORIGIN,
            "artifact": f"eSpeak NG {espeak.TAG} phsource phoneme tables",
            "version": espeak.PIN,
            "license": espeak.LICENSE,
            "kind": espeak.KIND,
        }:
            raise ValueError("source policy does not identify eSpeak NG")
        if revision.get("tag") != espeak.TAG:
            raise ValueError(f"revision tag is not {espeak.TAG}")
        accepted_revision = revision in (
            {"tag": espeak.TAG, "commit": espeak.REVISION},
            {"tag": espeak.TAG, "sha256": espeak.PHSOURCE_SHA256},
        )
        if expected_revision and not accepted_revision:
            raise ValueError("revision does not match the installed pin")
        if data["extractor"] != {
            "id": "ipakit.extraction.espeak.build",
            "version": "1",
        }:
            raise ValueError("extractor is not the eSpeak NG table builder")
        if build_record["tool"] != "ipakit":
            raise ValueError("build tool is not ipakit")
        if expected_revision and build_record["format"] != espeak.FORMAT:
            raise ValueError("build format does not match the installed format")
        inputs = policy["inputs"]
        if "phsource/phonemes" not in inputs or any(
            not isinstance(name, str) or not name.startswith("phsource/")
            for name in inputs
        ):
            raise ValueError("source inputs are not eSpeak NG phsource files")
        if data["license"] != {
            "id": espeak.LICENSE,
            "notices": {espeak.NOTICE: data["license"]["notices"][espeak.NOTICE]},
        }:
            raise ValueError("license notice is not the eSpeak NG notice")
        for name, artifact in data["artifacts"].items():
            relative = Path(name)
            if (
                relative.name != name
                or not name.endswith(".xml")
                or artifact.get("schema") != {"id": "ipakit-vocabulary", "version": 1}
            ):
                raise ValueError(f"invalid eSpeak NG table artifact: {name}")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, SourceContentError):
            raise
        raise SourceContentError(
            f"invalid eSpeak NG source receipt: {error}"
        ) from error


def _read_espeak_receipt(
    path: Path, *, expected_revision: bool = True
) -> dict[str, Any]:
    from .extraction import SourceContentError
    from .source_cache import read_receipt

    try:
        data = read_receipt(path)
        _validate_espeak_receipt(data, expected_revision=expected_revision)
        return data
    except SourceContentError:
        raise
    except (OSError, ValueError) as error:
        raise SourceContentError(
            f"invalid eSpeak NG source receipt: {error}"
        ) from error


def _verify_artifacts(directory: Path, data: dict[str, Any]) -> None:
    import hashlib

    from .extraction import SourceContentError

    for name, record in data["artifacts"].items():
        path = directory / name
        try:
            content = path.read_bytes()
        except OSError as error:
            raise SourceContentError(
                f"eSpeak NG table {name} does not match its receipt; "
                "run 'ipakit source build espeak'"
            ) from error
        if path.is_symlink() or hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise SourceContentError(
                f"eSpeak NG table {name} does not match its receipt; "
                "run 'ipakit source build espeak'"
            )


def _current_receipt(
    cache_dir: str | Path | None, *, verify_artifacts: bool
) -> dict[str, Any]:
    from .extraction import SourceContentError, espeak
    from .source_cache import receipt_path, tables_dir

    directory = tables_dir("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    path = receipt_path("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    if directory.is_symlink() or path.is_symlink():
        raise SourceContentError(
            "eSpeak NG managed build paths must not be symbolic links"
        )
    data = _read_espeak_receipt(path)
    if verify_artifacts:
        _verify_artifacts(directory, data)
    return data


def _status(
    *,
    source: str | Path | None,
    cache_dir: str | Path | None,
    verify_artifacts: bool,
    source_selection: Literal["argument", "environment", "cache"] | None = None,
) -> SourceStatus:
    from .extraction import SourceError, espeak
    from .source_cache import SourceStatus, cache_root, source_dir, tables_dir

    selected: Path | None
    selected_by: Literal["argument", "environment", "cache"] | None
    if source_selection is None:
        selected, configured_by = _selected_source(source)
        selected_by = configured_by
    else:
        if source is None:
            raise ValueError("an explicit source selection requires a source path")
        selected, selected_by = Path(source), source_selection
    selected_error: str | None = None
    selected_inputs: dict[str, str] | None = None
    selected_notice: str | None = None
    if selected is not None:
        try:
            import hashlib

            identity = espeak.validate_source(selected)
            selected_inputs = dict(identity.digests)
            selected_notice = hashlib.sha256(espeak._notice_bytes(selected)).hexdigest()
        except (OSError, ValueError) as error:
            selected_error = str(error)

    if selected_error is not None:
        return SourceStatus(
            "espeak",
            "invalid",
            selected_by,
            espeak.TAG,
            espeak.REVISION,
            None,
            espeak.FORMAT,
            None,
            None,
            selected_error,
        )

    target = tables_dir("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    if target.exists() or target.is_symlink():
        try:
            data = _current_receipt(cache_dir, verify_artifacts=verify_artifacts)
        except (SourceError, OSError, ValueError) as error:
            return SourceStatus(
                "espeak",
                "invalid",
                "cache",
                espeak.TAG,
                espeak.REVISION,
                None,
                espeak.FORMAT,
                None,
                None,
                str(error),
            )
        if selected_inputs is not None and (
            data["source-policy"]["inputs"] != selected_inputs
            or data["license"]["notices"][espeak.NOTICE] != selected_notice
        ):
            return SourceStatus(
                "espeak",
                "invalid",
                selected_by,
                espeak.TAG,
                espeak.REVISION,
                None,
                espeak.FORMAT,
                data["build"]["format"],
                data["build"]["built-at"],
                "the selected source does not match the existing managed build",
            )
        revision = _revision_value(data["source-policy"]["revision"])
        return SourceStatus(
            "espeak",
            "ready",
            selected_by or "cache",
            espeak.TAG,
            espeak.REVISION,
            revision,
            espeak.FORMAT,
            data["build"]["format"],
            data["build"]["built-at"],
            None,
        )

    tables_root = cache_root(cache_dir) / "tables" / "espeak"
    current_pin = tables_root / espeak.REVISION
    if current_pin.is_dir():
        candidates = sorted(current_pin.glob("format-*"), key=lambda path: path.name)
        for candidate in candidates:
            if candidate == target or not candidate.is_dir():
                continue
            try:
                data = _read_espeak_receipt(
                    candidate / "receipt.json", expected_revision=False
                )
                observed_format = data["build"]["format"]
                built_at = data["build"]["built-at"]
            except (SourceError, OSError, ValueError):
                suffix = candidate.name.removeprefix("format-")
                observed_format = int(suffix) if suffix.isdigit() else None
                built_at = None
            detail = (
                f"eSpeak NG tables in the cache are format {observed_format}; "
                f"this ipakit reads format {espeak.FORMAT}. Run "
                "'ipakit source build espeak'. Nothing was rebuilt."
            )
            return SourceStatus(
                "espeak",
                "stale-format",
                selected_by or "cache",
                espeak.TAG,
                espeak.REVISION,
                espeak.REVISION,
                espeak.FORMAT,
                observed_format,
                built_at,
                detail,
            )

    if tables_root.is_dir():
        for candidate in sorted(tables_root.iterdir(), key=lambda path: path.name):
            if candidate.name == espeak.REVISION or not candidate.is_dir():
                continue
            observed = candidate.name
            detail = (
                f"eSpeak NG tables in the cache were built from {observed}; "
                f"this ipakit expects {espeak.REVISION} (tag {espeak.TAG}). Run "
                "'ipakit source fetch espeak' then 'ipakit source build espeak'. "
                "Nothing was rebuilt."
            )
            return SourceStatus(
                "espeak",
                "stale-pin",
                selected_by or "cache",
                espeak.TAG,
                espeak.REVISION,
                observed,
                espeak.FORMAT,
                None,
                None,
                detail,
            )

    managed_source = source_dir("espeak", espeak.REVISION, cache_dir)
    if selected is None and managed_source.is_dir():
        try:
            espeak.validate_source(managed_source)
        except (OSError, ValueError) as error:
            return SourceStatus(
                "espeak",
                "invalid",
                "cache",
                espeak.TAG,
                espeak.REVISION,
                None,
                espeak.FORMAT,
                None,
                None,
                str(error),
            )
    if selected is not None or managed_source.is_dir():
        return SourceStatus(
            "espeak",
            "source-only",
            selected_by or "cache",
            espeak.TAG,
            espeak.REVISION,
            espeak.REVISION,
            espeak.FORMAT,
            None,
            None,
            None,
        )
    return SourceStatus(
        "espeak",
        "missing",
        None,
        espeak.TAG,
        espeak.REVISION,
        None,
        espeak.FORMAT,
        None,
        None,
        None,
    )


def status(
    provider: Provider,
    *,
    source: str | Path | None = None,
    cache_dir: str | Path | None = None,
    verify_artifacts: bool = True,
) -> SourceStatus:
    """Inspect one provider without fetching, building, or changing the cache."""
    _provider(provider)
    return _status(
        source=source, cache_dir=cache_dir, verify_artifacts=verify_artifacts
    )


def fetch(provider: Provider, *, cache_dir: str | Path | None = None) -> SourceStatus:
    """Explicitly acquire one pinned source without building tables."""
    _provider(provider)
    from .extraction import acquire

    destination = acquire.fetch("espeak", cache_dir)
    return _status(
        source=destination,
        cache_dir=cache_dir,
        verify_artifacts=True,
        source_selection="cache",
    )


def build(
    provider: Provider,
    *,
    source: str | Path | None = None,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build and publish tables from an argument, environment, or managed source."""
    import hashlib

    from . import __version__
    from ._identity import identity_fingerprint
    from ._source_receipt import RECEIPT_SCHEMA_ID, RECEIPT_SCHEMA_VERSION
    from .extraction import SourceContentError, espeak
    from .source_cache import publish_build, tables_dir

    _provider(provider)
    root = _build_source(source, cache_dir)
    revision = espeak.source_revision(root)
    identity = espeak.validate_source(root)
    notice = espeak._notice_bytes(root)
    target = tables_dir("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    if target.exists() or target.is_symlink():
        current = _current_receipt(cache_dir, verify_artifacts=True)
        if (
            current["source-policy"]["revision"] != revision
            or current["source-policy"]["inputs"] != dict(identity.digests)
            or current["license"]["notices"][espeak.NOTICE]
            != hashlib.sha256(notice).hexdigest()
        ):
            raise SourceContentError(
                "eSpeak NG source does not match the existing managed build; "
                "the existing build was left unchanged"
            )
        return current

    result = espeak.build(root)
    if result.source is None:
        raise SourceContentError("eSpeak NG table build has no source identity")
    if dict(result.source.digests) != dict(identity.digests):
        raise SourceContentError(
            "eSpeak NG source changed before the build; nothing was published"
        )
    if espeak.source_revision(root) != revision:
        raise SourceContentError(
            "eSpeak NG source changed during build: Git revision; nothing was published"
        )
    try:
        current_notice = espeak._notice_bytes(root)
    except OSError as error:
        raise SourceContentError(
            f"eSpeak NG source changed during build: {espeak.NOTICE}; "
            "nothing was published"
        ) from error
    if current_notice != notice:
        raise SourceContentError(
            f"eSpeak NG source changed during build: {espeak.NOTICE}; "
            "nothing was published"
        )
    artifacts: dict[str | Path, bytes] = {
        path.as_posix(): content for path, content in result.artifacts.items()
    }
    material: dict[str, Any] = {
        "schema": {"id": RECEIPT_SCHEMA_ID, "version": RECEIPT_SCHEMA_VERSION},
        "kind": "user-build",
        "domain": "espeak-ng-vocabulary-tables",
        "source-policy": {
            "version": 1,
            "source": result.source.metadata.to_dict(),
            "revision": revision,
            "inputs": dict(result.source.digests),
        },
        "extractor": {
            "id": "ipakit.extraction.espeak.build",
            "version": "1",
        },
        "artifacts": {
            str(name): {
                "sha256": hashlib.sha256(content).hexdigest(),
                "schema": {"id": "ipakit-vocabulary", "version": 1},
            }
            for name, content in artifacts.items()
        },
        "license": {
            "id": espeak.LICENSE,
            "notices": {espeak.NOTICE: hashlib.sha256(current_notice).hexdigest()},
        },
        "build": {
            "tool": "ipakit",
            "tool-version": __version__,
            "format": espeak.FORMAT,
            "built-at": _built_at(),
        },
    }
    built_receipt = {**material, "fingerprint": identity_fingerprint(material)}
    publish_build(target, artifacts, built_receipt)
    return _current_receipt(cache_dir, verify_artifacts=True)


def receipt(
    provider: Provider, *, cache_dir: str | Path | None = None
) -> dict[str, Any]:
    """Return the current validated managed-build receipt."""
    from .extraction import SourceMissingError, espeak
    from .source_cache import receipt_path

    _provider(provider)
    path = receipt_path("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    if not path.is_file():
        raise SourceMissingError(
            "eSpeak NG source receipt is unavailable; run 'ipakit source build espeak'"
        )
    return _current_receipt(cache_dir, verify_artifacts=False)
