# Comparative systems: different principles, shared computation

IPAkit makes phonetic inventories and feature assignments explicit so their
consequences can be computed and compared. Those choices remain testable and
revisable throughout the work.

TierGraph supplies the general computational and category-theoretic substrate.
IPAkit constructs a phonetic compositional calculus on it. The house system is
one inventory-plus-algebra instance, with its own substantive phonetic theory
and articulatory attachment. Other instances can use the framework under their
own declarations and compatible computational contracts.

## Compare the right layers

Notation, phoneset, feature system, structural model, and scoring algebra are
separate choices that can be varied independently where their contracts permit.
Unit identity and equivalent claims require evidence from those declarations,
including when systems share IPA spellings.

| System or instance | Organizing choices | Computation and current boundary |
| --- | --- | --- |
| [House phonetic system](house-style.md) | Declared features, constituent composition, ties and junctures; prosodic tiers; [articulatory attachment](tract-anatomy.md). | Parsing, composition, rewrites, structural comparison, and schematic posture/animation. Its inventory and theory remain open to testing and revision. |
| [Pinyin](pinyin.md) | Syllable-primary structure; tone belongs to the syllable; written mark placement is separate. Optional IPA realization. | Existing native profile, library construction/rendering, and serialization tests. No dedicated graph-ingestion CLI; the constructor is internal. |
| [Kana](kana.md) | Mora groupings and mora-kind-dependent orthographic realization. | Existing API/CLI and mora-tier renderer cover bounded attested adaptations. Comprehensive Japanese analysis remains outside this scope. |
| [CLTS/BIPA](clts-audit.md) | Sound descriptions and feature sets under a different declaration system. | Native frozen core feature-set/Jaccard scoring, shared alignment costs, and declaration census. Source-preserving Form integration and semantic feature mapping remain separate work. |
| Panphon | A different phonological feature-vector geometry. | Existing native vector-cost comparison machinery in [cost packs](../ipakit/bridges/costmodel.py). Using that geometry is distinct from asserting equivalence to house features. |
| Converter–Distributor | A future example intended to exercise a different set of organizing principles. | Unimplemented; deferred beyond the present CLTS integration scope. |

Pinyin and kana exercise different model choices. Kana's bounded bridge operates
over house IPA groupings; Pinyin additionally has an explicit syllable-primary
profile. Each system has its own supported ingestion, restoration, and operation
contracts, as summarized in the table.

## What makes a comparison fair

Use shared machinery with each representation's declared semantics. Hold the
computation and policy fixed while varying the representation, or hold the
representation fixed while varying the computation. Name the experiment being
performed.

Record the source version and inventory, segmentation and unit identity, feature
interpretation, algebra/cost policy, gap treatment, and normalization. Report
coverage, refusals, conversion losses, and unmatched claims alongside the scores.
Score commensurability and perceptual validity require evidence beyond shared
numerical ranges.

The existing cost-pack interface separates model costs from the shared alignment
operation. Its generic semiring fold remains experimental; the production
alignment path and the laws claimed for each operation are described in
[capabilities](capabilities.md#algebra-that-can-be-used-and-inspected). Common
machinery requires compatible contracts and explicit laws for each algebra.

## Comparing the house theory with CLTS

The [house expressivity goal](house-style.md#one-explicit-model-not-the-substrate)
is to cover the other inventories' distinctions, with explicit exceptions.
That goal motivates enhancement work. Foreign-to-foreign computation can use
the models' own declarations directly, independently of the house instance.
Establish coverage with constructive witnesses for the distinctions being
compared.

The useful questions are directional: which distinctions correspond, which
require interpretation, and which occur on only one side? Establishing
equivalence requires checking articulatory attachment, constituent structure,
and computational behavior alongside spellings and feature labels.

Mapping gaps can motivate house inventory enhancements, better adapters, or
explicitly retained source-only claims. The shared substrate makes these
alternatives inspectable. Evaluating the mapping and the phonetic theories
requires evidence for each. See the
[comparison overview](capabilities.md#choose-the-comparison-for-the-task) for
external references and the distinction between CLTS feature-set Jaccard,
Panphon feature costs, and native structural dissimilarity.
