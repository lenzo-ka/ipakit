# The gestural model (design note, post-release)

*Not implemented. This records a model that the current representation is converging on, so the reasoning survives the release. The minimal articulator work (articulator declared per place value, phone-level overrides, an articulator term in distance) is a deliberate first step toward it and does not conflict with it.*

## The idea

A constriction is a triple, and ipakit currently carries two thirds of it:

```
gesture = (articulator, location, degree)
           what moves    where      how close
             [gap]        arc        offset
```

`arc` and `offset` are already in the data as tract coordinates (`docs/ties.md`). The articulator — the organ that travels — is the missing third. This is the tract-variable framing of articulatory phonology (Browman & Goldstein): tongue-tip constriction location and degree, tongue-body constriction location and degree, lip aperture and protrusion, each an independent gestural dimension.

## What it unifies

Once articulator is explicit, a segment is a **set of simultaneous gestures**, and several things ipakit currently models by separate machinery become one thing:

| segment | gestures |
|---|---|
| `p` | lower lip @ bilabial, closure |
| `tʲ` | tongue tip @ alveolar, closure + tongue body @ palatal, approximation |
| `k͡p` | tongue dorsum @ velar, closure + lower lip @ bilabial, closure |
| `w` | tongue dorsum @ velar, approximation + lips, rounded |
| `ʘ` | lower lip @ bilabial, closure + tongue dorsum @ velar, closure (the velaric mechanism) |

So **secondary articulation and double articulation are not different mechanisms** — both are multiple simultaneous gestures, differing only in the degree of the second one (closure for a double articulation, approximation for a secondary). The current `SECONDARY_WEIGHT = 0.5` in `ipakit/metric.py` is a fudge factor standing in for exactly this distinction; the gestural model derives it instead of asserting it.

Clicks likewise stop being a special case: a click *is* two closure gestures with a velaric airstream between them, which is what the airstream correction already recorded featurally.

## What it fixes in distance

Today the metric best-matches place components by nearest neighbour, which is a heuristic. With articulators, gestures **match by articulator** — tongue tip against tongue tip, lips against lips — which is the natural key and needs no heuristic at all. Unmatched gestures (one segment has a lip gesture the other lacks) become gaps, exactly as constituents do now in the ordered alignment.

## What it gives the renderer

The visualization engine needs to know which organ moves, from rest, to where. `(arc, offset)` says where a constriction is; only the articulator says what travels there. Animation of `p` versus `t̼` — both labial-region constrictions — is impossible without it: one moves the lower lip, the other the tongue tip.

This is the microbeam framing: pellets on articulators, tracked relative to place targets.

## Staging

1. **Minimal (shipped pre-release)**: articulator declared per place value with phone-level overrides where it differs (linguolabial, retroflex); `articulator` re-typed categorical over the real organ inventory; one articulator term in distance. Closes the visible gap (`t̼`, `t̺`, `t̻` were invisible to the metric) and gives the renderer its organ.
2. **Gestural (post-release)**: segments carry gesture sets; secondary and double articulation unify; distance matches by articulator and drops the secondary weight fudge; the visualization engine consumes gestures directly.

Step 1 is strictly a subset of what step 2 needs, so nothing done now has to be undone.

## Open questions for step 2

- Do gestures live on `Constituent` (one bundle, several gestures) or does a constituent *become* a gesture set? The former preserves the current structure; the latter is cleaner but rewrites composition.
- Lip protrusion/rounding is currently a feature (`rounded`), not a gesture. Under the model it is a lip gesture — worth unifying, or worth leaving as a feature for compatibility?
- Timing: articulatory phonology gives gestures phase relations (what makes an affricate different from a stop-fricative cluster). Our typed ties already encode simultaneity vs sequence; the gestural model would give that a finer, continuous form. Probably out of scope even then.
