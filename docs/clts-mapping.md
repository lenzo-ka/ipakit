# Reviewed CLTS correspondences

The `ipakit.clts_mapping` library provides a bounded, directional correspondence
authority. It is not a general converter or a completed TierGraph/Form importer.
Neither inventory is semantically primary. The current rules prove eligibility
only for the exact plain-stop witnesses `p`, `b`, `t`, and `d`, from CLTS to IPAkit.
There is no inferred inverse.

```python
from ipakit.clts import read_snapshot
from ipakit.clts_mapping import read_authority

authority = read_authority()
result = authority.eligibility("p", read_snapshot())
assert result["status"] == "eligible-witness"
assert result["target"] == "p"
assert result["import_ready"] is False
```

This works offline with shipped artifacts; it does not load pyclts. Eligibility
requires the complete source claim set, exact source spelling, and the reviewed
native structural context. Extra claims are not silently discarded. Native
defaults not asserted by CLTS are recorded separately, not attributed to CLTS.
Other tokens remain unresolved, including affricates, approach/release forms,
vowels, and tone. Exact source recovery is a separate operation from reverse
phonetic conversion.

The authority binds the accepted CLTS policy, source input hashes, frozen core
identity, native declaration hash, effective native metric fingerprint, and its
own contents. Changed populations or provider bindings require reconciliation.
These fingerprints detect changed inputs; they are not signatures or proofs of
phonetic equivalence. `require_import_profile(...)` currently refuses every
request: final structural compatibility awaits the reviewed source-profile
binding. The `target` field is a research witness, not an imported Form.

## Declarations, rules, and token eligibility

The [generated gap report](clts-gaps.md) accounts for every master declaration
and native declaration, using the same [declaration audit](clts-audit.md) parser
with `include_catalog=False`. It contains no catalog observations, witness IDs,
counts or catalog-only domains. The default full audit remains an explicitly
external-checkout research operation; its catalog derivative is not shipped or
cleared by the core-data notice. The
[mapping notice](../ipakit/data/clts/MAPPING-NOTICE.txt) states the narrower
artifact's sources, transformations and attribution.
An entry with a conditional witness is not universally convertible; its rule
applies only in the stated complete-token context. Unproven entries remain
explicitly unresolved. Every reverse-direction entry remains unresolved.

The reviewed authored rules live in
[semantic-rules.json](../ipakit/data/clts/semantic-rules.json). The generated
[semantic-mapping.json](../ipakit/data/clts/semantic-mapping.json) holds receipts,
dispositions and constructive native witnesses. The historical `interop.py`
correspondence dictionary remains a diagnostic candidate table, not this
authority. A missing table entry does not establish native inexpressibility:
native nasal approach already exists, ties can lose information in CLTS, and
tone requires a caller-supplied host rather than strict segment interpretation.

## Rebuilding

Building needs the pinned development provider and accepted local CLTS checkout
described by the [CLTS source policy](../ipakit/data/clts/source.json). Acquisition
and dependency installation are separate from this command.

```sh
python scripts/interop.py --clts /path/to/clts clts-mappings --check
python scripts/interop.py --clts /path/to/clts clts-mappings --write
```

Without either flag the command emits the authority JSON. The reusable
`build_authority(root)` and `build_mapping_artifacts(root)` functions validate
inputs and return values without writing; the script only orchestrates output.
The report is generated from the same authority, not a second mapping registry.

CLTS-derived declarations retain CC BY 4.0 attribution and source references in
the source policy and packaged CLTS notices. IPAkit rules and native declarations
retain their repository license. This initial slice does not complete the wider
semantic correspondence audit or authorize additional native features.
