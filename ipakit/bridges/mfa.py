"""English MFA v3.1.0 vocabulary and dictionary-line bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..form import Form
from .vocabulary import VocabularyBridge

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "mfa" / "mfa.xml"


@dataclass(frozen=True)
class MFADictionaryEntry:
    word: str
    form: Form
    separator: str = "\t"


class MFABridge(VocabularyBridge):
    def __init__(self) -> None:
        super().__init__(_PATH)

    def read_tokens(self, labels: list[str] | tuple[str, ...]) -> Form:
        """Read an aligned label sequence as an explicitly segmented stream."""
        return self.read(labels)

    def read_dictionary_line(self, line: str) -> MFADictionaryEntry:
        """Read the plain MFA word-tab-segmented-phones dictionary form."""
        if "\t" in line:
            word, pronunciation = line.split("\t", 1)
            separator = "\t"
        else:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"MFA dictionary line has no pronunciation: {line!r}")
            word, pronunciation = parts
            separator = line[len(word) : len(line) - len(pronunciation)]
        return MFADictionaryEntry(word, self.read(pronunciation.split()), separator)

    def emit_dictionary_line(self, entry: MFADictionaryEntry) -> str:
        return entry.word + entry.separator + self.emit(entry.form, separator=" ")


MFA = MFABridge()
