"""MFA vocabulary and dictionary-line bridges."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..form import Form
from .vocabulary import VocabularyBridge, VocabularyProjection

_DATA = Path(__file__).parent.parent / "data" / "bridges" / "mfa"
UNION = "mfa"
"""The declaration name of the union of shipped MFA phone inventories."""


def declarations() -> tuple[str, ...]:
    """Return the shipped MFA declaration names in sorted order."""

    return tuple(
        sorted(path.stem for path in _DATA.glob("*.xml") if path.stem != UNION)
    )


@dataclass(frozen=True)
class MFADictionaryEntry:
    """A word, its grouped MFA form, and the dictionary's word separator."""

    word: str
    form: Form
    separator: str = "\t"


class MFABridge(VocabularyBridge):
    """One declared MFA vocabulary and the dictionary-line syntax."""

    def __init__(self, declaration: str = "english") -> None:
        """Load ``declaration``, refusing an absent MFA vocabulary."""

        path = _DATA / f"{declaration}.xml"
        if not path.is_file():
            raise ValueError(f"no declared MFA vocabulary for {declaration!r}")
        super().__init__(path)
        self.declaration = declaration

    def read_tokens(self, labels: list[str] | tuple[str, ...]) -> Form:
        """Read an aligned label sequence as an explicitly segmented stream."""
        return self.read(labels)

    def map_to_mfa(self, form: Form) -> VocabularyProjection:
        """Project an arbitrary reachable house form into MFA atoms."""
        return self.map(form)

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
        """Emit one entry in MFA's word-plus-segmented-phones syntax."""

        return entry.word + entry.separator + self.emit(entry.form, separator=" ")


MFA = MFABridge()
