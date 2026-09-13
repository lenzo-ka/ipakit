# Kana: mora structure and orthographic realization

The implemented kana work uses mora structure to render a bounded set of
attested Japanese loanword adaptations. It complements the
[syllable-primary Pinyin example](pinyin.md): the organizing unit and rendering
rules differ, while structure and computation use the common substrate.

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
