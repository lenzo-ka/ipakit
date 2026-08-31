# A constriction location from the vowel chart: assessment

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

[#123](https://github.com/lenzo-ka/ipakit/issues/123) is that a vowel reads its tract position from `backness` and nothing else, so `u o ɑ ɔ ʌ` all sit at `arc` 0.56. Two passes established that the values that would fix it by declaration do not exist: no coordinate per `(height, backness)` cell reproduces across sources, across languages, or across one speaker imaged twice, and almost nothing classifies the central series. This is the third route, and it does not go through a source at all. The IPA vowel quadrilateral is a **stated figure** with its two axes named as height and backness, and its proportions were fixed by publication rather than estimated from data. Placing it in the mid-sagittal plane and projecting each cell onto the tract wall is a geometric operation with a real answer, and that answer would be a declaration rather than a fit — checkable against measurement instead of validated against the data that produced it. That is exactly the shape of evidence the first two passes could not obtain.

**Verdict: NOT DEFENSIBLE, on three independent grounds, and measured anyway to show what it does.**

**The premise is refused by the IPA in print.** The quadrilateral is not a stated model of tongue-body position. *Handbook of the IPA* (1999) p. 10 says the vowel space "bears a relation, though not an exact one, to the position of the tongue in vowel production", p. 11 that the figure is a stylization of that space, and pp. 11–12 that because six of the eight cardinal anchors are defined by auditory equidistance rather than by articulation, "the vowel quadrilateral must be regarded as an abstraction and not a direct mapping of tongue position". Deriving an articulatory constriction location from it would import a claim the Association itself declines to make.

**The figure's own asymmetry predicts the interaction backwards, and Jones says why.** The measurement that killed every additive and multiplicative declaration is that height moves the constriction −0.011 at the front (`i`→`ɛ`) and +0.267 at the back (`u`→`ʌ`), a difference of +0.279. Jones documents the figure's back edge as shorter than its front edge, and gives the reason: between the four back cardinals the tongue moves *less*, because "the differences in tamber between Nos. 5, 6, 7, and 8 are produced by differences of tongue-position combined with important differences of lip-position". So the figure asserts less tongue movement per height step at the back, and any projection of it must put less constriction movement there. The tract does the opposite, by a third of its length.

**And the construction is more unreproducible than the coordinate already refused.** The figure has no scale, no anatomical anchor, and no rule taking a cell to a position, so a projection needs corners, a standoff and a reading, none of which is the chart's to state. Two readings of "lay the quadrilateral in the mid-sagittal plane" — flat, and wrapped around the tract's own bend — pinned to the same three anatomical corners and projected onto the same midline, disagree about one cell by 0.534 of tract length. That is more than twice the declared `backness` span of 0.24 and nearly twice the 0.284 cross-source spread that refused a fitted cell table on the first pass.

Measured over 120 embeddings — two readings, three front-edge insets including the figure's own, five tongue-body standoffs, and both defensible choices for two of the three corners — the height interaction runs **−0.341 to +0.037**. It is positive in 7 and reaches +0.279 in none. Band inclusion runs 9 to 25 of 35, against 14 for `backness`, 25 for Wood's four families read at the arcs `place` declares, and 26 for Wood's own proportions. **No embedding beats the classification.** Nothing was tuned: the best score in the family is reached by looking at the scores and taking the best one, which is the fit this line of work has now refused three times.

The assessment changed no data and moved nothing in the metric. It adds this document, a `chart` subcommand to `scripts/areafunctions.py`, two pins in `tests/test_vowel_tract_limit.py`, and a changelog line.

## Summary of findings

| Question | Finding |
|---|---|
| Is the quadrilateral a stated model of tongue position? | **No — the IPA says so itself.** "an abstraction and not a direct mapping of tongue position", *Handbook* pp. 11–12. Six of the eight cardinal anchors are defined by auditory equidistance. |
| Is the figure free of parameters to fit? | **As a diagram, yes, and its proportions are documented.** Jones states 2:3:4 for the open, back and close edges with right angles at `ɑ` and `u`; the 2020 chart reproduces that to within 4%. |
| Then is a projection free of parameters? | **No.** The figure states no scale, no anatomical anchor and no cell-to-position rule. Corners, a standoff and a choice of reading all come from outside it. |
| Does the trapezoid's asymmetry produce the height × backness interaction? | **No, and it has the wrong sign.** The measurement needs +0.279; 120 embeddings give −0.341 to +0.037 and never reach it. |
| Which edge is short, and why? | **Both asymmetries are real.** The back edge is shorter than the front, and the open edge shorter than the close. Jones's reason for the first is that the lips do part of the work between the back cardinals, so the *tongue* moves less there — which predicts less constriction movement at the back, not more. |
| Where does the interaction actually come from? | The **tract's bend**. Wood 1975 states it: "Owing to the 90° bend in the vocal tract, this parameter is varied by raising or lowering the tongue for the palatal constrictions but by advancing or retracting the tongue for pharyngeal constrictions." That geometry is ipakit's already, and behind `arc` 0.45 every point of it is extrapolated rather than measured. |
| Is a projected location reproducible? | **No, and it is worse than the coordinate already refused.** One cell moves 0.534 of tract length across the embedding family, against a declared span of 0.24 and a 0.284 cross-source spread. |
| Does it beat `backness` on band inclusion? | **Usually, and never by enough.** The flat reading is above `backness` at 50 settings of 60; it reaches `place`'s 25 at 3 and beats Wood's 26 at none. |
| Has anyone tried this mapping before? | **Yes, and reported it failing.** Ladefoged & Maddieson replot the cardinal vowels in constriction coordinates and find "The groupings in this figure do not form any obvious natural classes from a linguistic point of view." |
| Is there a defense of the chart's articulatory status? | **Yes, and it is about ordering, not coordinates.** Lindau (1978) measures the highest point of the tongue against the auditory chart at *r* = 0.92 for height and 0.96 for backness over five speakers, and concludes neither domain is the better correlate. Nobody defends a per-vowel, per-speaker reading. |
| Does the surviving model support this parameterization? | **It exists to attack it.** Wood 1975: "tongue height is useless as an articulatory parameter of vocal tract shaping", and rectifying the coordinates would not help. His four families are what beat everything measured here. |
| Does the carrier [#160](https://github.com/lenzo-ka/ipakit/issues/160) landed take a projected value? | **No.** `constriction-location` declares `vocabulary="place"`, so it holds one of twelve place names and their declared arcs. A projection needs 35 numbers, one per cell, and that is the table refused twice. |
| Is any of this new information for the library? | **Half of it is already declared.** The five `backness` arcs are the quarters of `palatal` to `uvular` to within 0.01, and the seven `height` offsets reproduce the drawn rows to within 0.03. ipakit already is the chart; what a projection would change is which axis reaches `arc`. |

## Sources

- International Phonetic Association (1999). *Handbook of the International Phonetic Association*. Cambridge University Press. §2.6 "Vowels", pp. 10–12. Read directly, 2026-08-03; `docs/reading.md` records it as paywalled and a copy was obtained for this pass.
- Jones, Daniel (1969). *An Outline of English Phonetics*, 9th edition. Heffer. §§119, 131–140, 149–155, and the footnotes to §§134 and 149. Read directly, 2026-08-03.
- International Phonetic Association, *The International Phonetic Alphabet (revised to 2020)*, Kiel edition. <https://www.internationalphoneticassociation.org/IPAcharts/common_files/pdfs/pdfs_IPA_charts_archive/IPA_Kiel_2020.pdf>. CC BY-SA 4.0. The figure's geometry in §2 is measured from this file's content stream.
- Russell, G. Oscar (1928). *The Vowel*. Ohio State University Press. Chapter X and p. 325.
- Wood, Sidney (1975). "Weaknesses of the tongue-arching model of vowel articulation", Working Papers 11, Lund University, 55–107. <https://journals.lub.lu.se/LWPL/article/view/17002>. Open access, and named in `docs/reading.md` as the argument this document needed.
- Wood, Sidney (1979). "A radiographic analysis of constriction locations for vowels", *J. Phonetics* 7(1), 25–43. <https://doi.org/10.1016/S0095-4470(19)31031-9>.
- Lindau, Mona (1978). "Vowel features", *Language* 54(3), 541–563. <https://doi.org/10.2307/412786>.
- Ladefoged, Peter & Ian Maddieson (1996). *The Sounds of the World's Languages*. Blackwell. Chapter 9, pp. 282–285.
- Ladefoged, Peter & Keith Johnson (2015). *A Course in Phonetics*, 7th edition. Cengage. pp. 95 and 231.
- Catford, J. C. (1977). *Fundamental Problems in Phonetics*. Edinburgh University Press. pp. 167, 184–186.
- Strycharczuk, Patrycja, Sam Kirkham, Emily Gorman & Takayuki Nagamine (2025). "Dimensionality reduction in lingual vowel articulation", *Language and Speech* 68(3). Open access.
- Story, Titze & Hoffman (1996), Story (2008) and Yang & Kasuya (1994) — the three band sets, so the counts here are on the same 35 as [vowel-constriction.md](vowel-constriction.md) §8.

The chart's own measurements below cannot drift: they are of one published PDF and one printed footnote. What they are compared against can — `height`, `backness` and `place` in `ipakit/data/ipa.xml`, and the midline in `ipakit/data/heads.xml`. `scripts/areafunctions.py chart` reads both sides live.

## 1. The premise, stated as strongly as it deserves

The argument for trying this is good and should be recorded properly before it is refused, because it is the best argument anyone has made about #123.

Every route so far has ended in the same place. A coordinate per cell has to be a number, and the sources that measure it disagree by more than the span it would have to resolve — across speakers, across languages, and for one speaker imaged twice eight years apart. A partition into Wood's four families does reproduce, and ipakit's declaration vocabulary cannot state a partition of a plane. So the library is stuck between a value it cannot check and a shape it cannot say.

The quadrilateral looks like a way out of exactly that. It is not a dataset and it was not fitted to one: its proportions are stated in a textbook and reproduced by the Association's own drawing, and its two axes are the two features ipakit already declares. Project it and you get a location per cell that nobody chose. Then hold that location against measured area functions — a check the model could genuinely fail, run on data that had no hand in producing it. That is the methodology this project has been asking for, and the objection below is not to the methodology. It is that the object it would be applied to is not what it was taken to be.

## 2. What the figure actually is, and what it is a picture of

### The geometry, measured

Off the Association's own drawing, by interpreting the page's content stream and reading the coordinates of the lines it strokes. This is deliberately not read from the text layer: the chart's glyphs are in a custom-encoded font and extract to about nine real code points, which this project already records as a trap. The *paths* are ordinary numbers.

In page points, the quadrilateral is:

| edge | from | to | length |
|---|---|---|---|
| close, `i`–`u` | (381.3, 501.2) | (532.7, 501.2) | 151.4 |
| open, `a`–`ɑ` | (458.9, 386.3) | (532.7, 386.3) | 73.8 |
| front, `i`–`a` | (381.3, 501.2) | (458.9, 386.3) | 138.7 |
| back, `u`–`ɑ` | (532.7, 501.2) | (532.7, 386.3) | 114.9, vertical |

That is Jones's figure, drawn to his stated proportions. His footnote to §149 gives the simplified form as having the close, open and back edges "in the proportion 2:3:4" — reading his `a—ɑ`, `ɑ—u`, `i—u` as open, back and close — with right angles at `ɑ` and `u`. Measured, the three come out 2 : 3.11 : 4.10, and the two angles at the back edge are right. The 2020 chart reproduces a 1969 footnote to within 4%.

**Both asymmetries are real, and they are different facts.** The back edge is shorter than the front edge, 114.9 against 138.7 — which is what a brief calling this "a trapezoid with the back edge shorter" is pointing at, and it is correct. Separately, the open edge is shorter than the close edge, 73.8 against 151.4, which is what makes the front and back columns converge as a vowel opens. Jones chose the first deliberately, and says what it is for: the form should show "that the distance i—a is longer than the distance ɑ—u and which does not suggest that u has a more retracted tongue-position than ɑ".

The four struck rungs — close, close-mid, open-mid, open — sit at y 501.2, 463.4, 425.5 and 386.3, evenly spaced to within 1.4 points. Near-close, mid and near-open are not struck; their positions come from the text-positioning matrices of the symbols placed on them, which give a baseline per row without anyone having to decode which glyph is which. Normalized by the 114.9-point drop the seven rows are at 0.000, 0.155, 0.328, 0.489, 0.657, 0.820 and 0.999 — an even seven-rung ladder to within 0.013. The struck central column is at 0.500 across; near-front and near-back are not drawn.

### What it is a picture of

The figure's own documentation says it is not a tongue-position diagram, and it says so twice over.

The IPA's *Handbook* introduces the space as an abstraction from the start: vowels "cannot easily be described in terms of a 'place of articulation' as consonants can", so they are classified in an abstract vowel space, and "This space bears a relation, though not an exact one, to the position of the tongue in vowel production" (p. 10). The quadrilateral is then explicitly a stylization of that space rather than the space itself — the four extreme tongue positions give a boundary, and "For the purposes of vowel description this space can be stylized as the quadrilateral shown in the second part of figure 4" (p. 11). And the conclusion, pp. 11–12:

> The use of auditory spacing in the definition of these vowels means vowel description is not based purely on articulation, and is one reason why the vowel quadrilateral must be regarded as an abstraction and not a direct mapping of tongue position.

Jones's own account is the same shape and is more specific about which parts are which. Cardinal 1 and cardinal 5 are defined articulatorily — the tongue as far forward and high, or as far back and low, as it can go and still be a vowel. Cardinals 2, 3, 4, 6, 7 and 8 are defined by ear: "chosen so as to form an acoustic sequence between the vowels 1 and 5 such that the degrees of acoustic separation between each vowel and the next are equal" (§133). The outline was drawn from radiographs of Jones's own mouth, "the relative positions of i, a, ɑ, and u having been obtained from X-ray photographs" (§149), taken in 1919 — one speaker — and the outline was then straightened, because "The shape of this diagram is a compromise between scientific accuracy and the requirements of the practical language teacher. Scientific accuracy would require a diagram with curved sides."

**So six of the eight anchors are auditory, the four corners are one man's radiographs, and the shape between them is a teaching convenience.** That is not a geometry anything can be measured off, and this is before any of the twentieth-century X-ray literature is consulted.

## 3. What a projection needs that the chart does not give

Placing the figure in the mid-sagittal plane and reading an `arc` off it takes four things, and the chart states none of them.

**Corners.** The figure has no scale and no anatomical anchor. Something has to say where the close front corner *is*. The least arbitrary answer, and the one most favorable to the construction, is to pin three corners to places `ipa.xml` already declares under the names Wood's four locations carry: close front at `palatal` 0.32, close back at `velar` 0.45, open back at `pharyngeal` 0.74. Three points fix an affine map, so the open front corner then falls where the trapezoid puts it. This is generous — it hands the construction three of the answers before it starts, and every corner lands on its own anchor by construction. What is being asked of the projection is only the interior.

**A standoff.** The tongue body is not on the midline; it stands off it, and the projection is from the body to the wall. The standoff cancels at the corners and does not in the interior, so it is a free number. Swept here from 0.02 to 0.16 of head height, roughly 0.3 to 2.7 cm.

**A reading.** "Lay the quadrilateral in the mid-sagittal plane" is not one instruction. Two readings are equally faithful to the figure:

- **Flat.** The figure is a plane region and goes in as one, three corners pinned. Height is then a single direction everywhere — the displacement that carries a close back vowel down the pharynx carries a close front vowel back along the palate.
- **Wrapped.** The figure is read as the tongue *arch* it was named for. Backness is an angle about the center of curvature of the tract — not a free parameter, it is the circle through the palatal, uvular and pharyngeal midline points — and height is how near the arch comes to the wall.

**And a tract.** The midline these project onto is ipakit's, and its provenance is not uniform: of ten declared points exactly three are `measured` (arcs 0.24, 0.32 and 0.40) and the rest are `extrapolated`. Everything behind `arc` 0.45 is drawn, because `docs/articulatory-data.md` records that the X-Ray Microbeam instrument sees nothing behind 0.44. A projection whose behavior comes from the tract's bend is taking it from there.

## 4. The interaction, which is the whole question

`python scripts/areafunctions.py chart`

The measurement that killed every additive and multiplicative declaration is an interaction: height barely moves the constriction at the front and moves it a third of the tract at the back. If the geometry produces that on its own, the construction is worth having whatever else is wrong with it. It is the first thing to check and it is decisive.

Height's effect at fixed backness, measured from Story et al. against the two readings at the figure's own inset and a 0.04 standoff:

| reading | front, `i`→`ɛ` | back, `u`→`ʌ` | back − front |
|---|---|---|---|
| measured | −0.011 | +0.267 | **+0.279** |
| flat | +0.289 | +0.199 | −0.090 |
| wrapped | +0.152 | −0.009 | −0.161 |

Both get it backwards, in different ways: the flat reading moves everything too much and the front worst, the wrapped one moves the back not at all. Over all 120 embeddings the difference runs **−0.341 to +0.037**, is positive in 7, and reaches +0.279 in none.

**The figure is built to say the opposite, and Jones says so in as many words.** §§137–139 explain why the back edge is short: between cardinals 1 to 5 the differences are made mainly by the tongue, whereas "the differences in tamber between Nos. 5, 6, 7, and 8 are produced by differences of tongue-position combined with important differences of lip-position", and "It is for this reason that the distances between the tongue-positions of Nos. 5, 6, 7, and 8 are less than the distances between the tongue-positions of Nos. 1, 2, 3, and 4." The back column is drawn short *because the tongue moves less there*. Any projection of the figure inherits that and must put less constriction movement at the back than at the front. The tract puts +0.267 there and −0.011 at the front.

The second asymmetry fails the other measured pattern. A trapezoid narrowing toward the open end brings the front and back columns together as the vowel opens, so the backness effect must *shrink* with openness under any projection. Measured, it grows: +0.106 from `i` to `u`, +0.284 from `ɪ` to `ʊ`, +0.385 from `ɛ` to `ɔ`. It is worth being exact about where that growth stops, because it is a further difficulty rather than a rescue: at the open end it collapses, `æ` constricting at 0.655 and `ɑ` at 0.670, and Wood says the same thing structurally by giving front and back open vowels one family. A converging trapezoid produces a gradual shrink, not growth to open-mid followed by collapse.

And the interaction the tract does have does not come from the chart. It comes from the bend — over the oral run the tract axis is roughly horizontal, so lowering the tongue body moves it across the axis and barely along it, while in the pharynx the axis is roughly vertical and the same motion is along it. Wood had that in 1975, arrived at from the other side. Writing about constriction *degree* rather than location, he says: "Owing to the 90° bend in the vocal tract, this parameter is varied by raising or lowering the tongue for the palatal constrictions but by advancing or retracting the tongue for pharyngeal constrictions." Read against the measurement the two halves fit exactly. At the palate raising and lowering the tongue is what sets the degree, which is why height moves `offset` there and not `arc`; in the pharynx the degree is set by the root instead, which leaves height free to move the location, and it moves it a third of the tract. The geometry that produces the interaction is anatomy, it is already in `heads.xml`, and it is the half of `heads.xml` that is extrapolated.

## 5. Band inclusion, on the same 35 bands

The same instrument as everywhere else in this line of work — the data states an extent, and the anchor is inside it or not. Not a rank correlation, and [tract-validation.md](tract-validation.md) §3 says why in a sentence that transfers to this construction with one word changed: "Any figure reported here is a report of the cutoff, not of the model."

Over the 35 bands the three tabulated sources supply:

| reading | worst | best | above `backness` | reaching `place` |
|---|---|---|---|---|
| flat | 10 | 25 | 50 of 60 | 3 of 60 |
| wrapped | 9 | 19 | 22 of 60 | 0 of 60 |
| `backness` | 14 | 14 | | |
| `place`, Wood's four families | 25 | 25 | | |
| Wood's own proportions | 26 | 26 | | |

**Superseded by [#175](https://github.com/lenzo-ka/ipakit/issues/175), and the baseline column corrected — in the direction that strengthens the verdict below.** The `backness` row and the `above backness` column were scored over nine of Yang & Kasuya's fifteen columns while every other row was scored over all fifteen: `cmd_chart` asked `declared()` for a reading without naming the symbols it meant to score, and Story images no Japanese `/a/` and no `/e/`, which is the bias that function's own signature exists to prevent. The row is 17 rather than 14; `above backness` is 35 of 60 for the flat reading rather than 50, and 8 of 60 for the wrapped one rather than 22. The script now scores the baseline over the same fifteen columns as the rest of the table, and prints there the *library's* reading rather than `backness`, which is what it had in fact been computing ever since `constriction-location` landed — on these same 35 bands that is 26, and no embedding of either reading beats it at any setting of either free parameter.

The honest reading of that table has two halves. The flat projection is genuinely better than `backness` more often than not — it is not a worthless construction, and saying so is part of the result. And **it beats the classification at no setting of either free parameter.** It reaches `place`'s 25 at three settings of sixty, and the way to find those three is to look at the scores and take the best, which is a fit to the bands being scored against. `vowel-constriction.md` refused a table on that ground and then refused a coordinate on it again; there is no third standard for the same move performed with a ruler.

Even the first half does not survive a change of source. Run on Story 1996 alone — the ten bands `vowel-constriction.md` §3 uses — `backness` scores 5, `place` 6 and Wood 7, and the two readings run 3 to 5 and 2 to 5. On that source **no embedding of either reading beats `backness` at any setting.** So "better than `backness` more often than not" is itself a report of which sources are mounted.

The spread is the honest summary. Per cell, across the whole family:

| cell | lowest | highest | spread | measured |
|---|---|---|---|---|
| `a` | 0.327 | 0.861 | **0.534** | 0.568 |
| `æ` | 0.326 | 0.820 | **0.494** | 0.655 |
| `ɛ` | 0.325 | 0.779 | **0.453** | 0.263 |
| `u` | 0.457 | 0.867 | **0.410** | 0.380 |
| `e` | 0.323 | 0.637 | 0.314 | 0.477 |
| `o` | 0.576 | 0.864 | 0.288 | 0.375 |
| `ʊ` | 0.472 | 0.745 | 0.273 | 0.534 |
| `ɑ` | 0.672 | 0.880 | 0.208 | 0.670 |
| `ɔ` | 0.658 | 0.861 | 0.203 | 0.648 |
| `ʌ` | 0.658 | 0.861 | 0.203 | 0.648 |
| `ɪ` | 0.392 | 0.515 | 0.123 | 0.250 |
| `i` | 0.322 | 0.367 | 0.045 | 0.274 |

The declared `backness` span is 0.24 end to end. Eight of these twelve cells move further than that on choices nobody has a source for, and four move further than the 0.284 cross-source disagreement that refused the fitted table. The close front corner is stable at 0.045 because it is pinned; the rest is embedding.

## 6. The figure plots one thing and the location is another

The objection above is that the projection is underdetermined. This one is that even a determined projection would be computing the wrong quantity, and it does not go away with more anatomy.

The quadrilateral plots a **point** — the highest point of the tongue in the traditional articulatory reading, an auditory quality in the IPA's own. The quantity ipakit's `arc` names, and the quantity every band in this document measures, is the **narrowest section of the area function**. Those coincide only where the tongue body is what makes the tract narrow.

For an open vowel it is not. Lowering the tongue body opens the oral tract, and the tongue is a volume-conserving organ, so the same gesture carries the root back into the pharynx and the narrowest section is made *there*, by a different part of the tongue. This is not an inference: `æ` has no supralaryngeal local minimum narrower than 1.94 cm² against `i`'s 0.10, and it constricts at 0.655, behind every back vowel except `ɑ`. Wood reaches it from the other side by giving front and back open vowels one family.

Two consequences.

**A continuous projection has to pass through the jump.** On the front column the measured locations are 0.274, 0.250, 0.263 and then 0.655 — three rungs inside 0.024 of each other and a fourth 0.39 away. That is not a steep gradient; it is the argmin of the area function changing which of two local minima it names, and the ranks swap discontinuously while the posture moves smoothly. A projection of a straight chart edge onto a smooth wall has a bounded derivative and cannot do it. The flat reading's front column steps by 0.042, 0.043, 0.086, 0.118, 0.044 and 0.044 instead, spending four rungs in a region where this speaker's tract has no constriction at all.

**And the articulator changes underneath the declaration.** Every `backness` value declares `articulator="tongue-dorsum"`. For the open vowels the measurement says root, and `docs/tract-anatomy.md` §6 lists the active articulator as a derived quantity — "which mobile structure forms the constriction at that location" — that the place table currently declares as a default. A projection of the chart would put a dorsum where the tract is narrowed by a root, and nothing in the model would report it, because the value *was* read.

**This is not a new idea and it has been tried.** Ladefoged & Maddieson replot the cardinal vowels in exactly these coordinates — the Stevens & House constriction parameters, the same three-parameter model Wood feeds his four locations to — and report what came out: "The groupings in this figure do not form any obvious natural classes from a linguistic point of view." The mapping fails in the direction opposite to the one proposed here, which is worth more than a failure in the proposed direction, because it means the two spaces do not correspond rather than that one projection of one onto the other was badly chosen.

## 7. Whether the chart is an articulatory space at all

The standing objection was that the quadrilateral may be closer to an auditory or F1/F2 space than an articulatory one, and that building on it would import a claim much of the field rejects. That is roughly right, and the literature is more specific than "contested" in a way that matters here.

**The critical line runs from 1928 and is about this exact operation.** Russell X-rayed vowels and found the plotted tongue positions did not reproduce the triangle: "the point of arching for the u is not much farther back than is that for the front vowels", and "The point of arching for the e, a, ɔ, and o, is not against the velum or upper throat at all, but rather towards the back throat, or posterior wall of the pharynx, down by the epiglottis." His summary sentence is the one usually quoted — that phoneticians "were thinking in terms of acoustic fact and using physiological phantasy to express the idea" — but the load-bearing finding for this document is the one about speakers: "individuals show variation in the tongue positions taken, for this back group in particular, which is almost as great as the differences between their facial features. That is one of the most outstanding reasons why the physiological vowel triangle must be considered unreliable, and without value."

Ladefoged's textbook carries the same argument with the plot: the highest point of the tongue in a set of cardinal vowels "form an outline very different from" the quadrilateral, and "The position of the highest point of the tongue is not a valid indicator of vowel quality." He keeps *high, low, front, back* as terms while saying they describe "auditory qualities rather than tongue positions". Ladefoged & Maddieson state it without polemic: the labels were "originally proposed as descriptions of actual articulatory characteristics", but "it is not at all clear that the classes of vowels defined by tongue body positions are the same as those defined by the traditional use of these terms", and the measured inversions include that the tongue height of `ʊ` is below that of `ɪ` and that of `o` below that of `æ`.

**Wood is the sharpest, and it matters that he is the author whose model this project adopted.** His 1975 working paper is titled for the argument. It says the tongue-arching model "was a product of the imagination that was never confirmed in serious tests"; that "The tongue positions prescribed by the model do not agree with those observed in actual speech"; that height's effect "varies according to the location of the tongue constriction in the vocal tract", so "tongue height is useless as an articulatory parameter of vocal tract shaping". And it forecloses the repair this document set out to test:

> It would not therefore be sufficient simply to rectify the location of the errant vowels in the polygon by assigning the 'correct' coordinates. It would still be impossible to predict the resonator configuration satisfactorily, and hence the spectrum, from the coordinates.

So the four constriction locations that beat every other reading on the bands come from a paper whose thesis is that the two coordinates a chart projection would use are the wrong variables. Adopting Wood's families and deriving locations from the chart's geometry are not two compatible improvements; they are opposite answers to one question.

**The defense exists and is worth stating exactly, because it is narrower than it first looks.** Lindau measured five speakers cineradiographically and concluded that "Ladefoged has overstated his case: the traditional highest point of the tongue is virtually as good a measure of height and backness as the formant chart is" — auditory height against tongue height at *r* = 0.9207 where F1 gives 0.9522, auditory backness against tongue backness at 0.9649 where F2−F1 gives 0.9817 — and that "the features High and Back may be defined in both articulatory and acoustic terms. Neither domain can justifiably be preferred as the better correlate." Catford builds a constriction-location alternative that he thinks is "more in accord with the articulatory parameters involved", then keeps the quadrilateral for practical and proprioceptive reasons. The most recent test, 28 speakers by ultrasound, lands with the moderates and sharpens the limit: two dimensions suffice in principle, but "two dimensions of lingual vowel contrast do not have robust and reliable physical correlates across different vowels", "the optimal measures of articulatory retraction and raising may be different for different vowels", and such models "cannot serve as the foundation for extracting reliable articulatory measurements".

**What the defense defends is the ordering, averaged over speakers.** No one in it defends reading a coordinate off a cell for one vowel — which is what a projection is — and the strongest defender's own numbers are correlations over a normalized five-speaker average. That is a claim about a scatter plot, not about where `ɔ` constricts.

The one place the whole literature agrees is where it bears hardest here. Wood's abstract classification is fine and the coordinates are not, and he says why the confusion persists: "Many have continued to rely on the model simply because it has provided a convenient abstract classification system … An abstract classifying system is consequently not affected by any errors of fact regarding speech production providing the categories remain intact." That is exactly the license ipakit needs and exactly the license it would give up. `height` and `backness` as declared names for vowel qualities are unaffected by any of this. `height` and `backness` as a coordinate system a location is projected out of are the thing every source above refuses.

## 8. ipakit already is the chart

The last finding changes how the question should be asked, and it is checkable rather than arguable. Both pins are in `tests/test_vowel_tract_limit.py`.

**The five `backness` arcs are the quarters of the span from `palatal` to `uvular`, to within 0.01.** Declared: 0.32, 0.37, 0.44, 0.50, 0.56. The even ladder from 0.32 to 0.56: 0.32, 0.38, 0.44, 0.50, 0.56. Only `near-front` differs, by 0.01. So a vowel's `arc` today already *is* the chart's front-to-back axis laid linearly on the tract between two anatomical anchors — the horizontal half of exactly what a projection would compute, and it has been there all along.

**The seven `height` offsets reproduce the figure's own rows to within 0.03.** As fractions of the close-to-open span the declared offsets fall at 0.000, 0.152, 0.303, 0.485, 0.667, 0.848 and 1.000, against the 0.000, 0.155, 0.328, 0.489, 0.657, 0.820 and 0.999 measured off the drawing in §2.

So the chart is not a new source of information for this library. It is what the library declares, in both axes, faithfully. The vertical axis is declared as `offset` — constriction *degree* — and the entire content of the proposal is to route it into `arc` as well. That is the axis the measurement refuses, in sign, over 120 ways of doing it.

Put that way the proposal reduces to something already pinned. A projection is a function from a `(height, backness)` cell to a number; it fills 35 cells; and how the numbers are chosen — fitted to one MRI study, or drawn with a ruler — does not change what has to be true of them. [vowel-constriction.md](vowel-constriction.md) §5 puts the shape of the obstacle in one sentence, and a ruler does not get around it: "Every coordinate in `ipa.xml` is one feature, one value, one number, and no such declaration states a partition of a plane."

## 9. What it would have cost, and why the carrier does not fit

Recorded because the brief for this work assumed the mechanism was in place, and it is not, quite.

[#160](https://github.com/lenzo-ka/ipakit/issues/160) landed a `constriction-location` slot that the vowel branch reads ahead of `backness`. It declares `vocabulary="place"`, so a nucleus states one of the twelve place *names* and the arc comes from that place's own declaration — which is why adopting Wood's four families would cost nothing and move no consonant. A projected location is not a place name. It is a number per cell, 35 of them, none coinciding with a declared place, and the slot as built cannot hold one. Carrying it would mean either 35 new `place` values, or a second coordinate table keyed on two features, which is the cell table refused on the first pass and again on the second.

The rest of the cost is unchanged and is real: `arc` reaches `ipakit.metric` through `_tract_x`, so moving the vowel anchors moves a large part of the matrix and `confusion.json` has to be regenerated with every mover explained. None of it was incurred, because the values do not survive §4.

## 10. How to re-run this

```console
$ python scripts/areafunctions.py chart      # sections 4 and 5
```

The three band sources are copyrighted and outside the repository by policy, so `make check` cannot run it: without `--source` it prints why and exits 0, the shape every other subcommand here uses. `--second` and `--third` add the other two band sets; with only `--source` the counts are out of 10 rather than 35, and the run says which.

The chart geometry in §2 needs no source and is transcribed into `scripts/areafunctions.py` as constants carrying the page coordinates they were read from, because a PDF is not something a subcommand should parse to answer a question that has been answered once. The rows and the inset are the only numbers taken from it, and §8 is the check on them: if the declared ladders and the drawn ones stop agreeing, the two pins fail and this document's argument needs re-reading.

## Related

- [vowel-constriction.md](vowel-constriction.md) — the two passes that looked for the values, and Wood's four families, which this is measured against
- [tract-validation.md](tract-validation.md) — the first external check, the band instrument, and why a rank correlation is refused
- [../tract-anatomy.md](../tract-anatomy.md) — §6, the derived quantities, and the active articulator this projection would get wrong
- [../reading.md](../reading.md) — Wood 1975 and 1979, and why they are read for the argument against height and fronting
- `tests/test_vowel_tract_limit.py` — the limit, and the two pins holding the declarations against the figure
