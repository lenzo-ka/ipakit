# A calculus over the string set

`rewrite` maps a form to a form. That is the right answer for a grammar whose rules all hold, and the wrong shape for most of what people actually want to say about pronunciation, because a great deal of it is *variable*: French *petit* is [pəti] and [pti], from one speaker in one conversation, and neither is derived from the other.

So the object this document is about is not a form but a **set** of forms, and the operations over it. The notation is one character: `~>` in place of `->` marks a rule **optional**.

```python
import ipakit as ipa

ipa.rewrite("kæt", "t -> ʔ / _ #")            # 'kæʔ'
ipa.variants("kæt", "t ~> ʔ / _ #").forms     # ('kæt', 'kæʔ')
```

The engine is `ipakit.rules`, the notation is [rules.md](rules.md), and this document is the algebra: what the operations are, which of them are closed, what the identity is, whether composition is associative, whether the set is finite — and, stated as plainly as the rest, **what this calculus cannot say**.

## The one idea

`Query.sites` already answers with a *set* of sites, and `Action.edit` already maps one site to one edit. So the branch point in a rewrite was never the recognition or the action; it is the choice of **which subset of the edits to apply**, and it was simply never offered. `~>` offers it.

Nothing about matching changes. What changes is that the fold over a cascade carries a set of branches instead of one form, and an optional rule maps each branch to one child per subset of the edits it found at that branch.

## Optionality is per site, not per rule

This is the decision that costs, and it is not close. Rule-level optionality — the whole rule fires or it does not — bounds a set at 2^rules and is cheap. Site-level optionality bounds it at 2^sites and is the linguistically real one, because a word with two schwas has each of them independently droppable:

```python
french = ipa.ruleset("french-liaison")
french.variants("pətit").forms      # ('pəti', 'pti')
french.variants("dəvəniʁ").forms    # ('dəvəniʁ', 'dəvniʁ', 'dvəniʁ')
```

*Devenir* is the case worth staring at. Three of its four combinations are French and the fourth, \*[dvniʁ], is not — three consonants in a row, which the language does not allow there. A rule-level reading cannot produce the middle two at all. A site-level reading produces all four unless something stops it, and what stops it is [splitting the choices over ordered rules](#splitting-the-choices-over-ordered-rules), below — a technique with a boundary, which that section also measures.

## What this calculus cannot express

Not a list of bugs and not a roadmap. These are statements about the algebra's reach, and a reader deciding whether to teach with it or build on it needs them before the rest of the page, not after it.

One item has left the list, and it is named here rather than quietly deleted, because a reader may know the old one. **Agreement variables** — SPE's `n -> [place=α] / _ [place=α]` — are now notation, documented in [rules.md](rules.md#a-rule-may-bind-a-value-and-re-use-it), and the shipped English set states nasal place assimilation once instead of once per place. What that did *not* bring with it is the first item below.

**Metathesis.** There is no reordering operator. `ab -> ba` is not expressible, and the workaround — copy, then delete — is two ordered rules and says something slightly different. French liaison is shipped that way and the file argues the point.

Agreement variables were expected to bring this with them, since both want the right of the arrow to refer to material the left matched. They do not, and the two are worth keeping apart: a variable copies a feature **value** between positions the rule matched one at a time, where metathesis reorders the **positions**, which needs a target spanning more than one unit and a permutation to apply to it. A `Pattern` constrains one unit and a `Site` spans one, so `ab -> ba` is refused by the parser exactly as it was before variables existed. The mechanisms rhyme and are not the same one.

**A variable over a whole segment.** `[place=α]` binds a value of one declared feature. "A copy of whatever consonant stood there" is a variable over a *segment*, and there is no such term, so the shipped French set still writes one liaison rule per latent consonant: the copy rule has to name what it copies.

**Iterative within-rule spreading.** Vowel harmony as a single rule needs a loop, and a rule here matches against a snapshot of its input exactly so that it cannot feed itself. An ordered cascade of repeated rules says the same thing and terminates by construction.

**A constraint on the result of several optional choices.** New with `~>`, and the one worth reading twice. Within one rule the sites are found against a snapshot and then branch *independently*, so no site can see what another site chose. A well-formedness condition on the output — the loi des trois consonnes, or any output filter — therefore cannot be stated inside a rule:

```python
loose = ipa.ruleset("ə ~> ∅ / [-vowel] _ [-vowel] [vowel] ; both at once")
loose.variants("dəvəniʁ").forms
# ('dəvəniʁ', 'dvəniʁ', 'dəvniʁ', 'dvniʁ')
```

The fourth is over-generation. What is available instead is **ordering**, which answers this case and does not answer the general one; [Splitting the choices over ordered rules](#splitting-the-choices-over-ordered-rules) is that technique written down, with the word it fails on.

**A ranking over the set.** `variants` returns an *unranked* set. [pti] is commoner than [pəti] in most registers, and there is no way to say so: no weights, no probabilities, no ordering by likelihood. The order members come back in is derivational, not statistical, and reading it as a preference would be a mistake. A caller with frequency data joins it on afterwards.

**A relation, in the general sense.** A rule set is a *function from a form to a set*, not an arbitrary form-to-form relation. It cannot be inverted, intersected with another rule set, or complemented; there is no "the forms that both A and B derive" operator, because there is no operator that builds a rule set out of two rule sets except concatenation. Set intersection over two `VariantSet`s is of course available to a caller — the closure claims below are about which operations the *algebra* provides.

## Splitting the choices over ordered rules

A technique, written down here because a grammar-writer needs to be able to reach for it, and because it is the only answer this calculus has to the limit above. It is **not** a constraint, and the last part of this section is the word it gets wrong.

### The pattern

Rules are ordered and each sees the previous rule's output. Under `~>` that becomes: each rule sees the previous rule's output **branch by branch**, so a later rule asks its question of a form in which the earlier choice has already been made. That is where the information a single rule lacks comes back.

So: **partition the sites across two or more ordered rules, chosen so that taking the earlier choice destroys the later rule's environment.** The illegal combination is then not filtered out, it is never derived — it is ordinary bleeding, applied branch by branch instead of to one form.

### The worked case

French *e caduc* is governed by the **loi des trois consonnes**: a schwa may not drop if dropping it would leave three consonants in a row. *Devenir* /dəvəniʁ/ has two droppable schwas, three of whose four combinations are French:

| | |
| --- | --- |
| [dəvəniʁ] | neither drops |
| [dvəniʁ] | the first drops |
| [dəvniʁ] | the second drops |
| \*[dvniʁ] | both drop — *d v n*, and not French |

One rule matching both schwas derives all four, because within a rule the sites branch independently against a snapshot:

```python
loose.variants("dəvəniʁ").forms
# ('dəvəniʁ', 'dvəniʁ', 'dəvniʁ', 'dvniʁ')
```

The shipped set writes it as two ordered rules instead, split by what stands to the **left** of the schwa — a word edge for the first syllable, a vowel for the interior:

```python
[r.name for r in french if r.optional]
# ['e caduc (first syllable)', 'e caduc (interior)']
french.variants("dəvəniʁ").forms
# ('dəvəniʁ', 'dəvniʁ', 'dvəniʁ')
```

Exactly the three attested, and the mechanism is worth following on the branch where it matters. In the branch where the first schwa dropped, the form is `dvəniʁ`; the interior rule asks for `[vowel] [-vowel] _`, and the /v/ now stands behind a /d/ rather than behind a vowel. Its environment is gone, so the second schwa is not offered as a choice at all.

Each surviving member can say which rule made it:

```python
[(v.form, [s.rule for s in v.derivation.fired]) for v in french.variants("dəvəniʁ")]
# [('dəvəniʁ', []), ('dəvniʁ', ['e caduc (interior)']), ('dvəniʁ', ['e caduc (first syllable)'])]
```

The split is not a preference for one schwa over the other, and that is worth measuring rather than assuming. Reversing the two rules gives the same three forms in a different derivational order, because the bleeding runs both ways: after the interior schwa drops, `dəvniʁ` no longer offers the first rule its `_ [-vowel] [vowel]` either.

### When it works

Three conditions, and all three have to hold:

- **The illegal combination must be a local fact.** The later rule's environment is a window of neighbors, so taking the earlier choice has to change something inside that window. "Not both of these two adjacent choices" is reachable; "at most two schwas in the word" is not a context question at all, and no ordering states it.
- **The sites must be separable by context.** The partition is what makes them different rules. Here it is *first syllable* against *interior*, which is a distinction the left context already draws.
- **The constraint must survive being made directional.** Ordering imposes an asymmetry that a constraint does not have. Here it happens not to matter — measured, the two orders give the same set — but that is a fact about this pair, not a property of the technique.

### When it does not

**It is narrower than a real constraint, and the boundary is easy to reach.** The technique separates choices it can put in *different* rules. Two sites that fall to the **same** rule still branch independently against the snapshot, because that is exactly what the limit above says, and no amount of ordering reaches inside one rule.

French supplies the word. *Redevenir* /ʁədəvəniʁ/ has three droppable schwas, and the second and third are both *interior* — so they are one rule's two sites, and the shipped set derives a form the loi des trois consonnes forbids:

```python
french.variants("ʁədəvəniʁ").forms
# ('ʁədəvəniʁ', 'ʁədvəniʁ', 'ʁədəvniʁ', 'ʁədvniʁ', 'ʁdəvəniʁ', 'ʁdəvniʁ')
```

The fourth is \*[ʁədvniʁ] — *d v n* — and it is the same over-generation the two rules removed from *devenir*, one word further along. One of six here, where a single rule gave one of four there; the technique improved the ratio and did not change the kind.

So the honest statement is: **ordering states a constraint over a pair of choices the grammar can keep in separate rules, and states nothing about a pair it cannot.** A real output filter would rank or reject over the whole derived set, which is the operation this algebra does not have and which the list above says so. The technique is worth reaching for, and worth knowing the shape of, because a set that is *nearly* right reads exactly like one that is.

## The objects

`variants` answers with a `VariantSet`, not a list of strings, because two questions have to be answerable and one of them is easy to forget.

```python
found = french.variants("pətitə")
found.forms          # ('pətit', 'ptit')
found.complete       # True
len(found)           # 2
found[0].choices     # 0
found[1].choices     # 1
```

`VariantSet.complete` is the one to ask. `Variant` carries `form`, `choices` — how many optional edits that member takes — and a full `derivation`, so every member can account for itself.

`choices` is the **fewest** optional edits any derivation of that member takes, and the `derivation` is that one. The distinction is not idle: a cascade can reach one form by two routes, and the route it happens to reach first is not the cheapest one. Here `c` is one optional edit away by the first rule and two by the other two, and the member says one:

```python
detour = "a ~> c\na ~> b\nb ~> c"
ipa.variants("a", detour).forms          # ('a', 'b', 'c')
ipa.variants("a", detour)[2].choices     # 1
[s.rule for s in ipa.variants("a", detour)[2].derivation.fired]
# ['a ~> c']
```

Reporting the first route instead would make `choices` a fact about the order the rules are written in rather than about the form, and there is nothing else on a member for a caller to read cost from:

```python
found[1].derivation.result                        # 'ptit'
[s.rule for s in found[1].derivation.fired]
# ['final schwa deletion', 'e caduc (first syllable)']
```

## The order is part of the answer

Deterministic, and defined rather than incidental. Members come back in the order the cascade produced them; within one optional rule the subsets of its edits are enumerated **by size** first, smallest first, and by position within a size. Two consequences:

**`variants(f)[0]` is always `apply(f)`.** The first member is the one that takes no optional choice at all, which is exactly what the form-to-form entry points answer, so the two surfaces cannot drift apart:

```python
french.variants("pətitə")[0].form == french.apply("pətitə")   # True
```

An optional rule does not fire under `rewrite`, `derive` or `ipakit rules apply`. One form has to come out of those, so one choice has to be taken, and the null choice is the only defensible one. A trace marks the step *not taken* rather than *no change*, because a declined choice and a failed environment are different things.

**A truncated set keeps the members that depart least.** Two things make that true and the first of them is not enough on its own. Within one branch the subsets are graded by size rather than counted in binary, because counting in binary enumerates every subset of a *prefix* of the sites and none of the rest, so a cut set would show the leftmost schwa varying and the rightmost never varying at all — a biased sample dressed as a set. But a rule is handed a whole *set* of branches, and grading them one branch at a time spends the budget on the first branch's dearest children before the second branch's free child has been offered. So the graded streams are merged and the step keeps the cheapest children across every branch it was given:

```python
ipa.variants("abbb", "a ~> x\nb ~> y", limit=5).forms
# ('abbb', 'aybb', 'abyb', 'abby', 'xbbb')
```

Five members, none of them taking more than one optional edit, where a branch-at-a-time cut would have kept `ayyb` at two and dropped `xbbb` at one.

The cut is by cost and the presentation is derivational, and those are two different orders. Members come back in the order the cascade produced them either way, so a truncated answer is a *subsequence* of the complete one — the same members in the same sequence, with the dear ones missing. A cost-ordered presentation would reshuffle the answer as well as shorten it, and then a caller comparing a capped answer with a complete one would have to sort before diffing.

Nothing in the enumeration iterates a Python set or a hash, so the order does not depend on `PYTHONHASHSEED`.

## Closure, identity, composition

The algebra is small enough to state completely.

**The carrier** is the finite non-empty sets of forms.

**The operations closed over it** are two. Union, trivially. And *application of a rule set*, lifted from forms to sets by union: `R(S) = ⋃{R({f}) : f ∈ S}`. That lift is what makes everything below work — a rule set acts as a **union-preserving** (additive) map on finite form-sets, and a composition of additive maps is additive.

**The identity** is the empty rule set. `RuleSet(rules=())` maps every set to itself:

```python
empty = ipa.ruleset("")
len(empty)                        # 0
empty.variants("pətitə").forms    # ('pətitə',)
```

Identity *up to the read*: the answer is the form as the inventory read it, which is `Derivation.start`'s existing caveat and not a new one.

And up to the surface, which is the same shape of caveat. A form handed in may carry a zero; an answer never does ([below](#the-surface-projection-is-an-element-not-an-escape-hatch)), so the carrier above is sets of *surface* forms, and on that carrier the empty rule set is the identity exactly.

```python
ipa.ruleset("").variants("le∅ʃ").forms    # ('leʃ',)
ipa.ruleset("").variants("leʃ").forms     # ('leʃ',)
```

**Composition is concatenation of rule sets**, and it is associative — because concatenation of lists is, and because the lifted map of a concatenation is the composition of the lifted maps. Measured rather than asserted: every triple drawn from a pool of rules, against every form in a generated corpus, agrees on `(A ++ B) ++ C`, `A ++ (B ++ C)` and a single fold of all three. The sizes live in `tests/test_calculus.py`, which asserts a floor under them so the sweep cannot go quietly vacuous.

**Applying a rule set to the output set of another is the same as applying the concatenation.** This is the claim a user actually leans on, and it is stronger than it needs to be — the two agree *in order*, not merely as sets:

```python
a = ipa.ruleset("a ~> e / _ t ; raise")
b = ipa.ruleset("t ~> ʔ / _ # ; glottal")
both = ipa.ruleset("a ~> e / _ t ; raise\nt ~> ʔ / _ # ; glottal")

both.variants("at").forms                                   # ('at', 'aʔ', 'et', 'eʔ')
tuple(dict.fromkeys(w.form for v in a.variants("at")
                            for w in b.variants(v.form)))    # ('at', 'aʔ', 'et', 'eʔ')
```

Swept: every pair of rule sets against every generated form, all of them agreeing on the set **and on the order**. The order agreeing too is not required by the algebra and is worth having: it means a caller who splits a cascade for any reason gets back the same answer in the same sequence, so a diff between the two ways of writing it is empty rather than merely equivalent.

There is one gap in that proof worth naming, because it is the kind that hides. The internal fold carries `Unit` sequences between rules while the external composition carries *strings*, which are read back. The two agree only if spelling is faithful over the forms these rules produce. That is what the sweep measures; it is not something the argument can establish on its own.

### The surface projection is an element, not an escape hatch

A rule may write a **zero** — `z -> [zero]`, a position the transcription keeps open with nothing in it ([rules.md](rules.md#the-surface-carries-no-zero)) — and a derivation carries it, because holding the position is what makes the deletion site visible in the trace. A pronunciation does not. So the last thing that happens is the rewrite that removes them, and *that it is a rewrite* is what this page is about:

```python
ipa.rules.surface().rules[0].source     # '[zero] -> ∅ ; surface'
ipa.variants("dəvəniʁ", "ə ~> [zero] / [-vowel] _ [-vowel]").forms
# ('dəvəniʁ', 'dvəniʁ', 'dəvniʁ', 'dvniʁ')
```

A projection standing *beside* the notation would have left the closure claims above true of the algebra and not of the thing a caller reads. Written as a rule it is another element of the same algebra: it composes, it can be declined, and `ipa.ruleset("[zero] -> ∅")` is it.

**The set is deduplicated after the projection.** Members are keyed on their spelling and the surface rewrite is the last thing to change one, so two branches that differed only in where a zero stood come back as one pronunciation. Dedup first and project afterwards would let `forms` list the same string twice, and a set of pronunciations that repeats itself is not a set. Measured on the French schwa set, the choice is not observable — the two schwas of *devenir* stand in different company, so all four surfaces differ and either reading gives four. It parts on a word whose sites are interchangeable:

```python
ipa.variants("kaa", "a ~> [zero]", keep_zeros=True).forms   # ('kaa', 'k∅a', 'ka∅', 'k∅∅')
ipa.variants("kaa", "a ~> [zero]").forms                    # ('kaa', 'ka', 'k')
```

Four derivations, three pronunciations. `complete` and the cap keep their meanings exactly: the surface rewrite is obligatory, so it offers one child per branch and can merge but never truncate, and `unexplored` goes on counting the choice combinations the *cascade* did not enumerate. What changes is that `len(variants)` counts pronunciations where it counted derivations, and for a rule set that writes no zero those are the same number.

Like the cap, it is applied **per call**, and for the same reason: splitting a cascade into two calls applies it twice, so a zero the first half writes is gone before the second half can read it. `keep_zeros=True` on the inner call is the repair, and what it says is that the intermediate was a derivation rather than a pronunciation.

### The cap is where associativity stops

`limit` bounds what a cascade carries between rules, and it is a bound **per call**. So splitting one cascade into two calls doubles the budget, and the identity above fails as soon as the cap fires:

| | `A ++ B` in one call | `B` applied to `A`'s answer |
| --- | --- | --- |
| uncapped | 128 variants, complete | 128 variants |
| `limit=8` | 8 variants, **`complete` is `False`** | 64 variants |

Measured on `[vowel] ~> [length=long]` then `t ~> ʔ` over `atatata`. This is not a defect to be repaired; a bounded enumeration cannot be a homomorphism. It is the reason `complete` exists and the reason to ask it: **every algebraic claim on this page holds of a complete answer and none of them holds of a truncated one.**

## Finiteness

The set is **always finite**, for every rule set and every form, insertion included. The argument is short and rests on a property the engine already had:

1. A rule matches against a **snapshot** of its input, so it cannot feed itself and a pass terminates by construction.
2. One rule therefore offers at most `2 ** n` children per branch, where `n` is the number of edits it found — and `n` is bounded by the length of the form.
3. A cascade is a finite fold of steps each of which is finite.

Optionality alone does not endanger this. Neither does insertion, which was the case worth checking, because an insertion lengthens the form the *next* rule scans — so the bound grows, but stays a bound. Measured, on the adversarial set `∅ ~> t / [-vowel] _` repeated k times against `pk`:

| rules | variants | longest form |
| --- | --- | --- |
| 1 | 4 | 4 |
| 2 | 16 | 8 |
| 3 | 64 | 16 |
| 4 | 256 | 32 |

Exactly `4 ** k` variants over forms of `2 ** (k+1)` units. Finite, terminating, and **doubly exponential in the number of rules** — which is the whole case for a cap, and for the cap being visible.

## The cap

`limit` defaults to 256 — 2^8, eight independently varying sites in one word, which is past what a natural language offers. It is a parameter with no ceiling.

The rule of this repository is that there are **no silent caps**. A truncated set of pronunciations reads exactly like an exhaustive one, which is the shape every defect in this library has taken (see [reviewing.md](reviewing.md)). So a cut is reported in the returned object:

```python
long_word = ipa.variants("aaaa", "[vowel] ~> [length=long]", limit=4)
long_word.complete      # False
long_word.unexplored    # 12
long_word.truncations[0].rule
# '[vowel] ~> [length=long]'
```

`unexplored` counts **combinations of optional choices** the step did not enumerate — an exact count of what was not looked at, and an upper bound on the distinct forms missing, since distinct choices can spell the same form. It is exact without doing the work the cap exists to avoid, because the arithmetic is known in advance: a branch with n edits offers 2^n.

On the command line the count line carries it, so it cannot be missed by someone who did not know to look:

```console
$ ipakit rules variants -r '[vowel] ~> [length=long]' aaaa --limit 4
aaaa: 4 variants -- INCOMPLETE: cut at rule 1 ([vowel] ~> [length=long]), 12 choice combination(s) unexplored; raise --limit
  aaaa
  aːaaa
  aaːaa
  aaaːa
```

## The set has a distance to a target

Which is the operation that makes this useful outside a classroom, and it needs no new API — it is the metric composed with the set:

```python
target = "pti"
min(ipa.distance_model().distance(target, v) for v in french.variants("pətit").forms)
# 0.0
```

**Minimum over the set** is the definition that matches the question pronunciation assessment asks: *is what the learner said a possible pronunciation of this word?* A speaker who produces any licensed variant has produced the word, and scoring them against a single citation form penalises them for a variation the grammar itself licenses. The minimum is the natural reading and it is what a caller should reach for first.

Two things that minimum is not. It is not a distance between a *pronunciation* and a *word* in any distributional sense — an unranked set has no center and no spread, so a mean over the set would be an average over forms that are not equally likely, and would not mean anything. And it inherits the metric's limits wholesale, including that `distance` does not satisfy the triangle inequality ([distance.md](distance.md)), so this is a score, not a position in a space.

It is deliberately *not* a method on `VariantSet`. Making it one would put a dependency on the metric inside the rule engine to save a caller one line, and the line above says what it does more clearly than a name would.

## Where else to look

- [rules.md](rules.md) — the notation, including the `~>` arrow's other spellings, and everything about the obligatory half.
- `ipakit/data/rules/french-liaison.rules` — the shipped set, which argues the e caduc analysis at length and records what it leaves out.
- [reviewing.md](reviewing.md) — why the cap is visible, and why every number on this page is a measurement rather than a claim.
</content>
