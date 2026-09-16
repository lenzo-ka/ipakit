# Reviewed CLTS correspondences

The `ipakit.clts_mapping` library provides a bounded, directional correspondence
authority for the exact plain-stop witnesses `p`, `b`, `t`, and `d`, and for the
seven CLTS consonant-release declarations, from CLTS to IPAkit. Its token rules
establish eligibility in the declared direction and context.
Reverse conversion and TierGraph/Form import require separate reviewed bindings.
Each inventory retains its own semantics.

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
native structural context. Every extra claim participates in the eligibility check.
Native defaults absent from CLTS claims are recorded with their native provenance.
Other tokens remain unresolved, including affricates, approach/release token
forms, vowels, and tone. The declaration-level release adjudications do not make
those tokens import-ready. Exact source recovery is a separate operation from
reverse phonetic conversion.

The authority binds the accepted CLTS policy, source input hashes, frozen core
identity, native declaration hash, effective native metric fingerprint, and its
own contents. Changed populations or provider bindings require reconciliation.
These fingerprints detect changed inputs. Authentication and phonetic equivalence
require separate evidence. `require_import_profile(...)` currently refuses every
request: final structural compatibility awaits the reviewed source-profile
binding. The `target` field identifies the research witness; import remains pending.

## Declarations, rules, and token eligibility

The [generated gap report](clts-gaps.md) accounts for every master declaration
and native declaration, using the same [declaration audit](clts-audit.md) parser
with `include_catalog=False`. It contains no catalog observations, witness IDs,
counts or catalog-only domains. The default full audit remains an explicitly
external-checkout research operation; its catalog derivative is not shipped or
cleared by the core-data notice. The
[mapping notice](../ipakit/data/clts/MAPPING-NOTICE.txt) states the narrower
artifact's sources, transformations and attribution.
A conditional-witness rule applies only in its stated complete-token context.
The release rows are narrower declaration correspondences: unreleased, lateral,
nasal and schwa-colored release map to existing `release` values, while sibilant,
trilled and uvular release name constituent-sequence forms. A segmental release
is a constituent; a manner or phonation quality can remain a `release` value.
No new value is introduced to flatten a segment into that feature. Unproven
entries remain explicitly unresolved. Every reverse-direction entry remains
unresolved.

The reviewed authored rules live in
[semantic-rules.json](../ipakit/data/clts/semantic-rules.json). The generated
[semantic-mapping.json](../ipakit/data/clts/semantic-mapping.json) holds receipts,
dispositions and constructive native witnesses. The historical `interop.py`
correspondence dictionary supplies diagnostic candidates separately from the
reviewed authority. Expressivity assessments require checking native constructions:
native nasal approach already exists, ties can lose information in CLTS, and
tone requires a caller-supplied host profile.

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
The report is generated directly from that authority.

CLTS-derived declarations retain CC BY 4.0 attribution and source references in
the source policy and packaged CLTS notices. IPAkit rules and native declarations
retain their repository license. The wider semantic correspondence audit and
proposals for additional native features retain their own review requirements.
