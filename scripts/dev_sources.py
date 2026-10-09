#!/usr/bin/env python3
"""Explicit developer acquisition/update orchestration; never a runtime API."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ipakit import clts  # noqa: E402
from ipakit.extraction import (  # noqa: E402
    BuildResult,
    SourceError,
    acquire,
    espeak,
    mfa,  # noqa: E402
    phoible,
)

# This is an operation-support census, not a second inventory/pin registry.
# Producer pins and semantics remain with their library implementation.
PENDING = {
    "panphon": "promote existing Panphon extractor before registering an adapter",
    "icu": "promote X-SAMPA extraction and identify consumed ICU data",
    "inventory-cards": "existing script; downstream adapter pending",
    "cmudict": "local reader, no registered frozen-artifact producer",
    "ipa-dict": "external provider; no automatic redistribution/acquisition",
    "xrmb": "licensed research corpus; manual external input",
    "internal": "internal generators retain their Makefile ownership",
}


@dataclass(frozen=True)
class _Producer:
    """Script-side lifecycle wiring; source facts remain library-owned."""

    revision: str
    pin: str
    origin: str
    sparse_paths: tuple[str, ...]
    validate: Callable[[Path], Mapping[str, str]]
    build: Callable[[Path], BuildResult]


def _validate_mfa(source: Path) -> Mapping[str, str]:
    mfa.require_pin(source, dictionary=True)
    return {
        "metadata-sha256": mfa.META_SHA256,
        "dictionary-sha256": mfa.DICTIONARY_SHA256,
    }


def _mfa_producer() -> _Producer:
    return _Producer(
        mfa.REVISION,
        mfa.PIN,
        mfa.ORIGIN,
        ("/dictionary/*/*/*/meta.json", "/" + mfa.DICTIONARY.as_posix()),
        _validate_mfa,
        mfa.build,
    )


def _espeak_producer() -> _Producer:
    return _Producer(
        espeak.REVISION,
        espeak.PIN,
        espeak.ORIGIN,
        espeak.SPARSE_PATHS,
        lambda path: espeak.validate_source(path).digests,
        espeak.build_summary,
    )


def _clts_producer() -> _Producer:
    policy = clts.source_policy()
    source = policy["source"]
    return _Producer(
        source["version"],
        source["version"],
        source["upstream-url"],
        tuple("/" + name for name in sorted(policy["inputs"])),
        lambda path: clts.validate_source(path).digests,
        _build_clts,
    )


def _build_clts(source: Path) -> BuildResult:
    """Build every CLTS-derived artifact as one refresh transaction."""
    from ipakit._clts_profile import dumps_manifest
    from ipakit.clts_mapping import build_mapping_artifacts

    core = clts.build_core(source)
    core_path = Path("ipakit/data/clts/core.json")
    snapshot = clts.Snapshot(json.loads(core.artifacts[core_path]))
    mapping = build_mapping_artifacts(source, snapshot=snapshot)
    manifest_path = Path("ipakit/data/clts/manifest.json")
    artifacts = {
        **core.artifacts,
        **mapping.artifacts,
        manifest_path: dumps_manifest(snapshot=snapshot).encode("utf-8"),
    }
    return BuildResult(artifacts, tuple(artifacts), core.source)


def _phoible_producer() -> _Producer:
    policy = phoible.source_policy()
    source = policy["source"]
    origin = source["upstream-url"].partition("/tree/")[0] + ".git"
    return _Producer(
        source["version"],
        source["version"],
        origin,
        tuple("/" + name for name in sorted(policy["inputs"])),
        lambda path: phoible.validate_source(path).digests,
        phoible.build,
    )


PRODUCERS = {
    "mfa": _mfa_producer,
    "clts": _clts_producer,
    "phoible": _phoible_producer,
    "espeak": _espeak_producer,
}


def git(source: Path | None, *arguments: str) -> str:
    """Delegate an explicit Git operation to the installed acquisition code."""
    return acquire.git(source, *arguments)


def acquire_mfa(source: Path) -> None:
    """Acquire the pinned MFA source."""
    _acquire(source, _mfa_producer())


def acquire_espeak(source: Path) -> None:
    """Acquire the pinned eSpeak source through its registered producer."""
    _acquire(source, _espeak_producer())


def _acquire(source: Path, producer: _Producer) -> None:
    """Acquire a registered producer's pinned source."""
    _acquire_git(
        source,
        revision=producer.revision,
        origin=producer.origin,
        sparse_paths=producer.sparse_paths,
        validate=producer.validate,
    )


def _acquire_git(
    source: Path,
    *,
    revision: str,
    origin: str,
    sparse_paths: tuple[str, ...],
    validate: Callable[[Path], Mapping[str, str]],
) -> None:
    """Delegate acquisition while retaining the script's injectable runner."""
    acquire.acquire_git(
        source,
        revision=revision,
        origin=origin,
        sparse_paths=sparse_paths,
        validate=validate,
        git_runner=git,
    )


def publish(result: BuildResult, root: Path) -> None:
    """Write built artifacts and remove only explicitly owned stale files."""
    root = root.resolve()
    stale = result.stale(root)
    targets = {*result.artifacts, *stale}
    for relative in targets:
        target = root / relative
        if target.resolve() != target or not target.resolve().is_relative_to(root):
            raise ValueError(
                f"refusing artifact publication through symbolic link: {target}"
            )
        if target.exists() and not target.is_file():
            raise ValueError(f"artifact target is not a file: {target}")
    for relative, content in result.artifacts.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for relative in stale:
        if relative not in result.artifacts:
            (root / relative).unlink()


def candidate() -> dict[str, str]:
    """Discover MFA update candidates."""
    return _candidate(_mfa_producer())


def _candidate(producer: _Producer) -> dict[str, str]:
    """Discover upstream HEAD without fetching objects or advancing the pin."""
    value = git(None, "ls-remote", producer.origin, "HEAD").split()
    if (
        len(value) != 2
        or value[1] != "HEAD"
        or len(value[0]) != 40
        or any(char not in "0123456789abcdef" for char in value[0])
    ):
        raise ValueError("upstream did not return one valid HEAD revision")
    return {
        "candidate": value[0],
        "state": "unchanged" if value[0] == producer.revision else "candidate",
        "relationship": "same" if value[0] == producer.revision else "unverified",
    }


def run(operation: str, name: str, source: Path, output: Path) -> dict[str, object]:
    """Report each requested operation; unsupported producers remain visible."""
    report: dict[str, object] = {"source": name, "operation": operation}
    if name not in PRODUCERS:
        return {**report, "state": "unsupported", "detail": PENDING[name]}
    try:
        producer = PRODUCERS[name]()
        report.update(expected=producer.pin, path=str(source))
        if operation == "discover":
            report.update(_candidate(producer))
            return report
        if operation == "fetch":
            _acquire(source, producer)
        report["consumed"] = dict(producer.validate(source))
        report["observed"] = producer.pin
        if operation in {"status", "fetch"}:
            report["state"] = "available"
        else:
            result = producer.build(source)
            differences = result.stale(output)
            if operation == "build":
                publish(result, output)
            report.update(
                state="changed" if differences else "unchanged",
                artifacts=[str(path) for path in differences],
            )
    except (OSError, ValueError) as error:
        report.update(
            state=error.code if isinstance(error, SourceError) else "failed",
            detail=str(error),
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("status", "fetch", "build", "check", "discover")
    )
    parser.add_argument("sources", nargs="+", choices=("all", *PRODUCERS, *PENDING))
    parser.add_argument(
        "--cache", type=Path, default=Path.home() / ".cache/ipakit/sources"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="read one existing producer source; forbidden for acquisition",
    )
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.operation == "fetch" and args.source is not None:
        parser.error("fetch uses its managed revision cache; --source is read-only")
    selected = (
        (*PRODUCERS, *PENDING)
        if "all" in args.sources
        else tuple(dict.fromkeys(args.sources))
    )
    if args.source is not None and len(selected) != 1:
        parser.error(
            "--source requires exactly one source; use per-provider caches for multiple sources"
        )
    reports = []
    for name in selected:
        source = args.source
        if source is None:
            source = args.cache / name
            if name in PRODUCERS:
                source /= PRODUCERS[name]().revision
        reports.append(run(args.operation, name, source, args.output))
    success = {"available", "unchanged", "candidate"}
    if args.operation == "build":
        success.add("changed")
    complete = all(report["state"] in success for report in reports)
    print(
        json.dumps(
            {"operation": args.operation, "complete": complete, "results": reports},
            indent=2,
        )
    )
    return 0 if complete or args.operation == "status" else 1


if __name__ == "__main__":
    raise SystemExit(main())
