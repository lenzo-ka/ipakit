# External-source receipts

Generated external-source artifacts use the `ipakit-source-receipt` schema.
The schema data and validator live together in `ipakit._source_receipt`. Every
receipt names its schema and kind, finite domain, source policy, extractor,
derived artifacts, license and hashed notices, then fingerprints that complete
material. Unknown top-level fields and duplicate JSON keys are errors.

The common `source-policy` holds the source identity in `source`, all consumed
input hashes in `inputs`, and optional credit, resolver and revision records. A
revision is either a commit or source hash and may also name a tag. An optional
`build` record names the tool and tool version, positive table format and RFC
3339 UTC build time. Existing receipts without `revision` and `build` remain
valid.
Each derived artifact has a path and SHA256, with an artifact identity and
schema where the format supplies them. A resolver record carries its name,
version, and complete implementation-input hash map. The extractor always has
an id and version. `license` carries the source license id and every shipped
notice hash.

CLTS, PHOIBLE and Panphon all ship this schema today. Managed eSpeak builds use
the same schema in the user's cache, but their receipts and source-derived
tables do not ship in IPAkit.

- CLTS fills the common fields from `source.json`, including the pyclts resolver
  version and hashes. Its derived artifact is `core.json`, with both byte hash
  and snapshot identity. It also fills the house-declaration, adapter,
  projection-policy, and profile-family extensions. The adapter outcome table
  is receipt data used by the runtime adapter. Mapping identity and profile
  fingerprint are deliberately not receipt fields because either creates a
  fingerprint cycle. The projection policy's `unsupported: "error"` records
  the adapter's default action; callers may explicitly preserve unsupported
  occurrences as source material. Its `explicit-only` name likewise records
  the default projection; the opt-in `house-convention-v1` assumption is
  recorded per affected occurrence rather than changing the source receipt.
- PHOIBLE fills `source` and `inputs` in `data/phoible/manifest.json`, records
  the versioned deterministic-gzip extractor, and lists the transported main
  CSV, three InventoryID mapping tables, reference bibliography and copied
  upstream data license as derived artifacts. It hashes every shipped notice
  and license. The former
  `data/phoible-policy.json` and the old
  `source-sha256`/`transport-sha256` manifest shape are gone; the receipt is the
  sole authority. PHOIBLE has no resolver or CLTS profile extensions.
- Panphon fills `source` and `inputs` in
  `data/feature-models/panphon-receipt.json`, identifies and versions the
  `panphon_geometry.py` extractor, hashes `panphon.xml` as its derived artifact,
  and hashes the shipped MIT license and notice. The XML root carries only a
  `source-receipt` pointer, not a second provenance record. Panphon has no
  resolver or CLTS profile extensions.

An eSpeak managed-build receipt records the accepted tag and commit or source
hash, every consumed `phsource` input, the extractor and table format, the
build time, one hash per generated language declaration and the hash of the
source notice. It records no local source or cache path. The receipt fingerprint
covers the build time and therefore changes across rebuilds; each artifact hash
is the reproducible identity for byte-identical output. Runtime reads validate
the receipt and the one declaration being used. See
[user-supplied sources](user-sources.md) for the installed workflow and cache
layout.

## License classes and the wheel guard

`tests/license-classes.json` maps every license id reached from package data to
its SPDX id and shipping class. A receipt's `license.id` is that SPDX id (or a
`LicenseRef-...` id) and is the register key. The supported classes are
`shippable`, `shippable-share-alike`, `derived-shippable`, and `internal-only`;
a derived-shippable entry must cite its permitting term and name the permitted
artifacts. Unlisted `LicenseRef-LDC-*` ids default to internal-only. Files whose
shipped expression is IPAkit's own use the reviewed `house` list with a short
reason instead of pretending to have an external source.

The class deliberately stays outside the receipt. It is release policy rather
than source identity, and adding it to a receipt would change that receipt's
fingerprint and any downstream identity bound to it. The wheel guard in
`tests/test_license_classes.py` therefore joins the two at verification time.
Every non-Python member under `ipakit/` must resolve by exactly one route: an
XML root license, an XML `source-receipt` pointer, receipt/artifact/notice
membership, or the house list. Unknown and multiply classified files fail, as
do internal-only sources, unscoped derived artifacts, and dead register rows.
