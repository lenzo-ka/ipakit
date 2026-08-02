# The conlang sound-change appliers: assessment

The constructed-language community has built the most-used rewrite-rule engines outside the finite-state world — **Lexurgy**, **SCA²** and **Brassica** — and they are built on the same object historical phonology uses, which is why **Phono**, a diachronic tool rather than a conlang one, belongs beside them. Which of their capabilities should ipakit gain, and which should it refuse?

**Verdict: ADOPT ONE, REFUSE EIGHT, AND THE ONE WORTH BUILDING IS NOT ON THE LIST.** The wildcard is the adopt, and it is a *narrowing* rather than an addition: the notation already has **fifteen** terms that match every segment and no boundary, every one of them an accident of vacuous satisfaction, and every one of them collapses the shipped family that wants a wildcard with no corpus word moving. Everything else the brief expected to adopt fails its own demand test, and the capability the measurements keep arriving at — a **declared projection**, a rule that states which units it reads and steps over the rest — was not asked for by anybody and is the only change here that unlocks a process every phonology course teaches.

**Propagation has no shipped demand at all, and the textbook demand it exists for is not what it unlocks.** Zero of 12,642 rule-against-word trials over the five shipped sets self-feed: no shipped rule, applied a second time to its own output, moves anything. Run the *cascade* to a fixpoint instead and it is actively wrong on **36 of 156** corpus words — French *petite* derives [pəti], which is *petit*. The textbook case is vowel harmony, and it is real: ipakit needs `(k−1) × (m+1)` copies of one rule for a word of *k* vowels with clusters up to *m* consonants, 9 rules for four vowels and clusters of two, and the bound is the longest word the author thought of. But a repeat-until-fixpoint block does not fix that, and neither does a directional sweep on its own, because ipakit cannot say *the next vowel*. Kaplan & Kay's harmony schema writes `C*`; Lexurgy's harmony idiom is `harmony @vowel ltr:` — two devices, a projection and a direction. ipakit has neither, and **the direction is the half that is free and buys nothing alone.**

**The regularity question settles cleanly, and it settles against the device the brief expected to adopt.** Kaplan & Kay's condition is on the *center* of a rule and not on its contexts, and they say so about this exact case: *"we do not forbid material produced in one application of a rule from serving as context for a subsequent application of that rule, as would routinely be the case for a vowel-harmony rule"* (1994: 346). A left-to-right sweep checks its left context on the output side and its right context on the input side (p. 348), stays regular, and for attested directional harmony is in fact *subsequential* (Heinz & Lai 2013). **Fixpoint iteration is a different operator and it is not closed.** Iterating a *length-preserving* rational transduction to a fixpoint characterizes exactly the context-sensitive languages (Terlutte & Simplot 2000, Cor. 5.5), so length-preservation buys nothing; unrestricted reapplication *"can simulate the computations of an arbitrary Turing machine"* (Kaplan & Kay 1994: 365). Lexurgy's own documentation agrees from the other side: it states that the language is Turing complete and names `propagate`, `ltr` and `rtl` as how.

**The constituency behind these tools is not only conlangers, and the part of it that is historical phonology is already served.** The appliers are modeled on diachronic sound change and one of them is a historical tool rather than a conlang one. Relative chronology and rule interaction — feeding, bleeding, counterfeeding, counterbleeding — are that field's analytic apparatus, and an ordered cascade with a step-by-step trace is what states them. All four are writable in the shipped notation and all four trace: `an → ã` under counterbleeding prints the intermediate `ãn` that the answer does not contain, which is the whole of what makes an opaque derivation teachable. That is a claim worth making rather than a capability worth adding, and §11 makes it. It also changes one verdict — **[captures.md](captures.md)'s refusal of the metathesis span was thin on demand and sound on cost, and it should say which**, because metathesis is an attested sound change in every historical syllabus even though no shipped set writes one.

**Syllable structure is a refusal, and the reason is that ipakit can already write it.** `∅ -> . / [vowel] _ [-vowel] [vowel]` takes `batapa` to `ba.ta.pa` today — a syllabifier is an ordinary rule in the notation that ships. **No conlang applier has onset/nucleus/coda matchers either**: Lexurgy's `::` exists only inside a `syllables:` declaration and its own idiom for "a coda consonant" is to write `_ @nasal .`, which is what ipakit writes; SCA², Brassica and Phono have no syllable notion at all, and Phono says so outright. What ipakit lacks is a *shipped* syllabifier and a repetition operator so one rule covers an onset of any size. And the repair those terms were wanted for does not work even when the margins are written: syllabifying the English corpus first recovers 2 of the 6 nasalization words [braces.md](braces.md) measured and leaves **4** moving, because in *camp* and *tenth* the nasal is not syllable-final under any syllabification.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Does any shipped rule want propagation? | **No. 0 of 12,642** rule-against-word trials self-feed. |
| Does the shipped cascade want a fixpoint? | **No — it is wrong.** 36 of 156 corpus words move; *petite* → [pəti]. |
| Is a directional sweep regular? | **Yes.** K&K's restriction is on the center; context feeding is explicitly permitted (1994: 346, 348). |
| Is fixpoint iteration regular? | **No, and not narrowly.** Length-preserving iteration = the context-sensitive languages (Terlutte & Simplot 2000). |
| Does the sweep get harmony *here*? | **No.** ipakit cannot state "the next vowel"; K&K write `C*`, Lexurgy writes a filter. |
| What does harmony cost today? | **(k−1) × (m+1) rules.** 6 for three vowels, 12 for four vowels and clusters to three. |
| Do the appliers give rules onset/coda? | **None of the four.** Lexurgy's `::` is syllabifier-only; the other three have no syllables. |
| Can ipakit write a syllabifier today? | **Yes.** `∅ -> . / [vowel] _ [-vowel] [vowel]` → `ba.ta.pa`. One rule per onset size. |
| Does syllabifying rescue the syllable-final repair? | **Partly. 6 of 35 → 4 of 35.** The residue is linguistic, not notational. |
| Shipped demand for a wildcard? | **One family, 2 rules → 1**, and dropping the item instead is wrong on 2 of 29 words. |
| Is there a wildcard today? | **Fifteen**, all by vacuous satisfaction, all collapsing that family at 0 of 29. `[-word]` is accidentally exact. |
| What is the wildcard's spelling? | **`[]`** — Lexurgy's, and the spelling ipakit refuses today as "an empty query". |
| Does any applier weight change by probability? | **None of the four.** All are deterministic. There is nothing here to refuse. |
| Is per-rule optionality a step backwards? | **No — it is a different question.** Brassica ships both; `-?` is lexical diffusion, `-??` is ipakit's `~>`. |
| Are rule blocks a substitute for `RuleSet`? | **`then:` yes, `else:` no.** `else:` is the Elsewhere Condition, and Latin stress measured gives `kˈamˈiːnus`. |
| Do romanizers need machinery? | **No. Already there.** Every `Step.after` is a form, and every notation is a function of one. |
| Do the appliers do SPE's numbered permutation? | **One of four.** Three do *reversal of the matched target*; Lexurgy numbers, and is the one that is Turing complete. |
| Does that reopen the metathesis refusal? | **The demand half, yes.** The cost half holds: Brassica's own stated invariant is "targets never overlap". |
| Are the appliers' natural classes declared? | **No.** SCA² has no features; Lexurgy's `class` is enumerative and its documentation says so. |
| Do the appliers scan positionally? | **All four.** ipakit is the only one applying against a snapshot. |
| Would a sweep move the shipped data? | **No**, and for the same reason there is no shipped demand: nothing self-feeds. |
| Does anything serve conlangers alone? | **Yes, and it is all on one side of one line**: a wordlist. ipakit has no lexicon, and that is the line. |
| Does the engine already serve historical phonology? | **Yes.** Feeding, bleeding, counterfeeding and counterbleeding all state and trace; `an → ã` shows its own `ãn`. |

## Sources

**Every quotation below was checked against a dated local copy of the source**, taken on **2 August 2026**. That matters more here than in the other documents in this directory: four of these sources are living documentation pages that can be edited or moved under a citation, and one claim about a tool is taken from its source code rather than from its documentation and is labeled where it is made.

**Read directly, and primary.**

Lexurgy — the reference is the specification; every claim below is from it or from the tutorial it links.

- Reference: <https://www.lexurgy.com/sc/docs/reference> (§§ propagation, ltr, rtl, syllables, romanization, matrix-elements, filters, captures, sequential, hierarchical, class-declarations)
- Tutorial, Control Flow: <https://www.lexurgy.com/sc/docs/tutorial/controlflow>; Syllables: <https://www.lexurgy.com/sc/docs/tutorial/syllables>; Basics: <https://www.lexurgy.com/sc/docs/tutorial/basics>
- How To: <https://www.lexurgy.com/sc/docs/howto> (§ turing-completeness, § stress-assignment)
- Grammar, for the complete modifier keyword set: <https://github.com/def-gthill/lexurgy/blob/HEAD/core/src/antlr/sc/Lsc.g4>

SCA² — Mark Rosenfelder. The help page is the whole of the documentation.

- <https://www.zompist.com/scahelp.html>, application at <https://www.zompist.com/sca2.html>

Brassica — Bradley Rosenfeld.

- Reference: <https://github.com/bradrn/brassica/blob/master/docs/Reference.md>; Writing Sound Changes: <https://github.com/bradrn/brassica/blob/master/docs/Writing-Sound-Changes.md>; Using Brassica: <https://github.com/bradrn/brassica/blob/master/docs/Using-Brassica.md>

Phono — Lee Hartman. The SIU page the literature cites is gone (404, and no Wayback capture of it was reachable); the program is live at a new host and the manual is the primary.

- <https://langnhist.weebly.com/phonoTOC.html>, User's Manual (rev. 21 June 2018): <https://langnhist.weebly.com/files/theme/userManual.pdf>

Computational phonology.

- Kaplan & Kay, "Regular Models of Phonological Rule Systems", *Computational Linguistics* 20(3), 1994: <https://aclanthology.org/J94-3001/>. §4 pp. 346–351, §5.2 p. 355, §5.5–5.7 pp. 360–363, §6 pp. 364–366.
- Mohri & Sproat, "An Efficient Compiler for Weighted Rewrite Rules", ACL 1996: <https://aclanthology.org/P96-1031/>. Abstract and §1 for the finiteness condition, §3.1 for the left-to-right cascade, Theorem 1 in §4.
- Karttunen, "The Replace Operator", ACL 1995: <https://aclanthology.org/P95-1003/>. §2.3, on the oriented versions.
- Heinz & Lai, "Vowel Harmony and Subsequentiality", MOL 13, 2013: <https://aclanthology.org/W13-3006/>. §4, and the hierarchy in Fig. 6. Their Theorem 4 is the other half worth knowing: **Majority Rules is not regular**, so "harmony is finite-state" is true of the directional theories and false of some logically possible alternatives.
- Terlutte & Simplot, "Iteration of rational transductions", *RAIRO – Theoretical Informatics and Applications* 34(2), 2000: <https://www.numdam.org/item/ITA_2000__34_2_99_0/>. The introduction, and Corollary 5.5.
- Hume, "Metathesis: Formal and Functional Considerations", in Hume, Smith & van de Weijer (eds.), *Surface Syllable Structure and Segment Sequencing*, HIL Occasional Papers, Leiden 2001: <https://metathesisinlanguage.osu.edu/pdfs/hume_metathesisS5.pdf>. [captures.md](captures.md) cites it for the same argument; §4 here quotes two more sentences of the same passage.

**Read at one remove, and labeled where used.**

Lexurgy's `propagate` implementation does cycle detection rather than bounding its iterations, and reports a diverging word by name. That is read off the source rather than the documentation — the documentation says nothing about termination at all — and it is cited as source rather than as specification: <https://github.com/def-gthill/lexurgy/blob/HEAD/core/src/main/kotlin/com/meamoria/lexurgy/sc/ChangeRules.kt>.

Webb 1974 and Janda 1984 in §4 are quoted **through** Hume 2001 and are labeled there. The undecidability results named in §1.3 — Post 1947 and Markov 1947 for the word problem, Sénizergues 1995 for length-preserving systems — are standard and no quotation rests on them. Elgot & Mezei 1965 for composition closure and Kuroda 1964 for the linear-bounded-automaton characterization are cited through Terlutte & Simplot and through Berstel's textbook rather than read; both are paywalled. Brassica's documentation attributes its application algorithm to a 1973 dissertation on the directionality of phonological rule application, and that attribution is reported as Brassica's rather than checked against the dissertation.

**Not relied on.** Karttunen's "Directed Replacement" (ACL 1996) is the obvious next citation for directionality and is the wrong one: its `@->` is *unconditional*, and directionality there governs match factorization rather than context checking.

## 1. Propagation

### 1.1 The shipped demand is zero, and the fixpoint is worse than zero

The question a shipped rule set can answer is mechanical: apply each rule, then apply *the same rule* to its own output, and see whether anything moves. A rule that moves is a rule that wanted to iterate.

```
5 sets, 86 rules, 156 corpus words
  self-feeding rule/word pairs:  0

cross-set: every rule against every corpus word of every set
  86 rules x 147 distinct words = 12,642 trials
  self-feeding trials:  0
```

Not one shipped rule is waiting on `propagate`. That is the whole of the shipped-demand measurement for the brief's highest-ranked prior, and it is a clean negative.

The *cascade* is a different question and it answers in the other direction. Running a whole set until it stops changing is not the same as iterating one rule, and it is measurably wrong:

```
cascade run to a fixpoint instead of once:  36 of 156 words move

  french-liaison   pətitə      pətit       ->  pəti
  french-liaison   pətitə‿ami  pətit‿ami   ->  pəti‿tami
  japanese-moraic  mɪlk        miɾuku      ->  miːɾuːkuː
  japanese-moraic  bʊk         bukːu       ->  buːkːuː
```

*Petite* is [pətit]; a second pass takes the newly final /t/ off and derives *petit*. The Japanese set maps an English inventory onto a Japanese one, so a second pass maps the answer again and lengthens every epenthetic vowel. Each set reaches a fixpoint in one or two passes and none diverges, so this is not a termination problem — it is that **a broad-to-narrow cascade is a transduction, not a normalization**, and a fixpoint is the wrong object to ask it for. That is worth stating because `propagate` in Lexurgy is a *block* modifier and a block can be a whole rule set.

### 1.2 The textbook demand is real, and it is not propagation

Vowel harmony is what a phonology class means by iteration, and ipakit states it once and spreads one segment:

```
[vowel] -> [backness=α] / [vowel backness=α] [-vowel] _

  tetɑtɑtɑ  ->  tetatɑtɑ  ->  tetatatɑ  ->  tetatata
```

Three passes for three targets. Written as a cascade of copies — the shape [calculus.md](../calculus.md) prices at *"one copy per pass, and one per cluster width"* — the count is bounded and the bound is the word:

```
harmony over a word of k vowels, clusters of 0..m consonants between them

  3 vowels, clusters 0..2:   9 words,   6 rules   (3 cluster sizes x 2 passes)
  4 vowels, clusters 0..2:  27 words,   9 rules   (3 cluster sizes x 3 passes)
  4 vowels, clusters 0..3:  64 words,  12 rules   (4 cluster sizes x 3 passes)
```

Two things multiply, and only one of them is iteration. **The other is that ipakit's context is a fixed number of items**, so a rule that reaches across one consonant does not reach across two:

```
[vowel] -> [backness=α] / [vowel backness=α] [-vowel] _

  tetɑ     ->  teta        one consonant
  testɑ    ->  testɑ       two, and the rule does not fire
  testrɑ   ->  testrɑ      three
  teɑ      ->  teɑ         none
```

This is the finding that changes the recommendation. **A repeat-until-fixpoint block does not repair the second column, and neither does a directional sweep.** Both are about *when* a rule is asked again; neither is about *what a rule can see*. The primary sources agree from both ends: Kaplan & Kay's harmony schema is `Vᵢ → Bᵢ / Bⱼ C* __` (1994: 346), with a Kleene star in the context; Lexurgy's documented harmony rule is `harmony @vowel ltr:` — a **filter** naming the vowels, and a direction. Each needed a second device, and it is the same second device.

### 1.3 The regularity question, settled

This is the paragraph the brief asked for, and the answer is sharper than the question.

**Kaplan & Kay's restriction is on the center of a rule, not on its contexts.** The abstract states the theorem as holding *"if its non-contextual part is not allowed to apply to its own output"* (p. 331), and §4 gives the necessity proof [captures.md](captures.md) already quotes — an optional `ε → ab / a __ b` allowed to rewrite what it introduced maps a regular language to `{aⁿbⁿ}`. What follows in the same paragraph is the sentence that decides this design:

> However, we do not forbid material produced in one application of a rule from serving as context for a subsequent application of that rule, as would routinely be the case for a vowel-harmony rule, for example. It is this restriction on interactions between different applications of a given rule that motivates the notation φ → ψ / λ __ ρ rather than [λφρ → λψρ]. (p. 346)

**A directional sweep is exactly that permitted interaction**, and they build the transducer around it:

> In a left-to-right rule, the left context of the rule is to be verified against the portion of the string that results from previous applications of that rule, whereas the right context is to be verified against the portion of the string that has not yet been changed but may eventually be modified by applications further to the right. (p. 348)

Mohri & Sproat's cheaper cascade has the same shape — right context marked before the replacement, left context checked after it (§3.1) — and their Theorem 1 carries the same condition, *"does not rewrite its non-contextual part"*. Karttunen's replace operator gives the same configuration a different name, and the naming trap is worth recording so a reader does not think there are two results: what Kaplan & Kay call **left-to-right**, Karttunen 1995 calls **right-oriented** (`//`), and says of it that the oriented versions *"can model rightward or leftward iterating processes, such as vowel harmony and assimilation"* (§2.3). Heinz & Lai sharpen it: attested directional harmony is not merely regular but **subsequential** — one deterministic pass, no backtracking (§4).

**Fixpoint iteration is a different operator, and it is not closed.** The `R*` in Kaplan & Kay's closure table is repeated *concatenation*, not repeated *composition*, and the notation invites the confusion. Composition of rational relations is rational (Elgot & Mezei 1965, as Berstel Thm. III.4.4), so any **fixed** number of passes collapses to one transducer — which is exactly why Mohri & Sproat's condition is phrased as *"any more than a finite number of times to its own output"*. Iterating without a fixed bound does not:

> The subset of rational transductions is closed under composition but not under iteration. (Terlutte & Simplot 2000: 100)

And the sharp form, which answers the tempting escape hatch before anyone reaches for it — a length-preserving restriction buys **nothing**:

> Let A ⊆ Σ* be a language over Σ. It is a context-sensitive language if and only if there exist a finite alphabet X and a length-preserving rational transduction τ such that A = (X*)τ⁺(∩Σ*). (Corollary 5.5)

The one-line counterexample worth keeping beside it: `R = {(aⁿ, a²ⁿ)}` is rational, and `R⁺` applied to `a` is `{a^(2^k)}`, which is not regular. Kaplan & Kay say the same thing in phonological terms — *"In the worst case, in fact, we know that the computations of an arbitrary Turing machine can be simulated by a rewriting grammar with unrestricted rule reapplication"* (p. 365) — and **Lexurgy's own documentation confirms it from inside the tool**, stating that the language is Turing complete and that *"the key is usually to add temporary symbols (often diacritics) and use Lexurgy's iterative constructs (`propagate`, `ltr`, and `rtl`)"*.

Termination follows. It is undecidable in general (Post 1947, Markov 1947 for the word problem; Sénizergues 1995 for length-preserving systems), and Kaplan & Kay note that even a single left-to-right rule can fail to terminate: `ε → b / b __` *"will never terminate, and no finite-length output is ever produced"* (p. 347). Per-input termination under a length-non-increasing restriction is decidable — the reachable set from a fixed string over a finite alphabet is finite — but that is an observation about a search over a finite graph, not a theorem anybody states, and it costs what a linear-bounded automaton costs.

**What Lexurgy actually does about termination is worth knowing and is not in its documentation.** `PropagateBlock` memoizes every intermediate form and raises if it revisits one, reporting the last few versions of the word by name. So oscillation is caught; monotonic non-convergence is caught only by a thread interrupt. Four documentation pages and the cheat sheet say nothing about iteration caps or loops. That is not a criticism of a good tool — it is what "unbounded" costs a documenter, and it is the cost ipakit would take on.

### 1.4 What ipakit gives up, and what it would take

ipakit is **stricter than Kaplan & Kay's condition**, and pays for it. `Query.sites` finds every site against one snapshot, so a rule's output is invisible to that rule as a *center* — which is the condition — and also as a *context*, which is not. The library's own words are accurate about the mechanism and understate the consequence: *"within a single rule, every site is found against a snapshot before any is rewritten, so a rule cannot read its own output and a pass terminates by construction."* Termination is real; the price is that the regular, subsequential, textbook mode of application is out of reach.

The convergence worth recording: **ipakit's agreement variables already are Kaplan & Kay's batch rule.** They compile the α-notation into a finite batch of subrules applied as one (§5.6, p. 361), and they show that the batch is *necessary* — an ordered cascade of separate left-to-right rules gets Turkish wrong and no reordering fixes it:

> The proper results in all cases come only if we describe Turkish vowel harmony with rules that proceed left to right through the string as a group, applying at each position whichever one matches. (pp. 349–350)

`[vowel] -> [backness=α] / [vowel backness=α] [-vowel] _` is that group, written once. So of the three things harmony needs — a batch of alternants, an unbounded context, a directional sweep — ipakit has the first, and it is the one that took the most notation to build.

**On the sweep, ipakit is the outlier and the field is unanimous.** All four appliers apply a rule by a positional scan rather than against a snapshot. Phono *"traverses the length of the word from left to right, making each segment, momentarily, the focus segment"*. Brassica's documented algorithm scans positions left to right and cites a dissertation on the directionality of phonological rule application. Lexurgy makes the non-directional mode the default and offers `ltr` and `rtl` as opt-ins, and its harmony idiom takes the opt-in. SCA² has no directive but its report is position-indexed.

**And adopting the sweep would change nothing on the shipped data, which follows from §1.1 rather than needing its own measurement.** A directional sweep differs from simultaneous application only where a rule's own output falls inside its own context, and no shipped rule self-feeds in 12,642 trials. That is the argument for it being cheap and the argument against it being urgent, and they are the same fact.

**Verdict on propagation: REFUSE the fixpoint. The directional sweep is a defensible future change and is not worth making on its own.** Refusing the fixpoint is not a close call: no shipped rule wants it, the cascade-level version is wrong on 36 of 156 words, it leaves the regular relations under every restriction including length-preservation, its termination is undecidable, the one tool that ships it does not document that it can diverge — and, for the constituency §11 is about, a form iterated to convergence no longer says which pass changed it, which is the question relative chronology *is*. The sweep is the opposite on every count — regular, subsequential, bounded by the form, permitted by the exact condition ipakit already meets, and what every comparable tool does — but on the shipped data it changes nothing, and on the process it exists for it changes nothing either without §10.

## 2. Syllable structure

### 2.1 No applier gives a rule an onset or a coda

The brief's prior was that `nucleus` is half-present and onset and coda are the gap. Both halves need correcting.

**`nucleus` is not available to a rule at all.** It is a `DERIVED_CLASSES` member in `ipakit/constants.py`, and what that governs is `applies` — which features a *description* reads out. It is a different namespace from the query language, and the rule parser has never heard of it:

```
[nucleus] -> a     RuleError: 'nucleus' resolves to no feature term; ... not a declared
                   feature, a declared value, a declared natural class, or a short name
[consonant] -> t   the same
[obstruent] -> t   parses -- a declared natural-class, read off <value natural-class=...>
```

So the gap is three terms, not two. But it is also not a gap, because **onset and coda are not properties of a segment**. `nucleus` is a predicate over a feature bundle — vowel-or-syllabic — and could be a query term tomorrow. Onset and coda are positions in a structure the bundle does not carry, and no declaration reaches them.

**And the appliers agree, unanimously.** Lexurgy is the only one of the four with syllables at all, its structured syllable patterns do separate `onset :: nucleus :: coda`, and **those names exist only inside a `syllables:` declaration**. A rule sees `.` (a break), `!.` (not a break), `<syl>` (a whole syllable) and syllable-level features. The documentation's own idiom for conditioning on a coda is to write the environment out — `@vowel => [+nasalized] / _ @nasal .` — which is, term for term, what the shipped American English set would write. SCA² has no syllable notion at all — `#` is a *word* boundary and there is nothing below it — and no suprasegmentals either. Brassica has no onset/coda primitives; syllables are written structurally, `C* Vu C*`. Phono says it in one line: *"Phono does not recognize syllable boundaries"*, and emulates syllable position with `COUNT` lines over segments.

Four systems, one of them with a full syllabifier, and not one of them gives a rule an `onset` term. That is a strong prior against adding one.

### 2.2 A syllabifier is an ordinary rule, today

The thing that is missing is not a term. It is the structure, and ipakit can already write it:

```
∅ -> . / [vowel] _ [-vowel] [vowel]        batapa    ->  ba.ta.pa
. -> ∅                                     ba.ta     ->  bata
```

A rule that *writes* margins is what makes `. _` mean onset and `_ .` mean coda, and both of those are notation that already works. This is the same move [rules.md](../rules.md) makes for the surface projection — *"that it is a rewrite is the design and not the implementation"* — and it lands the same way: a syllabifier is a `RuleSet`, so it composes, it traces, and a caller can read what it did.

Two limits, both real and both narrow. Maximal onset over a cluster needs one rule per onset size, because a context item is one unit and there is no repetition operator:

```
∅ -> . / [vowel] _ [-vowel] [vowel]                  bataspa   ->  ba.taspa
plus  ∅ -> . / [vowel] _ [-vowel] [-vowel] [vowel]   bataspa   ->  ba.ta.spa
```

And nothing ships one. `ipakit/data/rules/` holds five sets and none of them writes a margin, so the affordance exists and is undiscoverable.

### 2.3 The repair the terms were wanted for still does not work

[braces.md](braces.md) §2 found twelve shipped rules whose brace is standing in for syllable-finality, measured the textbooks' repair, and found it moves 8 of 42 Japanese words and 6 of 35 English ones — concluding that *"an unwritten margin is unspecified, not absent"*. That leaves an obvious question open: would it work if the margins *were* written?

Measured, with a maximal-onset syllabifier applied to the English corpus first:

```
American nasalization, both right contexts replaced by one syllable margin

  as written, no interior dots     6 of 35 words move
  syllabified first                4 of 35 words move

      ˈt͡ʃænl    ˈt͡ʃæ̃nl̩   ->  ˈt͡ʃænl̩
      kˈæmp      kʰˈæ̃mp̚   ->  kʰˈæmp̚
      ˈɪnfənt    ˈɪ̃ɱ.fə̃nt̚ ->  ˈɪ̃ɱ.fənt̚
      tˈɛnθ      tʰˈɛ̃n̪θ   ->  tʰˈɛn̪θ
```

Two of the six were the missing dots and come back. **Four are not, and the reason is linguistic**: in *camp* and *tenth* the nasal is followed by another coda consonant, so no syllabification puts a margin after it, and the rule wants *pre-consonantal* rather than *syllable-final*. Hayes's repair is right about Cibaeño and Yawelmani and wrong about this family, independently of what the transcription carries. braces.md's conclusion holds and its reason is now two reasons.

**Verdict on syllable structure: REFUSE `onset` and `coda` as query terms. `nucleus` is a defensible small adopt on its own merits and is not a syllable question.** What follows instead is in §12: ship a syllabifier as data, and say in the notation that a margin-conditioned rule is what reads it.

**On the audience test.** The speech-ML and articulatory audiences work in syllabic units, and a syllabic representation model wants syllables — that is exactly right, and it is an argument for a **syllabifier**, which produces units, and not for an `onset` term, which consumes structure somebody else has to produce. The two are easy to conflate and the measurement separates them: `. -> ∅` and `∅ -> .` already move a transcription between the two states.

## 3. The wildcard

[braces.md](braces.md) §12(d) refused to solve this with braces and said it should be taken *"separately and on its own merits"*. Here are the merits.

**There is no honest term that matches every segment, and there are fifteen dishonest ones.** That is the finding, and it inverts the question.

Every term the query language can build was parsed through `rules._pattern` and matched against every unit of the canonical corpus. Seventeen match all 8,616. Two of those — `[-primary]` and `[-secondary]` — are an artifact of the corpus, which holds no stressed unit, and they drop out when the test is widened to `ˈa ˌa aː a˧˦ a͜ɪ ␣`. **Fifteen survive:**

```
[-epiglottis]  [-lower-lip]   [-major]      [-minor]        [-normal]
[-phrase]      [-sequential]  [-simultaneous] [-steady]     [-syllable]
[-tongue-dorsum] [-tongue-front] [-utterance] [-vocal-folds] [-word]
```

Every one of them works by **vacuous satisfaction**: it names a value the unit could not have declared, so the exclusion holds for free. This is [braces.md](braces.md) §7's sentence — *"exclusion is value-disjunction over the units that declare the feature, and vacuous satisfaction over the units that do not"* — read as far as it goes. And `[-word]` is the sharpest of the fifteen, because it is accidentally *exact*: `level` is a boundary feature that no segment declares, and a boundary has no bundle for a query to be compared against, so `[-word]` picks out **every segment and no margin**, which is precisely what a wildcard should do.

The empty bracket, meanwhile, is refused:

```
'a -> b / [] _'    RuleError: '[]' is an empty query
'a -> b / * _'     RuleError: '*' spells nothing this inventory registers
```

**So the question is not whether ipakit should gain a wildcard. It has fifteen, and any of them works.** Measured against the family that wants one:

```
the French schwa pair collapsed with each of the fifteen

  12 rules -> 11;  apply moved 0/29, variants moved 0/29     for all fifteen
```

**The shipped demand is that one family, and it is not decorative.** The French final-schwa pair is `[vowel]` or `[-vowel]` before a consonant — a partition of everything, which is a wildcard written as two halves. What the pair means is *some segment, then a consonant*, and the requirement is that the consonant not be word-initial. Drop the item instead of collapsing it and the set is wrong:

```
ə -> ∅ / [vowel] [-vowel] _ #        }  2 rules
ə -> ∅ / [-vowel] [-vowel] _ #       }

replaced by  ə -> ∅ / [-vowel] _ #      12 rules -> 11;  2 of 29 corpus words move
    lə   ->  l      (le)
    ʒə   ->  ʒ      (je)
```

So the family holds the position on purpose, and a wildcard is the one term that states it. Two rules become one, and the alternative is not a wider class — there is no wider class — it is the two rules that are shipped, or one of the fifteen accidents.

**That makes `[]` a narrowing of the language rather than a widening**, which is the argument for it. Every one of the fifteen is a rule whose meaning depends on a value continuing to be undeclarable by a segment: write `[-normal]` for *any segment* and it stops being one the day `length` gets a spelled `normal` mark, silently, in a rule file that says nothing about length. Adding `[]` costs one term, gives the intent one spelling, and turns fifteen accidental universals into a defect somebody can name — which is what the spin-off finding below does to the sharpest of them.

**It is also the positive spelling of the one position negation ipakit needs.** [rules.md](../rules.md) records the policy: *"Classical SPE negates feature values, not context positions, so the positive statement is the idiomatic one. Feature-value negation (`[-voiced]`) is available; position negation is not, and this is why it has not been needed."* This family is where it is needed, and the wildcard is how the policy is kept: *a segment stands here* rather than *the word does not begin here*.

**The spelling should be `[]`, and that is Lexurgy's.** Its reference says of an empty feature matrix that *"the case of zero values (i.e. an empty pair of brackets) is called a 'wildcard', since it matches any sound"*, and its tutorial that *"the symbol `[]` matches any single sound"*. ipakit refuses that spelling today with a message that would become the definition. Nothing else is free and honest: `*` and `@` spell nothing the inventory registers and are refused loudly, so either is available, but a bracket is where ipakit says *described, not spelled*, and an empty description is the widest one. The refusal is currently the right refusal for the wrong reason — an empty query is not meaningless, it is the identically-true one.

**What it must not match.** A boundary and a wildcard are the disjointness [braces.md](braces.md) §2 turns on: a query is compared against a feature bundle and a boundary has none, so `[]` matches segments and not margins, and the twelve brace rules are untouched by it. A **zero** is the live question, and it is not this document's to settle: `[-vowel]` matches a zero vacuously today, which captures.md's spin-off finding names as a defect, and whatever repair that gets decides what `[]` does at a zero. The two must be settled together or `[]` will inherit an answer nobody chose.

**Verdict: ADOPT, spelled `[]`, matching any segment and no boundary, and not before the zero question is settled.** It is the only adopt in this document, its shipped demand is two rules, and it is the smallest change here.

## 4. Metathesis

[captures.md](captures.md) refused the multi-term span. The brief asked whether the conlang implementations know something that refusal missed. They know one thing, and it narrows the ask rather than reopening it.

**The field is split three to one, and the split is the finding.** Three of the four write metathesis as *reversal of whatever the target matched*, with no numbering anywhere:

```
SCA²      nt/\\/_V     "will turn all instances of nt before a vowel to tn.
                        (To be precise, the input string is reversed;
                        it can be of any length.)"
Brassica  C ʔ / \ / V _   "produces in reversed order the graphemes which
                           were matched in the target"       namʔe -> naʔme
Phono     5: SWAP (*) (*-1)                                  two named positions
```

The fourth, **Lexurgy, writes exactly SPE's numbered permutation** — `@stop$1 @fricative$2 => $2 $1` — and is the only one of the four with numbered captures at all. It also has repeaters, so `([] [])$1` and `[]*` make the captured span unbounded, and it is the only one of the four that is Turing complete. Those are not unrelated facts, and taking the two together is the whole of what this section adds.

**Hume's objection reaches Lexurgy and does not reach the other three.** Her complaint is that the transformational formalism *"fails to rule out unattested cases in which sounds switch over any number of consonants and vowels, e.g. C₁V₂C₃V₄C₅V₆C₇ → C₇V₂C₃V₄C₅V₆C₁"* — a reversal operator cannot write that, because it has no numbering to permute, and Lexurgy can. So [captures.md](captures.md) is not citing an objection to a notation nobody built; it is citing an objection to the notation exactly one of them built, while three converged on the weaker device instead. That convergence is evidence about what the phenomenon needs, and captures.md's own closing sentence anticipates the conclusion: *"a span bounded at two units is a different and more defensible proposal from the general one."*

**But the refusal's actual reason is untouched, and Brassica confirms it.** captures.md refuses the span because `Query.sites` promises *"every non-overlapping position where this environment holds"*, and that promise holds because a target is one term whose match cannot interleave with the next one's. Brassica has multi-grapheme targets, and its documentation states the same invariant as a governing principle — *"targets never overlap with each other"*, while "environments may overlap with targets, as well as with themselves" — and ships a `-no` flag to control what happens at the boundary. An independent implementation arriving at the identical invariant, and needing a per-rule flag to manage it, is the best available confirmation that captures.md priced the change correctly rather than overpricing it.

**Shipped demand remains zero.** No shipped rule set wants metathesis, and the process that comes nearest — French resyllabification — is written as copy-then-delete with the file arguing that reading on its merits.

**But the demand argument is where this section has to be honest, because it is the one captures.md's refusal was thinnest on.** That document weighs the span against *"metathesis and nothing else"*, with no shipped set wanting it and the metathesis literature's own objection to the notation as the counterweight. Both halves are about the *span's* cost and about SPE's notation; neither is a measurement of how much the process is wanted. Metathesis is an ordinary, attested, much-discussed **sound change**, it is in every historical phonology syllabus, and all four appliers implement it — which is exactly the "no shipped demand, but a course covers it" case this document's own test says counts. Judged by that test rather than by the shipped sets, metathesis passes the second half of the demand measurement, and captures.md does not apply the second half to it.

**And the same source captures.md quotes says where that demand lives, two paragraphs above the sentence it quotes.** Hume opens by recording the position that metathesis is not a synchronic process at all — *"Webb (1974) claims that metathesis does not exist as a regular phonological process in synchronic grammar"* — and reports the reason theorists resist admitting it, that doing so risks *"a Pandora's box of implausible-seeming…processes"* (Janda 1984: 92, quoted by Hume). Both attributions are at one remove and are labeled here as such; Hume herself argues against that position at length. What the passage establishes for this document is not who is right about metathesis but **which side of §12's line the demand sits on**: it is a change over time, disputed as a synchronic process, and every implementation of it belongs to a family of tools that walk a wordlist through a chronology. That does not make the demand less real. It makes it demand for the thing ipakit deliberately is not.

**What does not change is the cost, and that is still the refusal.** `Query.sites` promises non-overlapping positions because a target is one term; a span breaks the promise, `_apply_edits` splices on the assumption that spans are disjoint, `_carry_prosody` has to decide what a permuted span's marks do, and `_check_no_exchange` has to run per term. None of that is softened by anybody wanting the feature. Brassica's independent arrival at the identical invariant, with a flag to manage it, says the price is real rather than imagined.

**Verdict: THE REFUSAL STANDS, ON COST AND NOT ON DEMAND, AND BOTH THE CLOSURE-LIST ENTRY AND `captures.md` SHOULD SAY WHICH.** Three things follow, and none of them is "build it".

The entry [calculus.md](../calculus.md) carries says metathesis *"needs a target of more than one term and a permutation to apply to it"*. The permutation half should go: three of four implementations converge on a **bounded target span and a reversal**, which is a smaller and better-motivated object, and Hume's objection applies to the numbering rather than to the reversal.

[captures.md](captures.md) §7's sentence *"the span buys metathesis and nothing else"* is true and reads as a dismissal. What it should say is that metathesis is a real and taught process with no shipped demand, and that the span is refused because of what it costs `Query.sites`, so that a reader who arrives with historical demand in hand knows which argument they have to answer.

And if it is ever revisited, the proposal to price is the **two-unit reversal**, not the general permutation: the width is bounded by the notation rather than by the form, the non-overlap property becomes checkable rather than accidental, and Lexurgy is the worked example of what taking the general version instead costs — numbered captures plus repeaters, and a language its own documentation calls Turing complete.

## 5. Sporadic change, and per-rule optionality

**No applier weights change by probability. None of the four.** This is a correction to the brief rather than a refusal: there is nothing here to refuse. SCA² has no sporadic mechanism of any kind and no randomness. Lexurgy has none, confirmed against the reference, the cheat sheet, the tutorial and the complete modifier keyword set in its grammar; "optional" in Lexurgy is the zero-or-one *repeater*, a structural device with nothing stochastic about it. Phono states the opposite assumption outright — *"Phono operates on the assumption that a large portion of the vocabulary of any language is regular in its historical development"*. Brassica has the flag people mean, and it is not probabilistic either.

**Brassica ships two sporadic flags, and the pair is the finding.** Verbatim:

> - `-?` causes the whole rule application to produce one additional result, which is identical to the input word.
> - `-??` causes an additional result to be produced for each successful replacement, which is identical to the word before that replacement.

`-??` is ipakit's `~>`, exactly — per site, every branch enumerated, no sampling. `-?` is per rule and per word, and what it models is not free variation but **lexical diffusion**: Brassica's own worked example is the Middle English *meet* / *meat* / *great* merger, where a word either underwent the change or did not, and the grammar-writer picks the branch that matches the attested reflex.

So the prior that a per-rule flag would be a step backwards is right about the outcome and wrong about the reason. It is not a coarser version of `~>`. It is a different question, and the difference is where the variation lives: `~>` says *this speaker may say it either way*, `-?` says *this word did or did not undergo this change*. The second is a fact about a lexicon.

**Lexical diffusion is real historical linguistics, so the refusal deserves a number rather than an assertion.** Per-rule and per-site optionality differ only where a rule finds more than one site in one word, and over the shipped sets that is rare:

```
rule/word pairs where a shipped rule finds at least one site:  296
                                    ... more than one site:      6
```

Six of 296. So on this data `-?` and `-??` would agree 98% of the time, and the flag's whole content is what happens in the other six — where the per-site reading says *these two schwas dropped independently* and the per-rule reading says *this word underwent the change, so both did*. The second is the right reading for a diachronic change diffusing through a lexicon, and it is the wrong reading for the *e caduc*, which [calculus.md](../calculus.md) spends a section on and which the shipped French set depends on.

**ipakit has no lexicon**, so there is nothing for a per-word claim to be a claim about: `variants` is handed one form, and the branch that answers "this word did not undergo the change" is `variants(f)[0]`, already there and already documented as what `apply` returns. What is missing is not the flag but the wordlist it would be indexed by, and that is §12's line.

**Verdict: REFUSE probability weighting (nothing to adopt, and [calculus.md](../calculus.md) already refuses ranking with its reasons). REFUSE per-rule optionality (nothing to attach it to), and record what would change the answer:** a wordlist-level entry point. If one is ever built, this is the first capability to reconsider, and the measurement to redo is the six.

## 6. Rule blocks and stages

The prior was that blocks are a substitute for the `RuleSet` composition ipakit already has. Half of that survives.

**`then:` is exactly `RuleSet` concatenation, and should be refused for that reason.** Lexurgy's sequential block *"consists of a list of other blocks separated by `then:`. Each nested block is applied in sequence, as if they were separate rules"*. SCA²'s `-*` stage markers and Brassica's `report` are the same idea in a different place: a name attached to a point in a cascade. ipakit already has that twice over — a cascade is a list, concatenation is composition and [calculus.md](../calculus.md) proves it associative, and `Derivation.steps` names every point.

**`else:` is not, and this is where the prior breaks.** Lexurgy's hierarchical block: *"The first nested block is applied; only if it fails to make any changes to the word, the second block is applied."* That is the **Elsewhere Condition**, and Lexurgy's documented use of it is stress assignment. Measured, in ipakit:

```
[vowel length=long] -> [stress=primary] / _ [-vowel] [vowel] [-vowel] #   ; penult, if heavy
[vowel] -> [stress=primary] / _ [-vowel] [vowel] [-vowel] [vowel] [-vowel] #  ; antepenult

  kamiːnus  ->  kˈamˈiːnus     two primary stresses in one word
  kamikus   ->  kˈamikus
```

Latin stress, in every phonology course, and the answer carries two primary stresses because the two rules do not bleed each other and ordering therefore says nothing.

**The honest complication is that the elsewhere relation is often flattenable, and the shipped data flattens it.** Restate the general rule with the special case excluded and it works — **but only in one of the two spellings, and the other is the spin-off finding below**:

```
antepenult, restated as "…with a light penult"

  penult written [vowel length=normal]    kamiːnus -> kamˈiːnus   kamikus -> kamikus
  penult written [vowel -long]            kamiːnus -> kamˈiːnus   kamikus -> kˈamikus
  wanted                                  kamiːnus -> kamˈiːnus   kamikus -> kˈamikus
```

`[vowel length=normal]` is the spelling a reader reaches for, and [rules.md](../rules.md) documents it as the *shortening* spelling on the right of the arrow. On the left it matches nothing, so the rule finds no site and the light-penult word comes out with no stress at all and no complaint. Per-value negation is the spelling that works. So the flattening technique is available, and the obvious way to write it is a silent wrong answer.

Flattening is also what the shipped Japanese epenthesis family does, by a different route: `o` after a coronal stop, `i` after an alveolo-palatal affricate, `u` elsewhere, and the earlier rules bleed the later one by destroying its environment. Shipped demand for `else:` is therefore **zero**, and the technique that covers it is the one [calculus.md](../calculus.md) already writes down for optional rules.

**Where flattening stops is where the exclusion is not a window of neighbors:**

```
[vowel length=long] -> [stress=primary]         ; the leftmost heavy syllable
[vowel] -> [stress=primary] / # [-vowel] _      ; else the first

  kamiːnus  ->  kˈamˈiːnus
```

"No heavy syllable anywhere in this word" is not a context question, and no restatement of the general rule reaches it — the same boundary [calculus.md](../calculus.md) already draws for splitting optional choices over ordered rules: *"'at most two schwas in the word' is not a context question at all, and no ordering states it."* Two independent limits landing on the same line is worth noting; it says the missing thing is a **non-local condition**, not a control-flow construct.

**Verdict: REFUSE `then:` (it is concatenation). REFUSE `else:` here, and record it as a real gap belonging to a different literature.** It is not a conlang capability — it is Kiparsky's Elsewhere Condition, it is taught, and adopting a control-flow keyword from a sound-change applier would be the wrong route into it. The entry [calculus.md](../calculus.md) should gain is that a rule cannot be conditioned on whether an earlier rule fired, with Latin stress as the case and the flattening technique as what is available instead.

## 7. Romanizers

**Refuse: there is nothing to build.** Lexurgy's intermediate romanizer is a rule named `romanizer-<name>`, and what it does is documented precisely: *"Intermediate romanizers don't affect the final output of the sound changes, but they add intermediate stages to the output"* — and the worked example is explicit that the derivation is untouched, *"the next rule still sees `cccc`, as if the intermediate romanizer wasn't there."*

That is a derivation carrying its intermediate forms, plus a spelling applied to one of them. ipakit has both, and every declared notation comes along:

```
ipa.ruleset("american-english").derive("pə.tˈe͜ɪ.to͜ʊ")   -- 14 steps, 2 fired

  tapping        pə.tˈe͜ɪ.ɾo͜ʊ    X-SAMPA  p@.t"e_I.4o_U
  aspiration     pə.tʰˈe͜ɪ.ɾo͜ʊ   X-SAMPA  p@.t_h"e_I.4o_U
  = result       pə.tʰˈe͜ɪ.ɾo͜ʊ   X-SAMPA  p@.t_h"e_I.4o_U
```

No new machinery, no new keyword, and it is the stronger version of the capability rather than the weaker one: Lexurgy attaches one declared rule set to one named point, where ipakit applies *any* declared notation at *every* point, because a `Step.after` is a form and a notation is a function of a form. The `<notations>` and phonemap machinery [samprosa.md](samprosa.md) assesses is what makes that true, and it is already the reason ipakit reads and writes X-SAMPA, CMU, TIMIT and Kirshenbaum.

The phonemaps come along on the same terms and with their own honesty about it — `ipa_to_phonemap(result, "cmu")` is `['P', 'AH', 'T', 'EY', 'DX', 'OW']` **and warns that it dropped `.`, `ʰ` and `ˈ`**, because CMU has nowhere to put them. That warning is the capability working: a romanizer that silently discarded the aspiration a rule had just written would be the failure this repository is about.

Lexurgy's `deromanizer` / `romanizer` pair with the `literal` modifier is a different thing again — an escape from its own declarations, needed because a romanization glyph can collide with a declared diacritic. ipakit's answer to that collision is the one it gives everywhere: the declaration wins, loudly, and the mechanism is `<notations>`. `β` is refused as an agreement variable by name and with the reason, for exactly this class of hazard.

**Verdict: REFUSE. The capability is shipped; what is missing is one paragraph in [rules.md](../rules.md) saying that a derivation's steps are forms and every notation reads one.**

## 8. Where ipakit is ahead, stated as claims

Two of these were briefed as claims to confirm. Both confirm, and one is stronger than the claim.

**Natural classes are read off the declaration, and no applier does this.** SCA² has no features at all — `V=aeiou`, and the documentation is candid that `F=khshzh` *"in fact defines the F category as k h s h z h"*, so a digraph cannot be a class member and rewrite rules are the workaround. Lexurgy's `class nasal {m, n, ŋ}` is enumerative, and its reference says so plainly: nesting classes *flattens* them, order inside a class is semantically significant because classes pair up positionally, and the same sound may be listed twice to keep two classes aligned. Brassica's categories are enumerations with set algebra over them. Phono has 21 binary SPE features, which is the closest of the four, and its natural classes are feature conjunctions written out per rule rather than named anywhere. ipakit's `[obstruent]` is `natural-class="obstruent"` on the `fricative`, `plosive` and `affricate` values of `manner`, and [rules.md](../rules.md) states the property that follows: *"a manner added to `ipa.xml` belongs to the class only if the data says so."* This is the house rule reaching a place the field has not.

**The `VariantSet` claim needs restating, because the comparison it was written against is not the one that exists.** The brief expected the contrast to be *enumeration against sampling*. **Nobody samples.** All four appliers are deterministic; Brassica's `-?`/`-??` enumerate every branch and emit them all, and `filter` exists precisely to prune the explosion afterwards. So the real claim is narrower and better:

```
5 optional insertion rules on 'pk'

  256 forms, complete=False, unexplored=17,177,628,652
  rule 5 (∅ ~> t / [-vowel] _): kept 256, 17177628652 choice combination(s) unexplored
```

Brassica enumerates and has no cap and nothing that reports one, so a rule set that multiplies its output multiplies it silently and the pruning is the author's job. ipakit's answer says in the returned object that it was cut, at which rule, and by at least how much. **The claim is not that enumerating beats sampling. It is that a truncated answer must not read like a complete one**, which is [reviewing.md](../reviewing.md)'s whole subject, and it is the one place in this comparison where ipakit has an instrument nobody else built.

**A third, unbriefed.** Lexurgy's **floating diacritic** — *"a diacritic marked with `(floating)` is interpreted as creating a superficial variant of the base sound, meaning rules that apply to the base sound should apply to the modified sound too"*, carried over automatically to the emitter — is a real and transferable idea, and ipakit already has the problem solved in a way that needs no per-diacritic flag. Prosody is a **second namespace** read off `Feature.mode`, so `a` matches `ˈa` and `t -> ʔ` does not shorten `tː`, and which features behave that way is a declaration rather than a mark-by-mark annotation. Lexurgy's version is more general (any diacritic may float) and less principled (the author decides, per glyph, and can get it wrong). Worth knowing that the two designs are answers to the same question.

## 9. What the appliers have that this document does not assess

Named so they are not mistaken for having been considered and refused.

**Lexurgy's `<syl>` and syllable-level features**, which are a genuinely different data model — a feature that belongs to a syllable rather than to a segment. ipakit's `level` ladder and its prosodic namespace overlap this and are not the same thing. It is a question about `Form`, not about the notation, and it belongs with [form.md](../form.md).

**Brassica's paradigm builder and MDF dictionary I/O**, and SCA²'s gloss separator `‣`. All three are lexicon tooling, and §12 is why they are out of scope rather than refused.

**Phono's batch validation of derived reflexes against a stored etymon/reflex vocabulary**, which is the historical workflow's own test harness and is again lexicon-shaped. The questions next to it — cognate detection, sequence alignment, sound classes for reduction, reconstruction as an inverse problem — are about the metric rather than the rules and are assessed elsewhere. This lane bumped into them at §11 and stopped.

**Lexurgy's `cleanup` and `defer` modifiers**, which are rule-set management rather than rule semantics; the first is a rule that reruns after every subsequent rule, the second a named rule invoked from elsewhere. Both are reasonable and neither has shipped demand.

**Brassica's Kleene star and wildcard in contexts** (`l*`, `^l`), and Lexurgy's repeaters (`[]*3`, `b*(2-5)`). This is the same unbounded-context question §1.2 and §10 arrive at from the other direction, and §10 argues the projection is the better answer for the process that wants it. A repetition operator is the more general answer and the more expensive one — a context item stops being one unit, so `Site.left`'s promise of *"one entry per context item"* becomes a span rather than an index. It deserves its own assessment and does not get one here.

## 10. The capability nobody asked for

Every measurement in §1 arrives at the same missing thing, and it is not iteration.

Harmony needs to reach the next **vowel**, not the next *unit*. Kaplan & Kay write that as `C*` in the context. Lexurgy writes it as a **filter** — a class or matrix placed after the rule name, after which *"the rule pretends that only sounds that match the filter exist"*, with the consequence stated exactly: *"two sounds are considered adjacent if all the sounds between them don't satisfy the filter condition."* Its harmony rule is `harmony @vowel ltr:`, and the filter is doing the long-distance half.

**ipakit has this mechanism already, hardcoded to one case.** Context scanning steps over transparent units, which is what makes the syllable dot optional notation:

```
t -> ɾ / [vowel stress=primary] _ [vowel]

  bˈʌtɚ    ->  bˈʌɾɚ
  bˈʌ.tɚ   ->  bˈʌ.ɾɚ      the dot is stepped over
```

The set stepped over is `Unit.transparent`, and a rule cannot change it. A **declared projection** is that decision handed to the rule: *this rule reads the vowels; everything else is not there.* It is the house rule applied to transparency, it is autosegmental phonology's tier written as one term, and it is the difference between one harmony rule and twelve.

It also serves the audience list without a stretch. Tier-based long-distance phonology is taught; harmony is a real process in large- and low-resource languages alike; and a projection is precisely how a speech-ML caller would ask for the vowel sequence of a form.

**This document does not recommend building it.** It recommends assessing it, because two of its questions are open and neither is small: what a projection does to `Site`'s promise that its entries align with the notation, and whether a rule that reads a projection and *writes* a segment can still promise the non-overlap `Query.sites` guarantees. Those are the same two questions the span raised in [captures.md](captures.md), arriving from a direction that has textbook demand behind it, and that is the strongest reason to look at it properly.

## 11. Relative chronology, and what this engine already is

The conlang appliers are modeled on **diachronic** sound change — that is what they are for, and Phono is a historical tool rather than a conlang one, calling its rule list the *Diachronic Order* and stating its central assumption as the regularity of historical development. So the audience behind these tools is not only conlangers, and the part of it that is historical phonology sits inside computational linguistics rather than beside it.

That matters for one verdict, in §4. It matters more for a claim this document should make in its own right, because the measurements were sitting there and nobody had asked for them.

**Relative chronology is the analytic apparatus of historical phonology, and an ordered cascade with a step-by-step trace is exactly what states it.** The four rule interactions, in the shipped notation, with the trace as the account:

```
FEEDING            at  ->  iʔ            COUNTERFEEDING     at  ->  it
  raising                                  glottalling  (no change)
      a -> i @0                                -
  = it                                     = at
  glottalling                              raising
      t -> ʔ @1                                a -> i @0
  = iʔ                                     = it

BLEEDING           an  ->  a             COUNTERBLEEDING    an  ->  ã
  final nasal loss                         nasalization
      n -> ∅ @1                                a -> ã @0
  = a                                      = ãn
  nasalization  (no change)                final nasal loss
      -                                        n -> ∅ @1
  = a                                      = ã
```

The counterbleeding case is the textbook one and the trace earns its keep on it. `ã` is an **opaque** surface form — a nasal vowel with no nasal consonant to have conditioned it — and the account of why is the middle line, `ãn`, which the answer does not contain and the trace does. That is the thing a historical phonology class spends a week on, and here it is a printed intermediate rather than a diagram on a board.

Four properties make it more than a printout, and each is already documented and tested elsewhere.

**Order is the semantics, and the algebra says so.** [calculus.md](../calculus.md) proves composition of rule sets is concatenation and associative, by sweep rather than by assertion, and that applying one set to another's output set is the same as applying the concatenation — *in order*, not merely as sets. A relative chronology is a list, splitting one into stages is concatenation, and the two ways of writing it are the same object.

**A rule that did nothing and a choice not taken are different reports.** `(no change)` and `(not taken)` are distinct in a full trace, which is what makes counterfeeding legible: the first line of the counterfeeding trace is a rule whose environment failed, and it has to be visible or the derivation looks like it had two steps and took one.

**An edit carries its index.** `a -> ã @0` says which position moved, so a rule with several sites is not reported as one event.

**A change spreading through a lexicon rather than complete is what `~>` and `VariantSet` are.** A rule marked optional answers with the set of forms the change does and does not reach, each carrying the derivation that produced it and the number of optional choices it took, and the set says whether it is complete. Lexical diffusion is a real historical phenomenon and this is the closest the engine comes to it — with the limit §5 states, that the branching is per *site* rather than per *word*.

**Where this stops, and it is worth saying because it is the next thing anyone would ask for.** Reconstruction is the inverse problem — given the reflexes, find the rules — and nothing here inverts. [calculus.md](../calculus.md) already says so: a rule set *"cannot be inverted, intersected with another rule set, or complemented"*. Cognate detection, alignment and sound classes are the metric's questions rather than the rules', and they are assessed elsewhere; this lane bumped into them and stopped.

## 12. The audience

**One audience for the notation, and the line inside the tool is a lexicon rather than a user.**

Historical linguistics is core demand, not a stretch, and §11 is the reason: the engine already does the thing that field teaches. Conlanging is the stretch, and the useful test on it turned out not to be *who asks* but *what is asked*.

Sort every capability in this document by whether it is a claim about a **form** or a claim about a **wordlist**, and it sorts cleanly.

Everything that failed the demand test is a claim about a wordlist. Per-rule sporadicity is lexical diffusion — which *words* underwent a change (§5). Romanizers and intermediate stages are a way to see a lexicon at each historical layer (§7). Rule blocks organize a long chronological sequence of them (§6). Brassica's paradigm builder and MDF dictionary export, SCA²'s gloss separator, Phono's etymon/reflex batch validation are all a wordlist moving through time.

Everything that passed, or came close, is a claim about a form, and every one of them is a process a phonology course teaches. Harmony. Syllabification. Stress assignment. Metathesis. A term meaning *any segment*.

**So the line is a lexicon, and ipakit does not have one.** `rewrite`, `derive` and `variants` take a form and answer about a form; the CLI is *"a filter, not a batch engine"*. Every capability on the wordlist side needs a list with etymologies attached, and adding one is a second product rather than a feature. That is a design boundary and not a gap, and stating it is most of what this section is for.

It also answers whether conlangers are a second audience. **Somebody working out the allophony of an invented language is doing what the American English set does**, with the same notation and no extension at all. Somebody deriving a daughter language from a proto-language over two thousand years wants a wordlist walked through a chronology, and there are four good tools for that.

**Where the line goes, if anything ever crosses it.** Nothing in this document should. If something does, it belongs beside the lexicon and not inside the notation — a separate module with its own entry point, the shape [supplement-bridges.md](supplement-bridges.md) reached for the perturbation file: *"a separate root element with its own constructor argument"*, on the grounds that a mechanism whose properties differ from a supplement's should not be called by a supplement's name. The rule notation's documented properties are that it is a function from a form to a finite set of forms, that composition is concatenation, and that a cascade terminates by construction. A capability that breaks any of those must not be reachable from `ipa.rule(...)`, whoever it serves. `propagate` breaks the third, which is why §1 refuses it on grounds independent of any demand count — **and a fixpoint would also erase the one thing §11 says this engine is good at**, since a form iterated to convergence no longer says which pass changed it, and relative chronology is exactly that question.

## 13. What follows

Six things, in order. None was applied in this lane.

### (a) The wildcard, with the zero question, and not before it

§3 and [captures.md](captures.md)'s spin-off finding are one change, because they are one mechanism: a query that excludes a value is satisfied by a unit that could not have declared it. `[]` matching any segment is two rules becoming one and a refusal message becoming a definition; `[]` matching a zero, or not, is decided by what `[-vowel]` does at a zero, and that is a defect with a repair already proposed. Settle that first, then `[]` inherits the answer instead of choosing one — and the fifteen accidental wildcards become something a reader of a rule file can be warned about rather than a spelling somebody has to discover.

### (b) Ship a syllabifier as data, and say what it is for

§2.2. `ipakit/data/rules/` holds five sets and none writes a margin, so the fact that `∅ -> . / [vowel] _ [-vowel] [vowel]` works is undiscoverable. A shipped `syllabify.rules` with one rule per onset size, and a sentence in [rules.md](../rules.md)'s underspecification section pointing at it, turns [braces.md](braces.md) §2's twelve rules from *waiting on structure nobody can supply* into *waiting on a rule set the caller may compose in*. It also gives the speech-ML and articulatory audiences the syllabic units they work in, which no query term would have.

### (c) Correct three closure-list entries

**Superseded in part by [#121](https://github.com/lenzo-ka/ipakit/issues/121): the first paragraph is carried out and [calculus.md](../calculus.md)'s entry now prices the cascade. The other two stand, and so does the same claim where [rules.md](../rules.md) and [captures.md](captures.md) §13 make it unquoted, which is where nothing checks it.**

*Iterative within-rule spreading* said an ordered cascade of repeated rules says the same thing and terminates by construction. It terminates, and it does not say the same thing: the cascade needs `(k−1) × (m+1)` rules and is bounded by the longest word anticipated. The entry should say what the two multiplicands are, and that the second is the missing one.

*Metathesis* should ask for what §4 found the field converged on — a bounded target span and a reversal — rather than for a permutation over numbered terms.

And a fourth entry is missing: **a rule cannot be conditioned on whether an earlier rule fired**, §6, with Latin stress as the case.

### (d) Say which argument the metathesis refusal rests on

§4. [captures.md](captures.md) refuses the span on two grounds and only one of them holds: no shipped set wants it *and* it breaks `Query.sites`. The first is not a refusal by this document's own test, because a process every historical phonology course teaches passes the second half of the demand measurement without any shipped rule. Adding a sentence to that document costs nothing and stops the refusal being re-opened by somebody who has noticed the same thing.

### (e) Assess the declared projection

§10, on its own, with the two open questions named there. This is the highest-value thing the conlang side surfaced and it is the one the brief did not ask about.

### (f) Nothing else

Propagation, per-rule optionality, probability weighting, rule blocks, romanizers, onset and coda terms, and the metathesis span are all refusals, and each of them is refused with a measurement rather than a preference.

The one addition that is not a refusal and not a build is §11: **write the rule interactions down**. Feeding, bleeding, counterfeeding and counterbleeding are four rule sets of two lines each, they all work today, and the trace is the explanation. [rules.md](../rules.md) has one pair already — `fed` and `starved`, under the sentence that names feeding and bleeding as where ordering lives — and it is the transparent pair. The **counterbleeding** case is the one worth adding beside it, because its answer is a nasal vowel with no nasal in it and the trace is the only place the reason appears.

## Spin-off finding: `length=normal` matches nothing and `[-normal]` matches everything

Turned up by §6 and §3, and unrelated to conlanging. It is one feature and two silent wrong answers with opposite signs.

`length` is the one prosodic feature declaring a default value that no mark spells — `default="normal"`, and `declaring_mark("length", "normal")` is `None`, because a bare vowel already says it. [rules.md](../rules.md) documents `[vowel] -> [length=normal]` as the *shortening* spelling, and it works. The same term on the **left** of the arrow can never match anything:

```
as a change:                     rewrite("kaː", "[vowel] -> [length=normal]")     'ka'
as a query, on a short vowel:    rewrite("ka",  "[vowel length=normal] -> e")     'ka'
as a query, on a long vowel:     rewrite("kaː", "[vowel length=normal] -> e")     'kaː'
control, the spelled value:      rewrite("kaː", "[vowel length=long] -> e")       'ke'

rule("[vowel length=normal] -> e").recognize("ka")    []
rule("[vowel length=normal] -> e").recognize("kaː")   []
```

It parses, it finds no site, and it says nothing — a rule its author believes is firing, doing nothing and reporting nothing. That is the shape [reviewing.md](../reviewing.md) exists to catch, and it is the near neighbor of a defect [rules.md](../rules.md) already records: `[manner=obstruent]` *"used to build a constraint no phone can satisfy and match nothing, silently"*, and the repair was a message naming the spelling that works.

**The other sign is the same cause.** Because no unit ever carries `length=normal`, its *negation* is satisfied by every unit — so `[-normal]` is a wildcard, and §3 measures it collapsing a shipped rule family with no corpus word moving:

```
[-normal] -> e     on 'ka'    'ee'      on 'kˈa'   'eˈe'
                   on 'kaː'   'ee'      on 'a#b'   'e#e'   -- the margin is not a segment
```

One feature, two answers nobody asked for: the query that can never hold, and the query that always does.

`length` is the only feature in the first position — every other prosodic feature either declares no default or declares one a mark spells — so that half of the fix is narrow. It is a query on a declared value of a declared feature, so it cannot be refused at parse the way an undeclared value is; what it needs is for a unit carrying no `length` to read as `length=normal`, which is what the declaration says it is. Making that true closes the second half too, since `[-normal]` would then hold of nothing rather than of everything.

Fourteen other terms remain universal for a different reason — they name a value of a feature a *segment* never declares — and §3 is what those are for. Reported here, not repaired: this lane is read-only.

## Reproducing the measurements

Every number was taken with `PYTHONHASHSEED=0` against this worktree, reading the library only. Nothing was written into the tree.

**The corpus is `tests/test_rule_sets.py`'s `CORPUS`, imported rather than retyped**, for the reason the other documents in this directory give; the unit corpus in §3 is `scripts/sweep.py`'s, taken through `sweep.corpus` and `sweep.check_corpus` rather than through a hand-rolled enumeration.

**The self-feeding measurement** wraps each shipped `Rule` in a one-rule `RuleSet` and compares `apply(apply(w))` with `apply(w)`, with `keep_zeros=True` so a rule that writes a zero is measured on what it wrote. It is run twice: once with each rule fed the form the cascade had actually reached at that point, and once cross-set, with every rule against every corpus word of every set. The second is the 12,642 and is the one quoted, because it is the wider question — whether any shipped rule *can* self-feed rather than whether it does on its own data.

**The cascade fixpoint** iterates `RuleSet.apply` to a fixed point with a cap of 40 passes, and reports both the pass count and the divergence count so a set that failed to settle would be visible rather than silently excluded. None did; the worst is two passes.

**The harmony counts** generate every word of *k* vowels with clusters of 0..*m* consonants between them, in product order, and search for the smallest *n* such that *n* copies of the (*m*+1)-rule family harmonize every one. The rules are generated rather than typed, so the count is a measurement and not something done by hand.

**The syllabifier in §2.3 is written for the measurement and is not a claim about English syllabification.** It is maximal onset over the units the engine reads, splitting a two-or-more consonant cluster after its first member, and it is applied to the corpus words before the rule set. What it is used for is a comparison against the same rule set on the same words undotted, so a crude syllabification is enough to answer *whether the missing dots were the whole problem* — and the answer is that they were two-sixths of it. Every rule-set figure rebuilds the shipped set from its own source and asserts that a rebuild with no changes is identical to `rules.shipped(name)` on every corpus word, for `apply` and, where a set has an optional rule, for `variants`.

**The wildcard universality check** generates every term the bracket language can build from the declaration — `[key]`, `[key=value]`, `[value]` and `[-value]` for every declared feature and value, 334 candidates of which 296 parse — puts each through `rules._pattern`, and tests it against every unit of the sweep corpus through `Pattern.matches`, so the answer is the engine's own predicate rather than a separate implementation of it. The seventeen survivors are then re-tested against six prosodically marked units the corpus does not hold, which is what separates the two corpus artifacts from the fifteen, and each survivor is substituted into the French family and measured against `rules.shipped("french-liaison")` on all 29 corpus words for both `apply` and `variants`.

**The cap figures** use the shipped `DEFAULT_LIMIT`, and every row reports `complete`. Raising the limit on the five-rule insertion cascade is what the limit exists to avoid and was not attempted.

**The rule-interaction traces in §11** are `Derivation.trace(all_steps=True)` on four two-rule sets built through `ipa.ruleset`, printed as the engine prints them and laid out in two columns here. The site-multiplicity count in §5 walks each shipped set rule by rule, calling `Rule.recognize` on the form the cascade has actually reached at that point rather than on the input, since a rule's site count is a fact about what the rules before it left behind.

**Lexurgy page anchors** are the MDX headings of the published reference and are stable; where a claim comes from the tutorial rather than the reference it is attributed to the tutorial. The one claim taken from Lexurgy's source rather than its documentation — that `propagate` detects cycles rather than bounding iterations — is labeled as such where it is made, and is the only one.
