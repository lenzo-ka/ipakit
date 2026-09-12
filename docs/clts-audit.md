# CLTS/BIPA declaration census and comparisons

## Native finite similarity

The shipped core BIPA snapshot can be queried without pyclts, an upstream
checkout, or network access:

```python
from ipakit.clts import read_snapshot

bipa = read_snapshot()
labels = bipa.features("p")
similarity = bipa.similarity("p", "b")
bipa.similarity("ç", "ç")  # 1.0
```

These are CLTS's raw feature-value labels, including its type labels, not
native IPAkit feature mappings. Unweighted Jaccard similarity counts set
intersection divided by union. `ipakit.feature_sets.FeatureSets` is the
provider-independent finite geometry; its empty-union convention is explicit
(zero similarity by default, matching CLTS). Distinct spellings can have the
same feature set. Neither label overlap nor a score proves perceptual or
articulatory equivalence.

The finite domain consists of the accepted core BIPA Sound entries, declared
aliases, and literal source spellings proven to resolve to the same core
Sound as their normalized dictionary key. There is no runtime normalization:
the NFC and NFD forms of `ç`, for example, are separately materialized lookup
keys. Original declaration spelling, canonical spelling, alias and
normalization metadata remain in `bipa.to_data()`.

Markers and literal source fields that the resolver rejects (including
whitespace-bearing TSV fields) are accounted for in `excluded`, not scored.
Productive composites such as `ai` are outside the shipped core even when
pyclts can resolve them. Missing keys raise `OutsideDomain` with code
`outside-artifact-domain`; this is not a claim that CLTS rejects that sound.
Inspect `requested`, `entries` and `excluded` for the exact generated
population. The full CLTS-to-Form importer and semantic feature mapping remain
separate work.

### Substitute the cost model, not the aligner

```python
from ipakit import load_ipa_features
from ipakit.bridges.costmodel import (
    Segmentation, compare_tokens, set_feature_pack,
)

pack = set_feature_pack(bipa.geometry, gap=1.0)
row = compare_tokens(
    load_ipa_features(), pack,
    Segmentation(("p", "a")), Segmentation(("b", "a")),
    return_alignment=True,
)
```

The pack supplies `1 - similarity` substitutions to the existing
`align_under` alignment fold. Gap cost is an explicitly named **adapter
policy**, not part of CLTS's sound similarity; scaling and normalization use
the existing `CostPolicy`. Unknown keys are validated for gaps as well as
substitutions, including unknown-self and empty-side comparisons.

Free strings are refused unless the caller supplies a tokenizer to the pack.
No whitespace splitting, native IPA parsing or longest-match segmentation is
silently substituted for CLTS token boundaries. The native default distance
is unchanged.

### Systematic explicit-token comparisons

Given a JSON corpus such as `[["p", "a"], ["b", "a"], ["p", "i"]]`:

```sh
python scripts/costmodel_compare.py --tokens-json corpus.json \
  --clts-snapshot --policy faithful --all-pairs --format json
```

This runs native, available declared Panphon, and selected CLTS costs through
the same fold. The report retains the caller's exact token corpus and its
identity, ordered-pair population, model/geometry/policy identities, scores,
and individual refusals. Token correspondences are supplied by the caller;
the comparison does not certify their phonetic equivalence. The reusable
library consumer is `compare_token_corpus` in `ipakit.bridges.costmodel`.

### Regeneration, verification and credits

```sh
python scripts/interop.py --clts /path/to/clts clts-snapshot --write
python scripts/interop.py --clts /path/to/clts clts-snapshot --check
python scripts/interop.py --clts /path/to/clts clts-parity
```

Library functions `extract_snapshot`, `build_core`, `validate_source`, and
`validate_parity` own extraction and checks; scripts only orchestrate their
results. `build_core` returns the shared `BuildResult` with relative artifact
bytes. Extraction requires the accepted clean CLTS revision and content
hashes, and the pinned pyclts version and module hashes. The single selected
source policy is [source.json](../ipakit/data/clts/source.json). Missing source,
missing resolver, wrong version, changed content and invalid artifact are
distinct errors; extraction never installs or fetches dependencies.

Parity checks every emitted key's exact set and every unordered unique-set
pair including diagonal, reporting the actual denominator. Deterministic
regeneration compares bytes, not just entry counts. `clts-snapshot
--tokens-json tokens.json` emits a separate explicitly scoped research
snapshot, including productive composites where the real resolver supports
them; it cannot overwrite the shipped core with `--write`.

The generated CLTS data remain **CC BY 4.0**, not IPAkit's BSD code license.
Credit: Johann-Mattis List, Cormac Anderson, Tiago Tresoldi, Christoph Rzymski,
and Robert Forkel, *CLTS. Cross-Linguistic Transcription Systems*.
See the [dataset DOI](https://doi.org/10.5281/zenodo.3515744),
[license](https://creativecommons.org/licenses/by/4.0/), and packaged
[artifact notice](../ipakit/data/clts/NOTICE.txt) for source revision,
transformations and attribution. pyclts is a separate Apache-2.0 development
dependency; none of its implementation is vendored into the runtime.

## Declaration census

CLTS/BIPA interoperability starts with the two systems' declarations, not
guessed symbol equivalences. The development instrument reads an external
[CLTS checkout](https://github.com/cldf-clts/clts); this full master/catalog
source is separate from the bounded shipped core snapshot above.

```sh
python scripts/interop.py --clts /path/to/clts declarations
```

This emits deterministic JSON (`ipakit-clts-declaration-census`, version 1).
Import the reusable library entry point with
`from ipakit.clts import declaration_audit`, then call `declaration_audit(Path(...))`;
the command delegates to it and only handles arguments, diagnostics, and JSON
output. The library returns the same plain dictionary and raises `ValueError`
for malformed input or `OSError` for inaccessible files.
It reads the master `pkg/transcriptionsystems/features.json` separately from
the derived `data/features.tsv` and observed `data/sounds.tsv`. Qualified
identities retain unit kind, feature name, and value: two features sharing a
value spelling are not merged. Native values come from the existing
`load_ipa_features()` declaration loader, retaining declared applicability,
mode, locus, type, axis, sequence support, and value order.

The output includes SHA-256 hashes of the consumed declaration/catalog
files, both directional queues, observed counts by sound kind, and up to five
sorted catalog sound IDs per CLTS feature/value. A master declaration without
a catalog witness remains present. A catalog feature absent from the master
is explicitly marked `declared: false`; it is not silently promoted into a
declaration. Missing inputs, malformed domains, duplicate identities, ragged
tables, and dangling feature references fail nonzero without emitting a report.
Featureless sound rows are outside this census and also refuse explicitly;
they cannot turn an empty observation population into a successful audit.
`cataloged` means membership in `data/features.tsv`, whereas `catalog.sounds`
counts rows in `data/sounds.tsv`; neither substitutes for `observed_count`.
Exit zero means the census ran, **not** that semantic correspondences passed.

Every entry currently has `status: unclassified` and no targets. This is an
audit foundation, not a conversion map or a claim that the target cannot
express a source distinction. Reviewed directional mappings, preconditions,
loss accounting, and enhancement dispositions remain separate work.

## Population boundary

This census covers finite feature/value declarations and feature occurrences
in the supplied sound catalog. Composite catalog kinds remain counted, with
their component feature contexts. Unit kinds lacking master domains are
listed explicitly. Productive composition rules, tier/host relationships,
and native combined or sequence-valued expressions are outside this census;
they must be audited before claiming a complete interoperability model.
The tool requires no `pyclts` import or runtime dependency.

## CLTS's own similarity

```sh
python scripts/interop.py --clts /path/to/clts similarity
```

This existing comparison needs the optional `pyclts` development dependency
(`pip install -e '.[interop]'`). CLTS's `Sound.similarity` is unweighted
Jaccard similarity over feature-value names: intersection size divided by
union size. The comparison uses `1 - similarity` so that smaller scores mean
closer sounds on both axes. It does not replace native `ipakit.distance`,
whose declared feature geometry distinguishes differences that a set overlap
does not. Neither a correlation nor nearest-neighbor agreement establishes
perceptual equivalence.

The population is registered native phone spellings directly resolved by
BIPA, with unknowns and markers excluded; it does not apply house spelling
normalization. Output identifies the resolver version, hashes `ipa.xml`, and
uses the existing native metric fingerprint to identify the effective feature
geometry. It hashes the whole CLTS transcription-system tree, including sibling
systems initialized by the resolver. Catalog hashes are separately labeled as
load-validation inputs, not sources of the pair scores. It then reports pair counts, score
resolution, rank correlation, and nearest-neighbor agreement. Equal nearest
scores use first native declaration order, not agreement between complete
tie sets. These results are measurements of the supplied sources, not frozen
claims about every release or all possible phones.

Upstream implementation: [pyclts sound models](https://github.com/cldf-clts/pyclts/blob/master/src/pyclts/models.py).
CLTS's inventory-level similarity methods are a separate API; this command
compares sound pairs, not inventories.

See [comparative systems](systems.md) and [capabilities](capabilities.md) for
the distinction between comparing models and establishing semantic fidelity.
