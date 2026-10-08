"""Read eSpeak NG vocabularies from a user-supplied source tree."""

from __future__ import annotations

import functools
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


def __getattr__(name: str) -> Any:
    """Load producer-owned provenance constants only when requested."""
    if name not in _PROVENANCE_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from .extraction import espeak

    return getattr(espeak, name)


@functools.lru_cache(maxsize=4)
def declaration_bytes(source: str) -> dict[str, bytes]:
    """Build every pinned declaration in memory from ``source``."""
    from .extraction import espeak

    root = Path(source)
    espeak.require_pin(root)
    declared, resolved = espeak.resolve(root)
    return {
        table.name: espeak.runtime_render(table.name, resolved[table.name])
        for table in declared
        if table.name not in espeak.INTERNAL
    }


def supplied_source(path: str | Path | None = None) -> Path:
    """Resolve explicit path, then ``IPAKIT_ESPEAK_NG``, and validate it."""
    import os

    supplied = path if path is not None else os.environ.get(ESPEAK_ENV)
    if supplied is None:
        raise FileNotFoundError(
            "eSpeak NG source is required; pass source=... or set IPAKIT_ESPEAK_NG"
        )
    return _validated_source(str(Path(supplied).expanduser()))


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


def languages(path: str | Path | None = None) -> tuple[str, ...]:
    """Return language codes generated from the selected user source."""
    source = supplied_source(path)
    return tuple(declaration_bytes(str(source)))
