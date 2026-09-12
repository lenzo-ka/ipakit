# Comparative systems: different principles, shared computation

IPAkit's purpose is not to settle every argument about the best phonetic
inventory before computation can begin. Inventories and feature assignments are
testable, revisable choices. The framework makes those choices explicit and
supports comparing their consequences.

TierGraph supplies the general computational and category-theoretic substrate.
IPAkit constructs a phonetic compositional calculus on it. The house system is
one inventory-plus-algebra instance, with its own substantive phonetic theory
and articulatory attachment. Supporting other instances does not make that theory
incidental, nor make agreement with it a prerequisite for using the framework.

## Compare the right layers

Notation, phoneset, feature system, structural model, and scoring algebra are
different choices. Changing one need not replace all the others. Conversely,
sharing IPA spellings does not establish identical units or equivalent claims.

| System or instance | Organizing choices | Computation and current boundary |
| --- | --- | --- |
| [House phonetic system](house-style.md) | Declared features, constituent composition, ties and junctures; prosodic tiers; [articulatory attachment](tract-anatomy.md). | Parsing, composition, rewrites, structural comparison, and schematic posture/animation. Its inventory and theory remain open to testing and revision. |
| [Pinyin](pinyin.md) | Syllable-primary structure; tone belongs to the syllable; written mark placement is separate. Optional IPA realization. | Existing native profile, library construction/rendering, and serialization tests. No dedicated graph-ingestion CLI; the constructor is internal. |
| [Kana](kana.md) | Mora groupings and mora-kind-dependent orthographic realization. | Existing bounded attested-adaptation API/CLI and mora-tier renderer, not a comprehensive Japanese system. |
| CLTS/BIPA | Sound descriptions and feature sets under a different declaration system. | Existing audit/comparison tooling; native frozen scorer and source-preserving integration are separate delivery stages. See [capabilities and status](capabilities.md#integration-status). |
| Panphon | A different phonological feature-vector geometry. | Existing native vector-cost comparison machinery in [cost packs](../ipakit/bridges/costmodel.py). Using that geometry is distinct from asserting equivalence to house features. |
| Converter–Distributor | A future example intended to exercise a different set of organizing principles. | Not claimed as implemented or included in the present CLTS integration scope. |

Pinyin and kana are already concrete examples, not future promises. They are
also different kinds of example: kana's bounded bridge operates over house IPA
groupings, whereas Pinyin additionally has an explicit syllable-primary profile.
The table does not claim that all systems already have interchangeable public
ingestion, full graph restoration, or access to every house operation.

## What makes a comparison fair

Raise representations onto shared machinery without silently replacing their
semantics with house semantics. Hold the computation and policy fixed while
varying the representation, or hold the representation fixed while varying the
computation. Name the experiment being performed.

Record the source version and inventory, segmentation and unit identity, feature
interpretation, algebra/cost policy, gap treatment, and normalization. Report
coverage and refusals as well as scores; conversion losses and unmatched claims
are evidence, not housekeeping to discard. Shared numerical ranges alone do not
make scores commensurate or validate them perceptually.

The existing cost-pack interface separates model costs from the shared alignment
operation. Its generic semiring fold remains experimental; the production
alignment path and the laws claimed for each operation are described in
[capabilities](capabilities.md#algebra-that-can-be-used-and-inspected). Common
machinery requires compatible contracts, not an assumption that every algebra
satisfies the same laws.

## Comparing the house theory with CLTS

The useful questions are directional: which distinctions correspond, which
require interpretation, and which occur on only one side? A spelling match or
matching feature label is not enough to establish the same articulatory
attachment, constituent structure, or computational behavior.

Mapping gaps can motivate house inventory enhancements, better adapters, or
explicitly retained source-only claims. They do not automatically prove either
model wrong. The shared substrate makes these alternatives inspectable; the
mapping and the phonetic theory still need their own evidence. See the
[comparison overview](capabilities.md#choose-the-comparison-for-the-task) for
external references and the distinction between CLTS feature-set Jaccard,
Panphon feature costs, and native structural dissimilarity.
