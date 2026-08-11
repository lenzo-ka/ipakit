#!/usr/bin/env python3
"""Checked CMUdict / ipa-dict convention-control disagreement demonstration."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit

# A small checked shared-word slice, written in the forms the two landed
# readers produce.  External full-dictionary measurement is deliberately not
# a test; these rows pin the convention control and one substantive contrast.
SAMPLE = (
    ("day", "dˈe͜ɪ", "ˈdeɪ"),
    ("time", "tˈa͜ɪm", "ˈtaɪm"),
    ("go", "ɡˈo͜ʊ", "ˈɡoʊ"),
    ("cat", "kˈæt", "ˈkɛt"),
)


def normalize_ipa_dict_conventions(form: ipakit.Form) -> ipakit.Form:
    """Seat stress on the nucleus and tie adjacent vowel units.

    This mirrors the in-flight English stress-seat normalization explicitly;
    the returned form is a recorded demonstration transform, never a hidden
    preprocessing step in :class:`DisagreementSpread`.
    """
    units = list(form.units)
    pending: str | None = None
    pieces: list[str] = []
    for unit in units:
        stress = unit.prosody.get("stress")
        if stress is not None:
            pending = "ˈ" if stress == "primary" else "ˌ"
        text = unit.core
        if pending and unit.features.get("manner") == "vowel":
            text = pending + text
            pending = None
        pieces.append(text)
    # The sample's source convention writes diphthongs as adjacent vowels.
    # Tie only V V, never every adjacent segment as add_ties(text) would.
    out: list[str] = []
    for index, piece in enumerate(pieces):
        if (
            index
            and units[index - 1].features.get("manner") == "vowel"
            and unit_is_vowel(units[index])
        ):
            out.append("͜")
        out.append(piece)
    return ipakit.read("".join(out))


def unit_is_vowel(unit: object) -> bool:
    return unit.features.get("manner") == "vowel"


def distribution(spreads: list[ipakit.DisagreementSpread]) -> dict[str, int]:
    counts = Counter(
        item.kind.value for spread in spreads for item in spread.disagreements
    )
    return {kind.value: counts[kind.value] for kind in ipakit.DisagreementKind}


def report() -> dict[str, object]:
    raw, normalized = [], []
    for word, cmu, ipa_dict in SAMPLE:
        left = ipakit.ProvenancedForm(f"cmudict:{word}", ipakit.read(cmu))
        right = ipakit.ProvenancedForm(f"ipa-dict/en_US:{word}", ipakit.read(ipa_dict))
        raw.append(ipakit.DisagreementSpread.compare(left, right))
        normalized.append(
            ipakit.DisagreementSpread.compare(
                left,
                ipakit.ProvenancedForm(
                    f"ipa-dict/en_US:{word}; normalized=stress-seat+diphthong-tie",
                    normalize_ipa_dict_conventions(right.form),
                ),
            )
        )
    before, after = distribution(raw), distribution(normalized)
    return {
        "sample_words": [row[0] for row in SAMPLE],
        "normalization": ["seat stress on the nucleus", "tie adjacent vowel units"],
        "raw": before,
        "substantive_after_normalization": after,
        "convention_removed": {key: before[key] - after[key] for key in before},
    }


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=2, sort_keys=True))
