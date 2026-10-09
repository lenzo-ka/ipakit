"""Explicit acquisition of pinned user-supplied source trees.

Importing this module does not contact an upstream service. The installed API
reaches the network only through :func:`fetch`; developer scripts reuse the
lower-level helpers explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from . import SourceContentError, SourceError, SourceMissingError


class _GitUnavailableError(OSError):
    """The Git executable is not available."""


class _GitOperationError(ValueError):
    """One explicit Git operation failed."""


class _AcquisitionSymlinkError(SourceContentError):
    """An acquisition destination is a symbolic link."""


Validator = Callable[[Path], Mapping[str, str]]


@dataclass(frozen=True)
class _Source:
    """One installed acquisition policy."""

    revision: str
    label: str
    origin: str
    sparse_paths: tuple[str, ...]
    validate: Validator


def _source(name: str) -> _Source:
    """Load one provider's policy only when acquisition is requested."""
    if name != "espeak":
        raise ValueError(f"unknown source provider: {name!r}")

    from . import espeak

    def validate(path: Path) -> Mapping[str, str]:
        return espeak.validate_source(path).digests

    return _Source(
        espeak.REVISION,
        espeak.TAG,
        espeak.ORIGIN,
        espeak.SPARSE_PATHS,
        validate,
    )


def git(source: Path | None, *arguments: str) -> str:
    """Run an explicit Git operation and return its stripped output."""
    import subprocess

    command = ["git", *(["-C", str(source)] if source else []), *arguments]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as error:
        raise _GitUnavailableError("git executable was not found") from error
    except subprocess.TimeoutExpired as error:
        raise _GitOperationError("source Git operation timed out") from error
    if result.returncode:
        raise _GitOperationError(result.stderr.strip() or "source Git operation failed")
    return result.stdout.strip()


def acquire_git(
    source: Path,
    *,
    revision: str,
    origin: str,
    sparse_paths: tuple[str, ...],
    validate: Validator,
    git_runner: Callable[..., str] | None = None,
) -> None:
    """Atomically acquire one pin, or validate an existing destination."""
    source = source.absolute()
    if source.is_symlink():
        raise _AcquisitionSymlinkError(
            f"refusing acquisition into a symbolic link: {source}"
        )
    if source.exists():
        validate(source)
        return

    import shutil
    import tempfile

    run = git if git_runner is None else git_runner
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        raise _AcquisitionSymlinkError(
            f"refusing acquisition into a symbolic link: {source}"
        )
    if source.exists():
        validate(source)
        return

    staging = Path(tempfile.mkdtemp(prefix=f".{source.name}.tmp-", dir=source.parent))
    try:
        run(None, "init", "-q", str(staging))
        run(staging, "remote", "add", "origin", origin)
        run(
            staging,
            "fetch",
            "-q",
            "--depth",
            "1",
            "--filter=blob:none",
            "origin",
            revision,
        )
        run(staging, "sparse-checkout", "set", "--no-cone", *sparse_paths)
        run(staging, "checkout", "-q", "FETCH_HEAD")
        validate(staging)
        if source.exists() or source.is_symlink():
            raise FileExistsError(f"source destination already exists: {source}")
        staging.rename(source)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def fetch(name: str, cache_dir: str | Path | None = None) -> Path:
    """Fetch one installed pin into its managed source-cache directory."""
    from ..source_cache import source_dir

    policy = _source(name)
    destination = source_dir(name, policy.revision, cache_dir)
    existed = destination.exists()
    try:
        acquire_git(
            destination,
            revision=policy.revision,
            origin=policy.origin,
            sparse_paths=policy.sparse_paths,
            validate=policy.validate,
        )
    except _AcquisitionSymlinkError:
        raise
    except _GitUnavailableError as error:
        raise SourceMissingError(
            "'ipakit source fetch' needs git on PATH; or clone "
            f"{policy.origin} at {policy.label} yourself and pass --source"
        ) from error
    except SourceError as error:
        if existed:
            raise SourceContentError(
                f"cached {name} source for {policy.revision} is invalid: "
                f"{error}; it was not modified"
            ) from error
        raise SourceError(
            f"could not fetch {name} {policy.revision} from {policy.origin}: {error}"
        ) from error
    except (OSError, ValueError) as error:
        if existed:
            raise SourceContentError(
                f"cached {name} source for {policy.revision} is invalid: "
                f"{error}; it was not modified"
            ) from error
        raise SourceError(
            f"could not fetch {name} {policy.revision} from {policy.origin}: {error}"
        ) from error
    return destination
