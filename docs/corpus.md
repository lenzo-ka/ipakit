# Corpus queries

The query language is the recognition half of rule notation: the same parser
reads literals, feature bundles, classes, and the context around `_`, but a
query has no rewrite arrow.

```text
[+nasal] / [vowel] _ [vowel]
t / _ #
[vowel, height=close]
a / * _ #
a{stress=primary}
a{+nasalized}
t{release=no-audible}
n{place=α}
```

The first three mean “an intervocalic nasal”, “word-final `t`”, and “a close
syllabic unit anywhere”. `*` consumes exactly one arbitrary segment; it is
legal in a context but refused as the entire query. A postfix brace is a
conjunction of feature constraints with the element before it. Thus
`a{stress=primary}`, `a{+nasalized}`, and `t{release=no-audible}` are the
conjunctions on those literal bases. They match `ˈa`, `ã`, and `t̚`, but are
not exact-spelling equivalents: for example, `a{stress=primary}` also matches
`ˈã`, while the literal `ˈa` does not. `n{place=α}` additionally exposes the
captured place value in `Match.bindings`.

```python
import tempfile
import ipakit

c = ipakit.corpus.create(tempfile.mkdtemp())
c.add("one", {}, {"broad": ipakit.read("an")})
matches = list(ipakit.corpus.query(c, "[nasal] / [vowel] _ #", role="broad"))
[(m.fileid, m.text) for m in matches]  # [("one", "n")]

grammar = ipakit.rules.RuleSet.parse("n -> m / _ [place=bilabial]")
answer = ipakit.corpus.derives(grammar, "anp", "amp")
isinstance(answer, ipakit.Derivation)  # True
```

Library parsing is exact unless `wild=True` is requested. The CLI defaults to
wild IPA (`g`, `:`, and `'` are normalized) and prints `query read as: ...` to
stderr once; `--exact` keeps literal codepoints.
