# Finite feature transformations

[Working with alternate feature inventories](inventory-operations.md) combines
house, Panphon, CLTS and custom cost packs in one explicit-token comparison.

`ipakit.feature_transform` re-encodes features within explicitly declared finite
domains using the [finite model provider](model-operations.md). Each transformation
declares its source and target schemas directly and reports preserved or lost
distinctions. Phonetic equivalence requires evidence beyond vector equality.

```python
from ipakit.finite_model import FeatureSchema, FiniteModel
from ipakit.feature_transform import BinaryEncoding, ternary_to_binary

source = FiniteModel(
    "example", FeatureSchema({"f": (-1, 0, 1)}),
    {"NEG": (-1,), "ZERO": (0,), "POS": (1,)},
)
operation = ternary_to_binary(
    source, BinaryEncoding.TWO_PREDICATE, missing="require-complete",
)
witness = operation.apply(source.read("POS"))
assert witness.target.values == (1, 0)
assert operation.decode(witness.target).count == 1
```

The required encoding choice is `TWO_PREDICATE` (`+ → 10`, `0 → 00`, `- → 01`)
or `POSITIVE_ONLY` (`+ → 1`, `0/- → 0`). The latter is deliberately lossy; zero
is never silently interpreted as negative. `require-complete` is the only
supported missing-cell policy: an absent row or input bundle is refused with
`MissingFeature`. No missing cell is hidden in the zero code.

## Contracts and loss

`FiniteTransform` also accepts general `FeatureMap`/`ScalarCase` declarations.
Each source feature has exactly one map, with one case per typed domain value;
its cases output tuples for a disjoint group of target features. Every target
feature must be covered exactly once. An empty target group explicitly drops
a source distinction. Outputs are validated against the target `FeatureSchema`.
String, integer and boolean source domains are supported; types remain distinct.

The operation binds actual source model content identity, ordered target schema,
maps, missing policy and optional operation `SourceMetadata`. Its target is an
immutable `FiniteModel` retaining the original inventory spellings and source
metadata. Forward witnesses carry both model-bound bundles, operation identity
and operation provenance. A schema-compatible-looking model with different
content is not accepted as the bound source.

`injective` concerns the complete declared feature domains. `collisions()`
reports only observed inventory groups with distinct source bundles mapped to
one target bundle. Spelling aliases share an existing source bundle and are excluded
from those collision groups. A noninjective map can have no observed inventory collisions.

`decode(target_bundle)` returns a `Preimage`: independent per-feature choices,
their product `count`, actual source-inventory spelling candidates, source model
identity and operation identity. It retains the factored choices and their count,
including choices with no inventory spelling. A code
outside the map's image, including `11` in the two-predicate encoding, raises
`OutsideImage`; schema-invalid codes raise `InvalidFeature` instead.

The shipped frozen Panphon declaration has 6,367 rows, all of which round-trip
through the two-predicate construction. Positive-only projection has 214 observed
collision groups of distinct complete vectors. These counts describe this pinned
table. Other provider versions and phonetic equivalence require separate measurements.
Load it with `from ipakit import feature_models` and
`feature_models.read("panphon")`; supplied paths still use the existing
`read_ternary_declaration(path)`. No external producer package, source update or
development checkout is needed. The packaged declaration includes its source
version/hash receipts and license/attribution notices.

## Binary comparison through the existing folds

```python
from ipakit.binary_cost import binary_pack
from ipakit.bridges.costmodel import Segmentation, semiring_alignment
from tiergraph.semiring import TROPICAL

pack = binary_pack(operation, gap=1.0)
cost = semiring_alignment(
    pack, Segmentation(("NEG",)), Segmentation(("POS",)),
    TROPICAL, encode=float,
)
assert cost == 1.0
```

`binary_pack` returns an existing `CostPack`: normalized weighted Hamming
substitution, an explicitly supplied constant positive gap price, and an optional
existing `CostPolicy`. With no weight mapping every bit has weight one; an
explicit mapping must name every target feature and have positive total mass.
Zero individual weights are permitted and can collapse additional distinctions.
Substitution is divided by weight mass before `substitution_scale`; gap pricing
is separately multiplied by `indel_weight`. Effective gap pricing must remain
positive and finite. Existing final normalization policies remain separate from
this per-substitution normalization.

For equal bit weights the two-predicate substitution equals the source ternary
formula `sum(abs(a-b)) / (2*n)` for complete bundles. Gap prices and other weighted
formulas have separate contracts. In the frozen fixture, the naive
Hamming-to-zero gap for `a` is `20/48`, while the declared source insertion price
is `44/48`. Callers explicitly choose the binary gap price.

The pack text tokenizer accepts **one exact token**, or an empty sequence. It
does not split concatenated foreign tokens, normalize their spelling, or route
unknown material through house phonetics. Use explicit `Segmentation` for
multi-token inputs. Substitution and callable gap prices both validate tokens
through the target model, including self-comparisons and generic semiring folds.
Pack identity binds transform, target model, ordered weights, gap, CostPolicy
and exact-token input policy.

These interfaces support finite scalar re-encoding and binary comparison.
General transform composition, context rewriting and productive phonetic
composition remain separate operations. TierGraph supplies the shared
graph/semiring substrate developed alongside IPAkit and IRN; comparisons use
its existing alignment fold.

## Repeatable original/binary experiments

The installed finite-model command selects binary encodings explicitly:

```sh
ipakit model compare --model panphon --tokens-json corpus.json \
  --encoding two-predicate --encoding positive-only \
  --binary-gap 1 --policy faithful -j
```

Here `corpus.json` is an array of exact token arrays, for example
`[["p"], ["b"], ["a"], []]`. Model selection, encodings, gap and policies are
required. `--model-declaration` selects another compatible file. An explicitly
selected missing or unreadable file refuses instead of producing house-only
output. No Panphon runtime, download or inferred house conversion is needed.
The command is foreign-only unless `--include-house` is supplied. Repeated
identical encodings or policies refuse rather than duplicate arms or overwrite
metadata. The repository's broader `scripts/costmodel_compare.py` retains its
house/declared/CLTS development workflows and uses the same library experiment in
binary mode.

The library entrypoint is
`ipakit.feature_experiment.compare_declaration_encodings`. Pass an IPAFeatures
alignment host, an already-read `TernaryDeclaration`, the token corpus, explicit
`encodings`, `binary_gap` and `policies`. Its default is foreign-only. All arms
use one `compare_token_corpus` call, retaining the same corpus identity, pair
denominator and individual refusal rows. An unknown token is not discarded or
retokenized. The host supplies alignment mechanics; each selected model supplies
its own feature semantics.

The report's `experiment` block records the declaration's model/content receipt,
source and directional bridge metadata, feature order, declared-but-unused weights,
and each arm's actual policy, transform/target identities, bit basis and weights.
Binary weights are explicitly all one in this bounded helper. Domain injectivity
and observed collision counts remain separate; aliases are not collisions.
The experiment identity names this configuration, while `corpus_identity` names
the separate input population. Neither certifies phonetic equivalence.

Source-dependent original indels and constant binary gaps are separately named.
With the frozen fixture and faithful policy, deleting `a` costs 44/48 in the
original arm and 1 with the selected binary gap above. Hamming-to-zero is 20/48
for that binary vector and is reported here as a diagnostic. The experiment uses
the selected constant gap policy. Matching substitution formulas do not imply matching
sequence distances when indels differ.

`pack_from_ternary_declaration` in `ipakit.bridges.costmodel` is the shared object
factory; `pack_from_declaration(path)` remains its reader-plus-factory wrapper.
The experiment parses no XML itself. Both paths validate the object contract,
including typed ternary domains, NFD tokens, finite nonnegative weight metadata
and consistent source receipts, before creating costs. Caller-built provenance
is checked for internal consistency; upstream authentication requires a separate
source validation step.
Incomplete weight metadata is still legal for the unweighted family; the
weighted family retains its stricter refusal. No weights are silently repaired.
