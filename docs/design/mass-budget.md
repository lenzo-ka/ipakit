# The comparison mass budget

> Historical design record (2026-08-11). The measurements record the comparison geometry before the segment mass budget was declared, and the reasoning for the convention now implemented in `ipakit/metric.py`.

## 1. The undeclared quantity

Comparable quantities in ipakit ordinarily have one declaration and any number of readers. The ordinal ladder, tract anchors, and mode precedence follow that form. The secondary-articulation set is one declaration read twice; it took that form after three copies had diverged.

The comparison mass budget was the exception. It arose from the number of terms assembled by each branch of `segment_metric` and the charge assigned to an unmatched term. It therefore had no declaration against which the branches could be checked. The ordered and unordered branches came to state different prices for the same material, while the suite continued to exercise each implementation on its own terms.

## 2. Three conventions for one situation

The shared situation is material on one side and nothing opposite it. Before the repair, its three readings were:

| comparison path | charge for extra material | measured instance |
|---|---|---|
| atomic against atomic | its declared value distance, term by term | a diacritic averaged `0.038`; aspiration `0.048` |
| unordered fusion | its distance to the nearest part present opposite | `d(ɡ, ɡ͡b) = 0.034`, half of `d(ɡ, b)` |
| ordered or phased | the flat maximum, `1.0` | `d(t, t͡s) = d(e, e͜ɪ) = 0.667` |

The first two rows state one rule in two places: charge the material by a comparison with material that is present. The third row had drifted to a flat charge.

For `t͡s` against `t`, the ordered branch counted a matched pair at approximately zero, an orphan constituent at `1`, and an unaligned juncture at `1`. Its three-term mean was `(0 + 1 + 1) / 3 = 0.6667`. The orphan's identity did not enter the calculation, so every affricate was exactly `0.6667` from either constituent.

The rest of the measured budget located that constant. Applicable diacritics averaged `0.038` and reached `0.144`; dentalization of `t` cost `0.005`, labialization `0.002`, and aspiration `0.048`. Atomic-phone contrasts averaged `0.195` and reached `0.460`. A phased second constituent therefore began above the complete atomic range, while a fused second articulator cost `0.034`.

## 3. The geometry before the repair

The flat charge set `d(t͡ʃ, ʃ) = 0.6667`, `d(t͡ʃ, i) = 0.7553`, and `d(t͡ʃ, t͡s) = 0.0030`. Thus `t͡ʃ` was nearer the close front vowel `i` than it was proportionate to its own fricative release `ʃ`: the first distance was only 13% greater, while the distance to another affricate was 222 times smaller than the distance to `ʃ`.

Over the shipped 139-phone matrix, negative eigenvalues carried 8.7% of the eigenvalue mass. With silence excluded (138 phones), the leading positive axis carried 60.3% of positive variance and correlated `+0.977` with whether a unit was composite. Of 2,164 triangle violations, 94.8% used a composite intermediate; `ɡ͡b` was the intermediate in 1,292. The two branch conventions supplied that hub: `d(ɡ, ɡ͡b) = 0.034` and `d(ɡ͡b, b͡v) = 0.032`, while `d(ɡ, b͡v) = 0.689`.

The remaining phonetic contrasts among phased composites occupied a band `0.117` wide with standard deviation `0.032`, against `0.093` across atomic-phone contrasts. The flat structural terms compressed those graded differences into the upper part of the range.

## 4. One convention in both branches

The repair applies the unordered branch's convention to ordered alignment: an unmatched part is charged its distance to the nearest part present on the other side. A shared `_nearest_part_cost` now serves both paths. An ordered gap carries the real comparison term and one term for the unmatched part's material. This is `gap=nearest`: a divergence removed, with no fitted parameter added.

Two alternatives were measured separately. Leaving the gap flat while charging an absent juncture zero, `junc=absent`, put every affricate at `0.3333` from a constituent. That restored the ordering but retained the constant because the orphan's identity still did not enter. Applying both changes put `t͡s` `0.0129` from `t`, `t͡ʃ` `0.0152` from `ʃ`, and `e͜ɪ` `0.0049` from `e`. Those values erase the typed-tie distinction: an affricate or diphthong becomes approximately identical to one phase. The juncture term therefore remains categorical and charged when unaligned.

With `gap=nearest` alone, the constituent distances are graded: `p͡f`–`f` is `0.2574`, `t͡s`–`t` is `0.2629`, and `t͡ɬ`–`ɬ` is `0.2754`. The ordering is `d(t͡ʃ, ʃ) = 0.2652 < d(t͡ʃ, i) = 0.3846`; `d(t͡ʃ, t͡s) = 0.0030` remains smaller by a factor of about 88.

The shipped values in this paragraph and the live deferred comparison below are checked by `scripts/docexamples.py`:

```python
from ipakit import IPAFeatures

ipa = IPAFeatures()
round(ipa.distance("p͡f", "f"), 4)       # 0.2574
round(ipa.distance("t͡s", "t"), 4)       # 0.2629
round(ipa.distance("t͡ɬ", "ɬ"), 4)       # 0.2754
round(ipa.distance("t͡ʃ", "ʃ"), 4)       # 0.2652
round(ipa.distance("t͡ʃ", "i"), 4)       # 0.3846
round(ipa.distance("t͡ʃ", "t͡s"), 4)     # 0.003
round(ipa.distance("e͜ɪ", "e"), 4)       # 0.2549
round(ipa.distance("ɡ", "b͡v"), 4)       # 0.2897
round(ipa.distance("ɡ", "ɡ͡b"), 4)       # 0.0838
round(ipa.distance("t", "tʰ"), 4)        # 0.0476
```

## 5. The mover account

The protocol fixed `PYTHONHASHSEED=0`, captured the matrix before and after, and compared all 9,591 unordered phone pairs. There were 2,300 movers, with maximum absolute movement `0.4134`. Every mover involved one of the 20 shipped phased composites. No pair outside that class moved: all 7,021 such pairs were unchanged. Within the class, 270 pairs were also unchanged because their selected alignment had no affected gap. The class check was clean.

The predicted values were then checked directly: `t͡s`–`t` `0.2629`, `t͡ʃ`–`ʃ` `0.2652`, `t͡ʃ`–`i` `0.3846`, and `t͡ʃ`–`t͡s` `0.0030`. The regenerated confusion matrix, percentile distribution, distance models, acceptance pins, tutorial values, and metric fingerprint carry the same declared convention.

The spectrum was then remeasured with the instrument that produced §3's figures. The leading axis's compositeness correlation fell from `0.977` to `0.063`, and the axis now correlates `0.922` with the vowel–consonant contrast, diphthongs at one end and affricates at the other. Leading positive variance fell from `60.3%` to `43.4%` as the composite shell dissolved into graded positions near constituents (mean within-composite distance `0.273`, composites to atomics `0.321`). Negative eigenvalue mass rose from `9.1%` to `13.1%`: the flat shell had been self-consistent and therefore nearly embeddable while wrong, and the repaired space keeps phase families tight under typed ties while their external distances differ — which cannot embed, by construction. The dominant structural fact of the geometry moved from the gap convention to the vowel–consonant contrast; the remaining non-Euclideanity is the typed-tie commitment, documented in `docs/distance.md` beside the diagnosed figures.

## 6. The recurring rule

**Material is charged what it is, never a flat rate.** Index distance made a refined ordinal scale silently cheapen the dimension; declared tract anchors replaced it with the distance of the move. Flat insertion and deletion priced schwa and a released stop as the same loss; `CostSchedule` replaced it with the cost of the phone. Flat ordered gaps priced every orphan constituent as maximally unlike everything; nearest-part charging replaced it with the available comparison. These are three instances of the same rule.

`MATERIAL_BUDGET` now declares the kinds once: atomic feature, unmatched constituent, juncture, secondary articulation, and prosodic rider. Each graded price is derived from the feature and value declarations; the categorical juncture price records binding sense. The metric fingerprint includes the declaration.

## 7. Open measurements

The fusion branch still has no arity floor. A whole second articulator in `ɡ͡b` costs `0.0338`, less than aspiration on `t` at `0.0476`. This is real, deferred, and pinned in the suite. Whether a floor can be derived, and what declaration would support it, remains a separate measurement.

External validation against perceptual confusion data remains the empirical question. The repair makes a concrete prediction: `t͡ʃ`–`ʃ` now lands at `0.2652`, and that pair is the first comparison to hold against such data.

Prosodic riders are the fourth material kind in the operational comparison: one graded value-distance term per tier, folded after segmental comparison. They remain one term by design and are recorded as such in the declared budget.
