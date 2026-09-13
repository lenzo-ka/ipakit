# Kana: mora structure and orthographic realization

The implemented kana work uses mora structure to render a bounded set of
attested Japanese loanword adaptations. It complements the
[syllable-primary Pinyin example](pinyin.md): the organizing unit and rendering
rules differ, while structure and computation use the common substrate.

## Transcription and spelling conventions

The bridge has three distinct contracts:

| Surface | Adopted convention | Reference and scope |
| --- | --- | --- |
| Source and adapted IPA | Broad American English input with explicitly sequential vowel ties; adapted geminates use `tː` and affricates use house-style ties, such as `t͡ɕː`. | The [shipped adaptation rules](../ipakit/data/rules/japanese-moraic.rules) declare this local convention. [Okada's Japanese IPA illustration](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/EF0E01DD40A1B2779F3ADFF96B5D97E3/S002510030000445Xa.pdf/div-class-title-japanese-div.pdf), pp. 94–95, distinguishes broad `/u/` from its compressed-lip realization. |
| Mora analysis | `(C)(j)V` plus special morae; a geminate closes the preceding syllable and supplies the following onset. Readable `ho | t | to` shares one `tː` occurrence. | [The Japanese declaration](../ipakit/data/syllables/japanese.xml) adopts the syllable-based analysis discussed in [Moraic reversal and realisation](https://www.cambridge.org/core/journals/phonology/article/moraic-reversal-and-realisation-analysis-of-a-japanese-language-game/083B743CFC770D79886F97F39F2ED67E), §2, which also describes alternative analyses. |
| Kana output | Fullwidth katakana from the declared table, small `ッ` for obstruent gemination, `ン` for a nasal mora, and `ー` for vowel length. | [外来語の表記, detailed rules III.1–3](https://www.bunka.go.jp/kokugo_nihongo/sisaku/joho/joho/kijun/naikaku/gairai/honbun06.html) supplies the adopted orthographic conventions. The codec covers its shipped vocabulary; the reference also recognizes lexical exceptions. |

The adapted fixtures use broad `u` (for example, `su` and `ku`). Their current
house-IPA feature interpretation remains that of the written symbol; the
bridge supplies no Japanese-specific phonetic reinterpretation of `u`.
[Wikipedia's Japanese IPA key](https://en.wikipedia.org/wiki/Help:IPA/Japanese)
uses `ɯ` and supplies its own phonetic conventions. Producing that spelling or
a narrower compressed-vowel analysis requires a separately declared realization
mapping. These fixtures therefore carry the broad adaptation convention above,
with fine-grained vowel realization outside their scope.

`morae()` and `to_katakana()` admit exact source strings from the shipped fixture
set. They perform no spelling repair, Unicode-normalization admission, kana
reading or language detection before that lookup. For example, `hɑt` is an
accepted source and its adapted output `hotːo` is a different input to those
convenience functions. General IPA parsing and `syllabify(text, "japanese")`
are separate operations. The bars in readable mora examples mark the returned
sequence; they are display separators, while the underlying `tː` remains one
source unit.

## What the renderer reads

[`ipakit.bridges.kana.KANA`](../ipakit/bridges/kana.py) reads the `mora` tier to
render orthography. Ordinary mora spellings use a declared
table. Special mora kinds render the geminate half as `ッ`, nasal mora as `ン`,
and second long-vowel mora as `ー`.

A mora can group an IPA sequence spanning several segments. The renderer uses
that grouping directly to compute its orthographic realization.

Geminate labels preserve the supplied consonant (`ho | t | to`, `ka | p | pa`,
`ka | k | ka`). The special mora and following onset share one source segment.
An affricate contributes its closure to the special mora and retains the full
affricate in the following onset. A long nasal has a nasal mora, distinct from
the obstruent geminate kind. These labels retain consonant identity directly;
`Q` and `N` would be separate, explicitly selected abstractions.

## Public API and CLI

The attested-adaptation workflow has both a public convenience function and a
CLI command:

```python
import ipakit

ipakit.to_katakana("hɑt")  # 'ホット'
```

The spelling and English source of this worked example are recorded by
[Shogakukan's Digital Daijisen entry for ホット](https://kotobank.jp/word/%E3%81%BB%E3%81%A4%E3%81%A8-3218764).
The dictionary attests the orthographic form and borrowing; the local fixture
supplies the source and adapted broad IPA transcriptions.

```sh
ipakit convert to-katakana "hɑt"
ipakit rules morae "stɹa͜ɪk" -j
```

The first command renders `ホット`; the second exposes the adaptation and its
mora sequence. Library callers with an appropriately constructed `Form` can use
`KANA.render(form)` directly.

General rewrite traces acquire Japanese mora analysis through explicit
`derivation.to_form(mora_language="japanese")`. The default `to_form()` retains
the trace without assigning a language. The Japanese option uses the same
declaration as `syllabify(text, "japanese")` and refuses unlicensed output.

## Associations and serialization

Japanese syllabification adds ordered syllable → mora → segment containment.
The rewrite bridge adds mora → derived-segment containment on the input clock;
its phantom events carry structural ordering without measured acoustic time.
The shared source event preserves the original affricate, modifiers and length.

The native graph wire codec preserves these associations. The current backend
graph accessor is private; the public `Form.to_json()` compatibility format
stores units and intervals and omits graph-only relations and event labels.

```python
import ipakit
import tiergraph

analysis = ipakit.syllabify("hotːo", "japanese")
graph = analysis.form._graph
restored = tiergraph.wire.loads(tiergraph.wire.dumps(graph))
restored == graph  # True
```

See [syllabification](syllabification.md#3-japanese-morae-first) for shared
geminate spans, readable projections and explicit timing-policy refusals.

## Scope and evidence

This fixture-backed gairaigo codec covers the declared attested adaptations.
Comprehensive kana reading, productive loanword adaptation and accent simulation
are outside its scope. The convenience function refuses unlisted inputs.
The [shipped declaration](../ipakit/data/bridges/kana/kana.xml) identifies the
finite vocabulary and directional fidelity for this subset of Japanese.

The broad adaptations retain their declared nasal realizations. Fine-grained
nasal allophony is separate: utterance-final closure varies with the preceding
vowel, as measured in
[Production of the utterance-final moraic nasal](https://www.cambridge.org/core/journals/journal-of-the-international-phonetic-association/article/production-of-the-utterancefinal-moraic-nasal-in-japanese-a-realtime-mri-study/560B70DE7334F30F54E18D0486785E66).

[Profile tests](../tests/tiergraph/test_j_profiles.py) check the attested
adaptations and that special kana come from derived mora structure.
[CLI tests](../tests/test_cli.py) exercise both accepted adaptations and refusal
of unlisted inputs. See [comparative systems](systems.md) for how this example
fits alongside other models.
