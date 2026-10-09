"""Per-language eSpeak NG vocabularies built from user-supplied source."""

from __future__ import annotations

import functools
from pathlib import Path

from ..features import IPAFeatures
from .vocabulary import VocabularyBridge

ESPEAK_ENV = "IPAKIT_ESPEAK_NG"


@functools.lru_cache(maxsize=1)
def _features() -> IPAFeatures:
    """Share the read-only house declaration across generated vocabularies."""
    return IPAFeatures()


class EspeakBridge(VocabularyBridge):
    """One language-scoped eSpeak NG native-mnemonic vocabulary."""

    def __init__(
        self,
        language: str,
        source: str | Path | None = None,
        *,
        cache_dir: str | Path | None = None,
    ) -> None:
        """Load ``language`` from an argument, environment, or managed build."""
        from ..espeak_source import declaration

        super().__init__(
            declaration(language, source, cache_dir=cache_dir), ipa=_features()
        )
        self.language = language


__all__ = ["ESPEAK_ENV", "EspeakBridge"]
