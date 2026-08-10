# Animation limits (H0.2)

Where the H0.2 posture-trajectory cut is knowingly weak. Each is a concrete case, tagged with how the test suite treats it: **[tested: xfail]** asserts the behavior the cut *should* have and is expected to fail until the model grows; **[tested]** is a positive assertion that passes now; **[documented]** has no test and is a known gap. The gate is `tests/test_posture_animation.py`.

## 1. Constrictions do not slide; the residual limit is gesture *timing* — [tested]

`Posture.constrictions` carries one control per articulator, and `blend` holds each at its own arc while blending only its degree. So a transition between segments on *different* articulators (e.g. `a`, tongue-root at arc 0.74, to `i`, tongue-front at arc 0.32) fades the root out and the front in, and no constriction ever sits at the phantom arc ~0.53 where neither articulator reaches — the combining-place-at-the-mean defect does not occur here. `test_articulator_change_does_not_slide_the_constriction` pins this across the whole transition. What *does* interpolate is `Posture.reading`, the weighted mean of the units' readings; but reading drives jaw close only, not a tongue closure, so its midpoint arc is a jaw approximation, not a sliding constriction. The real residual is timing, not place: both gestures fade on one *symmetric* dominance schedule (see #3), so the order in which the root releases and the front forms — which gesture leads — is not represented. That is what the two-gesture / independently-phased model (`ast-layers-gestures.md` H5–H6) adds later.

## 2. Multi-constriction segments do not blend as two closures — [documented]

Clicks (a front closure plus a velar closure with a rarefied pocket) and double articulations (`w`: bilabial + velar) carry more than one constriction in `Posture.constrictions`, but the blend treats the primary reading as the thing that moves. A trajectory through a click or a `w` interpolates the primary point and does not phase the second closure independently — so the release order of a click, and the relative timing of the two closures of a double articulation, are not represented. Positive per-frame purity still holds (the frame is a pure function of whatever Posture it is handed); what is missing is a Posture that carries two independently-phased closures.

## 3. Anticipatory / carryover phasing is not modeled — symmetric dominance only — [documented]

The blend is a symmetric dominance function of the ordinal distance to each unit: a unit's influence depends only on how far `t` is from it, the same forward and backward. Real coarticulation is asymmetric — lip rounding anticipates a rounded vowel across a preceding consonant, nasality carries over past a nasal — and none of that is captured. Every segment influences its neighbors equally in both directions.

## 4. No real timings — uniform ordinal clock only — [tested]

The dominance timeline is `[0, N-1]`, one ordinal unit per segment. A timed Form may give those units measured spans: the sampler then warps fixed-fps wall-clock samples piecewise-linearly onto this ordinal axis, with an explicit `center` (default) or `onset` anchor choice, but dominance itself stays ordinal and a long span changes sampling density rather than the blend law. That single global anchor cannot express class-specific target timing; such phasing belongs to the gesture model. This is a deliberate cut — `test_no_seconds_on_the_model_surface` keeps `blend`, `score`, and `Posture` clockless while allowing the render-side `Trajectory` to carry stamps — and the timed trajectory pins check centers, boundaries, and the old onset arithmetic; untimed input retains uniform `frames_per_unit` sampling exactly.

## 5. None-glottal resolution is the blend's, not the model's — [tested]

`glottal_aperture` returns `None` when a bundle fixes no glottal state (silence). A trajectory cannot interpolate through `None`, so `blend` resolves it before blending. That resolution is a property of `blend`, verified by `test_glottal_and_velic_never_blend_through_none`; it is *not* a claim that the resolved value is the phonetically correct glottal state for a segment that never specified one. The limit: a word built from silence-adjacent units gets a defensible-but-arbitrary glottal aperture across the gap.
