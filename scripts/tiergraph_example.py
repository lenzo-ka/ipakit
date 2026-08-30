#!/usr/bin/env python3
"""Regenerate the two documented tiergraph examples.

They are a pair on purpose, because they show the two halves of where
structure comes from. ``build_example`` asserts what a transcription
cannot say: which orthographic word each run of phones spells, and that
one of them is emphatic. ``build_derived_example`` asserts nothing --
it reads a transcription whose boundary marks are written, and the
utterance, its phrases and its words fall out of the reading.
"""

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
        word_features = {"spelling": spelling}
        if spelling == "am":
            word_features["prominence"] = "emphatic"
        word = builder.begin("word", word_features)
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


#: A two-phrase utterance with every boundary it asserts written down.
#:
#: The single-phrase example above cannot demonstrate the derivation: one
#: phrase filling one utterance writes no break, and a mark that is not
#: written asserts nothing, so nothing above ``word`` would be derived and
#: the figure would be right and empty. Two phrases and a closing ``‖``
#: put the structure in the transcription, which is where reading can
#: reach it.
DERIVED_UTTERANCE = (
    "pɚhˈæps ˈa\u035cɪ ˈæm ə bˈæd mˈæn"
    " | "
    "bˌʌt ˈa\u035cɪ ˈæm nˈɑt ə kɹˈuəl wˈʌn"
    " ‖"
)


def build_derived_example() -> ipakit.Form:
    """One utterance of two phrases, read rather than built.

    Nothing here names a tier. The marks name levels, ``ipa.xml`` says
    which tier each level terminates, and :meth:`Form.with_tier_intervals`
    lands a span per node the reading asserts.
    """
    return ipakit.read(DERIVED_UTTERANCE).with_tier_intervals()


def main() -> int:
    figures = ROOT / "docs" / "figures"
    for name, form in (
        ("perhaps-i-am-a-bad-man", build_example()),
        ("derived-from-boundaries", build_derived_example()),
    ):
        destination = figures / f"{name}.dot"
        destination.write_text(form.to_dot(), encoding="utf-8")
        print(destination.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
