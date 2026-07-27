# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `Segment.disagreements()`: the features whose values differ across a unit's constituents — a diagnostic read (composition reports, never referees; `t͡ɮ` stays legal). Structural marks (the linking `‿`, breaks `|`/`‖`) now tokenize as their own boundary tokens instead of gluing onto the preceding segment, and are transparent to word-level distance (`word_distance("lez‿ami", "lezami") = 0`) (#14).
- Structural distance (`ipakit.metric`): constituent-bundle alignment with kind-driven ordering (double articulation unordered, phased units and sequences ordered), a binding-sense term (`D(u͡i, u͜i) = 1/3`), weighted secondary-articulation place components (`tʲ` strictly between `t` and `c`), nasality/laterality bridge features, and combined-place expansion for atomic `w`/`ɥ`. `distance`/`segment_distance`/`Segment.distance` all route through it; `Feature.value_distance` accepts value tuples. Distances shift: affricates now cluster with affricates rather than with their bare components; `confusion.json` regenerated (#13).
- `from_wild()`: explicit import of IPA written in other tie conventions — glyph-variant spellings of registered compounds canonicalize (`t͜s` → `t͡s`, `a͡ɪ` → `a͜ɪ`); unregistered uniform-glyph chains get the sense heuristic; mixed-glyph (house-authored) chains pass through (#11).
- Registered phones: the lateral affricates `t͡ɬ` (aliases `t͜ɬ`, NAPA `ƛ`) and `d͡ɮ`, and the labial-velar plosives/nasal `k͡p`, `ɡ͡b`, `ŋ͡m` (#7).
- Typed ties as house convention (see `docs/ties.md`): the over-tie fuses constituents into one timing slot, the under-tie binds a sequence into one unit, and the over-tie binds tighter in mixed chains (#9).
- Structured segment API: `Segment`/`Constituent`/`Sense`/`Kind`, `parse_segment`/`parse_segments`, `IPAFeatures.segment`/`segments`/`build_segment` — flat chain stored, grouping/kind/bag/scalar derived; versioned JSON round trip; sense-correct (documented-lossy) IPA emission (#10).
- Unicode canonicalization at ingest: precomposed and decomposed input parse identically; tokens emit in NFC (#8).
- Drift guard: registered tie-barred entries must match composition, with pinned exceptions (#8).
- `DistanceModel.confusability`/`distance`/`nearest` fall back to feature-derived similarity for out-of-matrix phones (#8).

### Changed
- House style is strict: diphthong canonical spellings flip to the under-tie (`a͜ɪ`, `e͜ɪ`, …), the glyph is authoritative at every entry point (no cross-glyph aliases; `t͜s` is a sequential chain, `a͡ɪ` a fused overlay), emission is faithful (`parse(emit(x)) = x`; the collision list is gone), and reverse phoneset conversions canonicalize through `from_wild` so registered compounds round-trip with correct sense (#11).
- The redundant `a͡ʊ̯` registration is dropped: composition resolves the narrow-transcription variant identically on the fly (#11).
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
