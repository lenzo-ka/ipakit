# The canonical representation

`Form` is the public stored representation for the house IPA model. IPA text,
CMU tokens, JSON, rendering, rewriting, alignment, and gestures are projections
around its validated tier graph. Model-relative operations can also retain an
explicit native TierGraph through a separate graph API; see
[graph-preserving finite rewrites](rules.md#decorating-an-existing-graph).

## Internal source-profile boundary

The internal CLTS source profile constructs and restores native TierGraph
documents independently of house IPA. Its strict occurrence input preserves
literal ordered tokens, optional `start` plus `duration` in seconds, and supplied
source tone-host links. Complete qualified declarations and provider/profile
bindings remain present even for empty input. Resolution outcomes are explicitly
supplied and validated against the caller's declared source schema; this path
does not run a resolver or infer claims from feature-set labels.
The outcomes are `resolved`, `unknown-sound`, and `outside-artifact-domain`.
Profile bindings own their accepted native JSON domain values and compare by
their typed declaration fingerprint, including constructor field bindings.
Native registry names include that identity so different provider bindings can
coexist; the persisted profile family and version remain separately declared.

Restoration validates the constructor layout and refuses changed declarations,
stale bindings, extra content or other layouts. The profile uses TierGraph's
native codec and constructors. Its native profile report leaves external resolver
truth, house coverage and public consumer admission explicitly undecided.

Source-only or mixed public `Form` admission remains closed. This internal path
does not change Form identity, IPA rendering, rewriting, distance or animation.
The finite CLTS scoring artifact alone is not a full structured resolution
record; integrating real source claims and linguistic hosts requires separately
validated provider/mapping contracts.

## One data structure, two views

`Form` owns one validated graph-backed representation. Its linear view—units,
intervals, and the segmental spine—is computed from that store and supplies
rules, distance, and syllabification. The TierGraph format serializes the store
for persistence and interchange.

Engines read tier claims through declared predicates over the linear view; they never walk the graph. A rule context may test a tier interval, but graph traversal remains the store's concern. The [language-relative syllabifier](syllabification.md) is the first tier producer, and the rules engine's tier-reading context is the consumer surface.

In the house model, tiers, their names, each language's inventory, and any
phasing declared over them are language-relative; its feature space and
`distance` are shared across those languages. [The ratified design
record](design/tiers.md#7-what-is-deliberately-not-made-relative) owns that model's
boundary and metric rationale. Foreign finite models retain their own declared
schemas and operations throughout computation.

## Public construction and navigation

```python
import ipakit

builder = ipakit.FormBuilder()
utterance = builder.begin("utterance")
phrase = builder.begin("phrase")
segments = builder.append_ipa("kæt")
builder.end(phrase)
builder.end(utterance)
builder.contain(phrase, segments)
builder.contain(utterance, (phrase,))
builder.add_root(utterance)
form = builder.build()

assert isinstance(form, ipakit.Form)
assert form.to_ipa() == "kæt"
assert form.direct_children(form.roots[0]) == ("/clock/0/phrase/0",)
assert form.leaves(form.roots[0]) == ("/clock/0/segment/0", "/clock/1/segment/0", "/clock/2/segment/0")
```

Builder handles are opaque edit-time identities, while navigation returns canonical paths. After `build()`, use `roots`, `at`, `direct_children`, `descendants`, `leaves`, `parents`, and `ancestors` on `Form`; never retain or compare a handle to a path. `at(path)` dereferences the same canonical paths returned by navigation and recorded by matches.

`append_ipa()` uses the same canonical scan and lowering as `read()`. For the
same IPA input, a parser-built form and a builder containing only that append
have byte-identical serialized JSON and equal authoritative graphs.

`ipakit.read()` populates a unit tier only where the transcription asserts a
feature on that unit. In particular, its `word` tier currently contains only
words with asserted prominence. Consumers that need every word must supply
complete word segmentation separately.

Containment may be heterogeneous. A phrase can directly contain initial,
medial, or final silence segments alongside word events. Filtering
`direct_children(phrase, "word")` returns only lexical words, while
`leaves(utterance)` expands the word children and retains the silence segments
in their declared order. Silence remains directly reachable on the segment tier.

## Tier-graph envelope

The native store uses tiergraph's plain-JSON envelope with
`format_version: "0.3.0"` and a `graph` member. Native namespace, tier, attribute
and relation declarations travel with the graph. `tiergraph.dumps(graph)` and
`tiergraph.loads(document)` are its serializer and reader; there is no second
ipakit native graph serializer. The older `type: "tiergraph", v: 1` description
was an earlier profile format, not the current authoritative native wire format.

For example, the native constructor's namespace-only graph serializes as:

```json
{"format_version":"0.3.0","graph":{"namespaces":[{"namespace":"urn:example","prefix":"example"}]}}
```

This minimal example contains only a namespace declaration. In the internal
input-clock view, one input phone produces its start and a terminal boundary;
non-consuming written occurrences refine a tick to additional stable gaps.
Native lowering preserves those coordinates as clock boundaries, event
incidence and attributes. Optional physical timing retains start + duration
without ordering structural events or creating ticks.

Internal navigation references such as `/clock/0/segment/0` are ipakit
coordinates, not literal paths into the native JSON envelope. Native durable
item references resolve these events; rebuilding requires a declared identity
policy rather than assuming an array offset is a cross-revision identifier.

Full native restoration is distinct from restoring a public Form. The public
Form JSON API remains the linear version 2 projection described below; native
source-profile restoration, identity and complete-projection guards must be
implemented before exposing incomplete foreign-source Forms.

Only edges of the same relation declaration marked `acyclic` participate in one cycle check. A cycle formed by combining two separately acyclic relation types is allowed unless a future declaration explicitly gives that union a shared constraint.

### Internal declared JSON values

The internal `FeatureDeclaration` can opt into lossless native value storage
with `value_name=(namespace, local_name)`. The qualified identity distinguishes
identical local names in different namespaces as
different features, and duplicate qualified identities are refused. The event's
tier must explicitly admit that feature. Declarations without this opt-in retain
the existing IPA payload codec and do not promise arbitrary feature retention.

Opted-in feature names are excluded from the unqualified house payload view,
when computing the graph cache key, constructing the graph, and resolving
house roles in Form, syllable, vocabulary, query and rendering order. Thus
a foreign `arc` or `unit` value has only its declared qualified
meaning; its local name does not create a private IPA attribute or Unit. Real
structural timing/spans and independently supplied Units retain their
own native meanings. A context with active house Units keeps `input`,
`unit-index` and `interval-index` unqualified: giving any of these support
names a foreign meaning in that context produces a named validation refusal.
Source-only native graphs may declare these foreign names and preserve their
qualified JSON values independently of the house views.
An explicitly selected custom render lane may read its declared qualified
values.

Opted-in values use tiergraph's `json_value_graph` constructors and
`JsonValueProfile`, including for scalar values. A qualified relation connects
each event to its value root; native value nodes, membership relations and typed
attributes retain nested objects and ordered arrays. Null, false and absence
remain distinct. The internal `declared_value` reader uses the same native
profile after graph restoration. Python objects, byte strings, non-string
object keys and nonfinite numbers are refused. Values are stored as native
graph structure. This internal storage facility preserves ordinary IPA Form
equality; CLTS import requires the additional source-profile contracts above.

Declared source/target tier restrictions on event-only relations are lowered
to native relation-side declarations and enforced there. This does not infer
sound-kind restrictions or a global maximum-one-host policy from per-instance
arity; those require a specific profile's additional constraints.

## IPA values and native Form admission

Structured IPA segment events retain constituents, approaches, modifiers,
junctures and prosody. Native Form profile bindings distinguish those typed
values from spelling strings. Resolved views derive from the explicitly bound
restoring inventory unless supplied as native facts. CMU and Pinyin retain their
own profile facts.

`Form.to_json()` writes the complete current native graph, compact by default;
`ipakit.read_json()` validates its profile and reconstructs an actual Form.
`to_json(pretty=True)` uses the same codec with indentation. Historical linear
documents are refused. Native durable IDs identify events; unit coordinates
remain public computed views. See [native graph JSON](graph-json.md) for bindings,
typed facts, native Graph readers, and CLI commands.

## Rendering and deferred mechanisms

A renderer selects transcription tiers through its explicit codec profile; it does not guess from graph roots. Mutually exclusive delivery roots use `alternatives`; rendering requires either one persisted `selects` relation or one ephemeral selection argument, and the ephemeral choice does not mutate the graph. Multiple unrelated roots may coexist for traversal.

The linear view supplies `units`, `intervals`, segment and boundary reads, rule sites and edits, pairwise `Alignment`, and rewrite traces. Capability negotiation, recognizer invocation, and rewrite-rule induction are intentionally deferred; version stamps identify the contract and do not negotiate it.

Rewrite recognition scans the rule engine's changing linear derivation state.
Projection then records broad, narrow, and allophonic
events on the immutable input clock. Insertions remain anchored to their input
boundary, deletions retain an empty-target rewrite relation, and chained
phantoms retain the engine's deterministic result order without adding clock
positions or changing unit indices.
## Draw the tier graph

Every `Form` can render its complete graph as Graphviz DOT:

```python
dot = form.to_dot()
```

The command-line equivalent reads either IPA or an existing Form JSON document:

```text
$ ipakit tiergraph "kæt" -o kæt.dot
$ ipakit tiergraph --from-json form.json -o form.dot
```

The clock is the visible top row. Its arrows and labels put all coarse ticks and
refined gaps in ascending order; dotted edges anchor events to their starting
positions and dashed `extent` edges end at their half-open structural endpoints.
Tier rows follow declaration order. Event order within a row is clock index and
event index, while declared relations are labeled edges. Those rules are also
the emission rules, so the output does not depend on dictionary, set, or hash
iteration order.

The worked [“perhaps I am a bad man” DOT figure](figures/perhaps-i-am-a-bad-man.dot)
is one utterance containing one phrase containing six words. Its word
pronunciations come from CMUdict phone entries through `CMUMapper`. The determiner
*a* uses CMUdict's unstressed `AH0`, realized as `ə`; no stress feature is present.
The figure does not claim a `derived-from` relation because ipakit did not compute
that reduction—it depicts the attested reduced realization only.

Its counterpart, the [boundary-derived DOT figure](figures/derived-from-boundaries.dot),
asserts nothing. It is one utterance of two phrases read out of a transcription whose
boundary marks are written — a space between words, `|` between the phrases, `‖` at the
end — and its utterance, phrases and thirteen words are spans no Python names. The pair
is the division of labor: a transcription says where the structure is, and a builder says
what the transcription cannot, which here is which orthographic word each run of phones
spells and that one of them is emphatic.

Nothing above `word` is read from that transcription alone: one phrase filling
one utterance writes no break, and an unwritten mark asserts nothing. The first
figure nevertheless carries the one phrase and one utterance events that its
builder supplied explicitly, around its six words.

```python
from pathlib import Path

worked_dot = Path("docs/figures/perhaps-i-am-a-bad-man.dot").read_text()
(worked_dot.count('label="/clock/0/phrase/0'),
 worked_dot.count('label="/clock/0/utterance/0'))  # (1, 1)
```

Regenerate both figures with `python scripts/tiergraph_example.py`.
