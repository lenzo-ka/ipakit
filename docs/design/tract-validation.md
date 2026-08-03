# Tract geometry against measured area functions: assessment

Does the tract posture `ipakit` computes from a phone's declared features agree with published articulatory measurement — and can that agreement be stated as one reproducible number?

**Verdict: SPLIT. The consonant check holds and should be believed; the vowel rank correlation is a free parameter wearing a statistic's clothes, and is refused.** The declared place arcs for `bilabial` and `alveolar` land inside the measured occlusion of all four imaged stops and nasals at those places, absolutely, with no fitting. The one external check this geometry had before (`docs/articulatory-data.md`, against the X-Ray Microbeam database) can see nothing behind `arc` 0.44 and nothing below the oral cavity; this source reaches the glottis. The vowel figure does not survive: the place of maximum constriction is not recoverable from an area function without deciding where the vocal tract begins, the source itself says the narrowing at 4–5 cm is the piriform sinuses and not a lingual constriction, and Spearman's ρ over the eleven imaged vowels runs from −0.02 to +0.73 as that cutoff moves through the range a reader could defend. There is no plateau to report a number from. Two instruments were tried and both move the same way.

**What the measurement did expose is a modeling limit worth a defect report.** A vowel takes `arc` from `backness` and from nothing else, so `u o ɑ ɔ ʌ` are all `back` and all sit at `arc` 0.56. The MRI data spreads those five over `arc` 0.38 to 0.72 — a third of the tract — in two clean groups, and Gaines et al. reach the same two groups from a comprehensive sample of a continuous articulatory model. Both sources say the back vowels use two tongue-body constriction locations. `ipakit` has one, at a position where the data puts neither group.

The assessment changed no code, no data and no tests. It adds this document, `scripts/areafunctions.py`, and a changelog line.

## Summary of findings

| Question | Finding |
|---|---|
| Do the two coordinate systems align at all? | **Yes.** Both are proportional position along the tract midline. Story et al. normalize by a per-vowel measured tract length; `arc` matches normalized arclength on the adult-male midline to within 0.027. No fudge factor is needed for the axis. |
| Can the imaged phonemes be identified reliably from a mangled text layer? | **Yes, two ways.** Column order is fixed by the example words in Table II, and confirmed independently by the natural-speech formants in Table IV against Peterson & Barney. The ragged rows are self-checking: section counts derived from the published tract lengths predict every row width exactly. |
| Do the declared consonant place arcs land in the measured occlusion? | **4 of 6 inside; 2 velars outside by 0.018 and 0.064 of tract length.** `bilabial` 0.00 and `alveolar` 0.13 are inside for `p m t n`. |
| Is the velar miss a defect? | **No — it is allophonic, and the direction is right.** `k` (before a back vowel) misses by 0.018, `ŋ` (imagined in a neutral context, so fronted) by 0.064. The declared 0.45 is posterior to both. |
| Does a rank correlation over the vowel set survive? | **No.** ρ over eleven vowels is −0.02 to +0.73 as the laryngeal cutoff moves from 3.0 cm to 8.0 cm; pairwise concordance over the 42 pairs the model orders is 22/42 to 33/42 over the same range. |
| Does a softer instrument rescue it? | **No.** A narrowness-weighted centroid moves +0.09 to +0.68 over the same cutoffs, and adds a weighting exponent as a second free parameter. |
| Is "place of maximum constriction" even defined for every vowel? | **No.** For `æ` no supralaryngeal local minimum is narrower than 1.94 cm²; for `ʌ` two minima tie at 0.66 cm² and the argmin is decided by index order. |
| Do the back vowels split into two constriction locations? | **Yes, and window-free.** `u o` at `arc` 0.375/0.380 (0.32 and 0.15 cm²); `ɑ ɔ ʌ` at `arc` 0.60–0.72. `ipakit` puts all five at 0.56. |
| Does the Gaines discreteness result hold against `ipakit`'s constrictions? | **The question is circular for `ipakit` and cannot be answered.** Its constriction locations are discrete because `backness` is a five-valued declared feature. Discreteness is an input, not a result. |
| Is there a substantive Gaines comparison? | **Yes, one.** Gaines reports three tongue-body locations: palatal, velar/uvular, lower pharyngeal. A vowel's `arc` sweeps palatal (0.32) to uvular (0.56) and stops. The third has no vowel that reaches it, though `place` declares `pharyngeal` at 0.74. |
| Does `docs/tract-anatomy.md` §6 hold? | **Untested, and contradicted where it can be tested.** It equates the declared `arc` with the centerline position of minimum aperture. For `ɝ`, `u`, `o` and `ɑ` they are not the same place — §6 below. |
| Should a script ship? | **Yes — `scripts/areafunctions.py`**, in the shape `docs/reviewing.md` already names for a comparison against external data: one command per measurement, a shape assertion so a bad read cannot report clean numbers, and a clean exit when the source is not mounted, because it never is in CI. |

## Sources

- Story, Titze & Hoffman, "Vocal tract area functions from magnetic resonance imaging", *J. Acoust. Soc. Am.* 100(1), 537–554, July 1996. <https://doi.org/10.1121/1.415960>
- Gaines, Kim, Parrell, Ramanarayanan, Nagarajan & Houde, "Discrete constriction locations describe a comprehensive range of vocal tract shapes in the Maeda model", *JASA Express Letters* 1(12), 124402, 2021. <https://doi.org/10.1121/10.0009058>
- Peterson & Barney, "Control methods used in a study of the vowels", *J. Acoust. Soc. Am.* 24(2), 175–184, 1952 — used only to confirm which column of Story et al. Table III is which vowel.

Everything measured below comes from Table III (p. 546): equal-interval area functions, 0.396825 cm per section, section 1 at the glottal end and the last section at the mouth termination, for 18 shapes from one adult male subject. The numbers in this document are measurements of that fixed published table and cannot drift. The declarations they are compared against can: they are `place`, `backness` and `height` in `ipakit/data/ipa.xml`, and the midlines in `ipakit/data/heads.xml`. `scripts/areafunctions.py` reads both sides live, so re-running it is how this document is checked — but `make check` cannot, for the reason in §8.

## 1. The comparison is possible in principle, and that was not obvious

`arc` is documented as "proportional position along the tract midline, 0 at the lips to 1 at the glottis". Story et al. give cross-sectional area against distance from the glottis in centimeters, with a measured tract length per shape (16.67 to 18.25 cm). Dividing one by the other gives the same quantity `arc` claims to be, in the same direction, with the same two endpoints. That is a genuine alignment and not a rescaling chosen to make a number come out.

Two things had to be checked before relying on it.

**Is `arc` actually proportional to arclength?** It is declared per feature value, and the head midline is hand-placed to realize it, so the two could have drifted apart without anything noticing. Measured over every shipped polyline, the largest disagreement between a point's declared `arc` and its normalized cumulative arclength is 0.0636, on the `child` head's nasal branch. The oral midlines are tighter and the worst of them is 0.062, again on `child`. That is not negligible: the tightest measured closure in §2 spans 0.045 of the tract, so the ambiguity is comparable to the margin. It is carried rather than waved away — every verdict in §2 was taken a second time with each declared `arc` read as its own midline's arclength instead (`bilabial` 0.000, `alveolar` 0.157, `velar` 0.446), and not one of them changes. The worst point is on a nasal branch, whose arcs name no place, so nothing in §2 rests on it; the child midline is the one at the edge of what this section can carry. `scripts/invariants.py` holds the gap of every polyline, pinned rather than bounded, and that is where the figures live — see §6.

**Is the vowel identification right?** The PDF's text layer uses a custom encoding that mangles IPA, so the column headings of Table III cannot be trusted. They do not have to be. Column order follows Table II (p. 539), which gives an example word for each imaged phoneme and extracts cleanly. That identification is then confirmed independently by Table IV (p. 548), whose natural-speech formants track Peterson & Barney's male averages column by column — including the low F3 of 2124 Hz that identifies column 11 as the rhotic. The ragged rows of Table III are self-checking as well: the published tract lengths divided by the section interval give 42, 42, 40, 42, 44, 44, 44, 44, 44, 46, 44, 46, 44, 44, 44, 44, 44, 44 sections, and those counts predict the width of every short row in the table exactly.

## 2. The consonant check holds

An occlusion has a location the data states outright: the sections where the area is zero. There is no window to choose and no argmin to be fragile.

Occlusion extent as `arc` from the lips, against the arc declared for the phone's place:

| phone | place | declared `arc` | measured occlusion (area = 0) | |
|---|---|---|---|---|
| `p` | bilabial | 0.00 | 0.000–0.023 | inside |
| `m` | bilabial | 0.00 | 0.000–0.068 | inside |
| `t` | alveolar | 0.13 | 0.114–0.159 | inside |
| `n` | alveolar | 0.13 | 0.091–0.227 | inside |
| `k` | velar | 0.45 | 0.409–0.432 | outside by 0.018 |
| `ŋ` | velar | 0.45 | 0.227–0.386 | outside by 0.064 |

Two places out of three land absolutely, on a hand-placed schematic scale that was never fitted to anything. `t` is the sharpest case: a two-section closure spanning 0.045 of the tract, and the declared 0.13 is inside it.

The velar miss is in one direction — declared posterior of measured, both times — and the size of the miss tracks the vowel context, which is what makes it allophonic rather than a defect. `k` was imaged in *cut*, before a back vowel, and misses by 0.018 of tract length (0.3 cm). `ŋ` was imaged with a neutral vowel imagined either side, which fronts a velar, and misses by 0.064 (1.1 cm). A declared value that sits behind a backed allophone by half a centimeter and behind a fronted one by a centimeter is a value sitting at the back of the velar range, not a wrong one. It is worth recording that the range exists and that 0.45 is at its posterior edge, because the same speaker's velar vowels agree with the fronted reading — see §4.

## 3. The vowel rank correlation is refused

Story et al. report an area function, not a constriction. Turning one into the other means taking the minimum somewhere, and "somewhere" is the whole problem.

Taken over the entire tract, the minimum is in the larynx for eight of the eleven vowels and at the lips for `o` and `ʊ`. Neither is a tongue-body constriction. The source explains the first (p. 544):

> A general observation with regard to all of the vocal tract shapes is that they show a widening of the tract above the glottis that starts at 2 to 3 cm and narrows again at approximately 4 to 5 cm. This is primarily due to the piriform sinuses merging with the main vocal tract tube.

So the narrowing at 4–5 cm is an artifact of side branches merging into the tube, present in every shape, and it has to be excluded. Excluding it requires a cutoff, and nothing fixes the cutoff. The paper says "approximately 4 to 5 cm"; the piriform contribution does not stop at a line.

Spearman's ρ between the declared vowel `arc` and the windowed argmin, over the eleven imaged vowels, as the glottal-end cutoff moves (labial exclusion held at 2 cm, which changes nothing over 1–4 cm):

| cutoff | 3.0 | 4.0 | 4.5 | 5.0 | 6.0 | 7.0 | 8.0 |
|---|---|---|---|---|---|---|---|
| ρ | −0.02 | −0.02 | +0.05 | +0.43 | +0.49 | +0.73 | +0.66 |

Pairwise concordance says the same thing without the rank machinery. Of the 55 vowel pairs, `ipakit` orders 42 — the other 13 are ties, because `i ɛ æ` share `front` and `u o ɑ ɔ ʌ` share `back`. Concordant pairs run 22/42 at a 4.5 cm cutoff and 33/42 at 7.0 cm.

A softer instrument does not rescue it. Replacing the argmin with a centroid of the area function weighted by how far below the vowel's own mean each section falls gives ρ of +0.19, +0.24, +0.34, +0.47, +0.68, +0.68 over cutoffs 3.0 to 7.0 — the same swing, plus a weighting exponent as a second dial (raising it to the fourth power moves ρ at a 5 cm cutoff from +0.47 to +0.38).

**Any figure reported here is a report of the cutoff, not of the model.** A reader handed "ρ = 0.49" cannot tell that 0.05 and 0.73 were equally available. That is the whole objection.

There is a second reason to refuse, independent of the window. For an open vowel the quantity being ranked does not exist. `æ` has no supralaryngeal local minimum narrower than 1.94 cm², against `i`'s 0.10 cm² — its area function is broad and its argmin follows whichever edge the window puts nearest, moving from `arc` 0.66 to 0.37 as the cutoff goes from 5 cm to 7 cm. `ʌ` has two local minima at exactly 0.66 cm², so its argmin is decided by which index the loop reaches first. Story et al. call `æ` "a transition vowel between the front and back categories"; the data agrees by declining to give it a place.

## 4. What survives the window

Drop the argmin and look at the whole set of local minima with their depths. That is window-free: a minimum's existence and its depth relative to its neighbors do not depend on where the analysis is told to start.

Supralaryngeal local minima per vowel, as `arc` from the lips with area in cm². The 4–5 cm piriform run is marked `*` and is the same artifact in every column.

| vowel | declared `arc` | minima (`arc` / cm²) |
|---|---|---|
| `i` | 0.32 | 0.77/2.49\* 0.70/3.78\* 0.63/4.43 **0.27/0.10** 0.20/0.24 0.15/0.28 |
| `ɪ` | 0.37 | 0.77/0.92\* 0.63/3.32 0.56/3.79 0.35/1.44 **0.25/0.75** 0.13/1.70 |
| `ɛ` | 0.32 | 0.76/0.72\* 0.39/1.78 **0.26/1.36** 0.11/2.11 |
| `æ` | 0.32 | 0.75/0.69\* 0.65/1.94 0.51/3.69 0.44/3.20 0.37/3.19 0.13/4.39 0.08/4.23 |
| `ʌ` | 0.56 | 0.72/0.66\* **0.65/0.66** 0.60/0.91 0.56/1.06 |
| `ɑ` | 0.56 | 0.72/0.26\* **0.67/0.23** 0.60/0.28 0.51/1.05 0.12/3.87 |
| `ɔ` | 0.56 | 0.72/0.43\* **0.65/0.32** 0.49/0.58 0.40/2.41 |
| `o` | 0.56 | 0.81/0.82\* 0.60/1.28 0.53/0.89 **0.38/0.32** |
| `ʊ` | 0.50 | 0.62/0.61 0.58/0.75 **0.53/0.53** 0.03/0.15 |
| `u` | 0.56 | 0.79/2.10\* 0.58/3.16 **0.38/0.15** 0.03/0.41 |
| `ɝ` | 0.44 | 0.74/0.77\* 0.51/2.01 **0.22/0.44** |

Three things fall out that no choice of window can move.

**The back vowels use two locations, not one.** `u` and `o` constrict at `arc` 0.380 and 0.375, at 0.15 and 0.32 cm², with nothing else in either column within a factor of three. `ɑ`, `ɔ` and `ʌ` constrict in a band at `arc` 0.60–0.72, four times narrower than anything forward of it in their columns. The gap between the two groups is 0.22 of tract length — about 4 cm — and no vowel of this speaker constricts inside it. `ipakit` places all five at 0.56, in that gap.

**`i` is forward of `ɑ`, robustly.** `i` constricts at `arc` 0.27 with the deepest constriction in the whole vowel set (0.10 cm²), `ɑ` at 0.67, and the ordering survives every cutoff and every instrument tried. `ɑ`'s narrowing is pharyngeal and it is where the data puts it. This is the claim that would have carried a rank correlation, and it does not need one.

**`ɝ` is the most anterior constriction in the set.** At `arc` 0.22 it is forward of `i`, which is the geometric signature of American English r-coloring. `ipakit` places it at 0.44, the most posterior of everything it calls non-back. The model is not silent about this: `rhotacized` declares no coordinates, so `unmodelled()` returns it with kind `unmodelled` and a renderer annotates rather than invents. The annotation layer is doing its job. The `arc` is still 0.22 away from the measurement, which means a figure drawn from it puts the constriction in the wrong place *and* prints a note saying something is missing, and a reader has no way to know the note explains the error.

## 5. Gaines, and a question that turns out to be circular

The issue hoped that if `ipakit`'s constrictions were discrete and Gaines et al.'s were too, that would show discreteness is not an artifact of starting from phonological categories.

**For `ipakit` it is exactly that artifact, so the corroboration is not available.** A vowel's `arc` is read from `backness`, which declares five values. Five discrete constriction locations come out because five went in. Gaines et al.'s result is interesting precisely because theirs does not: they sampled about 10⁶ vocoid-producing configurations from six continuous Maeda parameters, and the input distributions and the resulting formants are unimodal while the tongue-body constriction location is trimodal (124402-4 to 124402-5). Nothing in `ipakit` reproduces that argument, and running the analysis over its declarations would be measuring the shape of the IPA vowel chart.

Nor can the two be aligned numerically. Gaines et al. report constriction location as a polar angle from an origin at the center of the Maeda shape space, clockwise from the left horizontal — 95° palatal, 120° velar/uvular, 180° lower pharyngeal. Mapping an angle about a tongue-centered origin onto arclength from the lips needs the Maeda geometry, which is not what the paper reports. Only the ordinal content transfers.

Ordinally, there is one substantive comparison, and `ipakit` fails it.

| Gaines tongue-body location | `ipakit` |
|---|---|
| palatal | `backness=front`, `arc` 0.32 — the same value `place=palatal` declares |
| velar/uvular | `backness=back`, `arc` 0.56 — the same value `place=uvular` declares |
| lower pharyngeal | **nothing.** `place=pharyngeal` declares 0.74; no `backness` value reaches it |

The `tract.py` module docstring states this as design: "vowels from their backness (the tongue-body constriction sweeps the palatal..uvular span)". Both external sources say the span is short by one location, and Story et al. say which vowels use it: the same `ɑ ɔ ʌ` that sit at `arc` 0.60–0.72 in §4, behind `uvular` and near `pharyngeal`.

The two sources are independent — one MRI subject, one comprehensive sample of a model built from different speakers in a different language — and they agree on a location `ipakit` does not have.

## 6. Reported, not fixed

Three findings for the lanes that own the files. This lane touched none of them.

[#127](https://github.com/lenzo-ka/ipakit/issues/127) took up all three; each carries a superseded line below saying what it did, and only D3 is closed. The documentation correction under them was taken up separately by [#125](https://github.com/lenzo-ka/ipakit/issues/125) and is closed.

**Superseded by [#127](https://github.com/lenzo-ka/ipakit/issues/127): the defect stands and is now a stated limit. Every repair the declaration vocabulary can express was tried, including both named at the end of this entry, and each is refused by measurement; `tests/test_vowel_tract_limit.py` pins the limit and each refusal, so it can only change deliberately.**

**D1 — a vowel's constriction location cannot distinguish velar from pharyngeal.** `tract_point` reads `arc` from `backness` alone; `height` moves `offset` only. `u` and `ɑ` are both `backness=back`, so they share `arc` 0.56 exactly, and the model has no way to say that one constricts at the velum and the other in the pharynx. Reproducing case:

```python
from ipakit.features import IPAFeatures
from ipakit.tract import tract_point
f = IPAFeatures()
tract_point(f, f.get_features("u")).arc    # 0.56
tract_point(f, f.get_features("ɑ")).arc    # 0.56
```

Measured, those two constrict 5.6 cm apart in a 17.5 cm tract. `arc` feeds `ipakit.metric` through `_sagittal`, so this is not confined to drawing. It is a limit of the declarations rather than a coding error, and closing it means either extending `backness` past `uvular` or letting `height` contribute to `arc` for a vowel — both changes to `ipa.xml`, both with a distance sweep behind them, and neither is this lane's to make.

**Superseded by [#127](https://github.com/lenzo-ka/ipakit/issues/127): the shared point is what the measurement asks for. `ʌ` and `ɔ` both constrict at `arc` 0.65 in §4's own table, so giving them one tract point is right; what they do not share is a lip aperture, and that is the unmodelled thing.**

**D2 — `ʌ` and `ɔ` are the same point in tract space.** Both are `back` and `open-mid`, so both yield `arc` 0.56, `offset` 0.16. They differ only in `rounded`, which the geometry does not carry (`docs/tract-anatomy.md` §4.4 says so plainly, and the annotation layer reports it). The posture is therefore identical for two segments the data separates. Worth knowing before anyone reads a drawn posture as a claim about the sound.

**Superseded by [#127](https://github.com/lenzo-ka/ipakit/issues/127), and closed. `check_head_arcs` in `scripts/invariants.py` gates the three relationships this entry runs together as three, over the nasal branches as well as the midlines, pinning each gap rather than bounding it — a bound this data would pass also permits a vertex to sit where the next declared place lives.**

**D3 — `arc` has two meanings and nothing holds them together.** It is declared per feature value in `ipa.xml`, and separately realized as position along a hand-placed midline in `heads.xml`. The largest disagreement between a declared `arc` and its own midline's normalized arclength is 0.027 (adult-male), 0.035 (adult-female), 0.062 (child). Heads never affect distance, so no answer is wrong today, but §1 of this assessment depends on the two agreeing and the child head is at the edge of what it can carry. An invariant over the shipped midlines would cost a few lines and is the sort of thing `scripts/invariants.py` already does.

**Superseded by [#125](https://github.com/lenzo-ka/ipakit/issues/125), and closed. The sentence was replaced rather than corrected: §6 now states the correspondence as unbuilt work and computes the half of it a reader can check, in a `python` block `scripts/docexamples.py` executes, so a geometric claim there stands only where something checks it. This entry stops quoting the old wording — the words it recommended changing are gone, and a quotation of them would read as a citation and would not be one.**

**And one correction to the documentation.** `docs/tract-anatomy.md` §6 gives constriction location as the centerline position of minimum aperture, which is what `arc` currently declares, and then says that the current model's hand-placed anchors are what this geometry would compute. Against the one measured aperture function available, that holds for `p m t n` and for `i` to within 0.05, and fails for `ɝ` (0.44 declared, 0.22 measured), `u` and `o` (0.56 declared, 0.38 measured) and `ɑ` (0.56 declared, 0.67 measured). The section is a specification of work not yet done, so it is not wrong to state the intent — but it states an equivalence that has never been checked and is now known to fail in four places, and it should say so.

## 7. What it would take to get a number

A defensible agreement figure over vowels needs one of these, and none is cheap.

**An area function with the piriform sinuses separated out.** The cutoff problem is entirely the side branches merging into the tube. A source that reports them as branches, rather than folded into the main area, removes the free parameter and the argmin becomes well defined for every vowel except the genuinely open ones.

**Superseded by [#123](https://github.com/lenzo-ka/ipakit/issues/123), and answered. Wood was obtained, and a second measured set with it — Yang & Kasuya's three Japanese speakers, area functions printed as numbers. Both were read by band inclusion, the instrument this section asks for below, and the answer is that no agreement figure over vowels is available at all: one symbol's measured location moves up to 0.284 of tract length between sources, more than the declared span it would have to resolve. See [vowel-constriction.md](vowel-constriction.md).**

**More than one speaker.** Story et al. image one adult male, and the paper says the shapes "may be somewhat centralized". The velar range in §2 and the back-vowel split in §4 are that speaker's anatomy plus that session's coarticulation. Two of the three sources cited by Gaines et al. for discrete constriction locations — Wood's 40 subjects across 13 languages, and Boë et al.'s Maeda simulations — would be the right shape of evidence, and neither is in hand.

**A constriction definition that does not argmin.** The tongue-body constriction is a region, not a point, and both external sources treat it as one: Gaines et al. take a minimum over a bounded angular sector rather than over the tract, and Story et al. describe constrictions as pharyngeal or oral rather than as a coordinate. A location claim stated as a band, checked for inclusion the way §2 checks the occlusions, is defensible where a point estimate is not. That is what §4 does, and it is why §4 survives and §3 does not.

## 8. How to re-run this

`scripts/areafunctions.py` is every measurement above, one subcommand each.

```console
$ python scripts/areafunctions.py table        # parse it, and check the parse
$ python scripts/areafunctions.py occlusions   # section 2
$ python scripts/areafunctions.py vowels       # section 4
$ python scripts/areafunctions.py stability    # section 3
$ python scripts/areafunctions.py arc          # section 1, and D3
```

The paper is copyrighted and outside the repository by policy, so it is not bundled and `make check` cannot run any of this. `--source`, or `$IPAKIT_STORY1996_TEXT`, points at a text extraction of your own copy; without one every subcommand prints why and exits 0. That is the shape `scripts/articulatory.py` already uses for the X-Ray Microbeam database, for the same reason.

A run over a bad extraction has to fail rather than report clean numbers over nothing, and Table III makes that easy to enforce. The table is column-ragged, and nothing in a short row says which columns are still open — but the published tract lengths divided by the section interval do, so the parse asserts that those counts predict every row width and every column length. A misread digit or a dropped column breaks the prediction at once. The vowel symbols are never read: the text layer's encoding mangles them, and column order comes from Table II's example words instead.

`arc` needs no source and is the exception: it reads only the shipped heads. It is in this script because every other measurement here assumes `arc` is the proportional midline position it says it is, and nothing else had ever checked that.

## Related

- [docs/tract-anatomy.md](../tract-anatomy.md) — the geometry this checks, and §6 the claim it tests
- [docs/articulatory-data.md](../articulatory-data.md) — the measured data already in `heads.xml`, and what that instrument cannot see
- [docs/distance.md](../distance.md) — where `arc` and `offset` reach the metric
