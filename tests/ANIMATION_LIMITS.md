# Animation limits (H0.2)

Where the H0.2 posture-trajectory cut is knowingly weak. Each is a concrete case, tagged with how the test suite treats it: **[tested: xfail]** asserts the behavior the cut *should* have and is expected to fail until the model grows; **[tested]** is a positive assertion that passes now; **[documented]** has no test and is a known gap. The gate is `tests/test_posture_animation.py`.

## 1. Articulator-change transitions slide one primary point — [tested: xfail]

A `Posture.reading` is a single primary constriction point. Blending between two segments on *different* articulators (e.g. `a`, tongue-root at arc 0.74, to `i`, tongue-front at arc 0.32) interpolates that one point, so the midpoint sits at arc ~0.53, where neither the tongue-root nor the tongue-front actually constricts — a phantom position, the same defect as a combining place drawn at its components' mean. A true transition fades one gesture out while the other fades in; that needs two overlapping gestures per frame, which this cut does not model. `test_articulator_change_slides_xfail` asserts the midpoint does *not* land between the two arcs and is xfail until the two-gesture model lands.

## 2. Multi-constriction segments do not blend as two closures — [documented]

Clicks (a front closure plus a velar closure with a rarefied pocket) and double articulations (`w`: bilabial + velar) carry more than one constriction in `Posture.constrictions`, but the blend treats the primary reading as the thing that moves. A trajectory through a click or a `w` interpolates the primary point and does not phase the second closure independently — so the release order of a click, and the relative timing of the two closures of a double articulation, are not represented. Positive per-frame purity still holds (the frame is a pure function of whatever Posture it is handed); what is missing is a Posture that carries two independently-phased closures.

## 3. Anticipatory / carryover phasing is not modeled — symmetric dominance only — [documented]

The blend is a symmetric dominance function of the ordinal distance to each unit: a unit's influence depends only on how far `t` is from it, the same forward and backward. Real coarticulation is asymmetric — lip rounding anticipates a rounded vowel across a preceding consonant, nasality carries over past a nasal — and none of that is captured. Every segment influences its neighbors equally in both directions.

## 4. No real timings — uniform ordinal clock only — [tested]

The timeline is `[0, N-1]`, one ordinal unit per segment, every segment the same width. There are no per-segment durations, no seconds, no tempo: a stop and a long vowel occupy one unit each. This is a deliberate cut — the model surface carries articulation, not a clock — and it is enforced positively: `test_no_seconds_on_the_model_surface` checks that neither `blend`/`score` nor `Posture` grows a time-shaped parameter or field, and `test_timeline_endpoints_and_centers_land_on_units` checks the ordinal clock lands each integer `t` on its unit. The *limit* is that mapping frames to real time is left entirely to the renderer (`frames_per_unit`), and this cut asserts nothing about whether that mapping is phonetically faithful.

## 5. None-glottal resolution is the blend's, not the model's — [tested]

`glottal_aperture` returns `None` when a bundle fixes no glottal state (silence). A trajectory cannot interpolate through `None`, so `blend` resolves it before blending. That resolution is a property of `blend`, verified by `test_glottal_and_velic_never_blend_through_none`; it is *not* a claim that the resolved value is the phonetically correct glottal state for a segment that never specified one. The limit: a word built from silence-adjacent units gets a defensible-but-arbitrary glottal aperture across the gap.
