# Where a vowel constricts: assessment

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

[#123](https://github.com/lenzo-ka/ipakit/issues/123) is that a vowel reads its tract position from `backness` and nothing else, so `u o ɑ ɔ ʌ` all sit at `arc` 0.56. It was left open rather than fixed, because the only repair the declaration vocabulary had left was a coordinate per `(height, backness)` cell read off one MRI study, and a table fitted to the single source that produced it cannot be checked against anything. Closing it honestly needed a second measured source, or a principled model of tongue-body position. This is what happened when both were gone and looked for.

**Verdict, first pass: ANSWERED, NOT FIXED. Two further sources were found, and they refuse the fit rather than enabling it.** The same IPA symbol's measured constriction moves 0.15 to 0.28 of tract length between sources — for `o`, more than the entire declared `backness` span of 0.24 that a table would have to resolve. There is no per-cell coordinate to copy, because the quantity is not reproducible. What *does* reproduce is coarser and was not what the issue expected: Wood's four discrete constriction locations land inside the measured constriction band in 21 of the 25 columns the two tabulated sources supply, against 12 of 25 for the arcs ipakit declares. The model that survives is a four-way classification of the vowel space, not a coordinate per cell — and ipakit's declaration vocabulary, one feature and one value to one number, cannot state a classification that cross-cuts two features.

So the defect stands as a stated limit, and its reason changes. It is no longer blocked on evidence. It is blocked on a vocabulary, and on what the central vowel series turns out to be.

## The second pass: the central series, and the anchors

The first pass left three things open and named them in §9: a location for every vowel phone, a family for the central series, and a decision about where the four locations sit. Sections 6, 7 and 8 are what happened when those were taken. Two more sources were found and one more measurement was built.

**Verdict on the central series: the series cannot be classified as a series, and that is a result about the vowel chart rather than about the evidence.** Wood does classify two of the ten symbols ipakit places at `arc` 0.44, and he puts them in *different* families — `ɨ` at the soft palate, Swedish `ʉː` at the hard palate, with 0.44 in the gap between. A 28-speaker ultrasound study of the one central vowel with a real cross-linguistic literature finds the same symbol realized with a front dorsum in Polish and a back one in Russian. The best-studied central vowels of all, the American English rhotics, have two speaker-specific tongue shapes whose palatal constrictions sit in disjoint bands and which are acoustically near-identical. Every route into the central column returns the same shape of answer. For the two symbols that are classified the family is language-specific; for the rhotics it is speaker-specific; for the other six there is nothing, and for schwa the best-supported account makes its target a mean over the rest of a speaker's inventory rather than a constant. ipakit's 0.44 is not wrong for want of a measurement. It is a single coordinate standing where the evidence says there is no single coordinate to have.

**Verdict on a coordinate per phone: refused a third time, now without the escape.** The first pass showed a coordinate does not survive a change of speaker and language, which invites the reply that a coordinate could still be well defined once a speaker is fixed. Story re-imaged his own 1996 speaker in 2002. Three of the ten vowels in both sets move by more than 0.10 of tract length at every cutoff tried, and `o`'s two bands do not overlap at any of them.

**Verdict on the anchors: the two candidate placements cannot be told apart, so the cheaper one is the proposal.** Wood's own four proportions and the four arcs `place` already declares under the same four names differ by 0.003 to 0.069. Over 35 measured bands from three sources they score 26 and 25, and the difference changes sign inside the parameter sweep. `backness` scores 14 and is below both in every row of it. The classification is what does the work; where its four locations sit is, on this evidence, a free choice — so it should be made on cost, and the cost of reusing `place`'s declared arcs is nothing.

The assessment changed no data and no tests. It adds this document, four subcommands to `scripts/areafunctions.py`, and a changelog line.

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
| Should it be implemented? | **Not here.** Two things are missing and neither is a measurement: a family for the central series, and a way for a vowel's `arc` to come from something other than `backness`. **Superseded by [#123](https://github.com/lenzo-ka/ipakit/issues/123), and implemented** — see §8 and §9. The second was built as [#160](https://github.com/lenzo-ka/ipakit/issues/160)'s `constriction-location`; the first is still missing and is why nine central vowels state nothing and say so. |
| Does a coordinate reproduce for one speaker, twice? | **No.** Story's own 1996 speaker, re-imaged in 2002: `i` moves 0.103, `ɪ` 0.125 and `o` 0.136 of tract length at every cutoff, and `o`'s two bands never overlap. |
| Does any source classify the central series? | **Two symbols of ten, into two different families.** Wood puts `ɨ` at the soft palate and Swedish `ʉː` at the hard palate. Nothing reaches `ɘ ɵ ə ɜ ɞ ɐ`. |
| Is the one central vowel with a literature stable across languages? | **No.** Cavar et al. (2025), 28 speakers: Polish `ɨ` has a front dorsum, Russian `ɨ` a central or back one. |
| And the rhotics, where the evidence is thickest? | **Two articulations, disjoint bands, one sound.** Zhou et al. (2008) measure the palatal constriction at 12.6–14.6 cm from the glottis for retroflex `ɹ` and 10.7–12.3 cm for bunched, in two anatomically matched speakers. |
| Where should the four locations sit? | **The measurement does not say.** Wood's proportions score 26 of 35 bands, the arcs `place` already declares score 25, and the gap changes sign across the parameter sweep. `backness` scores 14 and loses to both in all 20 rows. |

## Sources

- Wood, Sidney (1979). "A radiographic analysis of constriction locations for vowels", *J. Phonetics* 7(1), 25–43. <https://doi.org/10.1016/S0095-4470(19)31031-9>. Reprinted with the journal's own pagination in Wood, *X-Ray and Model Studies of Vowel Articulation*, Working Papers 23, Lund University, 1982, which is open access: <https://journals.lub.lu.se/LWPL/article/view/16897>. Read there, 2026-08-03.
- Yang, Ching-Shyang and Hideki Kasuya (1994). "Accurate measurement of vocal tract shapes from magnetic resonance images of child, female and male subjects", *ICSLP 94*, Yokohama, 623–626. <https://doi.org/10.21437/ICSLP.1994-158>. Open at the ISCA Archive. Read 2026-08-03.
- Story, Titze & Hoffman (1996), *J. Acoust. Soc. Am.* 100(1), 537–554 — the incumbent, and the source `docs/design/tract-validation.md` measured against. <https://doi.org/10.1121/1.415960>
- Gaines et al. (2021), *JASA Express Letters* 1(12), 124402 — a comprehensive sample of the Maeda model, and the citation that named Wood. <https://doi.org/10.1121/10.0009058>
- Stevens & House (1955) is reached only through Wood, who parameterizes their three-parameter model with the four distances in his Fig. 5.

Found on the second pass:

- Wood, Sidney (1982). *X-Ray and Model Studies of Vowel Articulation*, Working Papers 23, Lund University. <https://journals.lub.lu.se/LWPL/article/view/16897>. The carrier of the 1979 article, and separately the source for Swedish `ʉː` — paper III, "The acoustical consequences of tongue, lip and larynx articulation in rounded palatal vowels". Read 2026-08-03.
- Story, Brad H. (2008). "Comparison of magnetic resonance imaging-based vocal tract area functions obtained from the same speaker in 1994 and 2002", *J. Acoust. Soc. Am.* 123(1), 327–335. <https://doi.org/10.1121/1.2805683>. Free author manuscript at PubMed Central, PMC2377017. Table I prints 44 areas for each of eleven vowels. Read 2026-08-03.
- Cavar, Malgorzata E., Emily M. Rudman, Neha Nagaraj and Lily Peters (2025). "High Central Vowels in Polish, Ukrainian and Russian", *J. Int. Phon. Assoc.* 55, 1–34. <https://doi.org/10.1017/S0025100325000040>. Open access, CC BY. 3D/4D ultrasound, 28 speakers. Read 2026-08-03.
- Zhou, Xinhui, Carol Y. Espy-Wilson, Suzanne Boyce, Mark Tiede, Christy Holland and Ann Choe (2008). "A magnetic resonance imaging-based articulatory and acoustic study of 'retroflex' and 'bunched' American English /r/", *J. Acoust. Soc. Am.* 123(6), 4466–4481. <https://doi.org/10.1121/1.2902168>. Free at PubMed Central, PMC2680662. Read 2026-08-03.

Added by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and read by the `#175` markers in §7 and §8 rather than by the body of this assessment:

- Story, Brad H., Ingo R. Titze and Eric A. Hoffman (1998). "Vocal tract area functions for an adult female speaker based on volumetric imaging", *J. Acoust. Soc. Am.* 104(1), 471–487. <https://doi.org/10.1121/1.423298>. Closed at the publisher and not on PubMed Central. Subject DJ, a 27-year-old female native to Texas — a different speaker, not a re-analysis of the 1996 male. Table III (p. 476) prints ten vowels plus electron-beam CT versions of `i` and `ɑ`; Table IV (p. 480) prints `ɝ` twice and `l`. Read 2026-08-03.
- Wood, Sidney (1990). "Vertical monovocalic vowel systems: the case of Kabardian", Working Papers 36, Lund University, 191–212. <https://journals.lub.lu.se/LWPL/article/view/2595>. Open access. Page 198 restates the four constriction locations at greater length than conclusion 2 of the 1979 article, naming `œ` in the palatal family and `ɯ` in the palatovelar one; p. 199 translates the four into SPE categories, and p. 205 says of the symbols this assessment cannot place that "the articulation of so-called *central* vowels obviously needs clarification". Read off rendered page images at 1600 dpi.
- Wood, Sidney, "Interpreting vowel articulation from formant frequencies", `swphonetics.com/methods/vowel-articulation-from-formants/`. Self-published, and the only statement of the four families that names `ʌ` or `ɒ`. The live domain now serves a parked page; read from the 2019 Wayback capture, where it expands the figure it credits to "Wood, 1979, Journal of Phonetics 7:25-43".

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

**Superseded by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and reversed: Wood names `ʌ` in a family, in the *upper* pharynx, and this figure was the wrong place to look.** Conclusion 2 is not his last statement of the four. Wood (1990: 198) restates them at greater length, and his own summary of the 1979 figure gives the third as "in the upper pharynx for [o ɔ] and [ɤ ʌ]". The sentence above is right that a figure is not a classification and wrong about which reading that leaves: Fig. 5's caption assigns no ellipse to a surface, so reading `ʌ`'s off the surface it overlaps was itself the inference. The classification and the measurement then agree — over the three American English sessions held, the upper pharyngeal proportion 0.629 is inside all three bands and the lower pharyngeal 0.743 inside one of three. `scripts/areafunctions.py` reads `ʌ` as upper pharyngeal now; over the ten bands in the table above Wood is unchanged at 8 of 10 at this depth and one lower at the two tightest depths of the sweep.

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

**Almost no source classifies the central series.** ipakit declares 39 vowels over 17 distinct `(height, backness)` cells, including `ɨ ʉ ɘ ɵ ə ɜ ɞ ɐ` and the rhotics. Wood names families for about a dozen cardinal qualities, of which exactly one is central; Story images `ɝ` and no other central vowel; Yang & Kasuya image five Japanese vowels. Assigning the rest of the series to a family would be exactly the unsupported extrapolation this whole line of work exists to prevent, and it would be doing it in the one region where the evidence is thinnest rather than in the one where it is thickest. §6 is what the second pass found when it went looking for that evidence, and the one central symbol Wood does name turns out to be the load-bearing case rather than a rounding error.

**And one thing that does not change.** Wood's conclusion 6 is that rounding increases the distance from the glottis to each of the four regions, and that this is allowed for by depressing the larynx, which lengthens the tract. That is a claim about centimetres with a compensation in the denominator, so it does not reopen `rounded` as a contributor to a normalized `arc`. #127's refutation of `rounded` stands, and this is a second reason for it rather than a first doubt about it.

## 6. The central series

This is the section the second pass exists for. §5 said no source classifies the central vowels and left it there. Read against the page rather than the OCR, that was too strong in one direction and much too weak in the other.

### Wood names two of them, and puts them in different families

Conclusion 2 of Wood 1979 (p. 41), read off the rendered page:

> The vowels produced at these locations fall into distinct families: [i-ɛ, y-ø]-like, [u-ʊ, ɨ]-like, [o-ɔ, ɣ]-like and [ɑ-a-æ]-like respectively (Figs 1–5).

The third symbol in the second family is `ɨ`, a barred i, and it is central. Every OCR of the page renders it `i`, which is why it can be read past. It is not a slip: `ɨ` appears again on p. 34, where Wood observes that "most cases of pre-palatal location in the collected material are from languages contrasting [i] with [y] or [ɨ] qualities". So Wood puts `ɨ` at the **soft palate**, with `u` and `ʊ` — proportionally `arc` 0.514.

The 1982 monograph adds a second. Paper III is on rounded palatal vowels, and in discussing the Swedish three-way close rounded contrast (p. 103):

> The slender spectral difference is related to the fact that phonologically Swedish /iː/ and /yː/ have to fit into a threeway contrast with another labial palatal vowel /ʉː/ with lower F₂ and F₃.

That is a classification of `ʉ` into the **hard palate** family — proportionally `arc` 0.314. Same author, same four-way model, and the two central symbols he names land at opposite ends of it. ipakit puts both at 0.44, which is between them and is neither.

The structure is exactly the failure #123 reports for the back vowels, one column to the left. There, five vowels share 0.56 and the measurement puts them in two groups at 0.38 and 0.65 with nothing in the gap. Here, ten vowels share 0.44 and the only two that any source places sit at 0.314 and 0.514 with 0.44 in the gap. The central column of the IPA chart is not a constriction location. It is where two constriction locations are both possible.

### The one central vowel with a cross-linguistic literature disagrees with itself

Cavar, Rudman, Nagaraj and Peters (2025) record 28 speakers of Polish, Ukrainian and Russian with 3D/4D ultrasound, on the vowel all three languages write `y` and phoneticians write `ɨ`. Their Table 4 summarizes the overall dorsum position as *front* for Polish, *central or back* for Russian, and *centralized* for Ukrainian, and the discussion is explicit that the middle option is the one that does not turn up:

> Further, we have not observed a systematic central position of the vowel dorsum between the front and back position in Polish or Russian /ɨ/. In individual cases, we observed a long constriction extending from front to back. Most of the time, however, the position of the dorsum in 'central' vowels in the two languages tends to be either close to the high front vowel (Polish) or close to the high back vowel (Russian).

Three closely related languages, cognate words, the same phonological behavior, one symbol, and the dorsum in two different places. Wood's assignment of `ɨ` to the soft palate is corroborated for Russian and refuted for Polish — by a study with 28 speakers, against Wood's review of tracings. Neither is wrong. The symbol is doing work that a constriction location cannot do.

This is an ultrasound study and reports no tract length, so nothing here is a band and nothing is compared by inclusion. What it supports is the classification claim, which is the claim that survived §3, and it supports it by saying the classification is language-specific.

### The rhotics: the thickest evidence, and the worst case for a coordinate

`ɝ` and `ɚ` are the central vowels the speech-technology world has measured most, and they are where a single `arc` fails hardest, for two independent reasons.

**A rhotic has three constrictions, not one.** Zhou et al. (2008) on the two configurations:

> These examples are typical in showing three supraglottal constrictions along the vocal tract: a narrowing in the pharynx, a constriction along the palatal vault, and a constriction at the lips. However, the locations of constrictions and the degrees and lengths of constriction significantly differ, especially along the palate.

`tract_point` returns one `(arc, offset)`, and [../articulatory-data.md](../articulatory-data.md) already says of it: "That is a **constriction locator, not an articulatory pose** — it says where the narrowest point is, not where each organ sits." A phone with three simultaneous constrictions is not under-measured by that return type; it is unrepresentable in it, and `constrictions` returning a tuple for secondary articulations is the shape the repair would take.

**And the one constriction a locator could carry is not shared between speakers.** Zhou et al. image two men both 188 cm tall, matched on palate length, depth and width and on tract length, one producing retroflex `ɹ` and one bunched. The palatal constriction runs 12.6 to 14.6 cm from the glottis for the retroflex speaker and 10.7 to 12.3 cm for the bunched one. Those two bands are disjoint in centimetres, before any normalization. The paper prints no per-subject tract length, so they cannot honestly be turned into `arc` here; on a 17.5 cm tract the two midpoints would be 0.12 apart, which is half of ipakit's entire declared `backness` span. And the two are near-identical in F1–F3 — the whole point of the paper is that they differ only in F4/F5 spacing, which is why the variation went unnoticed for decades.

So for the rhotic the evidence is thick and consistent, and it says the phone has no one location. That is a stronger result than the silence over `ɘ ɵ ɜ ɞ ɐ`, and it points the same way.

**Superseded by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and reproduced on a tabulated area function rather than at one remove.** Story, Titze & Hoffman (1998) image `ɝ` for an adult female and Story, Titze & Hoffman (1996) image it for an adult male. Both columns carry three or more supralaryngeal minima, and the two constriction bands are disjoint at every band depth up to 2.0 — 0.182–0.250 for the male against 0.316–0.500 for the female, the narrowest sections 0.166 of tract length apart. Zhou et al.'s two configurations are two subjects of one paper; these are two subjects of one laboratory, and they say the same thing about the same symbol. `scripts/areafunctions.py female` prints it.

**Acted on in the metric by [#183](https://github.com/lenzo-ka/ipakit/issues/183).** The `rhotacized` feature declares `constriction="unlocalized"`, and the distance withholds the tract-`x` term whenever a side states it: `ɝ` and `ɚ` are compared on `rhotacized` and height but never on the single central `arc` this section calls a coordinate the evidence denies. The drawing keeps the approximated point; only the metric refuses it, and it refuses it without asserting the maximal difference a dropped coordinate would.

### What was tried for the rest, and found nothing

`ə ɘ ɵ ɜ ɞ ɐ` have no measured tongue-body constriction location from any route tried on 2026-08-03. None of the three-dimensional MRI corpora releases a numeric area function; the vowel sets that are tabulated are American English and Japanese, neither of which contrasts a central quality at all. The routes are listed in the reference index rather than here, because a list of things that returned nothing is a record of an afternoon and not a property of the literature.

Schwa is the one worth naming, because for it the answer is not scarcity. Browman & Goldstein (1992) report that an explicit tongue gesture for a schwa was needed to model `[ˈpVpəpVp]`, "although the target of the required gesture was completely colorless in that it was the average of the tongue body positions for all full vowels for that speaker". That is a target defined as a mean over the rest of one speaker's inventory. It is a perfectly good articulatory object and it is not a constant: two speakers with different vowel systems have different schwas by construction, and so do two languages. A declared `arc` for `ə` would have to be a number, and the best-supported account of what schwa's location is says it is a function of everything else.

## 7. One speaker, twice

`python scripts/areafunctions.py intra`

§4 showed that a coordinate does not survive a change of speaker and language. The obvious reply is that those were different people speaking different languages, and that a coordinate could still be perfectly well defined once a speaker is fixed. Story (2008) is that reply's test: the speaker of Story, Titze & Hoffman (1996), re-imaged by the same author with the same procedure eight years later, and reported as a numeric table for the same reason the first set was.

Ten vowels are in both sets. The 1996 set has `ɝ` and no `e`; the 2002 set has `e` and no `ɝ`.

| | 1994 band | 1994 | 2002 band | 2002 | move | overlap |
|---|---|---|---|---|---|---|
| `i` | 0.238–0.310 | 0.274 | 0.091–0.295 | 0.170 | 0.103 | yes |
| `ɪ` | 0.190–0.357 | 0.250 | 0.000–0.386 | 0.125 | 0.125 | yes |
| `ɛ` | 0.075–0.475 | 0.263 | 0.659–1.000 | 0.693 | 0.431 | **no** |
| `æ` | 0.238–1.000 | 0.655 | 0.614–1.000 | 0.670 | 0.016 | yes |
| `ʌ` | 0.500–1.000 | 0.648 | 0.523–0.705 | 0.670 | 0.023 | yes |
| `ɑ` | 0.568–0.750 | 0.670 | 0.636–0.750 | 0.693 | 0.023 | yes |
| `ɔ` | 0.545–0.682 | 0.648 | 0.523–0.727 | 0.625 | 0.023 | yes |
| `o` | 0.341–0.432 | 0.375 | 0.477–0.682 | 0.511 | 0.136 | **no** |
| `ʊ` | 0.455–0.705 | 0.534 | 0.409–0.591 | 0.557 | 0.023 | yes |
| `u` | 0.326–0.413 | 0.380 | 0.364–0.432 | 0.398 | 0.017 | yes |

The median move is 0.023, which is a good deal smaller than the cross-source spreads in §4 and is the honest part of the reply: fixing the speaker does tighten most of the set. But the subcommand prints the move at four cutoffs beside the table, because one of these rows is a report of the cutoff and the rest are not. `ɛ`'s move runs 0.001, 0.431, 0.112, 0.112 as the cutoff goes 4, 5, 6, 7 cm — an open vowel with no supralaryngeal minimum worth the name, which is the case §3 already refuses. Three rows do not move with the parameter at all:

| | 4.0 | 5.0 | 6.0 | 7.0 |
|---|---|---|---|---|
| `i` | 0.103 | 0.103 | 0.103 | 0.103 |
| `ɪ` | 0.125 | 0.125 | 0.125 | 0.125 |
| `o` | 0.136 | 0.136 | 0.136 | 0.136 |

**One speaker's own constriction moves by more than 0.10 of tract length, for three of ten vowels, at every setting the instrument has.** `o`'s two bands do not overlap at any cutoff: there is no `arc` at all, not merely no principled one, that is inside both of this speaker's own measurements of his own `o`.

`o` was already the extreme case in §4 and this is why it deserves the attention. #123's headline number is that Story's `o` sits at 0.375 while ipakit declares 0.56. The same speaker in 2002 puts it at 0.511, in a band running 0.477 to 0.682 which contains ipakit's 0.560 and Wood's 0.628 and does not contain 0.375. A table fitted to the 1996 column would have placed `o` in the close back cell with `u`; the same man eight years later refuses it, before any other speaker or language is consulted.

Run over the 2002 session alone, the §3 comparison comes out the same way it did on the 1996 one: Wood's locations are inside the band for 7 of 10, the declared arcs for 5 of 10. The classification replicates. The coordinate does not.

## 8. Where the four locations would sit

`python scripts/areafunctions.py anchors`

§9 named this as a decision and warned that adopting the classification and keeping the current place arcs are not the same change. They are not. But the difference between them is measurable, and it turns out the measurement declines to choose.

Wood's four distances from the glottis, over the 17.5 cm his nomograms use, against the arcs `place` already declares under the same four names:

| location | ipakit name | Wood | `place` | gap |
|---|---|---|---|---|
| hard palate | `palatal` | 0.314 | 0.320 | 0.006 |
| soft palate | `velar` | 0.514 | 0.450 | 0.064 |
| upper pharynx | `uvular` | 0.629 | 0.560 | 0.069 |
| lower pharynx | `pharyngeal` | 0.743 | 0.740 | 0.003 |

Two coincide to within 0.006. The other two do not, and they miss in the same direction — `place` sits forward of Wood at both. The soft palate falls between `velar` and `uvular`; the upper pharynx falls between `uvular` and `pharyngeal`, not between `velar` and `uvular`.

Held against all 35 measured bands the three sources supply, with each of the three readings scored by inclusion:

| source | bands | `backness` | Wood | `place` |
|---|---|---|---|---|
| Story 1996 | 10 | 5 | 7 | 6 |
| Story 2002 | 10 | 5 | 6 | 6 |
| Yang & Kasuya | 15 | 4 | 13 | 13 |
| **all** | **35** | **14** | **26** | **25** |

And over the 5 × 4 sweep of band depth against cutoff, `backness` is below both of the other two in **20 of 20** rows, while Wood against `place` runs from −2 to +5 bands of 35 and **changes sign inside the sweep** — Wood is ahead at the tight depths where the band discriminates most, `place` at the loose ones where it discriminates least.

So the finding is an ordering with two members, not three. The classification beats reading `arc` off `backness`, robustly and by a wide margin, and where its four locations sit is not decided by anything measured here.

**Superseded by [#123](https://github.com/lenzo-ka/ipakit/issues/123), and adopted as written.** Read at the declared arcs, the library scores 26 of the same 35 bands against 25 for the classification and 26 for Wood's proportions, and no consonant moved. The one place the two readings differ over the shipped inventory is `ʌ`, which the scoring here puts in the lower-pharyngeal family off Fig. 5 and the declaration leaves unstated, because a figure is not a classification.

**Superseded by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and reproduced on a fourth source without changing its answer.** Story, Titze & Hoffman (1998) adds a second American English speaker — an adult female, ten vowels — and ten bands. On 45 bands the library scores 32, Wood's proportions 34, `place`'s arcs 31 and `backness` 23; the Wood-against-`place` margin still changes sign inside the same 5 × 4 sweep, so the instrument still does not separate the two placements. What the new speaker does add is a *direction*: on her six bands narrower than half the tract the library is inside 2 and Wood 4, and all four of the library's misses are the declared arc sitting in front of the measured band, never behind it. That is the same gap this section already measures between `place` and Wood at the soft palate and the upper pharynx, now with a speaker falling into it. It is not enough to move a `place` arc, which would move every consonant that reads it, and it is why the sentence above says the choice is free rather than settled.

**Superseded again by [#175](https://github.com/lenzo-ka/ipakit/issues/175), on the `ʌ` correction rather than on a new source.** Moving `ʌ` into the family Wood puts it in raises Wood's own proportions from 34 of 45 to 36 and `place`'s arcs from 31 to 32; the library stays at 32, because `ʌ` reads 0.56 whether it takes it from `backness` or from `uvular`. On the female speaker's six informative bands Wood goes from 4 of 6 to 5 of 6. The Wood-against-`place` margin now runs −2 to +8 and still changes sign inside the sweep, so the reading that could not separate the two placements still cannot.

**That makes the proposal the cheap one.** Adopt Wood's four families and read them at the arcs `ipa.xml` already declares for `palatal`, `velar`, `uvular` and `pharyngeal`. No new coordinate is introduced, no `place` value moves, and every consonant stays exactly where it is — which matters, because `place` arcs reach `ipakit.metric` for the whole consonant inventory and `docs/design/tract-validation.md` §2 already checks two of them against measured occlusions. Moving `velar` from 0.45 to 0.514 to satisfy the vowels would move `k` and `ŋ` away from the closures that check them.

Two things argue against pretending the choice is better supported than that. Wood's own conclusion 4 says the palatal location is the language-dependent one:

> There are documented examples of languages preferring either the pre-palatal or mid-palatal locations for the palatal constrictions. However, the sphincteral function of the palatoglossi and the pharyngeal constrictors leaves little opportunity to vary the locations of the other three constrictions.

And he measures the spread: his English subject centered the palatal constrictions "about 35 mm behind the central incisors" and his Arabic subject "about 27 mm behind the central incisors" (p. 34). Eight millimetres inside one family, across two of the subjects the four locations were established from. A location fixed to the third decimal is a false precision whichever of the two candidate values it takes.

## 9. Reported, not implemented

**Superseded by [#123](https://github.com/lenzo-ka/ipakit/issues/123), and implemented.** Every bullet in this section has since been taken, in the shape §8 recommends: the sixteen vowels §9's own sub-section names declare a `constriction-location`, read at the arcs `place` already declares. The band-inclusion score over the same 35 bands moves from 14 for `backness` to 26 for the library, and 2421 of 9591 pairs move. The one thing that came out differently is in the sub-section below.

What an implementation would need, so that the next lane starts from the cost rather than from the idea.

- **A constriction location per vowel phone**, from a source. This is the one the second pass did not close, and §6 is why. Wood supplies roughly a dozen; the inventory has 39; and the ten central symbols are not short of a measurement but short of a place for one to be about.
- **A vowel branch that reads it.** `tract_reading` takes `arc` from `backness` unconditionally on the `manner == "vowel"` branch. `place` is the obvious carrier — it already declares `palatal` 0.32, `velar` 0.45, `uvular` 0.56 and `pharyngeal` 0.74, which is Wood's four locations under ipakit's own names — but `place` on a vowel is currently read by nothing and reported as `unread`, and stating it renames the phone, because `describe` reads the place slot. The mechanism is [#160](https://github.com/lenzo-ka/ipakit/issues/160); it chooses no vowel's location, and this document chooses no mechanism.

**Superseded by [#160](https://github.com/lenzo-ka/ipakit/issues/160), and closed.** The branch reads a `constriction-location` a nucleus states, and `backness` where none is stated. `place` was refused as the carrier on the second obstacle named below, and on a third this assessment did not reach: the dental and linguolabial marks already put a place on a vowel, and reading that slot as the tongue body's constriction would have moved every one of those units, toward saying a dental vowel's *body* is at the teeth. The slot takes `place`'s values, aliases and arcs by declaration — `vocabulary="place"` — rather than restating them, so where `velar` is stays one number in one file and the last bullet below stays a single decision. No vowel states one, and nothing moved: zero movers over every pair the inventory makes and over the whole unit corpus.

- **A before and after over all 9591 pairs, with every mover explained.** `arc` reaches `ipakit.metric` through `_sagittal`. Moving the vowel anchors moves a large part of the matrix, and `confusion.json` has to be regenerated.
- **A decision about the anchors themselves.** Answered in §8, and answered by declining: the measurement cannot separate Wood's own proportions from the arcs `place` already declares, so reuse the declared ones and move nothing.

None of that is measurement, and none of it was this lane's to make on the strength of a document.

### What a partial declaration would and would not buy

The obvious middle course is to declare a family for the vowels that have one and leave the rest reading `backness`. It is worth being explicit about what that does, because it looks more honest than it is.

It is honest for the peripheral vowels: `i ɪ ɛ y ø e æ a ɑ u ʊ o ɔ ɤ ɨ ʉ` are the ones Wood's families name, and §3, §7 and §8 all say the classification is right for them. It is not honest for `ɘ ɵ ə ɜ ɞ ɐ ɝ ɚ`, and the reason is not that they would be left unstated. It is that leaving them on the `backness` branch leaves them at 0.44, which §6 shows is a value in the gap between the two locations the evidence puts central vowels at — so a partial declaration does not leave those eight alone, it silently keeps a number that the same evidence refutes for the two neighbours it does declare. The extrapolation would not be removed; it would be relocated into the default and stop being visible.

The way out of that is not more measurement. It is for `unmodelled` to be able to say that a vowel's constriction location is not stated, the way `rhotacized` already declares no coordinates and is reported rather than invented — `docs/design/tract-validation.md` §4 records that working for exactly this phone. That is a mechanism question and belongs to [#160](https://github.com/lenzo-ka/ipakit/issues/160), not here.

**Superseded by [#123](https://github.com/lenzo-ka/ipakit/issues/123), and taken — with the second half of the last sentence refused.** The partial declaration was made, and the way out of the trap this paragraph names is the one it names: `unmodelled` now returns `backness` with kind `approximate` for every vowel that states no location, and `Reading.approximated` carries the same fact, so the extrapolation is in the default *and* visible. What the citation supports is the opposite of what it is offered for, though. §4 of the sibling records the `rhotacized` annotation working *and* records why it is not enough — the rhotic is drawn 0.22 of a tract from where it was measured, with a chip saying something is missing, and "a reader has no way to know the note explains the error". Withholding the number rather than annotating it would have made that worse rather than better: `bundle_distance` scores a coordinate one side has and the other lacks as the maximal difference and two absences as no difference, so an unplaced schwa asserts that schwa is maximally unlike every placed vowel on the tract axis and identical to every other unplaced one. What the §4 finding actually asks for is a note that names the coordinate rather than a neighbouring property, which is what an `approximate` mark on `backness` is.

The eight symbols named above are also not the whole of the unstated set. `ä œ ɒ ɯ ɶ ʌ ʏ` are outside Wood's families too — `ä` is central and belongs with the other nine, and the rest are qualities his conclusion 2 does not reach — so a treatment that named eight would have been a list that was already wrong. The report is derived from the absence instead.

**Superseded by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and `ʌ` re-examined against a source that images it — still unstated, now on a measurement rather than on Wood's silence.** Story, Titze & Hoffman (1998) is the first source to put `ʌ` in a tabulated area function alongside the two sessions that already do, and the three agree: her constriction band is 0.588–0.676, the 2002 male's 0.523–0.705, the 1996 male's 0.500–1.000. The declared vocabulary offers `uvular` 0.56 and `pharyngeal` 0.74 and nothing between them. Over the 5 × 4 sweep against those three bands, `uvular` is inside 42 of 60 and `pharyngeal` 40 of 60, and at every setting tight enough for the band to discriminate neither reaches 2 of 3. `uvular` also *is* the arc `backness` already gives it, so declaring it would move nothing and would only withdraw the `approximate` mark — asserting the number is sourced at the one setting where the measurement says it is outside a band. The evidence narrows the question and does not answer it: what it now says is that `ʌ` constricts where the inventory declares no location, which is a different fact from nobody having looked.

**Superseded within [#175](https://github.com/lenzo-ka/ipakit/issues/175) by reading the source rather than measuring again — `ʌ` is declared, and so are `œ` and `ɯ`.** Every sentence above rests on `ʌ` being in no family, and it is in one. Conclusion 2 of the 1979 paper is not Wood's last statement of the four locations. Wood (1990: 198) restates them, and the restatement names two more of the unstated set — "along the hard palate for [i-ɛ,**y-œ**]-like vowels", "the faucial passage for [u-ʊ,**ɯ**]-like vowels" — read off a 1600 dpi render because every OCR of these scans mangles IPA. His own summary of the 1979 figure names a third: "in the upper pharynx for [o ɔ] and [ɤ **ʌ**], and in the lower pharynx for [æ a ɑ] and [ɒ]". Read as upper pharyngeal, `ʌ` is the case where the classification and the bands agree rather than the case where they conflict: Wood's 0.629 is inside all three of its bands and 0.743 inside one. So `œ` is `palatal`, `ɯ` is `velar` and `ʌ` is `uvular`, and the same 0.028 the paragraph above objects to is what `o` and `ɔ` have already carried under this family since #123, at 0.051. `ɒ` is left unstated, because the only statement of the four that names it is Wood's own site and no band checks it.

Twelve are still unstated, and the list the paragraph before this one gives is now `ä ɐ ɒ ɘ ə ɚ ɜ ɝ ɞ ɵ ɶ ʏ`. `ɝ` is the one proved rather than argued.

## 10. How to re-run this

```console
$ python scripts/areafunctions.py bands       # section 3
$ python scripts/areafunctions.py replicate   # section 4
$ python scripts/areafunctions.py intra       # section 7
$ python scripts/areafunctions.py anchors     # section 8
$ python scripts/areafunctions.py female      # the #175 markers in section 7 and section 8
```

`bands` needs `--source`, a text extraction of Story et al.; `replicate` needs `--second` as well, a CSV of Yang & Kasuya's Tables 1–3; `intra` needs `--third`, a CSV of Story (2008) Table I; `female` needs `--fourth`, a CSV of Story, Titze & Hoffman (1998) Tables III and IV, and reads `--source` and `--third` where they are given so it can put the three American English sessions side by side; `anchors` uses whichever of the four are given and prints how many bands it scored over. All four papers are copyrighted and outside the repository by policy, so `make check` cannot run any of it and each subcommand prints why and exits 0 without its source — the shape `scripts/articulatory.py` already uses.

Both transcribed tables are checked against themselves, because a transcription of a printed table cannot be checked against the table. Each paper prints a tract length and a section length per column as well as the sections, and the parse re-derives one from the others and fails if they disagree. The two identities are not the same and getting them the wrong way round shifts every arc by half a section: Yang & Kasuya's length is `(sections − 1) × dl`, Story's is `sections × dl`. Yang & Kasuya's scan has no text layer and was transcribed from a 300 dpi render; Story (2008) is a real HTML table on PubMed Central, and the one substitution needed there was that its open-mid front vowel is spelled with a Greek epsilon rather than the IPA one.

The 1998 table adds a check of its own, because it needs one the others do not. Its columns are ragged — 30 sections for `æ` against 38 for `u`, which is the table's own record of how much a rounded vowel lengthens a tract — so a dropped or duplicated line shifts every section under it by one without making any single number look wrong. That paper prints the distance from the glottis beside the section number, so `parse_female` re-derives one from the other for every row and refuses a row more than half a section from where its own section number puts it. The bound is half a section rather than a rounding because the two tables round that column differently: Table III prints `section × 0.396825` and Table IV prints `section × 0.396`, though both captions state the interval as 0.396 825 cm.

## Related

- [vowel-chart-geometry.md](vowel-chart-geometry.md) — the third route, which takes the location out of the vowel chart's own geometry instead of out of a source, and refuses it
- [tract-validation.md](tract-validation.md) — the first external check, which found the defect and named Wood as the evidence it lacked
- [../articulatory-data.md](../articulatory-data.md) — the X-Ray Microbeam measurement, and why that instrument cannot see a vowel constriction behind `arc` 0.44
- [../tract-anatomy.md](../tract-anatomy.md) — §6, the derived quantities, and what is computed rather than asserted about them
- `tests/test_vowel_tract_limit.py` — the limit, pinned so it can only move deliberately
