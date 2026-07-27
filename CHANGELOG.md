# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Registered phones: the lateral affricates `t͡ɬ` (aliases `t͜ɬ`, NAPA `ƛ`) and `d͡ɮ`, and the labial-velar plosives/nasal `k͡p`, `ɡ͡b`, `ŋ͡m` (#7).
- Typed ties as house convention (see `docs/ties.md`): the over-tie fuses constituents into one timing slot, the under-tie binds a sequence into one unit, and the over-tie binds tighter in mixed chains (#9).
- Structured segment API: `Segment`/`Constituent`/`Sense`/`Kind`, `parse_segment`/`parse_segments`, `IPAFeatures.segment`/`segments`/`build_segment` — flat chain stored, grouping/kind/bag/scalar derived; versioned JSON round trip; sense-correct (documented-lossy) IPA emission (#10).
- Unicode canonicalization at ingest: precomposed and decomposed input parse identically; tokens emit in NFC (#8).
- Drift guard: registered tie-barred entries must match composition, with pinned exceptions (#8).
- `DistanceModel.confusability`/`distance`/`nearest` fall back to feature-derived similarity for out-of-matrix phones (#8).

### Changed
- Tied inventory entries are constituent-derived: `ipa.xml` keeps only spelling/aliases/href for them, the loader derives their features under each entry's sense, and `IPAFeatures.derived_phones` lists them — registered and computed features cannot drift (#10).
- Alias spellings resolve token-locally at every entry point; `get_features`/`get_phone`/`in` now resolve aliases (previously returned empty for e.g. `t͜s`) (#9).
- Unregistered under-tie chains keep their tie through tokenization and project their first element (previously rewritten to the over-tie and merged) (#9).
- Phoneset conversions (X-SAMPA, CMU, TIMIT, Kirshenbaum) project the under-tie onto the over-tie at the boundary: unit-hood survives, tie sense does not; round trips return canonical over-tie spellings (#9).
- `normalize_ipa` inserts the tie by sense: adjacent vowels bind sequentially, anything else fuses (#9).
- The spacing undertie `‿` is the IPA linking mark (feature renamed from `liaison`); tie bars carry their sense in the data (`tie=simultaneous`/`sequential`) (#9).
- Structural features no longer default onto phone bundles; `confusion.json` regenerated (distances shift in the third decimal) (#9).
- `_COARTICULATED_PLACES` trimmed to the two true double articulations (#7).
- `MAX_MATCH_LEN` raised from 6 to 11 so longer tie chains tokenize as one unit (#10).

### Fixed
- Precomposed characters (`ã`) were silently dropped at ingest; decomposed `ç` misparsed as bare `c` (#8).
- The under-tie was dropped entirely at X-SAMPA conversion, degrading registered units to clusters (#9).
- `validate_ipa` treats both ties as ties; a lone under-tie is malformed, not standalone (#9).
