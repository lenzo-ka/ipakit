"""Pinned ZIPA recognizer-vocabulary bridge."""

from __future__ import annotations

from pathlib import Path

from ..features import IPAFeatures
from ..form import Form
from .vocabulary import (
    VocabularyBridge,
    VocabularyProjection,
    VocabularyResidueError,
)

_PATH = Path(__file__).parent.parent / "data" / "bridges" / "zipa" / "zipa.xml"


class ZIPABridge(VocabularyBridge):
    """Read ZIPA labels and IPAPack++ ``custom.original`` transcriptions."""

    NON_PHONE_MARKERS = frozenset({"<blk>", "<sos/eos>", "<unk>"})
    """Reserved ZIPA control labels that do not denote phones."""

    def __init__(self, *, ipa: IPAFeatures | None = None) -> None:
        """Load the shipped declaration pinned to the ZIPA source vocabulary."""
        super().__init__(_PATH, ipa=ipa)

    def read_tokens(self, labels: list[str] | tuple[str, ...]) -> Form:
        """Read an explicitly segmented ZIPA label sequence."""
        return self.read(labels)

    def emit(
        self, form: Form | VocabularyProjection, *, separator: str | None = None
    ) -> str:
        """Emit ZIPA tokens, retaining separate bare-mark labels."""
        rendered = super().emit(form, separator="")
        if separator is None:
            separator = self.separator
        if not separator:
            return rendered
        return separator.join(atom.output for atom in self.tokenize(rendered))

    def read_original(self, text: str) -> Form:
        """Read an IPAPack++ ``custom.original`` string into strict house IPA.

        That field retains word boundaries and tie bars, unlike the recognizer
        label stream.  Only ZIPA's ruled ASCII ``g`` spelling is adapted here;
        no change is made to the ordinary strict house reader.
        """
        marker = next(
            (candidate for candidate in self.NON_PHONE_MARKERS if candidate in text),
            None,
        )
        if marker is not None:
            raise VocabularyResidueError(
                f"{self.name} custom.original contains non-phone marker {marker!r}"
            )
        return Form.parse(text.replace("g", "ɡ"), features=self.ipa, strict=True)


ZIPA = ZIPABridge()
