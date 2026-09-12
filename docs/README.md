# ipakit documentation

Choose a task below. The tutorials introduce the public Python and CLI surfaces;
the reference pages explain their contracts and limits. Generated exhibits supply
checked examples and measurements. Dated design records preserve the reasoning,
not a second account of current behavior.

## Start here

| Guide | Use it for |
| --- | --- |
| [Basic use](tutorial-basics.md) | Read a form, inspect features, query classes and apply a rule. |
| [Task-based tutorial](tutorial.md) | Side-by-side Python and CLI workflows, with executed examples. |
| [Capabilities](capabilities.md) | What IPAkit implements, what remains planned, and how computation connects its representations. |
| [Glossary](glossary.md) | Phonetics and phonology vocabulary used in the guides. |

## Reference — how the representation works

Read, construct, navigate and exchange structured transcriptions.

| Guide | Use it for |
| --- | --- |
| [Canonical representation](representation.md) | Graph-backed Form, constructors, clocks, native persistence and linear JSON boundaries. |
| [Form views](form.md) | Compatibility projections: units, segments, boundaries, intervals and derived trees. |
| [House phonetic conventions](house-style.md) | The house model's spelling, composition, stress, boundaries and articulatory commitments. |
| [Units, ties and diacritics](ties.md) | Constituent structure and the distinction between simultaneous, sequential and adjacent units. |
| [Tone](tone.md) | Ordered contours, tone spellings and what individual marks assert. |
| [Syllabification](syllabification.md) | Language-relative syllable/mora intervals, constraints and conflicts. |
| [Corpus and structural search](corpus.md) | Persistent collections, structural queries and explicit external-resource ingestion. |
| [TextGrid interchange](textgrid.md) | Interval/point tiers, structural and physical clocks, and declared inventory styles. |

## Models and inventories

Notation, phoneset, feature geometry and algebra are separate choices. The house
model is one instance on the shared TierGraph substrate, developed alongside
IPAkit and IRN; it is not a required pivot for every model. The comparison guides
keep source distinctions, coverage and conversion losses explicit.

| Guide | Use it for |
| --- | --- |
| [Comparative systems](systems.md) | Compare organizing principles and implemented boundaries across models. |
| [Inventories and styles](inventories.md) | Named vocabularies, strict reading/spelling and dictionary-derived inventories. |
| [Inventory supplements](supplements.md) | Extend the house declaration and understand the effects on realization and comparison. |
| [Pinyin](pinyin.md) | Syllable-hosted tone, orthographic rendering and the internal graph-constructor boundary. |
| [Kana](kana.md) | Mora-tier rendering and bounded attested-adaptation API/CLI support. |
| [CLTS/BIPA](clts-audit.md) | Frozen native feature-set/Jaccard scoring, shared cost comparisons, source extraction and provenance; semantic mapping remains unresolved. |
| [Finite model operations](model-operations.md) | Typed declarations, model-bound feature edits and exact realization candidates; distinct from productive rewriting. |
| [Feature transformations](feature-transforms.md) | Declared finite re-encoding, explicit loss and preimages, and binary comparison through shared cost/alignment machinery. |
| [MFA vocabulary exhibit](mfa-vocabularies.md) | Generated declarations, source pins and refusal classes. |
| [eSpeak vocabulary exhibit](espeak-vocabularies.md) | Generated language-scoped and union vocabulary coverage. |
| [House declaration exhibits](house-style-exhibits.md) | Generated tie, boundary and character-class inventories behind the house conventions. |

## Rules and comparison

| Guide | Use it for |
| --- | --- |
| [Rewrite notation](rules.md) | Feature queries, contexts, insertion/deletion, traces and supported syntax. |
| [Variant calculus](calculus.md) | Optional rules, composition, enumeration caps and completeness reports. |
| [Similarity rationale](similarity.md) | Scoring choices, validation and comparison with neighboring approaches. |
| [Distance mechanics](distance.md) | Operational costs, normalization and the triangle-inequality limitation. |
| [Perceptual validation exhibit](perceptual-validation-exhibits.md) | Generated Miller–Nicely comparison evidence. |

## Reference — the articulatory model

| Guide | Use it for |
| --- | --- |
| [Tract anatomy](tract-anatomy.md) | Declared geometry, articulators and the posture model's limits. |
| [Tract reference](tract-reference.md) | The labeled key to the mid-sagittal figures. |
| [Figures and rendering](tract-figures.md) | Python, notebook and CLI drawing workflows and generated figures. |
| [Articulatory data](articulatory-data.md) | External X-Ray Microbeam grounding and its measurement limits. |
| [Anchor study](anchor-study.md) | Generated synchronization checks and target-timing measurements. |
| [Gestural model](gestural-model.md) | Implemented gesture/target projection versus the proposed dynamic model. |

## The wider literature

[Annotated reading](reading.md) connects the calculus, phonological theory,
articulation, speech technology and comparative work to their literature.
Historical assessments carry their own source lists.

## Working on ipakit

| Guide | Use it for |
| --- | --- |
| [Reviewing](reviewing.md) | Verification lessons and how to construct discriminating checks. |
| [Release checklist](releasing.md) | Package and release procedures. |
| [Developer sources](development-sources.md) | Shared extraction contracts, pinned sources and explicit update/build/check workflows. |
| [API/CLI reachability](cli-api-sync.md) | Generated checks of public reads and explicit library-only decisions. |
| [TierGraph acceptance](tiergraph-acceptance.md) | Implementation witnesses, upstream contracts and acknowledged coverage gaps. |
| [Historical state of the work](state-of-the-work.md) | Generated verdicts and superseded findings from dated design records—not a live task queue. |

The records in [design/](design/) retain historical evidence and decisions.
The canonical representation guide above supersedes their descriptions of the
current store; do not rewrite historical findings to look like present-day claims.

### Editing generated documentation

Edit tutorial prose in `tutorial-basics.src.md` and `tutorial.src.md`, then run
`make tutorial-basics` or `make tutorial`. Their rendered pages execute the
examples; `make notebook` derives the packaged notebook from the same tutorial
source. `ipakit notebook` makes that exercise notebook available without a checkout.

Generated pages and figures are regenerated, not hand-edited. The Makefile owns
the paths and commands for house/perceptual exhibits, vocabulary inventories,
figures and the historical state-of-work index. Documentation checks execute
examples, reconcile generated artifacts and check attributed quotations; each
guard's scope remains distinct.

## The shape of the repository

- `ipakit/` — the library. `ipakit/data/ipa.xml` declares the house inventory;
  other models and imported vocabularies have their own declarations.
  `ipakit/data/rules/*.rules` contains the shipped rule sets.
- `ipakit/cli/` — command-line task groups over library operations.
- `ipakit/tract.py` and `ipakit/tract_svg.py` — articulatory computation and
  rendering, kept separate.
- `scripts/` — measurements, generators and guards. Examples include
  `tutorial.py`, `docexamples.py`, `docquotes.py` and `invariants.py`;
  installed-library functionality belongs in the package.
- `tests/` — behavioral tests and shared corpus fixtures.
