# Interoperating with the transcription ecosystem: assessment

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

Should ipakit interoperate with CLTS/BIPA, the speech-technology stack, external inventories and PanPhon — in which direction, and at what cost?

**Verdict: CONSUME FREELY, EMIT ALMOST NOTHING, AND SHIP NO MAPPING TABLE AT ALL.** The brief expected a BIPA phonemap in the shape of `xsampa.xml` and a PanPhon emitter on the same terms. Neither survives measurement, and both fail for the same reason: **a mapping table has to be a bijection, and ipakit's segment set is finer than either target's in a dimension it cannot give up.** BIPA deletes both tie bars — 0 of its 8,765 graphemes contain one, and both normalize to the empty string — so `ts`, `t͡s` and `t͜s` are one BIPA sound with one name, where ipakit reads two segments, one segment, and a different one segment. 275 ipakit spellings are claimed by more than one BIPA grapheme. The relation is not a function, and no amount of care makes it one.

What is worth having is the opposite of a table: **a documented two-step read of foreign convention, which the library already implements.** `normalize_lookalikes` followed by `add_ties` moves BIPA agreement from 6,142 to 8,075 of 8,765 — from 70% to 92% — with no new code and no new data. The residue is not a long tail. It is a handful of inventory gaps and one parser defect, listed in §1.

The single most valuable output of this lane is not an interop verdict at all. It is that measuring against outside systems exposed **a silent wrong answer under `strict=True`**: `ipakit.segments("ⁿd", strict=True)` returns one segment spelling `d`, with no warning and no exception. `features("ⁿd")` is `{}` and `distance("ⁿd", "d")` is `0.0`. Swept over the whole diacritic table, **64 of 68 registered marks vanish this way**. Every external source measured here reaches it. That is §12(a), and it is the shape [reviewing.md](../reviewing.md) exists to catch.

The second most valuable is a correction to the question. The brief, and this document's own first draft, asked how many segments ipakit **refuses**. Over PHOIBLE's 3,142 that is 6.5%, and every one of them is loud and safe. The number that matters is the **43.8% ipakit accepts and silently reads as two segments** — 81% of the world's documented inventories load, and 11% load without a segment count changing underneath. For a phonetic layer under a model pipeline that is the whole story, and it is invisible to a refusal count.

And the cheapest item is not code at all. Across `docs/` and `README.md`, espeak, phonemizer, gruut, Festival, Festvox, Flite, CMUdict and "text-to-speech" appear **zero times**. The library already has the pieces a speech-technology practitioner needs — `from_cmu`/`to_cmu` round-trip CMUdict at 99.977%, X-SAMPA round-trips byte-identical, Kirshenbaum reads espeak's own ASCII — and says nothing to them. §7.

The assessment is read-only on the library. Nothing here changed `ipakit/`, `ipakit/data/`, or any test.

## Summary of findings

| Question | Finding |
|---|---|
| Do ipakit and BIPA agree where a segment begins? | **6,142 of 8,765 as shipped; 8,075 under two normalizations ipakit already has.** The gain is one function call, not a project. |
| Is the residue systematic or a long tail? | **Systematic.** 385 refusals over ~10 symbol classes, 305 resegmentations of which 293 are one `add_ties` limitation. |
| Do the two feature models say the same things? | **35,313 assertions agree, 824 disagree, 451 ipakit is silent on, 966 it cannot express.** The disagreements fall into six named classes. |
| Is "ipakit resolves, CLTS records base + modifier" true? | **No — each resolves different features, in both directions.** Any mapping has to be per-feature. |
| Does a BIPA phonemap fit `xsampa.xml`'s shape? | **No. The relation is not a bijection: 275 collisions**, and 8 of the top classes are ipakit dropping a symbol it should not. |
| Is CLTS only a catalog and normalizer? | **Mostly, but the brief named the wrong gaps.** It has a similarity and it has sound classes. It has **no tokenizer at all**. |
| Is CLTS's similarity a metric? | **No. 23 distinct values over 9,316 pairs**, against ipakit's 3,025; nearest neighbor agrees on 22 of 137 phones. |
| Could ipakit derive SCA / DOLGO / ASJP from its declarations? | **No: 2 of 12 DOLGO classes re-extend exactly.** They are historical judgments, so shipping them means a hand-maintained table. |
| Does BIPA preserve the tie distinction? | **No. It deletes it.** Both tie bars normalize to the empty string; `t͡s` and `t͜s` are the same BIPA sound. |
| Should ipakit consume Lexibank/CLDF corpora? | **No.** 191 repositories, ~2 GB, 28 with unclear licensing — and every word arrives normalized through BIPA, so it arrives with the ties already deleted. |
| Did the measurement expose an ipakit defect? | **Yes, nine.** The largest: **64 of 68 registered diacritics are silently dropped** when a source writes them before the base. §12(a). |
| Can a practitioner do real pronunciation-lexicon work today? | **Yes, at 99.977% over CMUdict** — but 31 entries are silently wrong because `to_cmu` and `segments` tokenize differently, and `to_cmu` rejects the tie glyph the safest TTS setting emits. §7. |
| Which speech tool is the worst partner? | **The one that never refuses.** gruut raises on 0 of 47 words and silently damages 30. espeak and phonemizer each become clean with one setting. |
| Which number should an interop effort be judged on? | **Not refusals.** PHOIBLE: 6.5% refused and loud, **43.8% silently resegmented**; per inventory, 81% accepted against 11% correctly segmented. |
| Is Epitran interop free? | **Almost: 98.3% of 8,463 outputs parse, 0 ties broken.** But the obvious recovery step silently turns ejectives into stress marks in four languages. §8. |
| Is PHOIBLE a sub-case of CLTS? | **No: CLTS rescues 34 of the 203 refusals (17%)**, because both spell the missing diacritics identically. |
| Should ipakit emit PanPhon feature vectors? | **Measure, do not ship.** 95.3% of cells agree but only 33.8% of segments agree on all 24, and there is no ground truth to check a shipped table against. |
| Is there a capability worth building whatever the interop verdict? | **Yes: a derived sonority scale** (ρ = 0.938 against PanPhon, from declarations alone) and a numeric vector export. §11. |

## 0. What the two systems are, measured rather than assumed

The brief's hypothesis was that CLTS is "a catalog and normalizer where ipakit is a computation toolkit — no rule engine, no distance metric, no articulatory rendering, no teaching narrative", and asked for it to be broken. It survives, but **two of the four named gaps are wrong**, and getting them right changes what is worth building.

**CLTS has a distance facility.** `Sound.similarity` is an unweighted Jaccard over the set of feature-value *names*, and `Inventory.strict_similarity` / `approximate_similarity` lift it to whole inventories with a greedy best-match alignment. So "no distance metric" is false as stated. What is true is sharper and more useful:

```
registered ipakit phones BIPA also resolves: 137
pairs: 9316
  distinct ipakit distances:        3025
  distinct CLTS similarities:         23
  Spearman rho:                   0.6771
  nearest neighbor agrees on:         22 of 137
```

Twenty-three distinct values over nine thousand pairs is not a resolution problem, it is a different kind of object. Two sounds are as similar as the words they share, so CLTS has no way to say that alveolar and postalveolar are adjacent while alveolar and glottal are not — every value name is an independent set member. The largest rank disagreements are all of one shape:

```
  ǁ    t͡ɬ   ipakit 0.6922 (rank  7596)   CLTS 0.3333 (rank    34)
  l    d͡ɮ   ipakit 0.6800 (rank  7230)   CLTS 0.3333 (rank    17)
```

CLTS calls a lateral click and a lateral affricate near-identical because both are `voiceless lateral consonant`; ipakit puts them far apart because one is velaric and one is pulmonic. Neither is wrong for its purpose — CLTS's similarity exists to match inventories across datasets, not to rank an inventory internally — but they are not substitutes, and the one that ranks is ipakit's.

**CLTS has sound classes**, which the brief did not name at all: SCA, DOLGO, ASJP, CV, plus `art` and `color`. These are the reductions cognate detection and historical work run on, and they are course material. §5 measures whether ipakit could derive them. It cannot.

**CLTS has no tokenizer.** This is the gap the brief missed and it is the largest one. `bipa["tsa"]` returns `UnknownSound`; `normalize` is a per-character substitution table. CLTS resolves graphemes that something upstream already segmented — in practice `lingpy` or the dataset author. ipakit's `segments` is a segmentation. For anything reading a running transcription rather than a curated grapheme list, that is not a feature difference, it is the difference between having a front end and not.

**Nothing in the symbolic stack represents a tract.** Checked directly: `pyclts.ipachart` draws the IPA chart as a table and a vowel trapezoid; every occurrence of "articulatory" in PanPhon is the adjective, describing features. Neither has constrictions, tract variables, or a sagittal geometry. Where ipakit renders an articulation, the ecosystem stops at a label. That is a real differentiator for work on articulatory representation, it is outside this lane's scope, and it wants an assessment of its own.

## 1. Segmentation agreement is the spine

**Superseded by [#118](https://github.com/lenzo-ka/ipakit/pull/118): the counts below were taken against a library that has since had §12(a), (b), (d) and (e) fixed, and (b) is the one that reaches this measurement. §12(b) predicts where it lands — roughly 8,368 of 8,765 — and re-deriving it needs a CLTS clone mounted, so the prediction is what stands here until somebody runs `scripts/interop.py` against one.**

Nothing downstream matters if the two systems disagree about where a segment begins, and for a phonetic layer under a model pipeline that agreement *is* the product: a tokenizer that splits where the ecosystem does not changes token counts, alignments and vector counts under everything downstream.

The corpus is BIPA's own sound table, `data/sounds.tsv` — 8,765 resolved sounds, generated and explicit alike. Every one is bucketed three ways, exhaustively: `agree` (ipakit reads one segment, as CLTS reads one sound), `differ` (ipakit reads two or more), `refuse` (ipakit will not read it).

```
                           agree  differ  refuse
raw BIPA spelling           6142    1999     624
+ normalize_lookalikes      6210    2170     385
+ add_ties (both)           8075     305     385
```

**The whole gain is two function calls that already exist**, and it is worth being precise about why each is needed, because both are convention rather than model.

`normalize_lookalikes` closes 239 refusals in one row: BIPA canonicalizes the voiced velar plosive as ASCII `g` (U+0067) and ipakit as script `ɡ` (U+0261) — and the two projects normalize in *opposite directions*, BIPA mapping U+0261 to U+0067 and `lookalikes.xml` mapping U+0067 to U+0261. Both are defensible; neither is a claim about a sound.

`add_ties` closes 1,865, and that is the tie question of §3 in its practical form: BIPA writes every affricate, every diphthong and every cluster untied, so ipakit reads each as two segments until a tie is supplied.

### The residue is short and it is a list of decisions

```
under both normalizations, by CLTS type:
  consonant   agree  5976  differ   31  refuse  237
  vowel       agree  1662  differ    0  refuse   12
  diphthong   agree   384  differ  262  refuse    0
  tone        agree     0  differ    0  refuse  132
  cluster     agree    53  differ   12  refuse    4
```

Every vowel that is not refused agrees. Every tone is refused, for one reason: BIPA spells tone as Chao digits (`⁵⁵`, `²¹⁴`) and ipakit as tone bars, and neither is wrong. The refusals name their own classes:

```
     59  '⁴' U+2074 SUPERSCRIPT FOUR
     59  '³' U+00B3 SUPERSCRIPT THREE
     59  '⁵' U+2075 SUPERSCRIPT FIVE
     58  '²' U+00B2 SUPERSCRIPT TWO
     58  '¹' U+00B9 SUPERSCRIPT ONE
     45  '͈' U+0348 COMBINING DOUBLE VERTICAL LINE BELOW
     35  '̫' U+032B COMBINING INVERTED DOUBLE ARCH BELOW
     34  'ʳ' U+02B3 MODIFIER LETTER SMALL R
     33  '͓' U+0353 COMBINING X BELOW
     24  '͉' U+0349 COMBINING LEFT ANGLE BELOW
     22  '̊' U+030A COMBINING RING ABOVE
     19  'ˢ' U+02E2 MODIFIER LETTER SMALL S
```

Counted per unknown symbol rather than per refused sound, so a sound missing two appears under both and the column deliberately sums high.

Three of these are decisions worth taking on their own merits, independent of any interop verdict:

- **U+030A COMBINING RING ABOVE** is the IPA's own voiceless diacritic for symbols with a descender — `ŋ̊`, `ɣ̊` — and ipakit declares only the ring below. It is not in `lookalikes.xml` either, so `features("ŋ̊")` is `{}` with a warning while `features("ŋ̥")` is a full bundle. This is the same glyph pair the IPA chart prints side by side, and it should be a row in the inventory rather than a gap.
- **The Chao tone digits** are the dominant convention in Sinitic and Southeast Asian description and in every corpus normalized through BIPA. Whether they belong in `ipa.xml` or in a phonemap is a real question; that they are absent from both is the finding.
- **`ʳ`, `ˢ`, `ʶ`** are release modifiers of exactly the shape ipakit already declares for `ʰ`, `ˡ` and `ⁿ`. 59 sounds, and the mechanism is there.

The rest — `͈` fortis, `͉` lenis, `͓` frictionalized, `̫` — are extIPA and near-extIPA, which is a scope question rather than an oversight.

### The resegmentations are one defect, not a disagreement

```
resegmentations (CLTS one sound, ipakit more than one):
    262  diphthong   e.g. e̞a e̞ɪ e̞ə e̞i e̞o̞ e̞u
     31  consonant   e.g. ŋ̥m̥ d̪ɮ d̪ɮˠ d̪ɮˠː d̪ɮˠʰ ˀd̪ɮ
     12  cluster     e.g. t̠pⁿ t̠p t̠pʲ t̪ʼkxʼ pʼkxʼ tʼkxʼ
```

Every example shares a shape, and it is not a model difference:

```python
>>> ipakit.add_ties("dɮ")     # 'd͡ɮ'
>>> ipakit.add_ties("d̪ɮ")    # 'd̪ɮ'   -- unchanged, silently
>>> ipakit.add_ties("ea")     # 'e͜a'
>>> ipakit.add_ties("e̞a")    # 'e̞a'   -- unchanged, silently
```

A diacritic on the first element blocks the tie, and `add_ties` returns its input with no warning and nothing in its docstring saying it can decline. The same function fails the other way on a whole word:

```python
>>> ipakit.add_ties("tʃˈeɪndʒ")   # 't͡ʃˈe͜ɪ͡n͡d͡ʒ'
```

`n`, `d` and `ʒ` are joined into one unit. The docstring says "in a multi-phone segment"; the function takes a word without complaint, and a word is the first thing a caller reaches for after seeing untied output from a front end. So it declines where it should act and acts where it should decline, both silently. **That one limitation accounts for 293 of the 305 resegmentations.** Fixing it would take BIPA agreement to about 8,368 of 8,765 with no change to the model at all — see §12.

## 2. The feature models mostly agree, and where they do not it is legible

Both systems describe a sound as an attribute-value bundle, so the comparison is direct: for every BIPA consonant and vowel that both read as one segment, take each feature value CLTS asserts and ask what ipakit says about the same thing.

The correspondence between the two vocabularies is curated, for the reason `xsampa_table.OVERRIDES` is: no rule derives one project's word for a thing from another project's word for it. What is **not** curated is either side's values — every ipakit target is checked against the declarations before the comparison runs, so a rename in `ipa.xml` breaks the table loudly instead of scoring every segment as a disagreement, and a CLTS value in neither the correspondence nor the excluded list is a hard error rather than a silent omission.

```
segments both systems read as one: 7638
CLTS assertions ipakit can express: 36588   agree 35313   differ 824   ipakit silent 451
CLTS assertions ipakit declares nothing for: 966
```

97.7% of expressible assertions agree. The 824 that do not are six classes, not a tail.

**(a) Base versus resolved — 358 assertions, and it runs both ways.** CLTS records `d̥` as `voiced` plus a separate `devoiced`; ipakit's `voiced` records the *result*, so it says `-`. That looks like a clean structural difference — CLTS states the base and its modifiers, ipakit states the outcome — and it is the account a reader would reach for. **It is wrong**, because the same measurement finds the opposite in the same corpus:

```
     48  CLTS mid            e̞ ipakit height=close-mid
     26  CLTS post-alveolar  t̠ ipakit place=alveolar
      7  CLTS approximant    ʁ̞ ipakit manner=fricative
```

Here CLTS resolves — lowered `e` *is* mid — and ipakit records the base plus `height-mod`, `fronting`, `raising`. So neither system is consistently one or the other; **they resolve different features**, and any mapping between them has to be written per feature. That is the finding that decides §4: a table that assumed one direction would be wrong about 81 segments and could not be told so by its own tests.

**(b) Clicks, ~180 assertions.** `ǂ` is palatal to CLTS and postalveolar to ipakit; `ǃǃ` is retroflex to CLTS and not retroflex to ipakit; `gʘ` is labial to CLTS and `bilabial^velar` to ipakit. Clicks are the messiest region of both inventories and the disagreements are substantive rather than notational. Worth documenting, not worth resolving by fiat.

**(c) The ejective click — 33 assertions, and it is an ipakit defect.** CLTS says `ǂʼ` is `click` and `ejective`; ipakit's `airstream` is single-valued and answers `velaric`. That much looked like a declared model choice pressed on by outside data. It is worse than that, and the PanPhon measurement found the same 40 segments independently:

```python
>>> ipakit.features("ǂʼ") == ipakit.features("ǂ")   # True
>>> ipakit.distance("ǂʼ", "ǂ")                      # 0.0
```

The ejective mark is not held in second place, it is **discarded**. `airstream` runs in `additive` mode — it adds only what the base leaves unstated — and every click already states `airstream="velaric"`, so `ʼ` has nothing to add and vanishes. `kʼ` works only because a pulmonic base leaves `airstream` unstated. Ejective clicks are contrastive in several Khoisan languages. §12(e).

**(d) `ç` is not a sibilant — 44 assertions, and this one is CLTS's error.** CLTS's data gives the voiceless palatal fricative `airstream=sibilant`; ipakit gives `channel=flat`. The voiceless palatal fricative is not a sibilant under any standard description, and CLTS gets `x`, `ɸ` and `θ` right. This is the counterexample to reading the agreement rate as an ipakit score: some of the 824 are the other system.

**Superseded by [#135](https://github.com/lenzo-ka/ipakit/issues/135), and closed.** The stack is read against the rule `ipa.xml` declares: a `sequence="+"` feature composes across a run of marks, every other feature is single-valued and a second mark stating it is reported, naming what contradicts what. The answer is the first mark's rather than a set, so it is still order-sensitive; what closed is that it is no longer silent and that the read now refuses what `compose_unit` refuses to spell.

**(e) Composition order — 61 assertions, and it is an ipakit defect.** `l̥ˠʱ` is breathy to CLTS and devoiced to ipakit; `ɛ̥̤` is devoiced to CLTS and breathy to ipakit. The cause is that ipakit's answer depends on the order the marks are written in:

```python
>>> ipakit.load_ipa_features().compose_segments("ɛ̥̤")[0][1]["phonation"]  # 'breathy'
>>> ipakit.load_ipa_features().compose_segments("ɛ̤̥")[0][1]["phonation"]  # 'devoiced'
```

CLTS gives one answer for both, because its bundle is a set. This is the order-dependence the composition lane found independently; the cross-check adds that the two orders are both attested in outside data, so it is reachable from real input rather than only from a constructed case.

### What ipakit cannot express at all

```
    192  pre-nasalized
    142  pre-glottalized
    109  ultra-long
     98  laminal
     87  velar-and-bilabial
     87  bilabial-and-alveolar
     86  apical
     49  pre-aspirated
     46  palatal-velar
```

**Superseded by [#131](https://github.com/lenzo-ka/ipakit/issues/131), and closed.** ipakit reads a pre-articulation: a mark before a base states the segment's `approach`, the counterpart of `release`, over the same values.

The **pre-modifier series is 402 assertions** and it is not an exotic corner: prenasalized stops are ordinary across Bantu, Austronesian and Sinitic, and pronunciation lexicons for those languages need them. ipakit had no pre-modifier position, and what it did with one instead is §12's defect. `apical` and `laminal` (184) are a laminality dimension ipakit does not declare. The co-articulated places are ipakit's `^` mechanism meeting CLTS's `X-and-Y`, in orders ipakit does not declare — a data question, not a model one.

## 3. The ties, and why they decide the direction

ipakit reads the tie as structure. BIPA deletes it.

**Superseded by [#151](https://github.com/lenzo-ka/ipakit/issues/151), in one figure only.** `segment_distance` normalized a multi-unit comparison twice, so the `ts` row below reads half of what a current run gives — the untied member is two units against one, and it re-derives at 0.8333. The `t͡s`/`t͜s` row is one unit a side, never reached that normalizer, and stands unchanged, as does everything this section concludes from either.

```
string   codepoints             BIPA reads ipakit reads
ts       0074 0073              ts         2 segment(s) ['t', 's']
t͡s      0074 0361 0073         ts         1 segment(s) ['t͡s']
t͜s      0074 035C 0073         ts         1 segment(s) ['t͜s']
aɪ       0061 026A              aɪ         2 segment(s) ['a', 'ɪ']
a͜ɪ      0061 035C 026A         aɪ         1 segment(s) ['a͜ɪ']

BIPA graphemes containing either tie bar: 0 of 8765
  both tie bars normalize to the empty string:  U+0361 -> ''  U+035C -> ''
  BIPA 'ts' and 't͡s' same sound: True   ipakit segment_distance = 0.6667
  BIPA 't͡s' and 't͜s' same sound: True   ipakit segment_distance = 0.3333
```

Zero of 8,765. Both tie bars map to the empty string in BIPA's own normalization table, so the deletion is by design and not an artifact of this corpus. BIPA then decides affricate-versus-cluster by lookup: `ts` is listed as an affricate and `kp` as a cluster, and a spelling it has not listed cannot state which it is.

ipakit distinguishes three things where BIPA has one. `t͡s` reads `manner=affricate`; `t͜s` reads `manner=plosive` with both constituents in the bag; `ts` is two segments. `segment_distance(t͡s, t͜s)` is 0.333 — a real contrast the other system cannot spell.

**This is what makes the mapping-table direction wrong, and it is a fact about the two models rather than about this data.** Two distinct ipakit units map to one BIPA grapheme, so BIPA → ipakit is not a function. A round trip through BIPA destroys the simultaneous/sequential distinction on every affricate, every diphthong and every cluster — 1,260 + 646 + 69 of BIPA's own sounds.

It also decides §7: a corpus normalized through BIPA arrives with the ties already gone. Consuming it is not consuming the ecosystem's data, it is consuming the ecosystem's data minus the dimension ipakit is built on.

## 4. A BIPA phonemap does not fit `xsampa.xml`'s shape

The house pattern is: derive the table from the declarations, ship it in `data/phonemaps/`, and fail `make check` if the shipped copy drifts. `scripts/xsampa_table.py` does exactly that and the machinery would cost nearly nothing to reuse. It does not fit, for three reasons in increasing order of weight.

**It is not a bijection.** A phonemap is a flat table between one IPA spelling and one foreign spelling, and `phonemap.rng`'s own comment turns on the first mapping of a symbol winning — which is only safe if there is one.

```
BIPA sounds ipakit reads as one segment: 8075
  spelled identically:  5779
  spelled differently:  2296   (rows a lexical table would need)
  ipakit spellings claimed by more than one BIPA grapheme: 275   (each breaks the bijection)
    'b' <- ['b', 'ʰb', 'ʱb', 'ˀb', 'ⁿb']
    'b͡v' <- ['bv', 'ˀbv', 'ⁿbv']
```

**The collisions are not near-misses, they are ipakit losing data.** Five distinct BIPA sounds read as plain `b`, because ipakit silently drops a leading modifier (§6). That is a defect rather than a mapping problem — but a table built today would have encoded the defect as five rows pointing at one target, and the staleness check would have held it there.

**The disagreement is compositional, not lexical.** The edits between the two spellings are dominated by a handful of character-level rules — 1,187 sounds differ by U+0361 alone, 381 by U+035C, 219 by the `g`/`ɡ` choice — which is why two function calls close 1,933 of them. A 2,296-row table would enumerate the consequences of about four rules, and would go stale against `ipa.xml` on every inventory change.

**And BIPA is not another notation.** X-SAMPA, Kirshenbaum, TIMIT and CMU are foreign alphabets; a table is the only possible relation. BIPA is IPA under different conventions, which is the thing `lookalikes.xml` is for — and `lookalikes.xml` is four rows, not two thousand, because it states conventions rather than segments.

**Verdict: do not build a BIPA phonemap.** What should exist instead is documentation of the two-step read, which costs nothing and is measured in §1. If anything is shipped, the candidates are individual `lookalikes.xml` rows, each earning its place by the rule that file already states — a character with one dominant reading in the wild.

## 5. Sound classes cannot be derived, so they should not be shipped

SCA, DOLGO, ASJP and CV are principled reductions of an inventory, used for cognate detection and historical work, and taught. ipakit has a metric and natural classes but nothing of this kind. The house rule decides whether it should: a shipped table is derived from the declarations or it is not shipped.

A class is derivable here if the features its members share re-extend to exactly its members — `natural_class` over the class, then `phones_matching` over the result.

```
sca     24 classes over 139 phones; derivable from ipakit's declarations: 4 of 22
dolgo   13 classes over 139 phones; derivable from ipakit's declarations: 2 of 12
asjp    40 classes over 139 phones; derivable from ipakit's declarations: 9 of 35
cv       4 classes over 139 phones; derivable from ipakit's declarations: 2 of 3
```

The two DOLGO classes that do derive are the vowels and one epiglottal pair. The ones that do not are the interesting ones: DOLGO's `K` holds velars, uvulars, palatals, clicks *and* the alveolar affricates; `T` holds dentals, alveolars, retroflex stops *and* the postalveolar affricates. Those are not synchronic feature classes and were never meant to be — they group segments by diachronic stability, which is a historical judgment and not a fact about a bundle.

**Verdict: do not ship sound classes.** Deriving them is measured impossible; hand-maintaining them is the second copy of the inventory `test_declared_not_hardcoded.py` exists to prevent; and there is no shipped demand — no rule set, no doc example and nothing in the metric asks for one. Someone doing historical work should use CLTS, which is where these live and where their curation is maintained.

**Sonority is the near neighbor of this question and the answer is the opposite: build it.** PanPhon computes a sonority value from a decision tree over its features; ipakit exposes none, and a sweep of `ipakit/` for `sonor|syllabif|onset|coda|nucleus` finds `is_nucleus`, onset tracking in `normalize_stress_to_nucleus` and coda reasoning in `rules.py` — every consumer of a sonority scale, and no scale.

Neither the axis nor the listing order in `ipa.xml` supplies one. The listing order is the tempting read, and it descends `vowel approximant trill tap nasal fricative` before putting `plosive` ahead of `affricate`, which no sonority hierarchy does. The *axis* is what the metric uses, and it measures something else entirely:

```
manner axis="+constriction", by declared offset, most open first:
  vowel 0.40   approximant 0.50   trill 0.70   tap 0.75
  fricative 0.80   affricate 0.95   nasal 1.00   plosive 1.00
```

`nasal` and `plosive` both declare `offset="1.00"`, so `value_distance("nasal", "plosive")` is **0.0** and constriction alone ranks nasals below fricatives. That is correct for a nasal's oral tract and wrong for its sonority, which is precisely why the axis is named `+constriction` and not `+sonority`. The declaration is honest; anything reading a sonority ordering off it is reading it for more than it says.

A scale that does hold falls out of the declarations without a table: the `obstruent` natural class, the same `offset`, and nasal airflow read together score **ρ = 0.938** against PanPhon's over 115 shared phones, with 97.4% of pairs ordered concordantly. That satisfies the house rule — nothing hand-maintained, and it moves when `ipa.xml` moves.

**Verdict: build a derived sonority scale.** It is the highest-value item this lane found that is not a defect: sonority is what syllabification runs on, it is taught everywhere, and ipakit already has the consumers.

What the derivation still needs before it can ship is a way to be wrong out loud. It rests on one claim no declaration makes — that every sonorant outranks every obstruent — and the only oracle for that claim is PanPhon, a dev-only dependency no release gate imports, so `make check` cannot fail when the scale drifts. Declaring the rank in `ipa.xml`, beside the `obstruent` class that is already there, is what would turn a formula in Python into the derived-and-checked artifact §5 is asking for.

## 6. Lexibank and CLDF: do not consume

This was briefed as the biggest prize on the CLTS side and the biggest scope expansion, needing a verdict of its own. It gets one: **no**, and the reason is not size.

Lexibank is 191 repositories totaling about 2 GB. Licensing is mostly clean — 155 CC-BY-4.0 — but 28 carry no license or an unrecognized one, which for a BSD-2 library means the corpus cannot be treated as one thing. Consuming it also means `pycldf` and `cldfbench`, which is a heavier dependency tree than anything currently in `dev`.

None of that is decisive. This is: **every Lexibank word is normalized through BIPA**, so by §3 it arrives with both tie bars deleted. A corpus that cannot spell the affricate/cluster contrast is not a test of a library whose segmentation turns on it, and the segments it *can* spell, ipakit already agrees with at 92%. Against `scripts/sweep.py`'s generated corpus — every phone and every phone plus one diacritic that re-spells itself, and which by construction includes ties — the marginal information is small and points the wrong way.

For a phonology class the case is better but still thin: what a wordlist gives that generation does not is *attestation* — which segments actually co-occur, and how often. That is a real thing to teach and ipakit has no way to say it. But it is one dataset's worth of value, not 191, and the honest form of it is a lesson that reads one CLDF wordlist a student downloads, not a corpus ipakit consumes.

**If anything is done here, take one dataset, not the collection**, and take it as a documented example rather than a dependency.

## 7. The speech stack, which is where this library's readers actually live

The brief framed interop around the linguistics stack. That is not where a text-to-speech front end, a grapheme-to-phoneme step or a pronunciation lexicon lives, and the tools there behave differently enough that the verdicts do not carry over.

espeak-ng 1.52, phonemizer 3.4, gruut 2.4 and the Indigenous-language mapping library `g2p` 2.3.1 all installed clean. Counting loud refusals apart from silent resegmentations, as §9 argues one must:

| tool and setting | tried | clean | refused (loud) | **resegmented (silent)** | unit delta |
|---|---|---|---|---|---|
| espeak `--ipa` (the obvious flag) | 99 | 69 | 11 | **19** | +27 |
| espeak `--ipa=2` | 99 | 83 | 12 | **4** | +4 |
| phonemizer, default | 79 | 64 | 1 | **14** | +19 |
| **phonemizer, `tie=True`** | 79 | **78** | 1 | **0** | 0 |
| gruut | 47 | 17 | **0** | **30** | −22 |
| `g2p`, after `from_wild` | 66 | **66** | 0 | **0** | 0 |

**Three of these are settings, not engineering.** `--ipa=2` instead of `--ipa` cuts espeak's silent resegmentation from 19 to 4 with no other change, because `--ipa` writes affricates and diphthongs untied and `--ipa=2` writes U+0361. `tie=True` makes phonemizer the cleanest partner in the set with one keyword argument. Neither is a code change in ipakit; both are a line of documentation that does not exist.

**gruut is the dangerous one, and it is dangerous precisely because it never refuses.** Zero of 47 raise, and 30 of 47 come back damaged — its prosodic boundary tokens `‖` and `|` vanish, and its diphthongs are untied while its affricates are tied, so the two halves of one word disagree. A caller gets no signal at all. This is the argument of §9 arriving from a different direction: **a tool that refuses loudly is a better partner than a tool ipakit accepts.**

**`g2p` is the best-behaved of the four**, which matters because Indigenous and under-resourced language work is a named audience. 66 of 66 clean, and the two that needed rescue were an ASCII colon for length and a stray apostrophe, both of which `from_wild` handles correctly.

### The lexicon question

`from_cmu` / `to_cmu` over the whole of CMUdict — 135,166 entries, 863,018 ARPABET phones:

```
exact round trip: 135,135 / 135,166 = 99.977%
every one of the 39 base phones round-trips individually
```

That is a usable number, and the per-symbol table is perfect. The 31 failures are one mechanism in three classes, and it is a defect: **ipakit contains two tokenizers that disagree with each other.**

```python
>>> ipakit.from_cmu(["N", "AO1", "IH0", "NG"])
'nˈɔɪŋ'
>>> len(ipakit.segments("nˈɔɪŋ", strict=True))   # 4 -- correct
>>> ipakit.to_cmu("nˈɔɪŋ", strict=True)
['N', 'OY1', 'NG']                                # 3 -- wrong, and strict=True does not catch it
```

`from_cmu` writes adjacent phones with no boundary; `to_cmu` then reads the untied digraph as one unit where `segments` correctly reads two. Fifteen entries lose `AO1 IH0` to `OY1`, twelve lose `T SH` to `CH`, four lose `AO2 IH0` to `OY2`. §12(g).

And there is a second, sharper one in the same function, which inverts the safety ordering:

```python
>>> ipakit.to_cmu("ˈe͡ɪt", strict=True)   # U+0361 -- what phonemizer(tie=True) emits
ValueError: Cannot convert to CMU ARPABET: unknown symbols ['e', '͡']
>>> ipakit.to_cmu("ˈe͜ɪt", strict=True)   # U+035C
['EY1', 'T']
>>> ipakit.to_cmu("t͡ʃ", strict=True)     # U+0361 -- accepted here
['CH']
>>> ipakit.to_cmu("t͜ʃ", strict=True)
ValueError: Cannot convert to CMU ARPABET: unknown symbols ['͜']
```

`to_cmu` accepts exactly one tie glyph per category and rejects the other, in opposite directions for affricates and diphthongs, while `segments` reads all four as one unit. The rejected diphthong spelling is exactly what the best-behaved TTS setting in the table above produces. `from_wild` first fixes it — `to_cmu(from_wild("ˈe͡ɪt"))` gives `['EY1', 'T']` — and that is documented nowhere. §12(h).

X-SAMPA round-trips byte-identical. Kirshenbaum is lossy on diphthong ties (4 units out, 5 back). TIMIT drops stress, as it must.

### What is not there at all

There is no reader for the Festival, Festvox or Flite lexicon and phone-set formats — no `.scm` entry reader, no phone-set definition, no `cmulex`. `data/phonemaps/` holds CMU, Kirshenbaum, TIMIT, X-SAMPA and lookalikes. Kirshenbaum is the near miss and it is a real one, because **Kirshenbaum is espeak's own ASCII set**, so `from_kirshenbaum` over `espeak -x` is a working path today — with the caveat in §12(i) that it deletes word boundaries.

Worth recording plainly, because it is checkable and someone should decide about it: across all of `docs/` and `README.md`, espeak, phonemizer, gruut, Festival, Festvox, Flite, CMUdict and "text-to-speech" appear zero times. Kirshenbaum and ARPABET appear. **The library has the pieces this audience needs and says nothing to them.** That is a documentation verdict rather than an interop one, and it is probably the cheapest item in this document.

### A trap worth one paragraph

`espeak -x` emits something that looks like X-SAMPA and is not:

```python
>>> ipakit.features_from_xsampa("tS'eIndZ")   # via xsampa; espeak -x output
't͡ʃʲeɪndʒ'
```

The `'` becomes U+02B2 palatalization. ipakit is correct — X-SAMPA spells primary stress `"` and palatalization `'` — and the trap is that the two ASCII conventions are visually near-identical. `from_kirshenbaum` reads it right. This is the same shape as §8's quote character: an ASCII character whose reading depends on which convention produced it, silently wrong when the guess is wrong.

## 8. Epitran: a recipe, and one instruction not to follow it

Briefed as almost certainly free — Epitran emits IPA, ipakit consumes IPA, no model contact — with the expectation of a short confident section. **The headline number holds and the conclusion does not.**

Epitran 1.35.2 installs clean. 158 of its 158 mapping-table modes construct and transliterate; `eng-Latn` needs `flite`, which was not installed, and is reported as unavailable rather than counted. Over every mode's whole table, run through the transducer with its own pre- and post-processors — 8,463 distinct output strings, which is what a caller actually receives:

```
parse strictly                              8315  (98.3%)
only via normalize_lookalikes / from_wild     65  (0.8%)
refused                                       83  (1.0%)
ties broken (silent resegmentation)            0
```

Zero broken ties across all 158 modes, and 117 of them are completely clean. A realistic word-level check — 382 words of common vocabulary across twelve typologically varied languages — parses 379 strictly, with one refusal that is a hyphen in an untransliterated compound.

**So the recipe would be one line, and one line of it would be wrong.** The confident short version says "if a string fails, run `from_wild`". Four languages write the ejective or the glottal with a quote character, and `lookalikes.xml` declares `'` as primary stress:

```python
>>> ipakit.from_wild("t͡s'unt͡s'u")   # Hausa tsuntsu, 'bird'
't͡sˈunt͡sˈu'                          # two ejectives -> two stress marks, no error
```

Five segments, no warning, no exception. The same character refuses loudly where nothing follows it — the bare table value `t͡s'` fails — so **the same input is a loud error or a silent wrong answer depending on what comes next.** It reaches `hau-Latn`, `lez-Cyrl`, `pii-latn_Wiktionary` and `ood-Latn-sax`.

This is not a defect in `lookalikes.xml`. That file already states the rule it lives by — a character earns a row only if it has one dominant reading in the wild — and argues explicitly that stress is the dominant reading of `'`, which it is. It is a defect in the recipe the brief expected, and the recipe has to name it: **map `'` U+0027, `’` U+2019 and `‘` U+2018 to `ʼ` U+02BC before any wild-import door**, and filter Epitran's own non-IPA leakage (`<`, `>`, `V`, `C`, `!` appear in its output where a rule variable escapes).

For contrast, the 65 rescues that did fire are all correct: `:` → `ː` and `g` → `ɡ`. The soft reads are right symbol by symbol and wrong at the word level for exactly one of them.

**Verdict: a documented recipe and no code — but the recipe is subtractive, and the section is not short because the one step it must forbid is the step a reader would reach for first.** The genuine inventory gaps Epitran's output names — `͈` (Korean tense series), `ᵐ` and `ᵑ` (ipakit registers `ⁿ` but not these), `ᶑ`, `ˢ`, `̱`, `̍`, `̊`, `⁀` (a third tie glyph) — are the same list §1 produced from BIPA, arriving independently.

## 9. Inventories: build three small things, and not an importer

PHOIBLE downloads clean: 105,484 rows, 3,020 inventories, 3,142 distinct phonemes. And it reframes the whole assessment, because it makes plain which number matters.

```
bucket                          types   type%   memberships  token%
strict, ONE segment              1562   49.7%        89,984   85.3%
strict, SILENTLY RESEGMENTED     1377   43.8%        13,947   13.2%
refused (loud)                    203    6.5%         1,553    1.5%
empty feature bundles               0
```

**The brief's implicit axis was how many segments ipakit refuses. That is the wrong axis and it is the most useful correction this lane produced.** Refusals are 6.5%, and they are loud and safe. The dangerous number is the **43.8% ipakit accepts and silently splits in two**. Per inventory the gap is stark:

```
inventories: 3020
  every member accepted:                 2443   (80.9%)
  every member accepted AS ONE SEGMENT:   339   (11.2%)
```

81% of the world's documented inventories load; 11% load without a segment count changing underneath. For the classroom that is the difference between a distance model over a real language and one over a silently different inventory; under a model pipeline it is every vector count downstream.

phonepiece behaves the same way, and its advertised coverage needs the same correction: it lists 7,546 language codes but holds **2,486 distinct inventories**, and `read_inventory` falls back to English with a warning rather than failing. 100% of languages load; 41.7% read cleanly at the phoneme level.

### PHOIBLE is not a sub-case of CLTS, and the reason is structural

The brief asked whether CLTS's `phoible.tsv` makes this a sub-case of §1. Measured:

```
PHOIBLE segments ipakit refuses:              203
  CLTS maps to a BIPA ipakit accepts as ONE:   34   <-- 17%
  BIPA grapheme ipakit ALSO refuses:          150
```

17%, and the reason is not that the table is thin. ipakit's refusals are gaps in its own **diacritic** inventory — `͈ ͉ ͓ ͇ ȵ ʆ ʓ` — and BIPA spells those sounds with the identical characters: `b͈` maps to `b͈`. A grapheme-to-grapheme table cannot fix what both sides spell the same way. The untied side fares no better: BIPA writes `ae` and `ai` untied too, so 880 of 1,377 survive the rewrite unchanged. And where CLTS's mapping does fire it is itself lossy — `ɡ̤ǀ͓` becomes `ǀ`, dropping the voicing and both diacritics.

**Answer: its own piece of work, and a small one.**

### What is already there does not do the job

`import_phoneset` is the public door and it is not an importer: over all 3,142 PHOIBLE segments it rewrote 21 and collapsed 0, canonicalizing tie glyphs and nothing else. `Phoneset` is a name and a list of strings. The nearest thing to a bridge is `add_ties`, and over the 1,377 resegmented members it fixes 789, leaves 517 untouched and makes 71 worse — which is §12(b) measured at scale.

**Verdict: build three small things, in this order, and no importer.**

1. **Fix §12(a).** It is one branch, and it reaches 126 PHOIBLE segments, 22 phonepiece segments and 2 Epitran outputs.
2. **Fix §12(b).** Alone it takes PHOIBLE from 49.7% to roughly 90% single-segment.
3. **Add the dozen missing diacritics**, ranked by how many inventories contain them rather than by symbol count — `͉` (416 inventories), `͈` (415), `ȵ` (391), `̊` (87), `͓` (67), `͇` (28), then the tail. That ranking closes about 90% of the refusal weight and it is a thing generation cannot produce.

Then document the two conventions rather than coding around them: PHOIBLE overloads `|` as "or" where ipakit correctly reads the IPA minor break, so an importer must split on it first (100 segments), and Epitran's quote is §8.

### What an external inventory adds that generation does not

`scripts/sweep.py`'s corpus is every phone and every phone plus one mark that re-spells itself — **closed under ipakit's own inventory**. Three consequences, and they are the argument:

- It can never contain `͈`, `ȵ`, or an untied `ai`. It is structurally incapable of finding either defect class this lane found. Generation tests the parser against itself; an inventory tests it against the world.
- It carries **no frequency prior**, weighting `t` and `ʘ̬` alike. The ranking that says to fix `͉` before `ᴱ` — 416 inventories against 3 — is the whole argument for what to do first, and generation cannot produce it.
- It is **one mark per base**. Real inventories stack three (`d̪z̪̤`, `ŋ̥ǂ͓ˡxˀ`), which is where the leading-mark path and mark ordering actually bite.

The sweep still covers base-and-mark combinations no language attests, which is where parser bugs hide. **They are complementary**; the inventory supplies the out-of-inventory and out-of-convention axis the sweep cannot reach. The concrete deliverable is small: an inventory capture alongside `sweep.py capture`, diffed the same way.

## 10. PanPhon: build the measurement, ship nothing

The brief's position was **emit, never consume** — a declared mapping computing PanPhon's 24 features from ipakit's declarations, shipped in `data/phonemaps/` and staleness-checked like `xsampa.xml` — with the argument that the mapping is testable against PanPhon's own `ipa_all.csv`.

**The direction is right and the artifact is wrong. Build the mapping as a measurement; do not ship a table.**

ipakit reads 6,215 of `ipa_all.csv`'s 6,367 rows as one segment, and the refusals are not inventory gaps at all: 142 are leading `ˀ`, which is §12(a), and 10 are bare tone letters, which correctly carry no segment. Over that overlap, a mapping derived from the declarations — no per-symbol table, every rule reading a declared natural class, a place's arc, a manner's offset — gives:

```
cell agreement (all 24):   142191/149160 = 95.328%
cell agreement (22 live):  129761/136730 = 94.903%
segments agreeing on all 24:   2103 (33.84%)

disagreeing cells by kind:
  polarity clash (+ vs -)                4142  (59.4%)
  PanPhon declines to state a value (0)  2574  (36.9%)
  ipakit has nothing to state (0)         253  ( 3.6%)
```

Eight of the 22 live features agree on all 6,215 segments; `hitone` and `hireg` also read as 100% and are vacuous, which is why the script reports the two rates apart. The disagreement is neither enormous nor unprincipled — 4,142 real clashes in 136,730 live cells, concentrated in six features, and most of them tracing to five named causes. By the brief's own test, that earns interop.

**And yet the table should not ship, for three reasons the measurement itself produced.**

**33.8% is the number a caller would meet.** Cell agreement flatters: two thirds of segments disagree somewhere in their 24 features. A shipped `panphon.xml` invites a caller to treat as interop something that is a second opinion.

**There is no ground truth to check against, so `xsampa.xml`'s guard cannot be copied.** That check is `shipped == derived` against one authority. Here there are two systems and PanPhon is demonstrably wrong in places: `ɫ` is `hi-` while `tˠ` is `hi+`; `ɹ` is `round+`; `h` is `cons+` while `ʔ` is `cons-`; `ç`, `ⱱ`, `ʜ`, `ʡ`, `ʢ`, `ɚ` and `ɝ` have no row at all. Equality is not the predicate. What would work is the shape [reviewing.md](../reviewing.md) calls pinning the escapes: **a pinned disagreement set, failing on movement in either direction.** That is a test, not a shipped mapping, and it belongs beside the other guards.

**PanPhon is coarser than the thing it would be checking.** Over the overlap, 6,215 segments resolve to **3,000 distinct vectors** — `e`, `ë`, `e̝`, `e̞`, `ĕ`, `e̘`, `ɛ̘` and `e̟` are one of them. A caller reaching for a PanPhon table from inside ipakit would be trading a 3,025-valued metric for a 3,000-vector inventory.

**"Never consume" is right, and for a stronger reason than the brief gives.** Not merely that PanPhon is coarse:

```python
>>> panphon.FeatureTable().word_to_vector_list("bɚd", numeric=True)
[<b>, <d>]        # two vectors. the vowel is gone. no exception.
>>> panphon.FeatureTable().validate_word("bɚd")
False             # it knows -- but ipa_segs/word_fts/word_to_vector_list do not say
```

PanPhon has no row for 24 of ipakit's phones, and `ipa_segs` returns the empty list for 10 of them — silently, on the path every tutorial uses. Consuming that would put a silent segment deletion inside ipakit.

### Ties, which is where the two systems actually part

```
string     tie         ipakit  panphon
ts         untied           2        2
t͡s        over-tie         1        1
t͜s        under-tie        1        2   <-- disagree
k͡p        over-tie         1        1
k͜p        under-tie        1        2   <-- disagree
a͡ɪ        over-tie         1        2   <-- disagree
a͜ɪ        under-tie        1        2   <-- disagree

segment-count disagreements: 6 of 15
  ipa_all.csv rows containing U+0361 (over-tie): 1472
  ipa_all.csv rows containing U+035C (under-tie): 0
```

The sequential tie does not exist in PanPhon; `ipa_segs("t͜s")` deletes the character and returns two segments. The over-tie is honored only for enumerated affricates — `a͡ɪ` is not a row, so it splits too. `validate_word` returns `False` for both, and the vectorizing path does not say so.

So PanPhon is a third position, distinct from both: BIPA deletes the tie and reads the result by lookup (§3); PanPhon honors one tie for a listed subset and deletes the other; ipakit reads both as structure. **For a model pipeline the headline is 6 of 15, not 95.3%** — feature agreement is measured over segments the two systems already agree exist.

## 11. Capabilities worth having, independent of any interop verdict

Assessed on shipped demand — does a rule set, a doc example, the metric, or a standard taught process want it — rather than in the abstract. Refusals are the common answer and are recorded as such.

| Capability | Where it exists | Verdict |
|---|---|---|
| **Sonority scale** | PanPhon `sonority.py` | **Build.** §5: derivable at ρ = 0.938, and ipakit already has the consumers. |
| **Numeric vector export** | PanPhon `word_to_vector_list`, `word_array`, `bag_of_features` | **Build, small.** `ipakit.__all__` contains nothing matching `vector`/`array`/`numeric`. For a library positioning itself under model pipelines this is the missing primitive; the order comes from `feature_order` and the values from the declared types. |
| **Phone / feature error rate** | PanPhon distances | **Weak build.** PER and FER are the standard evaluation metrics for pronunciation output; `word_distance` returns `edit_cost` and `similarity` but no error rate. Small on top of the existing alignment. |
| **Diacritic applicability guard** | PanPhon `diacritic_definitions.yml` `conditions` / `exclude` | **Worth stealing the idea, not the file.** `ipa.xml` already declares `applies="consonant"` and `applies="nucleus"`; making an inapplicable mark a refusal rather than a silent no-op is the same shape as §12(a) and §12(e). |
| **Sound classes (SCA, DOLGO, ASJP)** | CLTS | **Refuse.** §5: not derivable, and no shipped or teaching demand inside ipakit. |
| **`dolgo_prime_distance`** | PanPhon | **Refuse.** A 10-class historical metric — `d(d͡ɮ, ħ) = 0.0`. Nothing in the rule sets, docs or metric wants it. |
| **Permissive / prefix-matching helpers** | PanPhon `permissive`, `longest_one_seg_prefix`, `filter_string` | **Refuse.** They encode the silent-drop policy ipakit deliberately rejects — except where ipakit accidentally implements it anyway, which is §12(a). |
| **Inventory similarity** | CLTS `Inventory.approximate_similarity` | **Refuse for now.** Real and useful for comparing inventories across datasets, but it is a question about corpora, and §6 says ipakit should not take those on. |

**PanPhon's distance functions are not a capability gap.** Spearman ρ against `ipakit.distance` over 2,415 pairs: `feature_edit_distance` 0.670, weighted 0.622, `hamming_feature_edit_distance` 0.659. The worst disagreements are systematically affricates — `d(t͡ɕ, ɕ)` is 0.042 in PanPhon against 0.667 in ipakit — because PanPhon marks `ɕ`, `ʑ` and `ɧ` as `delrel+`, so an alveolo-palatal fricative is already affricate-shaped and a tied affricate sits one feature from a plain fricative. ipakit's answer is the defensible one.

### The frame this audience actually competes in

Outside the scope of interop but load-bearing for what to build next, and measured rather than asserted: ipakit's rewrite engine is a phone-to-phone rewrite calculus over declared vocabularies, and the thing it has that letter-to-sound rule systems in the synthesis lineage do not is the **derivation trace**.

```
>>> print(ipakit.derive("bʌtər", "american-english").trace())
bʌtər
  tapping
      tapping: t -> ɾ @2
  = bʌɾər
```

`Derivation` carries `steps`, `fired`, `edits` and a rendered `trace`, each `Edit` naming the rule, the site and the bindings. When a front end mispronounces a word, that is the question actually being asked — which rule fired, and why — and answering it is a stronger pitch than any feature-vector interop measured here.

## 12. Defects the measurement exposed

Reported, not fixed; this lane is read-only on the library.

Each of these that later work has closed carries a superseded line saying what closed it. **(c) and (i) carry none, and still reproduce.**

### (a) A leading modifier is dropped silently, under `strict=True`

**Superseded by [#118](https://github.com/lenzo-ka/ipakit/pull/118), and closed ([#95](https://github.com/lenzo-ka/ipakit/issues/95)). A mark reaching no unit is reported: `segments("ʷk", strict=True)` raises, naming the unplaced mark, and the lenient read warns. Superseded again by [#131](https://github.com/lenzo-ka/ipakit/issues/131): the four marks an outside source actually writes before a base are read there rather than refused, so `segments("ⁿd", strict=True)` is one unit spelling `ⁿd`, with `approach="nasal"`.**

```python
>>> ipakit.segments("ⁿd", strict=True)     # one Segment, to_ipa() == 'd'
>>> ipakit.features("ⁿd")                  # {}
>>> ipakit.distance("ⁿd", "d")             # 0.0
>>> ipakit.segments("ˀkp", strict=True)    # two Segments, 'k' and 'p'
```

No warning, no exception. `ⁿ` is a *registered* diacritic — `dⁿ` composes correctly to `release=nasal` — so the guard that catches an unregistered symbol never fires; what has gone wrong is a registered modifier in a position where nothing can carry it.

Swept over the whole diacritic table, this is not a corner:

```
registered diacritics: 68
  raise or warn when written before a base:  2   (the two tie glyphs)
  carried through:                           2   (the two stress marks)
  SILENTLY DROPPED under strict=True:       64
```

Two marks bind, two refuse, and sixty-four vanish. It contradicts `segments()`'s own docstring, which offers `strict=True` as the guarantee that `to_ipa(segments(x)) == x`; superseded stress and unbound ties are both reported when they reach no unit, and nothing reports these.

Three reasons this is at the top of the list. It is precisely the failure [reviewing.md](../reviewing.md) names — a well-formed wrong answer under a green suite, with `features()` returning `{}` among its own examples. It is reachable from every source measured here: 383 BIPA sounds, 126 PHOIBLE segments, 22 phonepiece segments, 142 PanPhon rows, 2 Epitran outputs. And prenasalized and preglottalized stops are ordinary — Bantu, Austronesian, Sinitic, and several Khoisan and Mesoamerican inventories — so a pronunciation lexicon for any of them loses the contrast with no diagnostic.

Whether ipakit should *model* a pre-modifier is a separate and larger question — §2 puts it at 402 CLTS assertions. Refusing it loudly is right either way and is much smaller.

### (b) `add_ties` declines where it should act, and acts where it should decline

**Superseded by [#118](https://github.com/lenzo-ka/ipakit/pull/118), and closed ([#98](https://github.com/lenzo-ka/ipakit/issues/98)). It now ties across an intervening diacritic and ties the junction the chain asks for: `add_ties("d̪ɮ")` is `d̪͡ɮ` and `add_ties("d̠ʒxʼ")` is `d̠͡ʒ͡xʼ`. This is the fix §1's counts predate.**

```python
>>> ipakit.add_ties("dɮ")     # 'd͡ɮ'
>>> ipakit.add_ties("d̪ɮ")    # 'd̪ɮ'  -- unchanged
>>> ipakit.add_ties("e̞a")    # 'e̞a'  -- unchanged
```

The docstring is "Add tie bars between base phones in a multi-phone segment" and says nothing about declining. A modifier resets the left neighbor, so the next base sees nothing to tie to; on a three-element chain it therefore ties the *wrong* junction — `add_ties("d̠ʒxʼ")` gives `d̠ʒ͡xʼ`, joining ʒ to x rather than d̠ to ʒ. 293 of the 305 residual resegmentations in §1 are this, as are 517 of PHOIBLE's 1,377 untouched and 71 of its tied-wrong; closing it takes BIPA agreement to roughly 8,368 of 8,765 and PHOIBLE from 49.7% to about 90% single-segment. Whether the fix is to tie across an intervening diacritic or to report that it could not is a design question, but returning the input unchanged and silent is the one answer that cannot be right.

### (c) Composition is order-dependent, and outside data reaches it

**Superseded by [#135](https://github.com/lenzo-ka/ipakit/issues/135), and closed.** What two marks stating one feature mean is declared in `ipa.xml` and had two answers in the code: a `sequence="+"` feature composes across a run of marks, every other feature is single-valued and a second mark stating it is now reported, naming what contradicts what. The answer is the first mark's rather than a set, so it is still order-sensitive; what closed is that it is no longer silent, and that the read now refuses what `compose_unit` refuses to spell.

`compose_segments("ɛ̥̤")` gives `phonation=breathy`; `compose_segments("ɛ̤̥")` gives `devoiced`. Found independently by the composition lane; recorded here because the cross-check adds something that lane could not see — both orders occur in BIPA's data, so the case arrives from real input rather than from a constructed one, and it accounts for 61 of the 824 feature disagreements.

### (d) The IPA's other voiceless diacritic is not declared

**Superseded by [#118](https://github.com/lenzo-ka/ipakit/pull/118), and closed. The ring above and the line above are declared as the marks below, spelled twice, so `features("ŋ̊")` is a full bundle.**

U+030A COMBINING RING ABOVE is the ring the IPA prints for symbols with a descender. `features("ŋ̊")` is `{}` with a dropped-symbol warning; `features("ŋ̥")` is a full bundle. 22 BIPA sounds; it is a row in `ipa.xml`, or a row in `lookalikes.xml`, rather than a gap in both.

### (e) An ejective click loses its ejection entirely

**Superseded by [#118](https://github.com/lenzo-ka/ipakit/pull/118), and closed. An airstream mark states the segment's airstream rather than being discarded against a base that already declares one, so `features("ǂʼ")` and `features("ǂ")` differ and `distance("ǂʼ", "ǂ")` is `0.05`.**

```python
>>> ipakit.features("ǂʼ") == ipakit.features("ǂ")   # True
>>> ipakit.distance("ǂʼ", "ǂ")                      # 0.0
>>> ipakit.features("kʼ", with_defaults=False)["airstream"]   # 'ejective'
```

Found twice independently, from CLTS (33 segments) and from PanPhon (40). The mechanism is `airstream`'s `additive` mode meeting a base that already states a value, so it is not confined to clicks: any mark whose feature the base already states is discarded on the same terms. Two distinct symbols reading as the same segment with distance 0 is the shape of §12(a) again, one feature over.

### (f) An over-tied vowel pair reads as a different existing phone

**Superseded by [#129](https://github.com/lenzo-ka/ipakit/pull/129), and closed ([#99](https://github.com/lenzo-ka/ipakit/issues/99)). `to_phone(features("u͡i"))` no longer answers with a phone that is no constituent of the input.**

```python
>>> ipakit.to_phone(ipakit.features("u͡i"))    # 'y'
>>> ipakit.to_phone(ipakit.features("a͡ɪ"))    # 'ɪ'
```

This one needs care, because the neighboring case is documented and correct. `to_phone(features("a͜ɪ")) == "a"` is the *sequential* tie projecting its first constituent, which `IPAFeatures.to_phone` rule 3 states outright. `u͡i` is not that: `y` is not a constituent of `u͡i` at all. The **simultaneous** tie merges to a bundle reading `close front rounded`, and the nearest registered phone to that is the front rounded monophthong. The metric does not follow it there — `d(a͡ɪ, a) = d(a͡ɪ, ɪ) = d(a, ɪ)/2`, exactly midway, which is coherent — so the flat read and the metric disagree about the same unit. `to_phone(features("ʈ͡ʂ"))` is `None` while `to_phone(features("t͡s"))` is `"t͡s"`, in the same function.

### (g) `to_cmu` and `segments` are two tokenizers that disagree

**Superseded by [#129](https://github.com/lenzo-ka/ipakit/pull/129), and closed ([#97](https://github.com/lenzo-ka/ipakit/issues/97)). `to_cmu` reads the segments the tokenizer read rather than matching the table's own keys, so it answers `['N', 'AO1', 'IH0', 'NG']` here and the two agree.**

```python
>>> ipakit.from_cmu(["N", "AO1", "IH0", "NG"])
'nˈɔɪŋ'
>>> len(ipakit.segments("nˈɔɪŋ", strict=True))   # 4
>>> ipakit.to_cmu("nˈɔɪŋ", strict=True)
['N', 'OY1', 'NG']                                # 3
```

`from_cmu` writes adjacent phones with no boundary marker, and `to_cmu` then matches an untied digraph as a single unit where `segments` correctly reads two. 31 of CMUdict's 135,166 entries do not survive the round trip, in three classes — `AO1 IH0` to `OY1`, `T SH` to `CH`, `AO2 IH0` to `OY2` — and `strict=True` catches none of them. `segments` gets all 31 right, which is what makes this a disagreement between two readers rather than a parsing gap.

### (h) `to_cmu` accepts one tie glyph per category and rejects the other

**Superseded by [#129](https://github.com/lenzo-ka/ipakit/pull/129), and closed. Ligature aliases resolve where no caller can bypass it, so both tie glyphs are accepted in both categories and no row of the table below raises.**

| spelling | `segments` | `to_cmu` |
|---|---|---|
| `t͡ʃ` U+0361 | 1 unit | `['CH']` |
| `t͜ʃ` U+035C | 1 unit | **ValueError** |
| `e͡ɪ` U+0361 | 1 unit | **ValueError** |
| `e͜ɪ` U+035C | 1 unit | `['EY1']` |

Opposite directions for affricates and diphthongs, and the rejected diphthong spelling is what a TTS front end configured for its safest output actually emits. The error blames `['e', '͡']` — but `e` is in the inventory, and the real cause is the glyph. `from_wild` canonicalizes it and fixes the call, which is a good recipe and is documented nowhere.

### (i) Three symbols are dropped where the docstring promises they cannot be

```python
>>> ipakit.segments("‖", strict=True)                          # []
>>> ipakit.to_ipa(ipakit.segments("ˈhɛ.loʊ", strict=True))     # 'ˈhɛloʊ'
>>> ipakit.from_kirshenbaum("g'Ud T'IN")                       # 'ɡˈʊdθˈɪŋ'
```

`segments`'s docstring offers `strict=True` as the guarantee of `to_ipa(segments(x)) == x` "rather than a quietly shortened result". `.`, `|` and `‖` are quietly shortened, and `‖` alone comes back as the empty list — which a front end emits as a token. `from_kirshenbaum` deletes word boundaries, which matters because `espeak -x` plus `from_kirshenbaum` is otherwise the working ASCII path for lexicon work.

Smaller, in the same family: `to_ipa` reorders two combining marks of the same canonical class, which Unicode's own ordering leaves alone — `ɛ̆̃` comes back as `ɛ̃̆` (7 of PHOIBLE's 3,142) — and `to_cmu` warns on every length mark, so an en-GB lexicon warns on every long vowel and the rational response is to suppress warnings and miss the real ones.

### Two things that are *not* defects, and were expected to be

The brief and its follow-ups named two behaviors as suspect. Both are documented and deliberate, and saying so is part of the job.

**`distance("a", "aː")` was `0.0`: prosody was excluded from the metric.** Superseded by [#190](https://github.com/lenzo-ka/ipakit/issues/190) — stress, tone and length now ride on the unit they attach to and each adds a graded ordinal term (see [distance.md](../distance.md)). At the time this was written it was documented and deliberate, not a defect; the design has since changed.

**`d(n, d) = 0.05` is not a nasality defect, and checking that was worth the time.** The PanPhon arm reported it as one, on a real observation: `/n/` and `/d/` differ in exactly one declared feature, `manner`, and `manner`'s axis is `+constriction`, on which `nasal` and `plosive` both declare `offset="1.00"` — so `value_distance("nasal", "plosive")` is `0.0`. The inference was that nothing carries nasal airflow, since `features("n")["nasalized"]` is `-`. The inference is wrong:

```
metric-bundle keys where n and d differ: {'nasality': ('+', '-'), 'manner': ('nasal', 'plosive')}
```

The velic dimension reaches the metric as a **derived bridge**, which is exactly the mechanism [supplement-bridges.md](supplement-bridges.md) is about — a key in the comparison bundle that is in no symbol's feature bundle. The metric is coherent and `nearest_phones("n")` returns five nasals. What remains true and is worth one line in `ipa.xml`: `manner`'s axis measures constriction and is correctly named for it, so anything wanting sonority must read `obstruent` alongside it. That is §5's verdict, and it is the same finding arriving from the other side.

**`to_phone(features("a͜ɪ"))` is `"a"`, not `"a͜ɪ"`.** This was briefed as "`to_phone` cannot recover a tied unit from a flat bundle", which is true and is the documented tie-break: `IPAFeatures.to_phone` rule 3 says a tied compound's flat bundle "is only the projection of one constituent, so it never outranks an atom matching equally well: 'a', not 'a͜ɪ'". There is nothing to recover — the flat bundle does not carry the second constituent, which is what `feature_values` / `Segment.bag` exist for. The comparison with CLTS is still worth having, because CLTS's `bipa[name]` round-trips **8,765 of 8,765** against ipakit's `to_phone(features(p))` at 131 of 139 — but the asymmetry is that a CLTS name carries the whole description while an ipakit flat bundle deliberately does not. The two are not the same read.

### Ergonomics, since a busy practitioner meets these first

Written down because the brief asked, and because this lane used the library the way a newcomer would.

- **`features("aː")["length"]` is `"normal"`.** The read that resolves a prosodic mark is `IPAFeatures.compose_segments`, which is not in the top-level API; `features`'s own docstring does not mention the divergence, though `compose_segments`'s does. This produced 1,831 spurious disagreements in an early run of §2 before it was caught, which is a fair estimate of how misleading it is.
- **`feature_values("manner")` raises `expected exactly one unit, got 6`.** The name reads as "the values this feature declares"; it means "the values each feature takes across one unit". The answer wanted is `load_ipa_features().features["manner"].values`.
- **`distance("ts", "t͡s")` raises** and names `segment_distance` in the message. That is the right shape and is called out as the contrast with the three above.
- **`add_ties` and the leading-modifier case both fail by returning something plausible.** A newcomer's first ten minutes with foreign IPA hits both.

## Sources

All fetched 2026-08-02 and read directly.

- CLTS (Cross-Linguistic Transcription Systems) and BIPA, data repository at commit `4da03b1`: <https://github.com/cldf-clts/clts>. `data/sounds.tsv` is the 8,765-sound corpus of §1–§4; `data/features.tsv` the feature vocabulary of §2; `pkg/transcriptionsystems/bipa/normalize.tsv` the tie deletion of §3; `pkg/soundclasses/lingpy.tsv` the sound classes of §5; `pkg/transcriptiondata/phoible.tsv` the mapping of §9.
- `pyclts` 4.0.2: <https://pypi.org/project/pyclts/>. Read as source, not as documentation — §0's claims about `Sound.similarity` and the absent tokenizer are claims about the code.
- PanPhon 0.22.2: <https://github.com/dmort27/panphon>. `panphon/data/ipa_all.csv` is §10's corpus; `sonority.py` is what §5's derived scale is measured against.
- PHOIBLE, `data/phoible.csv` on the `dev` branch: <https://github.com/phoible/dev>. 3,020 inventories, 3,142 distinct phonemes; §9. The branch is edited continuously and carries no release tag.
- Epitran 1.35.2: <https://github.com/dmort27/epitran>. 158 mapping tables; the nine modes flagged for "limited support due to highly ambiguous orthographies" are named in the package's own README, and §8 cites rather than re-litigates that caveat.
- `phonepiece` 1.4.2: <https://github.com/xinjli/phonepiece>. Per-language inventories, downloaded by the package on first use.
- Lexibank: <https://github.com/lexibank>, and the repository listing at <https://api.github.com/orgs/lexibank/repos> for §6's size and licensing counts.

CLTS, PHOIBLE and Lexibank are unversioned on their default branches and PanPhon ships its table inside the wheel, so every one of these moves under a reader. The copies these numbers were taken from are kept outside the repository with their access dates; the commit and versions above are what a re-run should pin to.

## Reproducing the measurements

Every number above was taken with `PYTHONHASHSEED=0` against this worktree, reading the library only; nothing was written into the tree.

The measurements live in `scripts/interop.py`, one subcommand each, in the shape `scripts/sweep.py` and `scripts/articulatory.py` already use — a design document is prose and nothing checks prose, so a claim that carries an argument has to be re-runnable by whoever doubts it. `pyclts` and `panphon` are a new dev-only extra (`pip install -e ".[interop]"`), on the same terms as `icu`: read by one script, never imported by the library.

`cmudict` takes the lexicon as a path, for the same reason:

```
curl -O https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
python scripts/interop.py cmudict --lexicon cmudict.dict
```

`marks` needs nothing at all — it sweeps ipakit's own diacritic table, which is why §12(a)'s 64 of 68 is the one number here that cannot go stale against an outside project. The PanPhon measurements read that package's own shipped `ipa_all.csv`. `inventory` takes a path, so it runs over PHOIBLE, phonepiece or any other segment list:

```
python scripts/interop.py inventory --inventory phoible.csv --column Phoneme
```

CLTS is a 54 MB data repository under its own license and is not bundled, so clone it and point the script at it:

```
git clone --depth 1 https://github.com/cldf-clts/clts
export IPAKIT_CLTS_DIR=$PWD/clts
PYTHONHASHSEED=0 python scripts/interop.py all
```

Every CLTS subcommand exits 0 with a message when the clone is not mounted, because CI will not have it, and `all` runs the PanPhon half regardless. Each asserts the shape of what it read — a sound-count floor, a row-count floor, a compared-segment floor — so a run over a truncated clone fails loudly rather than reporting a clean empty result.

The PanPhon mapping asserts one more thing before it runs: that `ipa_all.csv`'s header is the feature tuple it was written against. That order is not documentation, it is the vector layout, and building against a remembered order transposes two features into what reads as a model disagreement. The brief's own listing had `syl cons son`; the file has `syl son cons`.

Two choices in the measurement are worth stating because a different one would give different numbers.

**The corpus is `data/sounds.tsv`, BIPA's 8,765 resolved sounds**, not `data/graphemes.tsv`. The latter is every spelling any source dataset ever used, 81,896 rows, and measuring against it would report how noisy the field's transcription is rather than how the two models compare.

**`inventory` counts memberships, not just types.** Pointing it at PHOIBLE's row-per-inventory CSV weights each segment by how many inventories carry it, which is what produced §9's ranking of which missing diacritic to add first. A distinct-segment count would have put `ᴱ` (3 inventories) beside `͉` (416).

**§2 reads `compose_segments`, not `features`.** They differ on exactly one thing — a prosodic mark reaches the composed bundle and not the flat one — and since CLTS states duration as a feature, using `features` scored 1,831 length assertions as disagreements that are not. The choice is the reason that ergonomics note is in §12 rather than in a footnote.

**§7's per-tool table is not in the script, and that is a deliberate limit.** espeak-ng, phonemizer, gruut and `g2p` are four more packages plus a system binary, and the section's verdict is that the fixes are *settings* rather than engineering — so pinning four dependencies to re-derive numbers that say "pass `tie=True`" would cost more than it is worth. What is in the script is the part that carries an argument on its own: `cmudict`, which is the lexicon claim, and `marks`, which is the defect underneath several of them. The per-tool numbers were taken on 2026-08-02 against espeak-ng 1.52.0, phonemizer 3.4.0, gruut 2.4.0 and `g2p` 2.3.1, over a fixed word list, counting a refusal apart from a unit-count change; anyone re-running them should expect the tools to have moved and the shape of the answer not to have.

One trap in that measurement is worth passing on, because the first numbers taken were wrong because of it: attribute a refusal by removing characters until the string parses, not by testing characters in isolation. `ˈ` on its own raises "unbound stress mark", which would blame U+02C8 for every stressed word in the corpus.

The correspondence table in §2 is curated between two vocabularies and checked in both directions before every run: a CLTS value it does not name is a hard error, and an ipakit target `ipa.xml` no longer declares is a hard error. Neither can degrade into a silently better agreement rate.
