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

## Registered symbols win, including through their aliases

Lookup order everywhere (tokenizer, `get_features`, `get_phone`, `in`): registered symbol first — including its alias spellings, resolved token-locally — then on-the-fly composition. The registered inventory carries traditional spellings as aliases, so both of these resolve to their registered entries regardless of glyph:

- `t͜s` → the registered affricate `t͡s` (the under-tie spelling is a legacy alias);
- `e͜ɪ` → the registered diphthong `e͡ɪ` (currently registered with the over-tie spelling; the under-tie spelling is its alias).

For these specific alias strings the registered sense wins over the glyph's. Everywhere else the glyph is authoritative.

## Composition of unregistered sequences

An unregistered tie-joined sequence of known phones still resolves (`registered wins, composition is the long-tail fallback`):

- **Over-tie (simultaneous)**: features merge left to right; differing manners collapse to `affricate` (`q͡χ` → uvular affricate); same-manner pairs with a dedicated combined place get it (`ɡ͡b`-style → `labial-velar`).
- **Under-tie (sequential)**: the flat feature projection is the **first element** (`u͜i` → the features of `u`) — the same encoding the registered diphthongs use. The remaining constituents stay recoverable from the token itself.
- **Mixed chains**: the first top-level part's features (`t͡s͜a` → the affricate's features).

The flat projection is deliberately a summary, not the whole story; richer structured reads (per-constituent access, multi-valued feature bags) are planned on top of the same representation.

## Normalizing tieless input

`normalize_ipa` treats whitespace-separated groups as asserted units and inserts ties by a documented heuristic: adjacent vowels bind sequentially (`"eɪ"` → `e͜ɪ`), anything else fuses (`"ts"` → `t͡s`). An explicitly written tie always wins. The heuristic output round-trips: `e͜ɪ` resolves to the registered `e͡ɪ` through its alias.

## Ties across phoneset conversions

Tie **sense does not survive** conversion to other phonesets, and round trips do not restore it. X-SAMPA has a single tie encoding (`_`), and CMU/TIMIT/Kirshenbaum have none, so at those conversion boundaries the under-tie is **projected onto the over-tie**: unit-hood survives where the encoding can carry it, the sequential/simultaneous distinction does not.

- `t͜s` → `t_s` → `t͡s` and `u͜i` → `u_i` → `u͡i`: the round trip returns canonical **over-tie** spellings, whatever the input glyph.
- `ipa_to_xsampa("u͜i") == ipa_to_xsampa("u͡i")`: both senses convert identically.
- The known X-SAMPA collisions (`b͡v`, `t͡θ`, `ŋ͡m`, where `_v`/`_T`/`_m` re-parse as diacritics) apply to tie-adjacent segments generally — e.g. a tie before a segment whose X-SAMPA starts with `a` collides with the apical diacritic `_a`.

This projection is legitimate only at a lossy conversion boundary; parsing never rewrites tie glyphs. If tie sense matters, keep the IPA (or a structured form) as the source of truth and treat phoneset output as a projection.

## Unicode form

Input is canonicalized before matching: NFC/NFD variants are equivalent (`ã` precomposed or decomposed), registered precomposed symbols (`ä`, `ç`, `ť`) match in either form, and output tokens are emitted in NFC.
