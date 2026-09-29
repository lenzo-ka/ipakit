# Reviewed CLTS correspondences

The `ipakit.clts_mapping` library provides a bounded, directional correspondence
authority for the reviewed plain-stop witnesses `p`, `b`, `t`, and `d`, and for the
seven CLTS consonant-release declarations, from CLTS to IPAkit. Its token rules
establish eligibility and profile-bound house projections in the declared direction
and context. The [public CLTS import](clts-import.md) consumes those projections,
retains the native source graph, and limits complete house Forms to the reviewed
plain-stop domain. Reverse conversion remains separate. Each inventory retains its
own semantics.

```python
from ipakit.clts import read_snapshot
from ipakit._clts_profile import core_bipa_spec
from ipakit.clts_mapping import read_authority

authority = read_authority()
result = authority.eligibility("p", read_snapshot(), profile=core_bipa_spec())
assert result["status"] == "eligible-witness"
assert result["target"] == "p"
assert result["import_ready"] is True
```

This works offline with shipped artifacts; it does not load pyclts. Eligibility
requires the complete source claim set, exact source spelling, and the reviewed
native structural context. Every extra claim participates in the eligibility check.
Native defaults absent from CLTS claims are recorded with their native provenance.
In the profile-bound call, resolved affricates carry the reviewed
`unasserted-house-juncture` refusal; other resolved tokens outside the four rules
carry `outside-reviewed-token-context`. Unresolved spellings are not attempted
and carry the reason `not-attempted`. The declaration-level release adjudications
do not make those tokens import-ready.
Exact source recovery is a separate operation from reverse phonetic conversion.

The authority binds the accepted CLTS policy, source input hashes, frozen core
identity, native declaration hash, effective native metric fingerprint, its own
contents, and the hand-reviewed basis of the source profile. The basis covers the
complete profile fingerprint material except the mapping identity, avoiding a
cycle while making `require_import_profile(...)` refuse a different profile or
mapping. The reader recomputes the manifest fingerprint from the shipped snapshot
rather than reading `manifest.json`; `require_import_profile(...)` verifies the
committed receipt when the profile is used. Changed populations or provider
bindings require reconciliation. These fingerprints detect changed inputs.
Authentication and phonetic equivalence require separate evidence. The `target`
field identifies the research witness; the reviewed projection record does not
itself construct either the source-profile graph or the house Form.

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
nasal, schwa-colored, sibilant, trilled and uvular release map to exact
`release` values under their stated conditions. The superscript phase marks
remain distinct from tied constituent sequences. Unproven entries remain
explicitly unresolved. Every reverse-direction entry remains unresolved.

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
