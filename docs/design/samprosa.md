# SAMPROSA: assessment

Should ipakit carry SAMPROSA (the SAM PROSodic Alphabet) as a declared ASCII notation for the prosodic tier, the way X-SAMPA is the declared ASCII notation for the segmental one?

**Verdict: DON'T BUILD.** SAMPROSA is a separate-tier notation by its own design, and ipakit's string API is a single tier; shipping it would give 12 ASCII characters two incompatible readings in one string space, with no reference implementation to validate the table against and the canonical source offline.

The assessment is read-only. Nothing in this lane changed code, data, or tests. `make check` exits 0.

## Summary of findings

| Question | Finding |
|---|---|
| Do global/terminal tone sections exist? | **Yes, but they declare no symbols of their own** — both draw "from Local and Nuclear tone repertoires". Resolved against two independent sources. |
| SAMPROSA entries mapping cleanly onto already-declared ipakit values | **14 of 32** |
| Entries with no declared home | **16 of 32** (plus 2 contested/partial) |
| Is there a reference implementation or machine-readable source? | **No.** No ICU transliterator, no parser, no corpus tooling. The canonical UCL page is unreachable. |
| Does SAMPROSA collide with what ipakit already ships? | **Yes — 19 of 36 SAMPROSA symbols already carry a different meaning in ipakit's shipped X-SAMPA table**, 12 of them incompatibly. |
| Does a SAMPROSA string corrupt a rewrite rule? | **No — the rule parser refuses loudly.** Measured, and it is a genuine negative result. |
| Does a SAMPROSA string corrupt an IPA read? | **Yes, twice, silently** — `...` and `\|` both validate clean with the wrong meaning. |

## Sources

- SAMPROSA symbol set, Gibbon *Handbook of Standards and Resources for Spoken Language Systems* (SAM ESPRIT 2589; Wells, Barry, Grice, Fourcin & Gibbon 1992): <https://wwwhomes.uni-bielefeld.de/gibbon/Handbooks/gibbon_handbook_1997/node487.html>
- Mirror of the UCL SAMPROSA page: <https://www.datapacrat.com/True/LANG/SAMPROSA.HTM>
- EAGLES 1996, *Transcription systems* (names the coverage categories, gives no table): <https://ilc.cnr.it/EAGLES96/spokentx/node31.html>
- Gibbon, *Notes on Prosody Transcription*, Guangzhou Prosody Lectures 2017: <http://wwwhomes.uni-bielefeld.de/gibbon/Guangzhoulectures2017/Notes_on_prosody_transcription.pdf>
- Canonical primary source, **unreachable at the time of writing**: <https://www.phon.ucl.ac.uk/home/sampa/samprosa.htm>

### On source availability

The brief could not reach the UCL page and asked whether that was the page or the host. Measured: the whole host is down, not just that document.

```
https://www.phon.ucl.ac.uk/home/sampa/samprosa.htm      000
https://www.phon.ucl.ac.uk/home/sampa/home              000
https://www.phon.ucl.ac.uk/                             000
```

So the authoritative statement of the notation is not currently retrievable, and the two tables used here are third-party renderings of a 1992 project deliverable. They agree with each other, which is the most that can be said.

### The open question, resolved

The brief flagged that EAGLES describes SAMPROSA as covering "global, local, terminal and nuclear tones" while the Bielefeld table appeared to give only local and nuclear, and asked whether a distinct global and terminal section exists.

**It does not.** Both mirrors carry the sections, and both say the same thing:

- **Global tone**: from Local and Nuclear tone repertoire.
- **Terminal tone**: from Local and Nuclear tone repertoire.

Global and terminal are **scopes, not symbols**. SAMPROSA distinguishes them by which tier or bracketed region a symbol sits in, not by the character used. This matters more than it first appears, and it is the structural reason the fit is worse than the surface suggests: the same character means a different thing depending on position, so a flat symbol-to-value table — which is exactly what `xsampa.xml` is, and the only shape ipakit's notation machinery supports — **cannot express SAMPROSA**. A bare `H` is not decodable without knowing its tier.

Note also that ipakit's declared `global` feature (`rise` ↗ / `fall` ↘) is *not* the same idea as SAMPROSA's "global tone". ipakit's is an utterance-level pitch movement with its own two IPA glyphs; SAMPROSA's is a scope label over the local/nuclear repertoire. They share a word, not a concept.

## 1. The mapping

### Verified, not assumed

The brief's table (A) of declared values and their IPA spellings was re-derived from the library via `f.declaring_mark(key, value)` and **confirmed exactly**, with one addition worth recording: `|` declares *both* `break=minor` and `level=phrase`, and `‖` declares both `break=major` and `level=utterance`. The level ladder is `syllable < word < phrase < utterance`.

The brief's first read — that H/L/T/B/M is an exact bijection onto tone, `^`/`!` onto step, R/F onto contour, `"`/`%` onto stress, `:` onto length long — **holds**. That is the good news, and it is genuinely the strongest part of the case for building.

### SAMPROSA → ipakit, the clean 14

| SAMPROSA | meaning | ipakit declared value | IPA spelling |
|---|---|---|---|
| `H` | high pitch | `tone=high` | `˦` |
| `L` | low pitch | `tone=low` | `˨` |
| `T` | top pitch | `tone=top` | `˥` |
| `B` | bottom pitch | `tone=bottom` | `˩` |
| `M` | mid pitch | `tone=mid` | `˧` |
| `^` | upstep | `step=up` | `ꜛ` |
| `!` | downstep | `step=down` | `ꜜ` |
| `'` / `/` / `R` | rising (nuclear) | `contour=rising` | `̌` |
| `` ` `` / `\` / `F` | falling (nuclear) | `contour=falling` | `̂` |
| `"` | primary stress | `stress=primary` | `ˈ` |
| `%` | secondary stress | `stress=secondary` | `ˌ` |
| `:` | segment length | `length=long` | `ː` |
| `$` | syllable boundary | `level=syllable` | `.` |
| `#` | word boundary | `level=word` | `#` |

Fourteen of thirty-two, and the bijection on the tone ladder is genuinely exact.

### SAMPROSA → nothing, the unmapped 16

| SAMPROSA | meaning | why it has no home |
|---|---|---|
| `+` | higher pitch | **relative to the preceding pitch**, not an absolute value |
| `++` | much higher | relative, and a magnitude |
| `-` | lower pitch | relative |
| `--` | much lower | relative, and a magnitude |
| `+-` | peak | a derived contour over two relative moves |
| `-+` | trough | as above |
| `^^` | wide upstep | a **magnitude** on step; the IPA has no wide upstep |
| `!!` | wide downstep | as above |
| `=` / `>` / `S` | level or same tone | **anaphoric** — "same as the previous one" |
| `-` | level tone (nuclear) | a third sense of `-`, position-dependent |
| `` `' `` | fall-rise | a contour compound (grave then apostrophe) |
| `` '` `` | rise-fall | a contour compound (apostrophe then grave) |
| `[` | tone group boundary, left | directional bracketing, not a value |
| `]` | tone group boundary, right | as above |
| `-` | separator (meta) | notation punctuation, no phonetic content |
| `*` | conjunctor (meta) | notation punctuation, no phonetic content |

Two entries are contested or partial rather than cleanly unmapped:

- `|` tone group boundary — same character as ipakit's `break=minor`, but see collision (a) below; they coincide rather than agree.
- `...` silence — ipakit has a silence *phone* `␣` (`manner="silence"`), but that is a segment with duration on the segmental tier, not a pause mark on the prosodic one. Cross-tier, so partial at best.

Three observations about that unmapped column, because they decide the question.

**`-` carries three different jobs in one notation.** Lower pitch (local), level tone (nuclear), and separator (meta). SAMPROSA disambiguates them by tier and position. A flat table cannot.

**Six of the sixteen are relative or anaphoric.** `+`, `++`, `-`, `--`, `=`/`>`/`S` and the derived `+-`/`-+` do not name a pitch; they name a *move from the previous pitch*. ipakit's declared features are per-unit values — a unit carries `tone=high`, full stop. Encoding "one step higher than whatever preceded" is a different data model, not a missing table row. This is the deepest mismatch in the assessment and it is not fixable by declaring more values.

**Would declaring any of them be warranted on its own merits?** Mostly no. The relative and anaphoric marks are not values. The width distinction (`^^`, `!!`) has no IPA counterpart. The meta symbols are punctuation. The bracketing is notation-internal. **The one genuine exception is the contour compounds**, and it is worth separating out — see the spin-off finding below, because the IPA declares those independently of SAMPROSA and ipakit was short of them when this was written.

### ipakit → nothing, and whether each is warranted anyway

This is the half the brief called more important: a declaration that exists only to service an ASCII table is a bad declaration. The test applied is *would ipakit declare this if SAMPROSA did not exist?*

| ipakit declared value | SAMPROSA equivalent | warranted on its own merits? |
|---|---|---|
| `length=extra-short` `̆` | none | **Yes** — on the IPA chart. |
| `length=half-long` `ˑ` | none | **Yes** — on the IPA chart. |
| `length=normal` | none (default) | **Yes** — it is the declared default, unmarked on both sides. |
| `global=rise` `↗`, `global=fall` `↘` | none (see above; "global tone" is a scope, not symbols) | **Yes** — both are IPA chart symbols. |
| `linking='+'` `‿` | none — and SAMPROSA has taken `+` for "higher pitch" | **Yes** — IPA chart, French liaison; already load-bearing in `docs/ties.md`. |
| `break=major` `‖` | none — SAMPROSA has one tone group boundary plus directional brackets | **Yes** — IPA chart. |
| `level=phrase`, `level=utterance` | none — SAMPROSA has a single undifferentiated tone group | **Yes** — the ladder is read by `rules._reaches` and `form.tiers`; removing it breaks boundary matching. |

**Every unmapped ipakit declaration is independently warranted.** Not one exists to service an ASCII table, and not one would be added or removed on SAMPROSA's account. Conversely, adopting SAMPROSA in full would require *new* declarations — relative pitch, step width, anaphoric level — that are **not** independently warranted and that the declarative model does not have a shape for.

That asymmetry is the answer to question 1. The mapping is not a near-fit needing a few more rows; it is a good fit on the 14 values ipakit already has for reasons of its own, and a bad fit everywhere else.

## 2. The three collisions, measured

Everything in this section was produced by running code with `PYTHONHASHSEED=0`, not by reading it.

### (a) `|` — tone group boundary vs `break=minor`

The character is shared. The meaning is **not** shared, and it is worth being precise about why.

ipakit declares `|` as `break=minor` / `level=phrase`, and `‖` as `break=major` / `level=utterance`. In the IPA those are the minor (foot) group and the major (intonation) group. SAMPROSA's `|` is the **tone group** boundary — an intonation-phrase edge, which is the *major* group's job, spelled with the *minor* group's character.

So a SAMPROSA `|` and an ipakit `|` coincide in glyph and disagree in strength by one rung of the declared ladder. Measured, the collision is entirely silent:

```
'a|b'   SAMPROSA tone-group '|'  pure_ipa=True  errors=0 tokens=['a', '|', 'b']
```

`validate_ipa` reports nothing at all. A SAMPROSA tone group boundary is read as a well-formed ipakit phrase break, with no diagnostic, at the wrong level. This is precisely the shape `docs/reviewing.md` exists to catch: a well-formed wrong answer under a green read.

### (b) The rewrite-rule DSL

The rule DSL uses `-> → => / _ ; # . % | ‖ ‿ ∅ 0 Ø [ ]`, with `ANY_BOUNDARY = "%"` and `NULL = {∅, 0, Ø}` (`ipakit/rules.py`). SAMPROSA wants `#`, `%`, `|`, `[`, `]`, `+`, `-`, `*` and `.` for different jobs, so the brief asked whether a SAMPROSA string parses as, or corrupts, a rule.

**Measured: it does not. The parser refuses, loudly, in every case tried.**

```
'"kaet# H L | T'   -> RuleError: has no rewrite arrow; expected one of ->, →, =>
'H L -> T'         -> RuleError: 'H L' spells nothing this inventory registers...
'+- -> -+'         -> RuleError: '+-' spells nothing this inventory registers...
'[ H L ]'          -> RuleError: has no rewrite arrow
'^^ !! -- ++'      -> RuleError: has no rewrite arrow
```

The most dangerous candidate was deliberately constructed: SAMPROSA `--` (much lower) immediately followed by `>` (level/same tone) spells `-->`, which **contains the rewrite arrow `->`**. If anything was going to turn a transcription into a silent rule, that was it.

```
'H-->L'      -> RuleError: 'H-' spells nothing this inventory registers...
'H --> L'    -> RuleError
'T ++ --> B' -> RuleError
'%-->"'      -> RuleError
```

It is caught, because the tone letters are unregistered and the parser rejects a left-hand side that spells nothing. The rule DSL is **not** at risk from SAMPROSA text. This is a clean negative result and it is reported as one: the collision the brief expected here is not real.

The IPA readers are a different story. Two silent corruptions, both under a clean `validate_ipa`:

```
'a...b'  SAMPROSA silence '...'   pure_ipa=True  errors=0 tokens=['a', 'b']
'a|b'    SAMPROSA tone-group '|'  pure_ipa=True  errors=0 tokens=['a', '|', 'b']
'a$b'    SAMPROSA syll '$'        pure_ipa=True  errors=1 tokens=['a', 'b']
```

SAMPROSA's silence `...` is read as **three empty ipakit syllable breaks**, round-trips to `'ab'`, and raises no error — only two `empty_constituent` warnings that say nothing about a lost pause. `$` at least errors. `|` and `...` do not.

Everything else is loud, and `:` is already handled by the documented soft read: `validate_ipa("a:")` reports `Unknown symbol ':' (U+003A); from_wild() reads it as 'ː'`.

### (c) `$`/`#` and the level ladder

ipakit's rule is that a boundary pattern matches its declared level **or stronger**. Measured, that holds exactly:

```
a -> b / _ #     on 'a#c'  -> FIRED   ('#'(word) at word)
a -> b / _ #     on 'a|c'  -> FIRED   ('#'(word) at phrase    [stronger])
a -> b / _ #     on 'a‖c'  -> FIRED   ('#'(word) at utterance [stronger])
a -> b / _ #     on 'a.c'  -> no      ('#'(word) at syllable  [WEAKER])
a -> b / _ .     on 'a.c'  -> FIRED   ('.'(syll) at syllable)
a -> b / _ .     on 'a#c'  -> FIRED   ('.'(syll) at word      [stronger])
a -> b / _ .     on 'a|c'  -> FIRED   ('.'(syll) at phrase    [stronger])
a -> b / _ .     on 'a‖c'  -> FIRED   ('.'(syll) at utterance [stronger])
```

On the ladder question the news is good. SAMPROSA's `#` is a word boundary and ipakit's `#` declares `level=word` — they **agree exactly**, glyph and rung. SAMPROSA's `$` is a syllable boundary and ipakit's `.` declares `level=syllable` — same rung, different glyph, and `$` is unregistered so the difference is reported rather than swallowed.

So collision (c) is the benign one: one exact agreement and one loud spelling difference. It is (a) and the `...` case in (b) that are the real hazards.

### (d) The collision the brief did not ask about, and the one that decides it

SAMPROSA is not being considered in a vacuum. **ipakit already ships X-SAMPA**, in the same ASCII string space, from `data/phonemaps/xsampa.xml`. Comparing the SAMPROSA inventory against that shipped table:

```
COLLIDING SYMBOLS: 19 of 36
```

Of those 19, six agree (`!` downstep, `"` primary stress, `#` word boundary, `%` secondary stress, `:` length, `^` upstep), one is the contested `|`, and **twelve disagree outright**:

| symbol | SAMPROSA | shipped X-SAMPA |
|---|---|---|
| `H` | tone high | `ɥ` |
| `L` | tone low | `ʎ` |
| `T` | tone top | `θ` |
| `B` | tone bottom | `β` |
| `M` | tone mid | `ɯ` |
| `R` | rising | `ʁ` |
| `F` | falling | `ɱ` |
| `S` | level/same | `ʃ` |
| `'` | rising | `ʲ` |
| `` ` `` | falling | `ʴ` |
| `=` | level/same | `̩` |
| `*` | conjunctor | `␣` |

Every one of the five tone letters — the exact bijection that is the best argument for building — is a symbol X-SAMPA already spends on a consonant or vowel.

This is not ipakit's problem to solve; it is **SAMPROSA's stated design constraint**. The SAM documentation says so directly: prosodic and segmental transcriptions must be kept on separate tiers, "because certain symbols have different meanings in SAMPROSA from their meaning in SAMPA: e.g. H denotes a labial-palatal semivowel in SAMPA, but High tone in SAMPROSA". Gibbon's own proposal handles this with paired angle brackets `< >` as **tier escape symbols**.

ipakit's converter surface (`xsampa_to_ipa`, `ipa_to_xsampa`) is a single flat string in and a single flat string out. There is no tier. Shipping SAMPROSA into that surface means `H` has two readings and the function signature carries nothing to choose between them.

## 3. Validation

The standard the brief set is the right one: `scripts/xsampa_table.py` derives the shipped X-SAMPA table from ICU's `IPA-XSampa` transliterator plus documented overrides, and `make check` validates the shipped file against that derivation. The table is *checkable* rather than *asserted*, and a symbol added to `ipa.xml` that silently drops out of the table is an error rather than a silent omission.

**There is no equivalent for SAMPROSA. There is nothing at all.**

- ICU exposes 758 transliterators. Searching them: `IPA-XSampa` and `XSampa-IPA` exist; `und_FONIPA-und_FONXSAMP` and its inverse exist. **Nothing matches "prosod". Nothing matches SAMPROSA.** (`Tone-Digit`/`Digit-Tone` are Chinese tone-number conversions, unrelated.)
- No parser, corpus tool, or reference implementation surfaced in searching.
- No machine-readable distribution of the table exists — the two available sources are hand-written HTML.
- The canonical source is offline, as measured above.

So a shipped SAMPROSA table would be **asserted by whoever typed it, validated against nothing, and checkable only against an unreachable web page**. That is a materially different proposition from the X-SAMPA table beside it, and callers would have no way to tell the two apart: both would sit in `data/phonemaps/`, both would look equally authoritative, and only one would be guarded by `make check`.

This finding on its own is close to decisive, and it should be stated plainly: **ipakit would be shipping, under the same roof as a validated table, a second table that nothing can check.**

## 4. Where it would live, if it lived anywhere

Three options were considered.

**(i) A `<notation>` element in the core `ipa.xml` — rejected, and it does not actually work.** This is worth stating precisely because the brief listed it as supported. Measured against `ipakit/features.py`: the `<notations>` block maps *symbol → convention name* and nothing else. A `<symbol>` element carries `name` and `desc`; there is no `ipa=` attribute and no place to put one. The block answers "is this transcription pure IPA?" — it is a **provenance** mechanism, not a transliteration table. It could record that `H` is a SAMPROSA symbol; it could not record that `H` means `tone=high`. Option (i) is not a smaller version of the job, it is a different job.

**(ii) A `data/phonemaps/` mapping file — the only option that could technically hold the table, and still wrong.** It is the right shape for a flat symbol↔IPA map, and `xsampa.py`'s one-place rule is exactly the precedent to follow. But it puts an unvalidatable table next to a validated one with nothing distinguishing them, and it puts SAMPROSA's `H` in the same namespace as X-SAMPA's `H` with no tier to separate them.

**(iii) A supplemental XML file (task #19's mechanism, not yet built) — the least-bad option, and the recommendation *if* this is ever built.** Supplemental shipping is the honest home for a notation that is optional, unvalidated, and must not be confused with the core. It keeps SAMPROSA out of the default namespace, makes loading it a deliberate act, and lets the tier separation the notation requires be expressed as "you opted into a different alphabet".

**Recommendation: none of them today; (iii) if the decision is ever revisited.** The xsampa lesson — one place, so two copies cannot drift — is not an argument for a second table here. It is an argument that the *first* table's discipline (derived, validated, guarded by `make check`) is what makes shipping a notation safe, and SAMPROSA cannot meet it.

## 5. The recommendation

### DON'T BUILD

The reasoning, in order of weight.

**It is structurally the wrong shape.** SAMPROSA distinguishes global, local, terminal and nuclear tone by *scope*, not by symbol, and reuses `-` for three different jobs. A flat symbol→value table cannot express it, and a flat table is the only mechanism ipakit has. This is not a gap in the table; it is a mismatch in kind.

**Its own designers say it must not share a string with segmental transcription**, and ipakit's converter surface is exactly such a shared string. Measured, 19 of 36 SAMPROSA symbols already have a meaning in ipakit's shipped X-SAMPA table, 12 incompatibly, including all five tone letters.

**Nothing can validate it.** No ICU transliterator, no reference implementation, no machine-readable source, canonical page offline. It would be the only shipped table in the repo that `make check` cannot guard.

**The 14 values it would reach are already reachable, with better spellings.** Every one is already declared and already has an IPA glyph. SAMPROSA adds an alternative ASCII spelling for things ipakit can already say, and cannot say the 16 things it would need to add value.

**It carries weight against both stated goals.** For **learning and teaching**, an obscure 1992 project deliverable whose primary source is offline is a liability: a phonology student should be taught `˦` and `ˈ`, not that `H` means high tone here and `ɥ` three lines up. For **language technology**, SAMPROSA has negligible uptake — the modern prosodic annotation standards in that space are ToBI and its descendants, not SAMPROSA — so it would not connect ipakit to any corpus or tool anyone is actually using.

### Two questions, separated

The brief is right that "should we ship SAMPROSA?" and "does the prosodic tier need an ASCII notation at all?" are different questions. They get different answers, and the mapping work above is the reusable part.

**Does the prosodic tier need an ASCII notation at all? Not now, and not urgently — but the answer is not a flat no, and the reason is worth keeping.**

The case *against* needing one: the declared features plus their IPA glyphs are sufficient for everything ipakit currently does. Prosody sits on the unit rather than in the feature bag (`docs/ties.md`), the marks are all chart-proper, and the soft reads in `from_wild` already cover the two ASCII stand-ins anyone actually types — `:` for `ː` and `'` for `ˈ`. Unicode is not the obstacle it was in 1992, which is the entire reason SAMPA existed; a modern user can type `˦` as easily as `H`. Adding an ASCII prosodic alphabet today solves a problem that the last thirty years mostly dissolved.

The case *for* keeping the question open: if ipakit ever needs to ingest prosodically-annotated corpora, or to round-trip prosody through a channel that is genuinely ASCII-only, it will need *some* ASCII encoding. **What this assessment establishes is the requirements list for that encoding, and it is the durable output here even though the verdict is negative.** Such a notation would have to:

- cover the 14 declared values that map cleanly, which are the well-understood core and where any notation will agree;
- **not** reuse characters that ipakit's shipped X-SAMPA table already spends — that constraint alone rules out `H L T B M R F S = ' \` *` and is the single hardest requirement;
- **not** reuse the rule DSL's live tokens `-> → => / _ ; # . % | ‖ ‿ ∅ 0 Ø [ ]`;
- either avoid relative and anaphoric marks entirely, or come with a data model that has somewhere to put them, because ipakit's per-unit feature values do not;
- be derivable and validatable from something machinable, so `make check` can guard it the way it guards X-SAMPA.

SAMPROSA fails the second, third, fourth and fifth. Any future proposal should be measured against that list before it is built, and if nothing on offer passes, the right move is to extend the X-SAMPA table's existing prosodic coverage (it already encodes `ˈ ˌ ː ꜛ ꜜ |` and the tone bars) rather than to adopt a second alphabet.

## 6. What follows from DON'T BUILD

A verdict with no consequences is not actionable. Three things follow, none of them applied in this lane.

### (a) `ipa.xml`'s `<notations>` comment points at something that is not coming

The shipped data currently says, in the comment above `<notations>`:

> One block, not one flag per system: a further convention
> (SAMPROSA) is another `<notation>` with its own symbols, and
> `notation != "chart"` goes on answering the same question.

and a few lines later:

> The next symbol marked would not be so lucky, and a SAMPROSA
> batch marking real phones would move the matrix outright.

This is prose in shipped data promising a feature that this assessment recommends against — the same defect shape as a shipped `.rules` file describing a fixed bug as still open. The structural argument in the comment is sound and should survive; only the commitment should go.

Proposed replacement for the first passage:

> One block, not one flag per system: a further convention is
> another `<notation>` with its own symbols, and `notation != "chart"`
> goes on answering the same question. No second notation is
> planned — SAMPROSA was assessed for this slot and declined; see
> docs/design/samprosa.md. The block earns its keep on the three
> symbols above.

Proposed replacement for the second, which only needs the proper noun dropped:

> The next symbol marked would not be so lucky, and a batch
> marking real phones would move the matrix outright.

Not applied here — this lane is read-only, and the change belongs to whoever picks it up.

### (b) `tests/test_notation.py`'s `samprosa` fixture

Two tests build a hypothetical `samprosa` notation: `test_a_symbol_listed_under_two_notations_fails_to_load` and `test_the_question_survives_a_further_convention`.

**Judgement: keep them, and they are fine as they stand — but they are now *deliberately fictional*, not anticipatory, and that should be said in the file so nobody later reads the fixture as a commitment.**

The reasoning: what those tests exercise is the loader's behavior when a *second* notation exists — duplicate-symbol rejection, and that provenance never reaches a feature bundle. That behavior is worth pinning regardless of which notation ever arrives, and a fixture needs *some* name. The name being a real notation ipakit declined to ship is a documentation hazard, not a test defect. A one-line docstring note ("`samprosa` here is a stand-in for any second notation; ipakit does not ship one — see docs/design/samprosa.md") resolves it. Renaming the fixture to something obviously fictional would also work and is a matter of taste.

### (c) What `<notations>` is actually for

If SAMPROSA was the motivating case and SAMPROSA is off, the mechanism needs a justification that does not depend on it. It has one, and it is load-bearing today:

**`<notations>` exists so that `ipa.xml` does not misrepresent itself.** The file is a faithful record of the IPA chart except for three symbols that are not on the chart at all — `␣` (silence, borrowed from the visible-space convention), `#` (generative phonology), and `∅` (set theory). Unmarked, the file claims to be something it is not, and no caller can ask which symbols are which. The block turns that from lore into a query: `is_pure_ipa` / `extensions_in` are a real API answering a real question ("does this transcription use only the chart?"), tested over the whole inventory.

It is also justified by *shape* rather than by any second notation: the measured reason it is a block and not a per-symbol attribute — an attribute lands in the symbol's feature bundle, and a key in a bundle is a term in the metric, moving 58 of 8060 sweep units — is an argument about where provenance lives, and it holds with exactly one non-chart convention.

So the mechanism is **not** speculative machinery. It earns its keep on the three symbols it already marks. The only speculative thing about it was the comment naming a second notation that was never assessed until now, which is what (a) fixes.

## 7. Spin-off finding, since acted on

Chasing SAMPROSA's fall-rise and rise-fall compounds — the one unmapped group that *is* independently warranted, because the IPA declares contour tones of its own — turned up two things in `ipa.xml` that have nothing to do with SAMPROSA.

`᷅` (U+1DC5 COMBINING GRAVE-MACRON) was declared `contour="falling"`. Grave (low) followed by macron (mid) is a **rise**, and the Unicode proposal documenting these characters lists U+1DC4..U+1DC7 as higher rising, **lower rising**, lower falling, higher falling. Separately, U+1DC6, U+1DC7, U+1DC8 and U+1DC9 were not declared at all, so `contour` had two values where the IPA chart names five — and rising-falling was not expressible at all, because no pairing of a level with a direction names it.

Both are settled in [tone.md](../tone.md), which is the account of what a contour is: a **sequence of tone levels**, so `᷅` is `tone="low>mid"` and its rise follows from the levels rather than being declared beside them. The reasoning is a check rather than a comment — `scripts/invariants.py:check_contour_marks` derives each compound mark's levels from the pitch `ipa.xml` declares on its component marks and the time order Unicode's own character name spells them in, so a compound that disagrees with its parts cannot be declared again.

The prediction that a value change here would move the metric turned out to be wrong in the reassuring direction, and the measurement is the reason it was not left to stand: `tone` and `contour` are `mode="prosodic"`, so they live on the unit and never enter a feature bundle. `confusion.json` regenerates byte-identical, and no existing unit's features, description or distance moves.

Sources: <https://unicode.org/L2/L2025/25250-ipa-tone-diacritics.pdf>, <https://www.fileformat.info/info/unicode/char/1dc5/index.htm>

## Reproducing the measurements

All measurements in this document were run with `PYTHONHASHSEED=0` against this worktree. They read the library only — `IPAFeatures.declaring_mark`, `ipakit.rule(...).apply`, `ipakit.tokenize`, `ipakit.validate_ipa`, `ipakit.is_pure_ipa`, and `data/phonemaps/xsampa.xml` — and change nothing.

`make check` exits 0 on this branch, verified by exit status.
