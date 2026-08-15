# The ecosystem, as its users describe it

> Historical design record (2026-08-10). This assessment predates the completed tier-graph migration and is superseded as a description of the representation by [the canonical representation](../representation.md); its research findings and contemporaneous design reasoning are retained unchanged.

What do the people using the existing phonetics tools say goes wrong, and what should ipakit do differently as a result?

**Verdict: the dominant complaint is a silent wrong answer at the string boundary, and the reason it never gets fixed upstream is that there is no "correct IPA" to appeal to.** A character a tool does not recognize gets dropped, and the caller is handed a well-formed result computed over less than they wrote. The instance that recurs most is the two `g`s — three separate projects have been asked to accept `U+0067` where `U+0261` was meant, and each declined on the grounds that it implements the standard strictly. Measured today, **the field's two flagship cross-linguistic catalogs normalize that character in opposite directions**: PHOIBLE to `U+0261`, CLTS to `U+0067`. Strictness is not available as a position. What is available is *saying which one you chose and why*, which is what `data/phonemaps/lookalikes.xml` is.

Two of the complaints land on ipakit as well, and they are the most useful findings here. It cannot read the IPA's own raised-diacritic variants — `U+030A` and `U+030D`, the forms prescribed on glyphs with descenders — so `ŋ̊` loses its voicelessness. *(Since closed — these are now declared as `alias` spellings in the inventory; §5.)* And chasing PHOIBLE's "two segments, one feature vector" complaint into ipakit turned up not the collapse itself, which is deliberate and documented, but **a guard that has stopped guarding**: the exception in `check_descriptions` that excuses a vowel and its diphthongs in fact excuses any two atomic phones, consonants included, and one of its two conjuncts is tautological. Both are reported here with a reproducing case, not fixed; this lane changed no code, data or tests, and `make check` exits 0.

The articulatory hole is real. Nothing surveyed maps IPA to constriction location and degree. The symbolic toolkits emit distinctive features, which are phonological rather than geometric; the articulatory tools infer measured traces from audio or drive a synthesizer from a gestural score, and none of them takes IPA in.

## Summary of findings

| Question | Finding |
|---|---|
| What is the single most recurrent complaint? | **Input silently altered rather than refused.** Measured live: `panphon.FeatureTable().word_fts("gat")` returns 2 segments and raises no warning. |
| Is the `ɡ` problem widespread, or one annoyed user? | **Three projects, four issues, 2017–2021**, each answered "not ours to fix". |
| Is "just use correct IPA" an answer? | **No.** PHOIBLE normalizes `U+0067` → `U+0261`; CLTS/BIPA normalizes `U+0261` → `U+0067`. Both byte-verified 2026-08-02. |
| Is the confusion recognized outside linguistics? | **Yes.** Unicode UTS #39 `confusables.txt` v17.0.0 lists `ɡ→g`, `ː→:`, `ˈ→'`, `ʼ→'`, `ɑ→a`, `ə→ǝ`, `ǃ→!`, `ʔ→?`. |
| Does ipakit have that problem? | **No, and by an explicit decision.** Strict reads report `unknown_symbol` and name the character; substitution lives behind `from_wild`. |
| Does ipakit have a *different* Unicode gap? | **It did; now closed.** `U+030A` and `U+030D` were unregistered, so `ŋ̊` tokenized to `ŋ` under one warning; they are now `alias` spellings in the inventory and `ŋ̊` reads `['ŋ̥']`. PHOIBLE ships segments spelled that way. §5. |
| Do distinct segments collapse to one feature vector? | **Yes, everywhere, and worst where the table is largest.** panphon: 4,769 of 6,367 (74.9%). PHOIBLE: 839 of 2,162 (38.8%). ipakit: 4 of 139, all diphthongs, by design. |
| Is enumeration-versus-composition a real published critique? | **Yes.** SCiL 2024: fixed sound sets lack "a dynamic component", and meeting an unlisted sound is "rather the rule than the exception". |
| What is panphon actually used for? | **69 of 96 engaged papers use it as model input; 30 use it as an error metric.** The metric use was not anticipated by the brief and has stricter stability requirements. |
| Did chasing that into ipakit find anything? | **Yes, a defect.** `check_descriptions`' vowel exception excuses any two atomic phones, `['p','t']` included; its second conjunct is always true. |
| Is a rewrite trace a voiced need? | **In sound-change appliers, yes. In g2p, no — the incumbent already ships one** (`espeak-ng -X`). This contradicts the brief. |
| What do g2p users ask for that nobody answers? | **"What is the phone set?"** — 10 issues across three projects, 2019–2025. |
| What does the conlang world work around by hand? | **The absence of a shipped IPA feature inventory.** Hand-maintained codepoint lists stand in for natural classes. |
| What does the teaching world work around? | **A tool that cannot represent IPA at all**, and a platform requirement met by walking to a departmental lab machine. |
| Is the articulatory gap real? | **Yes.** No surveyed tool maps IPA to constriction location and degree. |
| Can an issue tracker be read as user sentiment? | **Only some of them.** Two of the eleven are development logs: 66% and 72% of their issues were filed by one account. |

## 1. Method, and what it cannot see

Every issue in eleven library trackers and five g2p/TTS trackers was pulled through the GitHub API on 2026-08-02, pull requests excluded, both states. Counts below are over those snapshots and the query for each is given where it is used, so any of them can be re-run.

**A tracker over-represents problems by construction**, and a busy one can mean an engaged community rather than a bad tool. Lexurgy is the clearest case: 84 issues, 7 open, the closed ones overwhelmingly answered rather than abandoned. That is a maintainer keeping up.

**More seriously, not every tracker is a user-complaint corpus.** Counting the account that opened each issue separates them:

| repository | issues | distinct openers | share from the largest single opener |
|---|---:|---:|---:|
| `PhonologicalCorpusTools/CorpusTools` | 734 | 23 | 66% |
| `phoible/dev` | 212 | 21 | 72% |
| `cldf/segments` | 29 | 9 | 45% |
| `cldf-clts/pyclts` | 29 | 9 | 38% |
| `dmort27/panphon` | 42 | 30 | 17% |
| `dmort27/epitran` | 109 | 93 | 4% |
| `bootphon/phonemizer` | 170 | 123 | 6% |
| `xinjli/allosaurus` | 70 | 53 | 6% |
| `def-gthill/lexurgy` | 84 | 33 | 19% |
| `bradrn/brassica` | 13 | 12 | 15% |

The first two are development logs — a team's own task list, kept in public. Reading CorpusTools' 734 issues as user sentiment would be a category error, and it is why this document draws almost nothing from it. The bottom six are genuine user-complaint corpora and carry most of the weight here.

**No individual is named anywhere in this document.** Complaints are attributed to a repository, an issue number and a date; quoted replies are quoted as project statements, which is what they are. Two cited URLs in §8 carry a personal name in their path because that is the only address those documents have, and a citation that cannot be followed is worse than one that can.

**The literature was surveyed by citation graph.** The papers citing the panphon (179), epitran (184), Allosaurus (173) and phonemizer (150) publications were enumerated through Semantic Scholar's by-identifier endpoint, and 189 full texts were downloaded from arXiv and the ACL Anthology and searched for sentences naming a tool alongside a limitation. Coverage is therefore good for arXiv, ACL and ISCA and poor for paywalled venues; two survey papers returned 403 and were not read. Category counts from that corpus are this lane's own classification, not the papers' own.

**What could not be reached** is listed in full at the end.

## 2. How the tools are actually used

Usage determines what interop is for, so it is worth settling before the complaints.

**panphon is used as a feature-vector emitter — and, increasingly, as a scoring function.** Its tracker says the first part: of 42 issues, 11 concern the correctness of a value in `ipa_all.csv` or `ipa_bases.csv`, and 5 concern the distance functions built over those vectors. Nobody asks it to describe a sound, search an inventory or apply a rule, because it does not do those things.

The citation graph says something the tracker cannot. Of the 179 papers citing the 2016 COLING paper, 96 mention panphon in body text rather than only in the bibliography; **69 of those use its vectors as model input and 30 use it as an error metric**, 20 doing both. The metric is Phonetic Feature Error Rate, an edit distance over panphon features, and it has become a standard reported number in multilingual phone recognition. **That partly refutes the framing this lane was given.** "IPA string in, vector out, into a neural model" is real and dominant, but a third of the engaged literature reaches for panphon to *evaluate* a system rather than to build one — and an evaluation metric has different requirements from a representation. A metric must be stable across versions and comparable across papers, which makes the drift in §6 more serious than it would be for a feature encoder.

The classification is by title and abstract with a stated priority order, and is this lane's own; another annotator would move perhaps 10–15% of borderline cases. The largest application categories are ASR and phone recognition (41), cross-lingual transfer (31), historical and cognate work (16), and g2p (13). The named-entity framing of the original paper appears in 1 of 179.

**epitran is used as a g2p front end, and the complaint is always a language.** The citation graph confirms it without qualification: of 184 citing papers, the largest category is g2p and phonemization front end (44, 23%), followed by cross-lingual transfer (35) and ASR (31); named-entity work, which the tool was partly motivated by, is 0. It is almost never the object of study — it is the thing that produces the training data. Of 109 issues, **29 name a specific language or ISO code in the title** — French liaison, German, Yoruba, Kirundi, Punjabi diacritics, Vietnamese tone, Arabic, Japanese kanji, Polish rule ordering. Eleven are open. A further 9 are about one thing: `lex_lookup` from flite, the external C binary the English path requires, generating install failures continuously from [#5](https://github.com/dmort27/epitran/issues/5) (2017-09) to [#204](https://github.com/dmort27/epitran/issues/204) (2025-03).

**phonemizer is a text front end for text-to-speech.** Of 150 citing papers, **64 (43%) are TTS**, and with ASR and g2p added, 57% use it as an orthography-to-IPA converter in a pipeline. Its tracker is mostly about the thing it wraps: of 170 issues, **12 are specifically about locating or installing espeak-ng**, six still open, including [#189](https://github.com/bootphon/phonemizer/issues/189) (2024-11) asking it not to raise on a missing espeak and [#192](https://github.com/bootphon/phonemizer/issues/192) (2025-01) asking for a prebuilt binary.

Its own test suite carries the sharpest available statement of a reproducibility hazard: assertions are conditioned on the espeak-ng version, because English *four* is `foːɹ` before espeak-ng 1.52.0 and `fɔːɹ` from 1.52.0 on. A pipeline's phone inventory therefore depends on a system package's version, which is not something a `requirements.txt` records.

**Allosaurus is used on languages that have no other option, and the inventory is what breaks.** [#1](https://github.com/xinjli/allosaurus/issues/1) (2020-06-25, open) reports the Kunwinjku phone inventory as incomplete against PHOIBLE, and the reply identifies the cause exactly: the inventories were built from PHOIBLE's `Segment` column rather than its `Allophone` column, because the allophone column is empty for many languages. Six years open. [#77](https://github.com/xinjli/allosaurus/issues/77) (2023-07, open) reports the model emitting phones outside the requested language inventory. [#14](https://github.com/xinjli/allosaurus/issues/14) (2020-10, open) asks for symbols outside IPA altogether, which is what field transcription often is.

**Lexurgy and Brassica are rule engines whose users work in diacritics and syllables.** Of Lexurgy's 84 issues, **18 name a syllable or stress in the title and 9 name a diacritic** — marks detaching after a change, marks doubling, a mark at position 0 not attached to a symbol, a diacritic that matches a base symbol. That is the territory ipakit calls mark binding.

## 3. There is no "just use IPA"

This is the finding the document exists for, and it is larger than the complaint that surfaces it.

### The complaint

`panphon` accepts `U+0261 ɡ` and not `U+0067 g`. In [#2](https://github.com/dmort27/panphon/issues/2) (2017-05-19) a user asked for both, having received expert transcriptions in which every symbol validated except that one; the maintainer declined and suggested normalizing input beforehand. The user's reply is the evidence: they said they would handle the remapping in adapter code.

Two and a half years later [#18](https://github.com/dmort27/panphon/issues/18) (2019-10-18) is the same problem arriving as confusion rather than as a request — twenty minutes lost to a program returning nothing for words containing `g`. The reply states the position plainly:

> I don't want to go down the de facto standard rabbit hole. My goal with PanPhon is to implement the Unicode IPA standards strictly, rather than worrying about deviations.
> Adding `"g"` to the table will break some downstream software that uses PanPhon to validate IPA.

**The second reason is unanswerable and the refusal is right.** A library other software uses as an IPA validator cannot quietly widen what it accepts. The same comment offers a mitigation:

> What I can do is add a warning that fires if an input string contains `"g"`, suggesting that they may have actually intended `"ɡ"`.

**Measured on panphon 0.22.2 (released 2025-06-12, checked 2026-08-02): the warning has not landed.**

```
word_fts('gat') -> 2 segs ['a', 't']; validate_word -> False; warnings raised: 0
```

The refusal is silent. `word_fts` returns the feature vectors of `at` and nothing in the return value says a character was dropped. `validate_word` does report `False`, so the information exists — but only for a caller who thinks to ask, and the caller who thinks to ask is not the caller who loses twenty minutes.

The same complaint reaches a third project in [phonemizer #86](https://github.com/bootphon/phonemizer/issues/86) (2021-11-08) from the other direction: a user found the output's first character was not the `g` on their keyboard. The answer was that this is espeak's behavior, not a phonemizer bug. Verified locally 2026-08-02, espeak-ng emits `U+0261`:

```
espeak-ng -q --ipa -v en-us "grandma"  ->  U+0261 U+0279 U+02C8 U+00E6 U+006E U+0064 U+006D U+0251 U+02D0
```

### The reason it never gets fixed

The first reason given above — implement the standard strictly — is the one that does not hold, and it does not hold as a matter of fact rather than of taste.

**PHOIBLE and CLTS, the two most widely used cross-linguistic phonological catalogs, normalize this character in opposite directions.** Both verified from primary data on 2026-08-02:

| catalog | rule | source |
|---|---|---|
| PHOIBLE | uses `U+0261`; normalizes input to NFD and then imposes its own diacritic order | <https://phoible.github.io/conventions/> |
| CLTS / BIPA | `ɡ U+0261` → `g U+0067` | `pkg/transcriptionsystems/bipa/normalize.tsv`, line for U+0261 |

That is not a difference in care. Both are peer-reviewed, both document the decision, and they went opposite ways. A tool that says it implements IPA strictly has to say *which* strict IPA, and none of the surveyed tools does.

The reason the disagreement is possible is that the standard permits it. *The Unicode Cookbook for Linguists* (Language Science Press, 2018, open access, <https://langsci-press.org/catalog/book/176>), §5.5:

> The International Phonetic Association has taken the stance that both the keyboard latin small letter g and the latin small letter script g are valid input characters for the voiced velar plosive (The International Phonetic Association 1999: 19). Unfortunately, this decision further introduces ambiguity for linguists trying to adhere to a strict Unicode Standard IPA encoding.

**That passage is the weakest-sourced thing in this document and is labeled accordingly.** It was recovered verbatim by two research lanes working separately, which is why it appears at all; but attempts to fetch the Cookbook PDF directly for this document failed at three mirrors, and the Handbook page it cites was opened by nobody. So it is quoted at one remove and establishes only what the Cookbook is reported to say. Nothing above depends on it: the divergence between PHOIBLE and CLTS is measured from primary data and stands whether or not this explains it.

The disagreement is not confined to `g`. CLTS's `normalize.tsv` is 47 lines, and three more of its rules would surprise a caller:

```
͡  U+0361  ->  (deleted)          tie bars are stripped
͜  U+035C  ->  (deleted)
ɚ  U+025A  ->  ə˞  U+0259+U+02DE  r-coloring decomposed
˥  U+02E5  ->  ⁵   U+2075         tone bars become superscript digits
```

So BIPA and chart IPA disagree about whether a tie bar exists at all. Feeding BIPA output to ipakit's strict reader, measured:

```
'g'   U+0067              tok=[]         error: unknown_symbol   warns=1
'⁵'   U+2075              tok=[]         error: unknown_symbol   warns=1
'ts'  U+0074+U+0073       tok=['t','s']  no error                warns=0
't͡s'  U+0074+U+0361+U+0073 tok=['t͡s']    no error                warns=0
```

The first two are refused loudly, which is the correct outcome for a symbol from another convention. **The third is the hazard**: a BIPA affricate arrives as two segments with no error and no warning, because `ts` is a perfectly well-formed IPA cluster. That is a silent wrong answer that no amount of validation can catch, because nothing is wrong with the string — the information was destroyed upstream. It is worth stating plainly rather than treating as an ipakit defect: **a lossy normalization in a source is not recoverable by a careful reader**, and the only defense is knowing which convention a corpus is in.

Outside linguistics the ambiguity is formally recognized. Unicode's UTS #39 `confusables.txt` (v17.0.0, dated 2025-07-22, fetched 2026-08-02) lists every pair at issue:

```
0261 ; 0067 ; MA  # ( ɡ → g )   LATIN SMALL LETTER SCRIPT G → LATIN SMALL LETTER G
02D0 ; 003A ; MA  # ( ː → : )   MODIFIER LETTER TRIANGULAR COLON → COLON
02C8 ; 0027 ; MA  # ( ˈ → ' )   MODIFIER LETTER VERTICAL LINE → APOSTROPHE
02BC ; 0027 ; MA  # ( ʼ → ' )   MODIFIER LETTER APOSTROPHE → APOSTROPHE
0251 ; 0061 ; MA  # ( ɑ → a )   LATIN SMALL LETTER ALPHA → LATIN SMALL LETTER A
0259 ; 01DD ; MA  # ( ə → ǝ )   LATIN SMALL LETTER SCHWA → LATIN SMALL LETTER TURNED E
01C3 ; 0021 ; MA  # ( ǃ → ! )   LATIN LETTER RETROFLEX CLICK → EXCLAMATION MARK
0294 ; 003F ; MA  # ( ʔ → ? )   LATIN LETTER GLOTTAL STOP → QUESTION MARK
```

Two things in that list are worth pulling out. **The apostrophe appears twice**, as the confusable of both primary stress and the ejective — Unicode itself records that `'` is two-way ambiguous, which is precisely the judgement `lookalikes.xml` had to make. And **`U+02CC`, secondary stress, has no entry at all**; verified negative, so the coverage is not uniform and the file cannot be treated as a complete inventory of the problem.

### Does ipakit have this problem?

No, and the design is close to the shape the evidence recommends. Measured over the eight pairs above:

- **ipakit reads the IPA member of all eight.**
- **It refuses the confusable in seven of the eight, naming it** (`unknown_symbol` plus a warning). The exception is `a` versus `ɑ`, where both are chart-proper IPA vowels and the confusion is genuinely between two real symbols, not between IPA and a keyboard.
- **Four have a soft read behind `from_wild` / `normalize_lookalikes`**: `g→ɡ`, `:→ː`, `'→ˈ`, `?→ʔ`. Every one of those four is in Unicode's confusables list.

So the strict path gives panphon's downstream validators exactly what they need, and the wild path gives two of panphon's own users the adapter they were told to write. The two are separate doors, which is the part neither project had.

The part of `lookalikes.xml` worth pointing at is not the four mappings; it is the refusal recorded beside them. `!` is left unmapped because it has three readings with no dominant one — the alveolar click, downstep, and ordinary punctuation — so guessing turns a full stop into a consonant. **That is a deliberate departure from what Unicode would sanction** (`ǃ→!` is in the confusables list) and the reason is written down where the next person to propose the row will read it. Likewise `'→ˈ` rather than `'→ʼ`, on a stated argument about which reading dominates in the wild, in a case where Unicode records both.

### What ipakit should do differently

Nothing in this section, and that is the point of measuring it. The finding is validation: a nine-year-old, three-project complaint has a shipped answer here, and the underlying reason it stayed open elsewhere — that strictness is underdetermined — is a fact about the field rather than about anyone's diligence.

One thing does follow, though it belongs in interop material rather than here: **`from_wild` should be described as choosing a convention, not as being lenient.** The evidence above says the interesting question a caller has is not "will you accept sloppy input" but "which of the two incompatible normalizations am I in", and a door named for leniency answers the wrong one.

## 4. Segmentation: enumeration versus composition

### The complaint

[panphon #63](https://github.com/dmort27/panphon/issues/63) (2025-04-15, open) asks how diphthongs are handled, having found `kaʊ` and `ka͡ʊ` both come back as three segments while `t͡ʃuːz` comes back as three with the affricate intact. Three users have commented. The last, 2025-10-06, states the workaround: no robust one found, and they were treating diphthongs as two vowels.

Measured on panphon 0.22.2, the asymmetry is exact and its cause is structural:

```
ipa_all.csv rows: 6367;  rows containing a tie bar: 1472
  t͡s  in table=True   ipa_segs=['t͡s']
  t͡ɸ  in table=False  ipa_segs=['t', 'ɸ']
  a͡ɪ  in table=False  ipa_segs=['a', 'ɪ']
```

The tie bar is not an operator. It is a literal character inside 1,472 enumerated strings, so a tie works exactly when somebody wrote that unit down. No vowel–vowel tie is in the table at all, which is why every diphthong splits — and why `t͡ɸ`, an ordinary affricate, splits too. Extending the list to cover diphthongs would not change the shape; it would enumerate one more region of a space that composes.

The same boundary shows up as diacritics. [panphon #5](https://github.com/dmort27/panphon/issues/5) (2017-06-07) reports symbols from disordered-speech transcription that the table does not carry. Measured today they still do not round-trip:

```
'p̪' segs=['p']   'z̥' segs=['z']   'ə̊' segs=['ə']   'sˡ' segs=['s']
word_fts('p̪') -> 1 segment; warnings: 0
```

`validate_word` returns `False` for each; `word_fts` does not, so the labiodental mark disappears and the caller receives a plain `p`. That is §3's shape on a different character class.

The reply on that issue is a design statement rather than a deflection: it explains which requested symbols would work if written with a tie bar and which would require relaxing a feature co-occurrence rule. The table is a curated set with constraints, and the cost of a curated set is that it ends somewhere.

### The critique exists in the literature, stated generally

This is not only a tracker complaint. "Generating Feature Vectors from Phonetic Transcriptions in Cross-Linguistic Data Formats" (SCiL 2024, <https://aclanthology.org/2024.scil-1.19/>) makes it the motivation for a whole system:

> all feature collections are fixed sets of sounds, lacking a dynamic component. This limits their potential when applying them to newly compiled datasets, since whenever a sound in a given dataset is not attested in the feature systems, users would have to add it or to label it as missing data.

> While this may seem to reflect a minor problem, it has grown into a major obstacle for many concrete applications in computational comparative linguistics, since practical experience in working with concrete language data clearly shows that meeting unobserved sounds when turning to new datasets is rather the rule than the exception

**"Rather the rule than the exception" is the finding this section exists to record**, and it is a published, peer-reviewed statement of exactly the enumeration boundary measured above. The paper's own answer is a rule system that derives a vector for an unlisted sound rather than looking it up — the same move ipakit's composition makes, arrived at independently and for the same reason.

The workarounds appear in methods sections, and they are consistent. A clinical-speech shared task (RaPID 2022, <https://aclanthology.org/2022.rapid-1.6/>) reports that neither panphon nor the textbook feature system it worked alongside defines features for diphthongs, so the authors synthesized those definitions themselves and then needed special rules in their error calculation to accommodate them. A 2026 ACL paper reports "Annotated segments incompatible with PanPhon are manually fixed" and "We fix misplaced diacritics that were incorrectly attached to adjacent phones in four languages." A loanword-detection paper (COLING 2022, <https://aclanthology.org/2022.coling-1.442/>) reports that "Panphon does not contain suprasegmental or tonal information which may explain why alignment logits involving tonal languages such as Chinese may not sufficiently encode articulatory features."

### Does ipakit have this problem?

No, and the difference is the mechanism rather than the coverage:

```
t͡ɸ  -> ['t͡ɸ']  'voiceless bilabial affricate'
a͜ɪ  -> ['a͜ɪ']  one unit
q͡χ  -> ['q͡χ']  'voiceless uvular affricate'
ŋ̥   -> ['ŋ̥']   one unit
```

Ties compose, so a unit nobody enumerated still reads. **ipakit's tie is an operator and panphon's is a character**, and that one sentence explains most of the difference in what the two will accept. It belongs in interop material; it is recorded here because it is the answer to a question that has been open in panphon's tracker since April 2025.

## 5. The raised diacritics — where ipakit is the one with the gap

### The complaint

[phoible/dev #225](https://github.com/phoible/dev/issues/225) (2019-05-10, open, 5 comments) asks PHOIBLE to stop supporting both the superior and inferior devoicing ring, pointing out that `j̊`/`j̥` and `ŋ̊`/`ŋ̥` are pairs of spellings for one sound. The discussion is the interesting part. One maintainer is against admitting the raised forms as synonyms; another cites the project's own published position, that the IPA states diacritics may be placed above a symbol with a descender. The thread also records that PHOIBLE *contains* segments spelled with the raised ring — a click series `ŋ̊ǀ ŋ̊ǁ ŋ̊ǂ ŋ̊ǃ` in one inventory. Seven years open, which is the honest state of a question with two defensible answers.

### Does ipakit have this problem?

**Yes, in the strict direction, and it was a real gap — now closed; see the note at the reproducing case below.** Measured against the worktree this survey read:

```
COMBINING RING BELOW           U+0325 registered=True
COMBINING RING ABOVE           U+030A registered=False
COMBINING VERTICAL LINE BELOW  U+0329 registered=True
COMBINING VERTICAL LINE ABOVE  U+030D registered=False

'ŋ̊'  tok=['ŋ']   validate=['unknown_symbol']  warns=1
'ɡ̊'  tok=['ɡ']   validate=['unknown_symbol']  warns=1
'ŋ̍'  tok=['ŋ']   validate=['unknown_symbol']  warns=1
'ŋ̥'  tok=['ŋ̥']  validate=[]                  warns=0
```

A transcription written the way the IPA prescribes for glyphs with descenders loses its voicelessness or its syllabicity, and a PHOIBLE inventory containing `ŋ̊ǀ` cannot be read. It is reported rather than silent — the warning fires and `validate_ipa` names the symbol — which is §3's mitigation working as designed. But the mark is still gone from the unit.

**This is not the lookalike case and must not be fixed as one.** `U+0325` and `U+030A` are not a keyboard character standing in for an IPA symbol; they are two spellings the IPA itself sanctions, distinguished by the shape of the base glyph. Putting `U+030A -> U+0325` in `lookalikes.xml` would place a chart-proper spelling behind the wild-import door, where a caller doing strict IPA work would never find it. The declaration belongs in the inventory, conditioned the way the IPA conditions it.

Two things make this more than a missing row. **It is a class, not a character** — at minimum `U+030A` (voiceless) and `U+030D` (syllabic), and whether the class is closed is a question about the inventory whose answer should be derived from the declared marks rather than typed out. And **the base-glyph condition is data, not code**: "above when the base has a descender" is a fact about `ŋ ɡ ɟ j ɥ ɰ`, and a hardcoded list of those would be the second copy of the inventory that `test_declared_not_hardcoded.py` exists to prevent.

**Superseded, and closed. Recommendation (a) below was taken: the voicelessness ring and the syllabicity line are declared in the inventory as `alias` spellings of the below forms — `<diacritic name="̥" … alias="̊">` and `<diacritic name="̩" … alias="̍">` in `ipakit/data/ipa.xml` — conditioned on nothing but being the same mark, which is how the IPA means them. Refusal (g) was honored: no `lookalikes.xml` soft read was added, so a caller doing strict IPA work reaches these without going through the wild-import door. The reproducing case below now reads them.**

Reproducing case, now accepting the raised spelling:

```python
import ipakit
ipakit.tokenize("ŋ̊")        # ['ŋ̥'] — the raised ring composes to the voiceless mark, no warning
ipakit.validate_ipa("ŋ̊")    # [] — accepted
ipakit.tokenize("ŋ̥")        # ['ŋ̥'] — the same sound, the other spelling, fine
```

Not applied in this lane.

## 6. Two segments, one feature vector

### The complaint

Four open issues on `phoible/dev` report distinct segments sharing an identical feature vector: [#348](https://github.com/phoible/dev/issues/348) (2022-01, `/kp/` and `/pˠ/`), [#352](https://github.com/phoible/dev/issues/352) (2022-03, `ə` and `ɜ`), [#369](https://github.com/phoible/dev/issues/369) (2023-12, `s̪` and `s̻`), [#372](https://github.com/phoible/dev/issues/372) (2024-02, `t̠ʃʼ` and `d̠ʒʼ`). On #348 the reply is that it is not by design. On #352 the reply is more useful: the problem is acknowledged as *pervasive*, and the causes are given — no features for tone, some source documents collapsing distinctions, clicks being hard to specify with the feature set, plain mistakes, and the feature set itself needing updating. That is a project describing its own limits accurately in public, which is the most one can ask.

Nobody in those threads counted it, so this lane did, over PHOIBLE's published segment-feature table (2,162 segments, 37 feature columns, fetched 2026-08-02):

```
distinct feature vectors: 1642
vectors shared by more than one segment: 319
segments not uniquely identified by their vector: 839 of 2162 (38.8%)
  largest group (41): every tone mark  ˦ ˨ ˧ ˥ ˩ ˦˨ ˨˦ ...
  next (8): ə ɜ ɪ̈ ë ï ä ë̞ ɑ̈
  next (8): kǃʼ kǁʼ kǁxʼ kǃxʼ kǃʰʼ k‼ʼ k‼ʰʼ k‼xʼ
```

The single largest cause is the one named first in that reply: **the feature system has no dimension for tone**, so all 41 tone marks are one vector. Excluding them, 788 of 2,110 segments still share a vector.

### It is worse in panphon, and for a reason that connects back to §4

The same measurement over panphon 0.22.2's `ipa_all.csv`:

```
6367 segments, 24 feature columns
distinct feature vectors: 3010 (47.3%)
segments not uniquely identified by their vector: 4769 of 6367 (74.9%)
largest equivalence class: 20   ɠʲ ʛʲ ɡ̰ʲ ɠ̰ʲ ɢ̰ʲ ʛ̰ʲ ɡ̰ˠ ɠ̰ˠ ɢ̰ˠ ʛ̰ˠ ɠˠ ʛˠ ɡ̰ ɠ̰ ...
```

**Three quarters of panphon's segments cannot be told apart by the vectors panphon exists to produce.** A downstream paper reports the same effect from the other side, collapsing the table to distinct vectors and getting 3,293 representatives where this measurement gets 3,010 — close, not identical, and the discrepancy is unexplained; possibly a different version or a different post-cleanup table. Both numbers should be treated as approximate.

The cause is §4's cause. Enumeration adds rows faster than a fixed feature set adds dimensions, so `ɡ̰ʲ` and `ɠˠ` end up identical because creaky voice, implosion, palatalization and velarization are not all separately encoded in the 24. **The collapse is not a data-entry problem to be fixed row by row; it is what happens when a table grows past what its columns can distinguish.** That is the strongest argument in this survey for deriving a unit's features from its parts rather than looking the whole unit up.

### Tone has no home in any of them, and all three say so

The convergence is worth stating on its own because it is the one thing every system in this survey agrees on. panphon's own paper is explicit that this is a design choice and not an oversight:

> PanPhon is segmental by design and tone is suprasegmental by nature.

The surrounding sentence concedes that non-linear representations "hold the upper hand" here, and the section opens by saying the goal "was not to implement a state-of-the-art feature system (from the standpoint of linguistic theory) but to develop a methodologically solid resource that would be useful for NLP researchers". **A limitation a project states about itself in its own paper is a design boundary, and criticizing it as a defect would be a misreading.**

PHOIBLE has no tone features, which is why all 41 of its tone marks share one vector. ipakit has tone and contour and deliberately keeps them off the feature bundle, so its prosodic marks collide there too — 3,624 corpus units, below. **Three systems, three different mechanisms, one shared consequence: a caller comparing segmental feature vectors alone will conflate things that differ in tone.** For ipakit the mitigation is that the information exists on the unit and the metric is not the only reader; for the other two it does not exist at all. That difference is worth stating in interop material, because a round trip through either will lose it.

### Does ipakit have this problem?

**Partly, and the honest answer needs two measurements rather than one.**

Over the 139 registered phones, **4 phones fall into 2 groups sharing an identical `get_features()` bundle**: `a͜ɪ`/`a͜ʊ` and `e͜ɪ`/`e͜ə`. Over all pairs of registered phones, **0 pairs are at distance 0.0**. The metric separates everything the inventory registers; the collapse is confined to the flat scalar read, and `describe` reads the same projection — where it is wider, covering **6 groups and 14 phones**:

```
['a',  'a͜ɪ', 'a͜ʊ']  'open front unrounded vowel'
['e',  'e͜ɪ', 'e͜ə']  'close-mid front unrounded vowel'
['o',  'o͜ʊ']         'close-mid back rounded vowel'
['ɔ',  'ɔ͜ɪ']         'open-mid back rounded vowel'
['ɪ',  'ɪ͜ə']         'near-close near-front unrounded vowel'
['ʊ',  'ʊ͜ə']         'near-close near-back rounded vowel'

feature_values("a͜ɪ") == feature_values("a͜ʊ")  False
distance("a͜ɪ", "a͜ʊ")  0.0265
```

Every chained diphthong shares a description with its own nucleus, so `describe("o͜ʊ")` and `describe("o")` are one sentence. **This is deliberate, documented and guarded**, which the first draft of this section got wrong: `scripts/invariants.py:check_descriptions` asserts that no two distinct phones share a description, with a stated exception — "an atomic vowel and the diphthongs built on it, whose flat projection is that vowel by design". The flat read is the nucleus on purpose, the tuple read and the metric distinguish the diphthongs, and `make check` holds the line. Not a defect.

**The defect is in the exception, and it is the shape [reviewing.md](../reviewing.md) calls a guard that no longer guards.** The predicate is much wider than the sentence describing it. Reproduced by evaluating it directly:

```
members        kinds                     exception excuses them?
['a', 'a͜ɪ']    {'atomic', 'diphthong'}   True     <- intended
['a͜ɪ', 'ɔ͜ɪ']   {'diphthong'}             True     <- two diphthongs, no shared nucleus
['a', 'e']     {'atomic'}                True     <- two plain vowels
['p', 't']     {'atomic'}                True     <- two consonants
```

The second conjunct is tautological — it compares the member count against the members whose kind is in a set built from those same members, so it is `True` for every input — leaving the test as `kinds <= {"atomic", "diphthong"}`. Since a plain consonant is `atomic`, **two consonants sharing a description would be excused by an exception written for vowels**, and the guard would report success. Nothing in the inventory triggers it today, which is exactly why it reads as protection.

Reproducing case, for whoever picks it up:

```python
from ipakit.features import IPAFeatures
ipa = IPAFeatures()
members = ["p", "t"]                                  # neither is a vowel
kinds = {ipa.segment(m).kind.value for m in members}  # {'atomic'}
kinds <= {"atomic", "diphthong"}                      # True -- excused
```

The fix is the one that document prescribes: state the shape of the mistake rather than today's offenders. The exception wants to say *a group is excused only when exactly one member is atomic and every other member is a diphthong whose nucleus is that member* — which is checkable from the segment structure, and which no group of consonants can satisfy. Reported, not applied; `ipakit/` and `scripts/` are read-only to this lane.

The corpus-scale number needs its qualification in the same breath or it misleads. Over the canonical corpus (8,616 units), **4,648 units share a flat bundle with another unit** — 53.9%, worse than PHOIBLE's 38.8% if the two are set side by side. They should not be. Decomposing:

- **3,624 differ only by a prosodic mark** — length `ː ˑ ̆`, the five tone bars, the tone accents, the six compound contour marks, the two global marks, each appearing on 116 bases. Prosody lives on the unit and not in the feature bag by documented design ([ties.md](../ties.md)), so these are not collisions in PHOIBLE's sense. They are the bundle correctly declining to answer a question about the unit.
- **1,024 involve a tie bar**, and that is the substantive residue: the diphthong head-leg read above, multiplied across every mark that composes with it.

The like-for-like comparison is the first measurement, not the second: 4 of 139 against 839 of 2,162. **The convergent finding is more interesting than either number** — in both systems a large part of the collapse is prosody having nowhere to go in a segmental vector. PHOIBLE has no tone features and says so; ipakit has tone and contour and deliberately keeps them off the bundle. Two answers to the same structural fact, and both mean a caller comparing feature vectors alone will conflate things.

## 7. What g2p and TTS front-end builders ask for

### The complaint that is real: "what is the phone set?"

Across the surveyed trackers, **10 issues ask how to enumerate the set of phones a tool can emit**, spanning three projects and 2019 to 2025:

| repository | issues |
|---|---|
| `espeak-ng/espeak-ng` | [#769](https://github.com/espeak-ng/espeak-ng/issues/769) (2020-05), [#1050](https://github.com/espeak-ng/espeak-ng/issues/1050) (2021-12), [#1216](https://github.com/espeak-ng/espeak-ng/issues/1216) (2022-06), [#1864](https://github.com/espeak-ng/espeak-ng/issues/1864) (2024-02), [#2236](https://github.com/espeak-ng/espeak-ng/issues/2236) (2025-07) |
| `bootphon/phonemizer` | [#118](https://github.com/bootphon/phonemizer/issues/118) (2022-04), [#131](https://github.com/bootphon/phonemizer/issues/131) (2022-06), [#184](https://github.com/bootphon/phonemizer/issues/184) (2024-11), [#206](https://github.com/bootphon/phonemizer/issues/206) (2025-07) |
| `dmort27/epitran` | [#27](https://github.com/dmort27/epitran/issues/27) (2019-05) |

Two are open. The question keeps being asked because a front-end builder cannot do the next thing without it: you cannot build a pronunciation lexicon, size an embedding table, or write a phone-set mapping without the list. Near relatives: [panphon #7](https://github.com/dmort27/panphon/issues/7) (2017-12, "What is the IPA that panphon accepts?"), [Kyubyong/g2p #29](https://github.com/Kyubyong/g2p/issues/29) (2022-01, "What is each phoneme in IPA terms?"), and [allosaurus #40](https://github.com/xinjli/allosaurus/issues/40) (2021-09, open, 11 comments), where a user asks what the emitted symbols actually sound like, is pointed at an IPA chart on the web, and separately observes that espeak-ng gives different IPA characters for the same language.

That last thread is two requirements at once: **enumerate the inventory, and say what each member is.** ipakit answers both — `phones` is a list, `describe` is a sentence, `phones_matching` is a query over the same data, and the tract figure is the picture the user was sent to a website for. This is the strongest positive finding for the speech-technology audience in the survey, and it did not arrive as a feature request; it arrived as people asking a question their tools could not answer.

### The complaint the brief expected, which does not hold as stated

The hypothesis put to this lane was that debugging is the recurring g2p pain — a synthesizer mispronounces a word and there is no way to see which rule fired — and that ipakit's derivation trace answers it.

**Measured, the pattern is the opposite of what was predicted, for a reason that is good news.** espeak-ng already ships a rule trace, verified locally 2026-08-02:

```
$ espeak-ng --help | grep -- -X
-X    Write phonemes mnemonics and translation trace to stdout
$ espeak-ng -q -X -v en-us "grandma"
Found: 'grandma' [grandmA:]
```

So in the dominant open TTS front end the affordance exists, and the complaints in its tracker are correspondingly not "show me the rule" but "this word is wrong" — 43 of 1,126 issues name an incorrect IPA or pronunciation in the title. Searching titles and bodies across all sixteen trackers for the shape of the request ("which rule", "what rule fired", "trace", "intermediate result", "step by step") returns nothing in the g2p corpus that survives excluding Python tracebacks.

**Where the request is real is in sound-change appliers**, and there both tools built it:

- [Lexurgy #32](https://github.com/def-gthill/lexurgy/issues/32) (2021-04, open): a request for a function reporting which rules apply, plus a count of words changed. Lexurgy has per-word tracing — [#55](https://github.com/def-gthill/lexurgy/issues/55), [#62](https://github.com/def-gthill/lexurgy/issues/62), [#80](https://github.com/def-gthill/lexurgy/issues/80) are all about improving it — so #32 is asking for the aggregate view over a lexicon, not the per-word one.
- [Brassica #8](https://github.com/bradrn/brassica/issues/8) (2025-11, closed): a feature request for a debug mode showing intermediate results of each change on a given word.

**The correction to the brief is twofold.** A rewrite trace is not an unmet need in g2p; it is table stakes the incumbent meets. It *is* a voiced need in rule engines, and the request still open there is not the per-form trace ipakit has — it is the **aggregate**: which rules fired at all, over how many forms. `Derivation.trace()` answers one form. Nothing surveyed answers the corpus, and it was asked for five years ago.

### Ergonomics: the dependency is the install

Transitive Python dependency counts, measured 2026-08-02 with `pip install --dry-run --report`:

| package | distributions installed |
|---|---:|
| `ipapy` | 1 |
| `ipakit` | 1 |
| `phonemizer` | 5 |
| `panphon` | 11 |
| `epitran` | 19 |
| `segments` | 19 |
| `pyclts` | 39 |

The number to distrust is phonemizer's. Its five wheels are cheap and its real dependency is espeak-ng, a system binary, accounting for 12 of its 170 issues; epitran's English path has the same shape with flite, 9 issues. **The painful dependency is the one pip cannot install**, and a Python-only count of a wrapper flatters it. ipakit shipping its phonetic data as XML inside the package is on the right side of that line, and the reason is not the wheel count — it is that there is no second artifact to fail to find.

## 8. The teaching audience

The instructional side is not served by the tools above, and its own tools are in worse shape than their maintenance dates suggest. Two findings, both sourced to the projects' own documentation.

**OTSoft cannot represent IPA.** Its manual (version 2.5, April 2021), §4.4, verified verbatim:

> Phonetic fonts are supported in the older OTSoft 2.3.3, still available on the OTSoft website. They are not supported by the current OTSoft, so you will have to use ad hoc symbols like "?" for [ʔ] or "S" for [ʃ].

The page is dated 2026-02-24, so this is current rather than archival. **This is the most direct evidence in the survey that the teaching audience is unserved**: a phonology tool still being updated asks its users to invent an ASCII transliteration of the IPA by hand, per user, per project, checked by nobody. An ASCII notation for an inventory is exactly what a phonemap is, and [samprosa.md](samprosa.md) already sets the standard one has to meet here — derived and validated, so `make check` can guard it rather than a person remembering.

**The platform requirement is met by walking to a lab machine.** A computing-assignment handout for a 2015 graduate phonology course, verified verbatim:

> Follow the instructions at [the OTSoft page]. Sadly, the software works only in Windows. If you are a Mac person, you'll need to use one of the department computers (many already have OTSoft installed, but make sure it's the latest version).

The same handout tells students that one option "sometimes makes the program crash afterwards. Just restart the program." A departmental lab machine as the documented workaround for a phonology assignment is a requirement statement, and the requirement is **runs where the student is**.

The manual is candid about why this persists, §16.1:

> I would love to make OTSoft open source, so anyone who wanted to could add to its capacities. Unfortunately, the wonderful programming language that I employed to write it (ca. 1994), namely Visual Basic, was cruelly abolished by Microsoft long ago.
> Many people over the years have offered to convert OTSoft into an extant programming language; all have been defeated by the size of the task (thousands of lines of code).

That is a project stating its own limit accurately, and it is the strongest available argument for minimizing ipakit's pure-Python dependency surface: portable dependencies have no native port to be defeated by.

Two supporting observations, both about reading maintenance signals correctly. Praat's Optimality Theory *code* is alive (a release dated 2026-06-30, grammar-module commits in late 2025) while its OT *tutorial* dates from 2007 — **stale documentation is not evidence of abandoned software**, and the inference should not be made in either direction without checking both. And OT-Help 2.0 cannot be installed as documented: its required linear-programming library returns 403 from the only host that ever served it, the vendor domain is dead, and no archived copy exists. That is documentary rather than runtime evidence — no JRE was available to attempt a run.

**Does ipakit have this problem?** Not the platform one. The IPA-representation one is worth checking in the other direction: OTSoft's users need an ASCII encoding of a phonological inventory for a tool that cannot take Unicode, and [samprosa.md](samprosa.md) already establishes the standard such a table must meet — derivable and validatable, so `make check` can guard it. The ARPABET, X-SAMPA, Kirshenbaum and TIMIT tables ipakit ships are the shape of that answer. Whether any of them is the *right* answer for tableau software was not investigated here.

## 9. The conlang audience

The sound-change appliers are the best-evidenced tools in the survey for one reason: their users are unusually articulate about workarounds, and the workaround is the same one every time.

**Nobody ships an IPA feature inventory, so users hand-maintain codepoint lists.** In a Zompist Bulletin Board thread dated 2024-06-06 the question was put directly — do any sound change appliers come with a set of feature definitions, given that a standard IPA chart has perhaps four dozen — and **no participant named one**. The consequence is visible in the same forum: a 2021-04-11 post publishes fourteen hand-maintained vowel categories totalling **80 distinct codepoints**, four macro-categories of forty each, together with the constraint that forces it — the tool requires precomposed characters, so a mark written as a combining sequence is processed as two separate characters and the categories must be written out.

That is a natural class, spelled by enumeration, maintained by a person, because the tool has no features. It is the same failure mode as §4's segment table, arriving in a different community, and it is the clearest single statement in the survey of what a shipped feature inventory is worth. `phones_matching` and the natural-class machinery answer it directly.

**The tools themselves say IPA input is somebody else's problem.** Lexurgy's tutorial tells users it works in Unicode and they "just need a way to enter them", pointing at a third-party site or a keyboard layout. SCA²'s entire IPA support is a clipboard palette: "**IPA** will post a set of IPA and other useful Unicode characters to the Output area." **Neither dominant tool in this community is IPA-first**, which materially changes what interop with them would mean.

**SCA²'s documentation states its limits precisely**, which is worth crediting since §3's theme is projects that do not. Verified verbatim from its help page:

> Variables can only be one character long (unless you use rewrite rules).
> If you use digraphs, you must follow the rules in this section. SCA² won't handle digraphs properly on its own.
> ... so they operate quickly, the rewrite rules are global and non-contextual.

Category mapping is positional rather than featural: "In this usage, the variables must correspond one for one — p goes to b, t goes to d, etc." There is no feature system, no syllable object and no normalization step. These are absences, not refusals, and the page has stated them since 2012.

**A design position worth recording, because it is the argument against ipakit's approach**, from the same 2024 thread, by the author of one of the three appliers:

> I think I can more concretely identify what I dislike about feature systems à la Lexurgy: they're not atheoretic enough. I've always wanted Brassica to be independent of any phonological theory, acting only on lists of characters and producing lists of characters as output.

That is a coherent objection and it is not answered by pointing at a better feature system, because the objection is to having one. It is the same trade [braces.md](braces.md) works through in a different setting: expressive power bought with a theoretical commitment. A tool aimed at this community has to decide whether it is selling the commitment or hiding it, and ipakit is unambiguously selling it — the features are the product.

**Access caveat.** Reddit could not be reached by any sanctioned path; the r/conlangs material behind the counted claims above was read through a third-party mirror and the reconstructed URLs were not verified against reddit.com, so no Reddit citation appears in this document. The Zompist Bulletin Board material was read directly from source HTML. The CONLANG-L archive at its long-standing host has been retired and no material from it was obtained.

## 10. The articulatory hole

### Is it real?

**Yes, as far as this lane could establish, and the shape is specific: everything either measures articulation or synthesizes from it, and nothing maps symbols to it.**

The symbolic side has no tract model. panphon's 24 features are SPE-style distinctive features — `syl son cons cont delrel lat nas strid voi sg cg ant cor distr lab hi lo back round velaric tense long hitone hireg` — phonological categories, not geometry. `hi`/`lo`/`back` name tongue-body positions the way SPE does, without a location or a degree. PHOIBLE's 37 columns are the same kind of object.

The articulatory side does not take symbols in. SPARC ([Berkeley-Speech-Group/Speech-Articulatory-Coding](https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding); *Coding Speech through Vocal Tract Kinematics*, IEEE JSTSP 18(8), December 2024, <https://arxiv.org/abs/2406.12998>) encodes audio to a 12-dimensional EMA trace plus source features. Its README gives the dimensions exactly:

```
"ema": (L, 12) array,  # TDX TDY TBX TBY TTX TTY LIX LIY ULX LLX ULY LLY
"loudness", "pitch", "periodicity", "pitch_stats", "spk_emb"
```

Those are **pellet coordinates in a speaker's own frame**, inferred from audio at 50 Hz. They are a measurement of a token, not a specification of a type. There is no entry point taking `/t/` and returning where the tongue tip should be.

VocalTractLab (<https://www.vocaltractlab.de/>, GPL since 2.3, version 2.4 dated 2025-12-05) is the synthesis side: driven by gestural scores and speaker files, offering GUI, API, manuals and gestural score examples, and **not mentioning IPA input**. Version 2.4 is Windows; VocalTractLab3D adds Linux.

So the two ends exist and the middle does not. A researcher wanting a canonical articulatory target for a phone — as opposed to a measured trace of one utterance of it — has to write the table.

**Read this as a finding with a caveat.** Web search was unavailable for this part of the lane, so it rests on repositories and pages reachable directly. TADA, ArtiSynth and the Praat articulatory synthesizer were not reached and are not characterized. If one of them provides an open IPA-to-tract-variable map, this section is wrong, and that would be the most valuable correction anyone could return to it.

### What ipakit already emits

`ipakit.tract` answers in the Articulatory Phonology shape rather than the EMA one:

```
t:  glottal_aperture=1.0    velic=0.0   TractPoint(arc=0.13, offset=1.0, articulator='tongue-tip')
k:  glottal_aperture=1.0    velic=0.0   TractPoint(arc=0.45, offset=1.0, articulator='tongue-dorsum')
s:  glottal_aperture=1.0    velic=0.0   TractPoint(arc=0.13, offset=0.8, articulator='tongue-tip')
m:  glottal_aperture=0.333  velic=1.0   TractPoint(arc=0.00, offset=1.0, articulator='lower-lip')
ʔ:  glottal_aperture=0.0    velic=0.0   TractPoint(arc=1.00, offset=1.0, articulator='vocal-folds')
i:  glottal_aperture=0.333  velic=0.0   TractPoint(arc=0.32, offset=0.38, articulator='tongue-dorsum')
```

Constriction location, constriction degree, and the responsible articulator, per phone, plus velic and glottal aperture — the tract-variable decomposition, read off the same declared data as the features and the metric. `t` and `s` share a location and differ in degree, which is what the distinction is.

**Two honest qualifications.** These are canonical targets, not measurements: no speaker, no time course, no coarticulation. And they are declared rather than fitted, so their agreement with a real tract is a separate question — one [articulatory-data.md](../articulatory-data.md) exists to answer, and which no amount of internal consistency can settle.

That is why the two sides are complementary rather than competing. SPARC gives measured, speaker-specific, time-varying traces with no symbolic entry point; ipakit gives a symbolic entry point with canonical, speaker-free targets. The join — supervising or interpreting an inferred trace against a declared target — is what neither provides.

One piece of corroborating evidence that the visualization half is wanted: SPARC's tracker has four issues, and [#2](https://github.com/Berkeley-Speech-Group/Speech-Articulatory-Coding/issues/2) (2025-06-03, open) asks for the code behind the demo page's articulatory animations, or "some other way to visualize the data as mouth/face animation rather than plotting the values over time". One request is one request and nothing should be built on it alone. But it is the want ipakit's sagittal figure serves, arriving unprompted in the tracker of the tool that has the data and not the picture.

## 11. Where the low-resource complaints land

The complaints separate into three kinds and only one is ipakit's to answer.

**The inventory does not match the language.** Allosaurus [#1](https://github.com/xinjli/allosaurus/issues/1) and [#77](https://github.com/xinjli/allosaurus/issues/77); epitran's 29 language-specific issues. This is a data problem in somebody's lexicon or model and ipakit cannot fix it. What ipakit can do is make the mismatch *visible*: a phone set that can be enumerated and compared, and a validator that names what it did not recognize, turn "the output looks wrong" into "these six symbols are not in that inventory".

**The transcription is not chart IPA.** Allosaurus [#14](https://github.com/xinjli/allosaurus/issues/14) asks for symbols beyond IPA; panphon [#5](https://github.com/dmort27/panphon/issues/5) brings disordered-speech transcription; PHOIBLE's tracker carries `U+0347` used as a feature marker in two source databases ([#321](https://github.com/phoible/dev/issues/321), 2020-11, open). Field and clinical transcription routinely uses marks a strict reader refuses. **ipakit's answer is the supplement mechanism plus `<notations>`**, and the relevant property is the one [supplements.md](../supplements.md) states: adding a supplement can only turn a `None` into an answer. A field project can declare its own symbols without editing the shipped inventory and without moving anybody else's distances. That is the right shape for this audience and it is already built.

**The encoding breaks.** Allosaurus [#73](https://github.com/xinjli/allosaurus/issues/73) (2022-12, open) is a `UnicodeEncodeError` on `ː` writing output on Windows; panphon [#55](https://github.com/dmort27/panphon/issues/55) (2024-08, open) is an encoding error on Windows; epitran [#188](https://github.com/dmort27/epitran/issues/188) (2025-01, open) is a `charmap` decode error. Three projects, three open issues, one cause: a non-UTF-8 default codepage meeting IPA. Nothing in ipakit's design prevents this in a *caller's* output path, and it is worth checking that nothing in ipakit's own file reads or writes relies on the platform default encoding. Not checked in this lane.

## 12. What follows

Seven things, in the order they should be considered. None was applied here.

**(a) Register the raised diacritic variants. — Done.** §5. `U+030A` and `U+030D`, declared in the inventory as `alias` spellings rather than mapped in `lookalikes.xml`. This was the one place the survey found ipakit refusing chart-proper IPA, and a PHOIBLE inventory it could not read; `ŋ̊` now reads `['ŋ̥']`.

**(b) Narrow `check_descriptions`' exception to what its docstring says.** §6. Its second conjunct is tautological and the first admits every atomic phone, so an exception written for a vowel and its diphthongs currently excuses `['p', 't']`. State the shape instead: exactly one atomic member, every other member a diphthong whose nucleus is that member. This is the only outright defect the survey found in ipakit, and it was found by cross-checking a measurement against the suite rather than by reading either.

**(c) Describe `from_wild` as choosing a convention, not as being lenient.** §3. PHOIBLE and CLTS normalize `g` in opposite directions and CLTS deletes tie bars outright, so the question a caller actually has is which normalization they are in. A door named for leniency answers the wrong question, and a caller who does not know their corpus is BIPA will get `t͡s` as two segments with no diagnostic — correctly, and disastrously.

**(d) An aggregate trace over a corpus.** §7. `Derivation.trace()` answers one form; the request open for five years in a neighboring tool is which rules fired across a lexicon and over how many forms. It is the relationship `scripts/sweep.py diff` has to a single unit, and it probably belongs in `scripts/` for the same reason.

**(e) Check the encoding path.** §11. Three projects have an open Windows encoding issue against IPA output; whether ipakit's own reads and writes name their encoding explicitly is a two-line check and was not run here.

**(f) Say that the tie is an operator.** §4. One sentence, in interop material rather than here, because it explains most of the difference between what ipakit and panphon accept and a reader comparing them would otherwise have to derive it.

**(g) Do not add a soft read for `U+030A`. — Honored.** Recorded as a refusal, because it is the obvious wrong fix for (a) and someone will propose it. (a) landed as an inventory `alias`, not a `lookalikes.xml` soft read, so strict IPA work reaches it directly.

## Sources

Issue trackers, all read through the GitHub API on 2026-08-02: `dmort27/panphon`, `dmort27/epitran`, `bootphon/phonemizer`, `cldf/segments`, `cldf-clts/pyclts`, `pettarin/ipapy`, `phoible/dev`, `xinjli/allosaurus`, `def-gthill/lexurgy`, `bradrn/brassica`, `PhonologicalCorpusTools/CorpusTools`, `espeak-ng/espeak-ng`, `roedoejet/g2p`, `EveryVoiceTTS/EveryVoice`, `ReadAlongs/Studio`, `lingjzhu/CharsiuG2P`, `Kyubyong/g2p`, `Berkeley-Speech-Group/Speech-Articulatory-Coding`.

- Unicode UTS #39 confusables, v17.0.0, dated 2025-07-22: <https://www.unicode.org/Public/security/latest/confusables.txt>
- PHOIBLE conventions: <https://phoible.github.io/conventions/>
- PHOIBLE segment feature table: <https://raw.githubusercontent.com/phoible/dev/master/raw-data/FEATURES/phoible-segments-features.tsv>
- CLTS/BIPA normalization table: <https://raw.githubusercontent.com/cldf-clts/clts/master/pkg/transcriptionsystems/bipa/normalize.tsv>
- *Coding Speech through Vocal Tract Kinematics*, IEEE Journal of Selected Topics in Signal Processing 18(8), December 2024: <https://arxiv.org/abs/2406.12998>
- *PanPhon: A Resource for Mapping IPA Segments to Articulatory Feature Vectors*, COLING 2016: <https://aclanthology.org/C16-1328/> — the tone limitation quoted in §6 is its own §3.
- *Epitran: Precision G2P for Many Languages*, LREC 2018: <https://aclanthology.org/L18-1429/>
- *Generating Feature Vectors from Phonetic Transcriptions in Cross-Linguistic Data Formats*, SCiL 2024: <https://aclanthology.org/2024.scil-1.19/> — the fixed-set critique quoted in §4.
- *The Unicode Cookbook for Linguists: Managing writing systems using orthography profiles*, Language Science Press 2018, open access: <https://langsci-press.org/catalog/book/176> — §5.5, quoted in §3. Two DOIs circulate for this work; the publisher's recommended BibTeX gives 10.5281/zenodo.1296780.
- Methods-section workarounds quoted in §4: RaPID 2022 <https://aclanthology.org/2022.rapid-1.6/>; COLING 2022 <https://aclanthology.org/2022.coling-1.442/>.
- Citation counts are from Semantic Scholar's by-identifier endpoint, 2026-08-02: panphon `ACL:C16-1328` 179, epitran `ACL:L18-1429` 184.
- VocalTractLab: <https://www.vocaltractlab.de/>
- OTSoft, page dated 2026-02-24: <https://brucehayes.org/otsoft/>; manual quoted above: <https://brucehayes.org/otsoft/OTSoftManual_2.5_April_2021.pdf>. The quoted computing-assignment handout, dated 24 November 2015: <https://linguistics.ucla.edu/people/zuraw/219_2015/H04OTSoftInstructions.pdf>. Both PDFs were extracted to text and the quotations checked against the extraction; `OTSoftManual.pdf` without the version suffix is a 404.
- SCA² documentation: <https://www.zompist.com/scahelp.html> (page dated 2012, last modified 2020-05-28). The URL `zompist.com/sca2doc.html` does not exist.
- Zompist Bulletin Board, read from source HTML at <https://www.verduria.org/>
- Package versions on PyPI as of 2026-08-02: panphon 0.22.2 (2025-06-12), epitran 1.35.2 (2026-06-18), phonemizer 3.4.0 (2026-07-31), segments 2.4.0 (2026-03-07), pyclts 4.0.2 (2026-06-09), ipapy 0.0.9.0 (2019-05-05).

**Read at one remove, and labeled as such where used:** the *Unicode Cookbook* §5.5 passage in §3 is quoted from the Cookbook, whose own citation to the IPA Handbook (1999: 19) was not checked against the Handbook. The two Zompist Bulletin Board items in §9 are dated and attributed to the forum but were read by a research lane rather than by the author of this document; the SCA² documentation quotations beside them were re-checked directly.

**Not reached, and therefore not characterized:** Reddit, whose every sanctioned access path failed, and CONLANG-L, whose long-standing archive has been retired — no citation from either appears here; TADA, ArtiSynth and the Praat articulatory synthesizer; any runtime verification of OTSoft, OT-Help or the UCLA phonotactic learner, for want of the platforms they require; two paywalled g2p surveys that returned 403. Web search ran out partway through. Sections resting on those sources say so where they occur.

## Reproducing the measurements

Every number here was produced on 2026-08-02. Issue counts come from the GitHub API:

```
gh api "repos/OWNER/REPO/issues?state=all&per_page=100" --paginate \
  --jq '.[] | select(.pull_request == null) | {n:.number,t:.title,s:.state,created:.created_at}'
```

Theme counts are title matches against a stated pattern, given at each use — the phone-set question in §7 is titles matching `(list of all|full list|complete (set|list)|all (the )?(ipa )?(phonemes?|phones)|what (ipa|phonemes?|phone set)|...)`, further filtered to titles containing `phone|phonem|ipa|symbol|segment`. Openers in §1 are `.user.login` over the same pull, counted with `sort | uniq -c`.

Other-tool behavior was measured against the current PyPI release in a throwaway virtualenv, not read from documentation:

```python no-run
import panphon
ft = panphon.FeatureTable()
ft.word_fts("gat"); ft.ipa_segs("a͡ɪ"); ft.validate_word("p̪")
```

PHOIBLE's collision count groups the 2,162 rows of `phoible-segments-features.tsv` by the tuple of their 37 feature columns and counts rows in groups of size greater than one. The CLTS and Unicode tables were fetched raw and decoded codepoint by codepoint rather than read as glyphs, because reading `ɡ` and `g` as glyphs is the failure mode under study.

ipakit measurements were run under `PYTHONHASHSEED=0` against this worktree and read the library only:

```python no-run
import sweep                                    # scripts/ owns the corpus definition
from ipakit.features import IPAFeatures
f = IPAFeatures()
units = sweep.corpus(f); sweep.check_corpus(f, units)
# bundle collisions: group units by tuple(sorted(f.get_features(u).items()))
# tract points:      ipakit.tract.constrictions(f, f.get_features(p))
```

espeak-ng behavior was measured with the binary on `PATH`; `espeak-ng --version` should be recorded alongside any re-run, since the phone tables move between releases.

`make check` exits 0 on this branch.
