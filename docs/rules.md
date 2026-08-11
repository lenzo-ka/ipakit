# Rewrite rules

A rule is the classic generative statement:

```
A  ->  B  /  C _ D
```

*Rewrite `A` as `B` when it stands between `C` and `D`.* This document is the notation, what each part means, and the decisions that are not obvious. The engine is `ipakit.rules`; the representation it works over is `ipakit.form`, documented in [form.md](form.md).

```python
import ipakit as ipa

ipa.rewrite("bˈʌtɚ", "t -> ɾ / [vowel stress=primary] _ [vowel]")
# 'bˈʌɾɚ'
```

## The two halves are separable

The left of the arrow **recognizes**; the right **acts**. Both are reachable alone, because "where does a plosive stand between vowels" is a question with no rewrite attached.

```python
r = ipa.rule("[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing")

r.recognize("atapa")   # [Site(start=1, end=2, left=(0,), right=(2,), bindings=()), Site(start=3, end=4, left=(2,), right=(4,), bindings=())]
r.edits("atapa")       # what it would do, without doing it
ipa.rewrite("atapa", r)                 # 'adaba'
ipa.derive("atapa", r).trace()          # the same, with an account
```

A `Site` records *which* neighbors licensed it, not merely that some did, so a trace can explain itself. An entry is `None` where the context matched the virtual edge past the end of the form rather than a unit that is really there. `bindings` is the same kind of record for [agreement variables](#a-rule-may-bind-a-value-and-re-use-it), empty for a rule that names none.

## Notation

| Piece | Means |
| --- | --- |
| `->` `→` `=>` | the rewrite arrow; any of the three |
| `~>` `~->` `~→` `~=>` | the same arrow, marked **optional**: the rule *may* fire |
| `/` | begins the context |
| `_` | where the target sits in the context |
| `;` | begins the rule's name |
| `#` | a word boundary |
| `.` | a syllable boundary |
| `%` | any boundary |
| `\|` `‖` `‿` | the declared prosodic break, major break, linking mark |
| `∅` `0` `Ø` | the empty string — insertion or deletion |
| `[...]` | a feature query |
| `[key=α]` | an **agreement variable**: this value, wherever else the rule writes `α` |
| `[key=-α]` | the *opposite* value; binary features only |
| `[key=∅]` | in a change: clear that prosodic value |
| `[zero]` | a structural zero — a position with no content |
| `(X)` | in a context: zero or one unit matching `X` |
| `(X)*` | in a context: zero or more units matching `X` |
| a bare glyph | that literal phone, with any prosody it wears |

The name separator is `;` and **not** `|`, because `|` is a declared prosodic break and therefore a legal context item. Using `|` for both meant `t -> ʔ / _ |` silently became an unconditional rule.

### Feature queries

Bracketed items use the **same query language** as `phones_matching` and `find` — not a second dialect. Bare class terms and `key=value` terms may be mixed:

```
[vowel]                     manner=vowel
[manner=plosive voiced=-]   a voiceless plosive
[vowel stress=primary]      a stressed vowel
[-voiced]                   voiced is '-'  (SPE's [-voice])
[vowel -nasalized]          a vowel that is not nasalized
[obstruent]                 a natural class declared over manner's values
[obstruent -fricative]      that class, narrowed: the plosives and affricates
```

A bare term may also name a **natural class** the data declares: `natural-class="obstruent"` sits on the `fricative`, `plosive` and `affricate` values of `manner`, and `[obstruent]` asks for it. The class selects or excludes whole — `[obstruent]`, `[-obstruent]` — and narrows like any other term. Because it is read off the declaration, a manner added to `ipa.xml` belongs to the class only if the data says so. Three shipped rule sets used to write the class out as `[-vowel -approximant -nasal -trill -tap -silence]`, which selects the same phones today and would take a new manner in without a word.

A term that names nothing fails loudly on **both** sides of the arrow, on **both** arms of a `key=value`, and **whatever else the bracket contains** — an undeclared key, an undeclared value and an unresolvable bare term are equally an error, not a constraint that quietly matches nothing:

```python
ipa.rule("[mannr=plosive] -> t")
# RuleError: '[mannr=plosive]' names undeclared feature(s): ['mannr']
ipa.rule("[manner=obstruent] -> [voiced=-]")
# RuleError: '[manner=obstruent]': 'obstruent' is not a value of feature 'manner'; declared values are ['affricate', 'approximant', 'fricative', 'nasal', 'plosive', 'silence', 'tap', 'trill', 'vowel']. 'obstruent' is a natural class over those values; ask for it as the bare term '[obstruent]'
ipa.rule("t -> ɾ / [vowel] _ [vowel -stress]")
# RuleError: '[vowel -stress]': '-stress' resolves to no feature term; feature 'stress' is not binary...; negate them individually instead, as '-none -primary -secondary'
```

The value arm was the later of the two. `[manner=obstruent]` — the query a reader reaches for first — used to build a constraint no phone can satisfy and match nothing, silently, while this document already promised the opposite; the claim was prose rather than an executed example, which is how it survived a pass that verified thirty others. Values resolve through the alias table and `expand()` as on every other write path, so a spelled alias and a generative overlap (`bilabial^velar`) are still accepted. A class is not a value of the feature it groups, so this spelling stays an error; the message names the one that works.

**Every** term must resolve, at every arity: a bracket that mixes a good term with a bad one raises rather than dropping the bad one, since a dropped term is a narrower query silently widened. The message names what would have worked. `stress` has no `-` to take — its values are `none`, `secondary` and `primary` — so a query about stress negates the marked values, `[vowel -primary -secondary]`; `none` is the unspelled ordinal anchor and matches no unit on its own.

## A rule may bind a value and re-use it

SPE's **agreement variable**. A Greek letter in the value slot means *this value, whatever it is, and the same one everywhere else the rule writes that letter*:

```python
ipa.rewrite("anpa", "n -> [place=α] / _ [place=α]")   # 'ampa'
ipa.rewrite("anka", "n -> [place=α] / _ [place=α]")   # 'aŋka'
```

That is one rule for a process that was otherwise one rule per place value — eleven or more in general, and two in the shipped English set, which enumerated the two places English happens to need and said in a comment that the general statement was not expressible.

**Recognition binds; the action refers.** The left of the arrow is where a variable takes a value, from the target or from a context item; the right may only name one the left already bound. A variable on the right that nothing on the left binds is refused, rather than resolving at some sites and not at others:

```python
ipa.rule("n -> [place=α]")
# RuleError: 'n -> [place=α]' writes the variable(s) α on the right of the arrow, and nothing on the left binds them...
```

**Every occurrence in the recognition half must agree**, so which one "binds" is not a rule anybody has to remember: the site holds exactly where they read the same value. Either side may be the one carrying the information — this asks the *target* to agree with its right neighbor and changes something else:

```python
ipa.rewrite("atta", "[place=α] -> [voiced=+] / _ [place=α]")   # 'adta'
ipa.rewrite("atka", "[place=α] -> [voiced=+] / _ [place=α]")   # 'atka'
```

**A value has to be there to be bound.** No vowel declares a `place`, so `[place=α]` does not reach one and `/n/` before a vowel is left alone. That is the ordinary reading of any query term rather than a rule about variables:

```python
ipa.rewrite("ana", "n -> [place=α] / _ [place=α]")     # 'ana'
```

**A variable ranges over one feature.** The declared values of `place` and of `voiced` are different sets, so a variable over both is over nothing:

```python
ipa.rule("n -> [place=α] / [voiced=α] _ [place=α]")
# RuleError: ... uses the variable 'α' on two features, 'voiced' and 'place'...
```

Independent variables are how a rule speaks about two features at once, and `α`, `γ`, `δ` … are a supply rather than one name:

```python
ipa.rewrite("atkza", "[manner=plosive] -> [place=α voiced=γ] / _ [place=α] [voiced=γ]")
# 'aɡdza'
```

**A variable used once says nothing**, and is refused for the reason a misspelled feature is: it is what a typo looks like — `α` on the left and `γ` on the right is two lone variables, not one shared one.

```python
ipa.rule("n -> t / _ [place=α]")
# RuleError: ... uses the variable(s) α once...
```

### Disagreement, and where it stops

`-α` is SPE's *opposite value*. For a binary feature the opposite is well defined and this is dissimilation in one line:

```python
ipa.rewrite("asta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")   # 'asda'
ipa.rewrite("azta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")   # 'azta'
```

For an n-ary feature there is no opposite to mean — the opposite of `velar` is every other place the feature declares — so it is refused rather than guessed at. That is a real limit, statable, and not a fudge:

```python
ipa.rule("n -> [place=-α] / _ [place=α]")
# RuleError: '[place=-α]' writes the opposite of a variable on 'place', which declares 14 values...
```

### The letter is checked against the inventory

The traditional series is `α β γ`, and **the second member is a registered phone** — the voiced bilabial fricative — as are `θ` and `χ` further along it. So the series is not taken on trust: a variable is a Greek small letter that spells *nothing this inventory reads*, which is asked of the declaration rather than answered from a list.

```python
from ipakit import rules
"".join(rules.SERIES)                                        # 'αβγδεζηθικλμνξοπρστυφχψω'
"".join(rules._free_variables(ipa.load_ipa_features()))      # 'αγδεζηικλμνξοπρστυφψω'
ipa.rule("n -> [place=β] / _ [place=β]")
# RuleError: 'β' spells something this inventory registers (β), so it cannot also be an agreement variable...
```

Refused **by name and with the reason**, which is the half that matters. Skipping `β` in silence would surprise exactly the reader who knows the series best. The property being protected is the other direction: a variable must never be able to reach a form, because a leak would then spell a phone rather than fail — `units("aαb")` drops the `α` and `units("aβb")` does not.

A letter the inventory registers is a phone wherever it is written, so a bare `[β]` gets the same answer from the other direction — brackets ask for a class, and `β` names none:

```python
ipa.rule("t -> d / _ [β]")
# RuleError: '[β]' asks for a class named 'β', and 'β' spells a registered phone (β) rather than a class...
```

The series is the alphabet's small letters and only those. `ά` is alpha with a tonos and falls outside the endpoints; `ς` is sigma at the end of a word and falls between `ρ` and `σ`, inside them — so a letter must also be the one its own capital lowercases back to. Two members that differ only in how they are drawn would be a notation whose typos are invisible.

The rule holds in both directions and the declaration always wins: declare `α` as a phone tomorrow and it stops being notation, loudly, exactly as `~` would.

## Stress is not part of a phone's identity

`features("a")`, `features("ˈa")` and `features("aː")` are one bundle: the `mode="prosodic"` features live on the unit, outside the feature bag (see [ties.md](ties.md)). So:

```python
ipa.rewrite("kˈat", "a -> ɑ")      # 'kˈɑt'  -- 'a' matches the stressed 'ˈa'
```

That is what a rule about the vowel /a/ should do. Prosody is a second **namespace**, not a second phone, and in that namespace it is both askable and writable:

```
[vowel]                  any vowel, stressed or not
[vowel stress=primary]   only the stressed one
```

A query term routes to whichever namespace *declares* it, read off `Feature.mode`, so no list of prosodic feature names appears in the engine.

### Writing prosody

Assign, change, clear — the same query language on the right of the arrow:

```python
ipa.rewrite("ka",   "[vowel] -> [length=long] / _ #")     # 'kaː'   lengthen
ipa.rewrite("kaː",  "[vowel] -> [length=normal] / _ #")   # 'ka'    shorten
ipa.rewrite("at",   "[vowel] -> [stress=primary] / # _")  # 'ˈat'   assign stress
ipa.rewrite("kˌat", "[vowel] -> [stress=primary]")        # 'kˈat'  restress
ipa.rewrite("kˈat", "[vowel] -> [stress=∅]")              # 'kat'   destress
```

**Removal is `∅`.** The notation already spells "nothing" three ways for a whole unit (`t -> ∅`); `[stress=∅]` is that same word applied to one dimension of one unit instead of to the unit. No new vocabulary, and it is needed only where a feature has no unmarked value to name — `length` declares a default of `normal` and *nothing declares that value*, because a bare vowel already says it, so shortening and clearing are one operation rather than two spellings of it:

```python
f = ipa.load_ipa_features()
f.features["length"].default              # 'normal'
f.declaring_mark("length", "long")[1]     # 'ː'
f.declaring_mark("length", "normal")      # None -- so absence is how it is written
f.features["stress"].default              # None -- nothing to name, hence '∅'
```

Clearing a *segmental* feature is refused rather than guessed at: every phone has some voicing, so `[voiced=∅]` names nothing.

```python
ipa.rule("[vowel] -> [voiced=∅]")
# RuleError: '[voiced=∅]' clears 'voiced', but only prosody can be absent
```

Prosody is written in **feature space** and spelled afterwards, so a rule about one feature leaves the marks that state the others as written:

```python
ipa.rewrite("kˈa᷄", "[vowel] -> [tone=∅]")     # 'kˈa'   -- the stress mark stays
ipa.rewrite("kˈa᷄", "[vowel] -> [stress=∅]")   # 'ka᷄'   -- and the tone stays
```

A tone is a **sequence of levels**, so it is written and cleared as one thing however it was spelled: `᷄` abbreviates `˧˦` and both say `tone="mid>high"` ([tone.md](tone.md)). A rule may name a sequence on either side, and `contour` is the shape derived from one, so a rule about a direction reaches both spellings:

```python
from ipakit.form import declared_prosody
declared_prosody("᷄", f)                                # {'tone': 'mid>high'}
ipa.rewrite("ka˧˦", "[tone=mid>high] -> e")             # 'ke'
ipa.rewrite("ka˧˦", "[vowel] -> [tone=low>high>low]")   # 'ka᷈'
ipa.rewrite("ka˩˥", "[contour=rising] -> e")            # 'ke˩˥'
```

A change the inventory cannot spell does not fire, on the same rule as a segmental one that cannot be realized. `t` plus the rising-contour caron recomposes to the registered `ť`, a different phone, and the result is checked by reading it back:

```python
ipa.rewrite("t", "t -> [contour=rising]")   # 't'  -- declined, not invented
```

### A literal may name prosody too

On the **left** it is an *additional* constraint layered over the identity match, not part of the identity. So `a` goes on matching `ˈa`, while `aː` matches only the long one:

```python
ipa.rewrite("kaː",  "aː -> a")    # 'ka'
ipa.rewrite("kˈat", "ˈa -> e")    # 'ket'
```

On the **right** a literal spells a whole unit, so its silence about prosody has to be given a meaning. It means *carry it across* — `t -> ʔ` must not shorten `tː`, since length and tone are phonemic in plenty of inventories — except for a feature one of the two sides named, which is what makes `aː -> a` shorten rather than do nothing:

```python
ipa.rewrite("kætː", "t -> ʔ / _ #")   # 'kæʔː'  -- length unnamed, so kept
ipa.rewrite("kˈaː", "aː -> a")        # 'kˈa'   -- length named, stress not
ipa.rewrite("kˈaː", "ˈa -> e")        # 'keː'   -- stress named, length not
```

A right-hand side of **more than one unit** has to say *which* of them inherits, and "carry it across" does not: `rewrite("katː", "t -> ts")` used to give `'kats'`, the geminate's length dropped on the floor, while `t -> ʔ` on the same input kept it. The answer is read off where the mark is written — before its unit (`ˈa`) or after it (`aː`). A mark written before the target lands on the first of the units replacing it, one written after lands on the last: **it stays on the side of the span it was written on**, which is what `_anchors` already says of a boundary run, applied to the marks that ride a span rather than divide it.

```python
ipa.rewrite("katː", "t -> ts")   # 'katsː'  -- written after, so it lands last
ipa.rewrite("kˈai", "a -> ai")   # 'kˈaii'  -- written before, so it lands first
```

That is one rule rather than one per feature, and it lands where each feature wants to be without either position being chosen: length at the end of a coda, stress on the nucleus. It rules out putting the mark on *all* of the new units by the same reading — that would state the length twice (`tːsː`) and put two stresses inside one syllable, and a mark is a property of the position, not of whatever fills it. Which side a mark is written on is `IPAFeatures.stress_markers`, the same read `Segment.to_ipa` uses to place the glyph, so where a mark lands and where it is spelled cannot come apart.

`[vowel length=long]` says what `aː` says, so it names length the same way: `ipa.rewrite("kaː", "[vowel length=long] -> a")` is `'ka'`.

A bare suprasegmental is not expressible on either side, and says so rather than parsing and never firing:

```python
ipa.rule("∅ -> ˈ / # _")   # RuleError: 'ˈ' is prosody with no phone under it
```

A prosodic mark is a property of a position, not a position of its own, so there is nothing for an insertion to insert. `[stress=primary]` on the unit is how that is said.

## Stress goes on the nucleus

The house convention marks stress on the **nucleus**, not at the syllable boundary, so a stressed vowel is a single unit and no syllabification is required:

```python
f = ipa.load_ipa_features()
f.normalize_stress_to_nucleus("ˌkænˈtiːn")     # 'kˌæn.tˈiːn'
f.normalize_stress_to_syllable("kˌæn.tˈiːn")   # 'ˌkænˈtiːn'   -- round-trips
```

The `.` left behind is what makes that round trip possible; it records where the syllable boundary was. Do not discard it if you intend to convert back.

## Boundaries

### A syllable dot is transparent

The dot is *optional notation*: `bʌtɚ` and `bʌ.tɚ` are the same word. If `.` blocked a context, flapping would fire on one spelling and not the other — one word, two answers, decided by whether somebody typed the dots. So context scanning **steps over** transparent units the pattern does not match:

```python
spec = "t -> ɾ / [vowel stress=primary] _ [vowel]"
ipa.rewrite("bˈʌtɚ",  spec)   # 'bˈʌɾɚ'
ipa.rewrite("bˈʌ.tɚ", spec)   # 'bˈʌ.ɾɚ'   -- same rule, same site
```

A rule may still **name** the boundary, and then it is not stepped over:

```python
ipa.rewrite("at.a", "t -> ʔ / _ .")   # 'aʔ.a'
ipa.rewrite("ata",  "t -> ʔ / _ .")   # 'ata'   -- no boundary, no match
```

### Tiers nest

The `level` feature declares its values in order — `syllable`, `word`, `phrase`, `utterance` — and is ordinal. So a boundary pattern matches its level **or stronger**: a word boundary *is* a syllable boundary.

```python
asp = "[manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary]"
ipa.rewrite("pˈɪn",   asp)   # 'pʰˈɪn'   -- the form edge is a syllable margin
ipa.rewrite("ə.tˈæk", asp)   # 'ə.tʰˈæk' -- an explicit syllable margin
```

The reverse does not hold: `#` is not matched by a mere syllable break.

Every boundary glyph declares its level, so `#` reaches all of them and no rule needs to name two:

| Glyph | `level` | also declares |
| --- | --- | --- |
| `.` | `syllable` | — |
| `#` | `word` | — |
| `‿` | `word` | `linking=+` — the absence of a *pause*, not of a boundary |
| `\|` | `phrase` | `break=minor` |
| `‖` | `utterance` | `break=major` |

The two break marks sit above `word`, which follows how they are used — `|` is written as a comma-like break between phrases — and not the chart's "minor (foot) group" label, which would put it below `word`. The reasoning is recorded in `ipa.xml` beside the declaration.

So a `#` or `.` context matches a break mark, because a phrase boundary *is* a word boundary and a word boundary is a syllable boundary:

```python
ipa.rewrite("a|b", "a -> o / _ #")     # 'o|b'   -- '|' reaches 'word'
ipa.rewrite("a|b", "a -> o / _ .")     # 'o|b'   -- and 'syllable'
ipa.rewrite("a#b", "a -> o / _ |")     # 'a#b'   -- but not the reverse
ipa.rewrite("lez‿ami", "z -> ∅ / _ #") # 'le‿ami'
```

That last one is why `‿` carries a level. It stands between two words and says they are run together; with no level, `#` did not reach it and only `%` did — and `%` also catches the syllable dot, so a word-final rule written with `%` fired at an interior dot too and the optional dot changed which rules fired.

### The edges of a form are word boundaries

`_ #` fires at the end of a form without a `#` having been typed, and `# _` at the start. The level the edge asserts is the strongest one `level` declares, so it reaches every weaker one too.

### A boundary run is one boundary

A form has **one** edge, not an unbounded run of them, and the same holds of written marks: a run of them is one boundary, and the virtual edge past the end of the form is part of any run it touches. So typing a mark the form's own edge already asserts adds no information and must not change the derivation, exactly as an optional dot must not. That is the general form of the claim above:

> **Edge redundancy.** For any rule `r` and form `f` whose ends carry no boundary run, `r(f) == strip(r("#"+f)) == strip(r(f+"#")) == strip(r("#"+f+"#"))`.

```python
ipa.rewrite("kæt",     "∅ -> ə / _ #")   # 'kætə'
ipa.rewrite("#kæt#",   "∅ -> ə / _ #")   # '#kætə#'  -- one gap, and it is the inner one
ipa.rewrite("kæt##",   "∅ -> ə / _ #")   # 'kætə##'  -- a run is still one boundary
ipa.rewrite("#kæt#",   "∅ -> ə / # _")   # '#əkæt#'  -- prothesis lands inside the word
```

Two consequences worth knowing. Which gap of a run an insertion takes is the **inner** one, because there is nothing outside the form to insert into and a schwa written outside a word mark would be a second word. And a context cannot name two boundaries in a row, since there is only one there to name: `_ # #` matches nothing at all.

The run is one boundary wherever it is read, and that includes as a **target**. A rule that restates a boundary writes one mark however many were written for it, and a rule that unwrites one reports a single change over the whole run rather than one change per mark:

```python
ipa.rewrite("a.b",   ". -> #")   # 'a#b'
ipa.rewrite("a..b",  ". -> #")   # 'a#b'   -- one boundary in, one out
ipa.rewrite("a.‿b",  "‿ -> ∅")   # 'a.b'   -- a named mark takes only its own
ipa.rewrite("a.‿b",  ". -> ∅")   # 'ab'    -- the class takes the whole run
```

The target is walked as far as the pattern matches, which is what keeps the last two apart: `.` is "syllable or stronger" and reaches every mark of the run, while `‿` names one mark and leaves the dot where it was written. The site is wider than one unit, and the *rule* still states one pattern and matches one boundary — the width is a fact about how the form was spelled, not about the rule, which is why this is not the multi-unit target [metathesis needs](calculus.md).

The edge is a **word** boundary specifically, not the top of the ladder: `_ |` does not fire at the end of a form, because a phrase break is written or it is not there. `#` is the mark a form edge is an unwritten instance of, and `ipakit.form.edge_level()` reads that off `<separators>`.

## A rule may read a tier, and may not rewrite one

A **tier** is not a rung on the boundary ladder above. `level` is ordinal — a word boundary *is* a syllable boundary — and `tier` is nominal: a syllable, a mora and a morph do not nest, and nothing orders two of them. A span on a tier is an [`Interval`](form.md#an-interval-is-carried-because-no-glyph-delimits-one) carried on a `Form`, and a rule may name one **in its context only**.

The notation is a labeled bracket, which is how prosodic constituency has been written since SPE, with the label inside it:

| term | holds where |
| --- | --- |
| `<mora` | an interval on the `mora` tier **starts** |
| `mora>` | an interval on the `mora` tier **ends** |

The labels come from `<feature name="tier">`, so a language declaring a fourth tier writes it with no code change; the brackets are notation and are spelled in `rules.py`. Angle brackets because the other two pairs mean something else — `[...]` is a feature query over a unit's bundle, `(...)` marks a context item optional — and neither is a claim about structure.

### A tier term claims a position, not a unit

Every other context item takes a unit. A tier term takes none: it says something about the **gap** the cursor is at, so `<syllable _` reads "the target begins a syllable" rather than "something precedes the target".

That is the choice that makes the read-only restriction livable, and it is worth stating why. The center of a rule is closed to a tier term, so a *per-unit* tier term could only ever describe a neighbor — and the statements that matter are about the target. "Aspirate a `t` that begins a syllable" would be unwritable. As a position term it is a claim about where the target sits, which is a context, so nothing is lost by the restriction.

Two consequences. A tier term can be conjoined with an ordinary item at the same position, because it consumed nothing: `[vowel] <syllable _` is a vowel before the target *and* an interval starting at the target. And two tier terms may sit together, which is a conjunction over one position and not a nesting — `mora> <syllable _` says a mora closes and a syllable opens where the target sits, in either written order, and says nothing about which contains which.

### It is a different claim from a boundary glyph

`.` and `#` are units the transcription spelled. An interval edge is asserted by a `Form`, and it may sit where no glyph is written — which is the whole point of carrying one. *Petite amie* is the case: the syllable `t‿a` starts inside a word, and no boundary pattern can name that position.

```python
from ipakit.form import Form, Interval

form = Form.parse("pətit‿ami")
syllables = [Interval("syllable", 0, 2), Interval("syllable", 2, 4),
             Interval("syllable", 4, 7), Interval("syllable", 7, 9)]
held = Form.of(form.units, syllables)

rule = ipa.rules.parse("t -> tʰ / <syllable _")
[s.start for s in rule.recognize(held)]        # [2, 4]
ipa.rules.spell(rule.apply(held)[0])           # 'pətʰitʰ‿ami'
```

Unit 4 is the `t` that opens `t‿a`. No spelling of a boundary reaches it — `.`, `#`, `%` and `‿` were all tried — because there is no boundary there: `‿` sits at unit 5, *inside* the syllable.

The converse holds too. A dot asserts a boundary and not a span, so a dotted form carries no interval and no tier term holds of it:

```python
dotted = Form.parse("pə.ti.t‿a.mi")
dotted.intervals                               # ()
rule.recognize(dotted)                         # []
```

Nothing is invented, here or in `form.py`: a form that asserts no interval is not given one, so a rule conditioned on a tier does not fire there — the same answer a margin-conditioned rule gives on an undotted word.

### The center is closed, and the refusal is at parse time

A tier term in the target or on the right of the arrow is refused when the rule is read, not answered when it is applied. A refusal at match time would be site-dependent: fine on one form and quietly nothing on the next.

```python
ipa.rules.parse("<mora -> d")
# RuleError: '<mora -> d' names the tier 'mora' in its target, and a rule may READ a tier and may not rewrite one.
```

The restriction is the finding rather than a caution. Kaplan & Kay's restriction is on a rule's **center** and not on its contexts ([calculus.md](calculus.md)), and what leaves the finite-state tradition is rewriting a tier rather than reading one: the multi-tape treatments go beyond regular power, and that power is required precisely for structure-modifying rules ([design/tiers.md](design/tiers.md)). So a tier read in a context costs nothing in formal power, nothing in intermediates and nothing in the derivation trace.

The same line closes a hole on the change side. A **structural** feature — `level`, `tier`, `tie`, `linking`, `break` — is a property of a boundary, a juncture or a tier rather than of a segment, so no unit carries one. A query naming one was already refused; a *change* naming one was not, and `t -> [tier=mora]` parsed, fired at every `t`, wrote into a bundle that does not exist and reported nothing.

```python
ipa.rules.parse("t -> [tier=mora]")
# RuleError: '[tier=mora]' rewrites the structural feature(s) ['tier'].
```

### A tier survives the cascade, because a rewrite rebases what it moved

A rule changes the length of the sequence an interval indexes, so a cascade that kept the spans as written would have every step after the first describing a different span. `RuleSet.derive` takes a `Form` and rebases at each step, so a rule conditioned on `<syllable` finds its sites at step ten for the same reason it finds them at step one:

```python
held = Form.of(Form.parse("pətit‿ami").units, syllables)
ipa.ruleset("p -> ∅ / # _\nt -> tʰ / <syllable _").derive(held).result
# 'ətʰitʰ‿ami'   -- the deletion moved every span left, and the tier rule still fires
```

`Rule.rewrite` is the single-rule form of it: a `Form` in, a `Form` out, spans rebased. `Rule.apply` still answers with a unit sequence, which carries no tier — that is a projection of `rewrite` rather than a gap, and the two are one implementation.

**The policy is one sentence: an interval may lose material to an edit and may never gain material from outside itself.** It is the only reading available where a rule may read a tier and may not write one, because an edit says what happened to the *units* and says nothing about the tier. Three consequences, and each is a case with a test:

- An edit **wholly outside** a span never joins it. So an insertion sitting exactly on an edge lands outside, and the epenthetic unit is on **no** tier rather than on the one it abuts — [form.md](form.md)'s rule that an unspecified tier is not invented, read from this side. Nothing said which mora it belongs to, and intervals do not tile.
- An edit **inside** a span stretches or shrinks it, coextensive or not. `a͜ɪ -> ai` under a mora gives one mora over two units. That is determined arithmetic and not a claim: "a long vowel is two morae" is a well-formedness statement about a language's tier, and deriving it here would be the structure creation a rule may not do.
- An endpoint **strictly inside a rewritten span** has no image, and `rebase` refuses with a `RebaseError` naming the span, the edit and the rule. It is reachable — a boundary target covers the whole run it opens, so `. -> #` on `a..b` is one edit over `[1, 3)` — and no shipped rule reaches it.

The first two policies and their opposites differ in **no spelling anywhere in the shipped corpus** and in the spans of a large minority of it. Only a tier read can tell them apart, which is why each is declared and tested as its own case rather than left to whichever formula fell out.

### What a tier term does not do yet

- **A term names an edge, not membership.** `<mora>` is refused rather than read as one of the two. Membership is true of nearly every position a span covers and so states almost nothing, while both cases the shipped sets reach for are edges.
- **`RuleSet.variants` refuses a form carrying an interval.** A variant is keyed by its spelling, and two branches that spell alike with different spans are two structures and one key; merging them would drop a tier reading in silence. `derive` is the cascade that carries a tier.
- **`Form.without_boundaries()` still refuses one.** Removing a position moves every index after it, and `rebase` lives beside `Edit` in the rule engine, which `form.py` sits below rather than above.
- **Association is not here at all.** What a stranded tone or a compensatory length does after a deletion is language-particular, is not endpoint arithmetic, and is the structure-modifying capability the extra formal power was for ([design/tiers.md](design/tiers.md)).

## `∅` is nothing; a zero is a position with no content

These are two different things, not two spellings of one. `∅` in a rule is **the empty string** — `rules.NULL`, alongside `0` and `Ø`. On the left it means "insert here"; on the right it means "delete this". A **zero** is a declared symbol in `ipa.xml`'s `<zeros>` block: a slot the transcription keeps open with nothing in it. `le∅ʃjɛ̃` has five sounds and six positions.

The glyph is the same character, and that is a spelling accident rather than an identity. `∅` on the left of an arrow stays the empty string — freeing it would silently change every shipped insertion rule, and `∅ -> ə` is epenthesis in two of them. A rule that wants to *emit* a zero says so in brackets, where brackets already mean *described, not spelled*:

```python
ipa.rewrite("lez", "z -> ∅ / _ #", keep_zeros=True)       # 'le'    -- the /z/ is gone
ipa.rewrite("lez", "z -> [zero] / _ #", keep_zeros=True)  # 'le∅'   -- a /z/ was here and could surface
```

`keep_zeros=True` runs through this section and the next, because what they ask about is the form a rule *wrote*. A pronunciation carries no zero, and the rewrite that takes it back out is [below](#the-surface-carries-no-zero).

The second is what a latent consonant needs. French liaison's /z/ is not absent from the word, it is unpronounced in this environment, and a derivation that records where it was can put it back. `[zero]` is read off the data — `zero` is the element class those symbols carry, and the symbol written is the one `<zeros>` declares — so neither the word nor the glyph is spelled in the engine.

A zero is a position, so it can be filled or unwritten, and it has no feature bundle to change:

```python
ipa.rewrite("le∅ʃ", "[zero] -> z")        # 'lezʃ'  -- filled
ipa.rewrite("le∅ʃ", "[zero] -> ∅")        # 'leʃ'   -- unwritten
ipa.rule("[zero] -> [voiced=+]")          # RuleError: a zero is a position with no content, so it has no bundle
ipa.rule("∅ -> [zero] / a _ b")           # RuleError: an insertion had none to lose, so there is nothing here for it to record
```

### A null is not an environment

A zero is opaque by default: it is a position, and positions block.

```python
ipa.rewrite("leʃ",  "e -> a / _ ʃ", keep_zeros=True)      # 'laʃ'
ipa.rewrite("le∅ʃ", "e -> a / _ ʃ", keep_zeros=True)      # 'le∅ʃ'  -- the zero is in the way
```

It cannot be named in an environment. All four null spellings are refused,
because an environment names what stands there and nothing stands at a
deletion site:

```python
ipa.rule("e -> a / _ ∅ ʃ")  # RuleError: 'e -> a / _ ∅ ʃ' names a null at position 11 in its environment. An environment names what stands there, and nothing stands at a deletion site; if zero-width context was meant, spell it with an optional element '(X)'.
```

Parentheses make one unit pattern a variable-width environment item. The
postfix forms are:

| Form | Units consumed |
| --- | --- |
| `(X)` or `(X)?` | zero or one |
| `(X)*` | zero or more |
| `(X)+` | one or more |
| `(X){n}` | exactly `n` |
| `(X){n,}` | at least `n` |
| `(X){,m}` | at most `m` |
| `(X){n,m}` | from `n` through `m`, inclusive |

`(X)?` preserves that spelling when a parsed query is serialized; it has the
same readings as `(X)`. Every open upper bound is capped by the form's length.
The wrapper is general over literals, bundles, brace constraints, and `*`:

```python
ipa.rewrite("cdae", "a -> b / c (d) _ e")  # 'cdbe'
ipa.rewrite("cae",  "a -> b / c (d) _ e")  # 'cbe'
```

Parentheses keep these forms distinct from bare `*`, which still means exactly
one arbitrary segment:

```python
ipa.rewrite("stra", "a -> [stress=primary] / # ([-vowel])* _")  # 'strˈa'
```


### The surface carries no zero

A zero holds a position, and holding the position is what makes a deletion site visible in a trace. A *pronunciation* has no room for a position with nothing in it. So a derivation carries the zero and the surface form does not, and what takes it out is **a rewrite**, applied after every rule of the cascade and after every step is recorded:

```python
ipa.rules.surface().rules[0].source            # '[zero] -> ∅ ; surface'
ipa.rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]")  # 'leami'
```

That it is a rewrite is the design and not the implementation. It is one rule, in this notation, run through this parser, and a caller can write it out for themselves:

```python
ipa.rewrite("le∅ami", "[zero] -> ∅")   # 'leami'
```

Three things follow from that. The projection composes, because a rule set composes. It is expressible, so [calculus.md](calculus.md)'s claim that the operations are closed over the carrier stays true of the map from a derivation to a pronunciation — a surface projection living *beside* the notation would have been an escape hatch from exactly that claim. And it reads off the declaration: `[zero]` is the element class `<zeros>` gives its members, so an inventory that declares no zero gets the empty rule set, which is the identity.

It removes zeros and **nothing else**. A constituent left holding no segment stays written, and `validate_ipa` reports it as the empty constituent it now is:

```python
ipa.rewrite("a.∅.b", "[zero] -> ∅")                       # 'a..b'
[d["code"] for d in ipa.validate_ipa("a..b")]             # ['empty_constituent']
```

Collapsing the boundary run as well would be a second statement, and this is one rule.

**`keep_zeros=True` declines it**, on `rewrite`, `derive`, `variants`, the three `RuleSet` methods and `--keep-zeros` on the command line. A caller reading a derivation wants the zero and a caller asking for a pronunciation does not, so neither may be out of reach:

```python
ipa.rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]", keep_zeros=True)  # 'le∅ami'
ipa.derive("lezami", "z -> [zero] / [vowel] _ [vowel]").steps[-1].rule     # 'surface'
```

The zero is in the trace where the rule wrote it either way — the step above it is the one that put it there, and the `surface` step is what the answer is. Where a derivation writes no zero the step is not recorded at all, so a trace of a rule set that has nothing to do with zeros is the trace it has always been, `--all` included.

## What a rule can do

```
t -> ɾ                       feature-equivalent literal substitution
t -> [manner=tap voiced=+]   a feature change
aː -> a                      a literal naming prosody on the left
[vowel] -> [length=long]     a prosodic change
[vowel] -> [stress=∅]        clearing prosody
∅ -> ə / C _ C               epenthesis  (insertion)
ə -> ∅ / ˈV C _              elision     (deletion)
z -> [zero] / _ #            latency     (a recorded empty position)
n -> [place=α] / _ [place=α] assimilation (an agreement variable)
```

A feature change is realized through `respell` where the result is a **registered** phone, and otherwise by composing the marks that declare it:

```python
f.respell("l", velarized="+")            # 'ɫ'   -- registered wins
f.respell("t", release="aspirated")      # None  -- tʰ is not registered
f.compose_unit("t", release="aspirated") # 'tʰ'  -- composed from declared marks
```

`compose_unit` asks `declaring_mark` which glyph carries a value (most specific first), emits marks in the order `<modes>` declares, and verifies by reading the result back. A change the inventory can spell **neither** way does not fire, rather than inventing a symbol.

**A change that is already true is a no-op**, on both routes. `respell("ɫ", velarized="+")` has always been `'ɫ'`; `compose_unit` used to append the mark anyway, so a rule firing on a unit that already carried the value doubled it — the shipped American English set spelled *hidden* `ˈhɪdⁿn̩̩`, because its nasal-release and syllabic-nasal rules both reach the same nasal, and the German set wrote a devoicing ring on consonants that were voiceless to begin with. The read-back could not see it: a doubled mark reads back carrying the requested value and moving nothing, so the guard measured the bundle while the defect was in the spelling, and `validate_ipa` was reporting `duplicate_diacritic` all along.

```python
f.compose_unit("ɪ̃", nasalized="+")                   # 'ɪ̃'   -- not 'ɪ̃̃'
f.compose_unit("s", voiced="-")                       # 's'   -- /s/ is voiceless already
f.compose_unit("ɪ̃", nasalized="+", release="aspirated")  # 'ɪ̃ʰ'  -- writes only the new half
```

A change naming a *prosodic* feature takes a third route, because neither of those two can carry it — and both are right about what they spell. Prosody lives on the unit, outside the feature bag, so `respell` refuses the key rather than letting it into a bundle it is defined to be outside of, and `compose_unit` verifies *through* the bag and therefore answers `None`:

```python
f.respell("a", length="normal")     # ValueError: respell cannot write ['length']
f.compose_unit("a", length="long")  # None  -- verified through the bag
```

Writing prosody means changing `Segment.prosody`, which is what `ipakit.form.with_prosody` does. A change may name both namespaces at once and is split by declared mode, so each half goes where it can be realized: `[vowel] -> [backness=back length=normal]` takes `kaː` to `kɑ`.

That read-back checks that nothing *else* moved, not only that the request landed. Some marks legitimately say more than one thing: the devoicing ring declares `phonation="devoiced"` and `voiced="-"`, which is one glottal fact written at two granularities, and refusing every surplus would refuse `ɹ̥` and stop approximant devoicing firing. Which dimensions stand in that relation is declared in `ipa.xml`'s `<projections>` block, so a mark whose surplus is a genuine second dimension is refused instead: the linguolabial mark is `place="bilabial"` *and*, independently, `articulator="tongue-tip"`, so `compose_unit("s", place="bilabial")` is `None` rather than `s̼`.

### A change modifies what the rule matched

A bracketed right-hand side does not build a segment. It takes the unit the rule matched and changes what the rule named, so everything the rule said nothing about survives:

```python
ipa.rewrite("aʃa", "ʃ -> [voiced=+]")   # 'aʒa'  -- grooved, postalveolar, fricative kept
ipa.rewrite("aʈa", "ʈ -> [voiced=+]")   # 'aɖa'  -- and retroflex
```

That reading wants a unit to modify, and an **insertion** matches none. `∅ -> [manner=plosive]` parsed, found its sites and produced no edit — a rule its author believed was firing, doing nothing and saying nothing:

```python
ipa.rule("∅ -> [manner=plosive] / a _ t")
# RuleError: inserts a unit and then describes it with a feature change...
```

The other reading — *insert the segment this bundle names* — is not available, and not because resolving it would be awkward. A query describes a class: `[manner=plosive]` holds every plosive the inventory registers, and narrowing it to a place and a voicing still holds several. Written out in full it is no better, because a tied diphthong states its first element's features and nothing separates the two, so a phone's own complete bundle need not pick that phone out again. A bundle does not determine a segment at any degree of specification, and an engine that picked one would be choosing rather than reading. The unit to insert is spelled, prosody and all:

```python
ipa.rewrite("ata", "∅ -> t / a _ t")   # 'atta'
ipa.rewrite("at",  "∅ -> ˈa / # _")    # 'ˈaat'
```

Three refusals say the one thing between them, and it is worth reading as one: a modification needs a term to modify. A boundary has no bundle, a zero has no content, and an insertion has no matched unit at all.

Not expressible, deliberately: **metathesis** (reordering) and **iterative within-rule spreading** (harmony as a single rule — an ordered cascade says the same thing). SPE's **agreement variables** used to stand third on that list, and [now they are notation](#a-rule-may-bind-a-value-and-re-use-it); the shipped English set states nasal place assimilation once as a result. Metathesis did **not** come with them, and the two are worth keeping apart because they rhyme: a variable copies a feature *value* between positions the rule matched one at a time, where metathesis reorders the positions themselves, which needs a target spanning more than one unit. A pattern constrains one unit, so `ab -> ba` is refused exactly as it was before. [calculus.md](calculus.md) states those as claims about the algebra's reach, and adds the two that optionality brings: no constraint on the *result* of several optional choices, and no ranking over the set.

## Rules are ordered

Classically, and here. Each rule sees the previous rule's output, which is where feeding and bleeding live:

```python
fed     = ipa.ruleset("a -> i / _ t ; raising\nt -> ʔ / i _ ; glottalling")
starved = ipa.ruleset("t -> ʔ / i _ ; glottalling\na -> i / _ t ; raising")
fed.apply("at")      # 'iʔ'  -- raising creates the environment glottalling needs
starved.apply("at")  # 'it'  -- it arrives too late
```

Within a single rule, every site is found against a **snapshot** before any is rewritten, so a rule cannot read its own output and a pass terminates by construction:

```python
ipa.rewrite("eaaa", "a -> e / e _")   # 'eeaa', not 'eeee'
```

## A rule may be optional, and then the answer is a set

`~>` in place of the arrow says the rule *may* fire rather than that it does. One form no longer determines one form, so the answer is a **set** of forms and `variants` is where it lives:

```python
ipa.rewrite("kæt", "t ~> ʔ / _ #")            # 'kæt'
ipa.variants("kæt", "t ~> ʔ / _ #").forms     # ('kæt', 'kæʔ')
```

**Optionality is per site.** Each site the rule finds branches on its own, which is what French *devenir* needs — [dəvəniʁ], [dəvniʁ] and [dvəniʁ] are all real and the fourth combination is not:

```python
ipa.ruleset("french-liaison").variants("dəvəniʁ").forms
# ('dəvəniʁ', 'dəvniʁ', 'dvəniʁ')
```

**An optional rule does not fire under `rewrite`, `derive` or `rules apply`.** One form has to come out of those, so a choice has to be taken, and the null choice is the only defensible one — which makes `variants(f)[0]` exactly `apply(f)`, by construction rather than by agreement. A full trace says *not taken*, which is a different report from *no change*:

```python
ipa.derive("kæt", "t ~> ʔ / _ #").trace(all_steps=True)
# 'kæt\n  t ~> ʔ / _ #  (not taken)\n      -\n  = kæt\n  (no rule fired)'
```

The four spellings are one rule: `~` before any arrow makes it optional, and `~>` is the ASCII arrow with a wavy shaft. `~` spells nothing in the inventory — no phone, no diacritic, no separator, no break mark, and `ipa.xml` does not contain the character at all — so it collides with nothing that can appear in a rule.

The set is always finite and always ordered deterministically, and it is bounded by a **visible** cap that a truncated answer reports rather than swallows. All of that, with the closure, composition and associativity claims and what the algebra cannot express, is [calculus.md](calculus.md).

## Rule sets

One rule per line. Blank lines are skipped, and a line **beginning** with `#` is a comment — only at line start, since `#` is also the word boundary. A line whose whole left-hand side is `#` is a rule rather than prose: `# -> ∅` unwrites a word mark and `# -> ‿` restates one as the linking mark. A target is everything left of the arrow, so the mark is a target exactly when nothing else stands there, and prose opening with `#` has words before its arrow if it carries one at all.

```python
ipa.ruleset("""
# American English, abbreviated
t -> ɾ / [vowel] _ [vowel -primary -secondary]                 ; flapping
[manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary] ; aspiration
""")
```

Sets can ship as data. `ipakit/data/rules/*.rules` are loaded by name:

```python
from ipakit import rules
rules.available()                       # ['american-english', 'french-liaison', 'german-final-devoicing', 'japanese-moraic', 'spanish-accented-english']
rs = rules.shipped("american-english")
rs.apply("pˈɪn")                        # 'pʰˈɪ̃n'
```

## A worked example: broad to narrow

The shipped set takes a **broad** (phonemic) reading to a **narrow** (phonetic) one — the allophonic detail that is predictable from context:

```
/pˈɪn/          -> [pʰˈɪ̃n]      aspiration, then vowel nasalization
/spˈɪn/         -> [spˈɪ̃n]      no aspiration: the margin is taken by /s/
/bˈʌtɚ/         -> [bˈʌɾɚ]      tapping
/kˈæt/          -> [kʰˈæt̚]      aspiration and an unreleased coda
/klˈin/         -> [kl̥ˈĩn]      approximant devoicing after a voiceless stop
/fˈʊl/          -> [fˈʊɫ]       dark l
/ˈbʌ.tn/        -> [ˈbʌ.tⁿn̩]    nasal release, syllabic nasal
/pə.tˈe͜ɪ.to͜ʊ/   -> [pə.tʰˈe͜ɪ.ɾo͜ʊ] aspiration and tapping in one word
```

Two things in there are worth copying.

**Aspiration is stated positively.** Not "not after /s/" but "at a syllable margin" — in `spin` the margin is *occupied* by /s/, so /p/ is not at one. Classical SPE negates feature **values**, not context **positions**, so the positive statement is the idiomatic one. Feature-value negation (`[-voiced]`) is available; position negation is not, and this is why it has not been needed.

**Tie your diphthongs.** Whether a diphthong is tied changes what a rule sees, because untied `eɪ` is two units and a stress mark lands on the first of them. Vowel nasalization is the clear case: `ˈkaɪn` nasalizes its second element to `ˈkaɪ̃n`, while the tied `ˈka͜ɪn` is one unit the composed mark does not read back on, and is left alone.

```
/ˈkaɪn/    -> [ˈkaɪ̃n]     untied: the rule reaches the second unit
/ˈka͜ɪn/    -> [ˈka͜ɪn]     tied: one unit, and the mark does not compose
```

Tapping is not an example of this, because it asks nothing about stress on its left: `/pə.tˈeɪ.toʊ/` and `/pə.tˈe͜ɪ.to͜ʊ/` both flap.

Do **not** reach for `ipakit.add_ties()` to do it. Despite the name it ties *every* adjacent pair, not the registered ones: `add_ties("kæt")` is `k͡æ͡t`, and following that advice on the example above gives `p͡ə.tʰˈe͜ɪ.t͡o͜ʊ`, where tapping does **not** fire. Its docstring is accurate — it ties base phones *within a multi-phone segment* — but it is not a word-level tool. Tie the diphthongs you mean.

## Underspecification

A word written without interior dots leaves its interior margins **unspecified**, and a margin-conditioned rule does not fire there rather than guessing:

```python
ipa.rewrite("ə.tˈæk", asp)   # 'ə.tʰˈæk'  -- margin stated
ipa.rewrite("ətˈæk",  asp)   # 'ətˈæk'    -- margin unspecified, so no claim
```

This is deliberate. The alternative — treating absence as "one syllable" — invents structure the transcription never asserted.

## From a shell

`ipakit rules` is the notation above with no Python around it. Rules come from exactly one of `-r NOTATION` (repeatable, and repeats are an *ordered* cascade), `-s NAME` (a shipped set) or `--file FILE`. Forms are positional, or one per line on stdin when none are given.

**Quote the rule.** It contains `#`, `|` and `;`, all of which a shell reads. Single quotes throughout, and a `#` inside them is the word boundary, not a comment.

```console
$ ipakit rules list
american-english
french-liaison
german-final-devoicing
japanese-moraic
spanish-accented-english
$ ipakit rules apply -s american-english pˈɪn
pʰˈɪ̃n
$ ipakit rules apply -r 't -> ʔ / _ #' kæt
kæʔ
```

`trace` is the affordance a human wants, because a cascade's interesting output is not the answer but the account of it. Only the rules that fired are listed; `--all` adds the ones that did nothing, which is what you want when a rule you expected did not fire. Those are marked `(no change)` **after** the name — a trace is read by scanning down the names, so the marker cannot be a prefix that moves the column they sit in. Marking after the name is also what keeps the default listing byte-identical, since every step it shows has fired and writes no marker at all.

```console
$ ipakit rules trace -s american-english pə.tˈe͜ɪ.to͜ʊ
pə.tˈe͜ɪ.to͜ʊ
  tapping
      tapping: t -> ɾ @6
  = pə.tˈe͜ɪ.ɾo͜ʊ
  aspiration
      aspiration: t -> tʰ @3
  = pə.tʰˈe͜ɪ.ɾo͜ʊ
```

`variants` is `apply` for a set that marks a rule optional. The first line is what `apply` prints, and the count line says whether the answer is complete — a capped set of pronunciations reads exactly like an exhaustive one, so it is never left to the caller to wonder.

```console
$ ipakit rules variants -s french-liaison pətit dəvəniʁ
pətit: 2 variants
  pəti
  pti
dəvəniʁ: 3 variants
  dəvəniʁ
  dəvniʁ
  dvəniʁ
```

`--keep-zeros` is the surface rewrite declined, on the three commands that print a derived form. What it prints is the derivation's own answer, zero and all:

```console
$ ipakit rules apply -r 'z -> [zero] / [vowel] _ [vowel]' lezami
leami
$ ipakit rules apply --keep-zeros -r 'z -> [zero] / [vowel] _ [vowel]' lezami
le∅ami
```

`recognize` is the left of the arrow alone — where the environment holds, with nothing rewritten. Each line is the rule, the index of the target, the target, and the neighbors that licensed it; `#` there is the form's own edge, matched without one having been typed.

```console
$ ipakit rules recognize -r '[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing' atapa
atapa: 2 sites
  voicing  @1  t  a _ a
  voicing  @3  p  a _ a
```

With a rule *set*, every rule is asked against the form **as given**. No rewriting happens, so the ordering effects `apply` and `trace` show are absent: a rule that fires only on an earlier rule's output recognizes nothing here. A form with no site is reported as such and is not an error.

The indices count rule units, which keep the boundaries `convert tokenize` drops:

```console
$ ipakit rules units bˈʌ.tɚ
b ˈʌ . t ɚ
```

Forms on stdin make it a filter:

```console
$ printf 'pˈɪn\nbˈʌtɚ\nkˈæt\n' | ipakit rules apply -s american-english
pʰˈɪ̃n
bˈʌɾɚ
kʰˈæt̚
```

`-j` gives every subcommand a machine-readable form: one row per input form for `apply`, `trace`, `recognize` and `units`, so the shape does not change with the number of forms. A malformed rule is reported as `Error: ...` on stderr with exit status 1, never a traceback.

## Known limits

Recorded so they are not discovered the hard way:

- **Boundaries are atomic separators, not a balanced bracketing.** An edge and a separator are one character doing two jobs, so nothing can be unbalanced and a balance check would have nothing to reject: `##kæt` and `kæt..dɒɡ` parse without complaint (`validate_ipa` warns `empty_constituent` on both; neither layer rejects them). They are also not *counted* — a run is one boundary (above) — so they derive as `#kæt` and `kæt.dɒɡ` do. `Form.tree()` records which delimiter supplied each end of a node's span (`Node.opened_by` / `closed_by`, `None` for the form edge, `Node.asserted` for "both were written"), but that is provenance on an already-atomic reading, not a bracketing the parser enforces. The reasoning, and what a bracketing would and would not buy, is in [form.md](form.md).
- **A prosodic mark is not a position**, so `∅ -> ˈ`, `ˈ -> ∅` and a bare `ˈ` in a context are refused rather than expressible. Prosody rides on a unit, and `[stress=primary]` / `[stress=∅]` on the unit is how it is written (above).
- **A prosodic composition that collides with a registered symbol declines.** `t` plus the rising-contour caron recomposes to `ť`, which is a different phone, so `t -> [contour=rising]` does not fire. The set is whatever the inventory makes it, because the check is a read-back rather than a list, and `tests/test_rules.py` sweeps every phone against every prosodic value and names each pair that declines.
- **There is no notation for a phrase boundary by level.** `#` and `.` name a level; `|` and `‖` are matched as the literal marks they are. A bracketed `[level=phrase]` never matches, because a query is compared against a segment's feature bundle and a boundary has none.
- **Variable width is recognition sugar only.** `(X)` and `(X)*` are refused in a rule target, nested variable-width elements are refused, and a change cannot use a variable bound only inside one. An absent element cannot supply a rewrite value. Parentheses in a rule's *name* are untouched, since the name is past the `;` and never reaches the context splitter.
- **An agreement variable stands for a feature value, not for a segment.** `[place=α]` is expressible; "a copy of whatever consonant stood there" is not, so the shipped French set still writes one liaison rule per latent consonant. A variable also ranges over one feature, is refused where nothing binds it or where it occurs once, and `-α` is legal only for a binary feature (above). Every one of those is a parse-time refusal rather than a rule that fires at some sites and not others.
- **The surface rewrite is applied per call**, like the cap, so splitting one cascade into two calls applies it twice and a zero written by the first half is gone before the second half can read it. `keep_zeros=True` on the inner call is the repair, and naming the intermediate as a derivation rather than a pronunciation is what it says.
- **An insertion has no unit to modify.** A bracketed right-hand side changes the unit the rule matched, so `∅ -> [manner=plosive]` is refused: there is no match to change, and a query describes a class rather than naming a segment to place. Spell the unit — `∅ -> t`, or `∅ -> ˈa` where the prosody matters. This is the parse-time member of a family whose other two are just below; what a rule *cannot* be told at parse is whether a change it can express will be spellable at a given site, and that one declines per site.
- **A zero cannot be inserted, and it has no bundle.** `∅ -> [zero]` is refused — a zero records that a position had content and now has none, and an insertion had none to lose — and so is `[zero] -> [voiced=+]`, for the reason a feature change on a boundary is refused. Filling one (`[zero] -> z`) and unwriting one (`[zero] -> ∅`) are the two things that work.
- A `Derivation`'s `start` is the form **as the engine read it**, not the string handed in. Reading drops what the inventory does not register, with a warning, and a trace whose first line is not what the first rule saw would account for a derivation that did not happen.
- `Form.rebuild` is an inverse up to spelling; `Boundary` equality is not object equality with the original. It does reproduce each boundary *unit* — text and declared features — from `Boundary.features`; rebuilding from `Boundary.level` alone put `‿` back as a plain word boundary with its `linking=+` gone, the same spelling describing a different unit.
- `Boundary.level` falls back to `word` where a mark declares none. Every shipped glyph declares one, so only a hand-made `Boundary`, or a mark added without a level, reaches it.
- **Whitespace is not declared in `ipa.xml`**, so `units()` assigns it the level a form edge delimits (`form.edge_level()`, `word` today) rather than a literal. A space and the form's own end therefore assert the same level by construction, which is what stops a context from matching one and not the other.
- The CLI parses a rule per invocation, so applying a set to a large corpus pays that parse once and the inventory load once; it is a filter, not a batch engine.
