# External-source receipts

Generated external-source artifacts use the `ipakit-source-receipt` schema.
The schema data and validator live together in `ipakit._source_receipt`. Every
receipt names its schema and kind, finite domain, source policy, extractor,
derived artifacts, license and hashed notices, then fingerprints that complete
material. Unknown top-level fields and duplicate JSON keys are errors.

The common `source-policy` holds the source identity and revision in `source`,
all consumed input hashes in `inputs`, and optional credit and resolver records.
Each derived artifact has a path and SHA256, with an artifact identity and
schema where the format supplies them. A resolver record carries its name,
version, and complete implementation-input hash map. The extractor always has
an id and version. `license` carries the source license id and every shipped
notice hash.

CLTS, PHOIBLE and Panphon all ship this schema today.

- CLTS fills the common fields from `source.json`, including the pyclts resolver
  version and hashes. Its derived artifact is `core.json`, with both byte hash
  and snapshot identity. It also fills the house-declaration, adapter,
  projection-policy, and profile-family extensions. The adapter outcome table
  is receipt data used by the runtime adapter. Mapping identity and profile
  fingerprint are deliberately not receipt fields because either creates a
  fingerprint cycle. The projection policy's `unsupported: "error"` records
  the adapter's default action; callers may explicitly preserve unsupported
  occurrences as source material.
- PHOIBLE fills `source` and `inputs` in `data/phoible/manifest.json`, records
  the versioned deterministic-gzip extractor, lists every transported `.gz`
  file and copied upstream license as a derived artifact, and hashes every
  shipped notice and license. The former `data/phoible-policy.json` and the old
  `source-sha256`/`transport-sha256` manifest shape are gone; the receipt is the
  sole authority. PHOIBLE has no resolver or CLTS profile extensions.
- Panphon fills `source` and `inputs` in
  `data/feature-models/panphon-receipt.json`, identifies and versions the
  `panphon_geometry.py` extractor, hashes `panphon.xml` as its derived artifact,
  and hashes the shipped MIT license and notice. The XML root carries only a
  `source-receipt` pointer, not a second provenance record. Panphon has no
  resolver or CLTS profile extensions.
