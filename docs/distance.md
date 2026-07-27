# Phonetic distance in ipakit

How `distance`, `segment_distance`, `word_distance`, and the shipped confusion matrix compute their numbers: the representation they read, the comparison they perform, and what the results do and do not mean.

## Quick reference

| | |
|---|---|
| Range | `[0, 1]`; 0 identical, 1 maximally different |
| Basis | Articulatory structure — where a constriction is, what makes it, how close it is |
| Claim | Structural consistency; **not** a model of perceptual confusability |
| Symmetry | `d(x, y) == d(y, x)` for all pairs (property-tested) |
| Silence | `d(␣, X) == 1.0` for every speech sound `X` |
| Weighting | None; every dimension contributes equally at maximal difference |
| Parameters | `GAP_COST = 1.0`, `SECONDARY_WEIGHT = 0.5` in `ipakit/metric.py` |
| Regenerate after changes | `python scripts/confusion.py generate --write` |

If you need perceptual confusability — which sounds listeners actually mistake for each other — this metric is a reasonable structural prior, not a substitute for confusion data. See [Implications](#implications-for-users).

## 1. What a segment carries

A constriction is three facts, and ipakit stores all three:

| fact | feature | meaning |
|---|---|---|
| **what moves** | `articulator` | the active organ: lower lip, tongue tip/blade/front/dorsum/root, epiglottis, vocal folds |
| **where it goes** | `arc` | position along the tract midline, 0 at the lips to 1 at the glottis |
| **how close** | `offset` | constriction degree, 0 at the open midline to 1 at full closure |

`arc` and `offset` are declared per feature value in `data/ipa.xml`: consonants take `arc` from `place` and `offset` from `manner`; vowels take `arc` from `backness` and `offset` from `height`. The values are hand-placed from published mid-sagittal anatomy and are schematic, not measurements.

The articulator is declared per place value as a default and overridden per phone where it differs. Place names the *target*, not the mover: a linguolabial `t̼` is the tongue tip at a labial target, and `t̺`/`t̻` differ only in which part of the tongue arrives. A combining place combines its articulators, so `w` moves the lower lip and the dorsum both.

Everything above is head-independent. A head shape (`data/heads.xml`) projects these coordinates to 2D for rendering; heads never enter distance, so the shipped matrix does not depend on whose vocal tract you picture.

## 2. Why anchors rather than scale positions

Ordinal features could compute distance from declaration order — value *i* to value *j* costs `|i−j|/(n−1)`. ipakit does that only for features without anchors. Where anchors exist, they are used instead, for three reasons:

**Steps are not uniform.** The lips-to-teeth move is much smaller than the velum-to-uvula move, though both are one label apart. Index distance prices them identically; anchors do not.

**Dimensions become commensurable.** `place` and `backness` describe the same physical continuum with different numbers of labels. Under index distance one backness step cost several times one place step — an artifact of labelling, not of anatomy. Under anchors both are positions on one arc.

**Distances survive inventory growth.** Adding a place value leaves every existing place distance unchanged, because anchors are absolute. Under index distance, adding a value would silently shift every distance in the library, and with it the shipped matrix.

Unanchored dimensions — `tone`, `length`, `phonation` — still use declaration order, honestly, because there the label set *is* the model. Categorical dimensions (`airstream`, `release`, `articulator`) score 0 for a match and 1 otherwise; they have no continuum to be positioned on.

## 3. The reference frame

Ordinal scales ascend a declared axis, recorded per feature in the data as `axis`:

| feature | axis | ascends |
|---|---|---|
| `place`, `backness` | `+x` | lips → glottis |
| `height`, `tone` | `+y` | jaw → palate, low → high |
| `manner` | `+constriction` | open → closed |
| `channel` | `+z` | lateral → flat → grooved (out → in) |
| `length` | `+t` | short → long |
| `phonation` | `+glottal-aperture` | creaky → devoiced |

The frame is a left-facing mid-sagittal section: +x along the tract, +y from jaw to palate, +z from the sides to the midline.

The z axis is the one the sagittal plane projects away, and it carries two facts that would otherwise be invisible or absent: laterality (airflow at the sides, midline occluded) and **sibilance** (a central groove concentrating the jet, versus flat diffuse airflow). Ordered out→in as `lateral → flat → grooved`, it is what separates `s` from `θ` — which differ in tongue cross-section, not in place. It has an ordering but no contour, and is the reason [docs/tract-anatomy.md](tract-anatomy.md) notes that grooving cannot be drawn mid-sagittally.

Two kinds of value hold **no position** on their scale:

- **Off-scale values.** `silence` is not a degree of constriction; it is the absence of signal. It is equidistant from every manner rather than nonsensically adjacent to `vowel`.
- **Combining values.** `bilabial+velar` is an overlap, not a point on the front–back continuum. It compares by expanding to its components, and never pads the interval between them.

## 4. Comparing two segments

Distance is computed over a segment's derived structure, never over a flattened feature bag. Given two segments:

**Atomic against atomic** — compare the two feature bundles directly (§5).

**Otherwise** — align the top-level children of the derived grouping and take one flat mean over matched pairs, gaps, and juncture terms:

```
D = min over alignments of
      ( Σ matched D(child_i, child_j) + γ · gaps + Σ juncture terms )
    / ( matched + gaps + juncture terms )
```

with `γ = 1.0`. An atomic segment is lifted to a one-part sequence, which defines every atomic-against-composite comparison.

**Alignment mode follows the unit kinds:**

- **Ordered** — sequence alignment with gaps: sequential units, and fused units whose phase order carries meaning (affricate, prenasalized, pre-stopped, lateral release, click accompaniment, overlay). A prenasalized stop and a pre-stopped nasal built from the same constituents are therefore distinct, as are `a͡t` and `t͡a`.
- **Unordered** — the larger of the two directional best-match means: single-block fusions, where order is notation rather than meaning. `d(u͡i, i͡u)` and `d(k͡p, p͡k)` are exactly 0.

An n-ary fusion aligns its phase blocks in order and matches unordered within them, so `ŋ͡m͡ɡ͡b` equals `m͡ŋ͡b͡ɡ` and differs from `ɡ͡b͡ŋ͡m`.

**Junctures contribute one term each.** A juncture on one side aligns with one on the other when both flanking pairs are matched; aligned junctures score 0 when their senses agree and 1 when they do not, and unaligned junctures score 1. So `d(u͡i, u͜i) = 1/3` exactly: the same constituents in the same order, one juncture-sense mismatch over three terms.

Prosody — stress, length, tone — is excluded: `d(a, aː) = 0`.

## 5. Comparing two bundles

A bundle distance is the mean over these terms:

- **Each shared or unshared feature key**, scored by that feature's `value_distance` (§2). A key present on one side only scores 1.
- **The place components**, as a weighted set. Primary components weigh 1.0, secondary articulations 0.5 (`SECONDARY_WEIGHT`); the term is the larger of the two directional weighted best-match means. This is what puts `tʲ` strictly between `t` and `c`.
- **Two tract terms**, `arc` and `offset`, compared directly.

**Bridge features** are derived for the comparison and never stored. They exist because one phonetic dimension can be spelled several ways: `nasality` unifies `manner=nasal`, `nasalized=+`, and `release=nasal`; `laterality` unifies `channel=lateral` and `release=lateral`. Without them, `ã` and `n` share no key expressing nasality at all. With them, `ã` is nearer `n` than plain `a` is.

The tract terms exist for the same reason at the level of position. The frame's axes are each stored twice — x as `place` for consonants and `backness` for vowels, y as `manner` and `height` — in features that never co-occur. Without shared coordinates, `j` and `i` have no comparable key despite being nearly the same articulation, and a voiceless alveolar stop scored closer to /i/ than /i/'s own glide. With them the orderings hold: `d(j, i) < d(t, i)`, and `d(w, u) < d(k, u) < d(t, u)`.

## 6. What is not weighted

No feature carries a weight. Each dimension contributes equally at maximal difference, and anchored dimensions give partial credit for genuine proximity. A total voicing difference therefore costs more than a small place move — which matches the finding that place is the fragile dimension under noise and voicing the robust one.

Weights were considered and rejected for three reasons. Sonority ranks syllabic prominence, not contrast salience, and affricates are the counterexample: low sonority, high salience. Sonority is also already encoded in the manner ordering, so weighting by it would double-count. And most apparent weighting problems turn out to be representation problems: `p` and `ʘ` once scored distance 0 not because voicing was underweighted but because clicks were filed under `manner` while silently defaulting to a pulmonic airstream. Correcting the data fixed it; a weight would have hidden it.

If weights are ever wanted, the only defensible source is empirical confusion data, and they belong in a layer over this metric rather than inside it — so that the structural claim stays honest.

## 7. Segments outside the inventory

`get_features` resolves registered phones first, then composes tie-barred sequences of known phones. Distance follows: any composable segment has a distance, whether or not it is in the inventory.

`DistanceModel` adds a percentile transform over a reference inventory. Phones absent from its matrix fall back to feature-derived similarity routed through the same CDF; phones whose features cannot be derived at all keep the explicit sentinels (`confusability` 0.0, `distance` 1.0, `nearest` empty). A phoneset whose members are absent from the matrix is reported, not silently dropped — see `import_phoneset` if the members are spelled in another tie convention.

## 8. Implications for users

**The numbers are structural.** Two segments are close when they are made similarly. That correlates with confusability but does not model it: `t͡ʃ` is much closer to `t͡s` than to `ʃ`, because an affricate shares phase structure with another affricate and not with a bare fricative. If your task is perceptual, treat these as a prior and calibrate against your own data.

**Thresholds are not portable across versions.** The shipped `confusion.json` is a derived artifact; changes to the anchors, the inventory, or the metric regenerate it and shift absolute values. Orderings are far more stable than magnitudes. If you have tuned an `is_similar` threshold, re-tune it after upgrading.

**Percentiles are inventory-relative.** `DistanceModel` reports where a pair falls in *its reference inventory's* distribution. The same pair scores differently under a small English set and the full bundled inventory; this is intended, and it is why `distance_model(phoneset)` exists.

**Silence behaves as a deletion.** `d(␣, X) = 1.0` for every speech sound, so substituting silence costs exactly what deleting the phone costs in an alignment.

**Word-level distance is an alignment over token distances.** Structural marks — the linking undertie, breaks — are transparent: `word_distance("lez‿ami", "lezami") = 0`.

## 9. Changing the parameters

`GAP_COST` and `SECONDARY_WEIGHT` are named constants in `ipakit/metric.py`. Anchors, axes, and articulator defaults are data in `data/ipa.xml`. Any change to either requires regenerating the matrix:

```sh
python scripts/confusion.py generate --write   # rewrite data/confusion.json
python scripts/confusion.py validate           # CI guard: shipped == derived
```

The test suite pins the metric's exact properties — `d(ɡ, ɡ͡b) = d_b(ɡ,b)/2`, `d(u͡i, u͜i) = 1/3`, the cross-class orderings, symmetry and range over a probe set. A parameter change that breaks one of those is a semantic change, not a tuning change.

This document states relations and invariants rather than measured values, deliberately: exact numbers belong in the test suite, where a change that moves them fails loudly. Prose that quotes them goes stale in silence.

## Related

- [docs/ties.md](ties.md) — tie conventions, the representation, and how segments compose
- [docs/gestural-model.md](gestural-model.md) — the model this representation is converging on, not yet implemented
- [docs/tract-anatomy.md](tract-anatomy.md) — the vocal-tract geometry that would derive these anchors rather than declare them
