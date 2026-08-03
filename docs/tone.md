# Tone: a contour is a shape, not a value

A level tone is a point; a contour tone is a **path between points**. ipakit represents both the same way: a unit's `tone` is a **sequence of declared levels, in time order**.

```python
import ipakit as ipa
from ipakit.form import units

units("a˩˥")[0].prosody     # {'tone': 'bottom>top', 'contour': 'rising'}
units("a˧˩˧")[0].prosody    # {'tone': 'mid>bottom>mid', 'contour': 'falling>rising'}
units("a᷄")[0].prosody       # {'tone': 'mid>high', 'contour': 'rising'}
units("a˧˦")[0].prosody     # {'tone': 'mid>high', 'contour': 'rising'}
```

The last two lines are the point of the representation: `᷄` and `˧˦` are the diacritic and tone-letter spellings of one contour, and they now read as one thing.

The sequence is what Chao tone letters already spell, and it is the only representation that closes. The IPA chart's contour column names five contours, but Chao's system permits *any* run of levels, so enumerating shapes as feature values never finishes — and one of the chart's own five, rising-falling, does not decompose into a level plus a direction at all. A sequence needs no new value for any of them.

## A tone letter rides on the unit; it is not a unit

A tone-letter run stays in `Segment.prosody`, which is already an ordered tuple of glyphs, and a whole run belongs to the one syllable it is written on. Making each letter its own unit was the alternative, and it is wrong in three ways at once: `phones` would gain positions that are not sounds, the rule engine's context scan would have to step over them, and `a˩˥` would stop being one thing to ask a question about. A contour is a property of a syllable, so it lives where the syllable's other properties live.

What changed is not where the letters are kept but what is made of them: the run composes into one sequence instead of the last letter overwriting the others.

```python
import ipakit

ipakit.to_ipa(ipakit.segments("ˈa᷈ː"))   # 'ˈa᷈ː'
```

## Prosody stays outside the feature bag

Nothing here is in a feature bundle. Tone is `mode="prosodic"` and prosody lives on the unit ([ties.md](ties.md)), so this whole document is invisible to `features()` and to `distance()`:

```python
ipa.features("a") == ipa.features("a᷈")   # True
ipa.distance("a", "a᷈")                   # 0.0
```

## `contour` is derived from the sequence, and asserted only where there is none

`contour` names the move between one level and the next: one step per adjacent pair, so a two-level tone has one step and a three-level tone has two.

```python
f = ipa.load_ipa_features()
f.features["contour"].over                # 'tone'
sorted(f.features["contour"].values)      # ['falling', 'rising', 'steady']
```

Each value declares the sign of the move it names (`move="+"`, `"0"`, `"-"`), so the direction between two levels is read off the declaration rather than off a table of directions in Python. Longer shapes compose from those steps — `rising>falling` for a peak — instead of each needing a name.

A **direction remains askable**, and that is deliberate: `contour=rising` is what rules are written with, and it reads better than a sequence for a rule that does not care which levels. Because the contour is derived, one query now reaches both spellings:

```python
ipa.rewrite("kǎ", "[contour=rising] -> e")    # 'ke'
ipa.rewrite("ka˩˥", "[contour=rising] -> e")  # 'ke˩˥'
```

## An abbreviating diacritic leaves the levels unstated

`ǎ` says the pitch rises. It does not say between which levels, and this repo does not invent a tier nothing asserted — an undotted word has unspecified syllabification rather than one syllable ([form.md](form.md)), and a bare caron has an unspecified level sequence rather than `˩˥`.

```python
units("ǎ")[0].prosody       # {'contour': 'rising'}
```

So the caron and the circumflex declare `contour` **directly**, with no `tone` key at all. They are the only two marks that do. The other six say their levels, and their contour follows.

This is not a technicality. The IPA's level diacritics are register-relative: the acute is the highest tone of a three-tone language and the second-highest of a four-tone one. A bare rise pinned to `bottom>top` would be a claim about the language's register that the transcriber did not make, and a rule asking `tone=bottom>top` would then match transcriptions that never said it.

## Two spellings of one contour are **compatible**, not identical

`units("ǎ")` and `units("a˩˥")` do not compare equal, and should not. They agree on everything either of them states — both rise — and one states more than the other. That is compatibility, which is a different relation from identity, and collapsing them would mean either inventing levels for the caron or discarding the ones the tone letters wrote.

Where both spellings state the same levels, they *are* identical: `units("a᷄")[0].prosody == units("a˧˦")[0].prosody`. That is the equivalence the chart claims, and it now holds exactly where it is true.

## The eight tone diacritics, and where they come from

The level sequences are read off the **Unicode character names**, which are compositional and unambiguous: grave is low, macron is mid, acute is high, read left to right as time order. That is the same reading `ipa.xml` already gives the three level diacritics (`̀`=low, `̄`=mid, `́`=high), so it is the only reading consistent with the rest of the file.

| glyph | codepoint | Unicode name | declared `tone` | derived `contour` | chart name |
| --- | --- | --- | --- | --- | --- |
| `◌̌` | U+030C | COMBINING CARON | — | `rising` (asserted) | Rising |
| `◌̂` | U+0302 | COMBINING CIRCUMFLEX ACCENT | — | `falling` (asserted) | Falling |
| `◌᷄` | U+1DC4 | COMBINING MACRON-ACUTE | `mid>high` | `rising` | High rising |
| `◌᷅` | U+1DC5 | COMBINING GRAVE-MACRON | `low>mid` | `rising` | Low rising |
| `◌᷆` | U+1DC6 | COMBINING MACRON-GRAVE | `mid>low` | `falling` | Low falling |
| `◌᷇` | U+1DC7 | COMBINING ACUTE-MACRON | `high>mid` | `falling` | High falling |
| `◌᷈` | U+1DC8 | COMBINING GRAVE-ACUTE-GRAVE | `low>high>low` | `rising>falling` | Rising-falling (peaking) |
| `◌᷉` | U+1DC9 | COMBINING ACUTE-GRAVE-ACUTE | `high>low>high` | `falling>rising` | Falling-rising (dipping) |

Four of these — U+1DC6 through U+1DC9 — were undeclared until now, which is why `contour` had two values where the chart names five.

Sources: the Unicode character names (`unicodedata.name`); the Unicode proposal documenting U+1DC4–U+1DC7 as *higher rising, lower rising, lower falling, higher falling* (<https://unicode.org/L2/L2025/25250-ipa-tone-diacritics.pdf>); and the IPA chart's tone tables as transcribed at <https://en.wikipedia.org/wiki/International_Phonetic_Alphabet_chart> and <https://en.wikipedia.org/wiki/Tone_letter>.

## The chart's tone-letter equivalents disagree with its own level column

This was cross-checked rather than assumed, and the two do not agree. It is a discrepancy in the sources, not a choice ipakit made silently.

The chart's **level** column pairs `́` with `˦`, `̄` with `˧` and `̀` with `˨`. Composing those, macron-acute is `˧˦` and grave-macron is `˨˧`. The chart's **contour** column instead gives `˧˥` for `᷄` and `˩˧` for `᷅` — the same shapes, but reaching one step further out at the extreme end. The chart is not composing its contour marks from its own level marks.

| glyph | compositional, from the level column | chart's contour column |
| --- | --- | --- |
| `◌᷄` | `˧˦` | `˧˥` |
| `◌᷅` | `˨˧` | `˩˧` |
| `◌᷆` | `˧˨` | `˧˩` |
| `◌᷇` | `˦˧` | `˥˧` |
| `◌᷈` | `˨˦˨` | `˧˥˨`, `˨˦˨`, `˩˧˩` |
| `◌᷉` | `˦˨˦` | `˥˧˥`, `˦˨˦`, `˧˩˧` |

Two things settle it. First, the three-level marks are given **three** tone-letter equivalents each, and the compositional reading is among them in both cases — so the chart is illustrating a shape at some register, not defining a spelling. Second, the diacritics are register-relative by design: the acute is the top of a three-tone system and the second level of a four-tone one, so no single absolute pair is *the* meaning of a two-level diacritic.

ipakit takes the compositional reading, because it is the one its own level declarations already commit to and the only one that keeps `᷄` and `˧˦` from being two different tones in the same file. A transcription that needs the chart's exact registers writes the tone letters, which say them.

The X-SAMPA table is a third opinion and was corrected to match: ICU encodes `᷄` as `_H_T` and `᷅` as `_B_L` (high-then-top, bottom-then-low), one step out again. Those are now `_M_H` and `_L_M`, and the four new marks encode as the level runs they name, so a conversion cannot change which contour a symbol is.

## What warns instead of dropping

A run of prosodic marks used to merge into one bundle by last-writer-wins, so `a˩˥` was recorded as `tone=top` and `a˥˩` as `tone=bottom` — a rise and a fall stored as opposite **level** tones, with no error and no warning. Anything spelled with tone letters lost its contours entirely.

Sequence-valued features now concatenate, so nothing is dropped. Where two marks state a **single-valued** feature, the first stands and the collision is reported rather than silently overwritten. That is not a rule about prosody: it is what two marks of one stack stating one feature mean anywhere ([ties.md](ties.md)), and the segmental projection and the unit's prosody read it through one function, so `compose("a˧˦")` and `units("a˧˦")[0].prosody` cannot disagree about the tone.

```python
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    units("aːˑ")

str(caught[0].message)
# "'aːˑ': two marks state 'length' ('long' then 'half-long'); 'length' is single-valued, so 'half-long' is a contradiction and is not recorded"
```

A written contour that contradicts the levels written with it is reported the same way — the mark stands, because only the writer knows which they meant.

Writing prosody keeps the same policy, since a write that disagreed with the read would be a second opinion about one transcription. `with_prosody` keeps a contour a mark *wrote*, agreeing with the levels or not, and never drops an assertion on the grounds that the levels would derive the same tier — that is how a caron over a falling sequence came back a fall, out of a call that changed nothing. It also refuses to clear a contour the levels entail: a tone reading `bottom>top` rises whether or not a mark says so, so a form with those levels and no contour does not exist, and the answer is `None` rather than a report of success.

## Known limits

- **The level tier is spellable by diacritic only in the middle three.** `ipa.xml` declares `̀` low, `̄` mid and `́` high; the chart's `̋` (extra high) and `̏` (extra low) are undeclared, so `top` and `bottom` are reachable only through the tone letters `˥` and `˩`. That gap is real and separate from contours.
- **A contour is a sequence of levels and nothing else.** Duration within the contour, and the difference between a fall reaching its target early and one gliding throughout, are not represented. Chao's letters do not say it either.
- **`steady` has no mark.** It is the value a step takes when two adjacent levels are equal (`a˧˧`), so it is derived and never written; nothing declares it, and `compose_unit` therefore cannot produce it.
