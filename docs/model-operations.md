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
loading the repository's frozen `tests/panphon/panphon.xml` and calling
`declaration.model.respell("p", {"voi": 1})` returns `b`, `b̟`, `b̠`—without
converting feature names or picking one spelling. That file is a repository
fixture, not an installed default artifact; callers supply their own path.

The frozen table has 24 features but 22 separately declared weights. Reading
and finite operations are valid independently of weighted scoring compatibility.
The weighted comparison family still refuses that incomplete weight basis;
the unweighted family, missing-cell policies and directional fidelity metadata
retain their existing behavior. Weights and scoring policies are not part of
the finite model's inventory identity: a comparison must additionally identify
its scoring policy and weight declaration. Bridge labels such as
`external-to-house` are retained historical metadata, not a mandated model path.

## Scope and substrate

This is finite lookup, query, edit and realization—not productive composition,
context-sensitive rewrite, an audio model or a new occurrence representation.
It does not make the native `Rule` parser accept foreign feature schemas.
Validated cross-model transformations and reusable rewrite backends remain
separate planned work.

These immutable tables describe schema and inventory data; they are not
TierGraph instances. TierGraph is the shared computational substrate developed
alongside IPAkit and IRN, including typed graphs and semiring machinery. The
existing comparison factory continues to use its semiring fold. Future model
occurrences and rewrite integration must reuse the graph and rule machinery
with explicit domain validation; an integer graph attribute alone does not
enforce a finite feature domain.
