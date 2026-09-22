# Library/API/CLI capability contract

This table is the synchronization contract for the flat `ipakit` API and the
codec/profile entry points relevant to a terminal. Each capability is classified
as CLI-reachable or library-only. Library-only entries construct reusable
objects or require caller-supplied graph structure and linguistic choices.

| Capability | Public/API entry points | Decision |
|---|---|---|
| Version, data, and inventory construction | `__version__`, `DATA_DIR`, `DEFAULT_CMU_MAP`, `DEFAULT_IPA_FEATS`, `PHONEMAPS_DIR`, `SUPPLEMENTS_DIR`, `IPAFeatures`, `CMUMapper`, `load_ipa_features`, `available_supplements`, `supplement_path` | **CLI-reachable:** `--ipa-xml` and `--cmu-xml` select the inventory `load_ipa_features` reads, and `analyze`, `query`, and `info` are its terminal-facing reports. The constants and constructors beside it are Python configuration objects with no separate command. |
| Module implementation support imports | `annotations`, `Any`, `Iterable`, `Path`, `Sequence` | **Library-only by decision:** these are non-underscored bindings used by the flat module's implementation and type annotations, not ipakit capabilities suitable for CLI commands. |
| Canonical forms, graph construction, containment, serialization, and DOT rendering | `Form`, `FormBuilder`, `FormProjectionError`, `Attribute`, `Boundary`, `Interval`, `Node`, `Timing`, `Unit`, `levels`, `tier_names`, `units`, `read`, `read_json`, `read_graph_json`, `write_graph_json`, `to_dot`, `Form.graph`, `Form.at`, `Form.to_dot` | **CLI-reachable:** `convert to-json [--pretty]`, `convert from-json`, `graph-json`, `rules units`, and `tiergraph IPA` / `tiergraph --from-json PATH`; graph editing is available through the library constructors. |
| Segments and normalization | `Constituent`, `Kind`, `Segment`, `Sense`, `tokenize`, `segmented`, `segments`, `segment`, `to_ipa`, `normalize`, `from_wild`, `normalize_lookalikes`, `add_ties` | **CLI-reachable:** `convert tokenize`, `normalize`, and `add-ties`; `features` intentionally offers interactive lookalike reading. |
| Feature lookup, querying, and respelling | `Feature`, `FeatureNarrowingWarning`, `FeatureQuery`, `Phone`, `PhoneMapping`, `Phoneset`, `features`, `feature_values`, `features_from_cmu`, `features_from_xsampa`, `feature_bundles`, `phones_matching`, `to_phone`, `respell`, `find`, `features_to_shorts`, `shorts_to_features`, `import_phoneset` | **CLI-reachable:** `features`; `query match`, `list`, `features`, `classes`, and `shorts` provide the terminal views and searches. The warning type is the Python control surface for narrowing reads. |
| Description, references, validation, and hierarchy | `wiki`, `wiki_ref`, `wiki_refs`, `describe`, `natural_class`, `minimal_pairs`, `nearest_phones`, `hierarchy`, `hierarchy_text`, `hierarchy_dot`, `stress_markers`, `validate_ipa`, `is_valid_ipa`, `extensions_in`, `is_pure_ipa` | **CLI-reachable:** `describe`; `analysis`; `hierarchy`; `info stress`; and `analyze` provide the useful terminal reports. |
| Raw distance and inventory-relative percentile positions | `Alignment`, `AlignmentStep`, `CostSchedule`, `Correspondence`, `Coverage`, `PhoneCost`, `PhonePosition`, `UnusableReferenceWarning`, `PhonesetMapping`, `PhonesetComparison`, `PronunciationMatch`, `ScoringParameters`, `SequenceMatch`, `TranscriptionDistanceResult`, `DistanceModel`, `distance`, `segment_distance`, `pairwise_distances`, `transcription_distance`, `directional_transcription_distance`, `transcription_similarity`, `explain_transcription_distance`, `nearest_pronunciation`, `rank_pronunciations`, `sequence_distance`, `sequence_similarity`, `rank_sequences`, `distance_position`, `similarity_position`, `distance_model`, `phoneset_mapping`, `phoneset_comparison` | **CLI-reachable:** `distance pair`, `segment`, `matrix`, `positions`, `transcription`, `nearest`, `seq`, `map`, and `compare`, including alignment/explanation output. `positions` emits `similarity_position` and `distance_position`; `map` relates two phonesets in one selected way; `compare` reports the ordered sets, nearest mappings both ways, similarity matrix, source terms, directional means and worst cases, asymmetry, and caller-chosen `--coverage-at` thresholds. |
| Inventory lookup and construction | `Inventory`, `Style`, `inventories`, `inventory`, `inventory_from_dictionary` | **CLI-reachable:** `inventory list`, `inventory show`, and `inventory from-dict`, including `min_entries` as `--min-entries` and `refuse_unreadable` as `--refuse-unreadable`. |

| Applicability-scoped phone, segment, and neighbor distance | `distance`, `segment_distance`, `nearest_phones`, `IPAFeatures.nearest_phones`, `Segment.distance` with `applicable_only=True` | **CLI-reachable:** `distance pair --applicable-only` and `distance segment --applicable-only`; neighbor ranking remains a library read over the selected denominator. |
| Applicability-scoped matrices and inventory-relative percentile positions | `pairwise_distances`, `distance_position`, `similarity_position`, `distance_model`, `DistanceModel.derive` with `applicable_only=True` | **CLI-reachable:** `distance matrix --applicable-only` and `distance positions --applicable-only`. |
| Applicability-scoped transcription distance | `transcription_distance`, `directional_transcription_distance`, `transcription_similarity`, `explain_transcription_distance`, `nearest_pronunciation`, `rank_pronunciations` with `applicable_only=True` | **CLI-reachable:** `distance transcription --applicable-only`, `distance directional --applicable-only`, and `distance nearest --applicable-only`, including raw and explanation output. |
| Applicability-scoped sequence distance | `sequence_distance`, `sequence_similarity`, `rank_sequences` with `applicable_only=True` | **CLI-reachable:** `distance seq --applicable-only`; ranking stays the library composition over the same scoped read. |
| Applicability-scoped phoneset distance | `phoneset_mapping`, `phoneset_comparison` with `applicable_only=True` | **CLI-reachable:** `distance map --applicable-only` and `distance compare --applicable-only`. |
| Provenanced retained-form disagreement | `ProvenancedForm`, `DisagreementSpread`, `FormComparison`, `AgreementPosition`, `DisagreementPosition`, `DisagreementKind` | **Library-only by decision:** these are immutable composition and query objects over two or more already-built Forms. Their complete result is structured JSON, while choosing corpus roles and entry matching is source-specific and cannot be inferred by a generic terminal command. |
| CMU ARPABET stable conversion | `to_cmu`, `from_cmu`, `features_from_cmu` | **CLI-reachable:** `convert to-cmu` and `from-cmu` use the stable public mapper. |
| CMU dialect graph projection | `_cmu_graph.read`, `_cmu_graph.render`, `_cmu_graph.projection_losses`, `BASE_CMUDICT`, `POCKETSPHINX` | **Library-only by decision:** declared loss objects and the ASR boundary profile require a graph-aware caller; silently selecting a lossy dialect at the terminal would obscure stress loss. |
| X-SAMPA, TIMIT, Kirshenbaum, phonemaps, and named inventory styles | `to_xsampa`, `from_xsampa`, `to_timit`, `from_timit`, `to_kirshenbaum`, `from_kirshenbaum`, `to_phonemap`, `from_phonemap`, `features_from_xsampa`, `Inventory`, `Style`, `inventory` | **CLI-reachable:** the corresponding `convert to-*` and `from-*` commands cover the established notation APIs; `convert phoneset --from-style SOURCE --to-style TARGET` performs strict all-or-nothing transcoding through house IPA for any named inventory style. |
| Rewrite calculus | `Action`, `Derivation`, `Edit`, `Invertibility`, `InvertibilityReport`, `Matchable`, `Query`, `RebaseError`, `Rule`, `RuleError`, `RuleSet`, `Site`, `Step`, `Truncation`, `Variant`, `VariantSet`, `DEFAULT_LIMIT`, `available`, `rebase`, `shipped`, `rule`, `ruleset`, `rewrite`, `derive`, `variants`, `rules` | **CLI-reachable:** `rules apply`, `variants`, `trace`, `recognize`, `units`, `list`, and `invertibility`. |
| Language-relative syllabification | `Conflict`, `Language`, `Syllabification`, `Syllabifier`, `language`, `languages`, `syllabifier`, `syllabify` | **CLI-reachable:** `syllabify IPA --language NAME` and `syllabify --languages`, in text or JSON. JSON is the full result -- intervals, unsyllabified residue, and conflicts -- because the text view flattens what this mechanism exists to preserve. `syllabifier` stays a Python constructor: it returns a reusable callable, and strictness is a corpus-level decision. |
| Praat TextGrid interchange | `ipakit.textgrid.write`, `ipakit.textgrid.read`, `ipakit.textgrid.profiles`, `ipakit.textgrid.profile` | **CLI-reachable:** `ipakit textgrid write` and `ipakit textgrid read` expose named profiles, named inventory styles, and explicit tier-role maps. |
| Corpus storage, provenance, splits, experiments, CMUdict ingestion, and structural query DSL | `corpus`, `Corpus`, `FormProvenance`, `Producer`, `Match`, `CorpusMatch`, `Experiment`, `ExperimentReport`, `Residue`, `Movement`, `parse_query`, `query_rule` (and the public `ipakit.corpus` operations `create`, `open`, `validate`, `find`, `query`, `derives`, `query_derivations`, `ingest_cmudict`, `CMUdictIngestReport`, `CMUdictRefusal`) | **CLI-reachable:** `query DSL [IPA...]` is the form-level door; `corpus init`, `add`, `ingest-cmudict`, `validate`, `ids`, `show`, `query`, and the retained pairwise `derives` expose collection operations. `rules derives` runs and serializes an `Experiment`; typed provenance and split mutation remain Python composition primitives because neither has a terminal result without a producer or experiment. |
| Arbitrary rewrite/alignment graph bridge | `_rewrite_graph.project_derivation`, `_rewrite_graph.derive_morae` | **Library-only by decision:** arbitrary projection requires structured derivations and downstream graph use; only the bounded curated mora view is terminal-facing. |
| Curated Japanese loanword fixtures | `morae`, `to_katakana`; codec/profile: `_rewrite_graph.japanese_moraic_fixtures`, `_rewrite_graph.japanese_moraic_fixture`, `_katakana_codec.render` | **CLI-reachable:** `rules morae IPA` and `convert to-katakana IPA`. Both accept only the curated fixture sources and refuse unmapped input; neither simulates a Japanese accent. |
| Pinyin tone placement | codec/profile: `_pinyin_graph`, `_codecs.render_pinyin` | **Library-only by decision:** the renderer needs a syllable/tone graph, while the CLI has no Pinyin graph ingestion surface. A raw-string command would bypass semantic tone attachment. |
| Declared external-representation bridges | `ipakit.bridges.Bridge`, `VocabularyBridge`, `NotationBridge`, `ProviderBridge`, `GeneratorDoor`, fidelity and projection reports; instances `bridges.mfa.MFA`, `bridges.kana.KANA`, `bridges.pinyin.PINYIN` | **Library-only by decision:** vocabulary reads return structured Forms with grouping tiers and dictionary entries are composable Python values. `MFA.map_to_mfa` projects reachable house forms with positioned, serializable loss reports and refuses undeclared residue. The corpus/lexicon CLI door is a later lane. |
| Gesture backend | codec/profile: `_gesture_graph`, `_gesture_backend.ArticulatoryFrame`, `_gesture_backend.oral_tract_frames` | **Library-only by decision:** callers must supply graph timing and choose a fallback level; `tract draw` remains the plausible terminal visualization rather than inventing a frame interchange format. |
| Rendering profiles and delivery/signature codecs | codec/profile: `_codecs.RenderLane`, `_codecs.RenderProfile`, `_codecs.DeliveryProfile`, `_codecs.DeliveryRenderings`, `_codecs.DeliverySelectionError`, `_codecs.render_graph`, `_codecs.ipa_profile`, `_codecs.render_delivery`, `_codecs.SignatureEdit`, `_codecs.apply_signature` | **Library-only by decision:** these operate on caller-assembled graphs and selections; the CLI has no lossless graph-authoring grammar for them. |
| Tract rendering, trajectories, tracks, and tutorial | `tract.Trajectory`, `tract.trajectory`, `tract.trajectory_from_track`, `tract_svg`, `notebook` | **CLI-reachable:** `notebook` writes the tutorial, and `tract draw` and `tract heads` render. Trajectories and their JSON tracks stay Python interchange objects: their timed Form construction has no CLI ingestion surface. |

Finite-model module APIs have a separate measured witness in
`tests/test_cli_model.py`: `model list`, `inspect` and `respell` reach the shipped
resource accessor, ternary declaration codec and `FiniteModel.respell` directly.
They require explicit selection and retain complete realization candidates.
`tests/test_cli_model_query.py` checks `model query` delegation through
`FiniteInventory.phones_matching` to `FiniteModel.query`, including typed
refusals and complete declaration-order enumeration.
`tests/test_cli_model_rules.py` additionally spies `Rule.recognize_tokens` and
`RuleSet.derive_tokens` through finite `rules recognize/apply/trace`; installed
entry-point tests exercise both named and supplied declarations. These commands
use explicit model selection and exact JSON token arrays; see the
[finite CLI contract](rules.md#explicit-finite-rules-on-the-command-line).
Generic typed schema/AST and transform construction remain library composition
interfaces. Native wrappers retain their existing signatures, and the
flat-export reachability test covers the flat API.

`distance metrics` lists named registrations; `distance across` delegates to
`DistanceRegistry.compare_corpus`. Repeated `--metric` names select arms and
standalone `all` expands the registry. `--all-pairs` independently expands
ordered input pairs. Supplied ternary declarations use `--metric-declaration
NAME=PATH`; custom factory construction remains a library interface.
`tests/test_cli_distance_registry.py` checks discovery, exact-token delegation
and selector refusals. A completed report retains unavailable metrics and
refused comparisons with their statuses; status0 means report production
succeeded. See [inventory operations](inventory-operations.md#named-metric-selection).

`ipakit.model_graph.GraphBinding` is library-only: callers supply a native graph,
qualified value relations, source references and clock binding. Derivation
and bound-operation restoration operate through this Python interface; CLI
graph input and general house `Form` admission remain separate work.
See [graph decoration](rules.md#decorating-an-existing-graph).

The CLI exit contract applies to every reachable row: 0 for success, 1 for a
command error, 2 for usage, and 3 when a soft read produced output after losing
input (`--lax` accepts that partial read as status 0). Converters aggregate
loss diagnostics; `--strict` fails and names every unconvertible symbol.
