# The canonical representation

`Form` is the sole public stored representation. IPA text, CMU tokens, JSON, rendering, rewriting, alignment, and gestures are projections around one validated tier graph; the kernel modules remain package-internal.

## One data structure, two views

The graph is the store: `Form` owns one validated graph-backed representation. The linear view—units, intervals, and the segmental spine—is computed from that store and is the computation surface read by rules, distance, and syllabification. The tiergraph format is the portable artifact, a serialization of the store rather than a third representation.

Engines read tier claims through declared predicates over the linear view; they never walk the graph. A rule context may test a tier interval, but graph traversal remains the store's concern. The [language-relative syllabifier](syllabification.md) is the first tier producer, and the rules engine's tier-reading context is the consumer surface.

Tiers, their names, each language's inventory, and any phasing declared over them are language-relative; the feature space and `distance` are universal. [The ratified design record](design/tiers.md#7-what-is-deliberately-not-made-relative) owns the boundary and its metric rationale.

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
have byte-identical serialized JSON and equal authoritative graphs; construction
does not maintain a second parser-shaped representation.

`ipakit.read()` populates a unit tier only where the transcription asserts a
feature on that unit. In particular, its `word` tier currently contains only
words with asserted prominence; it is not an inventory of the words in the
input. Consumers that need every word must not infer them from the presence of
word-tier events.

Containment may be heterogeneous. A phrase can directly contain initial,
medial, or final silence segments alongside word events. Filtering
`direct_children(phrase, "word")` returns only lexical words, while
`leaves(utterance)` expands the word children and retains the silence segments
in their declared order. Silence therefore remains reachable without becoming
a fabricated word.

## Tier-graph envelope

The native store uses tiergraph's plain-JSON envelope with
`format_version: "0.2.0"` and a `graph` member. Native namespace, tier, attribute
and relation declarations travel with the graph. `tiergraph.dumps(graph)` and
`tiergraph.loads(document)` are its serializer and reader; there is no second
ipakit native graph serializer. The older `type: "tiergraph", v: 1` description
was an earlier profile format, not the current authoritative native wire format.

For example, the native constructor's namespace-only graph serializes as:

```json
{"format_version":"0.2.0","graph":{"namespaces":[{"namespace":"urn:example","prefix":"example"}]}}
```

This is a minimal native wire example, not a populated Form. In the internal
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
with `value_name=(namespace, local_name)`. This is a qualified feature identity,
not a prefix convention: identical local names in different namespaces remain
different features, and duplicate qualified identities are refused. The event's
tier must explicitly admit that feature. Declarations without this opt-in retain
the existing IPA payload codec and do not promise arbitrary feature retention.

Opted-in values use tiergraph's `json_value_graph` constructors and
`JsonValueProfile`, including for scalar values. A qualified relation connects
each event to its value root; native value nodes, membership relations and typed
attributes retain nested objects and ordered arrays. Null, false and absence
remain distinct. The internal `declared_value` reader uses the same native
profile after graph restoration. Python objects, byte strings, non-string
object keys and nonfinite numbers are refused instead of being stringified or
dropped. This adds native structure, not embedded graph JSON or Python-object
serialization. It is an internal storage prerequisite, not a CLTS import API or
a change to ordinary IPA Form equality.

Declared source/target tier restrictions on event-only relations are lowered
to native relation-side declarations and enforced there. This does not infer
sound-kind restrictions or a global maximum-one-host policy from per-instance
arity; those require a specific profile's additional constraints.

## IPA values and linear JSON

Structured IPA segment events carry exact spelling and a versioned `ipa-segment` value containing constituents, approaches, modifiers, junctures, and prosody. The lean IPA mode derives resolved features and provenance from that source value; a self-contained snapshot is opt-in and restoration validates it against the structured source. CMU and Pinyin facts are already their profiles' authoritative values and are serialized directly.

`Form.to_json()` and `ipakit.read_json()` expose the `ipakit.form` version 2 linear projection in unit and interval coordinates. `to_json(self_contained=True)` embeds resolved IPA views. Tiergraph durable item IDs are authoritative for event identity; canonical `/clock/...` paths are the versioned ipakit coordinate projected from them. Every projected unit and interval endpoint round-trips through the compatibility adapter.

## Rendering and deferred mechanisms

A renderer selects transcription tiers through its explicit codec profile; it does not guess from graph roots. Mutually exclusive delivery roots use `alternatives`; rendering requires either one persisted `selects` relation or one ephemeral selection argument, and the ephemeral choice does not mutate the graph. Multiple unrelated roots may coexist for traversal.

The linear view supplies `units`, `intervals`, segment and boundary reads, rule sites and edits, pairwise `Alignment`, and rewrite traces. Capability negotiation, recognizer invocation, and rewrite-rule induction are intentionally deferred; version stamps identify the contract and do not negotiate it.

Rewrite recognition scans the rule engine's changing linear derivation state,
not the stored graph. Projection then records broad, narrow, and allophonic
events on the immutable input clock. Insertions remain anchored to their input
boundary, deletions retain an empty-target rewrite relation, and chained
phantoms retain the engine's deterministic result order without adding clock
positions or changing compatibility-unit indices.
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

Nothing above `word` appears in the first figure, and that is correct rather than missing.
One phrase filling one utterance writes no break, and an unwritten mark asserts nothing,
so a reading of it has words and stops. Regenerate both figures with
`python scripts/tiergraph_example.py`.
