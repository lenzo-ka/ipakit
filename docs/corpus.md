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
a / c (d) _ e
[vowel] / # ([-vowel])* _
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

An environment element wrapped as `(X)` is optional: it contributes either
zero or one matching unit. The wrapper accepts one literal, bundle,
brace-constrained element, or `*`; nested optionality and an optional query or
rule target are refused. Every consistent width is a recognition site. Thus
`t / (a) a _` has two sites at the `t` in `aat`, one with the first `a`
absent from the reading and one with it present. A rewrite still edits that
one target once, following the engine's existing simultaneous,
non-overlapping-target discipline.

`(X)*` is the bounded-span form: zero or more consecutive units matching `X`,
with the maximum read from the form's length. For example,
`[vowel] / # ([-vowel])* _` finds the `a` in both `a` and `stra`. Parentheses
make the repeated element explicit. This avoids colliding with bare `*`, which
already means exactly one arbitrary segment: `(*)*` is therefore the
unambiguous spelling of zero or more arbitrary segments, while `*` retains its
old one-unit meaning.

Agreement variables inside either variable-width form bind only when at least
one unit is present. A rule may not use a variable in its change when the
variable binds only in an optional or repeated element, because its zero-width
reading supplies no value. Queries may expose the binding on present readings
and no binding on absent ones.

Null spellings are not context elements. `∅`, `[zero]`, `0`, and `Ø` are all
refused in an environment: an environment names what stands there, and nothing
stands at a deletion site. Use `(X)` when the intended context unit may be
absent.

```python
import tempfile
import ipakit

c = ipakit.corpus.create(tempfile.mkdtemp())
c.add("one", {}, {"broad": ipakit.read("an")})
matches = list(ipakit.corpus.query(c, "[nasal] / [vowel] _ #", role="broad"))
[(m.fileid, m.text) for m in matches]  # [("one", "n")]

optional = ipakit.corpus.parse_query("t / (a) a _")
[site.left for site in optional.sites(ipakit.read("aat").units, ipakit.load_ipa_features())]
# [(1, None), (1, 0)]

span = ipakit.corpus.parse_query("a / # ([-vowel])* _")
len(span.sites(ipakit.read("stra").units, ipakit.load_ipa_features()))  # 1

grammar = ipakit.rules.RuleSet.parse("n -> m / _ [place=bilabial]")
answer = ipakit.corpus.derives(grammar, "anp", "amp")
isinstance(answer, ipakit.Derivation)  # True
```

Library parsing is exact unless `wild=True` is requested. The CLI defaults to
wild IPA (`g`, `:`, and `'` are normalized) and prints `query read as: ...` to
stderr once; `--exact` keeps literal codepoints.

## CMUdict ingestion

`ipakit.corpus.ingest_cmudict(corpus, path)` streams an external
`cmudict.dict` or `cmudict-0.7b` file into an existing corpus. The dictionary
is not bundled. Each pronunciation is stored under the `cited` role, with the
lowercased headword in `meta["text"]` and `meta["word"]`. The integer
`meta["variant"]` groups pronunciations: `word` has fileid `word` and variant
1, while `word(2)` has fileid `word.2` and variant 2. Apostrophes in CMUdict
headwords remain literal in fileids; the dot before a variant ordinal cannot
be confused with CMUdict's parenthesized spelling and is filesystem-safe.

The returned `CMUdictIngestReport` has `added` and a tuple of `refusals`.
Each `CMUdictRefusal` carries `line_number`, the complete source `line`, the
parsed `word` when available, and `reason`. This preserves every failed line
for callers while valid lines continue to stream into the corpus. A missing
or unreadable source path raises `CorpusError` instead of producing a report.
ARPAbet is converted by `CMUMapper` in strict mode; stress therefore uses the
same nucleus placement as `from_cmu`, with no ingest-specific mapping table.

The corresponding shell door is:

```sh
$ ipakit corpus init ./cmu-corpus
$ ipakit corpus ingest-cmudict ./cmu-corpus /path/to/cmudict.dict
$ ipakit corpus query '[+nasal] / _ #' -C ./cmu-corpus
```

Refusals are written to stderr, one tab-separated record per source line; a
summary is written to stdout. Any refusal gives status 1. Corpus query defaults
to the `cited` role, and `--role` selects another role explicitly.

A full-scale measurement is intentionally not a test. Run it against a local
upstream checkout with, for example, `/usr/bin/time -p ipakit corpus
ingest-cmudict ./cmu-corpus /path/to/cmudict.dict`; the measured wall time and
resulting corpus size belong in the run report, not in this committed guide.
