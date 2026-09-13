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

## Scope and evidence

This fixture-backed gairaigo codec covers the declared attested adaptations.
Comprehensive kana reading, productive loanword adaptation and accent simulation
are outside its scope. The convenience function refuses unlisted inputs.
The [shipped declaration](../ipakit/data/bridges/kana/kana.xml) identifies the
finite vocabulary and directional fidelity for this subset of Japanese.

[Profile tests](../tests/tiergraph/test_j_profiles.py) check the attested
adaptations and that special kana come from derived mora structure.
[CLI tests](../tests/test_cli.py) exercise both accepted adaptations and refusal
of unlisted inputs. See [comparative systems](systems.md) for how this example
fits alongside other models.
