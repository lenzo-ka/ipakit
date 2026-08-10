# Morphological boundaries: assessment

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

How should ipakit mark the boundary in *cat+s*, *un+happy*, *hand+ful* — the morphological seam, which no IPA symbol names and which the prosodic hierarchy has no rung for?

**Verdict: BUILD IT, as a tier of its own, and make it transparent.** One separator, `+`, declaring a `morph` feature and no `level`, so `rules._reaches` never ranks it against `syllable`, `word`, `phrase`, `utterance`, and so context scanning steps over it unless a rule names it.

Putting it on the prosodic ladder is wrong in both directions and both are measured below: above `syllable`, the shipped German final-devoicing rule takes *dogs* `dɔɡ+z` to **`dɔk+s`**; below it, a rule written for a morpheme boundary fires at the syllable break in *a.pple*. A tier of its own does neither, and it costs nothing in the metric — 0 of 8,616 bundles, 0 of 9,591 pairwise distances — because a separator is not a phone and `mode="structural"` keeps the key out of every bag.

**Four things the brief expected did not survive the measurements or the sources.**

**SPE's own boundaries are not a strength scale, which is a better argument for the separate tier than the ladder measurement is.** *SPE* §1.3.1 makes each boundary a set of features on a `[−segment]` symbol: `+` is `[−segment, +FB, −WB]`, `#` is `[−segment, −FB, +WB]`, `=` is `[−segment, −FB, −WB]`. Two binary features, not one ordinal. And their *defaults are opposite* — `+` is transparent to a rule that does not mention it, while a string containing `#` is not subject to a rule unless the rule names `#` in the proper position. Two marks that differ in default opacity cannot be two points on one scale, and the source that invented both says so. ipakit already has that split, between the transparent `.` and the opaque `#`; the seam joins the transparent side, and nothing about it belongs on the ladder.

**Transparency is the half that would have been got wrong, and it is expensive.** A level-less separator is opaque under `Unit.transparent` as it stands, because that property reads `level == "syllable"`. Swept across all five shipped rule sets, writing a seam at every legal position:

| | seam positions where writing the seam changes the pronunciation |
|---|---|
| `+` opaque | **122 of 486** |
| `+` transparent | **0 of 486** |

That is the dot's own argument arriving for a second reason — *if `.` blocked a context, the same word would get two answers depending on whether someone typed the dots* — and it is SPE's stated convention, verified in the primary: **"the presence of `+` can be marked in a rule, but the absence of `+` cannot be marked in a rule … If a process applies to a sequence without formative boundaries, it also applies to otherwise identical sequences containing these units."**

**The plural does not need braces.** [captures.md](captures.md) found that six times more shipped rules are waiting on SPE's braces than on any capture, and the reasonable guess was that the English plural is another of them. It is not. `[sibilant]` is a declared *alias* on `channel="grooved"` and it selects exactly the class the epenthesis rule wants, affricates included. Three lines give all seven test words. Nothing here is blocked on braces, and nothing here is blocked on captures.

**And the textbook rules do not mention the boundary at all.** Hayes, Levine and Odden each state the plural with features and a word edge and no morpheme boundary anywhere in the environment; *SPE* never states the English plural rule. The `+` sits in the *underlying representation* and is named by no rule. So the case for the seam is not "the rules cannot be written without it" — measured, they can, and they give the right answers. The case is that **the underlying form cannot be written without it**, which is the form the analysis is about and the one an exercise has to hand a student.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Does a morph boundary rank against the prosodic ladder? | **No, and both placements are wrong.** Above `syllable`: a shipped rule takes `dɔɡ+z` to `dɔk+s`. Below it: a `+` rule fires at `.` and at `#`. |
| Does the source that invented `+` and `#` treat them as one scale? | **No.** Two binary features on a `[−segment]` symbol, with opposite default opacity. Read in the primary. |
| Does a tier of its own avoid both failures? | **Yes.** `. _` does not reach `+`, `+ _` does not reach `.` or `#`, and `+ _` reaches `+`. |
| Should the seam block a context that does not name it? | **No — 122 of 486 seam positions across the five shipped sets change the pronunciation if it does.** Transparent: 0 of 486. |
| Does `+` collide with the binary value in `[voiced=+]`? | **No.** `[voiced=+]`, `[+voiced]`, `[voiced=-α]` and `[place=α]` all parse unchanged against an inventory declaring `+`. |
| Does it collide anywhere else in the rule parser? | **Yes, and worse than a collision.** Undeclared to `_pattern`, `+` parses as a *literal*: `s -> ʃ / + _` finds no sites and `+ -> ∅` makes no edit, both in silence, while `t -> +` on the right of the arrow is correctly refused as an exchange. The two sides of the arrow disagree. |
| Is one boundary enough? | **Yes**, and if a second is ever wanted the tier is **nominal, not ordinal** — the stratal work the second boundary would do belongs to the cascade, which is where the field moved it. |
| Did the field keep `+`? | **No — it was abandoned as a diacritic and its work reassigned to strata.** §6 answers why adopting it here is nonetheless right. |
| Can the English plural be stated with it? | **Yes, in three lines, needing no operator that does not exist.** All seven test words. |
| Does it need braces? | **No.** `[sibilant]` selects the class exactly, and no source states the rule with braces either. |
| Do the standard textbook rules name the boundary? | **No — none of the four formal statements read puts a boundary in a rule environment.** It lives in the underlying form. |
| Should it be stripped by the surface rewrite? | **No.** Erasure after every rule gives `kæt+z` → `kætz`. As the last rule of the set it gives `kæts`. |
| What does it cost the metric? | **Nothing** — 0 of 8,616 bundles, 0 of 8,616 `d_from_base`, 0 of 9,591 pairs. But `mode="structural"` is what makes that true, not the tier: with the additive default and one diacritic declaring `morph`, 131 bundles and 139 distances move. |
| Does it make the not-a-bracketing worse? | **Neither.** `kæt+s` and `kæts` give the same tree, which is the right answer. But `kæt++s` validates clean where `##kæt` warns, because `empty_constituent` is keyed on `level`. |
| Does `%` reach it? | **Yes, as built, and it should not.** `%` is "a boundary of any *level*" and `+` declares none. |
| Does `Form.boundaries` report it correctly? | **No.** `Boundary.level` falls back to `word`, and the fallback is reachable from data for the first time. |

## Sources

**Read directly.**

- Chomsky & Halle, *The Sound Pattern of English* (Harper & Row 1968), §1.3.1 "Boundary Features", pp. 66–68 and n. 7 — the feature analysis of the boundaries and the transparency convention. Open access on Fulcrum: <https://www.fulcrum.org/concern/monographs/2z10wq58b>, PDF at <https://www.fulcrum.org/ebooks/ms35tc39t/download?locale=en>. See the spin-off finding at the end of this document.
- Bruce Hayes, *Introductory Phonology* (Wiley-Blackwell 2009), pp. 85, 112, 133–135, 220, 259, and p. 86 n. 5: <https://vulms.vu.edu.pk/Courses/ENG507/Downloads/Introductory%20Phonology%20by%20Hayes.pdf>. The PDF's text layer uses a custom-encoded font that mangles IPA, so the rule statements were verified from rendered page images rather than from extracted text.
- David Odden, *Introducing Phonology* (Cambridge University Press 2005), pp. 72, 77–78, 159: <https://jinxiaosong.wordpress.com/wp-content/uploads/2015/02/odden-introducing-phonology.pdf>
- Robert Levine, *Ling 601*, Ohio State, Winter 2010: <https://www.asc.ohio-state.edu/levine.1/pdf/601phonology1.pdf> — the fully formal plural derivation with explicit ordering.
- Gregory Iverson, in Goldsmith (ed.), *The Handbook of Phonological Theory*, ch. 19 — the epenthesis/devoicing bleeding order.
- Selkirk, "The prosodic structure of function words" (1995/96): <http://people.umass.edu/selkirk/pdf/PSFWUMOP'%20copy.pdf> — the decomposition of the Strict Layer Hypothesis into Layeredness, Headedness, Exhaustivity and Nonrecursivity. Must be fetched with `curl` and read with `pdftotext`; an ordinary fetch returns a truncated six-page copy of a paper about 2,600 lines long.
- Selkirk 2011, on what survives of the case for prosodic constituency; Kiparsky 1982 and Newell 2021 on the stratal reassignment of `+`; Bermúdez-Otero 2013 §28. Quoted in §6.

**Sought and not reached, with what was tried.** Each entry records an attempt on a date, by a route. None is a claim that the work is unavailable, and a search that came back empty is evidence about the search.

- Selkirk, *Phonology and Syntax: The Relation between Sound and Structure* (MIT Press 1984) — checked 2026-08-02: OpenAlex reports no open location and indexes only paywalled reviews. Read at one remove, through the secondary literature, and labeled where it appears.
- Nespor & Vogel, *Prosodic Phonology* (Foris 1986) — checked 2026-08-02: no open location for the Foris edition or for the De Gruyter reissue. Read at one remove, and labeled.
- Kenstowicz, *Phonology in Generative Grammar* (Blackwell 1994), and Kenstowicz & Kisseberth, *Topics in Phonological Theory* (Academic Press 1977) — checked 2026-08-02: no open location in OpenAlex for either, and the archive.org copies are lending-restricted with search-inside reporting no text without a loan. Nothing here is attributed to either.
- MIT OCW 24.900 problem-set solutions — HTTP 405, and not retried.

Selkirk 1984 and Nespor & Vogel are the canonical statements of the Prosodic Hierarchy, and every claim attributed to them below is from secondary literature and is labeled where it appears. That matters more than usual, because they are the works the non-isomorphism argument belongs to. One widely circulated line to the effect that prosodic structure is *not necessarily isomorphic to any constituents found elsewhere in the grammar* traces to a search-engine summary of a page nobody could open; it is not quoted here and should not be.

**Reachable, and not relied on here.**

- Anderson et al. (eds.), *Essentials of Linguistics*, 2nd edition (eCampusOntario Pressbooks 2022), CC BY-SA: <https://ecampusontario.pressbooks.pub/essentialsoflinguistics2/>. Openly licensed and readable in full. A search snippet attributing a bleeding-order account of the plural to it does not survive the book: §5.4 states English plural allomorphy descriptively and as a list of allomorphs, and §4.8 demonstrates a derivation table on a single French devoicing rule. There is no rule interaction in either, so the bleeding order here rests on Iverson and Levine.
- Kenstowicz & Kisseberth, *Generative Phonology: Description and Theory* (Academic Press 1979) — a copy was obtained and read for [braces.md](braces.md), which cites pp. 339–42 and 359–64. Not open access. Nothing in this document rests on it.

The reachability pattern is worth recording on its own: **the pedagogical sources are open, the 1968 primary is open, and the two 1980s theoretical monographs are not.** Every textbook statement of the plural rule in this document was read in full; neither book the Prosodic Hierarchy is usually cited from has an open copy this lane could find.

## 1. Why the ladder is the wrong home

The claim this document is downstream of is that prosodic constituency and morphosyntactic constituency are **different structures over the same string**, neither containing the other. *Cats* is the smallest demonstration: /kæts/ is one syllable, and it contains a morpheme boundary. Whatever a morpheme boundary is, it is not a rung between "syllable" and "word", because it is inside a syllable.

**That argument should not carry the whole verdict, and the reason is in the literature rather than in the code.** Selkirk 1984 and Nespor & Vogel 1986 are the references for the Prosodic Hierarchy and for the Indirect Reference Hypothesis — that phonological rules refer to prosodic constituents rather than to morphosyntactic ones. Neither could be opened, so the attribution here is secondhand. And Selkirk's own later position is weaker than the version usually repeated: *"It turns out that the only argument for prosodic constituent structure that stands the test of time comes from nonsyntactic influences on phonological domain structure"* (2011). The two-representations conclusion survives; the justification moved from systematic misalignment to markedness effects — weight, eurhythmy, speech rate. So the honest form of the claim is not "the two structures are always misaligned" but **"they can be, *cats* is a case, and a representation that forces them onto one ladder is wrong in a case that occurs in the first week of every phonology course."**

The hierarchy has also loosened from the inside, which is worth knowing before treating it as a rigid ladder. Selkirk 1995/96 decomposes the Strict Layer Hypothesis into four separable and violable constraints — Layeredness, Headedness, Exhaustivity, Nonrecursivity — so even *within* the prosodic tiers, strict containment is a preference rather than a definition. ipakit's `_reaches` implements the strict reading, and rightly, since every boundary it ranks is one people actually write. But a strict ladder is the wrong instrument for a mark that is not on the ladder at all, and it is worth being clear that adding the seam to it would be strengthening the strictest available reading, not extending an established one.

**Two things do carry the verdict, and both were verified rather than cited.** The first is §2's measurement, which needs no theory at all. The second is what *SPE* actually does with its boundaries, which turns out to be the separate-tier design.

*SPE* §1.3.1 treats each boundary as a symbol of the representation bearing a feature bundle, one of whose features is `[−segment]`; footnote 7 is explicit that the formative boundary is such a symbol and not the concatenation operator. Three boundaries are cut out of two binary features:

| | `segment` | `FB` | `WB` |
|---|---|---|---|
| `+` formative | − | + | − |
| `#` word | − | − | + |
| `=` | − | − | − |

That is a **feature space, not a scale**. Nothing in it says `#` is a stronger `+`, and nothing supports asking whether one reaches the other. And the defaults confirm it: `+` is transparent to a rule that does not mention it, while a string containing `#` is not subject to a rule unless the rule names `#` in the proper position. Two marks whose *defaults are opposite* cannot be two points on one strength scale.

ipakit already has that opposition, and has it for reasons of its own: `.` is transparent because it is optional notation, `#` is opaque because it is a real edge. The seam joins the transparent side. What it must not join is the ordinal ladder, and *SPE* is the source arguing so from the segmental end while the Prosodic Hierarchy argues it from the phrasal end.

So a syllable is a **domain** that rules are stated *over*. A morpheme boundary is a **fact about the string** that rules are stated *across*, transparently and by convention, and that a rule may name when it needs to. Those are different kinds of object, and an ordinal ladder holds only the first kind.

## 2. The ladder, measured in both directions

`rules._reaches` is `order.index(level) >= order.index(wanted)` over the declared values of `<feature name="level">`, and the file's own comment says why it is read rather than restated: *the order is what says a word boundary is also a syllable boundary*. Three throwaway copies of `ipa.xml` put `+` in three places — a value below `syllable`, a value above it, and a feature of its own — and nothing else differs between them.

```
1. reaching: does a morph boundary rank against the prosodic ladder?
  morph below syllable: level = ['morpheme', 'syllable', 'word', 'phrase', 'utterance']
    s -> ʃ / . _     on kæt+s   -> 'kæt+s' (0)
    s -> ʃ / + _     on kæt.s   -> 'kæt.ʃ' (1)
    s -> ʃ / + _     on kæt#s   -> 'kæt#ʃ' (1)
    s -> ʃ / + _     on kæt+s   -> 'kæt+ʃ' (1)
  morph above syllable: level = ['syllable', 'morpheme', 'word', 'phrase', 'utterance']
    s -> ʃ / . _     on kæt+s   -> 'kæt+ʃ' (1)
    s -> ʃ / + _     on kæt.s   -> 'kæt.s' (0)
    s -> ʃ / + _     on kæt#s   -> 'kæt#ʃ' (1)
    s -> ʃ / + _     on kæt+s   -> 'kæt+ʃ' (1)
  a tier of its own:
    s -> ʃ / . _     on kæt+s   -> 'kæt+s' (0)
    s -> ʃ / + _     on kæt.s   -> 'kæt.s' (0)
    s -> ʃ / + _     on kæt#s   -> 'kæt#s' (0)
    s -> ʃ / + _     on kæt+s   -> 'kæt+ʃ' (1)
```

Below `syllable`, a rule written about the morpheme boundary fires at every prosodic boundary there is, and the seam in *a.pple* is not a morpheme boundary. Above it, a rule written about the syllable margin fires at the morpheme boundary, and the /s/ of *cats* is not syllable-initial.

The second of those is not hypothetical. It reaches a rule this repository ships, unmodified:

```
2. a shipped rule set over morph-bounded input
  [obstruent] -> [voiced=-] / _ . ; final devoicing
    morph below syllable   dɔɡ+z->'dɔɡ+s'  kæb+z->'kæb+s'  dɔɡ.z->'dɔk.s'  dɔɡ#z->'dɔk#s'
    morph above syllable   dɔɡ+z->'dɔk+s'  kæb+z->'kæp+s'  dɔɡ.z->'dɔk.s'  dɔɡ#z->'dɔk#s'
    a tier of its own      dɔɡ+z->'dɔɡ+s'  kæb+z->'kæb+s'  dɔɡ.z->'dɔk.s'  dɔɡ#z->'dɔk#s'
```

German *Hunde* is [hʊndə], not \*[hʊntə]; final devoicing is *final*, and a morpheme boundary is not a final position. With `morpheme` ranked above `syllable`, writing the seam devoices the stem-final obstruent of every plural in the language, silently, from a data change alone.

Neither failure is a bug in `_reaches`. `_reaches` is right: the prosodic tiers *do* nest, and reading the containment off declaration order is what keeps one fact in one place. The mistake is asking an ordinal ladder to hold something that is not on it.

**So the separate-tier recommendation survives, and for a stronger reason than the brief gave.** The brief's argument was that either placement is wrong in one direction. The measurements say more: the wrong placement is not *detectably* wrong. Both prototypes load, both validate against `ipa.rng`, both pass every check in `scripts/invariants.py`, and both leave the metric byte-identical. The only thing separating them is a derivation coming out different, and nothing in the repository would say so.

## 3. Transparency

`Unit.transparent` is `self.level == "syllable"`. A separator declaring no level is therefore opaque, blocking context scanning as `#` does — which is what the data change alone produces, and it is wrong.

The sweep: for each of the five shipped rule sets and each word of `tests/test_rule_sets.py`'s corpus, insert `+` at every position between two segments that the parser re-spells, apply the set, strip the seam from the output, and compare against the derivation of the seam-less word. This is the shape of the boundary-run invariant `rules.py` already states for `#` — `r(f) == strip(r("#" + f))` — asked of the new mark.

```
  '+' opaque (level-less marks block context, as Unit.transparent stands)
    american-english              64 of   118 seam positions change the derivation
    spanish-accented-english      13 of    99 seam positions change the derivation
    japanese-moraic               35 of   104 seam positions change the derivation
    french-liaison                10 of   119 seam positions change the derivation
    german-final-devoicing         0 of    46 seam positions change the derivation
    TOTAL                        122 of   486
  '+' transparent (a level-less separator is stepped over unless named)
    american-english               0 of   118 seam positions change the derivation
    spanish-accented-english       0 of    99 seam positions change the derivation
    japanese-moraic                0 of   104 seam positions change the derivation
    french-liaison                 0 of   119 seam positions change the derivation
    german-final-devoicing         0 of    46 seam positions change the derivation
    TOTAL                          0 of   486
```

Opaque, a quarter of the places a student could write the seam change what the American English set does to the word. Transparent, none of them do.

**The reason is the dot's reason, for a second cause.** The dot is transparent because it is *optional notation*, and a rule set must not give one answer for `bʌtɚ` and another for `bʌ.tɚ`. The seam is transparent because it is *not prosodic at all*, so a rule stated over prosodic and segmental material has nothing to say about it either way. Two different reasons, one behavior, and the rule that produces both is not "syllable-level marks are transparent" but **"a boundary that is not a prosodic edge is transparent"**. `docs/rules.md` states the current version as *which are transparent is read from the declared `level`*; the generalization keeps that read and widens what it reads.

It is also the convention *SPE* states outright, which is the part worth having found rather than reasoned to — presence markable, absence not markable. A rule may say `/ [voiced=-] + _`, and a rule that says `/ [voiced=-] _` must fire whether or not the seam is written. That the measurement and the 1968 convention agree to the digit is the strongest evidence available that the transparent reading is the intended one rather than a convenience.

**Transparency does not cost the rules that name it.** Named, the seam still matches; the erasure rule still finds it; the boundary-run invariant still gives one edit per anchor with a seam beside an edge:

```
    s -> ʃ / + _               on kæt+s   -> 'kæt+ʃ' (1)
    s -> ʃ / + _               on kæt.s   -> 'kæt.s' (0)
    z -> s / t _               on kæt+z   -> 'kæt+s' (1)
    + -> ∅                     on kæt+s   -> 'kæts' (1)
    ∅ -> ɪ / [sibilant] + _ z  on bʌs+z   -> 'bʌs+ɪz' (1)
    ∅ -> ə / # _               on #+tæt   -> '#+ətæt' (1)
    ∅ -> ə / _ #               on tæt+#   -> 'tætə+#' (1)
```

**One residue, and it is a teaching point rather than a defect.** Transparency makes a *substitution* blind to the seam, exactly as intended, but an *insertion* still has to land on one side of it. The boundary-less epenthesis rule puts the vowel before the seam and the boundary-naming one puts it after:

```
    ∅ -> ɪ / [sibilant] _ z    on bʌs+z -> 'bʌsɪ+z'      the vowel joins the stem
    ∅ -> ɪ / [sibilant] + _ z  on bʌs+z -> 'bʌs+ɪz'      the vowel joins the suffix
```

Both erase to `bʌsɪz`, so the pronunciation is the same and the sweep above counts zero. What differs is the segmentation the derivation records, and the second is the analysis every textbook gives. That a rule can be right about the sound and wrong about the morphology is a good thing for an exercise to be able to show.

## 4. What the change is

Data, and four clauses.

### The declaration

```xml
<feature name="morph" short="mph" mode="structural" desc="Morphological boundary" href="Morpheme">
  <value name="formative" short="fmv"/>
</feature>
```

```xml
<separator name="+" morph="formative"/>
```

Both blocks accept it as they stand: `ipa.rng` requires `name` on a `<separator>` and admits any other attribute, because *those attribute names are not free-form: they ARE the feature names declared in `<features>` above them*. All three prototypes validate with `xmllint --noout --relaxng ipakit/data/ipa.rng`.

**The values of this feature are nominal, and the declaration should say so**, because `level` sitting three lines below it declares its values *in order* and is read ordinally in two places. Nothing reads `morph` that way, and nothing should: the matcher in clause (a) is exact-glyph equality. That is the `<separators>` half of the same fact §1 records about *SPE* — the boundaries are a feature space, and the one thing they are not is a ladder.

`mode="structural"` is doing real work and §8 measures how much. It is the same reasoning the `level` feature's own comment records: without it the key falls to the additive default, and an additive key is one a diacritic could put in a phone's bundle.

**A separator, not a suprasegmental.** Prototyped both. As a suprasegmental, `+` is a mark on a segment, and a structural mark on a segment is one the segment cannot spell back — declaring `morph` on `ʰ` took the sweep corpus from 8,616 units to 8,477, because the aspirated units stopped re-emitting themselves. A morpheme boundary is a relation between segments, which is what `<separators>` is for and what `ipakit/form.py` already says a boundary is. It is also what *SPE*'s `[−segment]` says, from the other direction.

`+` also has to be listed in `<notations>` as an extension, beside `␣`, `#` and `∅`, since it is off the IPA chart for the same reason `#` is. That is a two-place edit — the block and `NON_CHART` in `scripts/invariants.py` — and §9 records why the invariant will not catch the omission.

### (a) `rules._pattern`: a separator declaring no `level` is an exact-glyph mark

This must land with the data, because without it the notation is silently broken rather than merely incomplete:

```
3. '+' declared, and no clause in _pattern
  s -> ʃ / + _         on kæt+s   -> 'kæt+s' (0)
  + -> ∅               on kæt+s   -> 'kæt+s' (0)
  + -> t               on kæt+s   -> 'kæt+s' (0)
  + -> [level=word]    on kæt+s   -> 'kæt+s' (0)
  t -> +               on kæt+s   -> REFUSED RuleError
  + -> .               on kæt+s   -> REFUSED RuleError
```

`_pattern` reads `features.separators`, takes the `level` off the declaration, finds none, and lets `+` fall past the boundary branch, past `ANY_BOUNDARY`, past `boundary_marks`, into the literal branch — a segment pattern no boundary unit will ever match. Every rule naming it parses and does nothing. Meanwhile the *right* of the arrow already knows `+` is a boundary and refuses the exchange with its full message. One side of the arrow reading a symbol as a boundary and the other as a segment is the worst available state, and it is what the data change alone produces.

The clause is short, and the shape is already in the file. `‿`, `|` and `‖` are matched by `Pattern(mark=text)`, which is exact-glyph equality with no `_reaches` call at all — precisely the semantics a nominal tier wants:

```python no-run
declared = features.separators.get(text)
if declared is not None:
    level = (declared.features or {}).get("level")
    if level is not None:
        return Pattern(source=text, boundary=level)
    return Pattern(source=text, mark=text)      # no prosodic level: this glyph, exactly
```

With it, everything the notation should say, it says:

```
4. the same, with the clause
  s -> ʃ / + _         on kæt+s   -> 'kæt+ʃ' (1)
  + -> ∅               on kæt+s   -> 'kæts' (1)
  + -> ∅               on kæt.s   -> 'kæt.s' (0)
  + -> ∅               on kæt#s   -> 'kæt#s' (0)
  ∅ -> + / t _ s       on kæts    -> 'kæt+s' (1)
  t -> +               on kæt+s   -> REFUSED RuleError
```

Note the third and fourth lines against the second. `. -> ∅` deletes a written `#` too, because a boundary pattern is a class and the ladder nests; `+ -> ∅` deletes only `+`, because this one is not on the ladder. Both readings are right, and they are right for the same declared reason.

### (b) `Unit.transparent`: a boundary with no declared level is stepped over

§3 is the whole argument. One condition, and it should carry its own reason in the docstring, because the property's current docstring gives the dot's reason and the seam's is different.

### (c) `Pattern.matches`: `%` requires a declared level

`ANY_BOUNDARY` is documented as "a boundary of any level", and its implementation is `if self.boundary == "any": return True` for any boundary unit. A morph boundary has no level, so as built `%` reaches it:

```
5. '%' with and without the second clause
  as built                   kæt+s->'kæt+ʃ' (1)  kæt.s->'kæt.ʃ' (1)  kæt#s->'kæt#ʃ' (1)
  '%' needs a declared level kæt+s->'kæt+s' (0)  kæt.s->'kæt.ʃ' (1)  kæt#s->'kæt#ʃ' (1)
```

No shipped rule writes `%` — `french-liaison.rules` names it only in a comment saying *do not "simplify" `_ #` to `_ %`*, with 28 of 143 dotted spellings moving when it was tried. So this is prospective rather than live, and it is the same hazard that comment is about: a wildcard silently widening as the inventory grows. The clause is one condition.

### (d) `Form.Boundary.level` must not fall back to `word`

[form.md](../form.md) lists the fallback as a known limit: *"only a hand-made `Boundary`, or a mark added without a level, reaches it"*. Declaring `+` is exactly a mark added without a level, so the limit stops being unreachable:

```
Boundary(text='+', level='word', at=3, features={'morph': 'formative', 'class': 'separator'})
Boundary(text='#', level='word', at=4, features={'level': 'word', 'href': 'Word', 'class': 'separator'})
Boundary(text='.', level='syllable', at=7, features={'level': 'syllable', ...})
```

A caller reading `Form.boundaries` is told there is a word boundary inside *cats*. `Unit.level` already answers `None` correctly for the same mark; `Boundary.level` should be `str | None` and agree with it. `Boundary.features` carries `morph` either way, so nothing is lost by telling the truth.

## 5. The plural, worked

Underlying `/kæt+z/`, `/dɔɡ+z/`, `/bʌs+z/`, in ipakit's notation, run against the prototype:

```
∅ -> ɪ / [sibilant] + _ z ; plural epenthesis
z -> s / [voiced=-] + _ ; plural devoicing
+ -> ∅ ; boundary erasure
```

```
  erasure as the last rule:
    kæt+z        -> 'kæts'
    dɔɡ+z        -> 'dɔɡz'
    bʌs+z        -> 'bʌsɪz'
    bʌz+z        -> 'bʌzɪz'
    bɹɪd͡ʒ+z     -> 'bɹɪd͡ʒɪz'
    t͡ʃɜt͡ʃ+z    -> 't͡ʃɜt͡ʃɪz'
    ɡəɹɑʒ+z      -> 'ɡəɹɑʒɪz'
```

Three lines, seven right answers, every operator in them already there.

**`[sibilant]` is the finding.** The brief's expectation, following [captures.md](captures.md), was that epenthesis wants a brace over {s z ʃ ʒ t͡ʃ d͡ʒ} and would join the queue behind SPE's braces. It does not. `ipa.xml` declares `alias="sibilant"` on `channel="grooved"`, and the value selects `s z ɕ ʂ ʃ ʐ ʑ ʒ t͡s d͡z t͡ʃ d͡ʒ t͡ɕ d͡ʑ`. Restricted to an English inventory that is the six the rule wants, affricates included, and the affricates come for free because the tied units inherit `channel` through composition rather than declaring it. The surplus is eight grooved obstruents English does not have. There is no query that picks the English six and nothing else — and no need for one, because a rule set for English is applied to English.

The literature agrees on the class and disagrees on the features. Hayes uses `[+strident]`, defined so that only coronal fricatives and affricates can be [+strident], with a footnote rejecting a wider reading because it would predict \**cuff* → \*[ˈkʌfvz]. Levine uses `[coronal +, strident +]` and argues that [strident] alone over-generates to the labiodentals. ipakit's `channel="grooved"` is that same class cut on the aerodynamics — *in: concentrated central jet*, per the value's own comment — and it lands in the same place without needing two features to get there. **No source states the rule with braces**; the six-segment list appears only in prose glossing what the natural class picks out, and the flat objection to curly brackets is Odden's — *"a powerful device that undermines the central claim that rules operate in terms of natural classes"* (2005: 159). Hayes reports the objection rather than holding it — *"Many linguists have expressed the view…"* (2009: 259) — and teaches the notation at p. 220, offering it and writing two rules as interchangeable.

**Order matters, and it is not the boundary's doing.** Epenthesis must precede devoicing: run the other way, /s/ devoices the suffix and `[sibilant] _ z` no longer holds, giving \*`bʌss`. That is ordinary feeding and bleeding, unanimous in the sources, and ipakit's cascade already carries it with `Derivation` to show it.

**What the boundary buys is not the three right answers.** With the suffix simply concatenated and no seam at all, `∅ -> ɪ / [sibilant] _ z` and `z -> s / [voiced=-] _` give `kæts`, `dɔɡz`, `bʌsɪz` on the shipped inventory today. They give them because English has no tautomorphemic voiceless-obstruent-plus-/z/ for the rule to trip over — a phonotactic gap that the morphology is itself the explanation of. Written that way the rules are claims about every /z/ in the language, and the difference shows the moment somebody types a syllable dot:

```
form           boundary-less set    the same set with +
  bʌs.zoʊn       'bʌsɪ.zoʊn'          'bʌs.zoʊn'
  bʌszoʊn        'bʌsɪzoʊn'           'bʌszoʊn'
  kæt.zoʊn       'kæt.soʊn'           'kæt.zoʊn'
```

*Bus zone* gets an epenthetic vowel and *cat zone* gets devoicing, because the dot is transparent and there is nothing else in the rule to stop it. So the seam earns its place three ways, and none of them is "the rules cannot be written":

- the **underlying form** is writable as the analysis states it, which is the form an exercise has to hand a student;
- a rule that is morphologically conditioned can **say so**, and one that says so cannot fire in *bus zone*;
- the **segmentation survives the derivation** and is recoverable from the output, which is what `Form.boundaries` is for.

## 6. One boundary — and the objection that the field abandoned this one

*SPE* distinguishes the formative boundary from the word boundary, and lexical phonology distinguishes stem-level from word-level affixation: the *compar+able* against *comparable#ness* case, and its sharper English form, *in+possible* assimilating to [ɪmpɒsɪbl̩] where *un#popular* does not, on the same /n/ before the same /p/.

**The objection has to come first, because it is real.** `+` did not survive as a theoretical device. Its work was reassigned to strata in Lexical Phonology, and the reassignment was argued, not drifted into. Kiparsky 1982 grants that the stratal cut *"coincides entirely with the familiar distinction between the '+ boundary' and the '# boundary' affixes… but it in fact has deeper roots in the morphological system"*. Newell 2021 puts the complaint plainly: there is *"nothing inherent in the SPE diacritic '+' that indicates 'Level 1' phonological behaviour"*. And Bermúdez-Otero 2013 §28 uses it as the reductio — conceding of a rival proposal, *"But §26 is basically a retreat to SPE's theory of boundary symbols!"*

**All three objections are to the same second job, and ipakit's `+` does not take it.** The complaint is not that a representation should not record where a morpheme ends. It is that a *diacritic on the boundary* should not be what predicts stratal behavior, because the diacritic is unmotivated — a label that has to be stipulated per affix and explains nothing. What ipakit's `+` records is **where the seam is**, and that is the first job, which no one abandoned: Levine writes `/kæt+z/`, Odden writes `/kæt-z/`, Hayes writes the hyphen in the morphology row of his own derivation table. Every textbook statement of the plural puts the seam in the underlying form. What none of them does is name it in a rule, and what none of them does is give it a strength.

So: **one value, and the tier is nominal.** If a second morphological boundary is ever wanted it gets its own glyph and its own value, matched exactly, with no reaching between them — which is *SPE*'s own shape, two binary features rather than a scale. The graded reading is the one to refuse, and refusing it is what a nominal tier does by construction.

**And the stratal distinction is already expressible, without a second mark.** It is a fact about *when in the derivation* an affix attaches, and ipakit is already an ordered cascade. [calculus.md](../calculus.md) proves composition is concatenation of rule sets and that it is associative, so *run the stem-level rules, attach the word-level affixes, run the word-level rules* is two rule sets and a concatenation. That is the stratal answer, in the engine, today.

The alternative is worse in a way worth showing. Spelling *unpopular* `ʌn#pɒpjʊlə` gets the assimilation right —

```
  in+possible against un#popular, one rule:
    morph above syllable   ɪn+pɒsɪbl->'ɪm+pɒsɪbl' (1)  ʌn#pɒpjʊlə->'ʌm#pɒpjʊlə' (1)
    a tier of its own      ɪn+pɒsɪbl->'ɪm+pɒsɪbl' (1)  ʌn#pɒpjʊlə->'ʌn#pɒpjʊlə' (0)
```

— and gets it right by saying *unpopular* is two words, which it is not. `#` declares `level="word"`, `Form.tree` splits on it, `edge_tier` is `word`: the spelling makes a false prosodic claim in order to record a true morphological one. Which is the non-isomorphism again, in the other direction, and exactly what a graded morph tier would exist to avoid.

## 7. Erasure is the last rule, not the surface

A morph boundary is present in the input and absent from a pronunciation, which is the zero's shape exactly. [calculus.md](../calculus.md) argues at length that the zero is removed by a *rule*, `[zero] -> ∅`, rather than by a fourth `Form` projection, so that the operations stay closed over the carrier — and `surface()` runs it after every rule of the cascade, with `keep_zeros=True` to decline.

**Same mechanism, different placement, and the difference is measurable.**

```
  erasure as the last rule:      kæt+z -> 'kæts'   dɔɡ+z -> 'dɔɡz'   bʌs+z -> 'bʌsɪz'
  erasure after every rule:      kæt+z -> 'kætz'   dɔɡ+z -> 'dɔɡz'   bʌs+z -> 'bʌsɪz'
  no erasure:                    kæt+z -> 'kæt+s'  dɔɡ+z -> 'dɔɡ+z'  bʌs+z -> 'bʌs+ɪz'
```

Erase after every rule and *cats* comes out `kætz`. Devoicing names `+` in its context; epenthesis ran first, erasure removed the seam, and by the time devoicing looked there was nothing to condition on. *Buses* survives only because epenthesis had already fired and devoicing had nothing left to do.

The zero can be stripped that way because **the engine writes it**. `z -> [zero]` is a rule's own record of where a segment was, so no *later* rule was written expecting to find it; erasing it per step loses nothing a rule set declared. A morph boundary is the opposite: the *caller* writes it, in the input, and the rules are written against it. Erasing it between rules erases the environment the rule set is about.

That settles the composition question. It does not fight the existing surface rewrite; it does not go near it. `surface()` stays `[zero] -> ∅`, and a rule set that wants the seam gone ends with `+ -> ∅ ; boundary erasure` — one more element of the same algebra, declinable by leaving it off, which is what an exercise that wants to *show* the seam surviving will do.

**Leaving it on the surface is not obviously wrong either.** `#` survives: `rewrite("#pɪn", "p -> pʰ / . _")` gives `#pʰɪn`, and nobody thinks the output is mispronounced. The consistent default is that a boundary the caller wrote survives unless a rule removes it, and the reason to remove `+` in particular is that a word boundary has an acoustic correlate and a formative boundary does not. Hayes flags the same question as open on the theory side, asking whether morphological brackets are erased before the phonology at all; a library that makes the erasure a visible rule lets a reader take either side, and take it per rule set rather than once for everyone.

## 8. The metric

Nothing moves. The measurement is the argument, so here it is with the enumeration `sweep.py` defines:

```
7. the metric
  morph below syllable           units 8616->8616  bundles moved    0  d_from_base moved    0  pairs moved 0/9591
  morph above syllable           units 8616->8616  bundles moved    0  d_from_base moved    0  pairs moved 0/9591
  a tier of its own              units 8616->8616  bundles moved    0  d_from_base moved    0  pairs moved 0/9591
    same, additive default       units 8616->8616  bundles moved    0  d_from_base moved    0  pairs moved 0/9591
    structural, on a diacritic   units 8616->8477  bundles moved    0  d_from_base moved    0  pairs moved 0/9591
    additive, on a diacritic     units 8616->8616  bundles moved  131  d_from_base moved  139  pairs moved 0/9591
```

The first three rows are the answer to the brief's question and they are all zero, including the full pairwise matrix over the registered phones that `confusion.json` is derived from. `scripts/invariants.py`'s four metric checks pass against the tier unchanged.

**The fourth, fifth and sixth rows are why the answer is not "a boundary is free".** The `<notations>` comment records a key that looked harmless landing in a bundle and moving 37 distances, and asks that this be checked rather than assumed. Checked: the fourth row says that with `+` as a separator, `mode="structural"` versus the additive default makes no difference *today*, because no phone and no diacritic declares `morph`. The sixth row says what happens the day one does — give the aspiration mark `morph="formative"` under the additive default and the key lands in 131 unit bundles and moves 139 units' distance from their base.

So the mode is insurance, and it is the same insurance the `level` feature's comment describes taking for the same reason: *it fell to the additive default while no diacritic declared a level, so nothing showed; once `|` does, additive would offer a mark that adds an ordinal `level` to a base*. The stated reason for `mode="structural"` and the operative reason differ, and the operative one is about the next declaration rather than this one.

The fifth row is the argument for `<separators>` over `<suprasegmentals>` restated as a number: a structural key on a *diacritic* takes the corpus from 8,616 to 8,477, because the mark stops being spelled back onto its base. `+` belongs where `.` and `#` are.

## 9. What else it touches

**The not-a-bracketing: neither better nor worse, and right for the right reason.** [form.md](../form.md) argues that boundaries are atomic separators rather than a Dyck word, and that `#kæt#`, `kæt` and `#kæt` give identical trees. Adding `+` does not disturb that and does not extend it — the tier is not on the ladder, so `Form.tree` never splits on it:

```
  tree('kæt+s')=Node(form, 1 children, 'kæts')  tree('kæts')=Node(form, 1 children, 'kæts')
  phones('kæt+s')='kæts'   rebuild='kæt+s#dɔɡ.z'
```

*Cats* is one syllable and the tree says so. The morphological constituency is simply not in the prosodic tree, which is the correct answer rather than a limitation, and it is what indirect reference predicts. The units carry the seam and round-trip it, which is where it belongs — the same division form.md already draws for enchaînement, where `Form.units` reads `pə.ti.t‿a.mi` faithfully and `tree()` is the projection that cannot say it.

**One check goes quiet.** `empty_constituent` is computed over a `levels` map, so a level-less separator is invisible to it:

```
  tier validate_ipa('kæt+s')  []
  tier validate_ipa('kæt++s') []
  tier validate_ipa('##kæt')  ['empty_constituent']
  tier validate_ipa('kæt..s') ['empty_constituent']
```

`kæt++s` is a same-mark run delimiting no segment and it is exactly what the check exists to report. The fix is to key the check on "the same declared boundary" rather than "the same declared level"; a single-value nominal tier makes those the same question anyway.

**And one answer goes silently wrong if the `<notations>` edit is forgotten.** `is_pure_ipa("kæt+s")` returns `True`, because `notation_of` answers `chart` for anything not listed. `check_notation` in `scripts/invariants.py` passes anyway, because it compares the listed set against a hardcoded `NON_CHART = {'␣', '#', '∅'}` — so the invariant that exists to catch an unmarked extension cannot catch this one. That is not a reason to distrust the invariant; it is a reason for the two edits to be one commit.

**Enchaînement is the neighbor, not the same case.** `‿` declares `level="word"` and `linking="+"`, and it is where a word boundary and a syllable margin come apart: `pə.ti.t‿a.mi` has four syllables and `tree()` reports five, because `word` splits before `syllable` and the syllable `ta` straddles the division. That is a mismatch between two *prosodic* tiers, and form.md's answer is that the honest model is autosegmental. A morpheme boundary is a mismatch between the prosodic hierarchy and a different representation entirely, and it does not need the autosegmental repair: a tier of its own is enough precisely because nothing is being asked to contain anything. Adding `+` neither helps enchaînement nor is helped by it — they are the same lesson about two different pairs of tiers, which is why the linking mark is worth citing in the documentation of `morph`.

**X-SAMPA.** `xsampa.xml` maps `#` to `#` and `.` to `.`; X-SAMPA has `_+` for the advanced diacritic and leaves a bare `+` unassigned, so `<map ipa="+" xsampa="+"/>` is free and is the same house extension `#` already is.

## 10. What it buys: an assignable exercise set

Classroom material is the standing goal and there is nothing to assign. English plural allomorphy is the first-week exercise in every introductory course, and the reason it cannot be *set* today is not that the answers come out wrong — §5 shows they do not — but that the student cannot write down the input. The analysis posits /kæt/ + /z/; the library accepts `kætz`, which is a different claim, and the seam is the whole point.

With `+` there is a shape for a set of exercises, and it is one the library already supports end to end — `ruleset`, `Derivation`, `variants`, and the CLI.

**Exercise 1, the plural.** Give the data as surface forms — *cats, dogs, buses, churches, bridges, garages* — and the underlying forms with the seam written. Ask for two rules and their order. The library grades it: the rule set is three lines of text, `apply` gives the surface, `Derivation` shows which rule fired where. The interesting half is not getting *buses* right; it is discovering that the other order gives \*`bʌss` and being able to see why.

**Exercise 2, the same analysis on the past tense.** */wɒnt+d/*, */lʌv+d/*, */kɪs+d/*. The structure is identical, the epenthesis environment is a different class, and the point is that one analysis transfers. It also exposes the class question honestly: `[sibilant]` was waiting in the inventory for the plural, and the past tense needs `[place=alveolar manner=plosive]`, which is a query the student writes rather than a name they look up.

**Exercise 3, what the boundary is for.** Give the boundary-less rules and the form `bʌs.zoʊn`, and ask why the answer is wrong. This cannot be set at all today, and it is the one that teaches what a morpheme boundary *is* — not by definition, but by a rule misfiring somewhere the student can see.

**Exercise 4, transparency.** Ask whether `kætz` and `kæt+z` should derive the same pronunciation, then check. The answer is yes, it is *SPE*'s stated convention, and it is a property of the engine the student can test rather than be told — §3 is that question asked 486 times.

**Exercise 5, erasure.** Run the set with and without the final `+ -> ∅` and read the intermediate forms. The seam surviving the derivation and being removed at the end is the derivational-versus-surface distinction the library already makes for the zero, arriving where a first-year student has an intuition about it.

None of these needs a new API. What they need is the seam, a `docs/examples/` home for the rule sets, and the words with their segmentations — which is data, and small.

## 11. What it would take, in order

**(a) The four clauses, first, and in the same commit as the data.** `_pattern`'s level-less branch, `Unit.transparent`, `%`'s declared-level condition, and `Boundary.level` becoming `str | None`. None is optional: without the first the notation parses and does nothing; without the second a quarter of the seam positions in the shipped corpus change the derivation; without the third every `%` rule silently widens; without the fourth `Form.boundaries` reports a word boundary inside *cats*. The declaration alone is the broken state.

**(b) The `<notations>` entry and `NON_CHART`, in that same commit.** For the reason §9 gives: the invariant cannot catch the omission, so nothing else will.

**(c) The transparency sweep as a test.** §3 is the boundary-run invariant asked of a new mark, and it should be a test rather than a paragraph — `r(f) == strip(r(f with a seam at i))` over the shipped corpora, which is the shape `tests/test_rule_sets.py` already has the corpus for. It is the check that would have caught the opaque default, and the check that will catch the next mark declared without a level.

**(d) `empty_constituent` keyed on the mark rather than the level.** Small, and it restores the one warning the doubled seam would otherwise lose.

**(e) The shipped rule set and the exercises.** `english-plural.rules` beside the five already there, and §10's five exercises. This is the deliverable; everything above it is the cost of admission.

**(f) Documentation.** `docs/rules.md` gains the seam beside `#` and `.`, with the transparency rule restated as *a boundary that is not a prosodic edge is transparent* and the `dɔɡ+z → dɔk+s` measurement as the reason it is not on the ladder; `docs/form.md` gains a line under *why boundaries are atomic separators* saying the morph tier is a second reason the tree is a narrower read than the units; `docs/calculus.md`'s surface-projection section gains the erasure-placement result, because it is the sharpest available illustration of why the zero's treatment is the zero's and not a general rule about marks that vanish.

**Not needed: braces, captures, or anything else from [captures.md](captures.md).** Measured, not assumed. The two lanes' recommendations are independent and either can ship first.

## 12. What it costs to be wrong

**If the tier is wrong and the ladder was right**, the cost is a data edit — move `morph` from its own feature to a value of `level` — plus deleting one clause from `_pattern`. Nothing outside `ipa.xml` and `rules.py` encodes the choice, because `_reaches`, `form.tiers` and `edge_tier` all read the declaration. That is cheap in exactly the way the read-rather-than-restate rule is supposed to make things cheap.

**If transparency is wrong**, the cost is high and the failure is loud, which is the good direction. A transparent seam that should have been opaque means a rule fires across a boundary it should have respected — and the caller can see it, because they wrote the seam and can name it in the rule. The opaque version fails the other way: writing the seam silently changes what an unrelated rule set does, in 122 of 486 places, with nothing in the input suggesting it should. Between a rule that has to be made explicit and a derivation that changes because of a mark nobody's rule mentioned, take the first.

**If one boundary is wrong and a second is needed**, the cost is a second value and a second glyph, matched exactly like the first. *SPE*'s `=` is unclaimed and is the historically correct one. Because the tier is nominal there is no ordering to get wrong and no `_reaches` to teach, so the separate-tier decision does not have to be revisited. This is the cheapest of the four to be wrong about, which is the reason to start with one.

**If erasure should have been automatic**, the cost is that every rule set wanting the seam gone writes one line. That is the mistake worth making in this direction: a rule set that forgets `+ -> ∅` returns `kæt+s`, which is visibly odd and which the caller wrote the input for, where the automatic version returns `kætz` — a well-formed wrong answer with nothing to notice it by.

**The expensive mistake is the one this document exists to avoid**, and it is worth stating plainly because it is the attractive one. `<value name="morpheme"/>` in the `level` ladder is a three-word edit, needs no Python at all, makes every existing rule and check pass, validates against the grammar, leaves the metric byte-identical, and quietly devoices the stem of every German plural anybody writes the seam into. Nothing in the repository would report it. The separate tier costs four clauses and does not.

## Spin-off finding: *SPE* is reachable, and open access

*The Sound Pattern of English* is open access on Fulcrum, the University of Michigan Press platform, as a 484-page PDF:

```
https://www.fulcrum.org/concern/monographs/2z10wq58b            landing page
https://www.fulcrum.org/ebooks/ms35tc39t/download?locale=en     PDF, 54 MB
```

Fulcrum is the route, and it is worth naming because the obvious ones are dead ends: archive.org's copy is borrow-restricted and the usual mirrors fail, so a search that starts there concludes the book cannot be read and settles for secondary reports of it. Every *SPE* claim in the present document was read from the PDF, including the boundary feature analysis in §1 and the transparency convention in §3, neither of which is the kind of detail a secondary source reports precisely enough to build on.

## Reproducing the measurements

Every figure here was taken with `PYTHONHASHSEED=0` against this worktree, reading the library only. The prototypes are copies of `ipakit/data/ipa.xml` written to a temp directory and loaded with `IPAFeatures(xml_path=...)`; nothing was written into the tree.

The corpus is `scripts/sweep.py`'s, taken through `sweep.take_capture` against each prototype rather than through a hand-rolled enumeration, for the reason `review-state.md` gives. The pairwise figure is the full matrix over the registered phones — `itertools.combinations(sorted(features.phones), 2)` — which is the same set of pairs `confusion.json` is derived from, so a zero there is a zero in the shipped matrix.

The transparency sweep in §3 uses `tests/test_rule_sets.py`'s `CORPUS`, imported rather than retyped. A seam position is any index between two characters where neither neighbor is already a boundary or a space and where `Form.parse(probe).to_ipa() == probe`, so a seam inside a tie bar or a diacritic sequence is not counted. The comparison strips the seam from the output before comparing, which is what makes it the boundary-run invariant rather than a stricter one: an insertion may legitimately land on either side of a transparent mark, and only the pronunciation has to agree.

The four clauses are measured by monkeypatching in the throwaway script, since the point is what one clause would do and not what the shipped engine does. Every line reported under "with the clause" was produced by running it. The rule sets in §5 are parsed from the source shown, and `[sibilant]`'s membership is read from `phones_matching({'channel': 'grooved'})` rather than typed out.

The shipped rule set in §2 is `R.shipped("german-final-devoicing", features)` applied with the same `features` passed again to `apply`. Passing a prototype inventory to `shipped` and then letting `apply` fall back to the default silently drops the `+` and returns something that looks like the right answer — worth knowing about the API, and the reason the reproduction passes `features` twice.
