# Pinyin: a syllable-primary representation

Pinyin is an implemented example of different organizing principles on the
shared substrate, not merely another spelling for the house phone inventory.
See [comparative systems](systems.md) for the distinction between a notation,
an inventory, and a model of structure and computation.

## Structure and attachment

The Pinyin profile declares syllable, constituent, tone, and optional phonetic
tiers. A syllable contains its onset (when present) and rhyme constituent. Tone
associates with the syllable, not the vowel that happens to carry its written
mark. An optional IPA realization can be attached directly or referenced on the
phonetic tier; it is not required to establish the syllable's identity or tone
attachment.

The spelling codec independently selects the vowel on which to write the tone.
Thus `shui` with tone 3 renders as `shuǐ`, without moving the semantic tone
association to `i`.

## Library entry points

[`ipakit.bridges.pinyin.PINYIN`](../ipakit/bridges/pinyin.py) owns the shipped
vocabulary declaration, keyboard aliases (`u:` and `v` for `ü`), and tone-mark
renderer. The graph constructor is currently an internal profile API,
[`ipakit._pinyin_graph.build`](../ipakit/_pinyin_graph.py), not a promised stable
public constructor:

```python
from ipakit._pinyin_graph import build as build_pinyin
from ipakit.bridges.pinyin import PINYIN

syllable = build_pinyin("shui", "sh", "ui", 3)
PINYIN.render(syllable)  # 'shuǐ'
```

This call supplies spelling, onset, rhyme, and tone explicitly. It is not an
automatic parser for arbitrary Mandarin text. The vocabulary bridge also offers
groupings over house IPA sequences; that view must not be confused with the
syllable-primary graph profile or treated as a flat phoneset.

## Implemented boundaries

The [profile tests](../tests/tiergraph/test_j_profiles.py) exercise syllable-hosted
tone, optional referenced phonetic realization, and native graph serialization
round trips. [Codec tests](../tests/tiergraph/test_codecs.py) check orthographic
placement without changing semantic attachment. The declared syllabary also
supplies the membership domain for [Mandarin syllabification](syllabification.md).

Rendering this graph is currently library-only; there is no dedicated CLI
ingestion surface for the Pinyin syllable/tone profile. See the
[API/CLI boundary](cli-api-sync.md). These capabilities do not imply that every
house computation accepts every profile, or that the bridge is a general Chinese
text-processing system.
