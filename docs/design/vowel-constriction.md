# Where a vowel constricts: assessment

[#123](https://github.com/lenzo-ka/ipakit/issues/123) is that a vowel reads its tract position from `backness` and nothing else, so `u o ɑ ɔ ʌ` all sit at `arc` 0.56. It was left open rather than fixed, because the only repair the declaration vocabulary had left was a coordinate per `(height, backness)` cell read off one MRI study, and a table fitted to the single source that produced it cannot be checked against anything. Closing it honestly needed a second measured source, or a principled model of tongue-body position. This is what happened when both were gone and looked for.

**Verdict: ANSWERED, NOT FIXED. Two further sources were found, and they refuse the fit rather than enabling it.** The same IPA symbol's measured constriction moves 0.15 to 0.28 of tract length between sources — for `o`, more than the entire declared `backness` span of 0.24 that a table would have to resolve. There is no per-cell coordinate to copy, because the quantity is not reproducible. What *does* reproduce is coarser and was not what the issue expected: Wood's four discrete constriction locations land inside the measured constriction band in 21 of the 25 columns the two tabulated sources supply, against 12 of 25 for the arcs ipakit declares. The model that survives is a four-way classification of the vowel space, not a coordinate per cell — and ipakit's declaration vocabulary, one feature and one value to one number, cannot state a classification that cross-cuts two features.

So the defect stands as a stated limit, and its reason changes. It is no longer blocked on evidence. It is blocked on a vocabulary, and on the fact that no source classifies the central vowel series at all.

The assessment changed no data and no tests. It adds this document, two subcommands to `scripts/areafunctions.py`, and a changelog line.

## Summary of findings

| Question | Finding |
|---|---|
| Is there a second measured source? | **Yes, two.** Wood (1979), 40 subjects in 13 languages, X-ray; and Yang & Kasuya (1994), three Japanese speakers, MRI, area functions printed as numbers. |
| Does the defect survive them? | **Yes.** Both put the back vowels at more than one constriction location. Five vowels at one point is not one speaker's anatomy. |
| Can a `(height, backness)` table be fitted and then checked? | **No — it fails the check.** The cross-source spread of one symbol is 0.059 to 0.284 of tract length. A table has to pick one number per cell out of that. |
| Which symbol is worst? | `o`. Story et al. measure 0.375; the three Japanese speakers measure 0.605 to 0.659. |
| Is that just an argmin artifact? | **No.** The comparison is band inclusion, the instrument `docs/design/tract-validation.md` §2 uses for the occlusions, not the rank correlation §3 refuses. Every figure below is a band, not a point estimate. |
| Does a principled model exist? | **Yes, and it is not a table.** Wood's four locations — hard palate, soft palate, upper pharynx, lower pharynx — with a vowel family at each. |
| Does it beat what ipakit declares? | **Yes, at every setting of both free parameters.** 21 of 25 measured bands against 12 of 25, and Wood is ahead in all 20 rows of the depth × cutoff sweep. |
| Does the second source support the *parameterization* a table would use? | **No, it argues against it.** Wood's whole paper is against describing vowels by tongue-arch height and fronting. |
| Was `rounded` worth reopening? | **Not on this evidence.** Wood's conclusion 6 says rounding moves the four regions, and that the move is compensated by larynx depression — so it bears on the anatomy, not on a normalized `arc`. [#127](https://github.com/lenzo-ka/ipakit/issues/127)'s refutation stands. |
| Should it be implemented? | **Not here.** Two things are missing and neither is a measurement: a family for the central series, which no source states, and a way for a vowel's `arc` to come from something other than `backness`. |

## Sources

- Wood, Sidney (1979). "A radiographic analysis of constriction locations for vowels", *J. Phonetics* 7(1), 25–43. <https://doi.org/10.1016/S0095-4470(19)31031-9>. Reprinted with the journal's own pagination in Wood, *X-Ray and Model Studies of Vowel Articulation*, Working Papers 23, Lund University, 1982, which is open access: <https://journals.lub.lu.se/LWPL/article/view/16897>. Read there, 2026-08-03.
- Yang, Ching-Shyang and Hideki Kasuya (1994). "Accurate measurement of vocal tract shapes from magnetic resonance images of child, female and male subjects", *ICSLP 94*, Yokohama, 623–626. <https://doi.org/10.21437/ICSLP.1994-158>. Open at the ISCA Archive. Read 2026-08-03.
- Story, Titze & Hoffman (1996), *J. Acoust. Soc. Am.* 100(1), 537–554 — the incumbent, and the source `docs/design/tract-validation.md` measured against. <https://doi.org/10.1121/1.415960>
- Gaines et al. (2021), *JASA Express Letters* 1(12), 124402 — a comprehensive sample of the Maeda model, and the citation that named Wood. <https://doi.org/10.1121/10.0009058>
- Stevens & House (1955) is reached only through Wood, who parameterizes their three-parameter model with the four distances in his Fig. 5.

The numbers below are measurements of three fixed published tables and cannot drift. What they are compared against can: `backness`, `height` and `place` in `ipakit/data/ipa.xml`. `scripts/areafunctions.py` reads both sides live.

## 1. What arrived, and by what route

The issue was blocked on either a second measured set of vowel tract geometries, or a principled model that predicts the height/backness interaction rather than tabulating it. Both turned up, and they are the same literature.

**Wood 1979** is the principled model. It is a review of 38 sets of mid-sagittal tracings covering 12 languages, published over the preceding 75 years, plus new X-ray motion films of Southern British English and Egyptian Arabic — "confirms these four constriction locations without exception by 40 subjects in 13 languages" (Wood 1979: 27). It is the source Gaines et al. cite for discrete constriction locations, and `docs/design/tract-validation.md` §7 named it as the right shape of evidence while recording that it was not in hand.

**Yang & Kasuya 1994** is the second measured set, and the more useful of the two for checking a table, because it prints numbers. Tables 1–3 give equi-length area functions for the five Japanese vowels from an adult male, an adult female and a boy — fifteen area functions, each with its own tract length and section length, sections numbered from the glottis with the last one the lip opening (Yang & Kasuya 1994: 625).

Two things not found, recorded as attempts rather than as facts about the works. Baer, Gore, Gracco & Nye (1991) is not open access by any route tried on 2026-08-03 — Unpaywall reports no open location, Europe PMC requires a subscription — so whether it tabulates area functions is unknown here. Fant's Russian area functions are reachable only through two independent digital transcriptions that agree with each other, not through the book, whose only archive.org copy is lending-restricted; they are not used below. Story & Titze (1998) was considered and set aside: Story et al. (2018) describes it as the same procedure over the same ten vowels of the same speaker, so it is not a second source.

Three public 3D-MRI datasets were checked and give geometry but not numbers: the Dresden Vocal Tract Dataset ships meshes, finite-element models and transfer functions with no area function or centerline; the Aalto Finnish set ships DICOM and STL only; and no derived constriction time series was found released alongside the USC rtMRI corpora. That is a fact about what those releases contain, checked against their own file listings on 2026-08-03, and not a claim about what could be computed from them.

## 2. The instrument

`docs/design/tract-validation.md` established which instrument to use and which to refuse. A rank correlation over the vowels is a report of the piriform cutoff — ρ runs −0.02 to +0.73 as the cutoff slides through the range a reader could defend — and the place of maximum constriction is not even defined for an open vowel. Band inclusion is what survives, because it is what the occlusion check does: the data states an extent, and the declared anchor is either in it or not.

An area function gives no zero-area run for a vowel, so the band has to be grown rather than read off. `bands` takes the narrowest section in the window and extends it while the area stays within a factor of the minimum. That factor is a free parameter and is swept, and the sweep is printed beside every count, so a verdict that moves with it can be seen to.

Wood's four locations become an `arc` by dividing by a tract length. For the adult male shapes Story images, each shape's own published length is used. For Yang & Kasuya the four distances have to be read as proportions instead: subtracting 12 cm from the boy's 13.3 cm tract puts the hard palate at `arc` 0.10, forward of the teeth, which is a fact about the reading and not about the boy.

## 3. Wood against Story's bands

`python scripts/areafunctions.py bands`

Story et al.'s eleven vowels, each with the band its own area function gives, at a depth factor of 2 and the 5 cm piriform cutoff:

| | band | ipakit | Wood | location |
|---|---|---|---|---|
| `i` | 0.238–0.310 | 0.320, out by 0.010 | 0.280 **inside** | hard palate |
| `ɪ` | 0.190–0.357 | 0.370, out by 0.013 | 0.280 **inside** | hard palate |
| `ɛ` | 0.075–0.475 | 0.320 inside | 0.244 **inside** | hard palate |
| `æ` | 0.238–1.000 | 0.320 inside | 0.730 **inside** | lower pharynx |
| `ʌ` | 0.500–1.000 | 0.560 inside | 0.742 **inside** | lower pharynx |
| `ɑ` | 0.568–0.750 | 0.560, out by 0.008 | 0.742 **inside** | lower pharynx |
| `ɔ` | 0.545–0.682 | 0.560 inside | 0.628 **inside** | upper pharynx |
| `o` | 0.341–0.432 | 0.560, out by 0.128 | 0.628, out by 0.196 | upper pharynx |
| `ʊ` | 0.455–0.705 | 0.500 inside | 0.513 **inside** | soft palate |
| `u` | 0.326–0.413 | 0.560, out by 0.147 | 0.534, out by 0.121 | soft palate |

Eight of ten for Wood, five of ten for ipakit. Across the whole 5 × 4 sweep of depth factor against cutoff, Wood is ahead in every row and strictly ahead in seventeen of twenty; the two converge only where the band is grown so wide that the instrument stops discriminating. So the ordering is not a report of either parameter.

`ɝ` has no row: Wood's four families cover the cardinal space and not the American English rhotic, which is the same gap `docs/design/tract-validation.md` §4 found from the other direction when it measured `ɝ` as the most anterior constriction in the set.

`ʌ` is named in none of Wood's four families either. His Fig. 5 superimposes Southern British English vowel areas on the four nomogram surfaces and puts it on the lower pharyngeal one, which is how it is read here; the band it lands in runs from 0.50 to the glottis, so both available readings are inside and nothing turns on the choice.

## 4. A coordinate does not reproduce

`python scripts/areafunctions.py replicate`

This is the check a table fitted to one speaker cannot perform on itself. The same band instrument over Yang & Kasuya's fifteen columns:

| | Story, English | Yang & Kasuya, Japanese | Wood | spread |
|---|---|---|---|---|
| `a` | not imaged | 0.568  0.618  0.559 | 0.743 | 0.059 |
| `i` | 0.274 | 0.432  0.382  0.324 | 0.314 | **0.158** |
| `u` | 0.380 | 0.386  0.528  0.417 | 0.514 | **0.147** |
| `e` | not imaged | 0.477  0.417  0.324 | 0.314 | **0.154** |
| `o` | 0.375 | 0.659  0.639  0.605 | 0.629 | **0.284** |

The Japanese columns are the male, the female and the boy. Story et al. image no `/a/` and no `/e/`: their nearest columns are `ɑ` and `ɛ`, which are other vowels, and putting one under the other would be the assumption this table exists to test.

**The spread is the finding.** ipakit's whole declared `backness` span is 0.24, front 0.32 to back 0.56. One symbol's measured constriction moves 0.284 across the sources that measured it — more than that entire span — and no symbol moves less than 0.059. A coordinate per `(height, backness)` cell has to be one number, and there is no one number to take.

`o` is the extreme case and is worth naming, because it is the vowel #123's headline rests on. Story's is American English *hoe*, phonetically a diphthong imaged as a steady state and measured at `arc` 0.375, which is where #123 reports it. All three Japanese speakers put `/o/` between 0.605 and 0.659, and Wood's upper pharynx is 0.629 — three speakers, a different language and a 40-subject review agreeing against the one speaker a table would have been fitted to. Had the table been written from Story alone it would have placed `o` with `u` in the close back cell, and the check that arrived afterwards would have refused it.

Wood's locations are inside the band in 13 of these 15, against 7 of 15 for what ipakit declares. Both misses are `/u/` — the male's and the boy's — and Japanese `/u/` is conventionally transcribed narrowly as `[ɯ]`, unrounded and often central. That the symbol read as IPA does not pin the articulation across languages is not an aside here; it is the same finding as the spread column, seen in one cell.

## 5. What this says about the declarations

Three things, in descending order of how much they change.

**A table is refused on evidence, not on taste.** [#127](https://github.com/lenzo-ka/ipakit/issues/127) refused it because it would be a fit to one study with nothing to check it against. It is now checkable, and it fails: the quantity a cell would hold is not reproducible across the sources that measure it. `tests/test_vowel_tract_limit.py` keeps every pin it had; what changes is the reason recorded in it.

**The model that survives cross-cuts two features, and the vocabulary cannot state it.** Wood's four families are `[i–ɛ, y–ø]`-like, `[u–ʊ, ɨ]`-like, `[o–ɔ, ɣ]`-like and `[ɑ–a–æ]`-like (Wood 1979: 41, conclusion 2). Read against `height` and `backness` that partition is a genuine interaction — front and close goes to the hard palate, back and close to the soft palate, back and open-mid to the upper pharynx, and open goes to the lower pharynx whether it is front or back, so the backness effect vanishes at the open end. Every coordinate in `ipa.xml` is one feature, one value, one number, and no such declaration states a partition of a plane. This is the same wall #127 hit, reached from the outside: the interaction is real, it is now measured twice, and the vocabulary is what cannot carry it.

**No source classifies the central series.** ipakit declares 39 vowels over 17 distinct `(height, backness)` cells, including `ɨ ʉ ɘ ɵ ə ɜ ɞ ɐ` and the rhotics. Wood names families for about a dozen cardinal qualities and none of the central ones; Story images `ɝ` and no other central vowel; Yang & Kasuya image five Japanese vowels. Assigning the central series to a family would be exactly the unsupported extrapolation this whole line of work exists to prevent, and it would be doing it in the one region where the evidence is thinnest rather than in the one where it is thickest.

**And one thing that does not change.** Wood's conclusion 6 is that rounding increases the distance from the glottis to each of the four regions, and that this is allowed for by depressing the larynx, which lengthens the tract. That is a claim about centimetres with a compensation in the denominator, so it does not reopen `rounded` as a contributor to a normalized `arc`. #127's refutation of `rounded` stands, and this is a second reason for it rather than a first doubt about it.

## 6. Reported, not implemented

What an implementation would need, so that the next lane starts from the cost rather than from the idea.

- **A constriction location per vowel phone**, from a source. Wood supplies roughly a dozen; the inventory has 39.
- **A vowel branch that reads it.** `tract_reading` takes `arc` from `backness` unconditionally on the `manner == "vowel"` branch. `place` is the obvious carrier — it already declares `palatal` 0.32, `velar` 0.45, `uvular` 0.56 and `pharyngeal` 0.74, which is Wood's four locations under ipakit's own names — but `place` on a vowel is currently read by nothing and reported as `unread`, and stating it renames the phone, because `describe` reads the place slot.
- **A before and after over all 9591 pairs, with every mover explained.** `arc` reaches `ipakit.metric` through `_sagittal`. Moving the vowel anchors moves a large part of the matrix, and `confusion.json` has to be regenerated.
- **A decision about the anchors themselves.** Wood's four proportional positions are 0.314, 0.514, 0.629 and 0.743. Two of those land on values `place` already declares almost exactly; two sit between `velar` and `uvular`. Adopting the classification and keeping the current place arcs are not the same change.

None of that is measurement, and none of it was this lane's to make on the strength of a document.

## 7. How to re-run this

```console
$ python scripts/areafunctions.py bands       # section 3
$ python scripts/areafunctions.py replicate   # section 4
```

`bands` needs `--source`, a text extraction of Story et al.; `replicate` needs `--second` as well, a CSV of Yang & Kasuya's Tables 1–3 with the columns the module docstring names. Both papers are copyrighted and outside the repository by policy, so `make check` cannot run either and both print why and exit 0 without them — the shape `scripts/articulatory.py` already uses.

The second source is a transcription of a printed table from an image-only scan, which cannot be checked against the table. It can be checked against itself: the paper prints a tract length and a section length per column as well as the sections, and `replicate` re-derives one from the others and fails if they disagree, over all fifteen columns. A dropped or duplicated row breaks that at once. The vowel identities are the table's own column headings, which are Latin letters and legible.

## Related

- [tract-validation.md](tract-validation.md) — the first external check, which found the defect and named Wood as the evidence it lacked
- [../articulatory-data.md](../articulatory-data.md) — the X-Ray Microbeam measurement, and why that instrument cannot see a vowel constriction behind `arc` 0.44
- [../tract-anatomy.md](../tract-anatomy.md) — §6, the derived quantities, and what is computed rather than asserted about them
- `tests/test_vowel_tract_limit.py` — the limit, pinned so it can only move deliberately
