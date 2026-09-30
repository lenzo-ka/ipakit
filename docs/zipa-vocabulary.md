# ZIPA vocabulary bridge

`ipakit.bridges.zipa.ZIPA` is generated from the MIT-licensed
`ipa_simplified/unigram_127.vocab` file at
`lingjzhu/zipa@d6f7cbc74b29ab7cb0248a5cf2d93f116d79721d`. The pinned input has
SHA-256 `fc3efb3780b98ed1afd096699afb51eb53ccba10c59b9ff38605747d22f82ae8`.
The generated XML ships; the upstream vocabulary does not.

The declaration has 108 base-phone atoms, 15 trailing-mark atoms, and one
`▁` word-boundary atom. `<blk>`, `<sos/eos>`, and `<unk>` are control markers,
not phones, and are declared refusals. ASCII `g` is the only remapped base:
it reads as house `ɡ` and writes back as `g` through the ZIPA inventory style.
That spelling is local to the bridge; strict house IPA still refuses ASCII `g`.

```python
from ipakit.bridges.zipa import ZIPA

ZIPA.read_tokens(("g", "ʲ", "▁", "ᶑ")).to_ipa()  # "ɡʲ#ᶑ"
ZIPA.emit(ZIPA.read_tokens(("g", "ʲ")))            # "g ʲ"
ZIPA.read_original("t͡ʃa ga").to_ipa()             # "t͡ʃa ɡa"
```

`read_tokens` retains the recognizer's atom grouping. `read_original` instead
reads the IPAPack++ `custom.original` transcription, which preserves word
boundaries and tie bars. Do not substitute the space-stripped `text` field:
doing so can attach an orphan initial diacritic to the preceding word.

The external-to-house leg is lossless for declared phone, mark, and boundary
atoms. The house-to-ZIPA leg is classified `lossy-with-report`: ZIPA has no tie
bars, stress, or tone; permits at most one diacritic per phone; and lacks
`̯ ̤ ̆ ̈ ˑ`. These are declaration-level projection limits, not permission to
silently simplify arbitrary house IPA.

Regenerate from an already fetched pinned file with:

```console
$ ZIPA_VOCAB=/path/to/unigram_127.vocab make zipa-vocabulary
$ ZIPA_VOCAB=/path/to/unigram_127.vocab make zipa-vocabulary-check
```
