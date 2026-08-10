"""Streaming CMUdict ingestion for directory corpora."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from ._corpus import Corpus, CorpusError
from .features import IPAFeatures
from .mapper import CMUMapper

_ENTRY = re.compile(r"(?P<word>\S+?)(?:\((?P<variant>[1-9][0-9]*)\))?\Z")


@dataclass(frozen=True)
class CMUdictRefusal:
    """One source line that could not become a corpus entry."""

    line_number: int
    line: str
    word: str | None
    reason: str


@dataclass(frozen=True)
class CMUdictIngestReport:
    """The entries written and all source lines refused by an ingest."""

    added: int
    refusals: tuple[CMUdictRefusal, ...]

    @property
    def accepted(self) -> bool:
        return not self.refusals


def ingest_cmudict(
    corpus: Corpus,
    source_path: str | os.PathLike[str],
    *,
    mapper: CMUMapper | None = None,
    features: IPAFeatures | None = None,
) -> CMUdictIngestReport:
    """Stream a CMUdict file into ``corpus``, one cited form per pronunciation.

    A base spelling is its lowercased headword; ``word(2)`` becomes ``word.2``.
    Lines beginning with ``#`` or ``;;;`` and inline ``#`` comments are ignored.
    Invalid entry lines are skipped and returned together in the report.
    """
    if not isinstance(corpus, Corpus):
        raise TypeError("corpus must be a Corpus")
    source = Path(source_path)
    if not source.is_file():
        raise CorpusError(f"CMUdict source {source} is not a file")

    cmu = mapper or CMUMapper()
    ipa = features or IPAFeatures()
    refusals: list[CMUdictRefusal] = []
    added = 0
    try:
        stream = source.open(encoding="utf-8")
    except OSError as exc:
        raise CorpusError(f"cannot open CMUdict source {source}: {exc}") from exc

    try:
        with stream:
            for line_number, raw in enumerate(stream, 1):
                line = raw.rstrip("\r\n")
                content = line.split("#", 1)[0].strip()
                if not content or content.startswith(";;;"):
                    continue
                fields = content.split()
                spelling = fields[0]
                parsed = _ENTRY.fullmatch(spelling)
                word: str | None = None
                try:
                    if parsed is None or len(fields) < 2:
                        raise ValueError("expected a headword and one or more phones")
                    word = parsed.group("word").lower()
                    variant = int(parsed.group("variant") or "1")
                    fileid = word if variant == 1 else f"{word}.{variant}"
                    transcription = cmu.cmu_to_ipa(fields[1:], strict=True)
                    form = ipa.read(transcription, strict=True)
                    corpus.add(
                        fileid,
                        {"text": word, "word": word, "variant": variant},
                        {"cited": form},
                    )
                except (CorpusError, UnicodeError, ValueError) as exc:
                    refusals.append(CMUdictRefusal(line_number, line, word, str(exc)))
                    continue
                added += 1
    except (OSError, UnicodeError) as exc:
        raise CorpusError(f"cannot read CMUdict source {source}: {exc}") from exc
    return CMUdictIngestReport(added, tuple(refusals))
