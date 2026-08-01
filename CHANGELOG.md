# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- RELAX NG grammars for every XML document the repository ships, and `tests/test_schema.py` validating each against its own.
- `ipakit/data/supplement.rng`: the supplemental-inventory format as a grammar, so a supplement can be checked before it is loaded.
- Context-sensitive rewrite rules over forms, `A -> B / C _ D`, with `Query` and `Action` as separable halves — `docs/rules.md`.
- `ipakit.form`: `Form`, the unprojected read of a transcription; each narrower read is named and says what it drops — `docs/form.md`.
- Agreement variables, SPE's `α`: `n -> [place=α] / _ [place=α]` — `docs/rules.md`.
- Optional rules, `A ~> B`, and `variants()` answering with a `VariantSet` — `docs/calculus.md`.
- `VariantSet.complete`, `.truncations`, `.unexplored`: a capped enumeration says so in the returned object.
- Splitting the choices over ordered rules, as a technique with its limits — `docs/calculus.md`.
- Tone is a sequence of levels and `contour` is derived from it — `docs/tone.md`.
- The four undeclared IPA tone diacritics `᷆ ᷇ ᷈ ᷉` (U+1DC6–U+1DC9), with their X-SAMPA encodings.
- Prosodic tiers: `level` gains `phrase` and `utterance`, and `|`/`‖` declare which one they terminate.
- `<zeros>`: `∅` is a declared element class, outside the feature bag and outside the metric.
- A rule may write a zero (`z -> [zero]`) and may mark a context item optional (`(∅)`).
- `rules.surface()`, the final rewrite `[zero] -> ∅` that takes a derivation to a pronunciation; `keep_zeros` declines it.
- A rule may target a boundary: `∅ -> .` writes one, `. -> ∅` unwrites one, `. -> #` restates one.
- Prosody is writable from a rule: `[length=long]`, `[stress=primary]`, `[stress=∅]`, and literals naming prosody.
- `<notations>`, with `IPAFeatures.notations`/`notation_of` and `ipakit.extensions_in`/`is_pure_ipa` over it.
- `IPAFeatures.compose_unit`: a feature bundle to a composed spelling, for phones no inventory registers (`tʰ`, `ɪ̃`, `t̚`).
- Supplemental inventories: `load_ipa_features(supplements=[...])` merges extra symbols over `ipa.xml` — `docs/supplements.md`.
- `DistanceModel.derive` and `.save`: a supplemented inventory's own reference matrix, in the format `from_matrix_file` reads.
- `IPAFeatures.zeros`, `carries_no_segment`, `tie_bar`/`seq_tie`/`tie_bars`, `is_nucleus`, `declaring_mark`, `declared_symbols`.
- `Feature.sequence`, `steps()`, `sequenced()`, `over` and `move`.
- Five shipped rule sets: `american-english`, `french-liaison`, `german-final-devoicing`, `japanese-moraic`, `spanish-accented-english`.
- `ruleset(name)`, `shipped`, `available`; `rewrite` and `derive` accept a shipped set's name.
- `ipakit rules`: `apply`, `trace`, `recognize`, `units`, `list`, `variants`.
- `ipakit tract draw` and `ipakit tract heads`.
- `ipakit distance word --raw`, the raw feature-cost measure.
- The tract renderer ships in the package as `ipakit.tract_svg`, so it reaches an install.
- `Segment` and `Head` render as tract figures in a notebook, through `_repr_svg_`.
- `python -m ipakit`.
- `hierarchy()`, `hierarchy_text()`, `hierarchy_dot()` and `stress_markers()` at module level.
- `ipakit.units`, which is `ipakit.form.units`; `rule_units` is the same object under its older name.
- `Node.opened_by`/`closed_by`/`asserted` on `Form.tree()`, and `ipakit.form.edge_tier()`.
- `validate_ipa` gains `empty_constituent` and `no_segments`.
- A declared `natural-class` resolves as a query term: `[obstruent]`.
- `ipa.xml` carries the license it is offered under, and a test holds it to the repository `LICENSE`.
- `docs/tutorial.md`, generated from `docs/tutorial.src.md`; `make check` fails on a single byte.
- `docs/README.md`, `docs/calculus.md`, `docs/form.md`, `docs/rules.md`, `docs/tone.md`, `docs/design/samprosa.md`.
- `scripts/tutorial.py` and `scripts/docexamples.py` as `make check` gates.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, and the issue and pull-request templates.
- Structured segment API: `Segment`/`Constituent`/`Sense`/`Kind`, with `segment()`, `segments()` and `build_segment()` (#10).
- `find(ipa, query)`, natural-class search over a transcription; `to_ipa(units)`; `feature_values(unit)` (#22).
- `to_phone(bundle)` and `respell(phone, **changes)`: the feature level is writable, not only readable (#21).
- Structural distance (`ipakit.metric`), comparing units by aligning their constituent bundles (#13).
- `ipakit.closure.MetricClosure`, the shortest-path closure for callers that need the triangle inequality.
- A `channel` axis (`lateral` → `flat` → `grooved`), replacing the binary `lateral` and encoding sibilance (#17).
- Active articulator per phone, declared per place value and overridden per phone (#17).
- A shared reference frame for the ordinal scales (`axis` per feature) and normalized tract coordinates on phones (#17).
- `from_wild()` and `import_phoneset()`: explicit import of IPA written in other tie conventions (#11, #15).
- Registered phones `t͡ɬ`, `d͡ɮ`, `k͡p`, `ɡ͡b`, `ŋ͡m` (#7).
- Typed ties as house convention, carried in the data — `docs/ties.md` (#9, #14).
- Unicode canonicalization at ingest: precomposed and decomposed input parse identically, tokens emit NFC (#8).
- `DistanceModel.confusability`/`distance`/`nearest` fall back to feature-derived similarity for out-of-matrix phones (#8).
- `docs/distance.md`, the phonetic distance model and what its numbers mean (#17).
- `docs/reviewing.md`, how defects in this library are actually found.
- `docs/articulatory-data.md` and `scripts/articulatory.py`: the tract geometry measured against the X-Ray Microbeam database.
- `scripts/invariants.py`, one command for the properties the library holds; it exits non-zero, so it gates a release (#8, #17).
- `CHANGELOG.md` ships in the sdist.

### Removed

- `IPAFeatures.word_distance`'s `sub_cost` parameter; `_align` is the parameterized entry point.
- `ipakit.constants.TIE_BAR`, `SEQ_TIE` and `TIE_BARS`; the tie characters are read from `ipa.xml`.
- The `to_ipa` alias (use `from_cmu`) and `compose_single` (use `segment(s).scalar()`) (#20).
- `wiki`/`wiki_ref`/`wiki_refs` and `features_to_shorts`/`shorts_to_features` from the module level (#20).

### Changed

- Phonological corrections across the shipped rule sets; each file records its own choices.
- American English tapping asks for a following unstressed nucleus rather than a preceding stressed vowel.
- Nasal place assimilation is stated once over an agreement variable, which widens it to every declared place.
- The shipped English syllabic and lateral-release rules use classes where they used literals an earlier rule had bled.
- `french-liaison` states *e caduc* in two ordered rules, so the second sees the first choice made.
- Three shipped sets name `[obstruent]` instead of spelling the class out as a complement.
- The linking mark `‿` declares `level="word"`.
- `level` declares `mode="structural"`.
- The rule-name separator is `;`, since `|` is a legal context item.
- `Sense.glyph` is a method taking the features, not a property.
- `Action.becomes` is `dict[str, str | None] | str | None`.
- `form.units()` preserves the declared separating marks `‿`, `|` and `‖`.
- A boundary run is one boundary, and a form's own edge is part of any run it touches.
- `Derivation.start` is the form as the engine read it, so it is `steps[0].before` by construction.
- `rules._edge_level` calls `form.edge_tier()` instead of reading the top of the `level` ladder.
- `Site.left`/`right` report `None` for the virtual edge past the form, not `-1`.
- Every term of a feature query must resolve, in `phones_matching`, `find` and a bracketed rule pattern alike.
- An unregistered literal, a bare suprasegmental, a boundary target, `[voiced=∅]` and an undeclared feature key or value all raise.
- A lossy read reaches the CLI's exit status, on a status of its own distinct from an error.
- `ipakit rules trace --all` marks a declined optional rule `(not taken)`.
- `segment` names the `Segment` concept everywhere; `WordDistanceResult.distance` is `edit_cost` (#19).
- Soft reads move behind `from_wild`, out of the default parse path.
- `parse`/`tokenize`/`segmented`/`segments`/`segment` gain the `strict=` policy the converters carry.
- Diphthong canonical spellings use the under-tie (`a͜ɪ`, `e͜ɪ`, …), and the glyph is authoritative at every entry point.
- Combining values are spelled with `^`, not `+`: `features("w")["place"]` is `bilabial^velar`.
- Pre-glottalization `ˀ` and the schwa release `ᵊ` declare `release="glottal"` and `release="schwa"`.
- The tables that stated phonetic facts in Python are declared in `ipa.xml` and derived from it.
- Anchored dimensions (`place`, `backness`, `manner`, `height`) compute value distance from tract anchors rather than scale index.
- Clicks carry `airstream="velaric"` and their real oral manner, so `click` leaves the manner scale.
- A tie-bar composition no longer collapses to a place that is not an overlap of its parts.
- Tied inventory entries are constituent-derived; `ipa.xml` keeps only spelling, aliases and `href` for them.
- Alias spellings resolve token-locally at every entry point (#9).
- Phoneset conversions project the under-tie onto the over-tie at the boundary (#9).
- Structural features no longer default onto phone bundles (#9).
- Tie sense is one vowel test, and nucleus-hood one read, rather than a copy per caller.
- `Phoneset.from_file` drops silence by reading `manner="silence"` rather than by matching spellings.
- The mid-sagittal figures distinguish substantially more phones and rule-set outputs — `docs/tract-figures.md`.
- The airstream arrow is deliberately not drawn: `ipa.xml` declares no direction on an airstream value.
- `scripts/articulatory.py` reads `IPAKIT_XRMB_DIR`; no corpus path is baked in.
- `scripts/invariants.py` reads provenance and the zero through the library's own API rather than defining them.
- `is_pure_ipa`'s summary no longer invites the reading "is this valid IPA".
- The rule sets and `docs/` ship in the wheel and the sdist, and an unpacked sdist can run its own tests.

### Fixed

- A voiced phonation was read on a voiceless segment, and read out loud in `describe`.
- `compose_unit("s", voiced="+")` would have spelled a breathy-voiced segment.
- `᷅` U+1DC5 declared `contour="falling"` and rises; it is `tone="low>mid"`.
- A run of prosodic marks merged last-writer-wins, so only the final tone letter survived.
- The parser called the declared zero unknown, and said so by quietly shortening the string.
- `features()` returned `{}` for any base carrying a diacritic — `tʲ`, `ã`, `tʰ`, `eː`, `n̩`.
- `features()`, `compose()` and `Segment.scalar()` are one projection, where they were three that disagreed.
- `describe` reads everything a unit states, on both halves of the inventory.
- `compose_unit` no longer appends a mark for a value the base already carried.
- `compose_unit` refuses a composition that moves a dimension nobody asked for.
- The soft-reading `convert` subcommands dropped what they could not convert with no indication.
- `ipakit features` synthesized `class: composed` for any token that was not itself a registry key.
- A literal rewrite dropped the target's prosody, shortening every long segment it rewrote.
- A literal naming prosody could not match at all, since the left-hand side was compared against `Unit.core`.
- A declared ligature alias was refused as a literal on either side of the arrow.
- `Derivation.trace(all_steps=True)` put the rule names at two different columns.
- An insertion fired twice across a transparent syllable dot, and an insertion naming the dot could never fire.
- A rule naming `#` stopped the transparency skip, so a dot beside a word edge hid the edge.
- `_anchors` licensed the trailing gap of a boundary run only on the run's last mark.
- A form has one edge, not a run of them: `t -> ʔ / _ # # #` fired.
- `Unit.features` and `Unit.prosody` disagreed about the same unit; prosody has one home.
- `Form.rebuild` puts a boundary back as the unit it was, from `Boundary.features`.
- Vacuous tests in the rules suite are repaired rather than removed.
- `docs/rules.md` recommended `ipakit.add_ties()`, which ties every adjacent pair.
- The hardcoded-constant guard missed shapes of the mistake it was written against.
- Ligature aliases (`ʦ ʧ ʤ ʣ ʥ ʨ ƛ ˖ ˗`) resolve everywhere an IPA string is read.
- A stress mark binds the unit that follows it wherever it stands, and is refused on a tie composition.
- The data said every vowel was voiceless.
- R-coloring was spelled with two different features, so the diacritics and `ɚ`/`ɝ` disagreed.
- A secondary articulation was read off the glyph stack rather than off the assembled bundle.
- A tie bar written after a diacritic was dropped, in silence.
- The X-SAMPA round-trip guarantee in the README was not true, and symbols converted to the empty string.
- The derived confusion matrix is reproducible bit for bit; `bundle_distance` summed over an unordered set.
- Reads that answered where they should have failed now raise.
- `word_distance`/`word_similarity` silently dropped symbols the tokenizer could not convert.
- Phone feature bundles are read-only; a write through `get_phone(...).features` corrupted the inventory (#18).
- Precomposed characters (`ã`) were dropped at ingest; decomposed `ç` misparsed as bare `c` (#8).
- `docs/distance.md` states plainly that `distance` is not a metric.
