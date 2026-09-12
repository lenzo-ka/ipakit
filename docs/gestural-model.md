# The gestural model

The tier-graph backend now projects segment occurrences into declared gesture and articulatory-target tiers, and the animation traversal uses complete timed targets, then gestures, then structural segments as an explicit fallback. The larger dynamic model discussed below—gesture-set segment identity, articulator-keyed distance, and continuous phase relations—remains a historical design direction rather than implemented behavior; [representation.md](representation.md) is authoritative for the stored representation.

## The idea

A constriction is represented as a triple in the landed gesture projection:

```
gesture = (articulator, location, degree)
           what moves    where      how close
          articulator      arc       offset
```

`arc`, `offset`, and `articulator` are read from the inventory's tract declarations. This is the tract-variable framing of articulatory phonology (Browman & Goldstein): tongue-tip constriction location and degree, tongue-body constriction location and degree, lip aperture and protrusion, each an independent gestural dimension.

## Proposed unification

Under the proposed larger model, a segment would be a **set of simultaneous gestures**, and several things still modeled by separate machinery would become one thing:

| segment | gestures |
|---|---|
| `p` | lower lip @ bilabial, closure |
| `tʲ` | tongue tip @ alveolar, closure + tongue body @ palatal, approximation |
| `k͡p` | tongue dorsum @ velar, closure + lower lip @ bilabial, closure |
| `w` | tongue dorsum @ velar, approximation + lips, rounded |
| `ʘ` | lower lip @ bilabial, closure + tongue dorsum @ velar, closure (the velaric mechanism) |

In this proposed model, **secondary articulation and double articulation would share a mechanism**: multiple simultaneous gestures, differing in the degree of the second one (closure for a double articulation, approximation for a secondary). The implemented metric still declares `SECONDARY_WEIGHT = 0.5` in `ipakit/metric.py`; deriving that weight from gesture structure remains a proposal, not a property of the landed projection backend.

The proposed account would likewise represent a click as two closure gestures with a velaric airstream between them, connecting the gestural account to distinctions already recorded featurally.

## Proposed distance change

The current metric best-matches place components by nearest neighbor. The proposal would instead match gestures **by articulator** — tongue tip against tongue tip, lips against lips — with unmatched gestures charged as gaps. The landed gesture projection does not implement that replacement distance algorithm.

## What it gives the renderer

The visualization engine needs to know which organ moves, from rest, to where. `(arc, offset)` says where a constriction is; only the articulator says what travels there. Animation of `p` versus `t̼` — both labial-region constrictions — is impossible without it: one moves the lower lip, the other the tongue tip.

This is the microbeam framing: pellets on articulators, tracked relative to place targets.

## The geometry a gesture executes

A gesture says which articulator goes where, to what degree. Executing or drawing one needs the anatomy that constrains it: the fixed contours it moves against, the joints it pivots on, what carries what. [docs/tract-anatomy.md](tract-anatomy.md) specifies that — contours, articulators, degrees of freedom, and the constraint graph relating them — and sets out which of its quantities the current model declares and which such a geometry would compute instead. That correspondence is unbuilt work rather than a fact about the anchors: measured against area functions the declared consonant places hold and four of the vowels do not.

## Historical staging

1. **Minimal (landed)**: articulator is declared per place value with phone-level overrides, participates in distance, and gives the renderer its organ.
2. **Projection backend (landed)**: graph occurrences can carry gestures and timed targets, and animation consumes them with progressive fallback.
3. **Dynamic gestural model (not implemented)**: segments carry gesture sets as identity, secondary and double articulation unify, distance matches by articulator, and phase relations become continuous.

The landed declaration and projection layers provide inputs for the proposed dynamic model; they do not settle its identity, distance or phase-relation contracts.

## Open questions for the dynamic model

- Do gestures live on `Constituent` (one bundle, several gestures) or does a constituent *become* a gesture set? The former preserves the current structure; the latter is cleaner but rewrites composition.
- Lip protrusion/rounding is currently a feature (`rounded`), not a gesture. Under the model it is a lip gesture — worth unifying, or worth leaving as a feature for compatibility?
- Timing: articulatory phonology gives gestures phase relations (what makes an affricate different from a stop-fricative cluster). Our typed ties already encode simultaneity vs sequence; the gestural model would give that a finer, continuous form. Probably out of scope even then.
