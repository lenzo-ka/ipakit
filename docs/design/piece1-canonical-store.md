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

## Origin-main audit reconfirmation

The source and documentation scan at `f0d3b4a` found the same public routes as
the earlier audit: `Form` units/intervals/dataclass behavior; builder ticks and
opaque handles; roots/navigation paths; `Form.at`; `Match.paths`; version-2
wire; and DOT.  It additionally reconfirmed public CLI and bridge consumers of
those same routes, but found no public export of the embedded graph,
`_CompatibilityProjection`, or the durable identity seam.  Nothing changes the
KEEP verdict.
