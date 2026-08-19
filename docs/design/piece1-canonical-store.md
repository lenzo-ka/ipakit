# Piece 1 canonical-store cutover checkpoint

This checkpoint deliberately stops after the pre-change differential oracle and
the durable event-to-item identity seam.  The complete embedded-store retarget is
not a safe single increment at the pinned tiergraph surface: ipakit still needs
ordered polyadic construction, clock/boundary lowering, roots, typed value
profiles, generic traversal, and structural wire support in later pieces.

## Identity contract

Every embedded event carries an opaque, nonempty `durable_id`.  Builders assign
it before a JSON-pointer coordinate exists.  Persistent replay copies the ID of
every surviving event; new events receive a distinct ID.  Legacy graphs and the
version-2 compatibility reader deterministically backfill IDs in canonical event
order.  Duplicate IDs are refused.

`DurableEventIdentity` lowers the declared event tiers and IDs to a real
`tiergraph.Graph` containing `tiergraph.Item` values.  Its public operations are
the bijection used at the seam:

- legacy pointer to `DurableItemRef`;
- `DurableItemRef` to the current generic `ItemRef`; and
- `DurableItemRef` to the current legacy pointer spelling.

Thus deleting an earlier same-tier event changes a survivor's pointer and
generic coordinate without changing its durable identity.  The version-2 Form
wire intentionally remains byte-identical; structural durable wire belongs to
the later wire cutover.

## KEEP adapter

`_CompatibilityProjection` remains the version-2 adapter.  It holds only a
projection view and memoized public Python objects required by the audited
identity contracts.  It delegates event identity and generic coordinates to
the tiergraph carrier.  It does not validate or mutate graph structure, define
traversal, serialize structural tiergraph state, or manufacture identity from a
legacy pointer.  `Form.at` now crosses the durable seam before returning the
stored legacy object.

## Deferred retarget

The embedded `_tiergraph.py` graph still owns clock structure, relation
validation/order, roots, and legacy objects.  `_tiergraph_builder.py` still owns
materialization and pointer incidence.  No embedded type is deleted at this
checkpoint.  The safe retarget order is:

Pieces 2 and 8 must edit in memory without serializing between edits; a v2 wire
round-trip re-derives durable IDs positionally in canonical order and resets identity.

1. land ordered polyadic construction and replay all items with carried IDs;
2. lower clock positions/spans/timing and roots to their tiergraph profiles;
3. route containment and remaining traversal through tiergraph using durable
   references, projecting results to legacy paths only at `Form`/`Match`;
4. move typed values and structural wire/DOT authority; and
5. remove each embedded responsibility only after its piece-specific oracle is
   byte-identical and its deliberate mutation fails.

## Origin-main source-use audit (`6806617`)

The complete constructor/reader scan reconfirms these public paths into the
Piece-1 store and identity:

- `Form.parse`, `Form.from_parsed`, `Form.of`, `Form.from_dict`/`from_json`, and
  `FormBuilder.build` construct a `Form`; `dataclasses.replace` reconstructs one
  through the frozen dataclass contract. `FormBuilder.begin`, `end`,
  `add_event`, `append_ipa`, `contain`, `relate`, `add_root`, and
  `attach_timing` construct the graph consumed by `build`. Parser/profile
  constructors are `_ipa_graph`, `_cmu_graph`, `_mora_graph`, `_pinyin_graph`,
  `_panphon_graph`, `_gesture_graph`, `_gesture_backend`, and
  `_katakana_codec`.
- Public `Form.units`, `intervals`, dataclass equality/hash, `roots`, `at`,
  `direct_children`, `descendants`, `leaves`, `parents`, and `ancestors` read
  stored value, coordinate, identity, or containment state. `Form.at` performs
  the only Form-level resolve operation; there is no public `Form.resolve` in
  this revision. It resolves event, coarse `/clock/{tick}`, and refined
  `/clock/{tick}/gaps/{gap}` coordinates through the embedded graph.
- `Form.rebuild` and `Form.without_boundaries` reconstruct stored state. Public
  `Form.__iter__`, `__len__`, `__getitem__`, `__str__`, and `__repr__` expose
  projections of it, while `FormBuilder.current_tick` exposes construction
  position before `build`.
- `Form.to_ipa`, `to_dict`/`to_json`, `to_dot`, `tree`, and the remaining public
  projections (`segments`, `phones`, `attributes`, and `boundaries`) consume
  those reads. `_codecs` and `_tiergraph_json` walk or serialize the graph;
  `tiergraph_dot` derives pointer-based node identities. `_corpus` enumerates
  graphs, while `_corpus_query._unit_paths` produces the public `Match.paths`
  coordinates resolved by `Form.at`.
- Public alignment, rules/derivations, experiment and bridge operations reach
  the same state through `align`, `_rewrite_graph`, `rules`, `experiment`, and
  `bridges.vocabulary`/`kana`/`pinyin`. Their CLI entry points in
  `cli.convert` and `cli.rules` expose those results. `_tiergraph_builder` and
  its `_copy_builder` helper construct/reconstruct the embedded graph;
  `_navigation` and `_containment_projection` read it for navigation.
- `_CompatibilityProjection` reads input occurrences, intervals, timing, and
  legacy coordinates; it memoizes the public unit/interval objects.
  `_tiergraph_identity.DurableEventIdentity` supplies the durable event/item
  bijection used by `Form.at`. Neither type is publicly exported, but both sit
  on public read paths and therefore affect observable identity.

The oracle pins every store-retarget surface: roots and navigation in every
direction; event, coarse-position, and refined-gap `at` kind and aliasing;
canonical pointer
spelling and the unit-path/`Match.paths` crosswalk; version-2 wire and
self-contained wire bytes; pointer-derived DOT bytes; dataclass field and
replace behavior; equality and unequal comparison plus hash agreement and
disagreement; and memoized tuple and individual-unit object identity. Exact
UTF-8 refusal diagnostics now cover multi-source and boundary containment,
malformed and dangling pointers, invalid refined gaps, invalid interval
construction, and intervals outside a form.

Verdict: **KEEP** `_CompatibilityProjection` and the durable identity seam.
The audit proves they are not public exports, but it does not prove deletion is
safe: both mediate public object/coordinate identity and the projection caches
objects required by the frozen contracts. They may remain only as stateless
compatibility projections over the future authoritative store; neither may own
graph semantics, validation, traversal, serialization, or a second durable
identity store. This VERIFY lane deletes and retargets nothing.
