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

# IPAkit task tutorial

ipakit answers questions about speech sounds: *what is this sound, what is it like, what
else is like it, how do I write it in some other notation, and what happens to it in
context.* This page walks through those tasks in that order. Every command and every
value below was produced by running it.

Each section covers a task through both the command line and the Python API,
so you can use the same operation interactively or in a program.

Installing ipakit also installs its published tiergraph dependency:

```bash
pip install ipakit
```

That puts an `ipakit` command on your path and makes `import ipakit` work.

To run this page rather than read it, `ipakit notebook` writes a Jupyter notebook of the
same material into the current directory: the same examples as cells, with the answers
left out for you to produce. The page and notebook are generated from the same source.

Throughout, the Python examples assume:

```python-run
import ipakit as ipa
import tempfile
from pathlib import Path
```

For detailed reference material, see
[docs/README.md](README.md) — in particular [distance.md](distance.md) for why the
distance is not a metric, [ties.md](ties.md) for the tie model, [form.md](form.md) for
the representation, and [rules.md](rules.md) for the full rule notation. The
[glossary](glossary.md) introduces the linguistic terms used here.

## 1. Sound descriptions and feature bundles

The two basic reads are a **name** and a **feature bundle**. `describe` gives the name a
phonetician would use; `features` gives the bundle the rest of the library computes over.
A [distinctive feature](glossary.md#distinctive-feature--feature-bundle) is one
contrastive dimension of a speech sound. On the IPA chart, the consonant rows largely
encode manner, the columns encode place, and voicing supplies another dimension; a
feature bundle is that decomposition written as data.

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

Diacritics compose with registered phones. An aspirated /p/ combines /p/ with
the aspiration mark's declaration:

```python-run
ipa.describe("pʰ")
ipa.features("pʰ", with_defaults=False)
ipa.describe("ḁ")
```

> **Feature display defaults.** `features(phone)` returns
> the *full* bundle — every feature, defaults included — and `with_defaults=False` gives
> only what the phone states. `ipakit features p` is the other way round: it shows only
> the stated features, and `--all` adds the defaults. So the two spellings of "the
> features of /p/" give 4 keys and 24 keys respectively.

```python-run
len(ipa.features("p"))                 # the API default: everything
len(ipa.features("p", with_defaults=False))
```

Short codes are the compact form, useful when you are reading a lot of them at once:

```console-run
$ ipakit features p --short
$ ipakit features kæt --short
```

## 2. Phonetic distance and nearest phones

`distance` is an inventory-independent magnitude in `[0, 1]` over the feature bundles: 0 means the same phone, and larger is more different. A voicing contrast is small; a consonant against a vowel is large.

```python-run
ipa.distance("p", "b")
ipa.distance("p", "k")
ipa.distance("p", "a")
```

```console-run
$ ipakit distance pair p b
$ ipakit distance pair p a
```

`nearest_phones` finds the closest phones in a reference inventory and reports raw structural distances. A query that belongs to the reference inventory appears first at 0.0, using one of the requested result slots:

```python-run
ipa.nearest_phones("p", n=5)
```

```console-run
$ ipakit analysis nearest p -n 5
```

Raw distances are hard to interpret on their own, because the range that actually occurs is narrow — the median over the inventory is about 0.19 and the top half of `[0, 1]` is unreachable. **`confusability` places the pair in the whole inventory's similarity distribution.** That percentile is an inventory-relative position, not a distance magnitude, and it is not comparable to one from another inventory. Its complementary model distance reserves 0.0 for the same phone; the closest distinct pair sits just above zero:

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

> **Word comparison scales.** `ipakit distance word` prints the
> inventory-relative `distance_model().word_distance` score by default; add `--raw` to print `word_similarity`. Reach for `confusability`/`distance_model` when you want positions comparable across pairs under one stated reference inventory, and `word_similarity` or `distance word --raw` when you want the raw edit path. Neither scale is comparable to the other, and model positions are not comparable across inventories.

```console-run
$ ipakit distance word kæt kæd
$ ipakit distance word --raw kæt kæd
```

A word comparison also reports `coverage`, the shorter token count over the longer.
This separate value helps distinguish a length mismatch from differences between
similarly sized forms.

```python-run
ipa.word_distance("kætəloɡ", "kæt").coverage
ipa.word_distance("kætəloɡ", "ɡolətæk").coverage
```

Two shapes come up often enough to name. **`nearest_pronunciation`** answers "is this an
acceptable pronunciation?" — the best match of a form against the several transcriptions a
lexicon lists (free variants, a homograph read two ways), reporting which one won rather
than a bare number.

```python-run
match = ipa.nearest_pronunciation("kat", ["kæt", "kɑt"])
match.accepted, round(match.similarity, 3)
```

**`sequence_distance`** scores phone tokens you already hold — one element per unit —
without re-tokenizing, so boundaries you drew (`d͡ʒ` as one token) are kept as given.

```python-run
ipa.sequence_distance(["k", "a", "t"], ["k", "æ", "t"]).similarity
```

`distance` is symmetric, bounded and zero on identity, but about 0.5% of measured
triples violate the triangle inequality. Algorithms such as metric trees that require
that inequality need `ipakit.closure.MetricClosure`. [distance.md](distance.md)
describes these restrictions and the closure's inventory-relative behavior.

When a score needs an explanation, `explain_word_distance` exposes the alignment operation at each position and, for a substitution, the feature and tract terms that contributed to its cost.

```python-run
explanation = ipa.explain_word_distance("kæt", "kæd")
[(step["op"], step["a"], step["b"]) for step in explanation]
[term["label"] for term in explanation[-1]["terms"] if term["cost"] != 0]
sum(step["cost"] for step in explanation)
```

## 3. Feature queries and natural classes

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

## 4. Notation conversion

The following examples convert supported ASCII and machine notations in both directions:

```python-run
ipa.to_cmu("kˈæt")
ipa.from_cmu(["K", "AE1", "T"])
ipa.to_xsampa("t͡ʃ")
ipa.from_xsampa("t_S")
ipa.to_timit("kæt")
ipa.from_timit(["k", "ae", "t"])
ipa.to_kirshenbaum("ʃɑk")
ipa.from_kirshenbaum("SAk")
```

```console-run
$ ipakit convert to-cmu "kˈæt"
$ ipakit convert from-cmu K AE1 T
$ ipakit convert to-xsampa "t͡ʃ"
$ ipakit convert from-xsampa t_S
```

The CMU converter places the stress mark immediately before the vowel. The rule
engine uses that nucleus-leading convention in the examples in section 7.

You can read features straight out of a non-IPA symbol without converting first:

```python-run
ipa.features_from_xsampa("t_S")[0]["manner"]
ipa.features_from_cmu("K")[0]["place"]
```

**Converters skip what they cannot map**, and `strict=True` raises instead:

```python-run
ipa.to_cmu("k4t")                      # the '4' is dropped
```

> **Loss is explicit.** `ipakit convert to-cmu "k4t"` prints `K T`, warns that `4` was
> dropped, and exits 3, just as `ipakit features "k4t"` does under the CLI's lossy-read
> policy. Pass `--strict` to refuse the partial conversion instead.

## 5. Transcription units and structure

`segments` extracts speech sounds, omitting boundary markers:

```python-run
ipa.to_ipa(ipa.segments("#kæt.dɒɡ#"))
```

Use `Form` to retain the word marks and syllable break along with the sounds.
It provides round-trip serialization and named views of its structure.

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

Keep a `Form` when later operations need its structure, and select narrower views
at the point of use. [form.md](form.md) describes those views and the
`Form.rebuild` contract.

### Form construction, navigation and serialization

`FormBuilder` constructs the same graph-backed `Form` without requiring an IPA string to express its hierarchy. Builder handles are temporary construction identities; after `build()`, navigation returns canonical graph paths.

```python-run
builder = ipa.FormBuilder()
utterance = builder.begin("utterance")
phrase = builder.begin("phrase")
segment_nodes = builder.append_ipa("kæt")
builder.end(phrase)
builder.end(utterance)
builder.contain(phrase, segment_nodes)
builder.contain(utterance, (phrase,))
builder.add_root(utterance)
built = builder.build()

built.to_ipa()
built.direct_children(built.roots[0])
built.leaves(built.roots[0])
```

`Form.to_json()` writes the complete native tier graph, including typed facts, relations, optional timing, and the binding to the restoring inventory. Compact and indented output use the same TierGraph codec. `ipa.read_json()` validates the Form profile and restores a real Form; `ipakit.read_graph_json()` returns a native Graph for general graph documents. See [Graph JSON](graph-json.md) for the admission contract.

```python-run
import json

native_wire = json.loads(built.to_json())
native_wire["format_version"]
built.to_json() == ipa.read_json(built.to_json()).to_json()
ipa.read_json(built.to_json()).to_ipa()
```

## 6. Transcription validation

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

## 7. Allophonic rule application

A rule is the classical generative statement — rewrite `A` as `B` between `C` and `D`:

```python-run
ipa.rewrite("bˈʌtɚ", "t -> ɾ / [vowel stress=primary] _ [vowel]")
```

```console-run
$ ipakit rules apply -r "t -> ɾ / [vowel stress=primary] _ [vowel]" bˈʌtɚ
```

The shipped rule sets are discoverable from the command line:

```console-run
$ ipakit rules list
```

`american-english` is the worked example: an ordered cascade taking a broad, phonemic transcription to a narrow, phonetic one.

```console-run
$ ipakit rules list american-english
```

Applying the whole set, and asking what fired:

```console-run
$ ipakit rules apply -s american-english pˈɪn
$ ipakit rules trace -s american-english pˈɪn
$ ipakit rules trace -s american-english bˈʌtɚ
```

The top-level API follows the same path: `available()` lists the shipped names,
`ruleset(name)` resolves one, and `shipped(name)` loads one explicitly.

```python-run
ipa.available()
english = ipa.ruleset("american-english")
ipa.shipped("american-english").name
len(english)
ipa.rewrite("pˈɪn", english)
```

`derive` returns a derivation object that retains every step:

```python-run
derivation = ipa.derive("pˈɪn", english)
derivation.result
[step.rule for step in derivation.steps if step.fired]
```

Stress is carried by the nucleus. Both standard syllable-leading notation and the house
nucleus-leading spelling give rules the same stressed-vowel reading:

```python-run
ipa.rewrite("ˈpɪn", english)           # leading stress seats on the nucleus: aspirated
ipa.rewrite("pˈɪn", english)           # stress on the nucleus: aspirated
```

The explicit normalizer remains available for output conversion, and `from_cmu` already
produces the house convention:

```python-run
features = ipa.load_ipa_features()
features.normalize_stress_to_nucleus("ˈpɪn")
ipa.from_cmu(["P", "IH1", "N"])
```

Aspiration is conditioned on a syllable margin, which is why
`spin` does not aspirate — the margin there is taken by /s/:

```python-run
ipa.rewrite("spˈɪn", english)
```

A margin-conditioned rule requires an explicit margin. A word written with no
interior dot leaves its interior margins unstated, so the rule does not fire there:

```python-run
ipa.rewrite("ə.tˈæk", english)         # margin written
ipa.rewrite("ətˈæk", english)          # margin unspecified
```

The other four sets each demonstrate a different operation. German final devoicing is a
whole grammar in one rule, conditioned on a coda rather than a word edge:

```python-run
german = ipa.shipped("german-final-devoicing")
ipa.rewrite("taːɡ", german)
ipa.rewrite("liːb.lɪç", german)        # devoices word-internally too
ipa.rewrite("ʁaː.dəs", german)         # an onset, so it does not
```

French liaison is the deletion example, conditioned across a word boundary:

```python-run
french = ipa.shipped("french-liaison")
ipa.rewrite("lez‿ami", french)         # the /z/ surfaces
ipa.rewrite("lez‿ʃjɛ̃", french)         # and here it does not
ipa.rewrite("lez", french)
```

The two loanword sets are the insertion examples:

```python-run
ipa.rewrite("skul", ipa.shipped("spanish-accented-english"))
ipa.rewrite("stap", ipa.shipped("spanish-accented-english"))
```

### Curated loanword fixture to katakana

The `japanese-moraic` rules demonstrate locally curated gairaigo adaptations. Accent conversion and general Japanese speech modeling are outside this set's scope. The rewrite bridge preserves the broad input, each fired derivation layer, and derived morae on one graph-backed `Form`; the katakana codec renders those morae. This worked example uses ホット, whose spelling and borrowing from English *hot* are recorded in [Digital Daijisen](https://kotobank.jp/word/%E3%81%BB%E3%81%A4%E3%81%A8-3218764). That dictionary evidence supports the orthography; the exact IPA mapping is a local demonstration fixture.

```python-run
japanese = ipa.shipped("japanese-moraic")
hot_derivation = japanese.derive("hɑt")
hot_form = hot_derivation.to_form(mora_language="japanese")
hot_derivation.result
[event["value"] for event in hot_form.tier_events("mora")]

from ipakit._katakana_codec import render as render_katakana

render_katakana(hot_form)
```

The leading underscore on the codec module marks this as a backend surface rather than a stable top-level convenience API. Keeping the example executable still checks the complete rules → derivation → graph → derived morae → katakana path; applications should treat the curated fixture vocabulary as the codec's declared domain.

## 8. Custom rule sets

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

A misspelled feature name or value raises an error on either side of the arrow.
Validation covers both names and values:

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

Variable letters are checked against the inventory: `β`, the second letter in the
traditional series, is already a registered phone and is refused as a variable:

```python-run
rule_error("n -> [place=β] / _ [place=β]")
```

A rule set is a file. The ones that come with ipakit travel in the package and are asked
for by name from wherever you happen to be, the way `shipped()` asks for them above;
`--file` is for one of your own:

```console-run
$ ipakit rules apply --set german-final-devoicing taːɡ
```

[rules.md](rules.md) describes the operators, tier model and supported syntax.

## 9. Optional rules and pronunciation variants

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

`rewrite` applies obligatory changes and returns one form. It follows the same
execution path as the first variant:

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

Optional rules multiply, so enumeration has a configurable cap. `complete` reports
whether enumeration finished; the CLI includes this status in its count line:

```python-run
many = ipa.variants("aaaa", "[vowel] ~> [length=long]", limit=4)
many.complete
many.unexplored                         # at least this many choices declined
ipa.variants("aaaa", "[vowel] ~> [length=long]").complete
```

[calculus.md](calculus.md) describes closure, identity, composition, finiteness and
the limits of capped enumeration.

## 10. Articulation visualization

The feature data is backed by a declared vocal-tract geometry, and that geometry can be drawn. The checked-in mid-sagittal figures under [figures/](figures/) are regenerated with `make figures`:

```bash
make figures
```

Each is drawn through `Head.project` by `ipakit.tract_svg`, using the declared
geometry. Inspecting these figures has exposed model defects beyond the test suite's checks.

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

The animation backend chooses the most specific complete description available: complete timed articulatory targets, otherwise untimed gestures, otherwise segment-derived constrictions. A partially timed target tier falls back to gestures as a whole, so it never silently drops the untimed occurrences.

```python-run
from ipakit._gesture_backend import oral_tract_frames
from ipakit._gesture_graph import project as project_gestures
from ipakit import Timing
from ipakit.form import _graph_from_units

gesture_inventory = ipa.IPAFeatures()
segment_form = Form.parse("at", gesture_inventory)
segment_graph = _graph_from_units(segment_form.units, ())
gesture_graph = project_gestures(segment_graph, gesture_inventory)
timed_graph = project_gestures(segment_graph, gesture_inventory, target_timing={"/clock/0/segment/0": (Timing(0.0, 0.1),), "/clock/1/segment/0": (Timing(0.1, 0.1),)})
partial_graph = project_gestures(segment_graph, gesture_inventory, target_timing={"/clock/0/segment/0": (Timing(0.0, 0.1),)})

tuple(dict.fromkeys(frame.level for frame in oral_tract_frames(timed_graph, gesture_inventory)))
tuple(dict.fromkeys(frame.level for frame in oral_tract_frames(gesture_graph, gesture_inventory)))
tuple(dict.fromkeys(frame.level for frame in oral_tract_frames(segment_graph, gesture_inventory)))
tuple(dict.fromkeys(frame.level for frame in oral_tract_frames(partial_graph, gesture_inventory)))
```

These gesture modules are backend interfaces, so their underscore-prefixed imports are intentionally more specialized than the public `Form` and rewrite APIs above.

## 11. Corpus construction and queries

A directory corpus keeps canonical forms under named roles. The query notation is the
left, recognizing half of a rewrite rule, so the same context can be searched and then
used in a derivation:

```python-run
corpus_path = Path(tempfile.mkdtemp()) / "speech"
speech = ipa.corpus.create(corpus_path)
speech.add("one", {}, {"broad": ipa.read("an")})
[(m.fileid, m.role, m.text) for m in ipa.corpus.query(speech, "[nasal] / [vowel] _ #", role="broad")]
query = ipa.parse_query("n / _ [place=α]")
query.target.source
grammar = ipa.rules.RuleSet.parse("n -> m / _ [place=bilabial]")
type(ipa.corpus.derives(grammar, "anp", "amp")).__name__
```

The command-line equivalents are `ipakit query '<dsl>' IPA...` for ephemeral strings,
and the `ipakit corpus init`, `add`, `query`, and `derives` commands for a stored
collection. See [corpus.md](corpus.md) for the grammar and stable record columns.

## 12. Inventory supplements

The shipped inventory registers the phones on the IPA chart, and reads everything else by
composing it. A composed unit works as **input** everywhere a registered one does, with no
setup at all:

```python-run
ipa.describe("tʰ")
round(ipa.distance("tʰ", "t"), 4)
[p for p, _ in ipa.nearest_phones("tʰ", n=3)]
```

Registration adds membership in the pools the library draws answers from and
the distribution it normalizes against. The default inventory excludes `tʰ`
from those pools, so respelling cannot select it:

```python-run
ipa.respell("t", release="aspirated")   # no registered phone spells this
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

```python-run
inventory = ipa.load_ipa_features(supplements=["aspirated-stops"])
len(inventory.phones)
inventory.respell("t", release="aspirated")
```

An entry that states no features takes them from its own spelling, so the registered
reading and the composed reading are one fact rather than two copies of it:

```python-run
ipa.features("tʰ") == inventory.get_features("tʰ")
```

The raw distance is inventory-independent and does not move. The *normalized* reads do,
because they are percentiles within a reference inventory and the reference just gained
three phones — so a supplemented inventory needs its own derived matrix, which
`DistanceModel.derive` builds and `save` keeps:

```python-run
model = ipa.DistanceModel.derive(inventory)
model.reference_name
inventory.distance("tʰ", "t") == ipa.distance("tʰ", "t")
round(model.confusability("tʰ", "t"), 4)
round(ipa.confusability("tʰ", "t"), 4)
```

The instance is yours alone. Nothing loads a supplement unless you ask it to, so the
shipped matrix and every module-level call still answer for the bare inventory:

```python-run
"tʰ" in ipa.load_ipa_features().phones
"tʰ" in ipa.distance_model().reference_phones
```

[supplements.md](supplements.md) is the reference: what a supplement may declare, how it
merges, what it does to `to_phone`'s choice of winner, and how to carry your own derived
data.

## Further reading

- [docs/README.md](README.md) — what every document is for, and the order to read them.
- [rules.md](rules.md) — the rule notation in full.
- [calculus.md](calculus.md) — the algebra over the set of forms that `~>` opens.
- [form.md](form.md) — the representation under the rule engine.
- [supplements.md](supplements.md) — registering sounds the shipped inventory does not have.
- [distance.md](distance.md) — what the metric claims, and what it does not.
- [ties.md](ties.md) — tie bars, diacritics, and how a unit is put together.
- [reviewing.md](reviewing.md) — how defects in this library have actually been found.
