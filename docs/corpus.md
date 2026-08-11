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

An environment element wrapped in parentheses has these width readings:

| Form | Units consumed |
| --- | --- |
| `(X)` or `(X)?` | zero or one |
| `(X)*` | zero or more |
| `(X)+` | one or more |
| `(X){n}` | exactly `n` |
| `(X){n,}` | at least `n` |
| `(X){,m}` | at most `m` |
| `(X){n,m}` | from `n` through `m`, inclusive |

`(X)?` keeps its spelling when serialized and has the same readings as `(X)`.
An open maximum is capped by the form's length. The wrapper accepts one
literal, bundle, brace-constrained element, or `*`; nested variable-width
items and every quantified query or rule target are refused. Every consistent
width is a recognition site. Thus
`t / (a) a _` has two sites at the `t` in `aat`, one with the first `a`
absent from the reading and one with it present. A rewrite still edits that
one target once, following the engine's existing simultaneous,
non-overlapping-target discipline.

For example,
`[vowel] / # ([-vowel])* _` finds the `a` in both `a` and `stra`. Parentheses
make the repeated element explicit and avoid colliding with bare `*`, which
already means exactly one arbitrary segment. `(*)*` is therefore zero or more
arbitrary segments, while `*` retains its old one-unit meaning.

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

## Provenance, splits, and experiments

`Corpus.put_form` optionally records a typed `FormProvenance`: a producer name
and version or content fingerprint, plus the declaration fingerprint under
which it ran. `Entry.provenance` reports records by role; old entries honestly
report an empty mapping. A corpus created with `declaration_identity=...`
stores the same SHA-256-over-canonical-JSON fingerprint discipline used by the
tiergraph envelope.

`Corpus.put_split(name, ids)` stores an explicit ordered membership list in the
manifest. Later entries do not join it. `Corpus.split(name)` refuses if any
member has disappeared, so a cited split cannot quietly change meaning.

```python no-run
grammar = ipakit.shipped("german-final-devoicing")
experiment = ipakit.Experiment(
    grammar, c, "broad", "narrow", split="test", limit=256
)
report = experiment.run()
report.coverage                         # {'derived': 24, 'total': 25, 'ratio': 0.96}
report.counts
# {'derivable': 24, 'provably_underivable': 1,
#  'cap_truncated': 0, 'ill_formed_input': 0}
report.write("experiment-report.json")
```

Those values are executed over a 25-entry slice built by the CMUdict ingester
in `tests/test_experiment.py`. The slice's target forms are the grammar's own
output over its source forms, with one entry overwritten to an unrelated form,
so the 24/25 measures the classifier's discrimination — the constructed mismatch
lands in `provably_underivable`, everything else in `derivable` — not the
grammar's fit to independently observed data. A report contains every entry id and both forms,
the four-way classification, roles, cap, split, declaration fingerprint, and
content-addressed rule-set and corpus identities. `first.compare(second)`
returns the entries that moved class and refuses reports over different data.
An experiment refuses a source or target role absent from every entry in its
corpus or split; absence on only some entries remains per-entry
`ill_formed_input`, because partial coverage is data rather than operator error.

The command-line door prints the paper-table summary and writes the complete
re-runnable document:

```sh
$ ipakit rules derives -s german-final-devoicing -C ./corpus \
    --source cited --target observed --split test --report report.json
coverage        24/25   derivable=24    provably_underivable=1  cap_truncated=0 ill_formed_input=0
report  report.json
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

A full-scale measurement is intentionally not a test. The dated, generated
[`corpus-scaling-report.json`](corpus-scaling-report.json) measures the storage
kernel at 100, 500, 1,000, and 5,000 entries; regenerate it with
`PYTHONHASHSEED=0 python scripts/corpus_scaling.py --counts ... --output ...`.
On its recorded arm64 macOS/Python 3.12.12 run, 5,000 entries occupy 10.34 MB;
put/get/full-scan query take 0.95/0.90/2.82 seconds. The full-scan query is
linear in entry count, so that environment projects to roughly 76 seconds over
the complete CMUdict. This curve is a run report, not a performance threshold.

## Retained-form disagreement spreads

`DisagreementSpread` generalizes the PHOIBLE doculect-spread law from
inventories to forms. Its inputs are two or more `ProvenancedForm` values for
one entry. Empty identities and bare, anonymous `Form` objects are refused.
One input is the designated reference (index 0 unless stated otherwise), and
every other input is aligned independently against it with the landed
`Alignment` machinery. Pairwise reference alignment is deliberate: it keeps
each source claim independent and does not invent a multi-way gap policy that
could amount to adjudication.

```python
spread = ipakit.DisagreementSpread.compare(
    ipakit.ProvenancedForm("cmudict:cat", ipakit.read("kæt")),
    ipakit.ProvenancedForm("ipa-dict/en_US:cat", ipakit.read("kɛt")),
)
spread.comparisons[0].agreements       # k and t positions
spread.disagreements[0].terms          # named metric terms, including height
spread.disagreements[0].cost           # the AlignmentStep price
```

Kinds are the enum `DisagreementKind`, never strings in memory:

| Kind | Claim |
| --- | --- |
| `FEATURE` | aligned units differ in named declared metric terms |
| `STRUCTURE` | insertion/deletion, a substitution involving tied material (the metric compares tied composites as one segmental term, so their internal features are not itemized), or a tier interval on one side only |
| `TIMING` | aligned or unmatched carried units have different timing claims; always unpriced, since the metric declares no timing term — the structural row carries any step cost |

Tier-only structure has cost `0.0` because the segment metric declares no tier
price. The same rule applies to timing: the object reports the claim and reads
the aligned position's price; it never invents a weight. All other costs and
feature names come directly from `AlignmentStep`. The object selects no
winner, averages no forms, and cannot emit a merged transcription. Its
canonical, sorted-key JSON embeds every provenance identity and self-contained
form and round-trips byte-identically.

The checked CMUdict ∥ ipa-dict en_US demonstration is
`scripts/disagreement_demo.py`. Four shared-word rows first produce 5 feature
and 6 structure disagreements. Its explicit recorded transform mirrors the
English normalization shape: move leading stress from the consonant to the
nucleus and tie adjacent vowel units. This removes 4 feature and all 6
structure disagreements attributable to those conventions, leaving 1 feature
disagreement and no structure or timing disagreement as substantive. These
values are executed in `tests/test_disagreement.py`; normalization is confined
to the demonstration and never hidden in the comparison object.
