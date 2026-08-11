# The house style: how ipakit writes sound

A transcription is a set of claims. House style makes each claim at the smallest place that can carry it, keeps the writer's spelling, and leaves the rest open. That discipline matters because ipakit compares, queries, rewrites, and times the result: punctuation that looks merely presentational at the edge of a page becomes data once a program can act on it.

The declaration-backed inventories for this page are in the [generated exhibits](house-style-exhibits.md). They travel with the prose, while their values come from `ipa.xml` and are checked by `make check`.

## Ties are units

A tie names one unit and makes one claim about the timing inside it. The overtie reads its constituents simultaneously; adjacency reads them in sequence. That is why `n͡d` and `ⁿd` are different phonological objects on purpose: one writes internal constituents in a shared timing slot, while the other writes a nasal approach on a stop.

This lets tokenization preserve a distinction that matters to alignment and rewriting. Treating every tie as decoration would make the unit boundary depend on outside knowledge; treating every neighboring glyph as a compound would spend the contrast between a unit and a sequence. The glyph carries the claim at the point where the reader needs it.

The spacing undertie stands between words. Its own declaration, reproduced in the [boundary exhibit](house-style-exhibits.md#boundary-vocabulary), calls it "absence of a pause, not absence of a boundary." It therefore preserves the word edge while saying how speech passes across it.

## Stress sits on the nucleus

Stress belongs immediately before the nucleus that bears it. A margin-style mark combines a claim about stress with a claim about where a syllable begins. Those claims often come from different evidence: a listener may know which vowel is prominent while the onset's affiliation remains open.

House style writes only the available claim. `ˈa` is a complete statement. An unwritten margin is unclaimed, and the form may acquire explicit syllable structure later without revising where stress lives. This also gives a rule one local object to ask about: the nucleus and its prosody arrive together.

## Space spells the word boundary

A space and the canonical boundary mark spell the same boundary unit. Equality and structural queries see that unit; exact emission remembers which spelling the source used. Human-facing text can therefore remain ordinary text while rule notation can remain explicit, with neither surface creating a second kind of word edge.

Segmented input is a separate reading selected by the caller. There, whitespace delimits units rather than words, and each token belongs to the source vocabulary. A segmented stream is consequently an owned vocabulary, not a string from which ipakit infers atoms. Opting into that reading makes its contract clear at ingestion and keeps ordinary transcription free to use spaces as boundaries.

## Silence carries no segment

When a recording contains an interval for which the transcription makes no segmental claim, the form carries the interval and leaves its contents open. Duration then remains measured duration, rather than becoming a feature of a placeholder introduced to make the timeline look full.

That separation keeps analysis and presentation at their proper layers. A renderer may draw rest, blank space, or another visual treatment over the interval. The transcription continues to say exactly what was observed: time passed, and no segment was asserted there.

## Wild input is read, never guessed silently

Wild input is an explicit import mode. Its normalization is depth-aware, so phonetic material can be softened while expression vocabulary inside grouping punctuation keeps its grammar. The command-line echo reports the resulting reading before a query runs, and `--exact` bypasses the import reading when every glyph is already deliberate.

The house metacharacters are available precisely because IPA claims none of those ASCII glyphs as segment atoms. That gives the expression language punctuation of its own without borrowing a phone's spelling. Explicit import still matters: keyboard conventions can be useful and locally consistent, yet the same mark can carry another meaning in another source. Showing the reading gives the writer a chance to confirm the convention at the only moment ambiguity enters.

## For readers who know regex

The expression grammar leans on PCRE because its reading habits are useful here. Quantifier spellings carry their familiar width claims as the grammar grows; recognition stands on the left and rewriting on the right, much as the two sides of `s///` divide matching from replacement; and application is global by default, in the spirit of `/g`.

The atoms are phonological units rather than characters. A tied compound occupies one atom even though Unicode needs several code points to spell it, and a mark riding on a nucleus remains part of that unit. Character-oriented intuition still helps with grouping and repetition, while the unit model decides what one step consumes.

Bare parentheses mean optional context because phonological rule writing has used them that way since *The Sound Pattern of English*. PCRE gives parentheses a grouping role; SPE gives the same shape a concise statement about an optional environment. House style honors both traditions by keeping the familiar quantifier surface where it fits and letting the phonological tradition settle the bare form.

## Self-documentation

The declarations carry short descriptions beside outbound references for their stated basis. That makes the inventory useful on its own: a symbol says what structural work it performs and points beyond the repository for the convention it draws on.

The [tie compounds, boundary vocabulary, and character classes](house-style-exhibits.md) are rendered from those declarations. The page argues for the choices; the exhibits say exactly what the current declaration contains. Regeneration keeps those jobs separate, so an inventory change moves the checked table and invites the prose to change only when the reason has changed.
