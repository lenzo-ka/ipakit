# Why similarity has this shape

This page is the justification for ipakit's similarity scoring: what is declared, why those declarations replace simpler alternatives, what has been checked, and what remains unvalidated. [distance.md](distance.md) is the operational reference and owns the formulas, parameter definitions, and current measured budget. This page does not restate its tables.

## 1. The scoring claim

ipakit computes a structural phonetic dissimilarity. Its feature space is declared in `ipa.xml`. Ordered dimensions use declared positions where phonetic geometry supplies them: place, backness, and constriction location share the tract arc, and height and manner use declared degrees of constriction. Those values are coordinates, not positions in an XML list. An ordinal dimension without such a ground states its declaration order as the model instead. Categorical dimensions state only equality and difference.

The comparison keeps the representation's structure. Atomic bundles compare their declared terms. Secondary articulations enter as declared places with their stated share of the place term. Tied material is divided into phase blocks: sequential ties preserve phase order, while constituents within one simultaneous phase compare without an order invented from spelling. A juncture is a typed binding term, distinct from its constituents. Stress, tone, and length ride on the unit and contribute one graded term per tier; they do not multiply their contribution by the number of segmental terms.

Material present on only one side is charged by the same rule in every structural branch: compare it with the nearest material present opposite it. `MATERIAL_BUDGET` declares the kinds of comparison term once. The recent [mass-budget record](design/mass-budget.md) is the check on this discipline: before the declaration existed, an ordered gap acquired a flat price merely because one branch happened to count it that way.

The segment score is structural and inventory-independent. A `DistanceModel` can place it on a percentile scale over a stated reference inventory; that normalized value is a rank in that inventory, not a second phonetic geometry. At word level, `CostSchedule` lets a caller state named insertion and deletion prices, including phone-specific prices. Those schedules parameterize an alignment and do not alter segment distance. There is no universal schedule in the data because the cost of losing a phone is language- and task-relative.

Every returned comparison can be inspected. For a pair of atomic units, the `explain` path reports the named feature, tract, secondary-place, prosodic, and alignment terms from which it was made; a comparison involving a composite unit currently reports one aggregate segmental term, so its internal decomposition — including the juncture term — is readable in [distance.md](distance.md)'s account but not yet itemized by `explain`. Thus a quantity is either read from a declaration, supplied and named by the caller, or reported as a derived comparison. It is not fitted inside the metric, and it does not emerge accidentally from how many terms one implementation branch assembled.

## 2. Material is charged what it is

Three repairs have applied one recurring rule: **material is charged what it is, never a flat rate.**

An ordinal scale first used index distance. Inserting a new value then changed the price between old values even when nothing about either endpoint had changed. Declared anchors replaced list position where a physical axis is available. The small comparandum below implements the former convention, not a shipped ipakit API. It inserts one value between two old ones, then counts which old pairs move under index distance and under fixed anchors.

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

The eigenspectrum is a diagnostic of what distinction dominates the distance matrix, not an external truth criterion. Before nearest-part charging, the leading axis correlated with compositeness. Afterward it correlated with the vowel–consonant contrast, and the shell separating phased composites from atomic phones dissolved into positions determined by their constituents. The checked record is:

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

The rise in negative eigenvalue mass is not evidence that the repair failed. Phase families remain deliberately tight because typed ties say they share structure, while their distances to phones outside the family depend on which constituents they contain. Near points can therefore have different relations to the rest of the space.

The resulting dissimilarity is not a metric, on purpose: triangle inequality is not one of its commitments. Callers whose algorithms require that inequality can construct `ipakit.closure.MetricClosure`, the declared shortest-path closure over a stated inventory. Closure changes some pairwise values and makes them inventory-relative, so it is explicit rather than the default.

This structural consistency is necessary: a construction artifact should not become the leading phonetic distinction. It is not sufficient. An eigenspectrum can show that the declared structure survived computation; it cannot establish that listeners hear the resulting ordering.

## 4. External validation

Perceptual confusion data are the direct external test. The lineage begins with Miller and Nicely's controlled consonant-confusion matrices ([Miller & Nicely 1955](https://doi.org/10.1121/1.1907526)); a validation study would specify speakers, listening conditions, transcription inventory, and treatment of asymmetric confusions before comparing ranks. That study has not been run for ipakit.

The mass-budget repair makes one comparison immediately falsifiable: `t͡ʃ`–`ʃ` is the first pair to test, because the old flat gap obscured their shared fricative material and the repair gives that material its identity. A perceptual result need not equal a structural distance numerically. It can test whether the repair improves the ordering under a declared experimental condition.

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

That is evidence of agreement where both systems encode phonetic distinctions and of divergence where their representations make different commitments. It is not perceptual validation. The same assessment found that CLTS similarity and sound classes serve catalog matching and historical comparison at a different resolution; those measurements are comparisons with neighboring objects, not substitutes for listener data.

## 5. Neighboring commitments

[PanPhon](https://aclanthology.org/C16-1328/) represents IPA segments as fixed binary or ternary articulatory feature vectors backed by a hand-curated table. That supplies broad lookup coverage and a simple vector interface. It also makes the table and its feature resolution the authority: distinctions absent from the vector cannot enter its distances. ipakit instead derives a typed comparison from declarations and tract anchors, preserving tie phase and secondary articulation. The price is that every declaration must be defended phone by phone, and missing articulatory grounding cannot be filled by a convenient table entry.

[ALINE](https://aclanthology.org/A00-2038/) represents segments with multivalued phonetic features and applies salience weights in a dynamic-programming alignment. Its default saliences were selected for phonetic alignment of cognates, so the parameters can serve alignment quality on that evaluation material. ipakit does not fit feature weights: maximal differences on declared dimensions enter equally, while caller-stated schedules price word indels. The cost is explicit: ipakit has no task-tuned optimum unless a caller calibrates a layer over it, and its default may underperform a fitted system on the task used to tune that system.

Plain string edit distance compares symbol sequences with substitution, insertion, and deletion operations but no phonetic representation. It is inexpensive, defined for any strings, and makes its behavior easy to reproduce. It cannot distinguish a small articulatory substitution from an unrelated one unless the caller supplies that knowledge. Both ALINE and ipakit add phonetic structure; ipakit also pays for parsing, declaration maintenance, and cases where the declared structure withholds an answer that a character operation could always produce.

These are different commitments with different costs. The comparisons above do not establish a ranking among the tools.

## 6. What stays open

The fusion branch has no arity floor. Adding a second articulator can cost less than adding a smaller diacritic because the former receives the declared secondary share of a graded comparison. A floor is deferred and pinned; it needs its own derivation and measurement rather than a constant chosen to repair one example.

External validation against perceptual confusion data is queued and unrun. The `t͡ʃ`–`ʃ` comparison is the first stated test, not a claimed result.

Prosodic riders remain one value-distance term per tier by design. That convention prevents the same rider from acquiring more mass merely because its host exposes more segmental terms. It remains a declared modeling choice to revisit only with evidence about the tier, not by changing the denominator locally.
