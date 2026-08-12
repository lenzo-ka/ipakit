#!/usr/bin/env python3
"""Regenerate the documented single-phrase tiergraph example."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ipakit  # noqa: E402

# CMUdict 0.7b entries, retained as source phones so IPA comes through the
# library's attested-lexicon converter rather than a hand-written transcription.
CMUDICT_WORDS = (
    ("perhaps", ("P", "ER0", "HH", "AE1", "P", "S")),
    ("I", ("AY1",)),
    ("am", ("AE1", "M")),
    ("a", ("AH0",)),
    ("bad", ("B", "AE1", "D")),
    ("man", ("M", "AE1", "N")),
)


def build_example() -> ipakit.Form:
    """Build one utterance containing one phrase containing six words."""
    builder = ipakit.FormBuilder()
    mapper = ipakit.CMUMapper()
    utterance = builder.begin("utterance", {"spelling": "perhaps I am a bad man"})
    phrase = builder.begin("phrase", {"spelling": "perhaps I am a bad man"})
    words = []
    for index, (spelling, phones) in enumerate(CMUDICT_WORDS):
        word = builder.begin("word", {"spelling": spelling})
        segments = builder.append_ipa(
            mapper.cmu_to_ipa(phones, strict=True), strict=True
        )
        builder.end(word)
        builder.contain(word, segments)
        words.append(word)
        if index + 1 < len(CMUDICT_WORDS):
            builder.append_ipa(" ", strict=True)
    builder.end(phrase)
    builder.end(utterance)
    builder.contain(phrase, words)
    builder.contain(utterance, (phrase,))
    builder.add_root(utterance)
    return builder.build()


def main() -> int:
    destination = ROOT / "docs" / "figures" / "perhaps-i-am-a-bad-man.dot"
    destination.write_text(build_example().to_dot(), encoding="utf-8")
    print(destination.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
