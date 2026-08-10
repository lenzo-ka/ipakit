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
