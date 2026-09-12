# What ipakit brings to an interoperability pipeline

ipakit connects a declared phonetic notation to structured composition, feature
queries and rewrites, inspectable comparison, and articulatory visualization.
Its useful distinction is that these operations share a model of what the
transcription asserts. It is more than a lookup from IPA glyphs to vectors,
but it is not a replacement for a cross-linguistic catalog, a historical
linguistics toolkit, or a speech synthesizer.

## A spelling with computational meaning

The [house phonetic notation](house-style.md) gives ties, diacritics, stress,
and boundaries explicit jobs. It deliberately distinguishes an over-tie
(simultaneous constituents), an under-tie (a bound sequence), and adjacency
(separate units). Those tie meanings are a house convention, not a claim that
standard IPA requires the distinction. A nasal approach such as `ⁿd` likewise
does not assert the same structure as `n͡d`.

```python
import ipakit as ipa

ipa.read("t͡sa").phones     # ('t͡s', 'a')
ipa.read("t͜sa").phones     # ('t͜s', 'a')
ipa.read("tsa").phones      # ('t', 's', 'a')
ipa.respell("i", rounded="+")  # 'y'
```

Composition derives a unit from declared bases and operators; it does not
require an inventory row for each combination. [Ties and mark binding](ties.md)
keep the constituents and their relationships available instead of reducing
them to one unordered feature bag. Unicode normalization and declared aliases
handle spelling variants; importing another transcription convention is an
explicit choice through `from_wild` or a named inventory style. A successful
Unicode read is not evidence that two conventions mean the same thing.

## Algebra that can be used and inspected

Feature edits can be realized back to IPA, as above. Context-sensitive rules
compose into cascades with derivation traces. Optional application is per
matching site, and the [variant calculus](calculus.md) exposes the resulting
forms and whether enumeration was complete:

```python
ipa.variants("kæt", "t ~> ʔ / _ #").forms  # ('kæt', 'kæʔ')
```

This is an enumerating rewrite engine, not a compiled finite-state transducer
or a probabilistic grammar. Enumeration caps bound its algebraic guarantees;
the calculus documents those boundaries rather than treating a truncated set
as the whole relation.

There is also a separate algebraic seam for comparison.
[`ipakit.bridges.costmodel`](../ipakit/bridges/costmodel.py) separates
segmentation, substitution and gap costs, and normalization into named cost
packs/policies. Its experimental `semiring_alignment` folds an alignment grid
using `zero`, `one`, `add`, and `multiply`, allowing another carrier/algebra
without rewriting the recurrence. The normalized ternary vector-cost family uses
TierGraph's product of tropical semirings to accumulate numerator and denominator;
the ratio is taken afterward, not described as a semiring operation.

The production `align_under` path uses the existing tropical alignment DP and
can return its alignment witness. It does not route every comparison through
the experimental generic fold. The [cost-model tests](../tests/test_costmodel.py)
exercise both production parity and a symbolic carrier that would fail if the
generic fold depended on numeric arithmetic. These are concrete extension
points, not a claim that every operation in ipakit is a semiring.

## Structural comparison grounded in declarations

The native [distance](distance.md) uses declared phonetic features and tract
coordinates, preserving constituent and juncture structure. Where geometry
is available, an anchored place difference is not just disagreement between
two categorical labels. `explain` exposes the charged terms; word comparison
adds alignment with explicit insertion/deletion costs. Inventory mapping can
report collapsed contrasts rather than silently presenting nearest neighbors
as equivalent phones.

The result is a structural dissimilarity, not a perceptual probability or a
guaranteed mathematical metric. [Similarity and validation](similarity.md)
explain the triangle-inequality boundary, optional inventory-relative metric
closure, and the scope of perceptual evidence. Better resolution of a
declared distinction is not, by itself, better perceptual prediction.

## Structure and movement beyond a phone vector

`Form` has a graph-backed store with a linear computation view. Public
constructors can build containment, and navigation can follow it without
inventing a word for a pause. Tiers keep segmental and prosodic claims at their
appropriate levels; derived rewrite events remain relative to the input
clock. See [construction and navigation](representation.md#public-construction-and-navigation).

The gesture projection reads articulator, location, and constriction degree
from declarations. Its traversal prefers complete timed targets, then
gestures, then structural segments. Timing is optional start plus duration;
untimed traversal retains structural order rather than inferring seconds.
The [gesture integration tests](../tests/tiergraph/test_gesture_integration.py)
exercise timed, untimed, and partial-timing fallback cases.

The shipped [tract renderer](tract-figures.md) turns declared posture into SVG;
`ipakit.tract.score` and `blend` support target-to-target animation through
`ipakit.tract_svg.animate`. This is schematic kinematics, not a biomechanical
simulation, an acoustic synthesizer, or an audio aligner. The
[animation limits](../tests/ANIMATION_LIMITS.md) and
[gestural-model status](gestural-model.md) distinguish the implemented
posture/target work from continuous phase relations and gesture-set segment
identity that remain design directions.

## Choose the comparison for the task

These projects overlap; the table describes useful emphases, not exclusive
feature ownership. External API descriptions were checked against the linked
primary sources on 2026-09-12.

| Task | Relevant machinery | What to keep distinct |
| --- | --- | --- |
| Resolve cross-linguistic transcription conventions and name sounds | [CLTS/BIPA and pyclts](https://github.com/cldf-clts/pyclts) provide transcription-system sound descriptions and feature sets. | BIPA equivalence need not preserve house tie semantics or input segmentation. |
| Compare CLTS sounds by shared descriptions | [`Sound.similarity`](https://raw.githubusercontent.com/cldf-clts/pyclts/master/src/pyclts/models.py) computes unweighted feature-set Jaccard similarity. | This is set overlap, not an articulatory-coordinate distance or a sequence alignment. |
| Use phonological feature vectors and feature-edit distances | [Panphon](https://github.com/dmort27/panphon) provides segment vectors and [feature-edit distance variants](https://raw.githubusercontent.com/dmort27/panphon/master/panphon/distance.py), including weighted variants. | Declare which feature/cost scheme is used; a Panphon score and a native ipakit score are not interchangeable. |
| Align forms with sound classes and prosodic context | [LingPy's pairwise alignment](https://raw.githubusercontent.com/lingpy/lingpy/master/src/lingpy/align/pairwise.py) supports sound-class scorers, prosodic weighting, and configurable alignment modes. | A correspondence-oriented alignment score answers a different question from native structural phonetic dissimilarity. |
| Compose, rewrite, compare, and visualize one structured transcription | ipakit's house notation, `Form`, rewrite calculus, declared geometry, and posture machinery work together. | This combined scope does not establish complete foreign-inventory coverage or calibrated speech production. |

For CLTS sounds with feature sets A and B, the similarity is
`|A ∩ B| / |A ∪ B|`; the sets include the sound type, and complex sounds have
component-qualified features. [`scripts/interop.py similarity`](../scripts/interop.py)
already compares `1 - Sound.similarity` with native ipakit distances over
registered house phones that BIPA resolves. It reports rank correlation and
nearest-neighbor agreement. That is a comparison over a named resolved
population, not a semantic-fidelity audit or perceptual validation. Record
the CLTS data revision, pyclts version, house declarations, tokenization, and
cost policy when reporting results; do not reuse historical counts as current
coverage.

## Integration status

The shipped [inventory registry](inventories.md), [TextGrid profiles](textgrid.md),
and comparison tooling are usable today. The CLTS source-preserving runtime
bridge is separate work: the existing audit/approximation scripts do not yet
constitute a public importer that retains source-only CLTS claims safely in
`Form`. Full native graph persistence must be distinguished from the current
public `Form.to_json()` linear projection. A safe public adaptation/restoration
boundary, guarded incomplete projections, and directional mapping artifacts
are integration requirements, not capabilities claimed by this page.

The [historical ecosystem assessment](design/ecosystem.md) retains the
measurements and design motivations that led here. Its dated issue states,
counts, and descriptions of then-missing functionality are historical evidence,
not a current product comparison.
