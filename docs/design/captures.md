# Captures in the rewrite notation: assessment

Should ipakit's rewrite notation gain **captures** — terms of the match that the right of the arrow can name, copy and reorder, in the way PCRE writes `s/(a)(b)/\2\1/` and SPE writes `1 2 → 2 1`?

**Verdict: ADOPT THE REFERENCE. REFUSE THE SPAN.** They are two changes, they have been travelling under one name, and only one of them earns its keep. A *reference* lets the right of the arrow name a term the left matched; a *span* lets the target cover more than one unit. Metathesis needs both. Everything else needs only the first, and the first turns out not to be a new mechanism at all — the right of the arrow is **already** a capture with exactly one implicit term. `ʃ -> [voiced=+]` gives `aʒa`, keeping grooved, postalveolar and fricative, because a bundle on the right *modifies the matched unit* rather than constructing a segment from nothing. So the proposal is not "add captures beside what is there"; it is "let the one term that is already captured be named, and let there be more than one of them".

**And the case that motivated the question does not survive contact with the engine.** [calculus.md](../calculus.md) lists "a variable over a whole segment" as something the notation cannot express. Measured, it can: whole-segment copy is writable today by enumerating the feature space in agreement variables, and the rule is 526 characters long, uses 40 variable occurrences, fits inside the free Greek alphabet by two letters, and gives every right answer. The segment variable is not *missing*. It is *unwritable*. A reference is an abbreviation of a construction the notation already licenses, at about 17:1 — which is also the proof that it costs the calculus nothing, since anything it can say was already sayable.

**Where the reference is a genuine gain is the insertion**, because an insertion has no matched unit to modify, and there the same construction goes silent: a bundle on the right of `∅ ->` parses, finds its sites, and produces no edit. That is a live silent no-op of the shape [reviewing.md](../reviewing.md) exists to catch, and the general reading closes it — a modification with no term to modify has no referent, and should be refused rather than declined.

**The shipped French liaison set still does not collapse, and that is the measurement that overturns the expected answer.** The four liaison rules are one rule per latent consonant, and the brief's hypothesis was that a capture states them once. It does not, because the term would have to match exactly */z t n p/ and no feature query picks that set out. Widened to `[-vowel]`, one rule per latent consonant becomes one rule that is wrong on 2 of the set's 29 corpus words; widen the deletion half to match and it is wrong on 9. What blocks the French set is not the missing capture. It is the missing **brace** — SPE's disjunction, `{ }` — and that is a different and higher-value change.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Does the notation have numbered terms in the literature? | **Yes.** The transformational format numbers the terms of a structural description and writes the change over those numbers. |
| Does the numbering cover context as well as target? | **Yes**, verified from Chomsky 1957: pure context variables carry numbers 1 and 4 in `1 2 3 4 → 1 3 2 4`. |
| Is copying separate from reordering in the source notation? | **Yes.** A number may appear twice in the change (Kenstowicz & Kisseberth 1979: 371), which is copying and not permutation. |
| Is an ordinary rewrite rule already a capture? | **Yes.** A bundle on the right modifies the matched unit. 17 of the 86 shipped rules are that shape. |
| Is "a copy of whatever segment stood there" expressible today? | **Yes, on a substitution.** 20 declared segmental keys, 20 agreement variables, 526 characters, and it gives `akto → atto`, `aknu → annu`, `atma → amma`. |
| Is it expressible on an insertion? | **No, and it fails silently.** 1 site found, 0 edits, no diagnostic. |
| Would the shipped French liaison set collapse to one rule? | **No.** 2 of 29 corpus words wrong with the liaison half widened, 9 of 29 with both halves widened. |
| How many shipped rules are repeated because a segment must be *copied*? | **4**, all in one family. |
| How many are repeated because the notation cannot say *or*? | **27**, in nine families across four sets. |
| Does a reference threaten finiteness? | **No.** A copying rule is in the growth class insertion already occupies: identical variant counts and form lengths, measured. |
| Does a *span* threaten anything? | **Yes** — the non-overlap invariant in `Query.sites`, and four types' contracts. |
| Does any of it reach the metric? | **No.** `ipakit.rules` is not in `ipakit/metric.py`'s module-level import closure, and no bundle key is added. |
| Does α-notation become sugar over captures? | **No.** α is symmetric and constrains recognition; a reference is directional and only acts. |

## Sources

- Chomsky, *Syntactic Structures* (Mouton 1957), Appendix II, "Transformational Structure", pp. 111–114 — read in full text; the numbered structural analysis and structural change.
- Chomsky & Halle, *The Sound Pattern of English* (1968) — pp. 361, 427. **Not read directly.** The copy is borrow-restricted and every mirror reachable was dead, so all *SPE* page references here are secondary, and each is corroborated by at least two of the sources below.
- Kenstowicz & Kisseberth, *Generative Phonology: Description and Theory* (Academic Press 1979), pp. 369–371, 380 — the transformational format in phonology, and the statement that the `A → B / X _ Y` format cannot express reordering.
- Buckley, "Metathesis", ch. 59 of *The Blackwell Companion to Phonology* (Wiley-Blackwell 2011): <https://www.ling.upenn.edu/~gene/papers/Buckley2011_metathesis.pdf>
- Hume, *Metathesis: Formal and Functional Considerations*, in Hume, Smith & van de Weijer (eds.), *Surface Syllable Structure and Segment Sequencing*, HIL Occasional Papers, Leiden 2001: <https://metathesisinlanguage.osu.edu/pdfs/hume_metathesisS5.pdf>
- Zuraw & Martin, *SPE rule notation review*, UCLA Ling 200A, Fall 2004: <https://linguistics.ucla.edu/people/zuraw/200A_2004/0203RuleNotation.pdf> — §8 Greek letters, §9 parentheses, §10 braces, §11 subscripts, §12 star, §13 angle brackets, §14 transformational rules.
- Parker, *Handouts for Advanced Phonology: A Course Packet*, Dallas International University, p. 18: <https://www.diu.edu/documents/introductory%20phonology%20course%20packet.pdf>
- Kaplan & Kay, "Regular Models of Phonological Rule Systems", Computational Linguistics 20(3), 1994: <https://aclanthology.org/J94-3001.pdf>
- Chandlee, *Strictly Local Phonological Processes* (dissertation, Delaware 2014), pp. 63–64, 91, 107: <https://www.jeffreyheinz.net/advisees/2014_JaneChandlee_dissertation.pdf>
- Chandlee & Heinz, "Bounded copying is subsequential: implications for metathesis and reduplication", SIGMORPHON 2012: <https://aclanthology.org/W12-2306/>
- Gerdemann & van Noord, "Transducers from Rewrite Rules with Backreferences", EACL 1999: <https://aclanthology.org/E99-1017/>

## 1. The precedent is real, and it is a second rule format

The owner's framing is right and the sources bear it out, including on the detail that decides the design: **the numbering covers the whole structural description, context included.**

The clearest verified instance is not phonological. Chomsky's Auxiliary Transformation — affix hopping — is stated in *Syntactic Structures* Appendix II as a structural analysis whose terms are numbered left to right and a structural change written over those numbers, and two of its four terms are pure context variables:

```
20. Auxiliary Transformation -- obligatory:
    Structural analysis:  X  --  Af  --  v  --  Y
    Structural change:    X₁ -- X₂ -- X₃ -- X₄  →  X₁ -- X₃ -- X₂ # -- X₄
```

That is `1 2 3 4 → 1 3 2 4` with the numbers written as subscripts, and `X` and `Y` — the material the rule does not touch — carry numbers 1 and 4 exactly as the affected terms carry 2 and 3. In the transformational format there is no separate context: the string is analyzed into consecutive terms and any of them may be referred to in the change. ipakit's `/ X _ Y` layout is therefore a *presentation* of such a description in which `_` marks which term is the target, and it has to be read that way before a rule can name a context term — which is exactly what the French liaison rule wants to do.

The phonological adaptation writes the numbers as bare integers under the terms. The UCLA graduate handout gives the shape under the heading **Transformational rules** — "useful for metathesis, coalescence… anything where more than one segment is affected at once":

```
Structural description:   [+syll +low]   [+syll +hi αround]
                                1                2

Structural change:        1 2  →  [–lo +long αround αback] ,  Ø
```

Hume gives the minimal metathesis case, attributed to Chomsky & Halle 1968, and Buckley the three-term version:

```
s   k                             s   k   t
1   2   →   2   1                 1   2   3   →   2   1   3
```

Buckley's gloss is the one to keep: *"The need for indexation distinguishes metathesis from most other processes, such as insertion, deletion, and featural assimilation. In those sorts of changes, whatever elements of the representation remain after the change maintain their relative ordering."*

Five conventions of that format matter for what follows.

**Every term is numbered, including boundaries.** Parker's course packet is explicit that the numbers "index each element (**segment and/or boundary symbol**)", and Kenstowicz & Kisseberth's copying rule numbers a stem bracket and a `#`. So a boundary is a term like any other in the source notation — which is a place ipakit must diverge, for the reason §11 gives.

**Deletion is written by putting Ø in the term's slot in the change**, as the UCLA example does for term 2 and Parker's coalescence rule does for the nasal. It is not written by omitting the number; omitting it would be ambiguous with a change that says nothing about that term.

**Insertion introduces material in the change that has no number in the description**, since there was nothing there to number — the same asymmetry ipakit already has between `t -> ʔ` and `∅ -> ə`.

**A number may appear twice in the change, and that is copying rather than reordering.** Kenstowicz & Kisseberth 1979: 371 give it directly:

```
SD    V   C   C ] ] #   C
SI    1     2     3     4
SC    1   2 1     3     4
```

That is a term written back into the string beside itself, which is the operation the French liaison rule performs and the one a regex backreference is usually reached for. It is worth separating from metathesis in the source notation as firmly as this document separates them in the target one.

**A term is one position regardless of how many segments it spans.** SPE's abbreviatory devices — braces, subscripts `C₀`, the star — let a single term stand for a set of strings, and the syntactic variables `X`, `Y`, `Z`, `W` stand for arbitrary strings including the empty one. That is the one part of the convention ipakit must not adopt wholesale; §9 says why.

The statement that the ordinary format cannot express reordering is Kenstowicz & Kisseberth's, at p. 370, and it is worth quoting because it is the claim this whole assessment is downstream of:

> …metathesis differs from most of the processes described in this book in that it affects more than a single segment. Hence, such rules appear to motivate a rather different format for expressing rules. … But there is no way to express such a change in relative ordering directly by the rule format x → y / __ z.

*SPE* is of two minds about the phenomenon — p. 361 calls metathesis "a perfectly common phonological process", p. 427 "a marginal type of phenomenon" — which is worth knowing before treating either as the position.

## 2. The right of the arrow is already a capture

The engine does not construct a segment from the right of the arrow. It modifies the one the rule matched:

```
ʃ -> [voiced=+]   on 'aʃa'  ->  'aʒa'    grooved, postalveolar, fricative all survive
ʈ -> [voiced=+]   on 'aʈa'  ->  'aɖa'    retroflex survives
ʃ -> t            on 'aʃa'  ->  'ata'    a literal replaces outright
```

`Action.edit` reaches that through `features.respell(target.core, **segmental)`, falling back to `compose_unit`, and both of those take the existing phone and change what the rule named. So a feature change is a capture with modification whose term is implicit, and there can only ever be one of it.

Read that way, the three unrelated readings the right of the arrow currently has collapse into one. A right-hand side is a **sequence of terms**; each term is a literal, or a reference to a numbered term of the description, optionally modified by a bundle. Then:

| written today | under the general reading |
|---|---|
| `t -> ʔ` | one literal term, no reference |
| `t -> ts` | two literal terms |
| `t -> [voiced=+]` | one term: a reference to the target, modified |
| `t -> ∅` | the empty sequence |

**No shipped rule means anything different under that reading**, and that was checked rather than assumed. Across the five sets there are 86 rules — 48 literal substitutions, 17 feature changes, 13 insertions, 8 deletions — and **zero** insertions carrying a bundle right-hand side, which is the only shape where the sugar and the general form could come apart. The bare bundle stays exactly what it is; it acquires a longer spelling it does not have to use.

Two existing refusals stop being special cases and become instances of one rule. `_check_no_exchange` refuses `. -> [level=word]` because "a query is compared against a feature bundle and a boundary has none"; `_check_zero_target` refuses `[zero] -> [voiced=+]` for the same reason. Under the general reading both are the single statement **a term with no bundle cannot be modified**, which is a better thing to have written down once than twice.

And one live silence stops being silent. Today:

```
'∅ -> [voiced=+] / a _ a'   parses,  sites: 1,  edits: 0,  rewrite('aa') == 'aa'
```

Recognition succeeds, the action declines, and nothing says so. Under the general reading that rule names a modification with no referent and is refused at parse — the same treatment `_check_variables` gives a variable the left never bound, and for the same reason: a rule that quietly does nothing is worse than a rule that does not parse.

## 3. The segment variable is not missing; it is unwritable

This is the measurement that changes the shape of the recommendation, and it was a surprise.

[calculus.md](../calculus.md) says: *"`[place=α]` binds a value of one declared feature. 'A copy of whatever consonant stood there' is a variable over a segment, and there is no such term."* The first sentence is true and the second is not. A variable binds a value of one feature — so bind one for every feature, and the conjunction of them is the segment.

It works because binding is by first occurrence in the rule and a change is not a binder. Put the variables in the right context and in the change, leave the target unconstrained, and every feature of the following segment is copied onto the preceding one. That is total regressive assimilation, the process α-notation is supposed not to reach:

```
20 declared segmental keys, 22 free Greek letters

[-vowel] -> [airstream=α centralized=γ channel=δ fronting=ε height-mod=ζ labialized=η
  labio-palatized=ι manner=κ mid-centralized=λ nasalized=μ palatalized=ν pharyngealized=ξ
  place=ο retroflex=π rhotacized=ρ rounded=ς syllabic=σ tongue-root=τ velarized=υ voiced=φ]
  / _ [-vowel airstream=α centralized=γ channel=δ fronting=ε height-mod=ζ labialized=η
  labio-palatized=ι manner=κ mid-centralized=λ nasalized=μ palatalized=ν pharyngealized=ξ
  place=ο retroflex=π rhotacized=ρ rounded=ς syllabic=σ tongue-root=τ velarized=υ voiced=φ]

526 characters on one line (wrapped here), 40 variable occurrences, parses: YES

  akto -> 'atto'      aknu -> 'annu'      aspa -> 'appa'
  aʃta -> 'atta'      atma -> 'amma'
```

Every one of those is the right answer. Compare the one-variable rule a reader would actually write, which copies place and leaves everything else where it was:

```
[-vowel] -> [place=α] / _ [-vowel place=α]

  akto -> 'atto'   (right, by luck)      aknu -> 'atnu'   (wrong; /nn/ is wanted)
  aspa -> 'aspa'   (no place to copy)    aʃta -> 'asta'   (place copied, channel not)
```

Three things follow.

**A reference is an abbreviation, not an extension.** `[-vowel] -> \1 / _ \1[-vowel]` is 30 characters against 526, and says the same thing. Everything [calculus.md](../calculus.md) claims — closure, associativity, `variants(f)[0].form == apply(f)`, finiteness, the cap — is claimed of a language that already contains the long form, so no claim can move. That is a stronger guarantee than any sweep could give, and it is the single best argument for the reference half.

**The bound is fragile and nobody is watching it.** The construction fits because there are 22 free Greek letters and 20 declared segmental keys. The margin is two, and both sides move: declaring a feature narrows it, and so does registering a Greek letter as a phone — `β`, `θ` and `χ` are phones already and are refused by name for exactly that reason. A twenty-first segmental feature makes total assimilation inexpressible, silently, in a way no test would notice.

**The closure-list entry should be corrected either way.** "There is no such term" should become something like *there is no such term, and the space it would abbreviate is writable one feature at a time*, with the rule above as the evidence. The current wording is the kind of claim that a reader builds on.

## 4. Where it actually stops: an insertion has no term to modify

Run the same enumeration on the French liaison rule, which is an insertion:

```
∅ -> [airstream=α … voiced=φ] / [-vowel airstream=α … voiced=φ] ‿ _ [vowel]

parses: YES
  lez‿ami       sites=1  edits=0  ->  'lez‿ami'
  pətit‿ami     sites=1  edits=0  ->  'pətit‿ami'
  mɔ̃n‿ami       sites=1  edits=0  ->  'mɔ̃n‿ami'
  tʁop‿ɛmabl    sites=1  edits=0  ->  'tʁop‿ɛmabl'
```

Recognition is perfect — the variables bind, the site is found, the environment holds — and the action has nothing to apply the bundle to, so it returns `None` at every site and the rule spells nothing. That is the same silence as `∅ -> [voiced=+] / a _ a`, arrived at from a real analysis rather than from a typo.

So the line the architecture actually draws is not between "one unit" and "more than one". It is between **modifying a term that is there** and **placing a term that is not**:

| | expressible today | with a reference |
|---|---|---|
| substitution: whole-segment copy onto the target | yes, at 526 characters | yes, at 30 |
| insertion: whole-segment copy into a new position | **no — silent** | yes |
| reordering: two terms exchanged | no | needs the span as well |

The middle row is the whole of what a reference *adds*. It covers echo epenthesis (copy the neighboring vowel into an inserted position), the copy half of resyllabification, and gemination by insertion. It is a real gain, and it is a small one measured against the shipped grammars, because exactly one of them wants it.

## 5. What the French set would become

The brief's strongest argument was that a capture collapses the shipped French liaison rules from one per latent consonant to one. It does not, and this is the measurement.

The four rules are `∅ -> z / z ‿ _ [vowel]` and its /t n p/ counterparts. Written with a reference, the rule needs a class for the copied term, and the class has to be exactly the latent set. `[-vowel]` is the only class in reach, and the file itself already records why that is wrong: stable final /ʁ/ is the majority case of the language, which is why the /ʁ/ rules were removed rather than repaired.

Rebuilt from the shipped analysis with the latent set as a parameter, over the set's own 29-word corpus:

| scenario | corpus words moved | what breaks |
|---|---|---|
| shipped, latent = `{z t n p}` | — | baseline; the rebuild is identical on all 29 |
| liaison widened to `[-vowel]`, deletion left enumerated | **2 / 29** | `pʁəmjeʁ‿etaʒ → pʁəmjeʁ‿ʁetaʒ`, `il‿ɛt‿ɛ̃ → il‿lɛ‿tɛ̃` |
| both widened to `[-vowel]` | **9 / 29** | `bɔ̃ʒuʁ → bɔ̃ʒu`, `mɛʁ → mɛ`, `puʁ → pu`, `dəvəniʁ → dəvəni`, `ʃəval → ʃəva`, … |
| both widened, `{z t n p ʁ}` | **6 / 29** | the file's own /ʁ/ measurement, reproduced |

The second row is worth reading twice, because it is a failure the file never named: with the liaison half widened and the deletion half not, *il* copies its /l/ across the link and `il‿ɛt‿ɛ̃` comes out `il‿lɛ‿tɛ̃`. Widening only the copy rule adds consonants that nothing then removes.

**The obstacle is not the capture.** It is that the four latent consonants are a list, and a bracketed query is a conjunction — /z/ against /s/ is voice, /t/ against /d/ is voice, /p/ against /b/ is voice, /n/ against /m/ is place, and no conjunction of features separates the four from the rest. What the rule wants is SPE's **braces**, the disjunction device the UCLA handout gives at §10: "used to indicate multiple possibilities", expanding one schema into several rules.

That reverses the arithmetic the brief expected. With braces and no reference, the four *deletion* rules become one, since they copy nothing. With a reference and no braces, nothing collapses at all. With both, the eight become two:

```
{z t n p} -> ∅ / _ #                    ; final consonant deletion
∅ -> \1 / \1{z t n p} ‿ _ [vowel]       ; liaison
```

So the honest sentence about the French set is: **a reference is necessary and not sufficient, and the sufficient half on its own does more.** If one of the two is to be built, braces is the one with the higher return, and it is the one this document did not set out to recommend.

## 6. What could be stated once, across the five sets

The five shipped sets hold 86 rules. 35 of them sit in eleven families that state one thing more than once. Sorting those families by *why* they repeat is the whole argument:

| set | family | rules | repeated over | what states it once |
|---|---|---|---|---|
| american-english | tapping | 3 | left and right context | braces |
| american-english | nasalization | 2 | right context | braces |
| american-english | syllabic nasal / syllabic lateral | 2 | target and left context | braces |
| french-liaison | liaison | 4 | **the segment, copied** | **reference** + braces |
| french-liaison | final consonant deletion | 4 | the segment, not copied | braces |
| french-liaison | final schwa deletion | 2 | left context | braces |
| japanese-moraic | gemination | 2 | left context | braces |
| japanese-moraic | epenthetic /o/, /i/, /u/ | 6 | right context | braces |
| spanish-accented | prothesis | 2 | right context | braces |
| spanish-accented | /ɹ/ → trill | 4 | left context | braces |
| spanish-accented, japanese | r-colored vowel | 4 | target | **a declared class, available today** |

Nine of the eleven families repeat because the notation cannot say *or*, and they hold 27 of the 35 rules. One repeats because a segment has to be copied, and it needs both devices. One needs nothing that does not already exist.

The last row is a free finding: `ɚ -> eɹ` and `ɝ -> eɹ` are the only two phones the inventory marks `+rhotacized`, so `[+rhotacized] -> eɹ` states both today and gives `bˈʌtɚ → bˈʌteɹ`, `ˈnɝs → ˈneɹs`. The Japanese set writes the same pair against `aː`. Four rules could be two with no new notation at all, which is a small thing except as evidence for how much of the apparent need for captures is really something else.

The two-line French *e caduc* split must not collapse under any of this. It is deliberate — it is how a constraint over two optional choices is stated by ordering — and both [calculus.md](../calculus.md) and the rule file say so at length. A braces-style abbreviation that quietly rejoined those two lines would derive \*[dvniʁ].

## 7. The depth of the change

The two halves are separable, and separating them is most of the value of this assessment.

### The reference: shallow, because `Site` already records the positions

`Site` carries `left` and `right` as tuples with one entry per context item, "so the two sequences stay alignable with the notation", plus `bindings` for what each variable took. A positional record of the match is therefore already built, per site, for exactly the reason a reference would need it. What changes:

- **`Becomes`** stops being `Change | str | None` and becomes a sequence of terms, each a literal or a `(term number, Change)` pair. This is the only type whose shape changes.
- **`Action.edit`** resolves each reference through `site` — `items[site.left[i]]` — and applies its modification through the same `respell` → `compose_unit` path it already uses. Nothing in the spelling machinery is new; it is pointed at a different bundle.
- **`parse`** gains the static refusals in §11, and loses one silent no-op.
- **`Query`, `Pattern`, `Site`, `Edit`, `Rule`, `_apply_edits`, `Query.sites`** are untouched. Recognition does not change at all.

The invariant that changes is `Action`'s: today an edit replaces a span with a run of units built from at most one source, and after this it is built from a set of sources indexed by the site. The invariant that does *not* change is the important one — every source is a unit of the **snapshot**, so nothing can read the rule's own output.

### The span: deep, and it buys only metathesis

A multi-unit target is a different proposition, and the sentence in [calculus.md](../calculus.md) — "a `Pattern` constrains one unit and a `Site` spans one" — understates it by naming only the types. The load-bearing thing is `Query.sites`'s docstring promise: *"every non-overlapping position where this environment holds."* That is true today only because the scan advances by one and the target is one unit wide. Give the target width and `aa -> …` on `aaa` finds sites at 0 and 1, and `_apply_edits` — which splices rightmost-first on the assumption that spans are disjoint — corrupts the form. So the scan has to advance by the target's width, and "non-overlapping" has to become a checked property rather than an accident.

Beyond that: `_carry_prosody` has to decide what happens to marks that rode a span whose members were permuted; `_check_no_exchange` has to run per term rather than once; the boundary-run rule has to say what a target span containing a boundary means; and `Edit.before`/`after` stop being one unit's spelling.

Against that, the span buys metathesis and nothing else — and the metathesis literature's own objection to the notation is that it is too strong. Hume, on Chomsky & Halle's `1 2 → 2 1`: *"Unrestricted rewrite rules of this nature are excessively powerful and unconstrained… transformational formalism fails to rule out unattested cases in which sounds switch over any number of consonants and vowels, e.g. C₁V₂C₃V₄C₅V₆C₇ → C₇V₂C₃V₄C₅V₆C₁."* No shipped rule set wants metathesis; the one process that comes near it, French resyllabification, is written as copy-then-delete and the file argues that reading on its merits. **Leave it on the closure list, and say there that it is the span and not the capture that is missing.**

## 8. Captures and α: two mechanisms, and the house rule is satisfied

The house rule is that a thing declared once should not be expressible two ways without a reason. There is a reason, and it is not a matter of granularity.

**α is symmetric and constrains recognition.** `n -> [place=α] / _ [place=α]` holds *where the two positions agree*, and the module says so: "every occurrence of a variable in the recognition half must agree… so the direction does not matter and no 'first occurrence' rule has to be remembered." A rule can therefore use α to state a *condition* between two context positions with no copying anywhere — "fires only where these two agree" — which a reference cannot express, because a reference does not constrain the match at all.

**A reference is directional and only acts.** `\1` names a source and writes it somewhere else. It says nothing about what may match.

**The literature keeps them in different chapters, and for a reason worth borrowing.** The UCLA handout puts Greek letters at §8, among the *expansion conventions* — parentheses, braces, subscripts, angle brackets — which are devices for abbreviating a finite set of ordinary rules into one schema, and puts transformational numbered terms at §14 as a different rule *format*. The difference is eliminability: an α rule expands into a finite disjunction of rules the ordinary format can already write, and a numbered rule does not, which is exactly why Kenstowicz & Kisseberth say a different format is needed at all. So they are not two granularities of one device; one is an abbreviation and the other is a construction.

That is also the explanation of §3's surprise. ipakit's feature set is finite and declared, so the segment *is* the conjunction of its features, and enough α variables abbreviate the correspondence between two positions one feature at a time. The 526-character rule is an expansion convention doing a construction's job, which is why it works and why nobody would write it.

They overlap on exactly one shape: copying a value from a matched position into the target. There, α is the shorter and the better-known spelling, and it is the one the literature writes; §1 shows SPE using both devices in a single rule without either being sugar for the other. **α stays, and stays primary for feature-level agreement.** A reference should *not* grow a feature-selecting form (`[place=\1]`, "the place of term 1"), because that would be a second spelling of the thing α is for, and would make the readable one look like the special case.

What a reference does subsume is the enumerated form of §3 — the 20-variable rule — and that is subsumption of a construction nobody would write, not of a notation anybody uses.

## 9. What it costs the calculus

**Closure, identity, composition: nothing.** §3 is the argument. A reference on a substitution abbreviates a rule the notation already accepts, so the set of rule sets is unchanged up to spelling and every claim about the algebra holds of the same carrier. A reference on an insertion is new, and it is new in the same way `∅ -> t` is new: it adds units the rule chose, and additivity of the lifted map does not care where the unit came from.

**Finiteness holds, and the adversarial case was constructed rather than assumed.** The worry the brief names is right in shape — a rule that copies is a rule that grows a form — so the case to build is the one where copying compounds under optionality. A copying rule inserts one unit per matching position, which is exactly what an insertion rule does; the only difference is which unit. Measured, against the insertion cascade [calculus.md](../calculus.md) already documents:

```
insertion   '∅ ~> t / [-vowel] _'   on 'pk'
  1 rules  variants     4  longest   4  complete=True
  2 rules  variants    16  longest   8  complete=True
  3 rules  variants    64  longest  16  complete=True
  4 rules  variants   256  longest  32  complete=True

copy, distinguishable -- upper bound on '∅ ~> \1 / \1[-vowel] _' per pass, on 'pk'
  1 pass   variants     4  longest   4  complete=True
  2 passes variants    16  longest   8  complete=True

copy in place  'p ~> pp'  on 'p'  -- what '\1 ~> \1\1' would be
  1 rules  variants     2  longest   2  complete=True
  2 rules  variants     4  longest   4  complete=True
  3 rules  variants     8  longest   8  complete=True
  4 rules  variants    16  longest  16  complete=True

triplicate     'p ~> ppp' on 'p'
  1 rules  variants     2  longest   3  complete=True
  2 rules  variants     5  longest   9  complete=True
  3 rules  variants    14  longest  27  complete=True
```

Same branching factor, same doubling of form length per rule, same class. The copy emulation is an *upper* bound — it uses one rule per consonant, so the second sees the first's output where a single capture rule would see one snapshot — and it lands exactly on the insertion figures. A right-hand side that repeats a term *m* times multiplies form length by *m* per rule, giving *m^k·|f|* after *k* rules: bigger, still a bound, and already what `limit` exists for.

**The thing that would break it is not the copy. It is a term of unbounded extent.** SPE's numbered terms come with variables ranging over arbitrary strings, and a rule `X → \1\1` over such a term is total reduplication. The computational literature draws the line in the right place and puts the reference notation on the safe side of it: Chandlee & Heinz show that bounded copying is not merely regular but *subsequential*, and Chandlee rules directly on the numbered-term format itself — *"their proposed rule does not actually have the level of power needed for syntax (it is regular, and in fact subsequential)"*, and *"analyzing local or long-distance metathesis as transposition instead of copying followed by deletion does not require any additional formal power."* Unboundedness is what costs: a copying pattern in which no context is bounded *"could not be described with any FST"*, and full reduplication *"is not subsequential, or even regular."*

Kaplan & Kay supply the condition that keeps the bounded case safe, and it is the one ipakit already has. (They do not discuss metathesis; the word, and *transposition*, *permutation* and *reduplication* with it, appears nowhere in the paper.)

> our methods work only if the part of the string that is actually rewritten by a rule is excluded from further rewriting by that same rule. The following optional rule shows that this restriction is necessary to guarantee regularity: `c → ab / a __ b`. If this rule is allowed to rewrite material that it introduced on a previous application, it would map the regular language `{ab}` into the context-free language `{aⁿbⁿ | 1 ≤ n}`, which we have already seen is beyond the power of regular relations.

(Quoted from the ACL Anthology scan; the arrow and the set-builder are normalized, since the extracted text mangles both.)

That is ipakit's snapshot rule, independently arrived at, and it is what keeps a copying rule finite. The design constraint that follows is short and should be written into the notation rather than discovered later: **a term is a bounded span of the description — one unit, or a fixed number of them — and never a variable over a string.** Adopting SPE's `X`, `Y` alongside the numbering would take the site count from *O(n)* to *O(n²)* per rule and the branch count from *2ⁿ* to *2^(n²)*, which is finite and useless.

**The cap is untouched.** `unexplored` counts combinations of choices declined, which is arithmetic over the number of edits, and a reference changes what an edit *spells* rather than how many there are.

## 10. What it costs the metric

Nothing, and this was checked rather than assumed, because the last assessment in this series found a change believed to be outside the metric reaching it through a denominator.

The route that has to be ruled out is the bridges route: a mechanism that adds a key to the *comparison* bundle without adding one to any symbol's feature bundle, and so becomes a term in every denominator. A capture adds neither. It declares no feature, no value, no class and no bridge; it changes no XML; `_metric_bundle` reads a constituent's bundle, `excluded_keys`, the place components, `features.bridges` and the sagittal scalars, and a rewrite notation contributes to none of them.

The dependency runs one way and can be measured:

```
module-level import closure of ipakit/metric.py:
  _base _convert analysis constants distance features form hierarchy
  metric models segment tract tract_svg validation xsampa

'rules' is not in it.
```

`confusion.json` is derived by `scripts/confusion.py` from a bare `IPAFeatures()`, which imports `ipakit.features` and never the rule engine. `scripts/sweep.py`'s corpus is derived from the inventory. Neither can move.

The one thing worth saying positively: the reference reuses `respell` and `compose_unit`, which the metric does not read either — they are the write side, and their job is to turn a bundle back into a spelling. So the shared machinery is shared with the composer, not with the measure.

## 11. The zero, the optional arrow, and the virtual edge

Three edge cases, and the useful discovery is that the engine has already decided all three; the answers just have to be read off rather than invented.

**A term that matched the virtual edge — refuse at parse.** `Site` records `None` where the context matched past the end of the form, and the only patterns that can do that are boundary patterns. A boundary is a relation between segments and cannot be exchanged with one, which `_check_no_exchange` already refuses in both directions. So a reference to a term whose pattern names a boundary is refused statically, with the same message. Nothing site-dependent is left over.

This is a deliberate divergence from the source notation, where a boundary is a term like any other and gets a number — Parker's packet says the indexing covers "segment and/or boundary symbol", and Kenstowicz & Kisseberth's copying rule numbers a stem bracket. ipakit's boundaries are not segments, `Form` says so, and the engine already spends three refusals holding that line. A numbered term may *be* a boundary in the description; what it may not do is be referred to on the right.

**A term that was optional — refuse at parse.** `(∅)` marks a context item that may be absent, and `Site` records `None` for it. A reference to such a term would resolve at some sites and not others, which is precisely the shape `_check_variables` exists to prevent: "each is here rather than at match time because each would otherwise be a site-dependent answer." Statically knowable, statically refused.

**A capture inside a `~>` rule — nothing new.** Bindings are per-site already (`Site.bindings`, discarded with the candidate), and `Action.edit` is handed one site. Different sites choosing differently is the existing branch model, and a reference reads its source from the same snapshot every branch of that rule was found against.

**A term that bound a zero — this one is not clean, and the reason is a pre-existing defect.** A zero has no bundle, so a *modified* reference to it is refused for `_check_zero_target`'s reason, and a bare reference inserting it is refused for `∅ -> [zero]`'s reason — "an insertion had none to lose". Both would be static if the term's pattern named the zero. It does not have to:

```
'[-vowel]' matches the zero unit: True
'[obstruent]' matches the zero unit: True
'[vowel]' matches the zero unit: False
```

A negated query is satisfied by an empty bundle vacuously, so a class term can bind a zero without naming one, and the refusal becomes site-dependent. The right repair is upstream and is worth making on its own account; see the spin-off finding below. Until it is made, a reference over a negated class has to decline at a site whose term is a zero, which is a silence this document would rather not add.

**Prosody rides the position, not the copy.** `_carry_prosody` states the doctrine already: "a mark is a property of the position, not a property distributed over whatever fills it." So `\1` copies the segmental identity and a *new* position starts unmarked, while a substitution carries the target's prosody across exactly as it does today. A rule that wants the stress copied says so — `\1[stress=primary]` — and a rule that wants it agreed already has α, since `stress` is a declared feature and `Pattern` splits agreements by mode.

**An unspellable result declines the site, and no third convention is invented.** `\1[…]` can name a bundle no symbol spells, and the answer is the one `Action.edit` already gives: try `respell` for a registered phone, then `compose_unit` for a composed one, then decline — "a change the inventory can spell neither way does not fire, rather than inventing a symbol." Discriminating rather than blanket: it is per site and per result, so the rule goes on firing wherever the result *is* spellable. Two refinements the general form needs. A right-hand side is now a sequence, and an edit is atomic, so one unspellable term declines the **whole** edit rather than emitting a partial replacement. And a bare `\1` with no modification can never fail, because it is a unit that was read out of the form — which is the shape most references will have.

Worth recording while it is in view: a site declined for unspellability leaves no trace at all. `Rule.edits` skips the `None` and the `Derivation` never hears about it, where a declined *optional* choice is reported as "not taken". That asymmetry predates this proposal and is not made worse by it, but a reference makes the declining path much easier to reach.

## 12. Notation

**Numbered, explicitly marked, spelled `\1` … `\9`.** The rest of ipakit's notation decides most of this by elimination.

`(…)` is taken — it marks an optional context item, so `(1)[-vowel]` would collide with the one grouping the notation already has. `[…]` is the feature query. Greek is the agreement series, and §8 says it should stay that. `%`, `#`, `.`, `_`, `;`, `~`, `∅` are all live. `0` is a declared spelling of the empty string, and `>` is the tone-sequence separator, so neither is free. Digits `1`–`9` and the backslash are unregistered and spell nothing; every candidate spelling was checked against the parser rather than against the inventory, and all of them are refused loudly today:

```
't -> 1'        RuleError: '1' spells nothing this inventory registers…
't -> \1'       RuleError: '\1' spells nothing this inventory registers…
't -> 2 1'      RuleError: '2 1' spells nothing this inventory registers…
```

So no shipped rule and no rule anyone could have written changes meaning, whichever is chosen.

**Bare digits are the phonological spelling and are wrong for a one-line notation.** The numbers go on a second line *under* the structural description, where they cannot be confused with the terms; Chomsky's syntactic original does not even use bare integers, writing `X₁ — X₂ — X₃ — X₄` with the index carried on a symbol. On one line the integers can be confused: `t -> 2 1` has to be read as term references and not as a literal, and the only thing making that true is that digits happen to be unregistered — a fact about the inventory, not about the notation. A sigil says it structurally. `\` is the sigil, and that it is also regex's is a coincidence worth naming rather than hiding, since the two conventions really did arrive at the same idea.

The finite-state literature arrived at it too, and at the same restriction this document recommends. Gerdemann & van Noord open by observing that *"unrestricted use of backreferencing thus can introduce non-regular languages. For NLP finite state calculi this is unacceptable"*, and the schema they admit is:

```
x₁x₂ … xₙ  ⇒  T₁(x₁) T₂(x₂) … Tₙ(xₙ)  /  λ __ ρ        "multiple (non-permuting) backreferences"
```

That is a numbered structural description with a per-term change and a context, which is to say SPE's format with the permutation removed — the recommendation of this document, reached from the other end. Their reason for wanting it is the reason §2 gives for the reference being a generalization rather than an addition: they contrast it with Kaplan & Kay's `φ ⇒ ψ / λ __ ρ`, where *"any string from the language φ is replaced by any string independently chosen from the language ψ"*, and there is no correspondence between what matched and what is emitted. A capture is exactly that correspondence, and ipakit's bundle-on-the-right already supplies it for one term.

**The numbering is explicit, not positional.** SPE numbers every term left to right, which is fine when the numbers are printed under the terms and fragile when they are not: adding one item to the left context would renumber every reference on the right, silently. So a term is numbered where it is *bound*, and only terms a rule intends to refer to get numbers:

```
\1[-vowel]        on the left:  this term is number 1, and it matches [-vowel]
\1                on the right: the term bound as number 1
\1[voiced=+]      on the right: that term, with voiced=+
```

Bind on the left, refer on the right — the same division the module already states for α: *"Recognition binds; the action refers."* And the same refusals: a reference the left never bound is refused, and a number bound and never referred to is refused, exactly as a lone α is.

**The target keeps its shorthand.** `t -> [voiced=+]` goes on meaning what it means; it is the target reference with the number left out, because there is only one target and nothing to disambiguate. Numbering the target is available where a rule wants to say so.

The French liaison set, written in it — with the braces §5 says it also needs:

```
∅ -> \1 / \1{z t n p} ‿ _ [vowel]     ; liaison
{z t n p} -> ∅ / _ #                  ; final consonant deletion
```

Two lines where the shipped file has eight, and the reference is carrying one of the two.

Total assimilation, which needs no braces and no new class, and which is the case that actually justifies the reference:

```
[-vowel] -> \1 / _ \1[-vowel]         ; total regressive assimilation
```

against the 526 characters in §3.

And metathesis, for the record, in the notation this document recommends **against** building:

```
\1\2 -> \2\1                          ; needs a multi-unit target -- not recommended
```

## 13. What it still would not give

Confirmed by construction, not assumed.

**Iterative within-rule spreading still needs a loop, and does not get one.** A reference reads `items[site.left[i]]`, and `items` is the snapshot `Query.sites` scanned. Nothing a rule writes can be read by the same rule, which is the property Kaplan & Kay show is required for regularity and which ipakit already has for its own reasons. Harmony as a single rule stays out of reach; an ordered cascade still says the same thing.

**A constraint over the result of several optional choices still cannot be stated.** A reference is resolved per site from that site's own record, and no site gains any way to see what another site chose. The `redevenir` over-generation is exactly where it was.

**Metathesis stays on the list**, under the recommendation here, and its entry should say what is missing — a target spanning more than one unit — rather than what is not.

**A ranking over the set, and a relation in the general sense**, are untouched: neither has anything to do with the right of the arrow.

What leaves the list is one item, and it leaves in a more interesting state than it went on: *a variable over a whole segment* was never absent, only unwritable, and a reference is what makes it writable. The list entry should not simply be deleted, for the reason the agreement-variable entry was not deleted — a reader may know the old one.

## 14. What follows

Five things, in the order they should be done. None was applied in this lane.

### (a) Correct the two closure-list entries, first and independently

Both are wrong today and both are the kind of claim a reader builds on. *A variable over a whole segment* says "there is no such term", and §3 is a 526-character counterexample that gives every right answer. *Metathesis* says a `Pattern` constrains one unit and a `Site` spans one, which names the types and misses the invariant — `Query.sites` promises non-overlapping positions, and that promise is what a multi-unit target breaks.

This is not contingent on anything else here, and it should not wait for a decision on building.

### (b) The negated query and the zero, second

The spin-off finding below. `a -> i / [-vowel] _` fires on `∅a`, so a rule conditioned on a consonant fires where a transcription records a *deleted* consonant, silently. It has to be settled before a reference over a class can promise a static refusal, and it is worth settling anyway.

### (c) Braces, third, and ahead of captures

§5 and §6 together: nine of the eleven repeated rule families across the five shipped sets are repeated because the notation cannot say *or*, and the one that is not needs braces as well. SPE has the device, the UCLA handout gives its expansion semantics, and the expansion is into ordered rules — which is what this engine already is. If one change is built, this is the one.

The interaction with `~>` is the thing to get right and is not obvious: a braces schema expands to several rules, and several *optional* rules branch differently from one optional rule with several sites. The French *e caduc* pair is the worked case, and it must not be collapsible.

### (d) The reference, fourth

`\n`, as the general form of the right of the arrow, with the bare bundle as its one-term shorthand. §7 is the change: one type reshaped, one method taught to read a site, two static refusals added, one silent no-op closed, and recognition untouched.

Ship it with the finiteness constraint from §9 written into the notation rather than left to be discovered: **a term is a bounded span, never a variable over a string.**

### (e) The span, not at all

Metathesis stays where it is, and the entry gains a sentence about the non-overlap invariant. If it is ever revisited, Hume's objection is the thing to answer first — the notation as SPE wrote it permits `C₁V₂C₃V₄C₅V₆C₇ → C₇V₂C₃V₄C₅V₆C₁`, which no language attests, and a span bounded at two units is a different and more defensible proposal from the general one.

## Spin-off finding: a negated query is satisfied by the zero

Turned up by §11 and unrelated to captures.

A structural zero carries no phonetic features — that is what a zero is — so a query that *excludes* a value is satisfied by it vacuously. A rule conditioned on a consonant therefore fires where the transcription records a position that had content and now has none:

```
a -> i / [-vowel] _     on '∅a'  ->  'i'      the zero counts as "not a vowel"
a -> i / [-vowel] _     on 'ta'  ->  'ti'     control: a real consonant
a -> i / [-vowel] _     on 'a'   ->  'a'      control: nothing there

'[-vowel]'    matches the zero unit: True
'[obstruent]' matches the zero unit: True
'[vowel]'     matches the zero unit: False
```

This is reachable from a real analysis rather than only from a hand-typed `∅`: `z -> [zero]` is the shipped spelling of latency, and any later rule with a negated class in its context reads the zero as a consonant. It did not change a shipped derivation in the cases tried — the French set gives the same answers for `pətitə` / `pəti∅tə` and `lez‿ami` / `le∅z‿ami` — but that is a fact about which rules those sets happen to write.

The asymmetry is the tell. `[vowel]` correctly does not match, because a required key is absent; `[-vowel]` matches, because an excluded key is absent too. `(∅)` exists precisely so that a rule can declare a zero transparent to its own context "without deciding the question for every rule" — and a negated class decides it, in the other direction, for every rule that uses one.

The repair belongs in `Pattern.matches` or in `_query_matches`: a unit with no feature bundle should satisfy no segmental query, positive or negative, and `[zero]` should stay the way to name one. That is one clause, and it makes `(∅)` mean what its docstring says it means.

## Reproducing the measurements

Every number here was taken with `PYTHONHASHSEED=0` against this worktree, on `main`, reading the library only.

The French scenarios rebuild the shipped set from its own source with the latent consonant list as a parameter, and assert that the rebuild with `{z t n p}` is identical to `R.shipped("french-liaison")` on all 29 corpus words before any scenario is run. The corpus is `tests/test_rule_sets.py`'s `CORPUS` — imported, not retyped, for the reason `review-state.md` gives about hand-rolled corpora.

The enumerated-agreement rule in §3 is generated rather than typed: the segmental keys are `sorted(k for k in F.get_features("t") if k in F.features and F.features[k].mode != "prosodic")`, and the variables are the Greek small letters `_agreement` accepts, in code-point order. Generating it is the point — it is how the 20-against-22 margin is a measurement rather than a count someone did by hand.

The finiteness figures use `ipa.variants(..., limit=10**9)` so nothing is cut, and every row reports `complete=True`. The copy emulation uses one rule per consonant per pass, which is an upper bound on a single capture rule and is labeled as one.

The import closure in §10 is computed from the AST of `ipakit/metric.py` following level-1 `ImportFrom` edges, rather than from `sys.modules` — importing any submodule runs `ipakit/__init__.py`, which imports the rule engine, and would have made the answer look the other way.
