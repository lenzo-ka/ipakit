# Finite model operations

For executable lookup, `phones_matching`/query, respelling and multi-model
comparison recipes, see [working with alternate feature inventories](inventory-operations.md).

`ipakit.finite_model` provides lookup, query, editing and realization for explicitly
selected finite schemas and inventories. Each model operates on its own feature
domains and exact provider spellings. Models have equal standing in these
operations; conversion through house IPA requires an explicit separate operation.

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

`features(token)` returns a fresh dictionary in feature declaration order,
preserving scalar types and missing cells (`None`). `read(token)` returns a
complete, model-bound `FeatureBundle` for editing and realization; the convenience
dictionary carries no model identity or provenance. `phones_matching(mapping)`
delegates to `query(mapping)`, the compatible partial equality query; an empty
mapping matches every row in declaration
order. `edit(bundle, mapping)` validates the changed fields without inventing a
spelling. `realize(bundle)` returns all exact complete-bundle candidates, in row
order. `respell(token, mapping)` combines read, edit and realize.

Realization status is `none`, `unique` or `ambiguous`; zero candidates identifies
a valid bundle with no inventory spelling. `InvalidFeature` rejects unknown
features, invalid values and wrong bundle widths. `MissingToken` rejects absent
inputs. `ModelMismatch` rejects a bundle with another model identity, even if
its feature names happen to match. Transformations between models require an
explicit contract; these methods do not perform one.

Schemas and inventory rows are defensively copied and read-only. Model identity
is a content fingerprint of name, ordered schema/domains, ordered rows and
optional `SourceMetadata`. Bundles retain that identity; realization results
also retain source metadata. Equal bundles can have many spellings; realization
returns every candidate in declaration order.

## Existing ternary declarations

`ipakit.finite_declaration.read_ternary_declaration(path)` is the single XML
reader also used by `ipakit.bridges.costmodel.pack_from_declaration(path)`.
Its returned `TernaryDeclaration` exposes `.model`, ordered `.weights`,
`.weight_names`, directional `.bridge` metadata and `.tokenize(text)`.
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
These declarations expose finite feature models. House notation styles and
mappings have separate interfaces. Import the module explicitly with
`from ipakit import feature_models`.

The frozen table has 24 features but 22 separately declared weights. Reading
and finite operations are valid independently of weighted scoring compatibility.
The weighted comparison family still refuses that incomplete weight basis;
the unweighted family, missing-cell policies and directional fidelity metadata
retain their existing behavior. Weights and scoring policies are not part of
the finite model's inventory identity: a comparison must additionally identify
its scoring policy and weight declaration. Bridge labels such as
`external-to-house` retain historical provenance; each operation selects its model path explicitly.

## Command line

Select the model to inspect, query, edit or transform:

```sh
ipakit model list -j
ipakit model inspect --model panphon -j
ipakit model query --model panphon --features-json '{"voi":1}' -j
ipakit model respell --model panphon --token p --changes-json '{"voi":1}' -j
ipakit model transform --model panphon --token p --encoding two-predicate -j
ipakit model inspect --model-declaration TABLE.xml --rows -j
```

`--model` and `--model-declaration` are mutually exclusive and one is required
for inspection, querying or respelling. `list` enumerates shipped feature models; house
Styles have their own inventory. Inspection includes ordered domains, token count, source metadata,
content identity and codec policy; `--rows` adds the actual ordered inventory.
Respelling takes one exact token without segmentation or Unicode normalization.
Its report retains the input, edits, model identity, resulting values and all
ordered candidates. Text output quotes tokens as JSON too. Both commands accept
`-o` for output; `-j` selects JSON reports. Declaration serialization remains
with the model codec.

Edits must be a JSON object without duplicate keys. Integer `1`, boolean `true`
and string `"1"` remain distinct; only declared ternary integers or missing-cell
`null` are accepted by this codec. Unknown tokens, models, features and invalid
values fail with exit 1, including with `--lax`. Zero or multiple realization
candidates are successful answers, never a guessed first spelling. Missing or
mixed selectors are command-line errors (exit 2). Producer packages, checkout
fixtures and network access are not needed for named or supplied declarations.

`model transform` uses the library's declared `ternary_to_binary` operation. Its
report retains the source and target bundles, both model identities, the transform
identity and missing-cell policy, the decoded preimage, domain injectivity and all
observed inventory collision groups. `--encoding` is required and accepts
`two-predicate` or `positive-only`; no binary meaning is inferred from ternary zero.
The selected declaration must have complete integer-ternary rows, and an unknown
token or invalid transform fails with exit 1.

To compare the original declaration with selected transformed arms, put exact token
arrays in `corpus.json` and run:

```sh
ipakit model compare --model panphon --tokens-json corpus.json \
  --encoding two-predicate --encoding positive-only \
  --binary-gap 1 --policy faithful --all-pairs -j
```

`--model` or `--model-declaration`, at least one `--encoding`, `--binary-gap`, and
at least one `--policy` are all explicit. Policies may select `faithful` or
`conserving`; repeated duplicate encodings or policies are refused by the shared
experiment contract. The default comparison is foreign-only; `--include-house`
adds the native arm deliberately. `--all-pairs` selects every ordered pair of
distinct corpus positions instead of adjacent positions. The command delegates to
`compare_declaration_encodings`, so its JSON is the library report unchanged and
retains configuration identities, corpus identity, costs and per-input refusals.

## Scope and substrate

These methods provide finite lookup, query, edit and realization. Productive
composition, audio modeling and occurrence representation are outside this finite provider. Validated
cross-model operations are described in [feature transforms](feature-transforms.md).
The shared [rules engine](rules.md) also accepts explicitly bound finite models
for supported context-sensitive operations; its typed library contracts and
capability refusals also govern the [finite rule commands](rules.md#explicit-finite-rules-on-the-command-line).
Those commands share the explicit named/path selector above and receive exact
token arrays via `--tokens-json`. Typed AST construction remains a library
composition interface; the declared ternary-to-binary transform and its comparison
experiment have the command-line surfaces above.

These immutable tables describe schema and inventory data. TierGraph provides
occurrence graphs and is the shared computational substrate developed
alongside IPAkit and IRN, including typed graphs and semiring machinery. The
existing comparison factory continues to use its semiring fold.
[GraphBinding](rules.md#decorating-an-existing-graph) validates a model, ordered
source references, declared value relations and the source clock before the
shared rule engine decorates the existing graph. Original facts and optional
source timing are preserved; target timing and containment are not inferred.
Native codec round-trips retain the graph, while operation restoration requires
the explicit binding and rules. House `Form` admission follows its own profile
contract; operation discovery from a graph alone remains unsupported. Finite
feature domains are enforced by the model binding in addition to graph attribute types.
