# Kana: mora structure and orthographic realization

The implemented kana work uses mora structure to render a bounded set of
attested Japanese loanword adaptations. It complements the
[syllable-primary Pinyin example](pinyin.md): the organizing unit and rendering
rules differ, while structure and computation use the common substrate.

## What the renderer reads

[`ipakit.bridges.kana.KANA`](../ipakit/bridges/kana.py) renders the `mora` tier,
not a concatenation of segment spellings. Ordinary mora spellings use a declared
table. Special mora kinds render the geminate half as `ッ`, nasal mora as `ン`,
and second long-vowel mora as `ー`.

A mora can group an IPA sequence; it need not be a single IPA segment. Keeping
that grouping makes the orthographic realization a computation over structure
rather than an inference from adjacent characters.

## Public API and CLI

Unlike the current Pinyin graph profile, the attested-adaptation workflow already
has both a public convenience function and a CLI command:

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

This is a small, fixture-backed gairaigo codec, not a comprehensive kana reader,
a productive Japanese loanword adaptation system, or an accent simulator.
Unsupported convenience-function inputs are refused rather than approximated.
The [shipped declaration](../ipakit/data/bridges/kana/kana.xml) identifies the
finite vocabulary and directional fidelity; it must not be advertised as the
complete Japanese inventory.

[Profile tests](../tests/tiergraph/test_j_profiles.py) check the attested
adaptations and that special kana come from derived mora structure.
[CLI tests](../tests/test_cli.py) exercise both accepted adaptations and refusal
of unlisted inputs. See [comparative systems](systems.md) for how this example
fits alongside other models.
