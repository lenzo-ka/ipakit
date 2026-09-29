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

    def __init__(self, language: str, source: str | Path | None = None) -> None:
        """Build ``language`` from an explicit source, then ``IPAKIT_ESPEAK_NG``."""
        from ..espeak_source import declaration_bytes, supplied_source

        root = supplied_source(source)
        declarations = declaration_bytes(str(root))
        try:
            declaration = declarations[language]
        except KeyError as error:
            raise ValueError(
                f"no declared eSpeak NG vocabulary for {language!r}"
            ) from error
        super().__init__(declaration, ipa=_features())
        self.language = language


__all__ = ["ESPEAK_ENV", "EspeakBridge"]
