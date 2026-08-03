# Measuring the tract model against articulatory data

ipakit places every phone at an `(arc, offset)` in a normalized vocal tract and draws it through a mid-sagittal `Head`. Both sets of numbers were hand-placed from published anatomy, and `heads.xml` says so: *"Geometries are schematic, hand-placed from published mid-sagittal anatomy... They are not measurements."* This document is what happened when the parts of that geometry an instrument can actually see were checked against a corpus that measures the moving mid-sagittal tract directly.

`scripts/articulatory.py` is the measurement, reproducible on any mounted copy of the corpus. Everything quoted below is its output over all 48 speakers and all 8,670,344 frames.

## The corpus

The **X-Ray Microbeam Speech Production Database**, recorded at the University of Wisconsin-Madison. Eight gold pellets are tracked in the mid-sagittal plane while the speaker reads: upper lip (UL), lower lip (LL), four along the tongue from tip to back (T1-T4), and two on the mandible — the incisor (MNI) and the molar (MNM). 48 speakers are released, 22 male and 26 female, median age 21.

### Citing it

The database must be cited as:

> Westbury, John, with Greg Turner and Jim Dembowski (1994). *X-Ray Microbeam Speech Production Database User's Handbook*, v. 1.0. Waisman Center on Mental Retardation & Human Development, University of Wisconsin, Madison, WI.

The distributors also ask, in `readme.txt`, that any publication using the data carry this footnote:

> "Supported (in part) by research grant number R01 DC 00820 from the National Institute of Deafness and Other Communicative Disorders, U.S. National Institutes of Health."

The corpus is **not bundled with ipakit** and is not a dependency of anything in it. It is external data under its own terms; CI never sees it, and `scripts/articulatory.py` exits 0 with a message when it is absent.

### The format

Per speaker: a directory of `.txy` pellet tracks, matching `.wav` audio at 22050 Hz, `PAL.DAT` (the palate outline) and `PHA.DAT` (the posterior pharyngeal wall).

A `.txy` file is tab-separated text, 17 columns per row: a microsecond timestamp, then x,y for UL, LL, T1, T2, T3, T4, MNI, MNM in that order. Coordinates are microns — multiply by 1e-3 for mm — and `1000000` is the missing-value sentinel. The origin is the tip of the maxillary incisors, `+x` anterior and `+y` superior, with the x-axis on the maxillary occlusal plane (handbook §5.2.2.1). Two track files are missing from the distribution: `JW34/tp023.txy` and `JW43/tp118.txy`.

`PAL.DAT` is 9 to 52 points (median 12) of palatal midline, taken from a **dental stone cast** of the maxillary arch with a chain of gold pellets laid along the palatal vault, scanned separately from any speech (handbook §5.2.2.4.1). For a few speakers it is instead a manual trace with a hand-held pellet. Either way it is an independent measurement of a stationary object, which is what makes the palate check below a cross-check rather than a tautology.

`PHA.DAT` is **two points** for all 48 speakers — a single short line segment of pharyngeal wall, and nothing else behind the oral cavity.

## What it can and cannot ground

**The corpus is a validation source for part of the space, not a schema.** Nothing in ipakit's representation should be dropped, merged or reshaped because this instrument cannot see it. `tongue-root`, `epiglottis` and `vocal-folds`; the velum; the `+z` `channel` axis; and every place behind arc 0.5 stay exactly as they are. The blind spots below are facts about the X-ray microbeam, not facts about phonetics.

### Coverage

Two different reaches, and they are not the same number.

**Tongue position** is measurable wherever a tongue pellet goes. T1-T4 span x from about -4 mm to a median posterior reach of -64.7 mm, which on the arc mapping below is a median **arc 0.51** (range 0.45 to 0.59).

**Tract dimension** — any clearance, aperture or diameter — additionally needs a wall above the tongue, so it is bounded by `PAL.DAT`. The outline spans a median x of -5.0 to -51.8 mm, which is **arc 0.11 to a median of 0.44** (front edge 0.085 to 0.135, reach 0.38 to 0.54 across speakers). Forward of arc 0.11 there is no outline: the region covering bilabial (0.00), labiodental (0.03), dental (0.08) and the front of alveolar (0.13) has no upper wall in the data at all.

Behind that: uvular (0.56), pharyngeal (0.74), epiglottal (0.87) and glottal (1.00) have **no support of any kind**. `PHA.DAT`'s two points locate a wall but measure no articulator against it.

### What is not measured at all

- **Nasality.** There is no velum pellet, so velopharyngeal port state is unobservable. Every nasal and nasalized segment is invisible as such.
- **Voicing and phonation.** There is no laryngeal sensor. Neither is derivable from pellets — though the `.wav` audio makes both derivable *acoustically*, which is a different and available route.
- **The `channel` axis.** XRMB is mid-sagittal by construction, so sibilance and laterality — ipakit's `+z` axis — are unmeasurable in principle. This is not a new finding: `channel`'s own declaration in `ipa.xml` already says *"the mid-sagittal plane projects this axis away, so it has no contour, only an ordering."* The corpus confirms the existing reasoning rather than contradicting it.
- **The floor of the mouth.** The tongue's upper surface is measured; the sublingual space below it is not. This matters wherever the tongue is not the lower boundary of the airway.

### The arc mapping, and its one free parameter

`arc` is a *proportion* of total tract length, and XRMB sees nothing below the oral cavity, so it cannot supply that total. The mapping used here measures arc length along the upper wall — from the midpoint of the two lip pellets, straight back to the front of the palate outline, then along the outline — and divides by the length `heads.xml` itself declares for the speaker's head: 175 mm male, 150 mm female.

That divisor is the whole of the mapping's arbitrariness, and it is worth stating what it buys, because a single divisor for everybody is visibly wrong. Under one 175 mm divisor the male and female diameter profiles diverge by up to 0.24 in normalized units; under the two declared lengths they agree to within 0.02 out to arc 0.25 and 0.09 at arc 0.35. The disagreement was the divisor, not the anatomy.

## What the measurements say

Where the re-measurement disagrees, the disagreement is stated first, because it is the more useful half.

### 1. The palate is recoverable from motion

Bin every tongue-pellet sample by x, take the upper envelope of each bin, and compare it with `PAL.DAT`.

`python scripts/articulatory.py palate`

| | |
|---|---|
| rms residual, median over 48 speakers | **0.74 mm** |
| speakers within 1.4 mm rms | **40 of 48** |
| worst speaker | 5.43 mm (JW63) |
| signed bias, median | -0.27 mm (the envelope sits just under the outline) |

The envelope agrees with `PAL.DAT` to within 0.4-1.4 mm for 40 of 48 speakers. Eight sit outside that band.

The estimator matters more than it looks. Taking the literal maximum per bin gives a median rms of 0.78 mm — indistinguishable — but a worst case of 30.7 mm, because a handful of mistracked frames own the maximum outright. The script reports the 0.999 quantile and the raw maximum side by side; the gap between the columns is exactly what those frames are worth.

Two caveats the handbook states and this measurement inherits. First, an outline *may* have been extended behind the cast's reach using extreme T3/T4 positions, which would make its dorsal end partly circular with what is being compared to it. Second, the dorsal end lies under the soft palate, which moves, so a single outline there approximates a boundary that is not fixed.

### 2. The palate is a hard boundary

Signed clearance, tongue y minus palate y, pooled over every tongue sample that falls under the outline.

`python scripts/articulatory.py clearance`

| tongue y minus palate y | samples |
|---|---|
| -0.75 mm | 509,510 |
| -0.50 mm | 452,470 |
| -0.25 mm | 255,383 |
| **0.00 mm** | **102,597** |
| +0.25 mm | 37,951 |
| +0.50 mm | 11,751 |
| +0.75 mm | 3,217 |
| +1.00 mm | 798 |
| +1.25 mm | 231 |

Of **27,854,608** tongue samples that fall under the outline, 54,449 sit above it (0.195%) and 732 by more than 1 mm (0.0026%).

The distribution stops at the wall. Since the wall was measured from a dental cast and the pellets from speech, this is also a check on the whole coordinate alignment between the two records, not just on the outline.

### 3. The rigid-body screen

The distance between MNI and MNM is a distance between two points on one bone. Any variation in it is measurement error.

`python scripts/articulatory.py rigid`

**14 of 48 speakers exceed 3% sd/mean**: JW57, JW32, JW53, JW19, JW49, JW34, JW24, JW25, JW54, JW42, JW51, JW62, JW18, JW39. The worst are JW57 at 31.0% and JW53 at 8.7%. The screen needs the whole track set per speaker; reading only the first 60 files misses the worst offenders and flags speakers that pass over the full corpus.

The coefficient of variation is not the whole story, and the script prints a robust version (IQR/1.349 over the median) beside it:

| speaker | cv% | robust% | max |
|---|---|---|---|
| JW57 | 31.01 | 2.26 | 189.3 mm |
| JW53 | 8.70 | 2.11 | 208.3 mm |
| JW32 | 13.22 | 25.88 | 44.3 mm |

JW57 and JW53 are clean tracks with a few catastrophic frames. **JW32 is the only speaker whose mandible track is loose throughout** — 25.9% robust variation, and both mandible pellets present in only 25.2% of frames.

Worth recording separately: mandible pellet loss is severe for several speakers regardless of cv. JW29 tracks both pellets in 4.9% of frames, JW44 in 5.3%, JW33 in 21.0%, JW32 in 25.2%, JW60 in 25.4%, JW14 in 43.5%.

### 4. The mandibular hinge migrates

For a rigid body in the plane, every point turns about one center, which lies on the perpendicular bisector of each point's displacement chord. Two mandible pellets give two bisectors and one intersection.

`python scripts/articulatory.py hinge`

Over the 34 speakers that pass the rigid-body screen, with a minimum chord of 1 mm and a minimum rotation to keep the intersection conditioned:

| | median | range |
|---|---|---|
| center x | **-64.3 mm** | -84.1 to -46.8 |
| center y | **+14.4 mm** | -10.0 to +39.8 |
| IQR of x within a speaker | 44.0 mm | 28.7 to 67.4 |
| IQR of y within a speaker | 39.9 mm | 19.7 to 64.2 |

Anatomically plausible — posterior and superior to the tooth row — with an enormous per-frame-pair spread, which is what a two-point rigid body with sub-millimetre noise gives you. Only the aggregate is worth anything.

Split by jaw opening (upper and lower quartiles of MNI height), the center migrates:

| | median | direction |
|---|---|---|
| open minus closed, **y** | **-28.8 mm** | falls in **34 of 34** speakers |
| open minus closed, x | +5.6 mm | moves back in 13 of 34 — not a direction |

**The horizontal component does not generalize** — its sign is close to a coin flip across speakers. The center's measured range is x -84 to -47 mm, median -64.

The reading stands regardless: a jaw that turned about a fixed hinge would give one center, and this gives a center that drops by nearly 3 cm between closed and open. That is rotation plus condylar glide, and an articulatory renderer would need two degrees of freedom for it — which is what `docs/tract-anatomy.md` §4.1 already specifies.

### 5. The kinematic chain

Re-express every pellet in a frame fixed to the mandible — origin at MNI, x-axis toward MNM — and compare its variance there with its variance in the head frame. What the mandible carries disappears; what an organ does on top of the mandible remains.

`python scripts/articulatory.py chain`

| pellet | variance removed, median | range over 34 speakers |
|---|---|---|
| **UL** (upper lip) | **-731%** | -2533% to -135% |
| **LL** (lower lip) | **67.5%** | 29.9% to 84.8% |
| **T1** (tongue tip) | **28.4%** | 10.2% to 62.2% |
| **T2** | **20.8%** | -42.0% to 51.5% |
| **T3** | **7.6%** | -65.0% to 29.2% |
| **T4** (tongue back) | **1.3%** | -81.9% to 25.5% |

0%, T1 28.0%, T2 21.2%, T4 6.5%; measured 7.6% and 1.3%). The speaker set differs too — 34 pass the rigid-body screen over the whole corpus, not 40.

The upper lip is the control, and it behaves as it must: it is on the maxilla, rides on nothing, and subtracting mandible motion can only *add* to its variance. If that number came out positive the frame would be wrong.

What the ordering says is worth more than any single figure. The mandible carries two thirds of the lower lip's motion, about a quarter of the tongue tip's, and — with the median at 1.3% and the range straddling zero — **none of the tongue back's**. So a renderer that hangs the whole tongue off the jaw is wrong at the back, and one that moves the tongue independently of the jaw is wrong at the front. `ipakit/tract.py` has no jaw at all, so it is neither; what this measures is the chain such a renderer would have to build.

### 6. The diameter profile

The measurable analogue of `heads.xml`'s `diameter` is the largest sagittal clearance the tract takes at each position: the maximum of `palate_y(x) - tongue_y(x)` per arc bin.

The obvious estimator for that is biased, and the bias runs in the direction that matters most. Taking the maximum per bin over whatever frames happen to reach that bin selects, at the front of the mouth, exactly the frames where the tongue is forward — and a tongue that is forward is also high. So the front of the profile is measured on its own high-tongue subset and comes out too narrow. The `bin cover%` column below is the size of the problem: at arc 0.15 only a quarter of frames put any tongue surface there.

`scripts/articulatory.py clearance` therefore reports two estimators. The second keeps only the frames whose tongue polyline spans the entire arc 0.20-0.40 window, so every bin sees one frame set and the bias is gone — at the cost of ten speakers and a third of the frames.

| arc | every frame | n | spanning frames | n | bin cover% |
|---|---|---|---|---|---|
| 0.150 | 0.636 | 48 | — | — | 24.5 |
| 0.175 | 0.800 | 48 | — | — | 55.6 |
| 0.200 | 0.894 | 48 | 0.920 | 20 | 77.3 |
| 0.225 | 0.954 | 48 | **0.976** | 38 | 87.8 |
| 0.250 | 0.968 | 48 | 0.973 | 38 | 93.6 |
| 0.275 | 0.932 | 48 | 0.972 | 38 | 95.9 |
| 0.300 | 0.854 | 48 | 0.931 | 38 | 97.6 |
| 0.325 | 0.810 | 48 | 0.861 | 38 | 98.1 |
| 0.350 | 0.755 | 48 | 0.804 | 38 | 97.9 |
| 0.375 | 0.709 | 46 | 0.759 | 38 | 97.3 |
| 0.400 | 0.673 | 37 | 0.714 | 33 | 95.7 |
| 0.425 | 0.637 | 28 | 0.668 | 11 | 88.8 |

Each speaker is normalized to their own peak; the median peak clearance is 33.1 mm.

Against what `heads.xml` declared, normalized the same way — 0.13 → 0.94, 0.32 → 1.00, 0.45 → 1.00:

- **The declared profile was far too flat.** It varied by 6% across the whole oral run; the measurement falls by 27% (spanning frames) to 30% (every frame) between arc 0.225 and arc 0.40 — two estimators built on different frame sets, agreeing to within 0.08 at every arc.
- **The declared peak sat too far back.** Measured peak arc 0.225-0.275, against a declared peak at arc 0.32-0.45.
- **Nothing forward of arc 0.20 should be quoted from this corpus.** `PAL.DAT` begins at a median arc of 0.11, so a value at arc 0.1 is at or forward of the outline's own front edge, and only a quarter of frames reach even arc 0.15.
- **Two reaches, not one.** Tongue *position* reaches a median arc 0.51; tract *dimension* needs an upper wall and so is bounded by `PAL.DAT`, whose median reach is arc 0.44 and whose front edge is arc 0.11. A single coverage figure conflates them.

#### The same shape holds for both sexes

Split by speaker sex, with each speaker's arc divided by the tract length `heads.xml` declares for that head:

| arc | male (n=22) | female (n=26) | difference |
|---|---|---|---|
| 0.200 | 0.881 | 0.903 | -0.022 |
| 0.225 | 0.953 | 0.958 | -0.005 |
| 0.250 | 0.971 | 0.955 | +0.017 |
| 0.300 | 0.886 | 0.833 | +0.053 |
| 0.350 | 0.792 | 0.718 | +0.075 |
| 0.400 | 0.714 | 0.620 | +0.094 |

The residual difference at the back is real but small against a between-speaker sd of 0.11-0.14 at the same arcs, and it points the way a shorter tract should point. Under a single 175 mm divisor for everybody the same comparison diverges by up to 0.24, so most of the apparent sex difference was the divisor.

This is the evidence for giving `adult-female` the same normalized shape as `adult-male`, scaled to its own peak, rather than leaving it alone.

### 7. Two coronal constriction zones

Where the near-contact frames pile up, for the two pellets that reach the coronal region: T1 and T2 within 3 mm of the outline.

| | median | range |
|---|---|---|
| anterior mode | **arc 0.145** | 0.107 to 0.175 |
| posterior mode | **arc 0.253** | 0.174 to 0.314 |
| separation | **0.103** | 0.050 to 0.163 |

**44 of 48 speakers show two modes**; the four that do not (JW24, JW27, JW54, JW56) show one, at arc 0.12-0.15. The modes sit at arc 0.145 and 0.253, a separation of 0.103; 0.14 is near the top of the observed range rather than typical.

The anterior mode lands almost exactly on ipakit's declared alveolar (0.13). The posterior mode at 0.253 sits past postalveolar (0.19) and just past alveolo-palatal (0.24). ipakit declares an alveolar-to-postalveolar separation of 0.06; the data says 0.10.

Nothing in `ipa.xml` was changed for this. See "The deferred respacing" below.

## What the geometry declares

`heads.xml` is read only by `Head.project`, which places a tract point in 2D. `arc` and `offset` come from per-value coordinates in `ipa.xml` and are what `ipakit.metric` reads, so nothing in `heads.xml` can reach a distance. That separation is checked rather than assumed: over all 8060 units and 9591 pairs, no distance moves and `confusion.json` regenerates byte-identical.

The adult midline, each point marked in the file with where its number came from:

| arc | aperture | |
|---|---|---|
| 0.00 | 0.16 | extrapolated — no palate outline forward of arc 0.11 |
| 0.13 | 0.17 | extrapolated |
| 0.24 | 0.18 | **measured** — the peak |
| 0.32 | 0.16 | **measured** — 0.90 of the peak |
| 0.40 | 0.13 | **measured** — 0.73 of the peak |
| 0.45 | 0.13 | extrapolated — held flat past the palate trace |
| 0.56 | 0.123 | extrapolated — the original shape, rescaled to join the measured run |
| 0.74 | 0.108 | extrapolated |
| 0.87 | 0.094 | extrapolated |
| 1.00 | 0.079 | extrapolated |

Behind the measured run the points keep their original shape, rescaled by the ratio at the seam — 0.13/0.18 for the adult male, 0.12/0.16 for the female — because they had been placed under an oral run that measurement has since put lower. The profile therefore rises to the measured peak and falls monotonically, and **represents no oropharyngeal narrowing**. A real one may exist; this corpus cannot see behind arc 0.44, so putting one in would be inventing a feature at the point the data stops.

`adult-female` takes the same normalized shape against its own peak of 0.17. The **child head is hand-placed throughout**: XRMB's speakers are young adults, median age 21, and a child's tract is not a scaling of an adult's.

The one measured relation beyond the aperture is the jaw's. `heads.xml` declares a carriage profile — the fraction of what sits at each arc that the mandible carries, 0.66 at the lips falling to 0.013 by arc 0.60 — read by `Head.jaw_carriage`. The mandible constricts nothing, so it is not an articulator; it is what the lower lip, the lower teeth and the tongue's anterior attachment ride on, and its position therefore sets how open that part of the tract can be.

Everything else in the file — the nasal branch, both dentitions, the tongue's falloff — is hand-placed and says so.

## What this corpus cannot fix in the representation

Three gaps this measurement made visible. They are **placeholders to make real**, not dead code to delete — each names something XRMB cannot measure, which is why it is still a placeholder.

`RestPosture` in `ipakit/tract.py` declares `lips`, `jaw` and `velum` as strings. They are loaded from `heads.xml` and **never read**. The velum in particular has no pellet in this corpus, so nothing here could ground it either way.

There is **no jaw articulator, no upper lip articulator and no larynx** in the model. Findings 4 and 5 are precisely about the jaw: it has two degrees of freedom rather than one, and it carries two thirds of the lower lip and a quarter of the tongue tip. That is a kinematic chain the representation currently has no place to put.

`tract_point` returns a single `(arc, offset)`. That is a **constriction locator, not an articulatory pose** — it says where the narrowest point is, not where each organ sits. Animating from it would need the chain from finding 5 and a jaw with the freedom from finding 4. `docs/tract-anatomy.md` specifies both; this is measurement supporting that specification, not a new one.

## Synthesis feasibility

Whether these numbers could drive a synthesizer splits cleanly, and the split falls on a familiar line.

**Full formant synthesis is blocked, and the two reasons for it are not independent.** F1 and F2 depend on the pharyngeal cavity, and the pharynx is unmeasured — two points of wall and no articulator against them. That one stands alone.

The second is that a sagittal distance is not an area. Converting one to the other is the Heinz & Stevens power law, `A = αd^β`, and Ericsdotter (2007) evaluates exactly that equation over two Swedish speakers and eleven Swedish vowels imaged by MRI. Her finding is that the constants are **"vowel, place and speaker specific"** — vowel identity as well as position along the tract, which is a stronger parameterization than "varies along the tract" and makes a general mapping harder rather than easier. Even with equations that specific, average absolute area errors stay under 10% at most tract places in her female speaker and exceed it at three in her male, reaching 17% at the teeth and lips; the posterior oral cavity and velopharynx are worst; and the laryngopharynx is unproblematic only in the speaker whose larynx barely moves between vowels.

What that paper also finds is that it may not matter here, and the reason is why the two blockers collapse into one. Fitting the constants to vowel, place and speaker improves the *areas* and does not improve the *formants*: "Satisfactory acoustic patterns could be predicted from mid-sagittal profiles using specific as well as general conversion rules for obtaining the area functions, while satisfactory articulatory predictions were more dependent on specification." A single equation pooled over eight speakers loses almost nothing acoustically. But she gets that result by holding the midline and the tract's termination points fixed between conditions, "which practically assured cavity lengths were preserved" — and cavity length behind arc 0.44 is precisely what this corpus cannot supply. So the distance-to-area mapping is not the load-bearing obstacle it was written as; the unmeasured pharynx is, twice over.

**Fricatives are more tractable.** The noise source sits at the constriction, and the resonance that shapes it is the cavity *anterior* to the constriction. Both are inside the measured window: the constriction location is finding 7, its degree is the clearance profile, and the anterior cavity is bounded by the palate outline and the tongue, which are exactly what this corpus measures. What it still cannot supply is the cross-sectional shape of the channel — ipakit's `channel` axis, grooved against flat, is the difference between `s` and a non-sibilant fricative at the same place, and it is the one thing a mid-sagittal instrument cannot see.

The parallel is to Klatt's cascade/parallel split, where voiced sounds run through the whole-tract cascade and frication through a parallel branch. That architecture divides sounds by whether the whole tract or only the front cavity determines the output — and that is the same boundary this corpus's coverage falls on. It is not a coincidence: both follow from where the source sits.

## Follow-ups

### The deferred respacing of `arc`

Finding 7 says the two coronal targets sit 0.10 apart and ipakit declares 0.06. **No `arc` coordinate in `ipa.xml` was changed**, deliberately. A sensitivity analysis over all 9591 pairs, perturbing only `place` arc values:

| perturbation | pairs moved | max delta | median delta | phones whose 5-NN list reorders |
|---|---|---|---|---|
| modest: postalveolar .19 → .22, alveolo-palatal .24 → .27 | 1516 (15.8%) | 0.0030 | 0.0014 | — |
| measured-scale: postalveolar .19 → .25, alveolo-palatal .24 → .30, palatal .32 → .36 | 2550 (26.6%) | 0.0060 | 0.0027 | 38 of 139 (27%) |

The magnitudes are tiny — a max delta of 0.006 against a median pairwise distance of 0.19 — but nearest-neighbor lists reorder for over a quarter of the inventory, and `nearest_phones` is user-facing: `c` goes from ȶ,k,ç to ȶ,k,q, and `d` from ȡ,b,ɟ to b,ȡ,ð. This needs its own lane with its own before/after, not a ride on a rendering change.

Three reasons it is not ready even then:

- **The evidence gives two modes, not per-place positions.** Two coronal clusters do not tell you where alveolar, postalveolar, retroflex and alveolo-palatal each sit. Real values need forced alignment against the audio so every place gets its own measured constriction location.
- **The naive edit is not applicable.** Widening postalveolar to 0.27 collides with alveolo-palatal at 0.24. Any respacing has to move the whole front region coherently.
- **`arc` is one shared scale.** Stretching the front necessarily re-proportions the back, and XRMB stops around arc 0.44 — it says nothing about uvular, pharyngeal, epiglottal or glottal. Respacing the measured part would silently reshape the unmeasured part.

### Other work this suggests

- **Forced alignment.** Every measurement here is over all frames of all utterances. With the `.wav` audio aligned to phone labels, the same script would give per-phone constriction locations and degrees instead of pooled distributions — which is what would turn finding 7 from "two modes" into declared coordinates.
- **Per-frame outlier rejection in the rigid-body screen.** Thirteen of the fourteen speakers over threshold are a threshold effect, not a loose track; rejecting frames rather than speakers would return them to the analysable set.
- **Acoustic measures from the audio.** Voicing, phonation and nasality are all unmeasurable from pellets and all derivable from the `.wav` files, which ship with the corpus and are untouched here.

## Related

- Ericsdotter, Christine (2007). "Detail in vowel area functions", *ICPhS XVI*, Saarbrücken, paper 1337, 513–516 — the evaluation of `A = αd^β` the synthesis section rests on. The `α`/`β` pair is Heinz & Stevens's; she calls them constants rather than coefficients, and the paper publishes no per-vowel area function table, only deviations and comparisons in figures.
- [docs/tract-anatomy.md](tract-anatomy.md) — the geometry this measures against; §6 names `diameter` as the aperture function and §11 asks for exactly this kind of cited source
- [docs/distance.md](distance.md) — `arc` and `offset` as the metric reads them, and why heads never touch them
- [docs/reviewing.md](reviewing.md) — why the before/after above is the shape the check takes
- `scripts/articulatory.py` — the measurement, runnable against any mounted copy of the corpus
