# Tiers: assessment

Should the calculus support structures that ride the linearization without nesting — syllables, morae, morphs above the segment ([#137](https://github.com/lenzo-ka/ipakit/issues/137)); a gestural or phase timeline below it ([#136](https://github.com/lenzo-ka/ipakit/issues/136)) — and if so, which architecture, and what does it cost?

They are one question. #136 is a tier below the segment and #137 is tiers above it, over the same shared linearization, and an assessment that split them would produce two answers to one problem.

**Verdict: BUILD IT, as intervals a rule may read and may not rewrite.** An `Interval` carrying a declared tier name and a span over `Form.units`, a rule pattern that can name one in its context, and rebasing at `_apply_edits` from what `Edit` already holds. Tier names declared in `ipa.xml` as a nominal feature — the shape [morph-boundary.md](morph-boundary.md) already chose for `+` — never as rungs on the ordinal `level` ladder.

**The read-only restriction is the finding, not caution.** Multiple tiers over one spine are regular *as descriptions*: Bird & Ellison generalize their encoding to "an arbitrary number of charts" using ordered n+1-tuples (1994: 71) and combine the tiers by intersection, "remaining within the confines of regular grammar" (55). What leaves the regular tradition is rewriting a tier. The multi-tape treatments — Kay 1987, Kornai 1991, Wiebe 1992 — "go beyond regular grammar power" (57), and the reason is stated exactly: Wiebe's devices recognize "some (strictly) context-sensitive languages," power he argues "is crucially required for processing autosegmental analyses with feature- or structure-modifying rules" (85). So the line between free and expensive falls precisely where a rule stops reading a tier and starts writing one.

That line is one the calculus already draws. [calculus.md](../calculus.md) records that the restriction buying regularity is on the **center** of a rule and not on its contexts (Kaplan & Kay 1994: 346). A tier term in a context is a context term; a tier term in the center is a rewrite. Read-only tiers do not move the calculus at all.

**And therefore tiers cost nothing in intermediates and nothing in the derivation trace.** The star topology and the cascade are orthogonal. A tier is part of what one representation *contains*; the cascade is how successive representations are *related*. Bird & Ellison's own statement of what is not regular in their model — "the relationship between different formats of the same description" (88) — is a relation a cascade over one format never asks for. The `Edit` per change survives, and with it the step-by-step trace that makes this library usable in a classroom and in a g2p debugger.

**The deciding cost is not the one #136 predicted.** Fujimura's C/D model does not need a syllable-level object added beside the segment; it has no segment. The owner's own reconstruction makes `Syll` "the concatenative unit; atom of phonological representation," with features attached to positions in `{p-fix, onset, nucleus, coda, s-fix}`, and treats `/sp/` as one margin bearing manner `{spirantized}` whose place belongs to the following stop. C/D is not a tier over this spine. It is a different spine, and adopting it means giving up the object that `Form`, every rule and the metric are made of. Articulatory Phonology composes upward from something segment-shaped and can be a tier here; C/D can be a later *reading*, and the position vocabulary [#131](https://github.com/lenzo-ka/ipakit/issues/131) reserved is what an interval tier would name.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Does the star topology unwind into finite-state machinery? | **Yes as descriptions, no as relations, and the boundary is structure-modification.** Tiers read: regular. Tiers written: beyond regular, and the sources say so in those words. |
| Is anything relying on the level ladder meaning nesting? | **One function.** `Form.tree()` uses the ladder as recursion depth. Every other consumer is a scalar `>=` or plain string equality. |
| How much of the ladder is exercised? | **Half.** 4 levels declared; `phrase` and `utterance` are named by **0 of 86** shipped rules. The ladder's whole live weight is that `.` also matches `#` and the form edge, used by **2** rules. |
| What does the metric pay? | **Nothing.** `level` is `mode="structural"`, so it is in no phone bundle, and `metric.py`, `distance.py` and `distance_model.py` contain zero references to it. |
| What must be rebased, and how often? | Interval endpoints, on **21 of 86** shipped rules — the ones that change the length of the unit sequence. `Edit` already carries `start`, `end` and `replacement`, so the arithmetic needs no new information from any rule. |
| What can be stated today only by workaround? | Moraic weight. `japanese-moraic.rules` names the mora **20 times in its prose and 0 times in its rules**; all 35 rules are segmental. |
| What cannot be stated at all? | **Tone stability and compensatory lengthening** — the two founding arguments for autosegmental representation. Measured below; both fail silently. |
| Can a language's tiers be declared in `ipakit/data/rules/`? | **No, and this contradicts the brief.** A `.rules` file is rewrite rules only: no declaration form, no metadata, no schema. Supplements may add symbols and are explicitly refused declarations. A tier requires `ipa.xml`. |
| Is C/D a tier architecture for this codebase? | **No.** C/D has no segment; `Syll` is the atom. It is a replacement spine, not an addition to one. |

## Sources

- Bird & Ellison, "One-Level Phonology: Autosegmental Representations and Rules as Finite Automata", *Computational Linguistics* 20(1), 1994, pp. 55–90: <https://aclanthology.org/J94-1004/>. Read in full. Pages relied on: 55 (the abstract's regularity claim), 57 (Kay, Kornai and Wiebe go beyond regular power), 71–73 (generalizing to n charts; the encoding is linear or compositional and not both), 85 (Wiebe's multi-tape devices and what the extra power is for), 87–88 (intersection is not a transducer operation; what is and is not regular in a one-level model).
- Kaplan & Kay, "Regular Models of Phonological Rule Systems", *Computational Linguistics* 20(3), 1994, pp. 331–378: <https://aclanthology.org/J94-3001/>. Pages relied on here: 332 (Johnson's result, taken at one remove), 340 (the paper frames itself in binary relations and two-tape transducers, and offers n-ary only as a hope), 342 (regular relations are closed under neither intersection nor complementation), 346 (the restriction is on the center of a rule, not its contexts), 347 (the three application strategies, the third being simultaneous), 367 (the equivalence theorem, and that empirical coverage cannot choose between the two branches). The fuller reading is in [calculus.md](../calculus.md), which cites the same copy.
- Mohri & Sproat, "An Efficient Compiler for Weighted Rewrite Rules", ACL 1996, pp. 231–238: <https://aclanthology.org/P96-1031/>. Cited for the unwinding technique. Theorem 1 (236) states the discipline exactly — a rule "that does not rewrite its noncontextual part can be represented by a weighted finite-state transducer" — and 232 notes the construction "extend[s] straightforwardly to other modes of application (optional, right-to-left, simultaneous, batch)", the simultaneous mode being the one this engine matches. Obligatoriness and direction are parameters of the construction, not conditions on it.
- Kay, "Nonconcatenative Finite-State Morphology", EACL 1987, pp. 2–10: <https://aclanthology.org/E87-1002/>. The multi-tape transducer treatment of autosegmental structure. Cited at one remove through Bird & Ellison for the power claim.
- Fujimura, "C/D model: a computational model of phonetic implementation", in Ristad (ed.), *Language Computations*, DIMACS Series in Discrete Mathematics and Theoretical Computer Science 17, American Mathematical Society, 1994. The C/D reconstruction relied on in §5 is the owner's own working corpus, which carries provenance tags separating what is published from what is oral and unpublished; those tags are respected in what is attributed here, and DIMACS is reached through them rather than read for this assessment. It contains no finite-state or regularity claim and is not cited for one.

**Not held**, and every claim attributed to them here is at one remove, labeled: Johnson, *Formal Aspects of Phonological Description*, Mouton 1972 — reached through Kaplan & Kay 332, and the library's index records the acquisition attempt and its outcome. Kornai, *Formal Phonology*, doctoral dissertation, Stanford 1991, and Wiebe, *Modelling Autosegmental Phonology with Multi-Tape Finite State Transducers*, MSc thesis, Simon Fraser 1992 — reached through Bird & Ellison §5. Goldsmith's autosegmental phonology (1976; 1990) — the Mende tone argument that motivates the line is restated at Bird & Ellison 57, and that restatement is what is used.

Also read, and it bears on the verdict at one point: Lenzo, "s/($text)/speech $1/eg; (Speech synthesis in Perl)", *The Perl Journal* 3(4), Winter 1998. A TTS front end written as a cascade of ordered substitutions is an ordered rewrite system, which is the practitioner's form of the branch this verdict keeps — and the reason keeping it matters more than the formal argument does.

**A citation-hygiene note, because two claims are easy to merge and they are different.** "Mildly context-sensitive" in Joshi's sense — TAG, CCG, LIG, head grammars — is a specific class, and **no source read here makes that claim about autosegmental phonology, or about phonology at all.** What Bird & Ellison report of Wiebe is "(strictly) context-sensitive" (85), which is a different and stronger statement, and the two point in opposite directions on the hierarchy: mild context-sensitivity is properly above context-free, and the rewriting result is at or below regular. Separately, the non-recursive-rewriting result — that SPE-style rules denote regular relations when a rule may not rewrite its own output — is Johnson's, re-proved by Kaplan & Kay, and is about rewriting rather than about tiers. This document relies on that one.

**And one attribution that must not be made.** Kaplan & Kay prove nothing about multi-tier regularity, and say so: they frame the discussion "in terms of binary relations and two-tape transducers," note that "the obvious extensions of these properties do hold for the general case," and offer the autosegmental application only as something that "may be useful in developing a formal understanding of autosegmental phonological and morphological theories" (340), pointing at Kay 1987. That is a hope, not a theorem. The multi-tier result used here is Bird & Ellison's and is about acceptors.

## 1. What is already settled, and what the work therefore is

Three documents had reached the answer before the issues were filed, and the cost of the assessment is what changes because of that.

**The repository already chose the topology.** [form.md](../form.md) states the shape: "multi-tier intervals over a shared segmental spine, where a syllable interval and a word interval may overlap without either containing the other". That is the star — one shared spine with tiers associated to it — and not a chain of composed relations. So no topology decision is open, and the enchaînement case is already worked there in full: *petite amie* has a syllable `ta` that needs a `t` from one word and an `a` from the next, and `tree()` cuts it in two because `word` outranks `syllable` on the ladder.

**The owner's own C/D notes reject the hierarchical reading of "suprasegmental" independently**, and on a linguistic argument rather than a computational one: "supra-" in Firth's original sense means *spanning* domains, not a superordinate layer, and the hierarchical reading is a later accretion. The same notes observe that a melodic tier plus cross-tier anchoring — accent to a strong syllable, boundary tone to an edge — already yields a ladder graph with cycles, so the simplest honest two-tier model is not a tree. That is #137's thesis arrived at from the phonetics side, and it is stronger than the version in the issue, which argues from cases the ladder cannot state rather than from what the ladder is.

**[morph-boundary.md](morph-boundary.md) already built the pattern a tier should follow**: a separator declaring a nominal feature and no `level`, so `_reaches` never ranks it, and transparent so context scanning steps over it unless a rule names it. Its measurement is the relevant precedent — `+` opaque changes the derivation at 122 of 486 seam positions, `+` transparent at 0 — and its verdict is that a nominal tier costs the metric nothing. **Note that none of it is implemented.** There is no `+` in `ipa.xml` and no occurrence of `morph` anywhere in `ipakit/*.py`. The assessment stands; the data does not exist yet, and a later lane should not read it as shipped.

So the work here is costing a decision, not discovering it, and three of the four hard parts were already done. What remained was whether the star is affordable, whether the ladder is load-bearing, and what the smallest real version is.

## 2. Does the star unwind?

The technique is the one in the Johnson–Kaplan–Kay–Mohri line: a notation that looks more powerful than finite-state often compiles into it once the application discipline is fixed, and the apparent power of a notation is not its actual power under a stated discipline. Applied to tiers, the question is whether an n-tier star with bounded association unwinds the way an ordered cascade does.

**It does, and the construction is explicit — but it buys regularity by giving up levels.** Bird & Ellison encode each tier as an automaton over a tape, encode association lines as counts acting as synchronization marks, and combine tiers by **intersection**. That works because regular *languages* are closed under intersection. The generalization to a star of any width is theirs and is stated as routine — "for n charts we must employ ordered n+1-tuples" (71) — and the encoding "can be used directly as a finite-state recognizer of surface forms, simply by forming the intersection of the n tier encodings and projecting the first elements of the tuples" (72–73). Their conclusion is that "the declarative approach to phonology presents an attractive way of extending finite-state techniques to autosegmental phonology while remaining within the confines of regular grammar" (55).

There is a second price, on the same page, and it is worth carrying because it constrains any future compilation rather than the design below: "the encoding is either linear or compositional, but not both. Unfortunately, this is the best that we can hope for; Wiebe (1992) has shown that a compositional linear encoding does not exist" (73).

The price is stated in the same paper, at the end, and it is exact:

> The operation we have applied here--intersection---cannot be performed by a regular transducer. This does not invalidate our claim to regularity. What is regular in our theory is each individual description and generalization about phonological data. … What is not regular in one-level phonology is the relationship between different formats of the same description. There is no finite-state transducer that will form the product of two regular expressions. Multilevel analyses necessarily seek to capture relationships between different descriptions, and like the product operation, these relationships often cannot be captured by finite-state transducers. (88)

That is the same non-closure Kaplan & Kay state at 342 and [calculus.md](../calculus.md) already cites, arriving from the other direction. Bird & Ellison's model is monostratal by construction — no rule ordering, no intermediate representations — which is Koskenniemi's branch of the equivalence at 367, and the branch this library deliberately did not take.

**So the naive reading is that tiers cost the trace, and it is wrong.** It would be right if the tiers had to be *combined* by the machinery that also relates levels. They do not. In a star, tiers belong to one representation; the cascade relates successive whole representations, and it relates them through the segmental center. Nothing asks for the product of two regular expressions, because there is only ever one format in play. That is why the star and the cascade are orthogonal, and the orthogonality is not a hope — it follows from what Bird & Ellison name as the non-regular part.

**The boundary is structure modification, and the sources name it.** The multi-tape transducer treatments — Kay 1987, Kornai 1991, Wiebe 1992 — "go beyond regular grammar power and to our knowledge have never been implemented" (57). What the extra power is for is stated at 85: Wiebe's multi-tape devices "are more powerful than FSTs without epsilon transitions, claiming that they can recognize some (strictly) context-sensitive languages," and he "argues that this extra computational power is crucially required for processing autosegmental analyses with **feature- or structure-modifying rules**." The quoted passage that follows makes the mechanism plain — the read heads "scan n-tuples separated by arbitrary distances," because "association lines can associate segments in any part of one tier to segments in any part of the facing tier."

Unbounded association across tiers is what costs. Reading an interval that is already there does not.

**And this lands exactly where the calculus already stands.** [calculus.md](../calculus.md) records the restriction that buys regularity as being on the center of a rule and not its contexts, and records the engine's application strategy as Kaplan & Kay's third, the simultaneous one — which Mohri & Sproat's construction covers along with the others (232), under the condition their Theorem 1 states: that a rule not rewrite its noncontextual part (236). A tier named in a context is a context item and falls under the unrestricted half. A rule that rewrites a tier is a center, and would need the same no-self-feeding discipline the segmental center already has, plus, for cross-tier association, the machinery Wiebe needed. **No inconsistency was found between this conclusion and what `calculus.md` claims about the engine.**

One imprecision in that document did surface while checking, and it is small and not about tiers. "The simultaneous strategy" does not name a single construction: Kaplan & Kay give more than one formulation of obligatory simultaneous application, "depending on how competition between overlapping application sites is to be resolved," and the cascade they then give models the case where "the longest substring matching φ is preferred over shorter overlapping matches" (358). Naming the third strategy therefore under-determines the engine by one choice, and `calculus.md` should say which overlap resolution it means. Recorded here rather than fixed, because that document is not this lane's.

## 3. Is the ladder relied on as nesting?

**Almost not at all.** `_reaches` is `order.index(level) >= order.index(wanted)` — a scalar threshold, with exactly two call sites, both in `rules.py`: `Pattern.matches`, and the virtual form edge in `Query._side`. Its own docstring says the tiers nest, but the body consults no structure.

Every other consumer of `level` uses **equality of the declared string**, not ordering. `Unit.transparent` is `self.level == "syllable"`. `features.syllable_break` compares to `"syllable"`. The `empty_constituent` validator compares levels for equality and says in a comment that it never ranks them. Pattern compilation reads a separator's declared level as an opaque tag. The CLI prints it.

**One function treats the ladder as nesting: `Form.tree()`.** It walks `tiers(features)` outermost-first and uses ladder position as recursion depth; the split test itself is equality, and containment is produced by the recursion order alone. `tiers()` exists only to feed it. That is the whole migration surface for #137, and it is one function.

Reproduce the sweep:

```
grep -rn '_reaches\|tiers(\|edge_tier(\|== "syllable"' --include="*.py" ipakit/
```

**The ladder is also half-dead in the shipped data.** Four levels are declared; `phrase` and `utterance` are named by no shipped rule and no shipped test transcription. Across the five rule sets, 28 of 86 rules name a boundary: 23 at `word`, 2 at `syllable`, 4 by exact glyph (`‿`), and 0 use `%`. The ladder's entire live function is that a rule written with `.` also fires at `#` and at the form edge, and two rules use it — American English aspiration and German final devoicing.

```
python3 - <<'PY'
from ipakit import _get_ipa
from ipakit.rules import shipped, available
F = _get_ipa()
from collections import Counter
lvl, mark, tot, withb = Counter(), Counter(), 0, 0
for name in available():
    for r in shipped(name, F).rules:
        tot += 1
        pats = [p for p in (r.query.target,) + r.query.left + r.query.right if p is not None]
        b = [p for p in pats if p.names_boundary]
        if b:
            withb += 1
        for p in b:
            if p.boundary is not None:
                lvl[p.boundary] += 1
            if p.mark is not None:
                mark[p.mark] += 1
print(tot, withb, dict(lvl), dict(mark))
PY
```

**Two hardcoded literals contradict "the ladder is data."** `Unit.transparent` reads `level == "syllable"`, so a level-less mark is opaque — which is the transparency defect `morph-boundary.md` measured at 122 of 486 seam positions. And `Form.boundaries` synthesizes `level=unit.level or "word"`, which would report a word boundary inside *cats*. `tests/test_form.py` pins that declaring a *further top* rung needs no code change; it does not cover a rung below `syllable`, nor a mark with no level, and those are exactly the two shapes a tier introduces.

**Consequence for the verdict.** Tiers are additive, not a migration. Nothing has to be taken apart. `tree()` keeps the ladder and stops being the only structure a form has.

## 4. What a syllable-level object costs

### What cannot be stated at all

These are the measurements that decide the capability question, because they are neither workarounds nor gaps in coverage. They are the two founding arguments for autosegmental representation, and both fail silently.

**Tone stability.** Goldsmith's argument is that a tone is an autosegment: delete the vowel bearing it and the tone survives and relinks. Here it dies with the segment, because `Attribute.at` indexes the segment the tone rides on.

```
python3 -c "
import ipakit as ipa
from ipakit.form import Form
print(ipa.rewrite('páta', 'a -> ∅ / p _'))
print([(a.feature, a.value, a.at) for a in Form.parse('páta').attributes])
"
# pta
# [('tone', 'high', 1)]
```

The high tone is simply gone. There is no rule that rescues it, and no rule that can, because there is nothing for it to be on.

**Compensatory lengthening.** A coda consonant's mora survives its segment and lengthens the nucleus. `kans` → `kaːs` is the target; the engine gives `kas`, and the weight is lost with the segment:

```
python3 -c "import ipakit as ipa; print(ipa.rewrite('kans', 'n -> ∅ / _ s'))"
# kas
```

**Syllable-internal positions cannot be named.** A context item is one unit, so `coda`, `nucleus` and `heavy` parse as sequences of segments and the rule is refused — loudly, which is the good half.

### What is stated today only by workaround

`japanese-moraic.rules` is the case. Its header argues in morae throughout — a coda `/n/` is its own mora and takes no epenthetic vowel, a geminate's first half is its own mora, a long vowel is two morae, `CʲV` is one licit mora — and all 35 of its rules are segmental. The mora is the analysis and it is written entirely in prose. That is not a defect in the rule set; it is the shape of the gap.

### What it costs to add

**`Form` stops being one sequence with readings, and that is the real cost.** Today `Form` has exactly one field, `units`, and `segments`, `phones`, `attributes`, `boundaries` and `tree()` are all projections of it — which is what makes [form.md](../form.md)'s discipline work, because a projection can say what it drops. A tier is the first thing on a `Form` that is not derivable from the unit sequence. `Form.rebuild` currently inverts two projections; it would need a third, and the round-trip invariant would have to be restated to say what it now covers.

**Rebasing is one loop beside one function, and it is exercised on day one.** `_apply_edits` is six lines and splices rightmost-first so indices hold. An interval endpoint shifts by `len(edit.replacement) - (edit.end - edit.start)` when it sits at or after the edit, and an interval strictly containing the span keeps its start and moves its end. `Edit` already carries all three numbers, so no rule has to report anything new. It cannot be deferred: **21 of 86 shipped rules change the length of the unit sequence** — 12 in French liaison, 7 in Japanese, 2 in Spanish-accented English.

```
python3 - <<'PY'
from ipakit import _get_ipa
from ipakit.rules import shipped, available
F = _get_ipa()
n = sum(
    1
    for name in available()
    for r in shipped(name, F).rules
    if (0 if r.query.target is None or getattr(r.query.target, "is_zero", False) else 1)
    != (len(r.becomes) if isinstance(r.becomes, (tuple, list)) else (0 if r.becomes is None else 1))
)
print(n)
PY
```

**What stays untouched.** The metric, entirely. `level` is `mode="structural"` and so appears in no phone bundle, and `metric.py`, `distance.py` and `distance_model.py` contain zero references to it. A tier declared the same way inherits that by construction, which is `morph-boundary.md`'s measurement — 0 of 8,616 bundles, 0 of 9,591 distances — arriving for the same structural reason. The tract model, the renderer, the supplements, the phone maps and X-SAMPA are all untouched: none of them reads a boundary level today.

**What becomes two reads instead of one.** `Form.rebuild`, which gains a tier argument. `Pattern`, which gains a tier term beside `boundary` and `mark`. And `Form.tree()`, which does not have to change but stops being the answer to "what structure does this form have" and becomes one answer among several — the nested reading, which [form.md](../form.md) already documents as the read that cannot state enchaînement.

## 5. Which architecture

**Articulatory Phonology, for the tier below the segment. Not C/D, and the reason is the one #136 asked to be measured.**

The issue frames the asymmetry as: AP composes upward from something segment-shaped, while C/D "would require a syllable-level object that does not currently exist." Measured against the owner's own reconstruction, that understates it. In C/D the syllable is not a level above the segment — it is the atom. `Syll` is "the concatenative unit; atom of phonological representation," features are privative and attach to positions in `{p-fix, onset, nucleus, coda, s-fix}`, and `/sp/` is a single margin bearing manner `{spirantized}` whose place feature belongs phonemically to the following stop. There is no segment anywhere in the representation.

So C/D is not a candidate for "a tier over the shared segmental spine." It is a candidate for **a different spine**, and adopting it would mean giving up the object that `Form.units`, every rule's target, and every term in the metric are made of. That is not a cost that can be paid incrementally, and it is a much larger claim than #136 supposed.

**AP is a tier and can be added as one.** A gesture has temporal extent and is coordinated to others by phasing, and [gestural-model.md](../gestural-model.md) has already staged the segment-side half of it — articulator declared per place value, with step 1 a strict subset of what step 2 needs. A gestural score is intervals over the same linearization, below the segment, which is exactly the shape #137 wants above it. One interval type serves both, which is the argument for answering the two issues together.

**C/D survives as a reading, and the vocabulary is already reserved.** If tiers carry declared names and an interval can name a position within one, then `onset`, `nucleus`, `coda` and Fujimura's affix positions are available later without a change to the machinery — which is what [#131](https://github.com/lenzo-ka/ipakit/issues/131)'s rename of `onset` to `approach` was protecting. Nothing in the minimum below forecloses C/D; it just does not adopt it.

**Keep the two kinds of point apart, as #136 asked.** *On this codebase*, AP wins because it adds to a spine that exists and C/D replaces it. *As phonology*, the C/D case is untouched by that and is argued in the owner's corpus on its own terms — the syllable pulse as the single time reference, magnitude modulating temporal spread rather than only amplitude, quasi-ballistic gestures returning to a base position. Those are claims about speech. The measurement here is a claim about a Python library, and it decides only the second question.

## 6. The smallest thing that is real

Four pieces. Each is small, each is checkable, and a richer model extends them rather than replacing them.

**(a) A tier is a declared nominal feature, not a rung.** In `ipa.xml`, beside the ordinal `level` and following the shape `morph-boundary.md` chose for `morph`: `mode="structural"`, values nominal, and the declaration should say the values are nominal, because `level` three lines away is read ordinally in two places and nothing should ever read a tier that way. This is what keeps the metric at zero and keeps `_reaches` from ranking a tier against `word`.

**(b) An `Interval` on the `Form`.** `(tier, start, end)` over `Form.units`, half-open, the same convention `Site` already uses. `Form` gains a second field; `Form.rebuild` gains a third argument; `Form.to_ipa()` is unchanged, because an interval is not spelled. Whether intervals are also *derivable* from separators — so that `.` continues to imply syllable intervals and nothing needs re-transcribing — is the compatibility question, and the answer form.md already gives applies: an unspecified tier is not invented, so a form with no dots has no syllable intervals rather than one.

**(c) A rule may name a tier interval in its context, and may not rewrite one.** This is the restriction §2 argues for, and it is the whole of the formal claim. Notation is open and is the one genuinely undecided piece; whatever it is, it must not collide with the bracketed feature-query language or with a declared glyph, and the parser's existing behavior of refusing an unknown bare word loudly is the right default to keep.

**(d) Rebasing at `_apply_edits`.** One loop, from data `Edit` already carries. Endpoint arithmetic only.

**What is deliberately not in the minimum.** Association — whether a tone stranded by a deletion floats, relinks left, or relinks right — is not endpoint arithmetic and is not derivable from an `Edit`. It is a phonological policy and it is language-particular, which makes it the fourth instance of the pattern [#103](https://github.com/lenzo-ka/ipakit/issues/103) and [#101](https://github.com/lenzo-ka/ipakit/issues/101) established: what is particular to a language gets declared by that language. It is also exactly the structure-modifying capability that Wiebe needed extra power for. So the minimum ships intervals a rule can see, and leaves stranding for a second decision made against evidence rather than at the same time as this one.

**Correction to the brief on where a language would declare it.** #136's second comment says a C/D-shaped model "would not have to bend the library" because a language's phasing would live beside its rules in the file that already declares its other particulars. Measured, it cannot, as the format stands. A `.rules` file is one rewrite rule per line with `#`-initial comments and nothing else — no declaration form, no `define`, no metadata block, no import, and no schema; `find` turns up grammars for `ipa.xml`, `heads.xml`, phone maps and supplements, and none for rules. A rules file cannot introduce a symbol, a feature, a value or a level. Supplements are narrower still and deliberately so: `supplement.rng` refuses declarations outright, and the reason it gives is the metric — a bundle key is a term in it. So declaring a tier is an `ipa.xml` edit, which `ipa.rng` is built for, and the per-language half is a further decision about a format that does not yet have a place for it. **This does not weaken the case; it relocates it.** But "tiers can live there" had a cheap answer and the answer is no.

## 7. What is deliberately not made relative

#136's counterweight, addressed rather than deferred: the metric is universal and feature-based, and if a tier vocabulary becomes language-relative, something must say what does not.

**Distance does not become relative, and the mechanism that guarantees it is already load-bearing.** A tier is declared `mode="structural"`, and a structural feature is excluded by construction from every phone bundle — verified: `level` appears in no bundle, and no distance module references it. So a language declaring a syllable tier, a mora tier, or a gestural tier moves no distance, in the same way and for the same reason that a supplement adding three phones moves none while a three-line bridge moves up to 98% of them ([supplement-bridges.md](supplement-bridges.md)). The line is between a term in the comparison and a term in the structure, and a tier is on the far side of it.

Stated as the commitment: **tiers, their names, their inventory per language, and any phasing declared over them are language-relative. The feature space, the comparison bundle, and therefore `distance` are not.** If a later change would put a tier name into a comparison bundle, that is the boundary eroding, and the check that catches it is the one supplement-bridges.md asks for — a fingerprint, so a perturbed inventory reading the shipped matrix is refused rather than answering.

## 8. What it costs to be wrong

**If the read-only restriction is too strong**, the symptom is a phonology exercise that can be set up and not run: a form carrying a syllable tier, a rule that deletes a segment, and no way to say what happens to the tier. That is visible, it fails in the direction of refusing rather than answering wrongly, and it is exactly the marker for the second decision. The cost of having been too cautious is one further design pass; the cost of having been too permissive is the derivation trace, which is what the library is for.

**If intervals turn out to want anchoring to segments rather than to units**, the rebase changes and nothing else does. `Boundary.at` and `Attribute.at` already count and index *segments* rather than units, deliberately, so that a structural zero does not push later positions along. An interval that inherits that convention costs the same loop in a different arithmetic. This is cheap to be wrong about.

**If `Form` gaining a second field turns out to be the mistake**, it will show up as the round-trip and rebuild invariants getting harder to state rather than as a wrong answer, and [form.md](../form.md)'s known-limits section is where it will have to be admitted. The alternative — deriving every interval from separators, so `Form` stays one sequence — is available and is strictly weaker, because it cannot express an interval no glyph delimits, which is every interval on a gestural tier. The stronger version was chosen; if it is wrong, the weaker one is still there.

**If C/D is the right architecture after all**, the minimum here does not block it and does not help it much either. Nothing above commits to a segmental spine that a later C/D reading could not be layered over as a projection, and the position vocabulary stays reserved. What it would cost is that the spine is the segment and C/D's is not, so a C/D reading would be a *view*, not the representation — which is a real limitation and is stated here rather than discovered later.

## 9. What in the brief did not survive

**C/D's asymmetry is larger than "a syllable-level object does not exist here."** It has no segment at all; the syllable is the atom. §5.

**A `.rules` file cannot declare a tier, or anything else.** The claim that per-language phasing could live beside a language's rules without bending the library is false as the format stands. §6.

**Tiers do not cost the derivation trace, and the worry that they might is answerable from a source the repository already holds.** Read-only tiers are free in formal power and free in intermediates; the cost falls entirely on structure-modifying rules, and Bird & Ellison say so in those words. §2.

**`morph-boundary.md`'s `+` is an assessment, not a shipped feature.** There is no `+` separator in `ipa.xml` and no `morph` anywhere in the package. Its verdict is sound and its measurements stand; nothing should be built on the assumption that the data exists.

**The ladder is weaker than "weaker than it looks."** Not only is `_reaches` a scalar comparison — half the declared ladder is exercised by no shipped rule at all, and the whole live weight of the ordering is two rules relying on `.` also matching `#`.

**And one finding outside the brief.** Naming Kaplan & Kay's third application strategy under-determines the engine by one choice, because they give more than one formulation of obligatory simultaneous application (358). [calculus.md](../calculus.md) should say which overlap resolution it means. §2.
