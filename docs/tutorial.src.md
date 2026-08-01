<!--
This file is the SOURCE. docs/tutorial.md is generated from it by `make tutorial`,
and this comment is not carried into the generated page.

Write prose as normal. Two fenced blocks are executed rather than copied:

    ```console-run    every "$ ipakit ..." line is run, its output inserted
    ```python-run     every expression is evaluated, its value quoted beside it

No output is ever typed by hand. `make check` regenerates the page and fails if a
single byte differs, so an example that stops printing what the page claims is a
build failure rather than a reader's problem.

Prefer examples that would CATCH something if it broke over ones that merely
illustrate: this page is also a broad integration test of the public surface.
Everything must be deterministic. See scripts/tutorial.py.
-->

# Getting things done with ipakit

ipakit answers questions about speech sounds: *what is this sound, what is it like, what
else is like it, how do I write it in some other notation, and what happens to it in
context.* This page walks through those tasks in that order. Every command and every
value below was produced by running it.

It is organized by what you want to do, not by module. Each section shows **the command
line and the Python API side by side** for the same task, because most people arrive
wanting one and later need the other.

ipakit has **no runtime dependencies**, so installing it is the whole setup:

```bash
pip install ipakit
```

That puts an `ipakit` command on your path and makes `import ipakit` work.

Throughout, the Python examples assume:

```python-run
import ipakit as ipa
```

For the reference material this page deliberately does not duplicate, see
[docs/README.md](README.md) — in particular [distance.md](distance.md) for why the
distance is not a metric, [ties.md](ties.md) for the tie model, [form.md](form.md) for
the representation, and [rules.md](rules.md) for the full rule notation.

## 1. What is this sound?

The two basic reads are a **name** and a **feature bundle**. `describe` gives the name a
phonetician would use; `features` gives the bundle the rest of the library computes over.

```console-run
$ ipakit describe p
$ ipakit describe ɛ
$ ipakit describe t͡ʃ
$ ipakit features p
```

The same two reads from Python:

```python-run
ipa.describe("p")
ipa.describe("ɛ")
ipa.describe("t͡ʃ")
ipa.features("p", with_defaults=False)
```

Diacritics compose, so you are not limited to the registered inventory. An aspirated /p/
is not a separate entry in the data; it is /p/ plus what the mark declares:

```python-run
ipa.describe("pʰ")
ipa.features("pʰ", with_defaults=False)
ipa.describe("ḁ")
```

> **CLI and API differ here, deliberately but confusingly.** `features(phone)` returns
> the *full* bundle — every feature, defaults included — and `with_defaults=False` gives
> only what the phone states. `ipakit features p` is the other way round: it shows only
> the stated features, and `--all` adds the defaults. So the two spellings of "the
> features of /p/" give 4 keys and 23 keys respectively.

```python-run
len(ipa.features("p"))                 # the API default: everything
len(ipa.features("p", with_defaults=False))
```

Short codes are the compact form, useful when you are reading a lot of them at once:

```console-run
$ ipakit features p --short
$ ipakit features kæt --short
```

## 2. How similar are two sounds, and what is near this one?

`distance` is a number in `[0, 1]` over the feature bundles: 0 is identical, and larger
is more different. A voicing contrast is small; a consonant against a vowel is large.

```python-run
ipa.distance("p", "b")
ipa.distance("p", "k")
ipa.distance("p", "a")
```

```console-run
$ ipakit distance pair p b
$ ipakit distance pair p a
```

`nearest_phones` is usually the more useful question — not *how far* but *what is close*:

```python-run
ipa.nearest_phones("p", n=5)
```

```console-run
$ ipakit analysis nearest p -n 5
```

Raw distances are hard to interpret on their own, because the range that actually occurs
is narrow — the median over the inventory is about 0.19 and the top half of `[0, 1]` is
unreachable. **`confusability` rescales against the whole inventory**, so 1.0 means "as
close as any pair gets" and the numbers spread out:

```python-run
ipa.confusability("f", "θ")            # the most-confused English pair
ipa.confusability("f", "a")
```

```console-run
$ ipakit distance conf f θ
```

For whole words there are two different measures, and it matters which one you get.

```python-run
ipa.word_similarity("kæt", "kæd")      # raw weighted edit distance
ipa.distance_model().word_distance("kæt", "kæd").similarity
```

> **These are two numbers for one English phrase**, and the CLI gives the second.
> `ipakit distance word` is inventory-relative — it is `distance_model().word_distance`,
> not `word_similarity`. There is currently no CLI spelling of `word_similarity`, and no
> top-level API spelling of what the CLI prints other than going through
> `distance_model()`. Reach for `confusability`/`distance_model` when you want a number
> comparable across pairs, and `word_similarity` when you want the raw edit cost.

```console-run
$ ipakit distance word kæt kæd
```

**Do not build a metric tree on `distance`.** It is symmetric and bounded and zero on
identity, but about 0.5% of triples violate the triangle inequality. That is measured,
not feared, and [distance.md](distance.md) documents which uses it rules out and offers
`ipakit.closure.MetricClosure` when you genuinely need the inequality.

## 3. What phones match a description?

`phones_matching` takes the same query language the rule engine uses, so a pattern you
work out here transfers directly into a rule.

```python-run
ipa.phones_matching(["plosive", "bilabial"])
ipa.phones_matching(["nasal"])
ipa.phones_matching(["vowel", "+rounded", "front"])
```

```console-run
$ ipakit query match plosive bilabial
$ ipakit query match +voi plo bil
$ ipakit query list manner=nasal
```

The inverse question — *what do these phones have in common?* — is `natural_class`:

```python-run
ipa.natural_class(["p", "t", "k"], with_defaults=False)
ipa.natural_class(["m", "n", "ŋ"], with_defaults=False)
```

```console-run
$ ipakit analysis natural-class m n ŋ
```

The CLI prints the defaults too — that is `with_defaults=True`, which is what both the
CLI and `natural_class` do unless told otherwise. The stated features are the short list
above; everything else in that output is a default the three phones happen to share.

`minimal_pairs` finds the phones that differ from one phone in about a single feature,
and says which feature:

```python-run
ipa.minimal_pairs("p")[:5]
```

## 4. Converting between notations

Four ASCII and machine notations are supported in both directions. The round trip is the
thing worth checking, and it holds:

```python-run
ipa.to_cmu("kˈæt")
ipa.from_cmu(["K", "AE1", "T"])
ipa.ipa_to_xsampa("t͡ʃ")
ipa.xsampa_to_ipa("t_S")
ipa.to_timit("kæt")
ipa.from_timit(["k", "ae", "t"])
ipa.to_kirshenbaum("ʃɑk")
ipa.from_kirshenbaum("SAk")
```

```console-run
$ ipakit convert to-cmu "kˈæt"
$ ipakit convert to-ipa K AE1 T
$ ipakit convert to-xsampa "t͡ʃ"
$ ipakit convert from-xsampa t_S
```

Note where the CMU converter puts the stress mark: **before the vowel**, not at the
syllable boundary. That is the convention the rule engine expects, and section 7 depends
on it.

You can read features straight out of a non-IPA symbol without converting first:

```python-run
ipa.features_from_xsampa("t_S")[0]["manner"]
ipa.features_from_cmu("K")[0]["place"]
```

**Converters skip what they cannot map**, and `strict=True` raises instead:

```python-run
ipa.to_cmu("k4t")                      # the '4' is dropped
```

> **A gap worth knowing about.** `ipakit convert to-cmu "k4t"` prints `K T` and exits 0
> with no warning, while `ipakit features "k4t"` warns and exits 3 under the CLI's
> lossy-read policy. The converters drop unmappable symbols silently by design, so
> nothing reaches the policy layer that sets the exit status. If you are calling the
> converters from a script, pass `--strict`.

## 5. Splitting a transcription, and keeping what `segments()` drops

`segments` answers *what sounds are in this?* — and to answer it, drops everything that
is not a sound:

```python-run
ipa.to_ipa(ipa.segments("#kæt.dɒɡ#"))
```

That is the right answer to that question and the wrong one to keep, because the word
mark and the syllable break are gone and nothing said so. `Form` is the unprojected
reading: it round-trips, and every narrower view is reachable by name.

```python-run
from ipakit.form import Form

form = Form.parse("#kæt.dɒɡ#")
form.to_ipa()
form.phones
form.boundaries[1]
```

Prosody rides on a segment rather than being one, so it survives the same way:

```python-run
Form.parse("ˈaːkæt").attributes
```

`a`, `ˈa` and `aː` are **one phone** — stress and length are not part of a phone's
identity, which is why a rule written over `a` also matches `ˈa`:

```python-run
[Form.parse(x).phones for x in ("a", "ˈa", "aː")]
```

Tokenizing keeps tie bars and diphthongs together as single units:

```python-run
ipa.tokenize("t͡ʃe͜ɪnd͡ʒ")
```

```console-run
$ ipakit convert tokenize "t͡ʃe͜ɪnd͡ʒ"
$ ipakit rules units "#kæt.dɒɡ#"
```

Carry the widest reading you can and collapse at the point of use.
[form.md](form.md) has the full account, including what `Form.rebuild` does and does not
promise.

## 6. Is this transcription well formed?

```python-run
ipa.validate_ipa("kæt")
ipa.validate_ipa("k4t")
ipa.is_valid_ipa("kæt")
```

```console-run
$ ipakit analysis validate kæt
$ ipakit analysis validate k4t
```

The CLI exits 0 for a valid string and 1 for an invalid one, so it drops straight into a
shell test. Separately, **any** subcommand that could not read all of its input exits 3
and names what it dropped:

```console-run
$ ipakit convert tokenize "kæQt"
```

## 7. Applying allophonic rules, broad to narrow

A rule is the classical generative statement — rewrite `A` as `B` between `C` and `D`:

```python-run
ipa.rewrite("bˈʌtɚ", "t -> ɾ / [vowel stress=primary] _ [vowel]")
```

```console-run
$ ipakit rules apply -r "t -> ɾ / [vowel stress=primary] _ [vowel]" bˈʌtɚ
```

Five rule sets ship with the library:

```console-run
$ ipakit rules list
```

`american-english` is the worked example: twelve ordered rules taking a broad, phonemic
transcription to a narrow, phonetic one.

```console-run
$ ipakit rules list american-english
```

Applying the whole set, and asking what fired:

```console-run
$ ipakit rules apply -s american-english pˈɪn
$ ipakit rules trace -s american-english pˈɪn
$ ipakit rules trace -s american-english bˈʌtɚ
```

> **Loading a shipped set from Python is not where you would look for it.** The loader
> is `ipakit.rules.shipped`, and it is *not* re-exported at the top level — neither
> `ipakit.shipped` nor `ipakit.available` exists. Worse, `ipakit.ruleset("american-english")`
> is a plausible guess that fails confusingly: `ruleset` parses its argument as rule
> *text*, so it reports that `'american-english'` has no rewrite arrow.

```python-run
from ipakit.rules import shipped, available

available()
english = shipped("american-english")
len(english)
ipa.rewrite("pˈɪn", english)
```

The trace is a first-class object, not just a printout — `derive` keeps every step:

```python-run
derivation = ipa.derive("pˈɪn", english)
derivation.result
[step.rule for step in derivation.steps if step.fired]
```

**Stress must be marked on the nucleus**, not at the syllable boundary, or the rules that
condition on a stressed vowel will not fire. This is the single most likely reason a rule
set appears to do nothing:

```python-run
ipa.rewrite("ˈpɪn", english)           # stress at the boundary: no aspiration
ipa.rewrite("pˈɪn", english)           # stress on the nucleus: aspirated
```

The library will move it for you, and `from_cmu` already produces the right convention:

```python-run
features = ipa.load_ipa_features()
features.normalize_stress_to_nucleus("ˈpɪn")
ipa.from_cmu(["P", "IH1", "N"])
```

Aspiration is conditioned on a **syllable margin**, stated positively, which is why
`spin` does not aspirate — the margin there is taken by /s/:

```python-run
ipa.rewrite("spˈɪn", english)
```

And an unspecified margin is not guessed at. A word written with no interior dot leaves
its interior margins unstated, and a margin-conditioned rule declines to fire rather
than inventing a syllabification:

```python-run
ipa.rewrite("ə.tˈæk", english)         # margin written
ipa.rewrite("ətˈæk", english)          # margin unspecified
```

The other four sets each demonstrate a different operation. German final devoicing is a
whole grammar in one rule, conditioned on a coda rather than a word edge:

```python-run
german = shipped("german-final-devoicing")
ipa.rewrite("taːɡ", german)
ipa.rewrite("liːb.lɪç", german)        # devoices word-internally too
ipa.rewrite("ʁaː.dəs", german)         # an onset, so it does not
```

French liaison is the deletion example, conditioned across a word boundary:

```python-run
french = shipped("french-liaison")
ipa.rewrite("lez‿ami", french)         # the /z/ surfaces
ipa.rewrite("lez‿ʃjɛ̃", french)         # and here it does not
ipa.rewrite("lez", french)
```

The two loanword sets are the insertion examples:

```python-run
ipa.rewrite("skul", shipped("spanish-accented-english"))
ipa.rewrite("stap", shipped("spanish-accented-english"))
```

## 8. Writing your own rule set

A rule set is one rule per line; `#` starts a comment and `;` names a rule. Order
matters, and each rule sees the previous rule's output.

```python-run
my_rules = ipa.ruleset(
    """
    # Voice a plosive between vowels, then nasalize a vowel before a nasal.
    [manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; intervocalic voicing
    [vowel] -> [nasalized=+] / _ [manner=nasal]        ; nasalization
    """,
    name="my-rules",
)
len(my_rules)
ipa.rewrite("atapan", my_rules)
```

The two halves of a rule are separable, because *"where does a plosive stand between
vowels"* is a useful question with no rewrite attached:

```python-run
r = ipa.rule("[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing")
r.recognize("atapa")
ipa.rewrite("atapa", r)
```

```console-run
$ ipakit rules recognize -r "[manner=plosive] -> [voiced=+] / [vowel] _ [vowel]" atapa
```

A misspelled feature name or value fails loudly on both sides of the arrow, rather than
quietly building a constraint nothing satisfies. Both arms matter: an undeclared *value*
used to build a constraint no phone could meet and match nothing, in silence.

```python-run
def rule_error(text):
    """The message `ipa.rule` refuses this rule with."""
    try:
        ipa.rule(text)
    except ipa.RuleError as problem:
        return str(problem)
    return None

rule_error("[mannr=plosive] -> t")
rule_error("[manner=obstruent] -> [voiced=-]")
```

A rule can also **bind a value and re-use it**, which is SPE's agreement variable. A Greek
letter in the value slot means *this value, whatever it is, and the same one everywhere
else the rule writes that letter* — so nasal place assimilation is one rule rather than one
rule per place, which is what the shipped English set had before:

```python-run
ipa.rewrite("anpa", "n -> [place=α] / _ [place=α]")
ipa.rewrite("anka", "n -> [place=α] / _ [place=α]")
```

The left of the arrow binds and the right refers, so a variable nothing on the left names
is refused rather than resolving at some sites and not at others. `-α` is the *opposite*
value, which exists only where the feature is binary:

```python-run
rule_error("n -> [place=α]")
ipa.rewrite("asta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")
rule_error("n -> [place=-α] / _ [place=α]")
```

The letter itself is checked against the inventory rather than taken on trust, because the
second member of the traditional series is a registered phone:

```python-run
rule_error("n -> [place=β] / _ [place=β]")
```

Keep rule sets in a file and load them with `--file`, which is what the shipped sets are:

```console-run
$ ipakit rules apply --file ipakit/data/rules/german-final-devoicing.rules taːɡ
```

[rules.md](rules.md) is the full notation — every operator, the tier model, and the
known limits, which are a queue rather than a disclaimer.

## 9. When there is more than one right answer

Every rule so far has been obligatory: one form in, one form out. A great deal of
pronunciation is not like that. French *petit* is [pəti] **and** [pti], from one speaker
in one conversation, and neither is derived from the other.

Write the arrow `~>` instead of `->` and the rule becomes **optional** — it may fire at
a site, or it may not. `variants` is then the entry point, and it answers with a set:

```python-run
ipa.variants("kæt", "t ~> ʔ / _ #").forms
```

The shipped French set ships that: *e caduc*, the schwa that may drop, ordered after the
liaison and deletion rules section 7 showed.

```python-run
french.variants("pətit").forms          # petit
french.variants("samədi").forms         # samedi
french.variants("vɑ̃dʁədi").forms        # vendredi: three consonants, so it may not
```

**Each site chooses on its own.** That is the point, and it is what a word with two
droppable schwas needs. *Devenir* has three real pronunciations, and the fourth
combination — three consonants in a row — is not one of them:

```python-run
french.variants("dəvəniʁ").forms
```

The obligatory entry points are untouched. `rewrite` takes no optional choice, so it
still answers with one form — and that form is always the first variant, by
construction rather than by agreement:

```python-run
ipa.rewrite("pətit", french)
french.variants("pətit")[0].form == ipa.rewrite("pətit", french)
```

Every member carries its own derivation, so it can account for itself:

```python-run
[step.rule for step in french.variants("pətit")[1].derivation.fired]
```

From a shell, `variants` is `apply` for a set with an optional rule in it:

```console-run
$ ipakit rules variants -s french-liaison pətit dəvəniʁ
```

Optional rules multiply, so the enumeration is capped — and **the cap is never silent**.
Ask `complete`, and on the command line the count line says it outright:

```python-run
many = ipa.variants("aaaa", "[vowel] ~> [length=long]", limit=4)
many.complete
many.unexplored                         # choice combinations not enumerated
ipa.variants("aaaa", "[vowel] ~> [length=long]").complete
```

[calculus.md](calculus.md) is the algebra this opens: what is closed over the set, what
the identity is, whether composition is associative and where the cap stops it, whether
the set is always finite — and, said plainly rather than in a footnote, what it cannot
express.

## 10. Looking at the articulation

The feature data is backed by a declared vocal-tract geometry, and that geometry can be
drawn. Thirteen mid-sagittal figures are checked in under [figures/](figures/) and
regenerated with `make figures`:

```bash
make figures
```

Each is drawn through `Head.project` by `ipakit.tract_svg`, which computes no
geometry of its own — so a figure that looks wrong is the model being wrong, which is
how nine defects invisible to the test suite were found.

![Mid-sagittal reference](figures/tract-reference.svg)

The renderer ships inside the package, so an installed ipakit can draw without the
checkout. These are the heads a figure can be drawn on:

```console-run
$ ipakit tract heads
```

`ipakit tract draw t -o t.svg` writes one, and `figure` is the same call from Python,
returning a whole SVG document as a string:

```python-run
from ipakit.tract_svg import figure
figure("t").startswith("<svg ")
len(figure("t")) > 10000
```

In a notebook you need neither: a `Segment` renders as its own tract figure, so
`ipakit.segment("ʃ")` in a cell shows the picture, and so does a `Head`. A form is a
sequence of postures rather than one, so it has no figure of its own — iterate it and
let each segment draw.

[tract-figures.md](tract-figures.md) walks through the figures,
[tract-reference.md](tract-reference.md) is the labeled key, and
[tract-anatomy.md](tract-anatomy.md) is the model itself. What the geometry can and
cannot be checked against externally is in
[articulatory-data.md](articulatory-data.md).

## Where to go next

- [docs/README.md](README.md) — what every document is for, and the order to read them.
- [rules.md](rules.md) — the rule notation in full.
- [calculus.md](calculus.md) — the algebra over the set of forms that `~>` opens.
- [form.md](form.md) — the representation under the rule engine.
- [distance.md](distance.md) — what the metric claims, and what it does not.
- [ties.md](ties.md) — tie bars, diacritics, and how a unit is put together.
- [reviewing.md](reviewing.md) — how defects in this library have actually been found.
