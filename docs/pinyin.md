# Pinyin: a syllable-primary representation

Pinyin organizes syllables and tone on the shared substrate, with a profile
distinct from the house phone inventory.
See [comparative systems](systems.md) for the distinction between a notation,
an inventory, and a model of structure and computation.

## Structure and attachment

The Pinyin profile declares syllable, constituent, tone, and optional phonetic
tiers. A syllable contains its onset (when present) and rhyme constituent. Tone
associates with the syllable. The written mark's vowel host is selected separately.
An optional IPA realization can be attached directly or referenced on the
phonetic tier; syllable identity and tone attachment are established independently.

The spelling codec independently selects the vowel on which to write the tone.
Thus `shui` with tone 3 renders as `shuǐ`, without moving the semantic tone
association to `i`.

## Library entry points

[`ipakit.bridges.pinyin.PINYIN`](../ipakit/bridges/pinyin.py) owns the shipped
vocabulary declaration, keyboard aliases (`u:` and `v` for `ü`), and tone-mark
renderer. The graph constructor is currently an internal profile API,
[`ipakit._pinyin_graph.build`](../ipakit/_pinyin_graph.py), whose interface may change:

```python
from ipakit._pinyin_graph import build as build_pinyin
from ipakit.bridges.pinyin import PINYIN

syllable = build_pinyin("shui", "sh", "ui", 3)
PINYIN.render(syllable)  # 'shuǐ'
```

This call requires explicit spelling, onset, rhyme, and tone; automatic parsing
of arbitrary Mandarin text is outside its scope. The vocabulary bridge also
offers groupings over house IPA sequences. That sequence view and the
syllable-primary graph profile have separate interfaces; neither is a flat phoneset.

## Implemented boundaries

The [profile tests](../tests/tiergraph/test_j_profiles.py) exercise syllable-hosted
tone, optional referenced phonetic realization, and native graph serialization
round trips. [Codec tests](../tests/tiergraph/test_codecs.py) check orthographic
placement without changing semantic attachment. The declared syllabary also
supplies the membership domain for [Mandarin syllabification](syllabification.md).

Rendering this graph is currently library-only, with CLI ingestion outside the
implemented scope. See the [API/CLI boundary](cli-api-sync.md). Each house
computation has its own profile admission rules; this bridge covers the declared
syllabary and profile operations rather than general Chinese text processing.
