"""Offline, pinned PHOIBLE source aggregation; acquisition stays script-owned."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
from pathlib import Path

from ..phoible_source import (
    NOTICE_FILES,
    receipt_metadata,
    source_files,
    source_metadata,
    source_policy,
)
from . import (
    BuildResult,
    SourceContentError,
    SourceIdentity,
    SourceMissingError,
    SourceVersionError,
)

OUT = Path("ipakit/data/phoible")


def validate_source(source: Path) -> SourceIdentity:
    """Validate all consumed bytes, and the revision when a Git root is supplied."""
    policy = source_policy()
    revision_pin = policy["source"]["version"]
    if (source / ".git").exists():
        try:
            revision = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            raise SourceVersionError("cannot identify PHOIBLE Git revision") from error
        if revision != revision_pin:
            raise SourceVersionError(
                f"PHOIBLE revision {revision}; required {revision_pin}"
            )
    digests = {}
    for name, expected in policy["inputs"].items():
        try:
            content = (source / name).read_bytes()
        except OSError as error:
            raise SourceMissingError(f"missing PHOIBLE source input: {name}") from error
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected:
            raise SourceContentError(f"PHOIBLE source content mismatch: {name}")
        digests[name] = digest
    return SourceIdentity(source_metadata(), digests)


def build(source: Path) -> BuildResult:
    """Produce gzip transport without changing or filtering upstream data."""
    identity = validate_source(source)
    artifacts = {}
    for name in source_files():
        content = (source / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != identity.digests[name]:
            raise SourceContentError(f"PHOIBLE source changed during build: {name}")
        output = io.BytesIO()
        with gzip.GzipFile(
            filename="", fileobj=output, mode="wb", mtime=0, compresslevel=9
        ) as stream:
            stream.write(content)
        artifacts[OUT / (name + ".gz")] = output.getvalue()
    for original, target in (
        ("data/LICENSE", "MIT-upstream.txt"),
        ("LICENSE", "GPL-3.0.txt"),
    ):
        content = (source / original).read_bytes()
        if hashlib.sha256(content).hexdigest() != identity.digests[original]:
            raise SourceContentError(f"PHOIBLE notice changed during build: {original}")
        artifacts[OUT / target] = content
    policy = {
        "version": 1,
        "source": identity.metadata.to_dict(),
        "inputs": dict(identity.digests),
    }
    relative_artifacts = {
        str(path.relative_to(OUT)): content for path, content in artifacts.items()
    }
    notices = {
        name: (
            relative_artifacts[name]
            if name in relative_artifacts
            else (OUT / name).read_bytes()
        )
        for name in NOTICE_FILES
    }
    manifest = receipt_metadata(policy, relative_artifacts, notices)
    artifacts[OUT / "manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    return BuildResult(artifacts, (OUT / "data/*.gz", OUT / "mappings/*.gz"), identity)
