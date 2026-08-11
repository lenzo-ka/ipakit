"""Per-language eSpeak NG vocabulary bridges."""

from __future__ import annotations

from pathlib import Path

from .vocabulary import VocabularyBridge

_DATA = Path(__file__).parent.parent / "data" / "bridges" / "espeak"


class EspeakBridge(VocabularyBridge):
    """One language-scoped eSpeak NG native-mnemonic vocabulary."""

    def __init__(self, language: str) -> None:
        """Load the declaration for ``language``, refusing an absent one."""

        declaration = _DATA / f"{language}.xml"
        if not declaration.is_file():
            raise ValueError(f"no declared eSpeak NG vocabulary for {language!r}")
        super().__init__(declaration)
        self.language = language


ESPEAK_EN = EspeakBridge("en")
