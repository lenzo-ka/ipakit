# Glossary

These short definitions introduce the phonetics and phonology vocabulary used in the
guides. The linked pages show how each idea appears in ipakit.

## Phoneme and allophone

A **phoneme** is a sound category that can distinguish words in a language; an
**allophone** is a context-dependent pronunciation of a phoneme that does not create
that contrast. The shipped broad-to-narrow examples apply allophonic rules in
[rules.md](rules.md#the-shipped-rule-sets).

## Distinctive feature / feature bundle

A **distinctive feature** is one contrastive dimension of a sound, such as place,
manner, or voicing. A **feature bundle** records several such dimensions together; the
[tutorial](tutorial.md#1-what-is-this-sound) shows bundles returned by ipakit.

## Natural class

A **natural class** is a group of sounds selected by a shared feature description, such
as the class of nasals. [rules.md](rules.md#patterns-are-feature-queries) shows how a
declared class can be used in a query or rule.

## Minimal pair

A **minimal pair** is a pair of words that differ in one sound and have different
meanings, evidence that the differing sounds contrast in that language. ipakit also
uses the term for phones separated by about one feature, as the
[tutorial](tutorial.md#3-what-phones-match-a-description) explains.

## Onset, nucleus, coda, and margin

The **onset** precedes a syllable's central **nucleus**, and the **coda** follows it; the
nucleus and coda together form the rhyme. A **margin** is an edge position around a
nucleus, used when a rule needs the structural position without asserting a complete
syllable analysis; see [syllabification.md](syllabification.md).

## Mora

A **mora** is a unit of syllable weight: languages may count a short vowel as one mora
and a long vowel or other heavy structure as two. [syllabification.md](syllabification.md#3-japanese-morae-first)
shows Japanese mora intervals.

## Diphthong

A **diphthong** is a vowel whose quality moves between two targets within one syllabic
nucleus. [ties.md](ties.md) explains why ipakit ties its two written phases when they
form one unit.

## Aspiration

**Aspiration** is a period of open-glottis airflow, often heard as a puff after a stop.
The American English example in [rules.md](rules.md#the-shipped-rule-sets) conditions it
on syllable position.

## Final devoicing

**Final devoicing** is a process in which an otherwise voiced obstruent is pronounced
voiceless in a final position, often the syllable coda. The German example is described
in [rules.md](rules.md#the-shipped-rule-sets).

## Liaison

**Liaison** is the pronunciation of a word-final consonant before a following
vowel-initial word in contexts where it otherwise does not surface. The French rule set
in [rules.md](rules.md#the-shipped-rule-sets) models this alternation.

## Elision (e caduc)

**Elision** is the omission of a sound in a particular context; French **e caduc** is a
schwa that may be absent. [calculus.md](calculus.md) uses e caduc to demonstrate optional
rule application.

## Agreement variable (SPE alpha)

An **agreement variable** binds an unspecified feature value and requires the same value
where the variable appears again; `α` (alpha) is the traditional SPE notation.
[rules.md](rules.md#a-rule-may-bind-a-value-and-re-use-it) gives matching and rewriting
examples.

## Over-tie and under-tie

An **over-tie** (`͡`) and an **under-tie** (`͜`) join written phases into one unit;
their position differs typographically, not semantically. [ties.md](ties.md) describes
the normalization and the typed ties used for affricates and diphthongs.
