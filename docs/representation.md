# The canonical representation

IPA text is an input and output boundary. Inside ipakit, the widest reading is
`Form`: an immutable sequence of `Unit` occurrences plus unspelled tier
`Interval`s. Parse once with `read`, carry that value, and take a named
projection only where it is needed.

```python
import ipakit

form = ipakit.read("#kæt.ˈ.dɒɡ#", strict=True)
form.to_ipa()                         # '#kæt.ˈ.dɒɡ#'
[s.to_ipa() for s in form.segments]   # ['k', 'æ', 't', 'ˈd', 'ɒ', 'ɡ']
```

The inventory-bound spelling is `IPAFeatures.read`. The top-level `ipakit.read`
uses the shipped inventory. Rules, distance, converters, transcription search,
and animation consume this representation rather than choosing attachment or
extracting features independently.

## JSON

`Form.to_json()` is the lossless lean interchange format. `Form.from_json()`
and `ipakit.read_json()` restore it without reparsing its IPA spelling.

```python
encoded = form.to_json()
restored = ipakit.read_json(encoded)
restored == form                       # True
```

The top-level object declares `"type": "ipakit.form"` and the current numeric
`"v"`. Readers require that version. Each unit carries:

- its local text;
- its structured `Segment`, or `null` for a boundary or zero;
- optional timing.

That lean default omits resolved segmental features, prosody, and per-mark
provenance for segment units. They are derived from the structured segment and
the inventory on first access, then memoized. Boundary and zero units have no
segment decomposition, so their declared features remain inline.

`form.to_json(self_contained=True)` (and the corresponding `to_dict` option)
embeds `features`, `prosody`, and `provenance` on segment units. This shape is
for a backend that does not carry the inventory. When these views are present,
restoration checks them against the embedded segment; a document cannot say two
different things about one unit. Lean documents perform that derivation lazily.

Tier intervals carry their declared tier, half-open unit endpoints, and optional
timing. Exact source spelling is retained separately only where unit-local text
cannot reproduce its order, such as stress written across a separator.

From the command line:

```shell
$ ipakit convert to-json "#kæt.ˈ.dɒɡ#" --strict
$ ipakit convert to-json "kæt" --self-contained
$ ipakit convert to-json "kæt" | ipakit convert from-json -
```

## Optional time, structural time

Timing belongs to an occurrence, not a `Segment` identity: two occurrences of
the same phone can have different durations. A `Unit` or tier `Interval` may
therefore carry `Timing(start, duration)` in seconds. Zero duration states a
point target; the half-open endpoint is derived as `start + duration`.

Timing is optional. With no explicit endpoints, the ordered units and tier spans
state only their partial order on the animation's base clock. The representation
does not invent seconds, equal durations, interpolation, or a policy for moving
time through a rewrite. Explicit timings supplied by a future aligner constrain
that same clock; they do not change the untimed representation's meaning.

Overlapping spans are allowed. Coarticulation, simultaneous gestures, and tiers
that cross one another require that freedom. Deciding how a ballistic movement
approaches a target is animation policy, not a fact smuggled into serialization.
