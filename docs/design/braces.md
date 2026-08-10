# Braces in the rewrite notation: assessment

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

Should ipakit's rewrite notation gain **braces**, `{ }` — the device *SPE* introduces so that one rule may state a term as a choice among alternatives?

**Verdict: ADOPT, ONE PER RULE, AND SAY WHAT IT ABBREVIATES.** A brace is an *expansion convention*: it abbreviates a finite sequence of ordinary rules, applied in the order written, each seeing the last one's output. So the thing a brace abbreviates is not one rule, it is a **cascade** — which is the object this engine already is. That is what makes it cheap. Nothing in `Pattern`, `Query`, `Site`, `Action`, `Edit` or the calculus moves, because a brace schema *is* a `RuleSet` the parser already accepts, and every refusal that guards a rule guards a schema for free. It is also what makes the one restriction necessary: two braces in one rule expand to the cross product, and the cross product is right in one shipped family and silently wrong in another with nothing in the notation to tell them apart.

**The count that motivated this assessment does not survive re-derivation, and the way it fails is the finding.** It was 27 shipped rules in nine families repeated because the notation cannot say *or*, against 4 repeated because a segment must be copied, and it made braces look like the higher-value change by roughly seven to one. Re-derived family by family against the live inventory, **four of the 27 come off today**, with declarations that already exist and no notation at all — the same move `alias="sibilant"` made for the English plural in [morph-boundary.md](morph-boundary.md), found twice more:

| | rules | after | corpus words moved |
|---|---|---|---|
| american-english, syllabic nasal / syllabic lateral | 2 | **1** | 0 of 35 |
| spanish-accented-english, `ɹ` → trill | 4 | **2** | 0 of 34 |

**Half of what is left is not a natural-class question, and the literature's answer to it is measured here and does not work.** Of the 23 rules that still state something twice, **12 repeat over a disjunction of a segment query and a *boundary*** — "a consonant, or the word edge". Hayes gives exactly that shape as his example of a bad brace and answers it with the **syllable**: the two environments have in common that both are syllable-final. ipakit has a syllable margin, and it reaches a word edge because the tiers nest, so the repair is available. Applied to the Japanese epenthesis family it moves **8 of 42** corpus words — *mɪlk* becomes `miɾku` instead of `miɾuku` — because a word written without interior dots leaves its margins unspecified and this engine does not guess them. The brace in those twelve rules is standing in for a syllabification the transcription never asserts, and no feature declaration will ever reach it.

**The case that motivated the question is the one braces cannot state.** [captures.md](captures.md) proposed `∅ -> \1 / \1{z t n p} ‿ _ [vowel]` for French liaison. Braces alone cannot write it: the latent consonant appears in two positions and braces cross-multiply, so the sixteen expansions give `pətit‿ami → pəti‿zami`, `mɔ̃n‿ami → mɔ̃‿zami`, `tʁop‿ɛmabl → tʁo‿zɛmabl` — wrong on **4 of that set's 29 corpus words**. *SPE*'s device for a linked choice is a different bracket, and it is two-way rather than *m*-way. The liaison family stays where captures.md left it; the deletion half, four rules with one varying position, is the part that collapses.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Is a brace an expansion convention or a rule format? | **An expansion convention.** *SPE* p. 333 convention (4); Appendix convention (b), p. 394, expands it into *"a sequence of schemata"*. |
| Into what does it expand? | A sequence of ordinary rules, **conjunctively ordered** in *SPE*'s ordering sense — every expansion applies, in order (p. 61). |
| Is that the same as one rule with a disjunctive term? | **No, and three characters tell them apart.** `a -> b / {x, b} _` gives `xbb` on `xaa`; the one-rule reading gives `xba`. |
| Does the difference reach shipped data? | **Yes.** Read as one optional rule, the French *e caduc* pair derives \*[dvniʁ] and \*[vɑ̃dʁdi]. Read as its expansion, it is the shipped answer. |
| Is the order of the alternatives inside a brace load-bearing? | **Yes.** `{x, b}` and `{b, x}` give different answers on the same form. |
| How many of the 27 are waiting on *or*? | **23**, in eight families. Two families come off today, 0 corpus words moved in each. |
| How many of the 23 repeat over a boundary rather than a class? | **12** — nasalization 2, gemination 2, epenthesis 6, trill 2. |
| Does the literature's repair — restate it as syllable-final — work here? | **No.** Japanese epenthesis: 8 of 42 words move. American nasalization: 6 of 35. An unwritten margin is unspecified, not absent. |
| Is the objection to the device unanimous? | **No.** Kenstowicz & Kisseberth 1979: 363–64 call the flat claim premature, against a language where the syllable cannot replace the brace. The flat claim is McCawley's. |
| What do the 23 become? | **11 source lines**, one brace per rule. 10 if two braces were allowed; the difference is one line of the tapping family. |
| Does the French liaison set collapse? | **No.** Two positions, linked; independent braces are wrong on 4 of 29 corpus words. |
| Does the French *deletion* set collapse? | **Yes**, to one brace over `{z t n p}`. Widening instead to the smallest class containing them is right on all 29 corpus words and wrong on 3 of 9 real French words the corpus does not hold. |
| Does the query language already have disjunction? | **Yes, within one feature.** `[place=alveolar]` ∪ `[place=velar]` is exactly the 14-term exclusion, so a brace over feature *values* would be a second spelling. |
| May the alternatives be different lengths? | **In a context, yes, free** — each expansion is its own rule with its own item count. **In the target, no**: that is captures.md's span, and one expansion of it is a rule the parser already refuses. |
| What does it cost the calculus? | **Closure, identity, composition: nothing.** The cap: *m* alternatives take the branch count from 2^sites to (m+1)^sites. |
| Is there an adversarial case? | **Yes, and it is small.** Five alternatives on an optional insertion rule, against `pk`, cuts at the default limit with 17,177,628,652 combinations unexplored. |
| A brace on the right of an obligatory arrow? | **Every alternative after the first is dead**, silently: `a -> {b, c}` on `kaka` is `kbkb`, and only the first expansion ever fires. |
| Does it reach the metric? | **No.** `ipakit.rules` is not in `ipakit/metric.py`'s module-level import closure. |
| What stops a brace where a class exists? | *SPE* had the evaluation measure. ipakit has none, and a mechanical check catches **one** of the two families this document collapsed. |

## Sources

**Read directly.**

- Chomsky & Halle, *The Sound Pattern of English* (Harper & Row 1968) — open access on Fulcrum, landing <https://www.fulcrum.org/concern/monographs/2z10wq58b>, PDF <https://www.fulcrum.org/ebooks/ms35tc39t/download?locale=en>. Pp. 32, 42, 61–63, 76–77, 147, 333–35, 339–41, 392–99. The scan's OCR mangles stacked matrices and braces, so every rule quoted here was read from a 170 dpi page render; prose was read both ways and agrees.
- Kenstowicz & Kisseberth, *Generative Phonology: Description and Theory* (Academic Press 1979), pp. 339–42 and 359–64 — the overview of the abbreviatory devices, and the section of the notation chapter given over to braces. Not open access; a copy was obtained and read. Its text layer is OCR of a scan that mangles arrows, slashes and stacked braces, so the prose here is quoted from the extraction and every rule display was read from a 170 dpi page render.
- Bruce Hayes, *Introductory Phonology* (Wiley-Blackwell 2009), pp. 220, 259, 263–64: <https://vulms.vu.edu.pk/Courses/ENG507/Downloads/Introductory%20Phonology%20by%20Hayes.pdf>. The custom-encoded font mangles IPA, so no rule and no segment list is quoted here from the text layer; the two passages carrying the argument are ASCII prose and are verbatim.
- David Odden, *Introducing Phonology* (Cambridge University Press), pp. 52, 77, 158–59: <https://jinxiaosong.wordpress.com/wp-content/uploads/2015/02/odden-introducing-phonology.pdf>
- Zuraw & Martin, *SPE rule notation review*, UCLA Ling 200A, Fall 2004, §10: <https://linguistics.ucla.edu/people/zuraw/200A_2004/0203RuleNotation.pdf>
- Zuraw, *Class 3: Expansion conventions*, UCLA Ling 200A, 2020, §5: <https://linguistics.ucla.edu/people/zuraw/200A_2020/2020_03_ExpansionConventions.pdf> — which corrects the 2004 handout on the point §3 below turns on.

**Sought and not reached, with what was tried.** Each entry below records an attempt on a date, by a route. None of them is a claim that the work is unavailable, and a search that came back empty is evidence about the search.

- McCawley, "On the Role of Notation in Generative Phonology", in Gross, Halle & Schützenberger (eds.), *The Formal Analysis of Natural Languages*, Mouton 1973, pp. 51–62 — the classic argument that the abbreviatory apparatus can be dispensed with, and the origin of the objection §4 surveys. Checked 2026-08-02: OpenAlex resolves DOI `10.1515/9783110885248-004` and reports no open location, and the publisher's page answers 405. Read at one remove, through Kenstowicz & Kisseberth's report of it in §4, and labeled there. Kenstowicz & Kisseberth date the piece 1972 and the publisher 1973; a search on one year misses the other.
- Kenstowicz, *Phonology in Generative Grammar* (Blackwell 1994) — checked 2026-08-02: no open location in OpenAlex, and the archive.org copy is lending-restricted with search-inside reporting no text without a loan. Nothing here is attributed to it.

## 1. The count, re-derived

[captures.md](captures.md) sorted 35 repeated rules into eleven families by *why* they repeat, and found 27 in nine families repeating because the notation cannot say *or*. The nine families and the 27 rules are confirmed. What is not confirmed is the reading that all 27 are waiting on a notation.

The question asked of each family is mechanical. Take the position that varies, take the union of what its alternatives match over the unit corpus `scripts/sweep.py` defines, and compute **the smallest bracket that contains that union**. A bracket is a conjunction of per-feature constraints, and each of those is already an arbitrary disjunction over that feature's values — `required` is a one-value disjunction, `excluded` is the complement of one. So the sets a bracket can pick out are exactly the products of per-feature value sets, and the smallest containing bracket is computable by intersecting the constraints every member satisfies. If it equals the union, one bracket says it and there is nothing to abbreviate.

```
family / position                      alts  contained?  rectangle?  rectangle in-inventory?
american tapping, right                   2      False       False       False
american tapping, left                    1      False       False        True
american nasalization, right              1      False        True        True
american syllabic, target                 2      False       False       False
american syllabic, left                   2       True        True        True
french final-C deletion, target           4      False       False       False
french schwa deletion, left               2      False        True        True
japanese gemination, left                 1      False        True        True
japanese epenthesis, right                1      False        True        True
spanish prothesis, right                  2      False       False       False
spanish trill, left                       3      False       False        True
```

Two rows carry the finding, and both are the last column — the reading [morph-boundary.md](morph-boundary.md) established when `[sibilant]` turned out to select the English plural's class exactly. A rule set for a language is applied to that language, and a bracket exact over the inventory a set targets is exact.

**The American syllabic nasal and syllabic lateral are one rule, today.** The two left contexts are not a disjunction at all: `[obstruent]` is *contained* in `[-vowel -approximant -trill -tap -silence]`, which is the obstruents and the nasals. The two targets, the nasals and the lateral approximants, widen to the sonorant consonants at the cost of `j` and `ɹ`, neither of which stands word-finally after an obstruent in English.

```
[-vowel -fricative -plosive -affricate -tap -trill -silence] -> [syllabic=+]
    / [-vowel -approximant -trill -tap -silence] _ #      ; syllabic sonorant

14 rules -> 13;  0 of 35 corpus words move
```

**The Spanish trill's three segment triggers are one bracket, today.** `{n l s}` is not a class over the whole 139-phone inventory — the smallest bracket containing it adds `z ɫ ɬ ɭ ɮ ɳ ɹ ʂ ʐ` — but within a Spanish inventory the surplus is empty.

```
ɹ -> r / [place=alveolar -plosive -affricate -tap -trill -vowel] _   ; trill after an alveolar sonorant

24 rules -> 22;  0 of 34 corpus words move
```

Both are widenings rather than identities, and both are measured rather than argued. What they share with the plural is the shape of the mistake: a family was counted as waiting on a notation because nobody asked the inventory whether it was. That takes the nine families to eight and the 27 rules to 23.

## 2. Half of what is left is a boundary, and the syllable does not rescue it

The eight remaining families do not repeat for the same reason, and sorting them again is where the case for braces actually is.

| set | family | rules | the alternatives | |
|---|---|---|---|---|
| american-english | tapping | 3 | right: an unstressed vowel, an unstressed syllabic lateral; left: nothing, or `ɹ` | two classes, and a length-zero alternative |
| american-english | nasalization | 2 | right: `#`, `[-vowel]` | **a boundary and a class** |
| french-liaison | final consonant deletion | 4 | target: `z`, `t`, `n`, `p` | four literals |
| french-liaison | final schwa deletion | 2 | left: `[vowel]`, `[-vowel]` | a partition of everything |
| japanese-moraic | gemination | 2 | left: `[-vowel]`, `#` | **a boundary and a class** |
| japanese-moraic | epenthesis | 6 | right: `[-vowel -approximant]`, `#`, three times over | **a boundary and a class** |
| spanish-accented | prothesis | 2 | right: `[-vowel -approximant]`, `[channel=lateral]` | two classes |
| spanish-accented | `ɹ` → trill | 2 | left: `#`, the alveolar sonorants | **a boundary and a class** |

Twelve of the 23 are the bolded rows. In those the disjunction is between a segment query and a boundary, and no single term can hold both: a boundary carries no feature bundle, and `docs/rules.md` records the refusal as a known limit — *"a bracketed `[level=phrase]` never matches, because a query is compared against a segment's feature bundle and a boundary has none."* The two are disjoint by construction, and measurably so:

```
a -> o / _ [level=word]       on 'a#' -> 'a#'    on 'at' -> 'at'
a -> o / _ [-vowel]           on 'a#' -> 'a#'    on 'at' -> 'ot'
```

*SPE* writes exactly that brace. Page 341's spirantization rule, image-verified rather than taken from the mangled text layer, has a word boundary and two feature matrices in one pair of braces — on the page whose argument is that a notation should *"prevent abbreviations when no true generalizations are to be found."*

```
        ⎡−voc  ⎤        ⎧                ⎡+voc ⎤    ⎧ #      ⎫ ⎫
        ⎢+cons ⎥  →     ⎨  [+cont]   /   ⎣−cons⎦ __ ⎨ [−voc] ⎬ ⎬   (a)
        ⎣−nasal⎦        ⎩                           ⎩ [+cons]⎭ ⎭
```

**But the literature has a positive answer to that shape, and it has to be tried rather than dismissed.** Hayes's two brace examples are this shape and no other: Cibaeño liquid gliding, which applies *"if they precede a consonant or are word-final"*, and Yawelmani epenthesis, `∅ → i / C __ C {C, ]word}` — which is the Japanese epenthesis family, segment for segment. His answer both times is that the two environments do have something in common and it is a **syllable**: *"a widely adopted alternative solution is to suppose that the environment is syllable-final"* (p. 259). Odden's example of the device is ipakit's gemination family — *"shortens a long vowel if it is followed by either two consonants or else one consonant plus a word boundary"* — and his answer is the same one: *"the generalization can be restated as 'shorten a long vowel followed by a syllable-final consonant'"* (p. 159).

The repair is older than either textbook, and the primary writes it with the same glyph. Kenstowicz & Kisseberth report it of the same Yawelmani rule — *"it has been claimed that the use of braces to express the frequent conjunction of C and # in phonological rules can be dispensed with if rules are permitted to refer to syllable structure"* (Kenstowicz & Kisseberth 1979: 362) — and state the result, read from the page, as `∅ → i / C __ C.`, a dot for the syllable boundary. That is `_ .`, term for term.

ipakit has that. `.` is a syllable margin, the tiers nest so a word edge is one too, and `_ .` is therefore exactly *syllable-final*. Measured:

```
Japanese epenthesis, both right contexts replaced by one syllable margin
    rules 35 -> 32;  8 of 42 corpus words move
        mɪlk        miɾuku      ->  miɾku
        stɹa͜ɪk     sutoɾaiku   ->  stɾaiku
        kɹɪsməs     kuɾisumasu  ->  kɾismasu
        skul        sukuːɾu     ->  skuːɾu
        bɑks        bokusu      ->  boksu

American nasalization, both right contexts replaced by one syllable margin
    rules 14 -> 13;  6 of 35 corpus words move
        ˈɪnkʌm      ˈɪ̃ŋkʌ̃m      ->  ˈɪŋkʌ̃m
        kˈæmp       kʰˈæ̃mp̚      ->  kʰˈæmp̚
        tˈɛnθ       tʰˈɛ̃n̪θ      ->  tʰˈɛn̪θ
```

Nothing is wrong with the repair; what is wrong is the input. `docs/rules.md` states the policy it fails on: *"A word written without interior dots leaves its interior margins **unspecified**, and a margin-conditioned rule does not fire there rather than guessing."* Not one of the 42 Japanese corpus words carries an interior dot, and neither the caller nor the library will supply them — the alternative, treating absence as "one syllable", invents structure the transcription never asserted, and that is a decision this library has already taken and defended.

The Japanese case is worse still, and it is Hayes's own difficulty rather than ipakit's. Epenthesis is what *creates* the syllable structure — *"the underlying representations that undergo Epenthesis are precisely the ones that could not be syllabified"* (p. 264) — so conditioning it on a margin is conditioning it on the rule's own output. Hayes reaches for syllabification as a derivational step; ipakit has no syllabification rule and a rule cannot read its own output by construction. The difficulty is stated at the moment the repair is proposed and by the people proposing it: *"if this analysis is accepted the syllable structure assignment rules will have to apply both before and after (64) since insertion of [i] creates a new syllable nucleus"* (Kenstowicz & Kisseberth 1979: 362). It is a cost the repair carries, not an objection anyone raised later.

So for twelve of the 23 there is no class to prefer, no widening to measure, and the one repair the textbooks offer costs 8 of 42 words in one set and 6 of 35 in another. **A brace is the only device that states them**, and the objection that a brace hides a missing natural class does not reach a disjunction one of whose members is not a segment.

The remaining eleven are three families, and one of them is not a disjunction either. **The French schwa family's brace has nothing behind it.** `ə -> ∅ / [vowel] [-vowel] _ #` and `ə -> ∅ / [-vowel] [-vowel] _ #` differ only in a left context whose alternatives partition the universe: their union is all 8,616 units of the sweep corpus, and the smallest bracket containing it is the empty one. What the pair means is *some segment, then a consonant* — the requirement is that the consonant not be word-initial — and what the notation lacks is not disjunction but a **wildcard**. There is none: no single `key=value` term matches every unit, and `[]` is refused as an empty query. Writing that family with a brace would spell a missing term as a choice between two halves of everything, which is the one use of the device this document would refuse.

## 3. A brace is an expansion convention, and what it expands to is a cascade

[captures.md](captures.md) established the frame this has to be answered in. Agreement variables are an *expansion convention* — eliminable into a finite set of ordinary rules, so they compose with everything shipped and cost the calculus nothing — where numbered terms are a rule *format*, and not eliminable. Braces are the first kind, and the primary says so outright.

> Two partially identical rules may be coalesced into a single rule by enclosing corresponding nonidentical parts in braces: { }. (*SPE* p. 333, convention (4))

> Let us call (5) a "schema" which "expands" to the sequence of rules (2). (*SPE* p. 333)

The formal statement is Expansion Convention (b) in the Appendix to Chapter 8: where `{Y₁, …, Yₘ}` is maximal in `X₁{Y₁, …, Yₘ}X₂`, the schema *"expands into the sequence of schemata"* `X₁Y₁X₂, …, X₁YₘX₂` (p. 394).

**The sequence is applied conjunctively, and that is the half a reader will get wrong.** Two senses of one word have to be kept apart before the quotation makes sense. Braces are a *disjunction* in the ordinary logical sense — Hayes calls them *"a notational device that denotes the logical notion 'or'"*, Odden *"braces {…} express disjunctions"* — and they are **conjunctively ordered** in *SPE*'s ordering sense, which is a fact about how the expanded rules apply, not about the connective:

> When notations such as (2) have been used in the construction of generative grammars, it has generally been tacitly assumed that the ordering abbreviated by the use of parentheses is disjunctive (in this case the ordering (2a), (2b)). In the case of braces, however, the ordering is assumed to be conjunctive. (*SPE* p. 61)

The trap is live and has caught people who teach the material: the 2004 UCLA handout states disjunctive ordering for schemata generally, and its 2020 successor corrects it in a footnote — *"Rules from the same curly-bracket schema apply conjunctively… Thanks to Patrick Jones for de-confusing me on this!"* Calling braces *SPE*'s disjunction is right about the connective and reads as a claim about the ordering, which is why nothing here calls them that.

Conjunctive ordering is *SPE*'s convention (29), p. 341 — *"Rules are applied in linear order, each rule operating on the string as modified by all earlier applicable rules"* — which is this cascade, stated by the source in the words `docs/rules.md` already uses. So a brace schema is a **rule set**, and "what does a brace mean" has exactly one right answer here: the ordered rules it expands to, each seeing the last one's output.

That is not a distinction without a difference. Three characters tell the readings apart:

```
schema:  a -> b / {x, b} _       on 'xaa'
   written {x, b}   ->  'xbb'    the first expansion feeds the second
   written {b, x}   ->  'xba'    the second expansion has nothing to feed
   as ONE rule, both left contexts at once, all sites against one snapshot
                    ->  'xba'
```

Two things follow, and both are constraints on how a brace may be introduced rather than arguments against introducing it.

**The order of the alternatives inside the braces is load-bearing.** `{x, b}` and `{b, x}` are different rule sets. A reader who reads a brace as a set has read it wrong, and nothing about the glyph says so.

The three characters above are a construction, and the literature supplies the attested case. Kenstowicz & Kisseberth write Yawelmani epenthesis as one schema over `{#, C}` — `#` above, `C` below — and the two subrules stand in a bleeding relation: the word-final one must break up the final cluster first, and *"if the schema of (61) were written with the C above instead of below the #, the wrong result would be obtained for this derivation"* (Kenstowicz & Kisseberth 1979: 360), the derivation being `#logw-t#` to *logw-it*, which the other order takes to \**logiwit*. Their statement of the convention is the one this section argues for, in two sentences: *"Schemata abbreviated by braces are expanded into their constituent elementary rules from top to bottom. Furthermore, the subrules are interpreted as conjunctively ordered"* (Kenstowicz & Kisseberth 1979: 360). Top to bottom is left to right in a one-line notation, and that is the whole of the difference.

**Read as one rule, a brace inside an optional rule is a semantic change.** This is the case to attack, and the shipped data supplies it. The French *e caduc* pair is two ordered optional rules whose split is the analysis: [calculus.md](../calculus.md) argues at length that the loi des trois consonnes is stated by *ordering*, because within one rule the sites branch independently against a snapshot and cannot see each other's choices.

```
                 the expansion (shipped)                 as one optional rule
  dəvəniʁ        dəvəniʁ dəvniʁ dvəniʁ                   dəvəniʁ dvəniʁ dəvniʁ *dvniʁ
  vɑ̃dʁədi       vɑ̃dʁədi                                  vɑ̃dʁədi *vɑ̃dʁdi
  ʁədəvəniʁ      6 forms                                 8 forms
```

`*[dvniʁ]` is *d v n*, and it is not French. Under the expansion reading the pair is safe — measured, the two alternatives in either order give the same three variants of *devenir*, in a different derivational order, which is what [calculus.md](../calculus.md) already says of the two rules. What is lost is not correctness but visibility: the file spends paragraphs explaining that the split is deliberate, and a brace would present the same content as an abbreviation of one generalization. That is a good reason for the shipped French set to go on writing it out, and a bad reason to refuse the device.

## 4. The objection to braces, and what it costs here

**The objection is in Hayes's book but not in Hayes's voice** — see the spin-off finding at the end of this document — and what he reports is sharper than a dismissal, because it is an argument rather than a verdict:

> Many linguists have expressed the view that curly brackets offer little or no insight into linguistic phenomena, since they evade the question of what the two listed environments might have in common. (Hayes 2009: 259)

> There are two reasons why rules formulated in this way have struck many phonologists as unsatisfactory. First, as with the Cibaeño Liquid Gliding case, the rule makes no connection between the two cases listed in the curly brackets. Second, the rule does not take account of Yawelmani syllable structure. (Hayes 2009: 264)

Odden puts it in his own voice and without hedging, and adds the second head of the complaint:

> Although the brace notation has been a part of phonological theory, it has been viewed with considerable skepticism, partly because it is not well motivated for more than a handful of phenomena that may have better explanations (e.g. the syllable), and partly because it is a powerful device that undermines the central claim that rules operate in terms of natural classes (conjunctions of properties). (Odden 2005: 159)

> The brace notation is a device used to force a disjunction of unrelated contexts into a single rule… i.e. there is no coherent generalization. (Odden 2005: 52)

**The flat claim has a name on it, and the standard reference work of the period declines to follow it.** Kenstowicz & Kisseberth give the device a section of their notation chapter and report the objection with its source: *"In the case of the brace notation McCawley (1972) has claimed that all known uses of this device can be dispensed with because either the abbreviated rules are only accidentally related or the underlying relationships between the rules can be expressed more properly in some other fashion"* (Kenstowicz & Kisseberth 1979: 361–62). They grant the misuse first, and their example is the shape §2 refuses — Tonkawa apocope and truncation, collapsed into one schema over `{#, V}` because both happen to delete a vowel, where *"the vacuity of the unlimited use of the brace notation is clearly evident, for each of these rules has nothing in common except that they drop a vowel"* (Kenstowicz & Kisseberth 1979: 361). Having granted it, they refuse the conclusion:

> Given evidence such as that from Bella Coola, it appears to us to be premature to claim that all instances of the brace notation represent either false generalizations or else can be reformulated in a more insightful way. As matters stand, the brace notation seems justified, but (like most of the other notational devices sketched in this chapter) capable of being misused. (Kenstowicz & Kisseberth 1979: 363–64)

**Their counter-case is §2's, reached from the other end.** The repair on trial is the syllable, and Bella Coola is a language that cannot pay for it: Newman's description has words made entirely of consonants and concludes that the syllable is irrelevant at the phonemic level, and yet *"the conjunction [of C and #] is critical for the operation of several rules in the language"* (Kenstowicz & Kisseberth 1979: 362) — a syllabicity rule, an aspiration rule, a prepalatal realization rule, and a constraint on clustering, each conditioned on a consonant or a word boundary and on nothing the two have in common that the grammar can name. §2 measures the same shape from the other direction: ipakit's twelve rules are conditioned on a class or an edge, the syllable is available as a term, and using it costs 8 of 42 words in one set and 6 of 35 in another because the transcriptions do not carry the structure the term reads. One argument is about a grammar that has no syllables to refer to and the other about input that does not write them, and both end where §2 ends — the brace is standing in for structure that is not there to be named. The conjunction is not a curiosity in this repository's reading either: the copying rule [captures.md](captures.md) takes from the same book, rule (79) at p. 371, has `{#, C}` as its fourth term.

So the objection has two heads, and it is not unanimous. The dissent does not move the verdict — that rests on §2's measurements, which are about this data and no one else's. What it changes is the burden: the device does not have to be defended against the literature, it has to be used well, and §11 is the whole of what this repository can do about that. **The insight head** — a brace evades the question of what the alternatives share — is answered in §2 by measurement rather than by argument: for twelve of the 23 the alternatives *do* share something, it is syllable-finality, the notation can say it, and saying it moves 8 of 42 words in one set and 6 of 35 in another because the transcriptions do not carry the structure. What Hayes and Odden treat as an analytic failing is here a fact about the input, and it is not repairable by a better rule.

**The power head** is the one that bears on this repository, because it is the house rule in other words. *"A powerful device that undermines the central claim that rules operate in terms of natural classes"* is `docs/reviewing.md`'s concern exactly: a notation that lets a shipped rule set state a thing two ways, one of which is right and one of which merely works.

**The primary has an answer to the power head, and ipakit cannot have it.** *SPE* raises the unnatural-class problem itself, at p. 340 — *"the environment in (17) is a very unnatural class. This distinction must, of course, be brought out formally by an adequate linguistic theory"* — and answers it with the evaluation measure rather than with a ban:

> An examination of Table 1 shows that the four segments in the context of (23) can be uniquely identified in the language in question by specifying the two features [+vocalic, −consonantal]; and in view of the evaluation criterion (9), it is this most abbreviated schema that determines the value of the rules summarized by (23). (*SPE* p. 340)

The measure counts feature occurrences after all notational transformations (p. 392), and the notations themselves are *auxiliary expressions* that cost nothing (p. 393). So wherever a feature matrix picks out the same set, the matrix is shorter and wins, and a brace enumeration is permanently dominated. Braces are permitted and permanently subordinate.

**The hole in that, and it is the honest version of the "braces are free" complaint**, is what happens when no matrix exists. The measure still rewards the brace over two written-out rules — *"the sequence of rules (2) is more highly valued than the sequence of rules (3)"* (p. 334) — and charges nothing for the disjunction, because the brace and comma are free. So *SPE*'s theory prefers a collapsed schema over two rules for **any** partial identity between adjacent rules, accidental or not. The claim that a brace saves nothing under the evaluation measure is the wrong way round; the true version is that a brace saves everything the alternatives have in common and costs nothing for what they do not.

ipakit has no evaluation measure and is not going to grow one. §11 is what it can have instead, and it is less than *SPE* had — and less than the third instrument Kenstowicz & Kisseberth float, which §11 weighs.

## 5. What the eight families become

Under one brace per rule — §6 is the argument for the restriction — the 23 rules are 11 source lines.

```
american-english
  [manner=plosive place=alveolar] -> [manner=tap voiced=+]
      / [vowel] _ {[vowel -primary -secondary],
                   [syllabic=+ channel=lateral -primary -secondary]}   ; tapping
  [manner=plosive place=alveolar] -> [manner=tap voiced=+]
      / [vowel] ɹ _ [vowel -primary -secondary]        ; tapping (after a coda rhotic)
  [vowel] -> [nasalized=+] / _ [manner=nasal] {#, [-vowel]}            ; nasalization

french-liaison
  {z, t, n, p} -> ∅ / _ #                              ; final consonant deletion
  ə -> ∅ / {[vowel], [-vowel]} [-vowel] _ #            ; final schwa deletion

japanese-moraic
  [obstruent -fricative] -> [length=long] / {[-vowel], #} [vowel -long] _ #  ; gemination
  ∅ -> o / [manner=plosive place=alveolar] _ {[-vowel -approximant], #}
  ∅ -> i / [manner=affricate place=alveolo-palatal] _ {[-vowel -approximant], #}
  ∅ -> u / [-vowel -nasal] _ {[-vowel -approximant], #}

spanish-accented-english
  ∅ -> e / # _ s {[-vowel -approximant], [channel=lateral]}            ; prothesis
  ɹ -> r / {#, [place=alveolar -plosive -affricate -tap -trill -vowel]} _    ; trill
```

Every one of those expands to the shipped rules in the shipped order, because *SPE*'s adjacency condition happens to hold of this data — a brace *"is possible only when the subrules in question are adjacent in the order of the rules"* (p. 341). Checked rather than assumed:

```
american tapping                             3 rules at [0, 6, 7]  NOT ADJACENT
american nasalization                        2 rules at [12, 13]  adjacent
american syllabic nasal / syllabic lateral   2 rules at [4, 5]  adjacent
french final consonant deletion              4 rules at [4, 5, 6, 7]  adjacent
french final schwa deletion                  2 rules at [8, 9]  adjacent
japanese gemination                          2 rules at [26, 27]  adjacent
japanese epenthesis                          6 rules at [28, 29, 30, 31, 32, 33]  adjacent
spanish prothesis                            2 rules at [0, 1]  adjacent
spanish ɹ -> trill                           4 rules at [11, 12, 13, 14]  adjacent
```

Tapping is the exception, and its own file answers it: *"MEASURED, lifting all three into one block here changes no derivation in the corpus."* Re-measured, moving the three into one contiguous block below the syllabic block moves 0 of 35 corpus words, and the one real ordering constraint — the tapping block must run *after* the syllabic block, so that `[syllabic=+ channel=lateral]` has something to match — survives, because that is where the block goes.

That the adjacency holds is luck rather than design, and it is worth knowing it is checkable. A family whose members are separated by a rule that feeds or bleeds one of them cannot be braced at all, and nothing about the notation would say so; the check is the one printed above.

**Two families are absent from that listing and should be said out loud.** The `ɹ`-colored vowel family [captures.md](captures.md) found needs no new notation, and [morph-boundary.md](morph-boundary.md)'s English plural needs none either. With §1's two that is four families in three lanes, and the lesson is the same each time: a family that looks like it wants disjunction usually wants a look at the declaration first.

## 6. The French set, and why one brace per rule

The four liaison rules are one per latent consonant, and [captures.md](captures.md) proposed `∅ -> \1 / \1{z t n p} ‿ _ [vowel]` — a brace *and* a reference. The reference is what links the two positions, and it is needed because braces do not link.

*SPE* fixes only an **order** of expansion for two brace sets, never a pairing. The p. 339 double-brace rule collapses a two-alternative change with a four-alternative environment and yields eight rules, which is the cross product; the p. 32 gloss is an explicit nested loop — *"first, expand the context P__Q… next, apply the rules abbreviated as X → Y / Z__R in the usual sequence, under the condition that the element ZXR under consideration is in the context P₁__Q₁; next, apply the same rules under the condition that the element ZXR is in the context P₂__Q₂; etc."* Expansion Convention (b) strips one *maximal* brace at a time and hands back schemata that still contain the other. There is no reading on which the *i*th alternative here pairs with the *i*th alternative there.

The linked device is a different bracket, and *SPE* introduces it for exactly this gap:

> An expression with angled brackets abbreviates two expressions — one in which all angled elements appear and another in which none of these elements appear. (*SPE* pp. 76–77)

All or none: two-way, not *m*-way, and disjunctively ordered rather than conjunctively. It does not state the liaison family either.

Measured, the cross product is wrong on the shipped data:

```
liaison as a brace in both positions: 16 expansions
    rules 12 -> 24;  4 of 29 corpus words move
        pətit‿ami    pəti‿tami   ->  pəti‿zami
        mɔ̃n‿ami     mɔ̃‿nami    ->  mɔ̃‿zami
        tʁop‿ɛmabl   tʁo‿pɛmabl  ->  tʁo‿zɛmabl
        il‿ɛt‿ɛ̃     il‿ɛ‿tɛ̃    ->  il‿ɛ‿zɛ̃
```

Every liaison consonant becomes the first alternative, because the first expansion reaches every site before the others are tried. The output is well-formed French and wrong, which is the shape [reviewing.md](../reviewing.md) exists to catch.

**And the same cross product is right in the tapping family.** Its two positions vary independently — a left context that may carry a coda rhotic, a right context that may be a vowel or a syllabic lateral — so all four expansions are wanted and the fourth is harmless, while the linked reading is wrong:

```
a brace in BOTH positions, expanded independently: 4 rules   0 of 35 corpus words move
a LINKED expansion (the angle-bracket reading):    2 rules   3 of 35 corpus words move
        bˈɑ.tl     bˈɑ.ɾl̩   ->  bˈɑ.tˡl̩
        pˈɑɹti     pʰˈɑɹɾi  ->  pʰˈɑɹti
        lˈɪtl      lˈɪɾl̩    ->  lˈɪtˡl̩
```

So one notation is correct in one family and silently wrong in another, and the only thing separating them is which reading the author had in mind. **One brace per rule closes it by construction**, and the cost is measurable: tapping writes two lines instead of one, which is one of the twelve lines braces save. Take the trade. A device that can be read two ways with no marking is precisely what this repository's review method exists to find.

**The deletion half does collapse, and the alternative to collapsing it is worse.** `{z, t, n, p} -> ∅ / _ #` is one brace in one position, four rules to one line. The other way to state four literals once is to widen to a class, and the smallest bracket containing `/z t n p/` is not `[-vowel]` — it is the bilabial and alveolar plosives, nasals and fricatives, which over a French inventory is `{b d m n p s t z}`:

```
deletion half widened to the smallest class containing /z t n p/
  over the shipped 29-word corpus                      0 of 29 words move
  plus 9 real French words with a pronounced final consonant
                                                       3 of 38 words move
        syd   -> sy       (sud)
        bys   -> by       (bus)
        film  -> fil      (film)
```

The widening is wrong about French and the shipped corpus holds no word that shows it. That is the strongest available argument for the enumeration — **a brace states the list, and a list is what the language has** — and it is also a warning about §1, whose two collapses rest on the same kind of evidence. The honest reading of both is *no corpus word moves*, not *the widening is right*.

## 7. Where a brace may go, and what it may hold

**A whole term, in a context or as the target.** Under the expansion reading each alternative becomes its own ordinary rule, so a term is whatever a term already is: a literal, a bracketed query, a boundary, a declared mark. The heterogeneous case needs no new machinery at all, precisely because a boundary and a query never meet inside one pattern.

**Not a feature value.** The query language already has disjunction within a feature, spelled by exclusion, and a value-level brace would be a second spelling of it:

```
[place=alveolar] ∪ [place=velar]                      36 phones
[-alveolo-palatal -bilabial -bilabial^palatal -bilabial^velar -dental -epiglottal
 -glottal -labiodental -palatal -pharyngeal -postalveolar -uvular -vowel -silence]
                                                      36 phones, and the same 36
```

The `-silence` term is the interesting part of that line. Without it the exclusion form is wider by exactly one phone — `␣`, which declares no `place` at all and so satisfies every exclusion of a `place` value vacuously. That is [captures.md](captures.md)'s spin-off finding arriving from another direction, and it is the one place where the equivalence has to be stated with care: **exclusion is value-disjunction over the units that declare the feature, and vacuous satisfaction over the units that do not.** The house rule is that a thing declared once should not be expressible two ways without a reason; there is no reason here, so a brace holds terms and not values.

**Alternatives of different lengths: free in a context, refused in the target.** The `{VC, C}` case is answered by the expansion without a decision having to be taken. Each alternative becomes a rule with its own number of context items, so `Site.left` keeps its promise — *"one entry per context item"* — per expanded rule, and nothing ever has to align two shapes. A length-zero alternative is the same thing at the limit, and it is what tapping's left position wants: `{∅, ɹ}` is *SPE*'s parenthesis written as a brace, and either spelling expands to two rules.

In the *target* it is a different proposition, and the answer is captures.md's rather than this document's:

```
'ab -> ba'   refused: 'ab' names 2 units (a b), and a pattern constrains a single unit
'st -> s'    refused: 'st' names 2 units (s t), and a pattern constrains a single unit
```

`{ab, a} -> …` is the span by another name, and the refusal that already exists refuses it in the right place — not because it is a brace, but because one of its expansions is a rule the notation does not accept. **That is the cleanest property of the expansion reading: every constraint on rules is inherited by schemata for free, and not one of them has to be restated.**

**Nesting: allowed, and it changes nothing.** A brace inside a brace expands innermost-first into a longer sequence of ordinary rules. Nothing in the engine sees it. It is also not needed by any shipped family, and the one-brace-per-rule restriction of §6 forbids it anyway, since a nested brace is a second brace.

**On the right of the arrow: refused under `->`, and this one is measured.** *SPE* writes braces over whole rules, so the right-hand side is in scope in the source notation. Under a conjunctive expansion and an obligatory arrow, every alternative after the first is a silent no-op — the first has already consumed the target:

```
a -> {b, c}   on 'kaka' -> 'kbkb';  fired: ['alt1']
a -> {c, b}   on 'kaka' -> 'kckc';  fired: ['alt1']
```

Under `~>` the same schema is meaningful, and it is the one thing a brace adds that nothing else can say — free variation among realizations, each site independently taking one of *m* + 1 outcomes:

```
a ~> {b, c}   on 'kaka' -> ('kaka', 'kcka', 'kakc', 'kckc', 'kbka', 'kbkc', 'kakb', 'kckb', 'kbkb')
```

Nine forms, which is 3², and every one of them is a pronunciation somebody could be offering. So the rule is not "no braces on the right" but **a brace on the right of an obligatory arrow is refused at parse**, on the grounds every other refusal in this parser rests on: a rule that quietly does nothing is worse than a rule that does not parse.

## 8. What it costs the calculus

**Closure, identity, composition: nothing, and the argument is one sentence.** A brace schema expands to a sequence of ordinary rules, so the set of rule sets is unchanged: every schema names a `RuleSet` the parser already accepts. Composition is concatenation and stays concatenation, associativity is a fact about lists, and `variants(f)[0].form == apply(f)` is a fact about how the null choice is enumerated. Nothing on [calculus.md](../calculus.md)'s page is a claim about how the rules were spelled.

**The cap is where a brace becomes visible, and the adversarial case is small.** `unexplored` counts combinations of optional choices declined, and a brace multiplies the *base* of that count rather than the exponent: a rule with *m* alternatives offers each site one of *m* + 1 outcomes, so 2^sites becomes (*m*+1)^sites. One alternative per line, on `aaa`:

```
    m   variants   longest  complete
    1          8         3  True        2^3
    2         27         3  True        3^3
    3         64         3  True        4^3
    4        125         3  True        5^3
    5        216         3  True        6^3
```

The case that actually attacks the cap is a brace inside an optional *insertion*, because each alternative lengthens the form the next expansion scans — the doubly-exponential cascade [calculus.md](../calculus.md) already documents, with *m* now inside one line of notation:

```
    m   variants   longest  complete  unexplored
    1          4         4      True  0
    2         16         8      True  0
    3         64        16      True  0
    4        256        32      True  0
    5        256        24     False  17177628652
```

Five alternatives, one rule, a two-consonant form, and the default limit of 256 is cut with seventeen billion choice combinations unexplored. **Finiteness is not threatened**: every row is a bound, and `complete=False` reports the cut exactly as it should. What is threatened is a reader's sense of scale, because the cascade producing those figures is now one line rather than five. That is a documentation obligation on the brace rather than a defect in the cap, and the sentence to write is short: *m* alternatives cost what *m* rules cost, because they are *m* rules.

## 9. What it costs the metric

Nothing, and it was checked rather than assumed, because [captures.md](captures.md) records a lane that found a change believed to be outside the metric reaching it through a denominator.

The route to rule out is the bridges route: a mechanism that adds a key to the comparison bundle without adding one to any symbol's bundle, and so becomes a term in every denominator. A brace adds neither. It declares no feature, no value, no class and no bridge, it changes no XML, and it introduces no key anywhere. The dependency runs one way and is measurable:

```
module-level import closure of ipakit/metric.py:
  _base _convert analysis constants distance features form hierarchy metric
  models phonemaps segment tract tract_svg validation xsampa

'rules' is not in it.
```

A brace is further from the metric than a capture would have been. A capture would at least have shared `respell` and `compose_unit` with the composer; a brace shares nothing at all, because it is a source transformation that runs before a rule exists.

## 10. What the change is

Shallow, and most of it is one function.

**`RuleSet.parse` gains an expansion step.** A source line containing a brace is expanded into several lines, in the order the alternatives are written, before any of them is handed to `rules.parse`. Every existing refusal, every existing check and every existing type is downstream of that and untouched: `Rule`, `Query`, `Pattern`, `Site`, `Action`, `Edit`, `Derivation`, `VariantSet` do not change.

**`_items` gains brace-aware splitting.** The context splitter reads items separated by whitespace, and a brace's contents contain whitespace and commas — `{[vowel -primary -secondary], [syllabic=+ channel=lateral]}`. A brace has to be one item, which is the job the bracket splitter already does.

**The glyphs are free, and that was checked against the parser rather than against the data.** `{` and `}` do not occur in `ipa.xml` at all, and every spelling a brace would take is refused loudly today, so no shipped rule and no rule anyone could have written changes meaning:

```
't -> {z}'            RuleError: '{z}' spells nothing this inventory registers…
't -> a / _ {z, n}'   RuleError: '{z,' spells nothing this inventory registers…
'{z, t} -> ∅ / _ #'   RuleError: '{z, t}' spells nothing this inventory registers…
```

**The expanded rules are what a `RuleSet` holds.** `len(rs)` counts the expansion and `rs.derive(...).trace()` names each expanded rule, so the ordering a brace abbreviates is never hidden from anyone reading a derivation. That is the answer to §3's visibility problem and it is free — it is what happens if the expansion is done at parse and nothing is remembered about where the rules came from.

**A `Rule` should carry its schema's name, and that is the one addition worth arguing.** A trace naming four rules where the file has one line is a trace whose names do not appear in the source. The cheap answer is an indexed name — `final consonant deletion (1 of 4)` — which is a string, costs nothing, and keeps `trace()` and the file readable against each other.

**Three static refusals**, each closing a rule that would otherwise fire silently or not at all: more than one brace in a rule, with the message naming the cross product; a brace on the right of an obligatory arrow; and a brace with fewer than two alternatives, on the grounds `[]` is refused.

**And one check that is not a refusal.** §11.

## 11. What it costs to be wrong

The expensive mistake is the one *SPE* p. 341 names and the plural nearly made: **a brace where a declared class already says it.** *SPE* had an answer built into the theory — §4 — and it was the evaluation measure, which ipakit has no equivalent of and no reason to grow one. The discipline has to be mechanical instead, and a mechanical check does not reach all of it. The two checks worth having are the two §1 ran, and the honest report on them is mixed:

- **Containment.** If one alternative's extension contains another's, the brace is not a disjunction and the wider alternative already says it. Exact, cheap, inventory-independent — and it catches the American syllabic family's left context, which is one of the two families §1 collapsed.
- **The smallest containing bracket.** If the union of the alternatives is exactly the smallest bracket containing it, one query says it. Also exact and cheap over the declared inventory — and over the declared inventory it catches *neither* of §1's two families, because both collapse by widening rather than by identity. Scoped to the inventory a set actually targets it catches the Spanish trill, and a rule set does not declare that scope.

So the check that would have prevented the mistake this document found twice is a check the repository cannot write from the declaration alone. What it can write is the containment check as a refusal, and the bracket check as a warning over the registered inventory — which will be quiet in exactly the cases that matter most. **That is a limit to record beside the notation rather than a reason to withhold it**, and it is the same limit `docs/reviewing.md` is about: the failure is a well-formed answer, and nothing in the machinery notices.

**The literature's own proposal is a third instrument, and it is a list rather than a computation.** Kenstowicz & Kisseberth close their section on the device with it — *"One approach to the problem would be to allow only certain expressions to be conjoined by the brace notation: that is, to set up a universal inventory of conjoined expressions"* (Kenstowicz & Kisseberth 1979: 364) — and the inventory they sketch admits the conjunction of a consonant and a word boundary and excludes the conjunction of a word boundary and a vowel, which is Tonkawa's accidental pair. It asks a different question from either check above: not *is there a class here?* but *is this conjunction one a rule may state?*, which is the sort §2 does by hand and neither check reaches. Applied here it sorts §2 the way §2 sorts itself — the admitted conjunction is the twelve rules, and the excluded one is the accidental kind, which is what the French schwa family turns out to be. Its authors do not claim it works: *"It is unclear at this stage whether such an approach to restricting the use of braces is viable"* (Kenstowicz & Kisseberth 1979: 364). Nor can this repository adopt it, because a fixed inventory of admissible conjunctions is a claim about what a possible rule is, and every inventory here is declared from data rather than legislated. It is recorded because it is the only instrument on offer that would have sorted both of §2's families, and because what stops it is a property of this repository rather than of the proposal.

**A second thing to be wrong about is what the brace is standing in for.** §2's twelve rules are a syllable structure the transcriptions do not carry, and a brace makes that permanently comfortable to write. If ipakit ever grows a syllabification rule — a rule that *writes* margins rather than reading them — those twelve want revisiting, and the way to keep that live is for the rule files to say so where they write the brace. Hayes and Odden are right about the analysis and wrong about this data, and the difference is worth a sentence in each file rather than a decision here.

**If the one-brace-per-rule restriction is wrong**, the cost is one source line in the tapping family and a later decision about which of *SPE*'s two brackets a second position should get. That is cheap to defer and expensive in the other direction: with two braces allowed and no linkage, the liaison schema parses, expands to sixteen rules, and answers `pəti‿zami`.

**If the conjunctive reading is wrong**, everything in §3 inverts and the *e caduc* pair must never be braced. The reading is the primary's, stated in explicit contrast to the device it is usually confused with, and it is also the only reading on which the shipped French set survives being abbreviated. Two independent reasons, agreeing.

**If braces should not be adopted at all**, what is lost is twelve source lines across four files and one thing nothing else can say — a context that is a class *or* an edge, which is 12 of the 23 rules, which no declaration will reach and which the syllable-based repair costs 8 of 42 words. That is the case to weigh. It is much smaller than the seven-to-one that opened this assessment and it is not nothing.

## 12. What follows

**(a) The two collapses, first, and independently of any decision here.** §1 is two data edits with no notation attached, both measured at 0 corpus words moved, both removing rules the files themselves describe as enumerations. The files' comments should record the widening and its measurement, the way the tapping block records its own.

**(b) Braces, as §10 describes them.** One per rule, terms and not values, refused on the right of an obligatory arrow, expanded at parse into the rules a `RuleSet` holds.

**(c) The containment refusal, in the same commit.** It is the only exact part of §11, and shipping the device without it is shipping the failure mode with no instrument for it.

**(d) The wildcard, separately and on its own merits.** The French schwa family wants a term meaning *any segment*, there is none, and writing it as a brace over two halves of everything is the one use of the device this document would refuse. It is one term matched against a unit that has a feature bundle, and it is not a braces question.

**Not needed: captures, the span, or anything else from [captures.md](captures.md).** Measured, not assumed. The liaison family still wants a reference, still needs the linkage braces do not supply, and is untouched by anything here.

## Spin-off finding: the flat objection to braces is Odden's

Hayes never rejects the notation in his own voice. Both times he raises it he attributes the objection: *"Many linguists have expressed the view…"* (p. 259), *"have struck many phonologists as unsatisfactory"* (p. 264). He presents the syllable-based alternative as *"a widely adopted alternative solution"*, not as the only admissible one. And at p. 220 he teaches the notation and sets it as an exercise, offering it and writing two rules as interchangeable: *"Try to reduce the set to just two natural classes, connecting them with curly brackets… or just write two rules."* There is no index entry for braces or curly brackets in the book, and `grep` over the whole text finds five occurrences, at pp. 220, 259 and 263–64.

The citation in an author's own voice and unhedged is **Odden 2005: 159** — quoted in §4 — which gives both heads of the objection and names the syllable as the better explanation.

The "many linguists" Hayes attributes it to have a name upstream of him. Kenstowicz & Kisseberth put the flat claim on McCawley (1972), state it in one sentence, and decline it as premature (1979: 361–64). So a document wanting a flat statement that braces should be avoided should cite Odden, attribute Hayes as Hayes attributes it, and know that the field's standard reference of the period weighed the same claim against a language and did not take it.

## Reproducing the measurements

Every number here was taken with `PYTHONHASHSEED=0` against this worktree, reading the library only. Nothing was written into the tree.

The universe for the natural-class question is `scripts/sweep.py`'s unit corpus — every phone, bare and under every diacritic that composes and re-spells — taken through `sweep.corpus` rather than through a hand-rolled enumeration, for the reason `review-state.md` gives. Restricting it to the 139 registered phones answers a question about a smaller world than the one the rules run in, and it is where the syllabic lateral `l̩` lives, which is one of the alternatives being measured.

The smallest containing bracket is computed rather than guessed: for each declared segmental feature, `required[k]` is the value every member of the union shares and `excluded[k]` is every declared value no member takes. Its extension is taken through `IPAFeatures._query_matches` against the same bundles, so the answer is the engine's own predicate. Where a bracket is quoted as notation it was parsed back through `rules._pattern` and its extension checked against the computed one.

Every corpus figure rebuilds the shipped set from its own source with the family's rules dropped or replaced, asserts that a rebuild with no changes is identical to `R.shipped(name)` on every corpus word, and compares `apply` — and `variants`, for the one set with an optional rule — against the shipped set. The corpus is `tests/test_rule_sets.py`'s `CORPUS`, imported rather than retyped.

The nine French words in §6 are additions to that corpus, not part of it, and they are labeled as such because that is the point: the widening they catch is invisible to the shipped 29.

A brace schema is prototyped as its expansion, written out as ordered rules and parsed by the shipped parser. That is not a convenience — it is what *SPE* Expansion Convention (b) says a schema is, so a prototype that expanded any other way would be measuring a different notation.

The finiteness and cap figures use `ipa.variants(..., limit=10**9)` where the question is the size of the complete set and the shipped default where the question is whether the cap fires; every row reports `complete`.

The import closure in §9 is computed from the AST of `ipakit/metric.py` following level-1 `ImportFrom` edges, rather than from `sys.modules` — importing any submodule runs `ipakit/__init__.py`, which imports the rule engine, and would have made the answer look the other way.

*SPE* page references are to the printed pages; the Fulcrum PDF's page *n* is printed page *n* − 14. Every rule reproduced from it was read from a 170 dpi `pdftoppm` render, because the OCR text layer mangles stacked matrices and braces systematically. Hayes's page numbers were verified against both the running head and the typesetter's page stamp, and no IPA is quoted from that book's text layer at all.

Kenstowicz & Kisseberth was read the same way and for the same reason: its text layer collapses a stacked brace to a single character and mangles arrows and slashes, so rules (61), (62), (63) and (64) and the conjunctions named on pp. 362 and 364 were read from a 170 dpi render and only prose is quoted from the extraction. Its page numbers are the printed ones, verified against the running head, which carries the section title on the odd pages and the chapter title on the even.
