# Working with alternate feature inventories

Select an inventory, inspect its features, find matching tokens, and edit or
compare them using that inventory's declarations. The examples below use the
shipped Panphon and CLTS data plus a small caller-defined model. They run with
the installed library; producer packages and source checkouts are needed only
for regeneration. Run the Python blocks in order in one session.

## Lookup, matching, and respelling

```python
import ipakit
from ipakit import feature_models

declaration = feature_models.read("panphon")
panphon = declaration.model
values = dict(zip(panphon.schema.features, panphon.read("p").values, strict=True))
assert values["voi"] == -1

voiced = panphon.query({"voi": 1})
assert "b" in voiced and "p" not in voiced
changed = panphon.respell("p", {"voi": 1})
assert changed.candidates == ("b", "b̟", "b̠")
assert changed.status == "ambiguous"

house_matches = ipakit.phones_matching({"manner": "plosive", "place": "bilabial"})
assert "p" in house_matches and "b" in house_matches
assert "p" in ipakit.phones_matching(["+plo", "-voi"])
```

The respelling result retains all spellings with the edited complete vector.
Applications can present those candidates or apply their own explicit selection
policy. A valid vector can also have no spelling in the selected inventory.

| Operation | House inventory | Finite feature model |
| --- | --- | --- |
| Read features | `ipakit.get_features(token)` projects the house unit's features. | `model.read(token)` returns the exact row with its model identity. |
| Find matching inventory phones | `ipakit.phones_matching(query)` accepts a house feature dictionary or a collection of long/short names, including signed terms. | `model.query(mapping)` performs typed partial equality and returns matching tokens in declaration order. |
| Change features and spell | `IPAFeatures.respell(token, **changes)` uses house composition and returns one spelling or `None`; see [phonological rules](rules.md). | `model.respell(token, changes)` returns every complete-vector spelling candidate. |
| Compare | House segment geometry and alignment costs have separate interfaces. | A declared or custom cost pack supplies costs to the shared alignment fold. |

House `phones_matching` searches registered phones and applies declared defaults
by default (`with_defaults=False` changes that reading). Its query language also
supports named classes and exclusions. A bare query string is refused; use a
dictionary or collection. `ipakit.find(text, query)` applies house queries to
the parsed units of a transcription.

Finite queries use each model's own feature names and value types: Panphon uses
integer `-1`, `0`, `1`; generic finite models can declare strings or booleans.
`None` queries a missing cell. Unknown features or invalid values raise
`InvalidFeature`. House shortcuts such as `+plo` have no implicit finite-model
interpretation. `query({})` returns the complete finite inventory in declaration
order. Exact token spelling and typed equality are preserved throughout.

## Shared inventory interfaces

Adapters give inventory operations common method names while retaining each
model's feature types and realization policy:

```python
from ipakit.inventory_operations import FiniteInventory, HouseInventory

finite = FiniteInventory(panphon)
house = HouseInventory(ipakit.IPAFeatures())
assert "b" in finite.phones_matching({"voi": 1})
assert "b" in house.phones_matching({"voiced": "+"})
assert finite.respell("p", {"voi": 1}).status == "ambiguous"
assert house.respell("p", {"voiced": "+"}).spelling == "b"
```

The common read interface exposes `name`, `identity`, `declared_tokens`,
`admission`, and `read(token)`. Observation values remain model-specific.
Matching and respelling are additional capabilities. Finite respelling retains
every exact-vector candidate; house respelling returns its canonical spelling.
Keep a bound house `IPAFeatures` instance unchanged for the adapter's lifetime.

The finite CLI exposes matching with typed JSON constraints:

```sh
ipakit model query --model panphon --features-json '{"voi":1}' -j
ipakit model query --model panphon --features-json '{}' -j
```

An empty constraint object enumerates the model's declared tokens. Use
`--model-declaration TABLE.xml` to select a supplied ternary declaration.

## A caller-defined declaration

This illustrative two-feature table assigns values explicitly. Its labels and
values are local definitions; they do not establish a phonetic mapping to the
other inventories. Save and read it through the existing ternary XML codec:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from ipakit.finite_declaration import read_ternary_declaration

xml = '''<model name="example-two-feature" upstream="Example author"
  upstream-url="https://example.org/model" artifact="example.xml"
  version="1" license="MIT" kind="features">
  <round-trip>
    <external-to-house fidelity="lossy-with-report"/>
    <house-to-external fidelity="lossy-with-report"/>
  </round-trip>
  <features><feature name="voice"/><feature name="vowel"/></features>
  <segments>
    <s name="p" voice="-" vowel="-"/>
    <s name="b" voice="+" vowel="-"/>
    <s name="a" voice="+" vowel="+"/>
  </segments>
</model>'''
with TemporaryDirectory() as directory:
    path = Path(directory) / "example.xml"
    path.write_text(xml, encoding="utf-8")
    custom = read_ternary_declaration(path)

assert custom.model.query({"voice": 1}) == ("b", "a")
assert custom.model.respell("p", {"voice": 1}).candidates == ("b",)
```

The historical directional labels in this XML retain the codec's required
provenance contract. Computation below uses the custom vectors directly.

## Compare an explicit set of cost models

Build named packs and send the same token corpus through all of them:

```python
from ipakit.bridges.costmodel import (
    CostPolicy, compare_token_corpus, house_pack,
    pack_from_ternary_declaration, set_feature_pack,
)
from ipakit.clts import read_snapshot
from ipakit.feature_sets import FeatureSets
from ipakit.feature_transform import BinaryEncoding, ternary_to_binary
from ipakit.binary_cost import binary_pack

ipa = ipakit.load_ipa_features()
policy = CostPolicy()
bipa = read_snapshot()
custom_sets = FeatureSets("example-labels", {
    "p": {"stop", "voiceless"},
    "b": {"stop", "voiced"},
    "a": {"vowel", "voiced"},
})
binary = ternary_to_binary(
    custom.model, BinaryEncoding.TWO_PREDICATE, missing="require-complete",
)
selected = {
    "house": house_pack(ipa, policy),
    "panphon": pack_from_ternary_declaration(declaration, policy),
    "clts": set_feature_pack(bipa.geometry, policy, gap=1.0),
    "custom-declaration": pack_from_ternary_declaration(custom, policy),
    "custom-labels": set_feature_pack(custom_sets, policy, gap=1.0),
    "custom-binary": binary_pack(binary, policy=policy, gap=1.0),
}
corpus = [["p"], ["b"], ["a"], []]
report = compare_token_corpus(ipa, list(selected.values()), corpus, all_pairs=True)
assert report["ordered_pairs_per_pack"] == 12
assert len(report["rows"]) == len(selected) * 12
assert all(row["status"] == "scored" for row in report["rows"])

# Keep short caller labels alongside each pack's full reported identity.
names = {pack.name: name for name, pack in selected.items()}
for row in report["rows"]:
    if (row["source_index"], row["target_index"]) == (0, 1):
        print(names[row["pack"]], row["edit_cost"])
```

`all_pairs=True` selects all ordered pairs of distinct corpus positions, including
both directions. The explicit pack list selects the models. The report retains
corpus, policy and geometry identities and records a refusal per unsupported pair.
The caller supplies the correspondence between tokens across these inventories;
matching spellings alone do not establish phonetic equivalence.

`FeatureSets` and `set_feature_pack` support caller-defined Jaccard geometry.
The binary option reuses a validated finite transformation. For other formulas,
`CostPack` accepts model-owned substitution, insertion, deletion, tokenization
and optional token-validation callables, plus declared ceilings and policy.
Those callables must implement the stated admission and pricing contracts.

## Read scores with their policies

For `p` and `b` in these shipped declarations:

```python
from math import isclose

assert isclose(ipa.segment_distance("p", "b"), 1 / 21)
assert isclose(selected["house"].sub_cost("p", "b"), 2 / 21)
assert isclose(selected["panphon"].sub_cost("p", "b"), 1 / 24)
assert isclose(bipa.similarity("p", "b"), 0.6)
assert isclose(selected["clts"].sub_cost("p", "b"), 0.4)
```

House raw segment distance is converted to an alignment substitution price.
Panphon's default declared family uses normalized ternary difference; CLTS's
adapter uses `1 - similarity`. Sequence alignment also considers insertion and
deletion paths. `CostPolicy` names substitution scaling, indel scaling and final
normalization. Its default reports raw edit cost; alternative normalizations
change the `normalized` field. CLTS and binary gaps are explicit adapter choices.
The declared Panphon family derives indels from its vector cells.

Some combinations refuse while building the pack, before corpus scoring:

```python
from ipakit.bridges.costmodel import AbsentCell, DeclaredCostFamily

assert len(panphon.schema.features) == 24
assert len(declaration.weight_names) == 22
try:
    pack_from_ternary_declaration(
        declaration, family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
        absent=AbsentCell.SKIP,
    )
except ValueError as error:
    assert "one weight per feature" in str(error)
else:
    raise AssertionError("incomplete weight declaration was accepted")
```

The shipped unweighted family remains usable. Weighted scoring requires a complete
declared weight basis; callers should report this construction refusal separately
from unsupported-token rows returned by the corpus comparison.

## Command-line comparisons

In a repository checkout, save the corpus as JSON and run:

```sh
python scripts/costmodel_compare.py --tokens-json corpus.json --clts-snapshot \
  --policy faithful --all-pairs --format json
```

This selects house, shipped Panphon and CLTS packs. `--declaration TABLE.xml`
replaces the declared feature table; `--foreign-only` omits house. Policies can
be repeated explicitly. Binary experiments have their own flags described in
[feature transforms](feature-transforms.md#repeatable-originalbinary-experiments).
The script currently keeps binary and CLTS modes separate.

## Named metric selection

The metric registry collects named configurations over inventories. Each
inventory can support several metrics. The built-in registry includes house
articulatory alignment, Panphon symmetric and weighted difference, and CLTS
Jaccard-complement alignment. The weighted Panphon entry reports its incomplete
weight basis as unavailable.

```python
from ipakit.distance_registry import builtin_registry

registry = builtin_registry()
all_distances = registry.distances(("p",), ("b",), metrics="all")
selected_distances = registry.distances(
    ("p",), ("b",),
    metrics=["house/articulatory", "panphon/symmetric-difference"],
)
all_pairs = registry.compare_corpus(
    [["p"], ["b"], ["a"], []], metrics="all", all_pairs=True,
)
```

`metrics="all"` expands the registry's names in registration order. An explicit
name list preserves caller order and rejects duplicate or unknown names.
`all_pairs=True` separately compares every ordered pair of distinct corpus
positions, producing quadratic output. Both directions are retained for
asymmetric costs. Inputs are exact token sequences.

Reports retain metric configuration and inventory identity, construction
unavailability, and per-pair scoring refusals. A completed report can therefore
include entries without a numeric score. Raw edit cost, normalization and
reference distribution stay attached to the result.

Arm IDs describe the recorded inventory and metric configuration. For custom
callbacks, include the implementation version and every cost parameter in that
configuration, and establish implementation provenance before sharing cached
results across providers. Registration records the caller's declarations.
Numeric comparisons require finite costs, accumulated totals and normalization
budgets; values outside that range produce refusals.

The installed CLI uses the same registry:

```sh
ipakit distance metrics -j
ipakit distance across --tokens-json corpus.json --metric all --all-pairs -j
ipakit distance across --tokens-json corpus.json \
  --metric house/articulatory --metric panphon/symmetric-difference -j
ipakit distance across --tokens-json corpus.json \
  --metric-declaration custom/table=TABLE.xml --metric custom/table -j
```

`--metric-declaration NAME=PATH` registers a supplied ternary table with the
symmetric-difference family. Custom library registrations can supply other
existing cost packs and explicit configurations. The CLI returns status0 when
it produces the complete report; inspect each metric and pair's status to
distinguish scores, unavailability and refusals.
