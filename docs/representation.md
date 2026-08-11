# The canonical representation

`Form` is the sole public stored representation. IPA text, CMU tokens, JSON, rendering, rewriting, alignment, gestures, and compatibility coordinates are projections around one validated tier graph; the kernel modules remain package-internal.

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

## Tier-graph envelope

The canonical graph envelope is plain JSON with `type: "tiergraph"` and version `v: 1`; readers require that exact version. `model` references the declaration contract by name and version or fingerprint. Bundled declarations need no embedded copy, and declaration snapshots are deferred. `tiers` fixes tier order, `relations` contains canonical default-omitting relation declarations, `roots` names traversal or delivery roots, `clock` contains the structural axis and its final boundary, and `links` contains ordered source/relation/target triples.

This CMU envelope is emitted by the landed serializer, not transcribed from an illustrative schema:

```json
{"type":"tiergraph","v":1,"model":{"name":"cmudict","version":"base-1"},"tiers":["phone"],"relations":{},"roots":[],"clock":[{"gaps":[{}],"phone":[{"features":{"phone":"AH","stress":"primary"}}]},{"gaps":[{}]}],"links":[]}
```

One input phone produces two clock entries: its start and the mandatory final boundary. Every clock entry has `gaps`; non-consuming written occurrences refine one tick to additional stable gaps. Events appear under their tier at their start tick. Omitted `duration` means one structural span, explicit zero means a point, and `span: {"start": ..., "end": ...}` preserves refined endpoints. Optional physical timing is `timing: {"start": ..., "duration": ...}` and does not order structure.

Internal references are canonical JSON Pointers such as `/clock/0/phone/0`; paths are document-revision-local. An application that needs durable cross-revision identity stores a declared label feature and resolves it anew after rebuilding. Arbitrary extension features participate normally and serialize in lexical key order.

Declaration fingerprints are SHA-256 over the declaration provider's canonical, compact, key-sorted JSON identity. The PanPhon profile pins `{"domain":[-1,0,1],"features":[...],"provider":"panphon"}`; feature sequence is declaration order and object keys are sorted. The envelope carries the resulting `sha256:` value as the model version.

Only edges of the same relation declaration marked `acyclic` participate in one cycle check. A cycle formed by combining two separately acyclic relation types is allowed unless a future declaration explicitly gives that union a shared constraint.

## IPA values and compatibility JSON

Structured IPA segment events carry exact spelling and a versioned `ipa-segment` value containing constituents, approaches, modifiers, junctures, and prosody. The lean IPA mode derives resolved features and provenance from that source value; a self-contained snapshot is opt-in and restoration validates it against the structured source. CMU and Pinyin facts are already their profiles' authoritative values and are serialized directly.

`Form.to_json()` and `ipakit.read_json()` retain the current `ipakit.form` version 2 compatibility projection for callers using unit and interval coordinates. `to_json(self_contained=True)` embeds resolved IPA views. Compatibility projection is explicit: graph paths remain authoritative internally, while every old unit and interval endpoint round-trips through the graph-backed store.

## Rendering and deferred mechanisms

A renderer selects transcription tiers through its explicit codec profile; it does not guess from graph roots. Mutually exclusive delivery roots use `alternatives`; rendering requires either one persisted `selects` relation or one ephemeral selection argument, and the ephemeral choice does not mutate the graph. Multiple unrelated roots may coexist for traversal.

Compatibility projections remain available for `units`, `intervals`, segment and boundary reads, rule sites and edits, pairwise `Alignment`, and rewrite traces. Capability negotiation, recognizer invocation, and rewrite-rule induction are intentionally deferred; version stamps identify the current contract and do not negotiate it.
