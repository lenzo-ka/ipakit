# Finite model operations

`ipakit.finite_model` exposes finite schemas and inventories without making any
inventory semantically primary. A token can be an opaque provider spelling;
there is no fallback through house IPA. The native default remains a convenience
elsewhere, not a required pivot for these operations.

```python
from ipakit.finite_model import FeatureSchema, FiniteModel

model = FiniteModel(
    "example",
    FeatureSchema({"register": ("low", "high")}),
    {"UNIT-1": ("low",), "UNIT-2": ("high",), "ALIAS": ("high",)},
)
result = model.respell("UNIT-1", {"register": "high"})
assert result.candidates == ("UNIT-2", "ALIAS")
assert result.status == "ambiguous"
```

Schemas preserve feature order and finite domains of strings, integers or
booleans. Types are significant: integer zero and boolean false are distinct.
Schema and bundle equality and hashing preserve those types; they can be used
as dictionary/set keys without merging distinct values. Schema declaration
order and inventory row order are significant, including in model identity.
`None` always means a missing cell, distinct from an explicit domain zero; it is
not permitted as a domain member. Rows have exactly one cell per feature.
Directly constructed tokens are exact strings, without implicit normalization.

`read(token)` returns a complete, model-bound `FeatureBundle`. `query(mapping)`
is a partial equality query; an empty mapping matches every row in declaration
order. `edit(bundle, mapping)` validates the changed fields without inventing a
spelling. `realize(bundle)` returns all exact complete-bundle candidates, in row
order. `respell(token, mapping)` combines read, edit and realize.

Realization status is `none`, `unique` or `ambiguous`; zero candidates is a valid
but unrepresented bundle, not an invalid edit. `InvalidFeature` rejects unknown
features, invalid values and wrong bundle widths. `MissingToken` rejects absent
inputs. `ModelMismatch` rejects a bundle with another model identity, even if
its feature names happen to match. Transformations between models require an
explicit contract; these methods do not perform one.

Schemas and inventory rows are defensively copied and read-only. Model identity
is a content fingerprint of name, ordered schema/domains, ordered rows and
optional `SourceMetadata`. Bundles retain that identity; realization results
also retain source metadata. Equal bundles can have many spellings, and no
first-row inverse or canonical spelling is inferred.

## Existing ternary declarations

`ipakit.finite_declaration.read_ternary_declaration(path)` is the single XML
reader also used by `ipakit.bridges.costmodel.pack_from_declaration(path)`.
Its returned `TernaryDeclaration` exposes `.model`, ordered `.weights`,
`.weight_names`, legacy directional `.bridge` metadata and `.tokenize(text)`.
The latter returns `(tokens, dropped)` with NFD longest-match tokenization.
Declaration keys must already be nonempty NFD strings. Duplicate features or
tokens, undeclared row features and non-ternary cell values are rejected.

The XML codec maps `-`, `0`, `+` to integers `-1`, `0`, `1`; omitted attributes
remain `None`. Generic finite schemas do not require this domain. For example,
loading the shipped model with `ipakit.feature_models.read("panphon")` and calling
`declaration.model.respell("p", {"voi": 1})` returns `b`, `b̟`, `b̠`—without
converting feature names or picking one spelling. `feature_models.available()`
enumerates shipped declarations; `resource_path(name)` exposes their canonical
package paths. Explicit caller paths still use `read_ternary_declaration(path)`.
The frozen `ipakit/data/feature-models/panphon.xml` travels with its source
version/hash receipts, attribution and MIT permission notice. Panphon itself is
needed only to regenerate or validate the artifact, not to read or operate on it.
These feature models are not automatically house notation styles or mappings.
Import the module explicitly with `from ipakit import feature_models`; it is
not an optional-provider import or a new overload of the native flat wrappers.

The frozen table has 24 features but 22 separately declared weights. Reading
and finite operations are valid independently of weighted scoring compatibility.
The weighted comparison family still refuses that incomplete weight basis;
the unweighted family, missing-cell policies and directional fidelity metadata
retain their existing behavior. Weights and scoring policies are not part of
the finite model's inventory identity: a comparison must additionally identify
its scoring policy and weight declaration. Bridge labels such as
`external-to-house` are retained historical metadata, not a mandated model path.

## Command line

Select a model explicitly; the finite commands do not choose a primary inventory:

```sh
ipakit model list -j
ipakit model inspect --model panphon -j
ipakit model respell --model panphon --token p --changes-json '{"voi":1}' -j
ipakit model inspect --model-declaration TABLE.xml --rows -j
```

`--model` and `--model-declaration` are mutually exclusive and one is required
for inspection or respelling. `list` enumerates shipped feature models, not
house Styles. Inspection includes ordered domains, token count, source metadata,
content identity and codec policy; `--rows` adds the actual ordered inventory.
Respelling takes one exact token without segmentation or Unicode normalization.
Its report retains the input, edits, model identity, resulting values and all
ordered candidates. Text output quotes tokens as JSON too. Both commands accept
`-o` for output; `-j` selects JSON reports, not a new model serialization format.

Edits must be a JSON object without duplicate keys. Integer `1`, boolean `true`
and string `"1"` remain distinct; only declared ternary integers or missing-cell
`null` are accepted by this codec. Unknown tokens, models, features and invalid
values fail with exit 1, including with `--lax`. Zero or multiple realization
candidates are successful answers, never a guessed first spelling. Missing or
mixed selectors are command-line errors (exit 2). Producer packages, checkout
fixtures and network access are not needed for named or supplied declarations.

## Scope and substrate

These methods provide finite lookup, query, edit and realization—not productive
composition, an audio model or a new occurrence representation. Validated
cross-model operations are described in [feature transforms](feature-transforms.md).
The shared [rules engine](rules.md) also accepts explicitly bound finite models
for supported context-sensitive operations; its typed library contracts and
capability refusals remain distinct from the inspect/respell CLI slice above.

These immutable tables describe schema and inventory data; they are not
TierGraph instances. TierGraph is the shared computational substrate developed
alongside IPAkit and IRN, including typed graphs and semiring machinery. The
existing comparison factory continues to use its semiring fold. Future model
occurrences and rewrite integration must reuse the graph and rule machinery
with explicit domain validation; an integer graph attribute alone does not
enforce a finite feature domain.
