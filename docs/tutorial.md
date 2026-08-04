# Getting things done with ipakit

<!-- Generated from tutorial.src.md by scripts/tutorial.py. Do not edit: run `make tutorial`. -->

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

To run this page rather than read it, `ipakit notebook` writes a Jupyter notebook of the
same material into the current directory: the same examples as cells, with the answers
left out for you to produce. It is rendered from the source this page is rendered from,
so the two cannot come to disagree.

Throughout, the Python examples assume:

```python
import ipakit as ipa
```

For the reference material this page deliberately does not duplicate, see
[docs/README.md](README.md) — in particular [distance.md](distance.md) for why the
distance is not a metric, [ties.md](ties.md) for the tie model, [form.md](form.md) for
the representation, and [rules.md](rules.md) for the full rule notation.

## 1. What is this sound?

The two basic reads are a **name** and a **feature bundle**. `describe` gives the name a
phonetician would use; `features` gives the bundle the rest of the library computes over.

```console
$ ipakit describe p
voiceless bilabial plosive
$ ipakit describe ɛ
open-mid front unrounded vowel
$ ipakit describe t͡ʃ
voiceless sibilant postalveolar affricate
$ ipakit features p
name: p
class: phone
manner: plosive
place: bilabial
```

The same two reads from Python:

```python
ipa.describe("p")  # 'voiceless bilabial plosive'
ipa.describe("ɛ")  # 'open-mid front unrounded vowel'
ipa.describe("t͡ʃ")  # 'voiceless sibilant postalveolar affricate'
ipa.features("p", with_defaults=False)
# {'manner': 'plosive', 'place': 'bilabial', 'href':
# 'Voiceless_bilabial_plosive', 'class': 'phone'}
```

Diacritics compose, so you are not limited to the registered inventory. An aspirated /p/
is not a separate entry in the data; it is /p/ plus what the mark declares:

```python
ipa.describe("pʰ")  # 'voiceless aspirated bilabial plosive'
ipa.features("pʰ", with_defaults=False)
# {'manner': 'plosive', 'place': 'bilabial', 'href':
# 'Voiceless_bilabial_plosive', 'class': 'phone', 'release': 'aspirated'}
ipa.describe("ḁ")  # 'voiceless open front unrounded vowel'
```

> **CLI and API differ here, deliberately but confusingly.** `features(phone)` returns
> the *full* bundle — every feature, defaults included — and `with_defaults=False` gives
> only what the phone states. `ipakit features p` is the other way round: it shows only
> the stated features, and `--all` adds the defaults. So the two spellings of "the
> features of /p/" give 4 keys and 23 keys respectively.

```python
len(ipa.features("p"))  # 23   the API default: everything
len(ipa.features("p", with_defaults=False))  # 4
```

Short codes are the compact form, useful when you are reading a lot of them at once:

```console
$ ipakit features p --short
plo bil
$ ipakit features kæt --short
k: plo vel
æ: vow nop frt +voi -rnd
t: plo alv
```

## 2. How similar are two sounds, and what is near this one?

`distance` is a number in `[0, 1]` over the feature bundles: 0 is identical, and larger
is more different. A voicing contrast is small; a consonant against a vowel is large.

```python
ipa.distance("p", "b")  # 0.05
ipa.distance("p", "k")  # 0.0675
ipa.distance("p", "a")  # 0.33772727272727276
```

```console
$ ipakit distance pair p b
0.0500
$ ipakit distance pair p a
0.3377
```

`nearest_phones` is usually the more useful question — not *how far* but *what is close*:

```python
ipa.nearest_phones("p", n=5)
# [('t', 0.0195), ('ɸ', 0.02666666666666666), ('f', 0.029666666666666664),
# ('ȶ', 0.033499999999999995), ('k͡p', 0.03375)]
```

```console
$ ipakit analysis nearest p -n 5
p (voiceless bilabial plosive)
--------------------------------------------------
  t  0.019  voiceless alveolar plosive
  ɸ  0.027  voiceless bilabial fricative
  f  0.030  voiceless labiodental fricative
  ȶ  0.033  voiceless alveolo-palatal plosive
  k͡p  0.034  voiceless labial-velar plosive
```

Raw distances are hard to interpret on their own, because the range that actually occurs
is narrow — the median over the inventory is about 0.19 and the top half of `[0, 1]` is
unreachable. **`confusability` rescales against the whole inventory**, so 1.0 means "as
close as any pair gets" and the numbers spread out:

```python
ipa.confusability("f", "θ")  # the most-confused English pair
# 0.9962464810760088
ipa.confusability("f", "a")  # 0.35439474507350643
```

```console
$ ipakit distance conf f θ
f ~ θ: confusability=0.9962 distance=0.0038  [reference: ipa, 139 phones]
```

For whole words there are two different measures, and it matters which one you get.

```python
ipa.word_similarity("kæt", "kæd")  # raw weighted edit distance
# 0.9833333333333333
ipa.distance_model().word_distance("kæt", "kæd").similarity
# 0.9864108713029577
```

> **These are two numbers for one English phrase**, and the CLI gives the second.
> `ipakit distance word` is inventory-relative — it is `distance_model().word_distance`,
> not `word_similarity`. There is currently no CLI spelling of `word_similarity`, and no
> top-level API spelling of what the CLI prints other than going through
> `distance_model()`. Reach for `confusability`/`distance_model` when you want a number
> comparable across pairs, and `word_similarity` when you want the raw edit cost.

```console
$ ipakit distance word kæt kæd
kæt ~ kæd: similarity=0.9864  [reference: ipa, 139 phones]
```

A word comparison also reports `coverage`, the shorter token count over the longer. It
is beside the score and never inside it, because a low similarity has two readings and
the score cannot tell them apart on its own — these two are alike as numbers and are not
alike as diagnoses.

```python
ipa.word_distance("kætəloɡ", "kæt").coverage  # 0.42857142857142855
ipa.word_distance("kætəloɡ", "ɡolətæk").coverage  # 1.0
```

Two shapes come up often enough to name. **`nearest_pronunciation`** answers "is this an
acceptable pronunciation?" — the best match of a form against the several transcriptions a
lexicon lists (free variants, a homograph read two ways), reporting which one won rather
than a bare number.

```python
match = ipa.nearest_pronunciation("kat", ["kæt", "kɑt"])
match.accepted, round(match.similarity, 3)  # ('kæt', 0.997)
```

**`sequence_distance`** scores phone tokens you already hold — one element per unit —
without re-tokenizing, so boundaries you drew (`d͡ʒ` as one token) are kept as given.

```python
ipa.sequence_distance(["k", "a", "t"], ["k", "æ", "t"]).similarity
# 0.9968013468013468
```

**Do not build a metric tree on `distance`.** It is symmetric and bounded and zero on
identity, but about 0.5% of triples violate the triangle inequality. That is measured,
not feared, and [distance.md](distance.md) documents which uses it rules out and offers
`ipakit.closure.MetricClosure` when you genuinely need the inequality.

## 3. What phones match a description?

`phones_matching` takes the same query language the rule engine uses, so a pattern you
work out here transfers directly into a rule.

```python
ipa.phones_matching(["plosive", "bilabial"])  # ['b', 'p', 'ɓ', 'ʘ']
ipa.phones_matching(["nasal"])  # ['m', 'n', 'ŋ', 'ɱ', 'ɲ', 'ɳ', 'ɴ', 'ŋ͡m']
ipa.phones_matching(["vowel", "+rounded", "front"])  # ['y', 'ø', 'œ', 'ɶ']
```

```console
$ ipakit query match plosive bilabial
b p ɓ ʘ
$ ipakit query match +voi plo bil
b ɓ
$ ipakit query list manner=nasal
Phones with manner=nasal (8):
  m
  n
  ŋ
  ŋ͡m
  ɱ
  ɲ
  ɳ
  ɴ
```

The inverse question — *what do these phones have in common?* — is `natural_class`:

```python
ipa.natural_class(["p", "t", "k"], with_defaults=False)
# {'manner': 'plosive'}
ipa.natural_class(["m", "n", "ŋ"], with_defaults=False)
# {'manner': 'nasal', 'voiced': '+'}
```

```console
$ ipakit analysis natural-class m n ŋ
airstream=pulmonic
centralized=-
channel=flat
fronting=0
height-mod=0
labialized=-
labio-palatized=-
length=normal
manner=nasal
mid-centralized=-
nasalized=-
palatalized=-
pharyngealized=-
retroflex=-
rhotacized=-
rounded=-
syllabic=-
tongue-root=0
velarized=-
voiced=+
```

The CLI prints the defaults too — that is `with_defaults=True`, which is what both the
CLI and `natural_class` do unless told otherwise. The stated features are the short list
above; everything else in that output is a default the three phones happen to share.

`minimal_pairs` finds the phones that differ from one phone in about a single feature,
and says which feature:

```python
ipa.minimal_pairs("p")[:5]
# [('t', 'place', 'alveolar'), ('ɸ', 'manner', 'fricative'), ('f', 'manner',
# 'fricative'), ('ȶ', 'place', 'alveolo-palatal'), ('k͡p', 'place',
# 'bilabial^velar')]
```

## 4. Converting between notations

Four ASCII and machine notations are supported in both directions. The round trip is the
thing worth checking, and it holds:

```python
ipa.to_cmu("kˈæt")  # ['K', 'AE1', 'T']
ipa.from_cmu(["K", "AE1", "T"])  # 'kˈæt'
ipa.ipa_to_xsampa("t͡ʃ")  # 't_S'
ipa.xsampa_to_ipa("t_S")  # 't͡ʃ'
ipa.to_timit("kæt")  # ['k', 'ae', 't']
ipa.from_timit(["k", "ae", "t"])  # 'kæt'
ipa.to_kirshenbaum("ʃɑk")  # 'SAk'
ipa.from_kirshenbaum("SAk")  # 'ʃɑk'
```

```console
$ ipakit convert to-cmu "kˈæt"
K AE1 T
$ ipakit convert to-ipa K AE1 T
kˈæt
$ ipakit convert to-xsampa "t͡ʃ"
t_S
$ ipakit convert from-xsampa t_S
t͡ʃ
```

Note where the CMU converter puts the stress mark: **before the vowel**, not at the
syllable boundary. That is the convention the rule engine expects, and section 7 depends
on it.

You can read features straight out of a non-IPA symbol without converting first:

```python
ipa.features_from_xsampa("t_S")[0]["manner"]  # 'affricate'
ipa.features_from_cmu("K")[0]["place"]  # 'velar'
```

**Converters skip what they cannot map**, and `strict=True` raises instead:

```python
ipa.to_cmu("k4t")  # ['K', 'T']   the '4' is dropped
```

> **A gap worth knowing about.** `ipakit convert to-cmu "k4t"` prints `K T` and exits 0
> with no warning, while `ipakit features "k4t"` warns and exits 3 under the CLI's
> lossy-read policy. The converters drop unmappable symbols silently by design, so
> nothing reaches the policy layer that sets the exit status. If you are calling the
> converters from a script, pass `--strict`.

## 5. Splitting a transcription, and keeping what `segments()` drops

`segments` answers *what sounds are in this?* — and to answer it, drops everything that
is not a sound:

```python
ipa.to_ipa(ipa.segments("#kæt.dɒɡ#"))  # 'kætdɒɡ'
```

That is the right answer to that question and the wrong one to keep, because the word
mark and the syllable break are gone and nothing said so. `Form` is the unprojected
reading: it round-trips, and every narrower view is reachable by name.

```python
from ipakit.form import Form

form = Form.parse("#kæt.dɒɡ#")
form.to_ipa()  # '#kæt.dɒɡ#'
form.phones  # ('k', 'æ', 't', 'd', 'ɒ', 'ɡ')
form.boundaries[1]
# Boundary(text='.', level='syllable', at=3, features={'level': 'syllable',
# 'href': 'Syllable', 'class': 'separator'})
```

Prosody rides on a segment rather than being one, so it survives the same way:

```python
Form.parse("ˈaːkæt").attributes
# (Attribute(feature='stress', value='primary', at=0, glyph='ˈ'),
# Attribute(feature='length', value='long', at=0, glyph='ː'))
```

`a`, `ˈa` and `aː` are **one phone** — stress and length are not part of a phone's
identity, which is why a rule written over `a` also matches `ˈa`:

```python
[Form.parse(x).phones for x in ("a", "ˈa", "aː")]  # [('a',), ('a',), ('a',)]
```

Tokenizing keeps tie bars and diphthongs together as single units:

```python
ipa.tokenize("t͡ʃe͜ɪnd͡ʒ")  # ['t͡ʃ', 'e͜ɪ', 'n', 'd͡ʒ']
```

```console
$ ipakit convert tokenize "t͡ʃe͜ɪnd͡ʒ"
t͡ʃ e͜ɪ n d͡ʒ
$ ipakit rules units "#kæt.dɒɡ#"
# k æ t . d ɒ ɡ #
```

Carry the widest reading you can and collapse at the point of use.
[form.md](form.md) has the full account, including what `Form.rebuild` does and does not
promise.

## 6. Is this transcription well formed?

```python
ipa.validate_ipa("kæt")  # []
ipa.validate_ipa("k4t")
# [{'type': 'error', 'code': 'unknown_symbol', 'message': "Unknown symbol '4'
# (U+0034)", 'position': '1', 'symbol': '4'}]
ipa.is_valid_ipa("kæt")  # True
```

```console
$ ipakit analysis validate kæt
Valid: kæt
$ ipakit analysis validate k4t
Issues in: k4t
----------------------------------------
  ERROR [unknown_symbol] Unknown symbol '4' (U+0034)
      at position 1
```

The CLI exits 0 for a valid string and 1 for an invalid one, so it drops straight into a
shell test. Separately, **any** subcommand that could not read all of its input exits 3
and names what it dropped:

```console
$ ipakit convert tokenize "kæQt"
k æ t
ipakit: warning: dropped 1 unregistered symbol(s) ['Q'] while parsing IPA: the result is shorter than the input. Pass strict=True to raise instead, or import wild-convention text with from_wild().
ipakit: input was not read in full; exiting 3. Rerun as 'ipakit --lax ...' to accept the lossy read and exit 0.
```

## 7. Applying allophonic rules, broad to narrow

A rule is the classical generative statement — rewrite `A` as `B` between `C` and `D`:

```python
ipa.rewrite("bˈʌtɚ", "t -> ɾ / [vowel stress=primary] _ [vowel]")  # 'bˈʌɾɚ'
```

```console
$ ipakit rules apply -r "t -> ɾ / [vowel stress=primary] _ [vowel]" bˈʌtɚ
bˈʌɾɚ
```

Five rule sets ship with the library:

```console
$ ipakit rules list
american-english
french-liaison
german-final-devoicing
japanese-moraic
spanish-accented-english
```

`american-english` is the worked example: twelve ordered rules taking a broad, phonemic
transcription to a narrow, phonetic one.

```console
$ ipakit rules list american-english
american-english: 14 rules
   1  [manner=plosive place=alveolar] -> [manner=tap voiced=+] / [vowel] _ [vowel -primary -secondary] ; tapping
   2  [manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary] ; aspiration
   3  [manner=approximant voiced=+] -> [phonation=devoiced] / [manner=plosive voiced=-] _ [vowel] ; approximant devoicing
   4  n -> [place=α] / _ [place=α] ; nasal assimilation
   5  [manner=nasal] -> [syllabic=+] / [obstruent] _ # ; syllabic nasal
   6  [channel=lateral manner=approximant] -> [syllabic=+] / [-vowel -approximant -trill -tap -silence] _ # ; syllabic lateral
   7  [manner=plosive place=alveolar] -> [manner=tap voiced=+] / [vowel] _ [syllabic=+ channel=lateral -primary -secondary] ; tapping (before a syllabic lateral)
   8  [manner=plosive place=alveolar] -> [manner=tap voiced=+] / [vowel] ɹ _ [vowel -primary -secondary] ; tapping (after a coda rhotic)
   9  [manner=plosive] -> [release=nasal] / _ [manner=nasal] ; nasal release
  10  [manner=plosive] -> [release=lateral] / _ [syllabic=+ channel=lateral] ; lateral release
  11  [manner=plosive voiced=-] -> [release=no-audible] / _ # ; unreleased coda
  12  l -> [velarized=+] / [vowel] _ ; dark l
  13  [vowel] -> [nasalized=+] / _ [manner=nasal] # ; nasalization
  14  [vowel] -> [nasalized=+] / _ [manner=nasal] [-vowel] ; nasalization (closed syllable)
```

Applying the whole set, and asking what fired:

```console
$ ipakit rules apply -s american-english pˈɪn
pʰˈɪ̃n
$ ipakit rules trace -s american-english pˈɪn
pˈɪn
  aspiration
      aspiration: p -> pʰ @0
  = pʰˈɪn
  nasalization
      nasalization: ˈɪ -> ˈɪ̃ @1
  = pʰˈɪ̃n
$ ipakit rules trace -s american-english bˈʌtɚ
bˈʌtɚ
  tapping
      tapping: t -> ɾ @2
  = bˈʌɾɚ
```

> **Loading a shipped set from Python is not where you would look for it.** The loader
> is `ipakit.rules.shipped`, and it is *not* re-exported at the top level — neither
> `ipakit.shipped` nor `ipakit.available` exists. Worse, `ipakit.ruleset("american-english")`
> is a plausible guess that fails confusingly: `ruleset` parses its argument as rule
> *text*, so it reports that `'american-english'` has no rewrite arrow.

```python
from ipakit.rules import shipped, available

available()
# ['american-english', 'french-liaison', 'german-final-devoicing',
# 'japanese-moraic', 'spanish-accented-english']
english = shipped("american-english")
len(english)  # 14
ipa.rewrite("pˈɪn", english)  # 'pʰˈɪ̃n'
```

The trace is a first-class object, not just a printout — `derive` keeps every step:

```python
derivation = ipa.derive("pˈɪn", english)
derivation.result  # 'pʰˈɪ̃n'
[step.rule for step in derivation.steps if step.fired]
# ['aspiration', 'nasalization']
```

**Stress must be marked on the nucleus**, not at the syllable boundary, or the rules that
condition on a stressed vowel will not fire. This is the single most likely reason a rule
set appears to do nothing:

```python
ipa.rewrite("ˈpɪn", english)  # stress at the boundary: no aspiration
# 'ˈpɪ̃n'
ipa.rewrite("pˈɪn", english)  # 'pʰˈɪ̃n'   stress on the nucleus: aspirated
```

The library will move it for you, and `from_cmu` already produces the right convention:

```python
features = ipa.load_ipa_features()
features.normalize_stress_to_nucleus("ˈpɪn")  # 'pˈɪn'
ipa.from_cmu(["P", "IH1", "N"])  # 'pˈɪn'
```

Aspiration is conditioned on a **syllable margin**, stated positively, which is why
`spin` does not aspirate — the margin there is taken by /s/:

```python
ipa.rewrite("spˈɪn", english)  # 'spˈɪ̃n'
```

And an unspecified margin is not guessed at. A word written with no interior dot leaves
its interior margins unstated, and a margin-conditioned rule declines to fire rather
than inventing a syllabification:

```python
ipa.rewrite("ə.tˈæk", english)  # 'ə.tʰˈæk̚'   margin written
ipa.rewrite("ətˈæk", english)  # 'ətˈæk̚'   margin unspecified
```

The other four sets each demonstrate a different operation. German final devoicing is a
whole grammar in one rule, conditioned on a coda rather than a word edge:

```python
german = shipped("german-final-devoicing")
ipa.rewrite("taːɡ", german)  # 'taːk'
ipa.rewrite("liːb.lɪç", german)  # 'liːp.lɪç'   devoices word-internally too
ipa.rewrite("ʁaː.dəs", german)  # 'ʁaː.dəs'   an onset, so it does not
```

French liaison is the deletion example, conditioned across a word boundary:

```python
french = shipped("french-liaison")
ipa.rewrite("lez‿ami", french)  # 'le‿zami'   the /z/ surfaces
ipa.rewrite("lez‿ʃjɛ̃", french)  # 'le‿ʃjɛ̃'   and here it does not
ipa.rewrite("lez", french)  # 'le'
```

The two loanword sets are the insertion examples:

```python
ipa.rewrite("skul", shipped("spanish-accented-english"))  # 'eskul'
ipa.rewrite("stap", shipped("spanish-accented-english"))  # 'estap'
```

## 8. Writing your own rule set

A rule set is one rule per line; `#` starts a comment and `;` names a rule. Order
matters, and each rule sees the previous rule's output.

```python
my_rules = ipa.ruleset(
    """
    # Voice a plosive between vowels, then nasalize a vowel before a nasal.
    [manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; intervocalic voicing
    [vowel] -> [nasalized=+] / _ [manner=nasal]        ; nasalization
    """,
    name="my-rules",
)
len(my_rules)  # 2
ipa.rewrite("atapan", my_rules)  # 'adabãn'
```

The two halves of a rule are separable, because *"where does a plosive stand between
vowels"* is a useful question with no rewrite attached:

```python
r = ipa.rule("[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing")
r.recognize("atapa")
# [Site(start=1, end=2, left=(0,), right=(2,), bindings=()), Site(start=3,
# end=4, left=(2,), right=(4,), bindings=())]
ipa.rewrite("atapa", r)  # 'adaba'
```

```console
$ ipakit rules recognize -r "[manner=plosive] -> [voiced=+] / [vowel] _ [vowel]" atapa
atapa: 2 sites
  [manner=plosive] -> [voiced=+] / [vowel] _ [vowel]  @1  t  a _ a
  [manner=plosive] -> [voiced=+] / [vowel] _ [vowel]  @3  p  a _ a
```

A misspelled feature name or value fails loudly on both sides of the arrow, rather than
quietly building a constraint nothing satisfies. Both arms matter: an undeclared *value*
used to build a constraint no phone could meet and match nothing, in silence.

```python
def rule_error(text):
    """The message `ipa.rule` refuses this rule with."""
    try:
        ipa.rule(text)
    except ipa.RuleError as problem:
        return str(problem)
    return None

rule_error("[mannr=plosive] -> t")
# "'[mannr=plosive]' names undeclared feature(s): ['mannr']"
rule_error("[manner=obstruent] -> [voiced=-]")
# "'[manner=obstruent]': 'obstruent' is not a value of feature 'manner';
# declared values are ['affricate', 'approximant', 'fricative', 'nasal',
# 'plosive', 'silence', 'tap', 'trill', 'vowel']. 'obstruent' is a natural
# class over those values; ask for it as the bare term '[obstruent]'"
```

A rule can also **bind a value and re-use it**, which is SPE's agreement variable. A Greek
letter in the value slot means *this value, whatever it is, and the same one everywhere
else the rule writes that letter* — so nasal place assimilation is one rule rather than one
rule per place, which is what the shipped English set had before:

```python
ipa.rewrite("anpa", "n -> [place=α] / _ [place=α]")  # 'ampa'
ipa.rewrite("anka", "n -> [place=α] / _ [place=α]")  # 'aŋka'
```

The left of the arrow binds and the right refers, so a variable nothing on the left names
is refused rather than resolving at some sites and not at others. `-α` is the *opposite*
value, which exists only where the feature is binary:

```python
rule_error("n -> [place=α]")
# "'n -> [place=α]' writes the variable(s) α on the right of the arrow, and
# nothing on the left binds them. A variable takes its value from what the
# rule MATCHED, so it has to appear in the target or the context: 'n ->
# [place=α] / _ [place=α]'."
ipa.rewrite("asta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")
# 'asda'
rule_error("n -> [place=-α] / _ [place=α]")
# "'[place=-α]' writes the opposite of a variable on 'place', which declares
# 14 values (bilabial, labiodental, dental, alveolar, postalveolar,
# alveolo-palatal, palatal, bilabial^palatal, velar, bilabial^velar, uvular,
# pharyngeal, epiglottal, glottal). 'The opposite' is well defined only for a
# binary feature with two of them; for an n-ary feature name the value you
# mean, or use the plain variable to say the two agree."
```

The letter itself is checked against the inventory rather than taken on trust, because the
second member of the traditional series is a registered phone:

```python
rule_error("n -> [place=β] / _ [place=β]")
# "'β' spells something this inventory registers (β), so it cannot also be an
# agreement variable -- a variable that reached a form would be a phone. The
# letters free today are α γ δ ε ζ η ..."
```

A rule set is a file. The ones that come with ipakit travel in the package and are asked
for by name from wherever you happen to be, the way `shipped()` asks for them above;
`--file` is for one of your own:

```console
$ ipakit rules apply --set german-final-devoicing taːɡ
taːk
```

[rules.md](rules.md) is the full notation — every operator, the tier model, and the
known limits, which are a queue rather than a disclaimer.

## 9. When there is more than one right answer

Every rule so far has been obligatory: one form in, one form out. A great deal of
pronunciation is not like that. French *petit* is [pəti] **and** [pti], from one speaker
in one conversation, and neither is derived from the other.

Write the arrow `~>` instead of `->` and the rule becomes **optional** — it may fire at
a site, or it may not. `variants` is then the entry point, and it answers with a set:

```python
ipa.variants("kæt", "t ~> ʔ / _ #").forms  # ('kæt', 'kæʔ')
```

The shipped French set ships that: *e caduc*, the schwa that may drop, ordered after the
liaison and deletion rules section 7 showed.

```python
french.variants("pətit").forms  # ('pəti', 'pti')   petit
french.variants("samədi").forms  # ('samədi', 'samdi')   samedi
french.variants("vɑ̃dʁədi").forms  # vendredi: three consonants, so it may not
# ('vɑ̃dʁədi',)
```

**Each site chooses on its own.** That is the point, and it is what a word with two
droppable schwas needs. *Devenir* has three real pronunciations, and the fourth
combination — three consonants in a row — is not one of them:

```python
french.variants("dəvəniʁ").forms  # ('dəvəniʁ', 'dəvniʁ', 'dvəniʁ')
```

The obligatory entry points are untouched. `rewrite` takes no optional choice, so it
still answers with one form — and that form is always the first variant, by
construction rather than by agreement:

```python
ipa.rewrite("pətit", french)  # 'pəti'
french.variants("pətit")[0].form == ipa.rewrite("pətit", french)  # True
```

Every member carries its own derivation, so it can account for itself:

```python
[step.rule for step in french.variants("pətit")[1].derivation.fired]
# ['final t deletion', 'e caduc (first syllable)']
```

From a shell, `variants` is `apply` for a set with an optional rule in it:

```console
$ ipakit rules variants -s french-liaison pətit dəvəniʁ
pətit: 2 variants
  pəti
  pti
dəvəniʁ: 3 variants
  dəvəniʁ
  dəvniʁ
  dvəniʁ
```

Optional rules multiply, so the enumeration is capped — and **the cap is never silent**.
Ask `complete`, and on the command line the count line says it outright:

```python
many = ipa.variants("aaaa", "[vowel] ~> [length=long]", limit=4)
many.complete  # False
many.unexplored  # 12   at least this many choices declined
ipa.variants("aaaa", "[vowel] ~> [length=long]").complete  # True
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

```console
$ ipakit tract heads
head          length cm  description
------------  ---------  ------------------------------------------
adult-female  15.0       Adult female mid-sagittal tract
adult-male *  17.5       Adult male mid-sagittal tract
child         10.5       Child (approx. 5 years) mid-sagittal tract
```

`ipakit tract draw t -o t.svg` writes one, and `figure` is the same call from Python,
returning a whole SVG document as a string:

```python
from ipakit.tract_svg import figure
figure("t").startswith("<svg ")  # True
len(figure("t")) > 10000  # True
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

## 11. Extending the inventory

The shipped inventory registers the phones on the IPA chart, and reads everything else by
composing it. A composed unit works as **input** everywhere a registered one does, with no
setup at all:

```python
ipa.describe("tʰ")  # 'voiceless aspirated alveolar plosive'
round(ipa.distance("tʰ", "t"), 4)  # 0.0476
[p for p, _ in ipa.nearest_phones("tʰ", n=3)]  # ['t', 'ȶ', 'p']
```

So most of what "register this sound" sounds like it buys, you already have. What it buys
is **membership**: a seat in the pools the library draws *answers* from, and a place in the
distribution it normalizes against. Today `tʰ` is in neither, which is why the write side
has nothing to say about it:

```python
ipa.respell("t", release="aspirated")  # no registered phone spells this
```

A **supplement** is a second XML file merged over `ipa.xml` at load time. It adds symbols
and declares nothing else:

```xml
<?xml version='1.0' encoding='utf-8'?>
<!-- Aspirated stops, registered as phones of their own: the worked
     supplement, shipped beside supplement.rng so an install carries an
     instance of the format and not only the grammar for it. Nothing loads
     it. A supplement is opt-in, per instance, and asked for by name:
     load_ipa_features(supplements=["aspirated-stops"]). -->
<supplement name="aspirated-stops">
  <phones>
    <phone name="pʰ"/>
    <phone name="tʰ"/>
    <phone name="kʰ"/>
  </phones>
</supplement>
```

That file ships in the package, which is why the line below names it instead of
spelling a path:

```python
inventory = ipa.load_ipa_features(supplements=["aspirated-stops"])
len(inventory.phones)  # 142
inventory.respell("t", release="aspirated")  # 'tʰ'
```

An entry that states no features takes them from its own spelling, so the registered
reading and the composed reading are one fact rather than two copies of it:

```python
ipa.features("tʰ") == inventory.get_features("tʰ")  # True
```

The raw distance is inventory-independent and does not move. The *normalized* reads do,
because they are percentiles within a reference inventory and the reference just gained
three phones — so a supplemented inventory needs its own derived matrix, which
`DistanceModel.derive` builds and `save` keeps:

```python
model = ipa.DistanceModel.derive(inventory)
model.reference_name  # 'ipa+aspirated-stops'
inventory.distance("tʰ", "t") == ipa.distance("tʰ", "t")  # True
round(model.confusability("tʰ", "t"), 4)  # 0.9637
round(ipa.confusability("tʰ", "t"), 4)  # 0.9624
```

The instance is yours alone. Nothing loads a supplement unless you ask it to, so the
shipped matrix and every module-level call still answer for the bare inventory:

```python
"tʰ" in ipa.load_ipa_features().phones  # False
"tʰ" in ipa.distance_model().reference_phones  # False
```

[supplements.md](supplements.md) is the reference: what a supplement may declare, how it
merges, what it does to `to_phone`'s choice of winner, and how to carry your own derived
data.

## Where to go next

- [docs/README.md](README.md) — what every document is for, and the order to read them.
- [rules.md](rules.md) — the rule notation in full.
- [calculus.md](calculus.md) — the algebra over the set of forms that `~>` opens.
- [form.md](form.md) — the representation under the rule engine.
- [supplements.md](supplements.md) — registering sounds the shipped inventory does not have.
- [distance.md](distance.md) — what the metric claims, and what it does not.
- [ties.md](ties.md) — tie bars, diacritics, and how a unit is put together.
- [reviewing.md](reviewing.md) — how defects in this library have actually been found.
