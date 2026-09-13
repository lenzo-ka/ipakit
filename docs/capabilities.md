# What ipakit brings to an interoperability pipeline

ipakit connects declared representations to structured composition, feature
queries and rewrites, inspectable comparison, and articulatory visualization.
Representations share structural and algebraic machinery while retaining their
own declarations and assumptions. Cross-linguistic catalog maintenance, historical
inference, and speech synthesis remain the work of the corresponding specialist
tools.

## Different representations, common computation

The ipakit house system is one inventory-plus-algebra instance on this substrate.
Its phonetic declarations and composition rules supply one choice of semantics;
other instances retain their own. A phoneset, a feature system, and a model of
units and tiers are separate choices. Shared structure and operations make those
choices inspectable and allow controlled comparisons: hold the computation and
policy fixed while varying the representation, or hold the representation fixed
while varying the computation.

The calculus and algebra connect representation to computation. Inventories and
feature assignments remain testable, revisable model choices, each requiring
empirical evaluation. Alternative models can use the framework under their own
declared semantics.

TierGraph supplies the general computational and category-theoretic substrate.
IPAkit constructs a phonetic compositional calculus on that foundation, and its
house instance contributes a substantive phonetic theory, including articulatory
attachment. Concrete implementations must state the contracts and laws they satisfy,
including where bounded enumeration or other implementation choices limit them.

The design separates those questions: what a representation asserts, which
operations its algebra supports, and how shared computational machinery executes
those operations. Reusing an algorithm requires an explicit compatible contract
and an account of the laws each model's algebra satisfies.

The existing cost-pack interface makes this concrete for comparison: models
supply their own costs to a shared alignment operation, with segmentation, gap
costs, and normalization identified separately. The tier-based representation
provides the structural foundation for broader integration; source-preserving
CLTS adaptation is still work in progress, as detailed below.

Here, *fair comparison* means exposing and controlling the assumptions.
Coverage, refusals, conversion losses, and source-specific features remain part
of the result. Score commensurability and phonetic equivalence require their own
evidence.

## Pinyin: an existing different model

See the dedicated [Pinyin guide](pinyin.md), [kana guide](kana.md), and
[comparative-systems discussion](systems.md) for the existing implementations,
their different organizing principles, and their API boundaries.

Pinyin provides a concrete syllable-primary example. Its graph has syllable,
constituent, tone, and optional phonetic-realization tiers. Tone associates with
the **syllable**; the orthographic
renderer separately chooses which vowel receives the written tone mark.
The syllable attachment is preserved when an optional IPA realization is added.

The declared library bridge is
[`ipakit.bridges.pinyin.PINYIN`](../ipakit/bridges/pinyin.py). It owns the
vocabulary declaration, keyboard aliases, and tone-mark rendering. The existing
graph constructor is currently an **internal profile API**,
[`ipakit._pinyin_graph.build`](../ipakit/_pinyin_graph.py), with no public
stability guarantee. This executable example demonstrates that profile:

```python
from ipakit._pinyin_graph import build as build_pinyin
from ipakit.bridges.pinyin import PINYIN

syllable = build_pinyin("shui", "sh", "ui", 3)
PINYIN.render(syllable)  # 'shuǐ'
```

The constructor takes explicit spelling, onset, rhyme, and tone. Automatic
analysis of arbitrary Mandarin text is outside its scope. The
[profile tests](../tests/tiergraph/test_j_profiles.py) check syllable attachment,
optional referenced IPA realization, and native graph serialization round trips.
The vocabulary bridge groups house IPA; the profile supplies a separate
syllable-primary view with its own units and attachment semantics.

Pinyin rendering is currently library-only; dedicated CLI ingestion of its
syllable/tone graph remains unimplemented. See the [API/CLI boundary](cli-api-sync.md).
This model demonstrates a different unit and attachment choice on the same
substrate. Each computation still has its own supported-profile contract.

## The house instance: a spelling with computational meaning

The [house phonetic notation](house-style.md) gives ties, diacritics, stress,
and boundaries explicit jobs. It deliberately distinguishes an over-tie
(simultaneous constituents), an under-tie (a bound sequence), and adjacency
(separate units). These tie meanings are specific to the house convention.
A nasal approach such as `ⁿd` and a tied unit such as `n͡d` likewise express
distinct structures.

```python
import ipakit as ipa

ipa.read("t͡sa").phones     # ('t͡s', 'a')
ipa.read("t͜sa").phones     # ('t͜s', 'a')
ipa.read("tsa").phones      # ('t', 's', 'a')
ipa.respell("i", rounded="+")  # 'y'
```

Composition derives units from declared bases and operators, including
combinations without individual inventory rows. [Ties and mark binding](ties.md)
keep the constituents and their relationships available. Unicode normalization
and declared aliases handle spelling variants; importing another transcription convention is an
explicit choice through `from_wild` or a named inventory style. A successful
Unicode read establishes spelling admission; interpreting that spelling requires
the source convention's semantics.

## Algebra that can be used and inspected

Feature edits can be realized back to IPA, as above. Context-sensitive rules
compose into cascades with derivation traces. Optional application is per
matching site, and the [variant calculus](calculus.md) exposes the resulting
forms and whether enumeration was complete:

```python
ipa.variants("kæt", "t ~> ʔ / _ #").forms  # ('kæt', 'kæʔ')
```

The rewrite engine enumerates variants and reports whether enumeration was
complete. Its algebraic guarantees are bounded by the enumeration caps described
in the calculus. Compiled finite-state transducers and probabilistic grammars
are outside the current engine's scope.

There is also a separate algebraic seam for comparison.
[`ipakit.bridges.costmodel`](../ipakit/bridges/costmodel.py) separates
segmentation, substitution and gap costs, and normalization into named cost
packs/policies. Its experimental `semiring_alignment` folds an alignment grid
using `zero`, `one`, `add`, and `multiply`, allowing another carrier/algebra
without rewriting the recurrence. The normalized ternary vector-cost family uses
TierGraph's product of tropical semirings to accumulate numerator and denominator;
the ratio is a separate operation performed afterward.

The production `align_under` path uses the existing tropical alignment DP and
can return its alignment witness. The generic fold is a separate experimental
path. The [cost-model tests](../tests/test_costmodel.py) exercise both production
parity and a symbolic carrier that would fail if the
generic fold depended on numeric arithmetic. The semiring contract applies to
these specific folds; other operations carry their own contracts.

## Structural comparison grounded in declarations

The native [distance](distance.md) uses declared phonetic features and tract
coordinates, preserving constituent and juncture structure. Where geometry
is available, anchored place differences contribute coordinate-based terms.
`explain` exposes the charged terms; word comparison adds alignment with explicit
insertion/deletion costs. Inventory mapping can
report the contrasts collapsed by nearest-neighbor assignments.

The result measures structural dissimilarity. Perceptual-probability calibration
and general metric guarantees lie outside its contract.
[Similarity and validation](similarity.md) explain the triangle-inequality
boundary, optional inventory-relative metric closure, and the scope of
perceptual evidence. Perceptual prediction requires validation alongside the
resolution of declared distinctions.

## Structure and movement beyond a phone vector

`Form` has a graph-backed store with a linear computation view. Public
constructors can build containment, and navigation can reach segments such as
pauses independently of word membership. Tiers keep segmental and prosodic claims
at their appropriate levels; derived rewrite events remain relative to the input
clock. See [construction and navigation](representation.md#public-construction-and-navigation).

Explicit finite models can also [decorate an existing native graph](rules.md#decorating-an-existing-graph)
through `GraphBinding`, using the same rule engine and retaining source facts,
relationships and optional timing. Derived events anchor to the input clock;
target timing and containment require explicit information. The binding operates
directly on the native graph, independently of house `Form` admission. Restoring
an operation requires its explicit binding and rules as well as the serialized
graph.

The gesture projection reads articulator, location, and constriction degree
from declarations. Its traversal prefers complete timed targets, then
gestures, then structural segments. Timing is optional start plus duration;
untimed traversal uses structural order.
The [gesture integration tests](../tests/tiergraph/test_gesture_integration.py)
exercise timed, untimed, and partial-timing fallback cases.

The shipped [tract renderer](tract-figures.md) turns declared posture into SVG;
`ipakit.tract.score` and `blend` support target-to-target animation through
`ipakit.tract_svg.animate`. The implemented scope is schematic kinematics;
biomechanical simulation, acoustic synthesis, and audio alignment remain outside
it. The [animation limits](../tests/ANIMATION_LIMITS.md) and
[gestural-model status](gestural-model.md) distinguish the implemented
posture/target work from continuous phase relations and gesture-set segment
identity that remain design directions.

## Choose the comparison for the task

These projects have overlapping scopes. The table describes their useful
emphases. External API descriptions were checked against the linked
primary sources on 2026-09-12.

| Task | Relevant machinery | What to keep distinct |
| --- | --- | --- |
| Resolve cross-linguistic transcription conventions and name sounds | [CLTS/BIPA and pyclts](https://github.com/cldf-clts/pyclts) provide transcription-system sound descriptions and feature sets. | Preservation of house tie semantics and input segmentation requires separate verification from BIPA equivalence. |
| Compare CLTS sounds by shared descriptions | [`Sound.similarity`](https://raw.githubusercontent.com/cldf-clts/pyclts/master/src/pyclts/models.py) computes unweighted feature-set Jaccard similarity. | The score measures set overlap; articulatory-coordinate distance and sequence alignment require separate operations. |
| Use phonological feature vectors and feature-edit distances | [Panphon](https://github.com/dmort27/panphon) provides segment vectors and [feature-edit distance variants](https://raw.githubusercontent.com/dmort27/panphon/master/panphon/distance.py), including weighted variants. | Keep each score paired with its feature/cost scheme; comparing Panphon and native ipakit scores requires accounting for their different meanings. |
| Align forms with sound classes and prosodic context | [LingPy's pairwise alignment](https://raw.githubusercontent.com/lingpy/lingpy/master/src/lingpy/align/pairwise.py) supports sound-class scorers, prosodic weighting, and configurable alignment modes. | A correspondence-oriented alignment score answers a different question from native structural phonetic dissimilarity. |
| Compose, rewrite, compare, and visualize one structured transcription | ipakit's house notation, `Form`, rewrite calculus, declared geometry, and posture machinery work together. | Foreign-inventory coverage and speech-production calibration require their own evidence. |

For CLTS sounds with feature sets A and B, the similarity is
`|A ∩ B| / |A ∪ B|`; the sets include the sound type, and complex sounds have
component-qualified features. [`scripts/interop.py similarity`](../scripts/interop.py)
already compares `1 - Sound.similarity` with native ipakit distances over
registered house phones that BIPA resolves. It reports rank correlation and
nearest-neighbor agreement over a named resolved population. Semantic-fidelity
auditing and perceptual validation are separate tasks. Record
the CLTS data revision, pyclts version, house declarations, tokenization, and
cost policy when reporting results. Measure current coverage for that identified
configuration.

## Integration status

The shipped [inventory registry](inventories.md), [TextGrid profiles](textgrid.md),
and comparison tooling are usable today. The [CLTS/BIPA library](clts-audit.md)
provides a frozen finite core feature snapshot, native Jaccard scoring, shared
alignment cost packs, and a declaration census. Runtime scoring uses the shipped
snapshot; development extraction has separate source pins and validation.
The CLTS source-preserving runtime bridge remains in development. A public
importer that retains source-only CLTS claims safely in `Form` still requires
an adaptation/restoration boundary, guarded incomplete projections, and
directional mapping artifacts. The existing scripts provide auditing and
approximation. Full native graph persistence and the public `Form.to_json()`
linear projection have separate fidelity contracts.

The [historical ecosystem assessment](design/ecosystem.md) retains the
measurements and design motivations that led here. Its dated issue states,
counts, and descriptions of then-missing functionality document that historical
context. Use the current guides for present implementation status.
