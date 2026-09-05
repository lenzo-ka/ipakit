# Praat TextGrid interchange

A TextGrid is a document of numbered intervals and points over one extent. The numbers are not necessarily seconds: a text-parsed form has no durations, so ipakit writes it on ticks, one per segment, and invents no duration. A form read from a timed document carries its physical clock and is written on the physical face when the selected profile asks for it.

A tick profile's numbers are ordinal positions, so a read installs no timing and rebuilds the transcription's structure: a level tier's spans become the boundary marks the form spells.

A physical profile's numbers are durations in the named unit, so a read installs a `Timing` on every unit and carries the other tiers as `Interval`s.

An explicit `tier_map` without a named profile reads the document's numbers as physical timing because the document carries its own numbers and nothing declares otherwise.

## Profiles

- `segments` emits one segment interval tier, the shape an aligner reads.
- `words` emits word intervals followed by segment intervals.
- `prosody` emits utterance, word, syllable, and segment interval tiers followed by stress and tone point tiers.
- `mfa` emits the `words` and `phones` interval tiers used by forced alignment, on physical time.

The profile registry is the `ipakit/data/textgrid` directory, so adding a JSON document adds a profile.

Each profile document is an envelope with a one-line `summary`, a `tier_map`, and a `span_view` document accepted verbatim by `tiergraph.SpanViewProfile.from_data`. The span view declares the emitted tier names and order. The tier map assigns each TextGrid tier name an ipakit role: `segment`, a role declared by `ipakit.form.tier_names(features)`, or a prosodic role declared by `features.features_by_mode["prosodic"]`.

A document's tier names are whatever wrote it. A tier map says which ipakit role each name carries and must cover every tier in the document. Reading without an explicit map and without a named profile refuses because the segment tier cannot be inferred safely.

The codec infers containment between imported interval tiers by exact enclosure of their numbers. An empty-labeled interval is kept as an unclaimed span rather than dropped.

On write, a span tier label is the sequence of non-boundary segments it covers, spelled by ipakit. On read, a non-segment span label supplies extent only and is not interpreted, so an aligner's orthographic word labels do not become IPA.

The written extent is the extent of the form's units, so silence outside the outermost label is not carried by a `Form`. A document whose numbers do not use the emitter's spelling, such as `0.500000` where the emitter writes `0.5`, is not reproduced byte-for-byte.

`ipakit.textgrid.write(..., spell=...)` and `ipakit.textgrid.read(..., read=...)` form the single style seam for a named inventory spelling. Both callables are identity operations by default. `spell` reaches every written label, while `read` reaches only segment labels and point marks because a non-segment label supplies extent only.

```
ipakit textgrid write "kæt dɒɡ" --profile words -o speech.TextGrid
ipakit textgrid read speech.TextGrid --profile words
```
