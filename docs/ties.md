# Tie conventions

ipakit assigns the two IPA tie glyphs distinct senses. Standard IPA treats them as typographic variants (the under-tie exists largely to avoid collisions with marks above); ipakit's assignment is a house convention, chosen so that a transcription's structure can be decoded from its glyphs alone.

## The two ties

| glyph | codepoint | sense | meaning |
|---|---|---|---|
| `◌͡◌` over-tie | U+0361 | **simultaneous** | fuses constituents into **one timing slot** — internal phases allowed (affricates `t͡s`, prenasalized stops `n͡d`) or fully overlapped (double articulations `k͡p`) |
| `◌͜◌` under-tie | U+035C | **sequential** | binds **multiple timing slots into one unit** — a trajectory (diphthongs `u͜i`, moraic chains `a͜ɪ͜ə`) |

A tie's *presence* is contrastive and is never added or removed by normalization: `t͡s` is one segment, `ts` is a two-segment cluster — different objects, and no alias equates them.

The spacing undertie `‿` (U+203F) is a different symbol entirely: the IPA **linking** mark (absence of a break) between words — French liaison is one use. It is a separator-level mark, not a tie.

## Precedence

The over-tie binds tighter. A mixed chain decodes without brackets: `t͡s͜a` is the fused unit `t͡s` sequentially bound to `a` — one token, a CV-mora-like unit. A sequential tie always operates on the maximal fused unit on each side.

Both ties stacked on one juncture assert contradictory timing; on ingest the pair collapses to the over-tie (simultaneous precedence). It is never emitted.

## The glyph is authoritative; wild text imports explicitly

House style is the only default semantics: canonical spellings are sense-correct (affricates and double articulations over-tie — `t͡s`, `k͡p`; diphthongs under-tie — `e͜ɪ`, `a͜ɪ`), and every entry point reads the glyph as the sense. `t͜s` is a sequential chain, not a spelling of the affricate; `a͡ɪ` is a fused vowel overlay, not the diphthong. Only unambiguous single-character ligatures (`ʦ`, `ʧ`, NAPA `ƛ`) are aliases.

Text from the wild — where the two glyphs are typographic free variants carrying no sense — is imported **explicitly** with `ipakit.from_wild(text)` (or `IPAFeatures.from_wild`): each uniform-glyph tied chain is rewritten to house style, preferring the spelling that names a registered compound (`t͜s` → `t͡s`, `a͡ɪ` → `a͜ɪ`) and falling back to the sense heuristic for unregistered chains (all-vocalic → sequential, else simultaneous). Chains already mixing both glyphs are house-authored and pass through untouched. Because import is explicit, default parsing is faithful: `parse(emit(x)) = x` structurally for every expressible unit — there is no collision list and no lossy emission.

## Registered compounds are derived, not hand-encoded

Tied entries in `ipa.xml` carry only their spelling, aliases, and reference link; their **features are derived at load** by the same composer that serves unregistered chains, under each entry's sense (affricates via the simultaneous merge, diphthongs via the sequential first-element projection). Registration is therefore a cache of composition by construction — registered and computed values cannot drift, and `IPAFeatures.derived_phones` lists the entries this applies to. Every tied entry is derived — composition resolves diacritic-bearing parts (`ʊ̯` = base + non-syllabic modifier) as constituents.

## Composition of unregistered sequences

An unregistered tie-joined sequence of known phones still resolves (`registered wins, composition is the long-tail fallback`):

- **Over-tie (simultaneous)**: features merge left to right; differing manners collapse to `affricate` (`q͡χ` → uvular affricate); same-manner pairs with a dedicated combined place get it (`ɡ͡b`-style → `labial-velar`).
- **Under-tie (sequential)**: the flat feature projection is the **first element** (`u͜i` → the features of `u`) — the same encoding the registered diphthongs use. The remaining constituents stay recoverable from the token itself.
- **Mixed chains**: the first top-level part's features (`t͡s͜a` → the affricate's features).

The flat projection is deliberately a summary, not the whole story. The structured reads live on `Segment` (`ipakit.parse_segment` / `parse_segments`, or `IPAFeatures.segment` / `segments`):

- `Segment` stores the flat chain — `constituents` (base + modifier stack) joined by typed `junctures` — plus unit-level `prosody` (stress, length, tone). Everything else is derived: `children` (the grouping: sequential runs, then phase blocks, then constituents), `kind` (affricate, prenasalized, pre-stopped, lateral-release, click-accompaniment, double-articulation, overlay, diphthong, chain, atomic), `sense`, `left`/`right` (edge children) with `left_features()`/`right_features()`/`features_at(i)` (the edge feature reads — approach a composed unit from either side, e.g. `parse_segment("t͡s͜a").left_features()` is the affricate's read), `bag()` (per-feature value tuples in constituent order — `u͜i` carries `backness=('back', 'front')`), and `scalar()` (the same flat projection `get_features` gives).
- Modifiers contribute by mode: overriding marks replace their base's value (the devoicing ring makes `d̥` voiceless, never both-voiced), additive and secondary marks add only what the base doesn't state, release marks stay phase properties, and prosodic marks live on the unit, outside the feature bag.
- `to_json()`/`from_json()` carry the junctures explicitly and are the round-trip-guaranteed serialization. `to_ipa()` emits sense-correct glyphs and is lossy exactly on the legacy alias collisions: `build_segment(["a", "ɪ"], Sense.FUSE)` emits `a͡ɪ`, which re-ingests as the registered sequential diphthong — intent that must survive a string round trip needs the JSON form.
- `build_segment` is the intent channel: it constructs any combination directly, bypassing string-alias collisions.

## Normalizing tieless input

`normalize_ipa` treats whitespace-separated groups as asserted units and inserts ties by a documented heuristic: adjacent vowels bind sequentially (`"eɪ"` → `e͜ɪ`), anything else fuses (`"ts"` → `t͡s`). An explicitly written tie always wins. The heuristic output round-trips: `e͜ɪ` resolves to the registered `e͡ɪ` through its alias.

## Ties across phoneset conversions

Tie **sense is not carried** by the other phoneset encodings: X-SAMPA has a single tie notion (`_`, which both glyphs write to), and CMU/TIMIT/Kirshenbaum have none. Converting out therefore loses the sequential/simultaneous distinction — `ipa_to_xsampa("u͜i") == ipa_to_xsampa("u͡i") == "u_i"`. Coming back, the tie reads generically and the result is canonicalized through `from_wild`, so **registered compounds round-trip to their house spelling with the correct sense** (`t͡s → t_s → t͡s`, `a͜ɪ → a_I → a͜ɪ`, and even a wild `a͡ɪ` comes back as `a͜ɪ`); unregistered chains come back with the sense heuristic. The known X-SAMPA collisions (`b͡v`, `t͡θ`, `ŋ͡m`, where `_v`/`_T`/`_m` re-parse as diacritics) apply to tie-adjacent segments generally. If exact sense on unregistered chains matters, keep the IPA (or the Segment JSON) as the source of truth.

## Unicode form

Input is canonicalized before matching: NFC/NFD variants are equivalent (`ã` precomposed or decomposed), registered precomposed symbols (`ä`, `ç`, `ť`) match in either form, and output tokens are emitted in NFC.
