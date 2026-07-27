# Tie conventions

ipakit assigns the two IPA tie glyphs distinct senses. Standard IPA treats them as typographic variants (the under-tie exists largely to avoid collisions with marks above); ipakit's assignment is a house convention, chosen so that a transcription's structure can be decoded from its glyphs alone.

## The two ties

| glyph | codepoint | sense | meaning |
|---|---|---|---|
| `◌͡◌` over-tie | U+0361 | **simultaneous** | fuses constituents into **one timing slot** — internal phases allowed (affricates `t͡s`, prenasalized stops `n͡d`) or fully overlapped (double articulations `k͡p`) |
| `◌͜◌` under-tie | U+035C | **sequential** | binds **multiple timing slots into one unit** — a trajectory (diphthongs `u͜i`, moraic chains `a͜ɪ͜ə`) |

A tie's *presence* is contrastive and is never added or removed by normalization: `t͡s` is one segment, `ts` is a two-segment cluster — different objects, and no alias equates them.

The spacing undertie `‿` (U+203F) is a different symbol entirely: the IPA **linking** mark (absence of a break) between words — French liaison is one use. It is a separator-level mark, not a tie: it tokenizes as its own boundary token (`lez‿ami` → `l e z ‿ a m i`) so marked text round-trips faithfully, never glues onto a segment, never enters one, and is **transparent to distance** — `word_distance("lez‿ami", "lezami") = 0`; a boundary relation costs no alignment. (Its eventual structural home is a typed word-tier juncture, when a Word representation exists.)

## Precedence

The over-tie binds tighter. A mixed chain decodes without brackets: `t͡s͜a` is the fused unit `t͡s` sequentially bound to `a` — one token, a CV-mora-like unit. A sequential tie always operates on the maximal fused unit on each side.

Both ties stacked on one juncture assert contradictory timing; on ingest the pair collapses to the over-tie (simultaneous precedence). It is never emitted.

## The glyph is authoritative; wild text imports explicitly

House style is the only default semantics: canonical spellings are sense-correct (affricates and double articulations over-tie — `t͡s`, `k͡p`; diphthongs under-tie — `e͜ɪ`, `a͜ɪ`), and every entry point reads the glyph as the sense. `t͜s` is a sequential chain, not a spelling of the affricate; `a͡ɪ` is a fused vowel overlay, not the diphthong. Only unambiguous single-character ligatures (`ʦ`, `ʧ`, NAPA `ƛ`) are aliases.

Text from the wild — where the two glyphs are typographic free variants carrying no sense — is imported **explicitly** with `ipakit.from_wild(text)` (or `IPAFeatures.from_wild`); phonesets likewise with `ipakit.import_phoneset(phoneset)`, and `distance_model(phoneset)` warns — never silently drops — when members are spelled in another tie convention: each uniform-glyph tied chain is rewritten to house style, preferring the spelling that names a registered compound (`t͜s` → `t͡s`, `a͡ɪ` → `a͜ɪ`) and falling back to the sense heuristic for unregistered chains (all-vocalic → sequential, else simultaneous). Chains already mixing both glyphs are house-authored and pass through untouched. Because import is explicit, default parsing is faithful: `parse(emit(x)) = x` structurally for every expressible unit — there is no collision list and no lossy emission.

## Registered compounds are derived, not hand-encoded

Tied entries in `ipa.xml` carry only their spelling, aliases, and reference link; their **features are derived at load** by the same composer that serves unregistered chains, under each entry's sense (affricates via the simultaneous merge, diphthongs via the sequential first-element projection). Registration is therefore a cache of composition by construction — registered and computed values cannot drift, and `IPAFeatures.derived_phones` lists the entries this applies to. Every tied entry is derived — composition resolves diacritic-bearing parts (`ʊ̯` = base + non-syllabic modifier) as constituents.

## Composition of unregistered sequences

An unregistered tie-joined sequence of known phones still resolves (`registered wins, composition is the long-tail fallback`):

- **Over-tie (simultaneous)**: features merge left to right; differing manners collapse to `affricate` (`q͡χ` → uvular affricate); same-manner pairs with a dedicated combined place get it (`ɡ͡b`-style → `labial-velar`).
- **Under-tie (sequential)**: the flat feature projection is the **first element** (`u͜i` → the features of `u`) — the same encoding the registered diphthongs use. The remaining constituents stay recoverable from the token itself.
- **Mixed chains**: the first top-level part's features (`t͡s͜a` → the affricate's features).

The flat projection is deliberately a summary, not the whole story. The structured reads live on `Segment` (`ipakit.segment` / `ipakit.segments`, or the same names on `IPAFeatures`):

- `Segment` stores the flat chain — `constituents` (base + modifier stack) joined by typed `junctures` — plus unit-level `prosody` (stress, length, tone). Everything else is derived: `children` (the grouping: sequential runs, then phase blocks, then constituents), `kind` (affricate, prenasalized, pre-stopped, lateral-release, click-accompaniment, double-articulation, overlay, diphthong, chain, atomic), `sense`, `left`/`right` (edge children) with `left_features()`/`right_features()`/`features_at(i)` (the edge feature reads — approach a composed unit from either side, e.g. `segment("t͡s͜a").left_features()` is the affricate's read), `bag()` (per-feature value tuples in constituent order — `u͜i` carries `backness=('back', 'front')`), and `scalar()` (the same flat projection `get_features` gives).
- Modifiers contribute by mode: overriding marks replace their base's value (the devoicing ring makes `d̥` voiceless, never both-voiced), additive and secondary marks add only what the base doesn't state, release marks stay phase properties, and prosodic marks live on the unit, outside the feature bag.
- `to_json()`/`from_json()` carry the junctures explicitly and are the round-trip-guaranteed serialization. `to_ipa()` emits sense-correct glyphs and is lossy exactly on the legacy alias spellings, which return canonical: `segment("ʧa")` re-emits as `t͡ʃa`. Sense itself survives, because the glyph is authoritative — `build_segment(["a", "ɪ"], Sense.FUSE)` emits `a͡ɪ` and re-ingests as a fused double articulation, distinct from the registered sequential diphthong `a͜ɪ`. Intent that must survive a string round trip verbatim, aliases included, needs the JSON form.
- `build_segment` is the intent channel: it constructs any combination directly, bypassing string-alias collisions.
- The way back out is `ipakit.to_ipa(units)`, the inverse of `segments` — a join of parts, and no stronger than the `to_ipa()` above: alias spellings return canonical, and marks that belong to no unit (breaks, the linking `‿`) are carried by no Segment and cannot be restored. `ipakit.find(ipa, query)` searches a transcription for a feature pattern in the same query language `phones_matching` runs over the inventory, returning `(index, Segment)` pairs indexed against `segments`. `ipakit.feature_values(unit)` reaches `bag()` from the flat string API: the multi-valued companion of the scalar `features()`.

## Normalizing tieless input

`normalize` treats whitespace-separated groups as asserted units and inserts ties by a documented heuristic: adjacent vowels bind sequentially (`"eɪ"` → `e͜ɪ`), anything else fuses (`"ts"` → `t͡s`). An explicitly written tie always wins. The heuristic output round-trips: `e͜ɪ` resolves to the registered `e͡ɪ` through its alias.

## Agreement is reported, never refereed

Composition is intent-driven: a voicing-disagreeing tie like `t͡ɮ` is a legitimate object, and the library does not judge well-formedness. The diagnostic read is `Segment.disagreements()` — the features whose values differ across the unit's constituents, straight from the union bag: `t͡ɮ` reports `voiced=('-','+')`; a double articulation naturally "disagrees" in place; an atomic unit reports nothing.

## Distance is structural

*Summary; [docs/distance.md](distance.md) is the full account.*

`distance` (and everything built on it: `segment_distance`, the confusion matrix, `DistanceModel`) computes over the structure, not a flattened bag (`ipakit/metric.py`):

- **Constituents compare as whole bundles** — `ɡ͡p` and `k͡b` have identical per-feature value sets but stay apart, because which constituent is voiced matters.
- **Alignment mode follows the kind**: double articulation is unordered notation (`k͡p` ≈ `p͡k`, `u͡i` ≈ `i͡u`); phased units and sequences are ordered (`n͡d` ≠ `d͡n`, trajectories keep direction). N-ary fusions align their phase blocks in order, unordered within (`ŋ͡m͡ɡ͡b` ≈ `m͡ŋ͡b͡ɡ` ≠ `ɡ͡b͡ŋ͡m`).
- **Sharing an articulation is half the distance of not sharing it**: `D(ɡ, ɡ͡b) = d(ɡ,b)/2`, symmetric between the sharers.
- **The binding sense is one term**: `D(u͡i, u͜i) = 1/3` — same constituents, different timing claim.
- **Secondary articulations are weighted place components** (σ = 0.5): `tʲ` sits strictly between `t` and `c`.
- **Bridge features** unify one dimension spelled different ways: `ã` (nasalized) is nearer `n` (nasal manner) than plain `a` is; `tˡ` (lateral release) nearer `l` than `t` is.
- **Anchored dimensions measure in tract space, not by label count**: `place`, `backness`, `manner` and `height` compute value distance from their physical anchors, so the lips-to-teeth move is genuinely smaller than the velum-to-uvula move though both are "one label" apart, and place and backness stay commensurable (two views of one arc). This removes a real artifact — with index distance, one step costs 1/(n−1), so *refining* a scale silently made its dimension cheaper and **adding a value shifted every distance in the library**. Anchored distances are absolute: a new place value leaves existing distances untouched. Unanchored dimensions (`tone`, `length`, `phonation`) still use scale index, honestly, because there the label set is the model. Combining values (overlaps) hold no position either way and compare by expansion.
- **Structural consequence to know**: an affricate now sits near other affricates (shared phase structure), not near its bare fricative component — `t͡ʃ` is closer to `t͡s` than to `ʃ`. The old flat merge said the opposite; consumers of absolute distances should recalibrate thresholds (the shipped matrix and CDF are regenerated).

- **The ordinal scales ascend a declared reference frame** — a left-facing oral tract: +x lips→glottis (`place` and `backness` share it), +y jaw→palate (`height` ascends open→close; `tone` bottom→top), `manner` ascends +constriction, `length` +t. Each ordinal feature carries an `axis` attribute in the data. `silence` is off-scale on the constriction axis (absence of signal has no position — it is equidistant from every manner); `release` and `airstream` are categorical (no axis, every mismatch one step).
- **Tract space** (`ipakit/tract.py`): every phone carries a normalized, head-independent position and the organ that reaches it — `articulator` (the active articulator: lower lip, tongue tip/blade/front/dorsum/root, epiglottis, vocal folds; declared per place value, overridden per phone where it differs — a linguolabial `t̼` is *tongue tip* at a labial target), `arc` (proportional position along the tract midline, lips 0 to glottis 1; consonants from place, vowels from backness) and `offset` (constriction degree, open 0 to closed 1; consonants from manner, vowels from height). The anchors are declared per value in `ipa.xml`, hand-placed from published mid-sagittal anatomy and documented as schematic, not measurements. A combining place sits at its components' centre of gravity, so `w` falls between the lips and the velum.
- **Sagittal bridges** use those coordinates to make cross-class spatial proximity visible: the frame's axes are stored twice (place/backness on x, constriction/height on y) in features that never co-occur, so `j`~`i` and `w`~`u` were invisible to per-feature comparison — a stop scored closer to /i/ than its own glide. With real anchor geometry the orderings hold: `j–i` < `t–i`, and `w–u` < `k–u` < `t–u`. Secondary articulations shade the place term but do not relocate the tongue body.
- **Head shapes** (`data/heads.xml`: `adult-male`, `adult-female`, `child`) project tract space to 2D for rendering — a midline curve plus tract diameter, so the same phone data draws in any head geometry. Heads **never affect distance**: phone identity does not depend on whose head you imagine, and the shipped matrix stays reproducible.
- **Silence is not a speech sound**: `␣` receives no articulatory defaults, no bridge features, and no tract position, so it is exactly 1.0 from every speech sound and 0.0 from itself — substituting silence for a phone costs what deleting it costs, which is what it is. For *rendering* it still needs somewhere to be: each head declares a **rest posture** (jaw and lips closed, tongue neutral, velum lowered), and `Head.project(point, at_rest=True)` draws unplaced points there. Rest is anatomy, not features — and it is where an utterance starts and ends, so it is also the home position for animated trajectories.

Weighting: none. Each dimension contributes equally at maximal difference, with anchored dimensions giving partial credit for genuine proximity — so a total voicing difference costs more than a small place move, which matches the finding that place is the fragile dimension in noise and voicing the robust one. Ad-hoc weights would mostly paper over representation choices (see the label-count artifact above); if weights are ever wanted they belong in a pluggable perceptual layer fitted to confusion data, not baked into the structural metric.

A constriction is really a triple — articulator, location, degree — and ipakit now carries all three. Making that the *representation* (segments as gesture sets, which unifies secondary and double articulation) is designed but not implemented: see [docs/gestural-model.md](gestural-model.md).

The claim is structural consistency, not phonetic ground truth; parameters (gap cost γ = 1, secondary weight σ = 0.5, vowel aperture ceiling 0.5) are named constants.

## Ties across phoneset conversions

Tie **sense is not carried** by the other phoneset encodings: X-SAMPA has a single tie notion (`_`, which both glyphs write to), and CMU/TIMIT/Kirshenbaum have none. Converting out therefore loses the sequential/simultaneous distinction — `ipa_to_xsampa("u͜i") == ipa_to_xsampa("u͡i") == "u_i"`. Coming back, the tie reads generically and the result is canonicalized through `from_wild`, so **registered compounds round-trip to their house spelling with the correct sense** (`t͡s → t_s → t͡s`, `a͜ɪ → a_I → a͜ɪ`, and even a wild `a͡ɪ` comes back as `a͜ɪ`); unregistered chains come back with the sense heuristic. The known X-SAMPA collisions (`b͡v`, `t͡θ`, `ŋ͡m`, where `_v`/`_T`/`_m` re-parse as diacritics) apply to tie-adjacent segments generally. If exact sense on unregistered chains matters, keep the IPA (or the Segment JSON) as the source of truth.

## Unicode form

Input is canonicalized before matching: NFC/NFD variants are equivalent (`ã` precomposed or decomposed), registered precomposed symbols (`ä`, `ç`, `ť`) match in either form, and output tokens are emitted in NFC.
