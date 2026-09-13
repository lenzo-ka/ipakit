# The house style: how ipakit writes sound

A transcription is a set of claims. House style makes each claim at the smallest place that can carry it, keeps the writer's spelling, and leaves the rest open. That discipline matters because ipakit compares, queries, rewrites, and times the result: punctuation that looks merely presentational at the edge of a page becomes data once a program can act on it.

The declaration-backed inventories for this page are in the [generated exhibits](house-style-exhibits.md). They travel with the prose, while their values come from `ipa.xml` and are checked by `make check`.

<a id="one-explicit-model-not-the-substrate"></a>

## The house phonetic model

House style expresses IPAkit's phonetic model,
including choices about composition, feature interpretation, prosodic attachment,
and articulation. It provides an inventory and algebra on the shared TierGraph
substrate. Other models can supply their own declarations and interpretations.
House declarations are testable and revisable, with evidence and limits stated
for each phonetic claim.

The main commitments are collected here so that a reader need not infer the
model from punctuation or scattered implementation details. The linked accounts
give the rationale, operational boundaries, and evidence for the declarations.

| Choice | Computational consequence | Account |
| --- | --- | --- |
| Over-tie, under-tie, and adjacency make different claims. | Simultaneous constituents, a bound sequence, and separate units remain distinguishable in reading and comparison. | [Ties](#ties-are-units), [unit model](ties.md) |
| Stress attaches to the nucleus; syllable boundaries are separate claims. | Stress need not imply an inferred syllable margin. | [Stress](#stress-sits-on-the-nucleus), [syllabification](syllabification.md) |
| Canonical Unicode handling and explicit input conventions are part of reading. | Phonetic atoms follow declared composition rules; imported conventions identify their reading. | [Decomposition](#text-is-read-decomposed), [wild input](#wild-input-is-read-never-guessed-silently) |
| Ordinary spaces express word boundaries; segmented input is a separate mode. | The same whitespace cannot silently alternate between a word edge and a token delimiter. | [Boundaries](#space-spells-the-word-boundary) |
| An interval may carry no segmental claim. | Measured time need not introduce a placeholder phone or an invented word. | [Unclaimed intervals](#silence-carries-no-segment), [representation](representation.md) |
| Features use descriptive phonetic terminology and declared references. | Declared meanings can be checked against their references. | [Features](#features-are-named-from-the-ipa-and-referenced), [generated declarations](house-style-exhibits.md) |
| The house model attaches features to declared articulatory structure. | Geometry informs comparison and posture projection; these claims have their own empirical and rendering limits. | [Articulatory model](tract-anatomy.md), [validation](articulatory-data.md) |
| Composition and rewriting operate on structured claims. | A composed unit need not have its own inventory row; rewrite alternatives and their completeness are explicit. | [Composition](ties.md), [calculus](calculus.md) |
| Native comparison chooses particular costs and normalization. | Structural dissimilarity is not automatically a perceptual probability or a mathematical metric. | [Similarity rationale](similarity.md), [distance mechanics](distance.md) |

[Comparative systems](systems.md) places these commitments beside Pinyin, kana,
and external feature systems. Those comparisons identify each model's semantics,
disagreements, and conversion losses.

An explicit development goal is for house to express every distinction available
in the other inventories, subject to declared exceptions. This is an expressivity
goal whose coverage is measured through audits. Other models can operate directly
in their own feature systems. Compositional and tier-structured expressions can
provide house coverage; an opaque source label still needs an explicit house interpretation.
Coverage audits should distinguish demonstrated support, unresolved mappings,
enhancement gaps, and deliberate exceptions with their rationale. Directional
conversions must identify distinctions they merge or lose.

## Ties are units

A tie names one unit and specifies its internal timing. The **over-tie** `◌͡◌` (U+0361) reads its constituents *simultaneously*, in one shared timing slot: affricates and double articulations, `t͡s`, `k͡p`. The **under-tie** `◌͜◌` (U+035C) reads them *sequentially*, binding several timing slots into one unit: diphthongs and moraic chains, `e͜ɪ`, `a͜ɪ͜ə`. House style assigns these distinct meanings to glyphs that standard IPA treats as interchangeable; [ties.md](ties.md) gives the full account.

Adjacency expresses separate units: `t͜s` is one unit read in sequence, and `ts` is two units. The metric distinguishes these structures: `p͡w` and `p͜w` differ from each other, and both differ from `p` by more than `pʷ` does.

`n͡d` writes internal constituents in a shared timing slot; `ⁿd` writes a nasal approach on a stop.

The reader uses ties to determine unit boundaries in undelimited IPA strings:

| written | units |
| --- | --- |
| `t͡sa` | `t͡s` `a` |
| `tsa` | `t` `s` `a` |
| `a͜ɪt` | `a͜ɪ` `t` |
| `aɪt` | `a` `ɪ` `t` |

Tokenization follows the declared glyphs and ties independently of a language or lexicon.

Ties also compose the inventory's bases into units with features derived from their constituents:

| written | in the inventory | units | place |
| --- | --- | --- | --- |
| `k͡p` | yes | 1 | `velar`, `bilabial` |
| `b͡ɣ` | **no** | 1 | `bilabial`, `velar` |
| `p͡ʈ` | **no** | 1 | `bilabial`, `alveolar` |

Writing and reading therefore support composed units beyond the listed inventory rows. Explicit unit boundaries carry through to alignment and rewriting.

The spacing undertie stands between words. Its own declaration, reproduced in the [boundary exhibit](house-style-exhibits.md#boundary-vocabulary), calls it "absence of a pause, not absence of a boundary." It therefore preserves the word edge while saying how speech passes across it.

## Stress sits on the nucleus

Stress belongs immediately before the nucleus that bears it. A margin-style mark combines a claim about stress with a claim about where a syllable begins. Those claims often come from different evidence: a listener may know which vowel is prominent while the onset's affiliation remains open.

House style writes only the available claim. `ˈa` is a complete statement. An unwritten margin is unclaimed, and the form may acquire explicit syllable structure later without revising where stress lives. This also gives a rule one local object to ask about: the nucleus and its prosody arrive together.

Stress and syllable boundaries are independently writable: `ˈka.tə` says the nucleus `a` is stressed *and* that a syllable ends after it, while `ˈkatə` says only the first. The dot records the explicit boundary claim.

## Text is read decomposed

Input is canonicalized before anything reads it: NFD, and then the few symbols the inventory stores precomposed are recomposed so they match their keys — `ç`, `ä`, `ť` come back as one code point, while `ɛ̃` stays as base plus mark. The operation is idempotent.

Decomposition exposes a base and its marks to the same scan across spellings. Subsequent recomposition restores the registered precomposed inventory keys.

Equivalent precomposed and decomposed spellings therefore receive the same reading across input sources and editors.

## Space spells the word boundary

A space and the canonical boundary mark spell the same boundary unit. Equality and structural queries see that unit; exact emission remembers which spelling the source used. Human-facing text can therefore remain ordinary text while rule notation can remain explicit, with neither surface creating a second kind of word edge.

Segmented input is a separate reading selected by the caller. Whitespace then delimits exact tokens in the declared source vocabulary. Ordinary transcription continues to use spaces as word boundaries.

## Silence carries no segment

When a recording contains an interval for which the transcription makes no segmental claim, the form carries the interval and leaves its contents open. Its duration records the measured time independently of segment labels.

That separation keeps analysis and presentation at their proper layers. A renderer may draw rest, blank space, or another visual treatment over the interval. The transcription continues to say exactly what was observed: time passed, and no segment was asserted there.

<a id="wild-input-is-read-never-guessed-silently"></a>

## Explicit wild-input reading

Wild input is an explicit import mode. Its normalization is depth-aware, so phonetic material can be softened while expression vocabulary inside grouping punctuation keeps its grammar. The command-line echo reports the resulting reading before a query runs, and `--exact` bypasses the import reading when every glyph is already deliberate.

The house metacharacters are available precisely because IPA claims none of those ASCII glyphs as segment atoms. That gives the expression language punctuation of its own without borrowing a phone's spelling. Explicit import still matters: keyboard conventions can be useful and locally consistent, yet the same mark can carry another meaning in another source. Showing the reading gives the writer a chance to confirm the convention at the only moment ambiguity enters.

## Features are named from the IPA, and referenced

Feature names follow IPA terminology. `manner`, `place`, `voiced`, `airstream`, `height`, `backness`, `rounded` describe the chart's axes, with values such as plosive, alveolar, pulmonic, and close-mid. Further distinctions use descriptive phonetic vocabulary: `articulator`, `constriction-location`, `channel`, `phonation`.

`fortis` is the binary laryngeal feature written by U+0348 COMBINING DOUBLE VERTICAL LINE BELOW, extIPA's *strong articulation* mark, registered because Korean needs it for its tense obstruent series. It applies only to obstruents and makes no tract-position claim: the mark remains an annotation rather than a drawn constriction.

Wikipedia links provide reference material for the IPA and phonetic terms. Nearly every feature and phone names an `href`, as do many values. Polarities such as `+`, `-`, `0`, and scale points such as `bottom`, `high`, `half-long` derive their meaning from their containing feature and may omit a separate reference.

Descriptive names such as `constriction-location`, `tongue-blade` and `alveolo-palatal` favor readable phonetic meanings. Their references support learning and checking the declaration against the literature.

IPAkit and Panphon use different feature sets, with neither set contained in the other. Panphon's names appear below; [the generated exhibits](house-style-exhibits.md) list IPAkit's declarations from `ipa.xml`:

- panphon: `syl son cons cont delrel lat nas strid voi sg cg ant cor distr lab hi lo back round velaric tense long hitone hireg` — binary distinctive features, values `+`, `-`, `0`
- ipakit: `manner place articulator phonation airstream channel constriction-location height backness rounding …` — the IPA chart's descriptive axes, multi-valued

Most of panphon's names are the standard generative distinctive features — *delayed release*, *strident*, *anterior*, *coronal*, *distributed* and the rest of the Chomsky and Halle inventory — with later additions: `sg` and `cg` for the laryngeal states, `lab` where the earlier system used anterior and coronal, and two for tone. The names are one tradition and the conditioning in the zeros is a later one, feature geometry, so the set is not a single vintage. Both are inferences from the artifact rather than sourced claims: the installed package states no provenance, and the identification should be cited to Mortensen et al. (2016) before it is relied on.

The zeros are the other clue, and they point to the later half of the same tradition. Feature geometry organizes features under nodes, so a dependent is defined only when its dominating node is active: *distributed* and *anterior* under Coronal, *high* and *low* under Dorsal, *delayed release* under stricture, *tense* on vowel-hood. A fixed-width vector cannot say that, so panphon's third value carries the load, conflating three states — geometrically inapplicable, contrastively underspecified, and genuinely intermediate.

Where the zeros fall recovers part of the conditioning: `cor−` implies *distributed* unvalued in 3,330 of 3,330 segments, and *tense* is unvalued for every consonant. It is applied unevenly, though — *anterior* is unvalued for vowels yet valued on `k` and `p`, which are `cor−`, so one Coronal dependent is conditioned in one context and not another; *delayed release* is valued on everything including `/a/`. The representation is not committed to a geometry so much as retaining an unstated fragment of one.

Distinctive-feature systems describe phonological contrasts; articulatory descriptions record vocal-tract properties. Comparing these declarations therefore requires explicit correspondences and measurements ([interop.md](design/interop.md), [similarity.md](similarity.md)). Cell-level agreement and whole-segment agreement measure different aspects of that correspondence.

## For readers who know regex

The expression grammar leans on PCRE because its reading habits are useful here. Quantifier spellings carry their familiar width claims as the grammar grows; recognition stands on the left and rewriting on the right, much as the two sides of `s///` divide matching from replacement; and application is global by default, in the spirit of `/g`.

Expression atoms are phonological units. A tied compound occupies one atom even though Unicode needs several code points to spell it, and a mark riding on a nucleus remains part of that unit. Familiar grouping and repetition operators act on those units.

Bare parentheses mean optional context because phonological rule writing has used them that way since *The Sound Pattern of English*. PCRE gives parentheses a grouping role; SPE gives the same shape a concise statement about an optional environment. House style honors both traditions by keeping the familiar quantifier surface where it fits and letting the phonological tradition settle the bare form.

## Self-documentation

The declarations carry short descriptions beside outbound references for their stated basis. That makes the inventory useful on its own: a symbol says what structural work it performs and points beyond the repository for the convention it draws on.

The [tie compounds, boundary vocabulary, and character classes](house-style-exhibits.md) are rendered from those declarations. The page argues for the choices; the exhibits say exactly what the current declaration contains. Regeneration keeps those jobs separate, so an inventory change moves the checked table and invites the prose to change only when the reason has changed.
