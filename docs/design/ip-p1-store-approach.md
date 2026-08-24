# IP-P1-STORE approach

**Superseded: this approach is implemented. `Form` builds one authoritative `tiergraph.Graph` natively and the embedded graph engine is deleted; this record is kept for the approach it set out. [representation.md](../representation.md) describes the current representation.**

`Form` will store one authoritative structural object: a `tiergraph.Graph` built
once when the legacy `GraphBuilder` scaffold finishes.  The existing
containment conversion becomes that construction seam.  Its result also keeps
non-authoritative compatibility indexes: legacy path to durable id/item,
durable id/item to the original public event object, clock-position objects,
root durable ids, and the small ordering/admission metadata needed to reproduce
ipakit's public traversal order.  The legacy `ipakit._tiergraph.Graph` is then
dropped; it is neither a `Form` field nor captured by a reader helper.

Public navigation constructs `tiergraph.OrderedContainment` directly over the
stored graph.  The containment view is source-free and does not construct a
graph.  `roots` resolves its construction-time durable-id list through the same
stored graph.  Compatibility unit/interval projection and serialization read
the construction-time item metadata indexed by authoritative tiergraph item
identity, not the scaffold.

`Form.at` retains ipakit's `/clock` spelling parser and exact diagnostics.  The
parser is separated from the legacy graph's object lookup: it validates a path
against an immutable coordinate index captured while constructing the
authoritative graph.  For an event coordinate, `Form.at` converts the indexed
durable id to `tiergraph.DurableItemRef`, asks the authoritative graph to resolve
that id, and uses the resulting item reference to select the original public
event object.  For coarse/refined clock coordinates it selects the indexed
public clock object after the same parse/validation step.  Thus malformed,
dangling, and invalid refined-gap paths retain the legacy refusal bytes while
resolution never consults the scaffold.  Event paths remain spelling only;
durable tiergraph item identity is authoritative.

The legacy graph remains temporarily allowlisted only inside construction and
wire/parser bridges that produce the construction input.  Its reason is
`scaffold`, its served contract is byte-identical Piece-1 construction and
compatibility projection, its evidence is the Piece-1 oracle plus the P1
one-store boundary test, and its removal date is P9.
