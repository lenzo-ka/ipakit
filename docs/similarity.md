# Why similarity has this shape

This page explains ipakit's similarity scoring: its declarations, their rationale, validation results and open questions. [distance.md](distance.md) contains the formulas, parameter definitions and current measured budget.

## 1. The scoring claim

ipakit computes a structural phonetic dissimilarity. Its feature space is declared in `ipa.xml`. Ordered dimensions use declared positions where phonetic geometry supplies them: place, backness, and constriction location share the tract arc, and height and manner use declared degrees of constriction. Those coordinates determine distance independently of XML list position. An ordinal dimension without such a ground uses its stated declaration order. Categorical dimensions state equality and difference.

The comparison keeps the representation's structure. Atomic bundles compare their declared terms. Secondary articulations enter as declared places with their stated share of the place term. Tied material is divided into phase blocks: sequential ties preserve phase order, while constituents within one simultaneous phase compare without an order invented from spelling. A juncture is a typed binding term, distinct from its constituents. Stress, tone, and length ride on the unit and contribute one graded term per tier; they do not multiply their contribution by the number of segmental terms.

Material present on only one side is charged by the same rule in every structural branch: compare it with the nearest material present opposite it. `MATERIAL_BUDGET` declares the kinds of comparison term once. The recent [mass-budget record](design/mass-budget.md) is the check on this discipline: before the declaration existed, an ordered gap acquired a flat price merely because one branch happened to count it that way.

The segment score is structural and inventory-independent. A `DistanceModel` can place it on a percentile scale over a stated reference inventory. That rank is specific to the reference inventory, so comparisons between percentile positions require the same reference. At word level, `CostSchedule` lets a caller state named insertion and deletion prices, including phone-specific prices. Those schedules parameterize alignment while leaving segment distance unchanged. Callers choose a schedule for their language and task; the data supplies no universal one.

Every returned comparison can be inspected. For an atomic pair, the `explain` path reports the named feature, tract, secondary-place, and prosodic terms. For a comparison involving a composite, it reports the selected matched-constituent comparisons, each unmatched constituent's nearest opposite part and material term, and every aligned or unaligned juncture. The rows are a flat outer decomposition: each matched constituent contributes one row at this level, with its atomic children already accounted for. A consumer can reconstruct the distance by summing row costs and dividing by the row count. In particular, `u͡i` against `u͜i` reports `u`–`u` at `0`, `i`–`i` at `0`, and `fuse`–`seq` juncture at `1`, hence `(0 + 0 + 1) / 3 = 1/3`. Each quantity is read from a declaration, supplied and named by the caller, or reported as a derived comparison. These sources determine the score and its term budget; the metric uses no fitted parameters.

## 2. Material is charged what it is

Three repairs apply a recurring rule: comparison prices reflect the declared material.

An ordinal scale first used index distance. Inserting a new value then changed the price between old values even when nothing about either endpoint had changed. Declared anchors replaced list position where a physical axis is available. The standalone example below implements the former convention. It inserts one value between two old ones, then counts which old pairs move under index distance and under fixed anchors.

```python
from itertools import combinations

def index_distances(values):
    return {pair: abs(values.index(pair[0]) - values.index(pair[1])) / (len(values) - 1)
            for pair in combinations(("open", "mid", "closed"), 2)}

before = index_distances(["open", "mid", "closed"])
after = index_distances(["open", "near-mid", "mid", "closed"])
index_movers = sum(before[pair] != after[pair] for pair in before)

old_anchors = {"open": 0.0, "mid": 0.5, "closed": 1.0}
new_anchors = {**old_anchors, "near-mid": 0.25}
anchored_before = {pair: abs(old_anchors[pair[0]] - old_anchors[pair[1]]) for pair in before}
anchored_after = {pair: abs(new_anchors[pair[0]] - new_anchors[pair[1]]) for pair in before}
(index_movers, sum(anchored_before[pair] != anchored_after[pair] for pair in before))
# (2, 0)
```

A word alignment then used one flat insertion and deletion price. That prices a schwa and a released stop as the same loss. `CostSchedule` moved that claim to the caller, where the relevant language, rule set, or task can state both the membership and the price. No schedule is inferred from a corpus or installed as a universal default.

Finally, the ordered segment path used a flat gap while the unordered fusion path already compared unmatched material with the nearest constituent opposite it. The flat path put every phased second constituent above the full range of atomic contrasts and made its identity irrelevant. The [mass-budget measurement](design/mass-budget.md) records the failure, the alternatives, and the repaired mover class. Nearest-part charging now supplies one convention to both paths; the categorical juncture remains because it records the phase distinction rather than the material in either phase.

The first repair prevents a vocabulary edit from changing old geometry. The second makes alignment prices explicit parameters. The third prevents term counting from manufacturing a structural shell. Each replaces an incidental constant with a quantity stated at the layer that can justify it.

## 3. Structural validation

The eigenspectrum diagnoses which distinction dominates the distance matrix. Before nearest-part charging, the leading axis correlated with compositeness. Afterward it correlated with the vowel–consonant contrast, and the shell separating phased composites from atomic phones dissolved into positions determined by their constituents. The checked record is:

```python
structural_measurements = {
    "leading-axis/compositeness correlation before repair": 0.977,
    "leading-axis/vowelhood correlation after repair": 0.922,
    "negative eigenvalue mass before repair, silence excluded": "9.1%",
    "negative eigenvalue mass after repair, silence excluded": "13.1%",
}
structural_measurements
# {'leading-axis/compositeness correlation before repair': 0.977, 'leading-axis/vowelhood correlation after repair': 0.922, 'negative eigenvalue mass before repair, silence excluded': '9.1%', 'negative eigenvalue mass after repair, silence excluded': '13.1%'}
```

Negative eigenvalue mass rose after the repair. Phase families remain deliberately tight because typed ties say they share structure, while their distances to phones outside the family depend on which constituents they contain. Near points can therefore have different relations to the rest of the space; negative mass alone does not decide whether the repair succeeded.

The resulting dissimilarity can violate triangle inequality. Callers whose algorithms require that inequality can construct `ipakit.closure.MetricClosure`, the declared shortest-path closure over a stated inventory. Closure changes some pairwise values and makes them inventory-relative, so callers select it explicitly.

Structural validation checks that computation preserves the declared distinctions. Establishing how listeners hear the resulting ordering requires perceptual data in addition to the eigenspectrum.

## 4. External validation

Perceptual confusion data are the direct external test. The first run uses Miller and Nicely's controlled consonant-confusion matrices ([Miller & Nicely 1955](https://doi.org/10.1121/1.1907526)). Five female talkers/listeners heard sixteen consonants before the study's /a/ (the vowel of *father*) in flat noise at S/N −18, −12, −6, 0, +6, and +12 dB over 200–6500 cps. The attested table in `ipakit/data/attested/miller_nicely_1955.json` is Arabie and Carroll's aggregate of those conditions: their lower-triangle symmetric misclassification probabilities, mapped to house IPA. No cell is smoothed, imputed, or dropped. The diagonal is excluded from ranking by construction; every unordered off-diagonal pair is retained.

The hypothesis direction was stated before comparison: **more confusable ⇒ nearer**. Confusability descending and `segment_distance` ascending give the checked result below; ties receive average ranks.

```python
from scripts.perceptual_validation import measurements

validation = measurements()
{
    "consonants": 16,
    "unordered pairs": len(validation["pairs"]),
    "Spearman rho": round(validation["rho"], 6),
}
# {'consonants': 16, 'unordered pairs': 120, 'Spearman rho': 0.687092}
```

The positive rank association follows the hypothesized direction under these conditions. It validates ordering only at the strength this one matrix supports; it does not fit the metric, establish numeric calibration, or license a claim beyond Miller and Nicely's inventory and listening conditions. The executable [perceptual-validation exhibits](perceptual-validation-exhibits.md) carry the five most-confused pairs and five least-confused pairs with their distances and nonzero `explain` itemizations. They also carry every pair at the five-place rank-disagreement cutoffs, including ties: both where the metric puts a perceptually confusable pair farther away and where perception separates a metrically near pair.

The mass-budget repair makes one comparison immediately falsifiable: `t͡ʃ`–`ʃ` is the first pair to test, because the old flat gap obscured their shared fricative material and the repair gives that material its identity. Miller and Nicely's inventory contains no affricates, so this named first-pair test is not testable here and remains queued for a lineage successor with different conditions, such as Wang and Bilger (1973). A perceptual result need not equal a structural distance numerically. It can test whether the repair improves the ordering under a declared experimental condition.

Existing cross-tool evidence is narrower. [The interoperability assessment](design/interop.md) compared ipakit with PanPhon's three distance functions over their shared, successfully segmented phones. It found moderate rank agreement, with systematic divergence around affricates and other representation choices:

```python
panphon_rank_correlations = {
    "feature_edit_distance": 0.670,
    "weighted_feature_edit_distance": 0.622,
    "hamming_feature_edit_distance": 0.659,
}
panphon_rank_correlations
# {'feature_edit_distance': 0.67, 'weighted_feature_edit_distance': 0.622, 'hamming_feature_edit_distance': 0.659}
```

These results measure agreement and divergence between representations. The same assessment found that CLTS similarity and sound classes serve catalog matching and historical comparison at a different resolution. Listener data supplies the separate perceptual-validation evidence.

## 5. Neighboring commitments

[PanPhon](https://aclanthology.org/C16-1328/) represents IPA segments as fixed binary or ternary articulatory feature vectors backed by a hand-curated table. That supplies broad lookup coverage and a simple vector interface. It also makes the table and its feature resolution the authority: distinctions absent from the vector cannot enter its distances. ipakit instead derives a typed comparison from declarations and tract anchors, preserving tie phase and secondary articulation. The price is that every declaration must be defended phone by phone, and missing articulatory grounding cannot be filled by a convenient table entry.

[ALINE](https://aclanthology.org/A00-2038/) represents segments with multivalued phonetic features and applies salience weights in a dynamic-programming alignment. Its default saliences were selected for phonetic alignment of cognates, so the parameters can serve alignment quality on that evaluation material. ipakit does not fit feature weights: maximal differences on declared dimensions enter equally, while caller-stated schedules price word indels. The cost is explicit: ipakit has no task-tuned optimum unless a caller calibrates a layer over it, and its default may underperform a fitted system on the task used to tune that system.

Plain string edit distance compares symbol sequences with substitution, insertion, and deletion operations but no phonetic representation. It is inexpensive, defined for any strings, and makes its behavior easy to reproduce. It cannot distinguish a small articulatory substitution from an unrelated one unless the caller supplies that knowledge. Both ALINE and ipakit add phonetic structure; ipakit also pays for parsing, declaration maintenance, and cases where the declared structure withholds an answer that a character operation could always produce.

These tradeoffs support choosing a tool for a stated task; the comparisons above leave an overall ranking open.

## 6. What stays open

Ninety-one registered pairs differ in their feature bundle and score zero. Each added mark restates a property of the base: `ɡˠ` repeats velarity as a secondary articulation, `d̺` states the articulator `d` already implies, and `m̃` nasalizes a nasal. The distance treats these vacuous additions as equivalent; a distinctive feature difference must receive a nonzero score.

The reason the operator records them anyway is that respellings are operators: `compose_unit("ɡ", velarized="+")` is faithful to what it was asked and answers `ɡˠ`, while a value the base already carries comes back unchanged. The vacuity is a fact about the resulting segment's phonetics rather than about the operation, so it is stated here rather than repaired there. `tests/test_distinctive_difference.py` holds the boundary: no registered pair may differ in a non-vacuous feature while scoring zero, with vacuity derived from the declaration so a supplement is covered by the same rule.

The fusion branch has no arity floor. Adding a second articulator can cost less than adding a smaller diacritic because the former receives the declared secondary share of a graded comparison. A floor is deferred and pinned; it needs its own derivation and measurement rather than a constant chosen to repair one example.

External validation has begun with the Miller–Nicely ordering test above. Validation under different conditions remains queued. Its inventory excludes affricates, so testing `t͡ʃ`–`ʃ` requires a successor dataset such as Wang and Bilger (1973).

Prosodic riders remain one value-distance term per tier by design. That convention prevents the same rider from acquiring more mass merely because its host exposes more segmental terms. It remains a declared modeling choice to revisit only with evidence about the tier, not by changing the denominator locally.

The following measurements identify which marks reach that term and their contribution against `a`:

```python
import ipakit

round(ipakit.distance("a", "ˈa"), 6)    # 0.043478
round(ipakit.distance("a", "á"), 6)     # 0.043478
round(ipakit.distance("a", "à"), 6)     # 0.043478
round(ipakit.distance("a", "aː"), 6)    # 0.028986
round(ipakit.distance("a", "ǎ"), 6)     # 0.021739
round(ipakit.distance("a", "a᷅"), 6)    # 0.0
round(ipakit.distance("á", "à"), 6)     # 0.021739
```

In order: primary stress, a high level tone, a low level tone, length, a rising
direction-only contour, a low-to-mid tone trajectory, and the two level tones
against each other. These readings follow the house declarations in `ipa.xml`.

`á` and `à` each sit 0.043478 from `a`, and they sit 0.021739 apart from each
other. The pairwise comparison therefore retains their tone distinction.
Direction-only contour marks such as the caron in `ǎ` also contribute a term.
Multi-level trajectories such as `a᷅` (`low>mid`) are retained in the
representation but omitted from the scalar metric pending a trajectory
comparison policy. Their zero contribution indicates an unscored tier.
Single tone levels use the declared `bottom`, `low`, `mid`, `high`, `top`
scale. See [tone declarations and trajectories](tone.md).

Word alignment compares segment sequences and separately prices the boundary
claims retained on their segment-clock margins. A claim against an unclaimed
margin has one atomic comparison term's mass; claims at the same margin use
the ordinal `level` ladder declared in `ipa.xml`. Thus `a.a` is nearer `a#a`
than `a‖a`, while `ka.tə` and `kat.ə` differ because the same syllable claim
occupies different margins. Glyph choice is not a term: `#` and a space both
state the same word-boundary claim and compare equal.

The combining double acute U+030B in `a̋` is outside the house declaration.
Strict parsing refuses it; permissive parsing warns and retains `a`.
The declared spelling `a˥` supplies the top tone level. A raw feature lookup
for the unregistered `a̋` spelling returns an empty bundle, while the parsed
Form and its diagnostics report what the parser retained or refused.
