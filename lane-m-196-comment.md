The tier-graph work is now landed behind the public `ipakit.Form` representation. `Form` owns the validated graph-backed store while retaining explicit compatibility projections for units, intervals, segments, boundaries, and existing rule APIs; `FormBuilder` is the public incremental construction entry, and containment navigation is available directly on `Form`.

Pairwise distance continues to expose the public `ipakit.Alignment` and `AlignmentStep` surfaces, now pinned against the graph-backed projection with operation labels, costs, normalization, and per-feature explanations intact.

Rewrite results continue to expose `Derivation`, `Step`, `Edit`, and site accounting, while the internal rewrite bridge records ordered broad-to-derived relations and trace provenance without changing the shipped rule corpus. The final schema and compatibility boundary are documented in `docs/representation.md`, with criterion-level executable coverage mapped in `docs/tiergraph-acceptance.md`.
