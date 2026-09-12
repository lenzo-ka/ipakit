#!/usr/bin/env python3
"""Explicit developer acquisition/update orchestration; never a runtime API."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ipakit.extraction import (  # noqa: E402
    BuildResult,
    SourceError,
    mfa,  # noqa: E402
)

# This is an operation-support census, not a second inventory/pin registry.
# Producer pins and semantics remain with their library implementation.
PENDING = {
    "espeak": "promote existing eSpeak extractor before registering an adapter",
    "panphon": "promote existing Panphon extractor before registering an adapter",
    "icu": "promote X-SAMPA extraction and identify consumed ICU data",
    "clts": "frozen producer contract belongs to A2/C1",
    "inventory-cards": "existing script; downstream adapter pending",
    "cmudict": "local reader, no registered frozen-artifact producer",
    "phoible": "external provider; no automatic redistribution/acquisition",
    "ipa-dict": "external provider; no automatic redistribution/acquisition",
    "xrmb": "licensed research corpus; manual external input",
    "internal": "internal generators retain their Makefile ownership",
}


def git(source: Path | None, *arguments: str) -> str:
    """Run an explicit Git operation, converting process failures to errors."""
    command = ["git", *(["-C", str(source)] if source else []), *arguments]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise ValueError("source Git operation timed out") from error
    if result.returncode:
        raise ValueError(result.stderr.strip() or "source Git operation failed")
    return result.stdout.strip()


def acquire_mfa(source: Path) -> None:
    """Populate only a newly created directory; existing sources are read-only."""
    source = source.absolute()
    if source.resolve() != source:
        raise ValueError(f"refusing acquisition through a symbolic link: {source}")
    if source.exists():
        mfa.require_pin(source, dictionary=True)
        return
    # mkdir without exist_ok claims this exact new destination; a concurrent
    # creator wins rather than having its work reset by the updater.
    source.parent.mkdir(parents=True, exist_ok=True)
    source.mkdir()
    git(None, "init", "-q", str(source))
    git(source, "remote", "add", "origin", mfa.ORIGIN)
    git(
        source,
        "fetch",
        "-q",
        "--depth",
        "1",
        "--filter=blob:none",
        "origin",
        mfa.REVISION,
    )
    git(
        source,
        "sparse-checkout",
        "set",
        "--no-cone",
        "/dictionary/*/*/*/meta.json",
        "/" + mfa.DICTIONARY.as_posix(),
    )
    git(source, "checkout", "-q", "FETCH_HEAD")
    mfa.require_pin(source, dictionary=True)


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
    """Discover upstream HEAD without fetching objects or advancing the pin."""
    value = git(None, "ls-remote", mfa.ORIGIN, "HEAD").split()
    if (
        len(value) != 2
        or value[1] != "HEAD"
        or len(value[0]) != 40
        or any(char not in "0123456789abcdef" for char in value[0])
    ):
        raise ValueError("upstream did not return one valid HEAD revision")
    return {
        "candidate": value[0],
        "state": "unchanged" if value[0] == mfa.REVISION else "candidate",
        "relationship": "same" if value[0] == mfa.REVISION else "unverified",
    }


def run(operation: str, name: str, source: Path, output: Path) -> dict[str, object]:
    """Report each requested operation; unsupported producers remain visible."""
    report: dict[str, object] = {"source": name, "operation": operation}
    if name != "mfa":
        return {**report, "state": "unsupported", "detail": PENDING[name]}
    report.update(expected=mfa.PIN, path=str(source))
    try:
        if operation == "discover":
            report.update(candidate())
            return report
        if operation == "fetch":
            acquire_mfa(source)
        mfa.require_pin(source, dictionary=True)
        report["observed"] = mfa.PIN
        report["consumed"] = {
            "metadata-sha256": mfa.META_SHA256,
            "dictionary-sha256": mfa.DICTIONARY_SHA256,
        }
        if operation in {"status", "fetch"}:
            report["state"] = "available"
        else:
            result = mfa.build(source)
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
    parser.add_argument("sources", nargs="+", choices=("all", "mfa", *PENDING))
    parser.add_argument(
        "--cache", type=Path, default=Path.home() / ".cache/ipakit/sources"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="read an existing MFA source; forbidden for acquisition",
    )
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.operation == "fetch" and args.source is not None:
        parser.error("fetch uses its managed revision cache; --source is read-only")
    selected = (
        ("mfa", *PENDING)
        if "all" in args.sources
        else tuple(dict.fromkeys(args.sources))
    )
    source = (
        args.source if args.source is not None else args.cache / "mfa" / mfa.REVISION
    )
    reports = [run(args.operation, name, source, args.output) for name in selected]
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
