# The house style: how ipakit writes sound

A transcription is a set of claims. House style makes each claim at the smallest place that can carry it, keeps the writer's spelling, and leaves the rest open. That discipline matters because ipakit compares, queries, rewrites, and times the result: punctuation that looks merely presentational at the edge of a page becomes data once a program can act on it.

The declaration-backed inventories for this page are in the [generated exhibits](house-style-exhibits.md). They travel with the prose, while their values come from `ipa.xml` and are checked by `make check`.

## Ties are units

A tie names one unit and makes one claim about the timing inside it, and there are **two ties making two different claims** — the distinction is the mechanism, not a typographic variant. The **over-tie** `◌͡◌` (U+0361) reads its constituents *simultaneously*, in one shared timing slot: affricates and double articulations, `t͡s`, `k͡p`. The **under-tie** `◌͜◌` (U+035C) reads them *sequentially*, binding several timing slots into one unit: diphthongs and moraic chains, `e͜ɪ`, `a͜ɪ͜ə`. Standard IPA treats the two glyphs as interchangeable; here they are not, and [ties.md](ties.md) is the full account.

Adjacency is a third thing rather than the sequential reading: `t͜s` is one unit read in sequence, `ts` is two units. So the three spellings say three things, and the metric prices them apart — `p͡w` and `p͜w` differ from each other, and both differ from `p` by more than `pʷ` does.

That is why `n͡d` and `ⁿd` are different phonological objects on purpose: one writes internal constituents in a shared timing slot, while the other writes a nasal approach on a stop.

**This is also what lets an undelimited string decompose itself.** IPA is written without spaces between units, so something in the string has to say where a unit ends, and the tie is that something:

| written | units |
| --- | --- |
| `t͡sa` | `t͡s` `a` |
| `tsa` | `t` `s` `a` |
| `a͜ɪt` | `a͜ɪ` `t` |
| `aɪt` | `a` `ɪ` `t` |

No lexicon is consulted and no language is assumed. The reader needs only the glyphs, because the writer already said which neighbours belong together — which is why the same string tokenizes the same way in a language nobody has told us about.

**And it lets a unit be built rather than looked up.** The inventory names a finite set of bases; the tie composes them, so a unit the table never lists is still one unit with features derived from its constituents:

| written | in the inventory | units | place |
| --- | --- | --- | --- |
| `k͡p` | yes | 1 | `velar`, `bilabial` |
| `b͡ɣ` | **no** | 1 | `bilabial`, `velar` |
| `p͡ʈ` | **no** | 1 | `bilabial`, `alveolar` |

That is the same property read from the other end. Writing composes bases into a unit the inventory did not anticipate; reading decomposes the result without being told where the boundaries are. A transcriber describing a language nobody has tabulated needs both, and neither costs a new entry.

This lets tokenization preserve a distinction that matters to alignment and rewriting. Treating every tie as decoration would make the unit boundary depend on outside knowledge; treating every neighboring glyph as a compound would spend the contrast between a unit and a sequence. The glyph carries the claim at the point where the reader needs it.

The spacing undertie stands between words. Its own declaration, reproduced in the [boundary exhibit](house-style-exhibits.md#boundary-vocabulary), calls it "absence of a pause, not absence of a boundary." It therefore preserves the word edge while saying how speech passes across it.

## Stress sits on the nucleus

Stress belongs immediately before the nucleus that bears it. A margin-style mark combines a claim about stress with a claim about where a syllable begins. Those claims often come from different evidence: a listener may know which vowel is prominent while the onset's affiliation remains open.

House style writes only the available claim. `ˈa` is a complete statement. An unwritten margin is unclaimed, and the form may acquire explicit syllable structure later without revising where stress lives. This also gives a rule one local object to ask about: the nucleus and its prosody arrive together.

Moving the stress mark does not spend the syllable boundary. The two are separate claims and both are writable: `ˈka.tə` says the nucleus `a` is stressed *and* that a syllable ends after it, while `ˈkatə` says only the first. The dot is not a casualty of putting stress on the nucleus — it is the claim you make when you have it, on a mark of its own.

## Text is read decomposed

Input is canonicalized before anything reads it: NFD, and then the few symbols the inventory stores precomposed are recomposed so they match their keys — `ç`, `ä`, `ť` come back as one code point, while `ɛ̃` stays as base plus mark. The operation is idempotent.

Decomposition first is what makes a mark findable. A precomposed character hides its diacritic inside one code point, so a reader looking for the nasal hook on `ɛ̃` would have to know every precomposed spelling in advance; decomposed, the base and its marks are separate positions and the same scan finds them everywhere. Recomposing the registered few afterwards is not a retreat from that — those are symbols the inventory names in precomposed form, so leaving them apart would make them unfindable in the other direction.

It also means a caller's spelling does not decide the answer. The same sound typed precomposed or decomposed reads identically, which is a property worth having when transcriptions arrive from several sources and no two editors agree.

## Space spells the word boundary

A space and the canonical boundary mark spell the same boundary unit. Equality and structural queries see that unit; exact emission remembers which spelling the source used. Human-facing text can therefore remain ordinary text while rule notation can remain explicit, with neither surface creating a second kind of word edge.

Segmented input is a separate reading selected by the caller. There, whitespace delimits units rather than words, and each token belongs to the source vocabulary. A segmented stream is consequently an owned vocabulary, not a string from which ipakit infers atoms. Opting into that reading makes its contract clear at ingestion and keeps ordinary transcription free to use spaces as boundaries.

## Silence carries no segment

When a recording contains an interval for which the transcription makes no segmental claim, the form carries the interval and leaves its contents open. Duration then remains measured duration, rather than becoming a feature of a placeholder introduced to make the timeline look full.

That separation keeps analysis and presentation at their proper layers. A renderer may draw rest, blank space, or another visual treatment over the interval. The transcription continues to say exactly what was observed: time passed, and no segment was asserted there.

## Wild input is read, never guessed silently

Wild input is an explicit import mode. Its normalization is depth-aware, so phonetic material can be softened while expression vocabulary inside grouping punctuation keeps its grammar. The command-line echo reports the resulting reading before a query runs, and `--exact` bypasses the import reading when every glyph is already deliberate.

The house metacharacters are available precisely because IPA claims none of those ASCII glyphs as segment atoms. That gives the expression language punctuation of its own without borrowing a phone's spelling. Explicit import still matters: keyboard conventions can be useful and locally consistent, yet the same mark can carry another meaning in another source. Showing the reading gives the writer a chance to confirm the convention at the only moment ambiguity enters.

## Features are named from the IPA, and referenced

**The binder is the IPA itself.** `manner`, `place`, `voiced`, `airstream`, `height`, `backness`, `rounded` are the chart's own axes, and the values under them are the chart's own labels — plosive, alveolar, pulmonic, close-mid. Where the declaration goes past the chart it goes to the vocabulary the chart's own literature uses: `articulator`, `constriction-location`, `channel`, `phonation`. That consistency is what earns the name on the tin. A toolkit called IPAkit whose features were invented codes would be named after a standard it had left behind.

Wikipedia is where each term is *referenced*, not where it comes from — it carries the IPA's vocabulary and is stable enough to link. 39 of 40 features and 138 of 140 phones name an `href`. The values that carry none are the ones that are not independent concepts: the polarities `+`, `-`, `0`, and scale points like `bottom`, `high`, `half-long`, whose meaning is the feature they sit on rather than an idea with a literature of its own. 77 of 135 values name one.

This was a choice and it has a cost: `constriction-location`, `tongue-blade` and `alveolo-palatal` are longer to type than an invented code would be, and the set is larger than a minimal one — 40 features where a contrastive system needs far fewer. The return is that a reader who knows phonetics already knows what a value means, and one who does not has somewhere to go. A feature nobody outside this repository can look up is a feature only this repository can check.

It also fixes what the declaration is answerable to. A name taken from the literature can be *wrong* against the literature — the `href` is what makes that checkable — where an invented name can only be inconsistent with itself.

**The consequence is that ipakit's feature set is not panphon's, and the difference is one of kind.** Ours declares 40 features against panphon's 24, and neither is a subset of the other. Set the names beside each other and the two traditions are visible:

- panphon: `syl son cons cont delrel lat nas strid voi sg cg ant cor distr lab hi lo back round velaric tense long hitone hireg` — binary distinctive features, values `+`, `-`, `0`
- ipakit: `manner place articulator phonation airstream channel constriction-location height backness rounding …` — the IPA chart's descriptive axes, multi-valued

Most of panphon's names are the standard generative distinctive features — *delayed release*, *strident*, *anterior*, *coronal*, *distributed* and the rest of the Chomsky and Halle inventory — with later additions: `sg` and `cg` for the laryngeal states, `lab` where the earlier system used anterior and coronal, and two for tone. The names are one tradition and the conditioning in the zeros is a later one, feature geometry, so the set is not a single vintage. Both are inferences from the artifact rather than sourced claims: the installed package states no provenance, and the identification should be cited to Mortensen et al. (2016) before it is relied on.

The zeros are the other clue, and they point to the later half of the same tradition. Feature geometry organizes features under nodes, so a dependent is defined only when its dominating node is active: *distributed* and *anterior* under Coronal, *high* and *low* under Dorsal, *delayed release* under stricture, *tense* on vowel-hood. A fixed-width vector cannot say that, so panphon's third value carries the load, conflating three states — geometrically inapplicable, contrastively underspecified, and genuinely intermediate.

Where the zeros fall recovers part of the conditioning: `cor−` implies *distributed* unvalued in 3,330 of 3,330 segments, and *tense* is unvalued for every consonant. It is applied unevenly, though — *anterior* is unvalued for vowels yet valued on `k` and `p`, which are `cor−`, so one Coronal dependent is conditioned in one context and not another; *delayed release* is valued on everything including `/a/`. The representation is not committed to a geometry so much as retaining an unstated fragment of one.

The two sets are therefore answers to different questions. A distinctive-feature system asks what distinguishes one phoneme from another in a grammar, and is minimal by design. An articulatory description asks what the vocal tract is doing, and is larger because more is happening than any one language contrasts. That is why the comparison between them is a measurement rather than a translation ([interop.md](design/interop.md), [similarity.md](similarity.md)), and why cell-level agreement can be high while whole-segment agreement is not.

## For readers who know regex

The expression grammar leans on PCRE because its reading habits are useful here. Quantifier spellings carry their familiar width claims as the grammar grows; recognition stands on the left and rewriting on the right, much as the two sides of `s///` divide matching from replacement; and application is global by default, in the spirit of `/g`.

The atoms are phonological units rather than characters. A tied compound occupies one atom even though Unicode needs several code points to spell it, and a mark riding on a nucleus remains part of that unit. Character-oriented intuition still helps with grouping and repetition, while the unit model decides what one step consumes.

Bare parentheses mean optional context because phonological rule writing has used them that way since *The Sound Pattern of English*. PCRE gives parentheses a grouping role; SPE gives the same shape a concise statement about an optional environment. House style honors both traditions by keeping the familiar quantifier surface where it fits and letting the phonological tradition settle the bare form.

## Self-documentation

The declarations carry short descriptions beside outbound references for their stated basis. That makes the inventory useful on its own: a symbol says what structural work it performs and points beyond the repository for the convention it draws on.

The [tie compounds, boundary vocabulary, and character classes](house-style-exhibits.md) are rendered from those declarations. The page argues for the choices; the exhibits say exactly what the current declaration contains. Regeneration keeps those jobs separate, so an inventory change moves the checked table and invites the prose to change only when the reason has changed.
