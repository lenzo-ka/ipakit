# Praat TextGrid interchange

A TextGrid is a document of numbered intervals and points over one extent. The numbers are not necessarily seconds: a text-parsed form has no durations, so ipakit writes it on ticks, one per segment, and invents no duration. A form read from a timed document carries its physical clock and is written on the physical face when the selected profile asks for it.

A tick profile's numbers are ordinal positions, so a read installs no timing and rebuilds the transcription's structure. A document carrying a `boundary` tier restores the marks the form spelled. A document without one infers boundaries from the level tiers, which cannot recover adjacent marks, their order, or a linking mark.

A physical profile's numbers are durations in the named unit, so a read installs a `Timing` on every unit and carries the other tiers as `Interval`s.

An explicit `tier_map` without a named profile requires `face="physical"` or `face="tick"`; the numbers do not declare which clock face they carry.

## Profiles

- `segments` emits one segment interval tier, the shape an aligner reads.
- `words` emits word intervals followed by segment intervals.
- `prosody` emits utterance, word, syllable, and segment interval tiers followed by stress, tone, and boundary point tiers.
- `mfa` emits the `words` and `phones` interval tiers used by forced alignment, on physical time.

The profile registry is the `ipakit/data/textgrid` directory, so adding a JSON document adds a profile.

Each profile document is an envelope with a one-line `summary`, a `tier_map`, and a `span_view` document accepted verbatim by `tiergraph.SpanViewProfile.from_data`. The span view declares the emitted tier names and order. The tier map assigns each TextGrid tier name an ipakit role: `segment`, `boundary`, a role declared by `ipakit.form.tier_names(features)`, or a prosodic role declared by `features.features_by_mode["prosodic"]`.

A document's tier names are whatever wrote it. A tier map says which ipakit role each name carries and must cover every tier in the document. Reading without an explicit map and without a named profile refuses because the segment tier cannot be inferred safely.

The codec infers containment between imported interval tiers by exact enclosure of their numbers. An empty-labeled interval is kept as an unclaimed span rather than dropped.

Two tiers may share a non-segment role on read. A repeated role imports two annotators' tiers as intervals on one role, and a form carrying overlapping intervals on one role is refused on write because a tier is one cover.

On write, a span tier label is the sequence of non-boundary segments it covers, spelled by ipakit. On read, a non-segment span label supplies extent only and is not interpreted, so an aligner's orthographic word labels do not become IPA.

The written extent is the extent of the form's units, so silence outside the outermost label is not carried by a `Form`. A document whose numbers do not use the emitter's spelling, such as `0.500000` where the emitter writes `0.5`, is not reproduced byte-for-byte.

## Label styles

`ipakit.textgrid.write(..., style=...)` and `ipakit.textgrid.read(..., style=...)` take an inventory name or a `Style`; a name resolves through `inventory(name).style`, and an unavailable name is refused with the registry command `ipakit inventory list`. The lower-level `spell` and `read` callable seams remain available, but either callable is mutually exclusive with `style`.

A style spells and reads segment interval labels. On write, a word, utterance, or other non-segment interval label is built from its styled segment labels, using the style's declared separator or a space when it declares none; MFA declares concatenation to retain aligner word labels, while CMUdict declares a space. On read, a non-segment interval label continues to supply extent only and is not interpreted.

Each prosodic mark lives in exactly one place: when the profile declares a point tier for its role, the point carries the house mark and the styled segment label contains segmental text alone. When no such point tier exists, the mark stays in the segment label and the style spells the whole marked unit; a style that cannot do so refuses the label and directs the caller to a profile with that point tier.

Writing is strict and atomic: every phone the style refuses becomes an empty provisional label, all refusals are collected with the profile, tier, interval, and house-IPA label, and no document is returned. Reading is also strict and names the tier, interval, and document label it refuses.

MFA reads its untied `tʃ`, `aj`, and `kp` phone labels as the single house phones `t͡ʃ`, `a͜j`, and `k͡p`, then writes the untied labels again: `ipakit textgrid read aligned.TextGrid --profile mfa --style mfa` and `ipakit textgrid write "t͡ʃa͜jk͡p" --profile mfa --style mfa`. CMUdict reads a digit-0 label such as `AH0` as unstressed house `ə` and writes it back as `AH`, its declared collapse, while `AH1` and `AH2` keep their stress digits; both house `ə` and `ʌ` therefore spell canonically as `AH` when unstressed.

```
ipakit textgrid write "kæt dɒɡ" --profile words -o speech.TextGrid
ipakit textgrid read speech.TextGrid --profile words
```
