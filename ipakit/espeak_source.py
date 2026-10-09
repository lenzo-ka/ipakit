"""Read eSpeak NG vocabularies from a user source or managed build."""

from __future__ import annotations

import functools
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

ESPEAK_ENV = "IPAKIT_ESPEAK_NG"

if TYPE_CHECKING:
    from .extraction.espeak import (
        KIND as KIND,
    )
    from .extraction.espeak import (
        LICENSE as LICENSE,
    )
    from .extraction.espeak import (
        PIN as PIN,
    )
    from .extraction.espeak import (
        UPSTREAM as UPSTREAM,
    )
    from .extraction.espeak import (
        UPSTREAM_URL as UPSTREAM_URL,
    )

_PROVENANCE_NAMES = frozenset({"KIND", "LICENSE", "PIN", "UPSTREAM", "UPSTREAM_URL"})


@dataclass(frozen=True)
class _Selection:
    """One validated raw source or receipt-backed managed build."""

    path: Path
    receipt: dict[str, Any] | None = None


def __getattr__(name: str) -> Any:
    """Load producer-owned provenance constants only when requested."""
    if name not in _PROVENANCE_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from .extraction import espeak

    return getattr(espeak, name)


@functools.lru_cache(maxsize=4)
def declaration_bytes(source: str) -> dict[str, bytes]:
    """Build every pinned declaration in memory from raw ``source``."""
    from .extraction import espeak

    root = Path(source)
    espeak.require_pin(root)
    declared, resolved = espeak.resolve(root)
    return {
        table.name: espeak.runtime_render(table.name, resolved[table.name])
        for table in declared
        if table.name not in espeak.INTERNAL
    }


def _cache_selection(cache_dir: str | Path | None) -> _Selection:
    from . import sources
    from .extraction import SourceContentError, SourceError, SourceVersionError, espeak
    from .source_cache import tables_dir

    directory = tables_dir("espeak", espeak.REVISION, espeak.FORMAT, cache_dir)
    if directory.exists() or directory.is_symlink():
        try:
            receipt = sources._current_receipt(cache_dir, verify_artifacts=False)
        except (SourceError, OSError, ValueError) as error:
            if isinstance(error, SourceContentError):
                raise
            raise SourceContentError(
                f"invalid eSpeak NG source receipt: {error}"
            ) from error
        return _Selection(directory, receipt)

    state = sources.status("espeak", cache_dir=cache_dir, verify_artifacts=False)
    if state.state == "stale-pin":
        raise SourceVersionError(
            "eSpeak NG tables in the cache were built from "
            f"{state.observed_revision}; this ipakit expects {espeak.REVISION} "
            f"(tag {espeak.TAG}). Run 'ipakit source fetch espeak' then "
            "'ipakit source build espeak'. Nothing was rebuilt."
        )
    if state.state == "stale-format":
        raise SourceVersionError(
            "eSpeak NG tables in the cache are format "
            f"{state.observed_format}; this ipakit reads format {espeak.FORMAT}. "
            "Run 'ipakit source build espeak'. Nothing was rebuilt."
        )
    if state.state == "invalid":
        raise SourceContentError(state.detail or "invalid eSpeak NG managed build")
    raise FileNotFoundError(
        "eSpeak NG source is required; pass source=..., set IPAKIT_ESPEAK_NG, "
        "or run 'ipakit source fetch espeak' then 'ipakit source build espeak'"
    )


def _selection(
    path: str | Path | None = None,
    *,
    cache_dir: str | Path | None = None,
) -> _Selection:
    """Resolve argument, environment, then managed cache without falling through."""
    import os

    supplied = path if path is not None else os.environ.get(ESPEAK_ENV)
    if supplied is not None:
        return _Selection(_validated_source(str(Path(supplied).expanduser())))
    return _cache_selection(cache_dir)


def supplied_source(
    path: str | Path | None = None,
    *,
    cache_dir: str | Path | None = None,
) -> Path:
    """Resolve argument, environment, then a valid managed build."""
    return _selection(path, cache_dir=cache_dir).path


@functools.lru_cache(maxsize=4)
def _validated_source(supplied: str) -> Path:
    """Validate one selected checkout once per process."""
    source = Path(supplied)
    if not (source / "phsource").is_dir():
        raise FileNotFoundError(
            f"eSpeak NG source is unavailable at {source}; "
            "pass source=... or set IPAKIT_ESPEAK_NG"
        )
    from .extraction.espeak import require_pin

    require_pin(source)
    return source


def _receipt_languages(receipt: dict[str, Any]) -> tuple[str, ...]:
    """Read language names from validated receipt artifact keys."""
    return tuple(sorted(name.removesuffix(".xml") for name in receipt["artifacts"]))


def _languages(selection: _Selection) -> tuple[str, ...]:
    if selection.receipt is not None:
        return _receipt_languages(selection.receipt)
    return tuple(sorted(declaration_bytes(str(selection.path))))


def languages(
    path: str | Path | None = None,
    *,
    cache_dir: str | Path | None = None,
) -> tuple[str, ...]:
    """Return language codes from a raw source or managed-build receipt."""
    return _languages(_selection(path, cache_dir=cache_dir))


def declaration(
    language: str,
    path: str | Path | None = None,
    *,
    cache_dir: str | Path | None = None,
) -> bytes:
    """Return one declaration, verifying only the managed artifact used."""
    from .extraction import SourceContentError

    selection = _selection(path, cache_dir=cache_dir)
    if selection.receipt is None:
        try:
            return declaration_bytes(str(selection.path))[language]
        except KeyError as error:
            raise ValueError(
                f"no declared eSpeak NG vocabulary for {language!r}"
            ) from error

    name = f"{language}.xml"
    record = selection.receipt["artifacts"].get(name)
    if record is None:
        raise ValueError(f"no declared eSpeak NG vocabulary for {language!r}")
    table = selection.path / name
    try:
        content = table.read_bytes()
    except OSError as error:
        raise SourceContentError(
            f"eSpeak NG table {name} does not match its receipt; "
            "run 'ipakit source build espeak'"
        ) from error
    if table.is_symlink() or hashlib.sha256(content).hexdigest() != record["sha256"]:
        raise SourceContentError(
            f"eSpeak NG table {name} does not match its receipt; "
            "run 'ipakit source build espeak'"
        )
    return content
