# Phonetic distance in ipakit

How `distance`, `segment_distance`, `word_distance`, and the shipped confusion matrix compute their numbers: the representation they read, the comparison they perform, and what the results do and do not mean. [similarity.md](similarity.md) is the standing justification for these commitments and the record of what does and does not validate them.

## Quick reference

| | |
|---|---|
| Range | `[0, 1]`; 0 identical, 1 maximally different |
| Three scales, three names | `distance` (structural, `[0,1]`), `normalized_distance` (percentile in a reference inventory, `[0,1]`), `WordDistanceResult.edit_cost` (summed alignment cost, **unbounded**) |
| Basis | Articulatory structure — where a constriction is, what makes it, how close it is |
| Claim | Structural consistency; **not** a model of perceptual confusability |
| Symmetry | `d(x, y) == d(y, x)`, by construction: each directional reduction is wrapped in `max(a→b, b→a)` |
| Triangle inequality | **Not guaranteed** — see [Not a metric](#not-a-metric-in-the-mathematical-sense) |
| Silence | `d(␣, X) == 1.0` for every speech sound `X` |
| Weighting | None; every dimension contributes equally at maximal difference |
| Word alignment | a gap costs `GAP_COST`, a substitution costs `(delete + insert) ×` the pair's dissimilarity, and `similarity` is normalized by the null alignment's cost |
| Length asymmetry | reported as `WordDistanceResult.coverage`, never folded into the score |
| Parameters | Word gaps use `GAP_COST = 1.0`; segment material uses the declared `MATERIAL_BUDGET`; secondary place sharing uses `SECONDARY_WEIGHT = 0.5` in `ipakit/metric.py` |
| Regenerate after changes | `python scripts/confusion.py generate --write` |

If you need perceptual confusability — which sounds listeners actually mistake for each other — this metric is a reasonable structural prior, not a substitute for confusion data. See [Implications](#implications-for-users).

## 1. What a segment carries

A constriction is three facts, and ipakit stores all three:

| fact | feature | meaning |
|---|---|---|
| **what moves** | `articulator` | the active organ: lower lip, tongue tip/blade/front/dorsum/root, epiglottis, vocal folds |
| **where it goes** | `arc` | position along the tract midline, 0 at the lips to 1 at the glottis |
| **how close** | `offset` | constriction degree, 0 at the open midline to 1 at full closure |

`arc` and `offset` are declared per feature value in `data/ipa.xml`: consonants take `arc` from `place` and `offset` from `manner`; vowels take `arc` from the `constriction-location` they state, or from `backness` where they state none, and `offset` from `height`. The vowels a source classifies state one — the families Wood (1979) reproduces and names again in Wood (1990), read at the arcs `place` already declares — and the rest do not, so the rest take `backness`. That fallback is reported rather than passed off: `tract_reading` returns `backness` in `approximated` and `unmodelled` gives it kind `approximate`, because `backness` says where the tongue body is and not where it constricts. The consonant values are hand-placed from published mid-sagittal anatomy and are schematic, not measurements.

The articulator is declared per place value as a default and overridden per phone where it differs. Place names the *target*, not the mover: a linguolabial `t̼` is the tongue tip at a labial target, and `t̺`/`t̻` differ only in which part of the tongue arrives. A combining place combines its articulators, so `w` moves the lower lip and the dorsum both.

The metric reads *every* constriction a segment makes, not one summary point: the tract-`x` term is the set of arcs a segment closes at — two for a double articulation (`w` at the lips and the velum) or a click (its named place and the velum) — compared by directional best-match, the reduction place components already take. A single constriction is a one-element set, so its distance is the plain difference it always was and no single-constriction pair moved. A rhotacized nucleus is the exception the evidence forces: it declares `constriction="unlocalized"` because [docs/design/vowel-constriction.md](design/vowel-constriction.md) §6 finds no single arc the sources support, and the metric withholds its tract-`x` term entirely — scored neither as agreement nor as maximal difference, so no position is invented and its absence is not punished.

Everything above is head-independent. A head shape (`data/heads.xml`) projects these coordinates to 2D for rendering; heads never enter distance, so the shipped matrix does not depend on whose vocal tract you picture.

## 2. Why anchors rather than scale positions

Ordinal features could compute distance from declaration order — value *i* to value *j* costs `|i−j|/(n−1)`. ipakit does that only for features without anchors. Where anchors exist, they are used instead, for three reasons:

**Steps are not uniform.** The lips-to-teeth move is much smaller than the velum-to-uvula move, though both are one label apart. Index distance prices them identically; anchors do not.

**Dimensions become commensurable.** `place` and `backness` describe the same physical continuum with different numbers of labels. Under index distance one backness step cost several times one place step — an artifact of labeling, not of anatomy. Under anchors both are positions on one arc.

**Distances survive inventory growth.** Adding a place value leaves every existing place distance unchanged, because anchors are absolute. Under index distance, adding a value would silently shift every distance in the library, and with it the shipped matrix.

Unanchored dimensions — `tone`, `length`, `phonation` — still use declaration order, honestly, because there the label set *is* the model. Categorical dimensions (`airstream`, `release`, `articulator`) score 0 for a match and 1 otherwise; they have no continuum to be positioned on.

## 3. The reference frame

Ordinal scales ascend a declared axis, recorded per feature in the data as `axis`:

| feature | axis | ascends |
|---|---|---|
| `place`, `backness`, `constriction-location` | `+x` | lips → glottis |
| `height`, `tone` | `+y` | jaw → palate, low → high |
| `manner` | `+constriction` | open → closed |
| `channel` | `+z` | lateral → flat → grooved (out → in) |
| `length` | `+t` | short → long |
| `phonation` | `+glottal-aperture` | creaky → devoiced |

The frame is a left-facing mid-sagittal section: +x along the tract, +y from jaw to palate, +z from the sides to the midline.

The z axis is the one the sagittal plane projects away, and it carries two facts that would otherwise be invisible or absent: laterality (airflow at the sides, midline occluded) and **sibilance** (a central groove concentrating the jet, versus flat diffuse airflow). Ordered out→in as `lateral → flat → grooved`, it is what separates `s` from `θ` — which differ in tongue cross-section, not in place. It has an ordering but no contour, and is the reason [docs/tract-anatomy.md](tract-anatomy.md) notes that grooving cannot be drawn mid-sagittally.

Two kinds of value hold **no position** on their scale:

- **Off-scale values.** `silence` is not a degree of constriction; it is the absence of signal. It is equidistant from every manner rather than nonsensically adjacent to `vowel`.
- **Combining values.** `bilabial^velar` is an overlap, not a point on the front–back continuum. It compares by expanding to its components, and never pads the interval between them. The combiner is `^` rather than `+`, which is already the positive value of every binary feature.

## 4. Comparing two segments

Distance is computed over a segment's derived structure, never over a flattened feature bag. Given two segments:

**Atomic against atomic** — compare the two feature bundles directly (§5).

**Otherwise** — compare the top-level children of the derived grouping. Both composition paths use one convention for extra material: **charge an unmatched part its distance to the nearest part present on the other side**. The ordered path chooses a monotone alignment; the unordered path takes the larger directional best-match mean. Both call the same nearest-part function, so the convention cannot drift between them.

For an ordered alignment:

```
D = min over alignments of
      ( Σ matched D(child_i, child_j)
        + Σ nearest D(unmatched child, present child)
        + Σ juncture terms )
    / ( matched comparisons + unmatched comparisons
        + unmatched material + juncture terms )
```

An atomic segment is lifted to a one-part sequence, which defines every atomic-against-composite comparison. Every part on the shorter side makes a real pair; permitting an alignment to discard material on both sides would manufacture an indirect shortcut once gaps are graded. Silence remains maximally distant from speech material.

**Alignment mode follows the unit's phase structure** (`Segment.phased`), not what the unit is called:

- **Ordered** — sequence alignment with gaps: sequential units, and fusions of more than one phase block, where the order of the phases carries meaning (an affricate, a prenasalized stop, a pre-stopped nasal, a lateral release, a nasal click). A prenasalized stop and a pre-stopped nasal built from the same constituents are therefore distinct, as are `a͡t` and `t͡a`.
- **Unordered** — the larger of the two directional best-match means: single-block fusions, one timing slot at one manner, where order is notation rather than meaning. `d(u͡i, i͡u)`, `d(k͡p, p͡k)` and `d(b͡ǀ, ǀ͡b)` are exactly 0.

An n-ary fusion aligns its phase blocks in order and matches unordered within them, so `ŋ͡m͡ɡ͡b` equals `m͡ŋ͡b͡ɡ` and differs from `ɡ͡b͡ŋ͡m`.

The flat projection asks the same question of the same structure, so a pair scored at 0 here is a pair `describe` reads alike. An over-tie's order is phase order, and a fusion with one phase has none; [docs/ties.md](ties.md) is what the projection does with the disagreement that leaves it.

**Junctures contribute one term each.** A juncture on one side aligns with one on the other when both flanking pairs are matched; aligned junctures score 0 when their senses agree and 1 when they do not, and unaligned junctures score 1. So `d(u͡i, u͜i) = 1/3` exactly: the same constituents in the same order, one juncture-sense mismatch over three terms.

`explain_word_distance` exposes that arithmetic directly. Composite substitutions use flat qualified rows for matched parts, unmatched-part nearest comparisons and material, and junctures; they do not also include a parent `segmental` aggregate. A matched part remains one outer row even when its own atomic comparison can be explained one level down. Thus summing the row costs and dividing by their count never double-counts a parent beside its children. For `u͡i` / `u͜i`, the shipped rows are `matched part a[0]~b[0]: u/u = 0`, `matched part a[1]~b[1]: i/i = 0`, and `juncture a[0]~b[0]: fuse/seq = 1`, reconstructing `1/3`.

### The declared mass budget

The budget names each kind of material and derives its price from declarations already in the feature model. No entry is fitted.

| material | mass | shape | measured example |
|---|---|---|---|
| atomic feature | one declared `value_distance` term | graded | average atomic contrast `0.195`; maximum `0.460` |
| diacritic | the feature terms it contributes | graded, sub-additive | applicable-mark mean `0.038`; maximum `0.144` |
| aspiration | its declared release comparison | graded | `d(t,tʰ) = 0.048` |
| dentalization | its declared place comparison | graded | `d(t,t̪) = 0.005` |
| labialization | its secondary-place comparison | graded | `d(t,tʷ) = 0.002` |
| second articulator, fusion | nearest-part sharing at `SECONDARY_WEIGHT` | graded | `d(ɡ,ɡ͡b) = 0.034 = d(ɡ,b)/2` |
| unmatched phased constituent | nearest-part comparison plus one material term | graded | `d(t,t͡s) = 0.263`; `d(e,e͜ɪ) = 0.255` |
| juncture | one binding-sense term | categorical | agreement `0`, disagreement or unaligned `1` |
| prosodic rider | one declared `value_distance` term per tier | graded | one term on the unit clock |

The previous ordered-path flat gap made every phased second constituent cost `0.667`, above the complete atomic range, while the unordered path already charged nearest-part distance. The shared function removes that divergent implementation. The juncture charge deliberately remains: making an absent juncture free as well would put an affricate about `0.013` from its own stop and destroy the phase-clustering intent documented in [ties.md](ties.md). [design/mass-budget.md](design/mass-budget.md) is the dated record of the divergence, its measured geometry, and the repair.

One budget question remains explicitly deferred. A fusion has no arity floor, so adding the whole second articulator in `ɡ͡b` (`0.034`) is cheaper than adding aspiration to `t` (`0.048`). A floor may be defensible, but it must be measured separately; changing fusion arity in this repair would make neither mover class independently explainable. The test suite pins the live inversion so this limit stays visible.

**Prosodic tiers ride on the unit clock.** Stress, tone and length are `mode="prosodic"` marks that attach *to* a unit — unlike a break, which sits *between* units and is transparent to distance. Each rider adds one graded term to the unit it rides on, read via the ordinal `value_distance` (primary vs secondary stress is half a step, primary vs unstressed a full one) at the same weight as a segmental feature. It is read for the metric only: the unit's stored features are untouched, so a form still spells back unchanged, and a unit carrying no rider — every shipped phone — adds no term and scores exactly as before. A tone *contour*, a sequence value like `mid>high`, is a trajectory rather than a point on the scale, so it stays out until a sequence comparison exists (`d(a, a᷅) = 0`).

**A word comparison is inspectable.** `explain_word_distance(a, b)` returns one step per aligned position — `op` (match/sub/insert/delete), the two units, the position `cost`, and for a substitution the `(label, a, b, cost)` rows behind it, each comparable feature and every prosodic rider — so a score can be read term by term (`ˈk`~`ˌk` is `stress: primary vs secondary = 0.5`).

**A string of units is the same mean, one level up.** `segment_distance` compares its two arguments position by position: a position both sides reach costs the segment metric above, a position only one side reaches costs `GAP_COST`, and the answer is the mean over `max(len)` positions. Length is those positions and not a second quantity normalized beside them, so all three levels — parts within a unit, units within a string, tokens within a word — price a substitution against a gap in one currency. Two consequences worth stating: a pair scores the same alone as it does inside a longer string, so appending a unit identical on both sides leaves the summed cost untouched and only divides it over one more position; and an empty string against a spoken one is 1.0 because every position is unmatched, not because of a special case.

**A word is that currency spent, not measured.** `word_distance` searches for the cheapest alignment instead of comparing position by position, so it needs prices rather than proportions, and the two are not the same number. A gap costs `GAP_COST`, exactly what an unmatched position costs one level down. A substitution costs the pair's dissimilarity — the [0, 1] answer from the level below — multiplied by `delete + insert`, because a position whose two tokens share nothing is a deletion and an insertion: the material on one side went, and different material arrived. That fixes the one relation the two scales need. The usual constraint `sub(a, b) <= delete(a) + insert(b)` is met with equality at the top rather than with room to spare, so a chain of substitutions is chosen over a pair of gaps exactly when the tokens along it really do share something, and an alignment can say *this was dropped and that was added* instead of reporting every pair of unlike tokens as a substitution.

**The normalizer is the cost of the null alignment**, `n · delete + m · insert` — deleting every token of the first word and inserting every token of the second. That path is one the search minimizes over, so it is also the most any alignment can cost, and `similarity = 1 − cost / that` reaches both ends: 1 on identity, 0 when the two words share nothing anywhere. `max(n, m)` is a different claim, and the difference is exactly on length mismatch: it charges a truncation once where this charges the material that went missing and the material that replaced it apart. Both word-distance paths — `IPAFeatures.word_distance` and `DistanceModel.word_distance` — read one function for this, so a caller who switches to the model to get empirical weights changes which substitution costs the alignment sees and not what a similarity means.

**Length asymmetry is reported, never folded in.** `WordDistanceResult.coverage` is `min(n, m) / max(n, m)`, and it multiplies nothing. Length is already charged once, as the gaps the alignment pays for; a second multiplicative term would charge it twice, which is the mistake `segment_distance` used to make with its separate length penalty. What the ratio adds is a diagnosis rather than a magnitude — it is what separates "these differ throughout" from "one is a truncation of the other", two readings a single score cannot tell apart, and folding it in would destroy precisely that.

**Identity is checked before any "nothing comparable" sentinel.** The metric returns 1.0 where it has no basis for comparison — an unreadable symbol, a bundle with no key the other side shares — and that is a claim about the pair, not about either side alone: it cannot hold of a thing against itself. So `d(x, x) = 0` for every `x`, including the empty string and including input no inventory can read. The sentinel is reachable only when the two sides genuinely differ.

## 5. Comparing two bundles

A bundle distance is the mean over these terms:

- **Each shared or unshared feature key**, scored by that feature's `value_distance` (§2). A key present on one side only scores 1.
- **The place components**, as a weighted set. Primary components weigh 1.0, secondary articulations 0.5 (`SECONDARY_WEIGHT`); the term is the larger of the two directional weighted best-match means. This is what puts `tʲ` strictly between `t` and `c`. Which features are secondary articulations, and the place each constricts at, are declared in the data (`mode="secondary" place="velar"` on the feature) rather than tabulated here. A secondary articulation is read off the assembled bundle, not off the glyph stack, so it counts once and counts the same however it is written — inherent to the base phone (`ɫ`), as a modifier letter (`lˠ`), or as a combining diacritic (`l̴`) — and those three are at distance 0 from each other.
- **Two tract terms**, `arc` and `offset`, compared directly.

**Bridge features** are derived for the comparison and never stored. They exist because one phonetic dimension can be spelled several ways: `nasality` unifies `manner=nasal`, `nasalized=+`, and `release=nasal`; `laterality` unifies `channel=lateral` and `release=lateral`. Without them, `ã` and `n` share no key expressing nasality at all. With them, `ã` is nearer `n` than plain `a` is. The equivalences are declared in `ipa.xml`'s `<bridges>` block — that three spellings name one dimension is phonetics, not metric mechanics — and the exclusion that goes with them is derived from the same declaration: a feature every one of whose informative values a bridge claims is *carried* by that bridge, so counting it again would cancel the bridge out. `nasalized` is such a feature; `channel` and `release` are not, because each also holds values no bridge claims.

A bridge names `(feature, value)` pairs, so it can only unify a dimension that single values pick out. That is why there is no `glottality` bridge, although the case for one looks strong: a glottalized `tˀ` scores *further* from `ʔ` than plain `t` does, because the glottal release adds a key `ʔ` does not carry, and nothing says the two spellings name one dimension.

```python
import ipakit

ipakit.distance("tˀ", "ʔ") > ipakit.distance("t", "ʔ")   # True
```

Unifying `release=glottal` with `place=glottal` would fix that pair and break others: `place=glottal` is carried by `h` and `ɦ` as well as `ʔ`, and a glottalized stop is a glottal *closure*, not the open-glottis frication of `h`. Saying what is actually wanted takes a conjunction — `place=glottal` **and** `manner=plosive` — which a spelling cannot express. `nasality` escapes the problem because `manner=nasal` picks out a coherent set on its own. So the pair stays mis-ordered, and deliberately: the fix is either a mechanism that admits conjunctions or a measure fitted against empirical confusion data, and the second should come first, for the reason given in §6.

The tract terms exist for the same reason at the level of position. The frame's axes are each stored twice — x as `place` for consonants and `backness` for vowels, y as `manner` and `height` — in features that never co-occur. Without shared coordinates, `j` and `i` have no comparable key despite being nearly the same articulation, and a voiceless alveolar stop scored closer to /i/ than /i/'s own glide. With them the orderings hold: `d(j, i) < d(t, i)`, and `d(w, u) < d(k, u) < d(t, u)`.

## 6. What is not weighted

No feature carries a weight. Each dimension contributes equally at maximal difference, and anchored dimensions give partial credit for genuine proximity. A total voicing difference therefore costs more than a small place move — which matches the finding that place is the fragile dimension under noise and voicing the robust one.

Weights were considered and rejected for two reasons. Sonority ranks syllabic prominence, not contrast salience, and affricates are the counterexample: low sonority, high salience. And most apparent weighting problems turn out to be representation problems: `p` and `ʘ` once scored distance 0 not because voicing was underweighted but because clicks were filed under `manner` while silently defaulting to a pulmonic airstream. Correcting the data fixed it; a weight would have hidden it.

Neither reason needs the metric to carry a sonority ordering already, which is as well, because it does not. `manner`'s axis is `+constriction` and means it: `nasal` and `plosive` declare one position on it, so the axis does not separate them at all, and it puts a nasal on the closed side of a fricative — right for a nasal's oral tract and backwards for its sonority.

```python
import ipakit

manner = ipakit.load_ipa_features().features["manner"]
manner.value_distance("nasal", "plosive")   # 0.0
```

A sonority scale *is* derivable here — the `obstruent` natural class read alongside that axis puts the manners in the order every hierarchy gives them — but nothing in the metric reads one, and the first reason above is why nothing should: a scale of syllabic prominence would still be the wrong quantity to weight contrasts by.

If weights are ever wanted, the only defensible source is empirical confusion data, and they belong in a layer over this metric rather than inside it — so that the structural claim stays honest.

## 7. Segments outside the inventory

`get_features` resolves registered phones first, then composes tie-barred sequences of known phones. Distance follows: any composable segment has a distance, whether or not it is in the inventory.

`DistanceModel` adds a percentile transform over a reference inventory. Phones absent from its matrix fall back to feature-derived similarity routed through the same CDF; phones whose features cannot be derived at all keep the explicit sentinels (`confusability` 0.0, `distance` 1.0, `nearest` empty). A phoneset whose members are absent from the matrix is reported, not silently dropped — see `import_phoneset` if the members are spelled in another tie convention.

## Not a metric in the mathematical sense

`distance` is symmetric, is zero exactly on identity, and lies in `[0, 1]`. It does **not** satisfy the triangle inequality, and is therefore a *dissimilarity*, not a metric. Measured over the shipped inventory, a small fraction of triples violate it, and the worst cases are not marginal:

```
d(b͡v, ɡ)              far apart
d(b͡v, ɡ͡b) + d(ɡ͡b, ɡ)  an order of magnitude closer
```

This is structural rather than accidental. `ɡ͡b` is a double articulation that shares one constituent with `b͡v` and a *different* one with `ɡ`, so it sits near both, while `b͡v` and `ɡ` are compared as a phased unit against an atom and carry unmatched material. A composite can be close to two things that are far from each other, because closeness is being measured against different parts of it.

The pre-repair geometry was measured at the flat-gap diagnosis. Over the full 139-phone matrix, negative eigenvalues carried **8.7%** of total eigenvalue mass and **94.8%** of triangle violations routed through a composite hub; with silence excluded (138 phones), the leading axis carried **60.3%** of positive variance and correlated **0.977** with compositeness. These are the concrete cost of treating the dissimilarity as Euclidean or metric, rather than only a warning that the inequality can fail. They are checked values, kept together so none can drift independently:

```python
diagnosed_geometry = {
    "negative eigenvalue mass (139 phones)": "8.7%",
    "violations through composite hubs (139 phones)": "94.8%",
    "leading positive variance (silence excluded)": "60.3%",
    "leading-axis/compositeness correlation (silence excluded)": 0.977,
}
diagnosed_geometry
# {'negative eigenvalue mass (139 phones)': '8.7%', 'violations through composite hubs (139 phones)': '94.8%', 'leading positive variance (silence excluded)': '60.3%', 'leading-axis/compositeness correlation (silence excluded)': 0.977}
```

The same instrument over the repaired matrix reads differently, and the difference is the repair's measured consequence. The leading axis no longer encodes compositeness (correlation `0.063`, from `0.977`); it correlates `0.922` with the vowel–consonant contrast, with the diphthongs at one end and the affricates at the other — composites ordered by their content rather than their construction. The composite shell is gone: mean distance within the phased composites is `0.273` against `0.321` from composites to atomics, no longer a constant, and the leading positive axis carries `43.4%` of positive variance rather than `60.3%` — the variance spread to more axes because the geometry carries more information. Negative eigenvalue mass rose from `9.1%` to `13.1%`, and that is the honest direction: the flat shell was self-consistent and therefore nearly embeddable while being wrong, whereas the repaired space keeps phase families deliberately tight (the typed-tie commitment above) while their external distances are graded and identity-dependent — near-coincident points with different views of the rest of the space do not embed. The residual non-Euclideanity is the signature of that commitment rather than an artifact, and the closure below remains the route to a metric.

```python
repaired_geometry = {
    "negative eigenvalue mass (silence excluded)": "13.1%",
    "leading positive variance (silence excluded)": "43.4%",
    "leading-axis/compositeness correlation (silence excluded)": 0.063,
    "leading-axis/vowelhood correlation (silence excluded)": 0.922,
}
repaired_geometry
# {'negative eigenvalue mass (silence excluded)': '13.1%', 'leading positive variance (silence excluded)': '43.4%', 'leading-axis/compositeness correlation (silence excluded)': 0.063, 'leading-axis/vowelhood correlation (silence excluded)': 0.922}
```

### If you need a metric

`ipakit.closure.MetricClosure` is the shortest-path closure over an inventory — the largest metric that is nowhere greater than the distance it is built from. It satisfies the inequality by construction:

```python
import ipakit
from ipakit.closure import metric_closure

closure = metric_closure(ipakit.load_ipa_features())
closure.distance("p", "b")   # 0.05
```

It is deliberately **not** exported at module level and **not** the default, because closure is not free. A pair shortens whenever some third phone offers a cheaper path, and over the shipped inventory those paths are mostly artifacts: a double articulation shares one constituent with each endpoint, so `ɡ → ɡ͡b → b͡v` is cheap even though a voiced velar plosive and a voiced labiodental affricate are not alike. About a fifth of pairs shorten, and the largest shortcuts land on some of the least similar pairs — so a closure trades a true inequality for occasional badly wrong similarities.

It is also **inventory-relative**, unlike `distance`: a pair's value depends on which other phones are present, since they are the possible intermediate steps. Pairs outside the inventory raise rather than falling back, because a silent fallback would break the one property the closure exists to supply. `MetricClosure.shortened()` reports every pair the closure moved, so the cost is inspectable rather than assumed.

The claim the metric makes is structural consistency, and the operations it is built for — ranking neighbors, thresholding similarity, scoring an alignment — need ordering and boundedness, not metricity. Nothing in the library assumes the triangle inequality holds.

**What this means for you.** Anything that requires a true metric will be wrong here: metric trees and ball trees for nearest-neighbor search, algorithms whose correctness proof rests on the triangle inequality, and embedding the distances into a Euclidean space without checking the residuals. Brute-force nearest-neighbor, ranking, and clustering methods that only need a dissimilarity are all fine. If you need a metric, enforce it explicitly — for instance by taking the shortest-path (metric closure) over the distance graph — rather than assuming it.

## 8. Implications for users

**The numbers are structural.** Two segments are close when they are made similarly. That correlates with confusability but does not model it: `t͡ʃ` is much closer to `t͡s` than to `ʃ`, because an affricate shares phase structure with another affricate and not with a bare fricative. If your task is perceptual, treat these as a prior and calibrate against your own data.

**Thresholds are not portable across versions.** The shipped `confusion.json` is a derived artifact; changes to the anchors, the inventory, or the metric regenerate it and shift absolute values. Orderings are far more stable than magnitudes. If you have tuned an `is_similar` threshold, re-tune it after upgrading — and see [§9](#9-ranking-deciding-and-gamma), which is about the same subject from the other end: what a threshold on a percentile scale can and cannot mean in the first place. The configuration a number came from is nameable now: `DistanceModel.scoring` reports a versioned `ScoringParameters` bundling `gamma` and the two indel costs, so what you tuned against can be pinned rather than rediscovered from drifting results.

**Percentiles are inventory-relative.** `DistanceModel` reports where a pair falls in *its reference inventory's* distribution. The same pair scores differently under a small English set and the full bundled inventory; this is intended, and it is why `distance_model(phoneset)` exists.

**Silence is maximally different from every speech sound.** `d(␣, X) = 1.0`, so a position where one word has a phone and the other has silence costs a delete and an insert: the phone went, and a silence arrived. Silence is a token that fills a position, not the absence of one — a word that drops the segment outright is a token shorter, pays a single gap, and scores as the nearer of the two.

**The three scales are named apart.** `distance` is structural and bounded; `normalized_distance` is a percentile within a reference inventory and also bounded, but the two are *not* comparable; `WordDistanceResult.edit_cost` is a summed alignment cost that grows with word length and is not bounded at all. Compare word pairs with `.similarity`, which is normalized.

**Word-level distance is an alignment over token distances.** Structural marks — the linking undertie, breaks — are transparent: `word_distance("lez‿ami", "lezami") = 0`.

**Score against a set of acceptable pronunciations with `nearest_pronunciation`, not a citation form.** Every real lexicon lists several transcriptions per word — free variants (`iːðɚ`/`aɪðɚ`), a homograph read two ways (`record` the noun and the verb) — and "is this an acceptable pronunciation?" is the best match over that set, with `PronunciationMatch` reporting which member won. It is deliberately *not* word-to-word distance: a maximum over variants depends on how many each side lists, a property of the lexicon and not of the pair, so the two are named apart. `word_distance` remains the symmetric pairwise measure.

**A low word similarity has two readings, and `coverage` is which.** Two words can score alike because they differ at every position or because one is half of the other. The score is the same question in both cases — how far apart — and the ratio beside it is the diagnosis. Read them together, and do not multiply them: the gaps already charged the length.

## 9. Ranking, deciding, and gamma

`DistanceModel` takes a `gamma` that raises the percentile to a power, and it defaults to `1.0`, which is the identity. This section is why the knob exists, why it ships switched off, and what it is actually good for — which is narrower than its name suggests.

**A percentile is a ranking scale, not a decision scale.** The model counts how many reference pairs are no more similar than the pair in hand and divides by the total. That is a rank expressed as a fraction, and it is uniform over the reference pairs by construction, whatever the underlying similarities look like:

```python
import ipakit

model = ipakit.distance_model()
ref = model.reference_phones
sims = [model.confusability(a, b) for i, a in enumerate(ref) for b in ref[i + 1 :]]
round(sum(s > 0.5 for s in sims) / len(sims), 1)   # 0.5
```

Half the pairs sit above 0.5 because half of anything sits above its own median. That is exactly what makes the scale good at ranking — the value *is* the rank, so "how many pairs are nearer than this one" is read straight off it — and exactly what makes it bad at deciding. The number says nothing about whether the inventory is crowded or sparse, so a cut point tuned on one inventory means something else on another. Worse, the ranks are uniform over *pairs*, not over degrees of likeness, and most pairs of phones are nothing like each other; so every pair a listener could plausibly confuse is packed into the last few percent of the range, with the whole rest of the scale spent separating pairs no one would confuse either way.

**Gamma is monotone, so it reorders nothing at the phone level.** Raising every value to a common positive power leaves every comparison as it was; it only redistributes the spacing, pulling values below 1.0 toward 0 in proportion to how far below they already are.

```python
import ipakit

flat = ipakit.distance_model()
sharp = ipakit.distance_model(gamma=3.0)
pairs = [("p", "b"), ("p", "k"), ("s", "ʃ"), ("p", "a")]
rank = lambda m: sorted(pairs, key=lambda ab: m.confusability(*ab))
rank(flat) == rank(sharp)   # True
```

**On the phone-level API, a gamma is exactly a change of threshold.** This follows from monotonicity and is worth stating plainly, because it is the part that gets overclaimed: `p ** g >= t` holds precisely when `p >= t ** (1 / g)`, so any partition of pairs a gamma and a cut point produce is one some other cut point produces on the untransformed scale.

```python
cut = 0.5
({ab for ab in pairs if sharp.confusability(*ab) >= cut}
 == {ab for ab in pairs if flat.confusability(*ab) >= cut ** (1 / 3)})   # True
```

So on `confusability`, `distance` and `nearest`, gamma buys no decision that moving the threshold could not. What it buys there is legibility. A power above 1 stretches the scale near 1.0 and compresses it near 0 — the slope of `p ** g` is `g * p ** (g - 1)`, which is above 1 at the top and below it at the bottom — and the top is the crowded end. So it spreads the pairs worth telling apart and squeezes together the ones that were never in question:

```python
near = lambda m: m.confusability("s", "ʃ") - m.confusability("p", "b")
far = lambda m: m.confusability("k", "i") - m.confusability("p", "a")
near(sharp) > near(flat), far(sharp) < far(flat)   # (True, True)
```

Calling this *spreading the dissimilar pairs apart* invites the opposite reading, and the opposite reading is wrong: dissimilar pairs move **down**, toward each other and toward 0, and it is the similar ones that gain room. A cut point that sat at the median moves with them — under `gamma=3.0`, 0.5 falls where the top fifth of pairs begins:

```python
round(sum(s ** 3 > 0.5 for s in sims) / len(sims), 2)   # 0.21
```

**Where gamma does real work is word alignment**, because there the transformed values are *summed* rather than compared. `sub_cost` runs through the same percentile as `confusability`, but insertion and deletion cost a flat `insert_cost` and `delete_cost` and gamma never touches them. Raising gamma therefore raises the price of a substitution against a fixed price for a gap, and that is a change of exchange rate, not a relabeling. It can change which alignment the dynamic program picks:

```python
flat.word_distance("atə", "abt", return_alignment=True).alignment
# [('a', 'a'), ('t', 'b'), ('ə', 't')]
sharp.word_distance("atə", "abt", return_alignment=True).alignment
# [('a', 'a'), (None, 'b'), ('t', 't'), ('ə', None)]
```

At `gamma=1.0` substituting straight through is cheaper than a gap on each side of the shared `t`; at `gamma=3.0` it is not, and the words align on the material they share. Ordering of *word* pairs is not preserved either: a transform applied term by term does not survive being summed, so two word pairs can swap places. If you are tuning an `is_similar` threshold, that threshold is on word similarity, and gamma genuinely moves which pairs clear it — which is the other half of the warning in §8 about re-tuning thresholds.

**There is no tuned default, and there will not be one.** Any specific value is a fit to whichever inventory and task produced it, and a number fitted to one source cannot be checked against anything — [docs/design/vowel-constriction.md](design/vowel-constriction.md) is the worked case of refusing exactly that, and concludes that "a table is refused on evidence, not on taste." `1.0` is the honest default precisely because it is the identity: it asserts nothing.

To choose one, hold out pairs your own task has already labeled — words a lexicon treats as confusable, phones your listeners actually merged — and sweep gamma over `word_similarity` on that set, not over `confusability`. Sweeping it on the phone-level API is measuring a reparametrized threshold and will look like it is working. Values below 1.0 compress toward 1.0 and make substitutions cheaper, which is occasionally what a noisy-channel task wants; a value at or below 0 is refused at construction, since `p ** g` there is a constant or a reflection out of `[0, 1]` rather than a redistribution of it. There is no upper bound: the transform stays in range and stays order-preserving however large the exponent gets, and how far up is useful is a fact about the caller's inventory rather than about the library.

**Gamma has no meaning on the plain `word_distance` path.** `ipakit.word_distance` and `IPAFeatures.word_distance` align on structural feature distance and never build a CDF, so there is no percentile for an exponent to act on and no knob to expose. Likewise `ipakit.confusability` and `ipakit.normalized_distance` are shortcuts onto a default model, fixed at `gamma=1.0`; build a model with `ipakit.distance_model(gamma=...)` to change it.

### Sweeping gamma, and choosing a threshold

Gamma and any `is_similar` threshold are tuned **together, on data your task has labeled** — never hand-picked. The recipe:

1. Collect labeled pairs: a `1` for pairs your task treats as the same, a `0` for pairs it does not.
2. Sweep gamma. For each candidate value build a model at that gamma and score every pair with `word_similarity` (or `sequence_similarity`, below, for pre-tokenized input). Rank the gammas by a **threshold-independent** measure of separation — the probability a positive scores above a negative (ROC-AUC) is the honest one, since it smuggles in no threshold.
3. Fix the threshold **last**, on the winning gamma, to the false-negative/false-positive balance the task wants. A threshold is not portable across gammas, inventories, or versions (§8), so pin the gamma it was chosen under — `DistanceModel.scoring` records it.

```python
import ipakit

# (a, b, label) triples your task has labeled
pairs = [(("k", "æ", "t"), ("k", "æ", "d"), 1),
         (("k", "æ", "t"), ("d", "ɒ", "ɡ"), 0)]

def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    wins = sum((s > t) + 0.5 * (s == t) for s in pos for t in neg)
    return wins / (len(pos) * len(neg))

labels = [y for *_, y in pairs]
for g in (1, 2, 4, 8, 16):
    model = ipakit.distance_model(gamma=g)
    scores = [model.sequence_similarity(a, b) for a, b, _ in pairs]
    print(g, round(auc(scores, labels), 3))
```

Sweep on `word_similarity` / `sequence_similarity`, **not** on `confusability` or `distance`: on the phone-level API a gamma is exactly a change of threshold (above), so a sweep there measures nothing a cut point could not. How far up is useful is a fact about your inventory and task, not the library — which is why the default stays `1.0` and there is no shipped calibration.

## 10. Per-phone indel costs, and what they are relative to

`insert_cost` and `delete_cost` are `float | Callable[[str], float]`. Passed a float, every phone costs the same to lose or to supply; passed a callable, each phone is priced on its own. `CostSchedule` is the callable to reach for — a name, a mapping, and a default — and the name is what a result reports.

```python
import ipakit

drop = ipakit.CostSchedule("my-english/deletion", {"ə": 0.25}, default=1.0)
r = ipakit.directional_word_distance("kætə", "kæt", delete_cost=drop)
r.costs        # 'insert=1.0 delete=my-english/deletion'
```

**Why per phone at all.** A flat indel cost is a claim, not a neutral starting point: that a schwa and a released stop are the same kind of loss. What varies by phone should be read from something that states it per phone. That is the justification the feature metric already rests on, applied to the other half of the alignment — the half that was still a constant in the code.

**A cost schedule is language-relative, and a score computed under one is not comparable to a score computed under another.** Which phones are droppable is a fact about a language, not about phonetics: a schwa deletes freely in English and in French and is contrastive elsewhere, and a released final stop is a different kind of loss in a language that permits final clusters than in one that does not. Two similarities computed under different schedules are two different measurements that happen to share a range. Do not average them, threshold them together, or read one against the other. This is the same warning as *thresholds are not portable across versions* in [§8](#8-implications-for-users), one turn further out: a tuned threshold is now portable across neither versions nor languages.

**This does not make `distance` relative.** [design/tiers.md](design/tiers.md) §7 commits that "tiers, their names, their inventory per language, and any phasing declared over them are language-relative. The feature space, the comparison bundle, and therefore `distance` are not." That commitment stands. A cost schedule parameterizes a comparison; it is not a term in the feature space. It declares no feature, enters no bundle, and moves no value `distance`, `segment_distance` or the shipped matrix returns — measured, and the measurement is in the test suite. What the caller supplies is how much a loss is worth to them. A word similarity is a function of the universal feature space **given** a stated parameterization, and the line between the two is the line between a term in the comparison and a price on it.

That reading only holds if the parameterization is nameable, which is why every result carries one. `WordDistanceResult.costs` is `insert=<name> delete=<name>`, a flat cost naming itself and a schedule naming what it is a schedule for. An unnamed lambda reports `<lambda>`, which is the honest answer and the reason to pass a schedule when the number is going anywhere a reader will see it.

**Directional distance.** `word_distance` is symmetric and stays symmetric, and it is the code rather than the suite that makes it so: the two reductions that could introduce an order dependence — the arc distance and the weighted place distance — each take `max(direction(a, b), direction(b, a))`, and part-matching minimizes over matchings symmetrically. The tests probe that with a curated list covering the cross-arity cases where an asymmetry would surface, rather than quantifying over the inventory; the `max()` is what earns the guarantee. Callers rely on it — the shipped matrix stores only the upper triangle. `directional_word_distance(reference, hypothesis)` is the entry point that names its reference side: `delete_cost` prices the phones of the reference, which is the material an omission removes, and `insert_cost` prices the phones of the hypothesis, which is the material that was added. "Did the speaker omit something the target has" and "did the speaker add something the target lacks" are different questions and a symmetric score cannot express either. With equal flat costs the two functions agree exactly; the asymmetry comes from the schedule, not from the entry point.

**The denominator sums over the phones.** `similarity` is `1 - edit_cost / denom`, where `denom` is the null alignment's cost: delete every phone of the first word, insert every phone of the second. That is a sum over the actual phones, not a token count times a price. The two agree whenever the price is flat and disagree as soon as it is not, and only the sum keeps `similarity` bounded below by 0 once prices vary.

### Deriving a schedule instead of typing one

Writing the mapping out by hand is the same pattern this repository rejects everywhere else: a second copy of something already declared, which goes stale in silence. `CostSchedule.from_rules` reads the membership off a rule set — the phones some rule rewrites to zero, or writes where there was nothing — and takes the two prices from the caller:

```python
import ipakit
from ipakit import rules
from ipakit.distance import CostSchedule

ipa = ipakit.load_ipa_features()

deletes = CostSchedule.from_rules(
    rules.shipped("french-liaison", ipa), "delete", ipa, price=0.25, default=1.0
)
inserts = CostSchedule.from_rules(
    rules.shipped("japanese-moraic", ipa), "insert", ipa, price=0.25, default=1.0
)
```

Those two are the worked pair the shipped rule sets already supply, one deletion-driven and one insertion-driven: `french-liaison` deletes the latent final consonants and the schwa, `japanese-moraic` inserts the epenthetic vowels. A rule set stating none of the requested side is refused rather than answered with a schedule that prices nothing.

**A schedule built this way is a claim about the rule set, not about the language, and it should be read and named as one.** `french-liaison` deletes what that file was written to state; a French speaker drops other things it says nothing about. The narrow claim is the true one, and it is the only kind available — which is also why the *prices* are still the caller's. They are stated nowhere in the data and cannot be derived from it, and inventing them here would be the fitted table again.

**There is no shipped schedule and there will not be a universal one**, for the reason [§9](#9-ranking-deciding-and-gamma) gives about gamma and [design/vowel-constriction.md](design/vowel-constriction.md) gives at length: a table fitted to whatever corpus produced it validates cleanly against that source and is wrong. A per-language table is the same refusal with one more way to be wrong, since it would be fitted to one corpus *and* to one variety of one language.

## 11. Changing the parameters

`GAP_COST` and `SECONDARY_WEIGHT` are named constants in `ipakit/metric.py`. Anchors, axes, and articulator defaults are data in `data/ipa.xml`. Any change to either requires regenerating the matrix:

```sh
python scripts/confusion.py generate --write   # rewrite data/confusion.json
python scripts/confusion.py validate           # CI guard: shipped == derived
```

A saved matrix records the space it was derived in. `metric` in the matrix format is a digest of what the metric reads — every comparison bundle over the phones the file itself lists, and every declared feature's value scale — and every reader compares it against the inventory in hand and refuses a disagreement: `from_matrix_file` for a file you name, and `global_` and `for_phoneset` for the shipped one, which is the path `distance_model()` and `confusability` take and so the path an edit to `ipa.xml` is actually read on. `phones` cannot stand in for it: a bridge adds a term to the denominator of every distance in the inventory and leaves the phone list byte-identical, so it detects membership drift and nothing else. It is a refusal rather than a warning because the wrong answer is a well-formed percentile from another inventory's reference distribution, and nothing about such a number looks wrong. A file recording no `metric` is read without comment — an empirical TSV grid is not derived from this metric and has nothing to agree with. The bare `DistanceModel(...)` constructor is the deliberate escape: it takes a matrix as an argument and makes no claim about where it came from.

Keying the digest to the phone list the file carries is what keeps it independent of membership. A supplement adds phones and declares nothing, so a supplemented inventory reading a matrix derived before the supplement gets the same digest, correctly: the space did not move. Membership is `phones`' question, and the two keys do not overlap.

The test suite pins the metric's exact properties — `d(ɡ, ɡ͡b) = d_b(ɡ,b)/2`, `d(u͡i, u͜i) = 1/3`, the cross-class orderings, symmetry and range over a probe set. A parameter change that breaks one of those is a semantic change, not a tuning change.

This document states relations and invariants rather than measured values, deliberately: exact numbers belong in the test suite, where a change that moves them fails loudly. Prose that quotes them goes stale in silence.

## 12. Pre-tokenized sequences, n-best, and local matching

`word_distance` and `word_similarity` take IPA **strings** and tokenize them. When you already hold phone tokens — each element one unit, possibly multi-character like `d͡ʒ` — pass them to `sequence_distance` / `sequence_similarity` instead, and the boundaries you gave are kept:

```python
ipakit.sequence_similarity(["t", "ʃ"], ["t͡ʃ"])   # < 1.0: two units, not the affricate
ipakit.sequence_similarity(["k", "æ", "t"], ["k", "æ", "d"])
```

Re-tokenizing a joined string would merge `["t", "ʃ"]` into the affricate `t͡ʃ` and change the length; the sequence methods never do. They exist on the raw `IPAFeatures` path and on `DistanceModel` (gamma-aware). No lexicon is involved anywhere — the inputs are the phone sequences you supply.

**Best of a set (n-best).** `rank_sequences(observed, candidates)` ranks candidate sequences by similarity, best first; `rank_pronunciations` is the same for IPA strings, and `nearest_pronunciation` is its top-1. Pass `n` for the n-best; a tie keeps the earliest-listed candidate.

```python
ipakit.rank_sequences(["b", "ʌ", "t", "ɚ"],
                      [["b", "ʌ", "t", "ɝ"], ["b", "ɪ", "t"]], n=2)
```

**Local (fit) matching.** `mode="local"` scores the second sequence as a **target that must align fully** while the first sequence's ends are free — for a target embedded in a longer, noisier sequence. It is directional (the two sides are not interchangeable), which is why it is offered on the sequence and ranking methods and not on the symmetric `word_distance`. It is a specialized tool: on whole-to-whole comparison it over-accepts, because free ends stop charging the surrounding material, so reach for it only when the target really is embedded.

On the command line: `distance seq` compares two pre-tokenized sequences (each argument a space-separated token list, `--local` for the fit), and `distance nearest -n K --local` ranks candidates.

## Related

- [docs/ties.md](ties.md) — tie conventions, the representation, and how segments compose
- [docs/gestural-model.md](gestural-model.md) — the model this representation is converging on, not yet implemented
- [docs/tract-anatomy.md](tract-anatomy.md) — the vocal-tract geometry that would derive these anchors rather than declare them
