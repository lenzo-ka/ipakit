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
of arbitrary Mandarin text is outside its scope. The supplied constituent facts
are authoritative: the constructor checks the tone category and normalizes
spelling, while the caller supplies linguistically consistent onset and rhyme.
Synthetic spellings remain useful for testing structural operations.

## Canonical conventions and references

The orthographic reference is
[GB/T 16159–2012](https://wsb.sjz.gov.cn/atm/7/20210601162434276.pdf), particularly
§6.3 for capitalization and §6.5 for tone placement. This codec's canonical
output uses NFC Unicode, marked vowels, preserved input capitalization, and
ASCII `'` for the syllable separator. Keyboard aliases are input conveniences;
output uses `ü`/`Ü`. Internal tone category 5 denotes neutral tone, which renders
unmarked; the standard's external numeric notation uses 0. Rendering operates
on supplied syllables within one word; retone, sandhi, and word segmentation
require separate caller-supplied analysis.

The IPA realization reference is the shipped
[`pinyin.xml`](../ipakit/data/bridges/pinyin/pinyin.xml) profile: its `syllable`
records' `ipa` values are the canonical forms of this curated membership domain.
These records combine broad spellings with selected phonetic detail.
[Wikipedia's Mandarin IPA key](https://en.wikipedia.org/wiki/Help:IPA/Mandarin)
guides symbol style, while
[Lee and Zee (2003)](https://doi.org/10.1017/S0025100303001208) supplies a phonetic
reference for the cited vowel and transcription choices. The profile preserves
its explicit row choices, including `xau`, `ʂuei`, `kuɔ`, and `ʈ͡ʂʊŋ`;
extensions should declare their transcription convention and evidence.

## Tone and orthographic rendering

Supply an unmarked syllable spelling and an integer tone category from 1 through
5. Category 5 is the profile's neutral tone and renders without a mark; an absent
tone association also renders unmarked. This internal convention is separate
from external numeric notation using 0 for neutral tone. Pre-marked spellings
require a separate retone operation. Multiple tone associations to one syllable
raise `ValueError`, so rendering requires an explicitly selected analysis.

Input is normalized to NFC. The declared `u:` and `v` keyboard aliases, including
uppercase `U:` and `V`, become `ü` and `Ü`. The renderer preserves capitalization:

```python
PINYIN.render(build_pinyin("Ai", "", "Ai", 4))  # 'Ài'
PINYIN.render(build_pinyin("LU:", "L", "U:", 4))  # 'LǛ'
PINYIN.render(build_pinyin("lu\u0308", "l", "u\u0308", 3))  # 'lǚ'
```

The selected syllable tier represents one orthographic word in item order.
Rendering inserts ASCII apostrophes before subsequent syllables beginning with
`a`, `e`, or `o`: supplied `xi` + `an` with tones 1 + 1 renders `xī'ān`.
Word grouping, inter-word spaces, punctuation, and tone sandhi remain caller
responsibilities. Case and tone placement follow
[GB/T 16159–2012, §§6.3 and 6.5](https://wsb.sjz.gov.cn/atm/7/20210601162434276.pdf);
§6.6.2 illustrates the separator in `Xī’ān`.

## Qualified graph bindings

`PINYIN.render` and `ipakit._codecs.render_pinyin` accept native TierGraph graphs.
The default local name `syllable` must identify exactly one tier. That tier's
namespace binds the `spelling` attribute, `tone` tier, integer `value` attribute,
and `associates-with` relation together. Custom namespaces work with the same
profile declarations. Unrelated qualified attributes and relations are ignored.

When several namespaces declare a syllable tier, pass
`namespace="urn:ipakit:pinyin"` or a `tiergraph.QualifiedName` as `syllable_tier`.
The `tone_tier` argument also accepts a qualified name within the selected
namespace. Ambiguous tier selection or incompatible tone endpoints raises
`ValueError`; namespace prefix spelling has no semantic effect.

## Vocabulary and membership views

The `PINYIN.read` / `PINYIN.emit` interface maps six explicitly separated
simple-vowel symbols into house IPA groupings:

| Pinyin symbol | IPA value |
|---|---|
| `a` | `a` |
| `e` | `ɤ` |
| `i` | `i` |
| `o` | `o` |
| `u` | `u` |
| `ü` | `y` |

The `e` and `ü` values follow [Lee and Zee (2003)](https://doi.org/10.1017/S0025100303001208)
and the [Mandarin IPA spelling key](https://en.wikipedia.org/wiki/Help:IPA/Mandarin).
Pass a single symbol, space-separated symbols, or an explicit sequence:

```python
PINYIN.read("e").to_ipa()  # 'ɤ'
PINYIN.read("ü").to_ipa()  # 'y'
PINYIN.emit(PINYIN.read(("e", "ü")))  # 'e ü'
```

Contextual letter sequences such as `ei`, `ie`, and `ju` require a syllable
analysis and are refused by this simple-vowel reader. Pinyin `e` in `ie` and
`u` after `j`, `q`, or `x` have context-dependent interpretation. The separate
syllable records supply explicit IPA values, including `e` → `ɤ` and `yu` → `y`;
arbitrary Pinyin words require an analysis before phonetic realization.

The curated Mandarin membership list contains 24 IPA syllable shapes. Membership
is tone-independent; lexical tone remains contrastive and associates with the
syllable. The rows combine broad spellings with selected phonetic detail as
declared demonstration forms. Unlisted syllables are reported as uncovered.
Extending this inventory is a separate curation operation with explicit
transcription conventions and pronunciation evidence.

## Implemented boundaries

The [profile tests](../tests/tiergraph/test_j_profiles.py) exercise syllable-hosted
tone, optional referenced phonetic realization, and native graph serialization
round trips. [Codec tests](../tests/tiergraph/test_codecs.py) check orthographic
placement without changing semantic attachment.
[Correctness tests](../tests/tiergraph/test_pinyin_correctness.py) cover namespace
collisions, conflicting tones, Unicode and case, separators, and declared reads.
The declared syllabary also
supplies the membership domain for [Mandarin syllabification](syllabification.md).

Rendering this graph is currently library-only, with CLI ingestion outside the
implemented scope. See the [API/CLI boundary](cli-api-sync.md). Each house
computation has its own profile admission rules; this bridge covers the declared
syllabary and profile operations rather than general Chinese text processing.
