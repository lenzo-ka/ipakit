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

`ipakit.read()` populates a unit tier only where the transcription asserts a
feature on that unit. In particular, its `word` tier currently contains only
words with asserted prominence; it is not an inventory of the words in the
input. Consumers that need every word must not infer them from the presence of
word-tier events.

## Tier-graph envelope

The canonical graph envelope is plain JSON with `type: "tiergraph"` and version `v: 1`; readers require that exact version. `model` references the declaration contract by name and version or fingerprint. Bundled declarations need no embedded copy, and declaration snapshots are deferred. `tiers` fixes tier order, `relations` contains canonical default-omitting relation declarations, `roots` names traversal or delivery roots, `clock` contains the structural axis and its final boundary, and `links` contains ordered source/relation/target triples.

The serializer emits this CMU envelope:

```json
{"type":"tiergraph","v":1,"model":{"name":"cmudict","version":"base-1"},"tiers":["phone"],"relations":{},"roots":[],"clock":[{"gaps":[{}],"phone":[{"features":{"phone":"AH","stress":"primary"}}]},{"gaps":[{}]}],"links":[]}
```

One input phone produces two clock entries: its start and the mandatory final boundary. Every clock entry has `gaps`; non-consuming written occurrences refine one tick to additional stable gaps. Events appear under their tier at their start tick. Omitted `duration` means one structural span, explicit zero means a point, and `span: {"start": ..., "end": ...}` preserves refined endpoints. Optional physical timing is `timing: {"start": ..., "duration": ...}` and does not order structure.

Internal references are canonical JSON Pointers such as `/clock/0/phone/0`; paths are document-revision-local. An application that needs durable cross-revision identity stores a declared label feature and resolves it anew after rebuilding. Arbitrary extension features participate normally and serialize in lexical key order.

Declaration fingerprints are SHA-256 over the declaration provider's canonical, compact, key-sorted JSON identity. The PanPhon profile pins `{"domain":[-1,0,1],"features":[...],"provider":"panphon"}`; feature sequence is declaration order and object keys are sorted. The envelope carries the resulting `sha256:` value as the model version.

Only edges of the same relation declaration marked `acyclic` participate in one cycle check. A cycle formed by combining two separately acyclic relation types is allowed unless a future declaration explicitly gives that union a shared constraint.

## IPA values and linear JSON

Structured IPA segment events carry exact spelling and a versioned `ipa-segment` value containing constituents, approaches, modifiers, junctures, and prosody. The lean IPA mode derives resolved features and provenance from that source value; a self-contained snapshot is opt-in and restoration validates it against the structured source. CMU and Pinyin facts are already their profiles' authoritative values and are serialized directly.

`Form.to_json()` and `ipakit.read_json()` expose the `ipakit.form` version 2 linear projection in unit and interval coordinates. `to_json(self_contained=True)` embeds resolved IPA views. Tiergraph durable item IDs are authoritative for event identity; canonical `/clock/...` paths are the versioned ipakit coordinate projected from them. Every projected unit and interval endpoint round-trips through the compatibility adapter.

## Rendering and deferred mechanisms

A renderer selects transcription tiers through its explicit codec profile; it does not guess from graph roots. Mutually exclusive delivery roots use `alternatives`; rendering requires either one persisted `selects` relation or one ephemeral selection argument, and the ephemeral choice does not mutate the graph. Multiple unrelated roots may coexist for traversal.

The linear view supplies `units`, `intervals`, segment and boundary reads, rule sites and edits, pairwise `Alignment`, and rewrite traces. Capability negotiation, recognizer invocation, and rewrite-rule induction are intentionally deferred; version stamps identify the contract and do not negotiate it.
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
event index, while declared relations are labelled edges. Those rules are also
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
