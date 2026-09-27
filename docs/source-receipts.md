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

CLTS writes this schema today. PHOIBLE and Panphon still ship their earlier
receipt shapes; the fills below say how each maps onto the schema.

- CLTS fills the common fields from `source.json`, including the pyclts resolver
  version and hashes. Its derived artifact is `core.json`, with both byte hash
  and snapshot identity. It also fills the house-declaration, adapter,
  projection-policy, and profile-family extensions. The adapter outcome table
  is receipt data used by the runtime adapter. Mapping identity and profile
  fingerprint are deliberately not receipt fields because either creates a
  fingerprint cycle.
- PHOIBLE will fill `source` and `inputs` from its policy and current manifest,
  record the versioned gzip extractor, list each transported `.gz` file and
  shipped license as a derived artifact, and hash its MIT and GPL notices. It
  has no resolver or CLTS profile extensions.
- Panphon will fill `source` from the current XML root metadata, `inputs` from
  the `ipa_all.csv` and `feature_weights.csv` hashes, identify and version the
  `panphon_geometry.py` extractor, hash `panphon.xml` as its derived artifact,
  and hash the shipped MIT license and notice. It has no resolver or CLTS
  profile extensions.
