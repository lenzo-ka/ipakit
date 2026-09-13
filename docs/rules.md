# Rewrite rules

A rule is the classic generative statement:

```
A  ->  B  /  C _ D
```

*Rewrite `A` as `B` when it stands between `C` and `D`.* This guide describes the notation, matching behavior, and supported operations. The engine is `ipakit.rules`; its representation is `ipakit.form`, documented in [form.md](form.md).

```python
import ipakit as ipa

ipa.rewrite("bˈʌtɚ", "t -> ɾ / [vowel stress=primary] _ [vowel]")
# 'bˈʌɾɚ'
```

## The two halves are separable

Recognition locates the target in its context; the action specifies its replacement. Both operations are available separately, so a caller can locate plosives between vowels before deciding whether to rewrite them.

```python
r = ipa.rule("[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing")

r.recognize("atapa")   # [Site(start=1, end=2, left=(0,), right=(2,), bindings=()), Site(start=3, end=4, left=(2,), right=(4,), bindings=())]
r.edits("atapa")       # what it would do, without doing it
ipa.rewrite("atapa", r)                 # 'adaba'
ipa.derive("atapa", r).trace()          # the same, with an account
```

A `Site` records the neighbors that licensed the match. An entry is `None` where the context matched a virtual form edge. `bindings` records the values of [agreement variables](#a-rule-may-bind-a-value-and-re-use-it) and is empty for a rule without variables.

The rule engine scans each changing linear derivation. When a derivation is
projected into a tier graph, its original input clock remains the axis:
insertions anchor to an input boundary, deletions retain an empty-target
`rewrites-to` relation, and later broad/narrow/allophonic events do not rebase
earlier positions. The graph records the order produced by that scanner,
including deterministic phantom events.

## Finite token projections

The notation below defaults to the house model. Finite foreign inventories have
an explicit token-projection API using the **same** Pattern/Query/Action/Rule
scanner, edit splicer and feeding cascade. They do not parse tokens as house IPA
or run the native surface rules:

```python
from ipakit.finite_model import FeatureSchema, FiniteModel
from ipakit.rules import RuleSet, parse

model = FiniteModel(
    "demo",
    FeatureSchema({"spark": ("dim", "bright"), "host": ("gate", "body")}),
    {"@D": ("dim", "body"), "@B": ("bright", "body"), "@G": ("bright", "gate")},
)
rule = parse("[spark=dim] -> [spark=bright] / _ [host=gate]", model=model)
result = rule.rewrite_tokens(("@D", "@G", "@D", "@B"))
assert result.tokens == ("@B", "@G", "@D", "@B")
assert rule.recognize_tokens(("@D", "@G"))[0].right == (1,)
feeding = parse("[spark=bright host=body] -> [host=gate]", model=model)
assert RuleSet((rule, feeding)).derive_tokens(("@D", "@G")).tokens == ("@G", "@G")
```

These rules bind the finite model's content identity, operation, notation and
`unique-or-refuse` realization policy. Supplying another `model=` to execution
refuses even on empty input or when nothing would match. Every input token is
validated before scanning. Bound query, action, target and context children must
retain the same model ownership; composing a fresh AST does not silently rebind
a child compiled for another model. Genuinely unbound ASTs and same-model child
reuse remain supported. A feature edit invokes the finite provider's exact
realization relation: no candidates raises `ModelRuleError` with code
`unrealizable`; multiple candidates raises code `ambiguous`, retaining the full
`candidates` tuple. A requested no-op on an aliased bundle is still ambiguous.
An unknown token raises the provider's `MissingToken`; invalid feature/value
constraints raise `InvalidFeature`. These are not successful no-match results.

For typed values and punctuation-bearing tokens, construct the same AST and
call `bind(model)`:

```python
from ipakit.rules import Action, FeatureChanges, FeatureConstraint, Pattern, Query, Rule

rule = Rule(
    "brighten",
    Query(Pattern("dim", constraints=(FeatureConstraint("spark", ("dim",)),))),
    Action(finite=FeatureChanges({"spark": "bright"})),
).bind(model)
assert rule.rewrite_tokens(("@D",)).tokens == ("@B",)
```

`FeatureConstraint` admits a tuple of typed alternatives; `exclude=True` negates
that membership test. Booleans, integers and strings remain distinct, including
in equality/hash keys. `None` explicitly tests or writes a missing cell; it is
not zero or an omitted term. Exclusion matches a missing cell unless `None` is
among the excluded values. `LiteralTokens((...))` is an alternative `Action`'s
`finite=` payload for an exact replacement token sequence, including reserved
punctuation. `Action()` deletes a matched token. Native `becomes=` and native
pattern feature/prosody fields are not interchangeable with these finite AST
fields; unsupported mixtures refuse during binding.

The finite safe-bare DSL supports exact literals and explicit `feature=value`
terms, fixed left/right contexts, and `∅` for deletion. Values decode against
the declared domain; if `1` could mean integer `1` or string `"1"`, use the typed
AST. Quoted literals, named `;` suffixes, agreement, quantifiers, optional rules,
insertion, boundaries, natural classes and structural/prosodic terms are outside
this finite slice and refuse. A feature named `stress` is an ordinary foreign
feature, not native prosody. `model=` and native `features=` cannot be combined.

Input must be an explicit tuple/list of token strings, not a concatenated
string, Form, graph, or timing/attachment-bearing object. Results retain exact
token tuples, and each Step has `before_tokens`/`after_tokens`; display joins
are not used to reconstruct state. Native `variants` and `to_form` are not
finite graph conversions. Variant enumeration remains
separate work; this token API does not claim full-representation fidelity. See
[model-operations.md](model-operations.md) for the finite provider contract.

### Decorating an existing graph

`ipakit.model_graph.GraphBinding` is a separate, explicit input contract for
finite-model graph rewrites. Supply the native TierGraph `Graph`, `FiniteModel`,
ordered unique source `ItemRef`s, qualified token/model value relations,
`starts_at` relation, and clock tier. Optional `feature_values` maps model feature
names to qualified value relations; claims must match both the typed schema and
the exact token row. Values retain their native JSON structure and model
semantics. Caller order is retained, including selections across tiers.

Call `binding.derive(rules)` to run the same token engine and trace traversal.
The result exposes `graph`, `trace`, `final_refs`, and a content-based operation
`identity`. The writer edits the actual source graph: all original facts,
relations, document attributes and optional source timing remain intact. Derived
events are appended in deterministic step/site/application/target order and
anchor to actual original clock boundaries. Split children share their source
anchor; deletions have explicit empty-target history. All events use the original
clock. Silence can be selected independently of word membership. Original
containment remains in source history; target containment requires a separate
explicit policy.

Target physical timing is unassigned, even for a one-to-one change. The only
admitted migration policy is `preserve-source`; requested timing or attachment
migration refuses. Finite insertion needs a separate explicit anchor policy and
is not supplied here. No-match and empty selections validate their full binding
before returning a byte-identical source graph.

Use the native TierGraph codec to serialize the extended graph. Then
`result.restore(decoded_graph)` validates it against the explicit bound source,
model, selection and rules. Reconstructing equivalent binding and execution in
a fresh process works because validation uses content identity. Graph facts
persist independently; restoring an operation also requires the bound source,
model, selection and rules. This API validates bound operations. Operation-profile
reading and house `Form` conversion remain outside its scope, and other profiles
keep their existing admission rules.

### Explicit finite rules on the command line

`rules recognize`, `apply` and `trace` also accept the same explicitly selected
finite models. Without a model selector their native behavior is unchanged:

Save this JSON document as `corpus.json`:

```json
[["p", "a"], []]
```

Then run the first two commands from that directory. For the third, paste the
same document into stdin and finish with end-of-file (or redirect
`corpus.json` into stdin). No external model or rule file is needed:

```sh
ipakit rules recognize --model panphon --tokens-json corpus.json -r 'p -> b' -j
ipakit rules apply --model panphon --tokens-json corpus.json -r 'p -> b' -j
ipakit rules trace --model panphon --tokens-json - -r 'p -> b' -j
```

The JSON input is an array of arrays of exact nonempty token strings, for
example `[["p", "a"], []]`. `--tokens-json -` reads that same document from
stdin. An outer `[]` is an empty corpus; an inner `[]` is an empty input. No
Unicode normalization, segmentation, line stripping or house interpretation is
performed. Input punctuation remains part of the token identity; punctuation
that the safe-bare rule DSL cannot express requires the typed library AST.
Model selection is exactly one of `--model NAME`
and `--model-declaration PATH`. The former uses the canonical installed resource;
the latter uses the same validated ternary reader.

Repeated `-r` rules form an ordered cascade. Rule files use the existing
`RuleSet.from_file(model=...)` reader, including its comment handling. Every
recognition rule sees the original input independently; apply/trace feed each
rule's output into the next. The finite DSL retains the library's restrictions,
including refusal of named `;` suffixes, quoted literals, optional rules,
insertion, agreement and structural terms. Native `--set`, positional forms,
`--keep-zeros` and native XML selectors cannot be mixed with finite mode;
variants and graph inputs have no finite CLI route here.

Each result includes operation, model identity, exact input and status.
Recognition reports each rule's sites with exact target token slices and
left/right indices. Apply reports the resulting token array; trace adds actual
`before_tokens`, `after_tokens` and ordered `replacement_tokens` from the shared
cascade. `--all` retains steps that did not fire. Text output uses JSON quoting
too, so tokens never become an ambiguous concatenation.

Unknown inputs and deterministic ambiguity/unrealizability remain per-row error
records, with the actual exception type, code and complete candidate list.
Other rows are not dropped; any refused row makes the command exit 1, including
with `--lax`. A no-match or empty row is a successful result, but even an empty
rule file validates every supplied token. Invalid document shapes and missing
conditional configuration also exit 1; argparse syntax errors and mixed model
selectors exit 2. This does not redefine exit 3's native dropped-input meaning.

Declared single-value option arguments are literal, including a file named
`help`, in both native and finite mode, including argparse's unambiguous option
abbreviations. Compound short options and unsupported argument arities are left
unchanged for argparse itself; use `--help` with those forms. Genuine help
command tokens still work
(`ipakit help rules apply`, `ipakit rules apply help`). Option resolution uses
the existing argparse parser.

## Notation

| Piece | Means |
| --- | --- |
| `->` `→` `=>` | the rewrite arrow; any of the three |
| `~>` `~->` `~→` `~=>` | the same arrow, marked **optional**: the rule *may* fire |
| `/` | begins the context |
| `_` | where the target sits in the context |
| `;` | begins the rule's name |
| `#` | a word boundary |
| `.` | a syllable boundary |
| `%` | any boundary |
| `\|` `‖` `‿` | the declared prosodic break, major break, linking mark |
| `∅` `0` `Ø` | the empty string — insertion or deletion |
| `[...]` | a feature query |
| `[key=α]` | an **agreement variable**: this value, wherever else the rule writes `α` |
| `[key=-α]` | the *opposite* value; binary features only |
| `[key=∅]` | in a change: clear that prosodic value |
| `[zero]` | a structural zero — a position with no content |
| `(X)` | in a context: zero or one unit matching `X` |
| `(X)*` | in a context: zero or more units matching `X` |
| a bare glyph | that literal phone, with any prosody it wears |

The name separator is `;`. The character `|` retains its declared meaning as a prosodic break, so `t -> ʔ / _ |` is conditioned on that break. Earlier use of `|` as a name separator incorrectly made this rule unconditional.

### Feature queries

Bracketed items use the query language shared by `phones_matching` and `find`. Bare class terms and `key=value` terms may be mixed:

```
[vowel]                     manner=vowel
[manner=plosive voiced=-]   a voiceless plosive
[vowel stress=primary]      a stressed vowel
[-voiced]                   voiced is '-'  (SPE's [-voice])
[vowel -nasalized]          a vowel that is not nasalized
[obstruent]                 a natural class declared over manner's values
[obstruent -fricative]      that class, narrowed: the plosives and affricates
```

A bare term may also name a **natural class** the data declares: `natural-class="obstruent"` sits on the `fricative`, `plosive` and `affricate` values of `manner`, and `[obstruent]` asks for it. The class selects or excludes whole — `[obstruent]`, `[-obstruent]` — and narrows like any other term. Because it is read off the declaration, a manner added to `ipa.xml` belongs to the class only if the data says so. Three shipped rule sets used to write the class out as `[-vowel -approximant -nasal -trill -tap -silence]`, which selects the same phones today and would take a new manner in without a word.

A term that names nothing fails loudly on **both** sides of the arrow, on **both** arms of a `key=value`, and **whatever else the bracket contains** — an undeclared key, an undeclared value and an unresolvable bare term are equally an error, not a constraint that quietly matches nothing:

```python
ipa.rule("[mannr=plosive] -> t")
# RuleError: '[mannr=plosive]' names undeclared feature(s): ['mannr']
ipa.rule("[manner=obstruent] -> [voiced=-]")
# RuleError: '[manner=obstruent]': 'obstruent' is not a value of feature 'manner'; declared values are ['affricate', 'approximant', 'fricative', 'nasal', 'plosive', 'silence', 'tap', 'trill', 'vowel']. 'obstruent' is a natural class over those values; ask for it as the bare term '[obstruent]'
ipa.rule("t -> ɾ / [vowel] _ [vowel -stress]")
# RuleError: '[vowel -stress]': '-stress' resolves to no feature term; feature 'stress' is not binary...; negate them individually instead, as '-none -primary -secondary'
```

Values resolve through the alias table and `expand()`, including spelled aliases and generative overlaps such as `bilabial^velar`. Natural classes use bare terms: write `[obstruent]`. The invalid value expression `[manner=obstruent]` raises an error with that correction; older versions accepted it as an unsatisfiable constraint. The executable example above guards this refusal.

**Every** term must resolve, at every arity: a bracket that mixes a good term with a bad one raises rather than dropping the bad one, since a dropped term is a narrower query silently widened. The message names what would have worked. `stress` has no `-` to take — its values are `none`, `secondary` and `primary` — so a query about stress negates the marked values, `[vowel -primary -secondary]`; `none` is the unspelled ordinal anchor and matches no unit on its own.

## A rule may bind a value and re-use it

SPE's **agreement variable**. A Greek letter in the value slot means *this value, whatever it is, and the same one everywhere else the rule writes that letter*:

```python
ipa.rewrite("anpa", "n -> [place=α] / _ [place=α]")   # 'ampa'
ipa.rewrite("anka", "n -> [place=α] / _ [place=α]")   # 'aŋka'
```

That is one rule for a process that was otherwise one rule per place value — eleven or more in general, and two in the shipped English set, which enumerated the two places English happens to need and said in a comment that the general statement was not expressible.

**Recognition binds; the action refers.** A variable takes its value from the target or a context item. The action may use only variables bound during recognition; an unbound variable is refused at parse time:

```python
ipa.rule("n -> [place=α]")
# RuleError: 'n -> [place=α]' writes the variable(s) α on the right of the arrow, and nothing on the left binds them...
```

**Every occurrence in the recognition half must agree.** A site matches where all occurrences read the same value. This rule requires the target and its right neighbor to agree on place, then changes voicing:

```python
ipa.rewrite("atta", "[place=α] -> [voiced=+] / _ [place=α]")   # 'adta'
ipa.rewrite("atka", "[place=α] -> [voiced=+] / _ [place=α]")   # 'atka'
```

**A value has to be there to be bound.** No vowel declares a `place`, so `[place=α]` does not reach one and `/n/` before a vowel is left alone. That is the ordinary reading of any query term rather than a rule about variables:

```python
ipa.rewrite("ana", "n -> [place=α] / _ [place=α]")     # 'ana'
```

**A variable ranges over one feature.** The declared values of `place` and of `voiced` are different sets, so a variable over both is over nothing:

```python
ipa.rule("n -> [place=α] / [voiced=α] _ [place=α]")
# RuleError: ... uses the variable 'α' on two features, 'voiced' and 'place'...
```

Independent variables are how a rule speaks about two features at once, and `α`, `γ`, `δ` … are a supply rather than one name:

```python
ipa.rewrite("atkza", "[manner=plosive] -> [place=α voiced=γ] / _ [place=α] [voiced=γ]")
# 'aɡdza'
```

**A variable used once says nothing**, and is refused for the reason a misspelled feature is: it is what a typo looks like — `α` on the left and `γ` on the right is two lone variables, not one shared one.

```python
ipa.rule("n -> t / _ [place=α]")
# RuleError: ... uses the variable(s) α once...
```

### Disagreement, and where it stops

`-α` is SPE's *opposite value*. For a binary feature the opposite is well defined and this is dissimilation in one line:

```python
ipa.rewrite("asta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")   # 'asda'
ipa.rewrite("azta", "[manner=plosive] -> [voiced=-α] / [voiced=α] _")   # 'azta'
```

An n-ary feature has multiple alternative values, so `-α` is refused for it. For example, `place` supplies several alternatives to `velar`:

```python
ipa.rule("n -> [place=-α] / _ [place=α]")
# RuleError: '[place=-α]' writes the opposite of a variable on 'place', which declares 14 values...
```

### The letter is checked against the inventory

The traditional series is `α β γ`, and **the second member is a registered phone** — the voiced bilabial fricative — as are `θ` and `χ` further along it. So the series is not taken on trust: a variable is a Greek small letter that spells *nothing this inventory reads*, which is asked of the declaration rather than answered from a list.

```python
from ipakit import rules
"".join(rules.SERIES)                                        # 'αβγδεζηθικλμνξοπρστυφχψω'
"".join(rules._free_variables(ipa.load_ipa_features()))      # 'αγδεζηικλμνξοπρστυφψω'
ipa.rule("n -> [place=β] / _ [place=β]")
# RuleError: 'β' spells something this inventory registers (β), so it cannot also be an agreement variable...
```

Refused **by name and with the reason**, which is the half that matters. Skipping `β` in silence would surprise exactly the reader who knows the series best. The property being protected is the other direction: a variable must never be able to reach a form, because a leak would then spell a phone rather than fail — `units("aαb")` drops the `α` and `units("aβb")` does not.

A letter the inventory registers is a phone wherever it is written, so a bare `[β]` gets the same answer from the other direction — brackets ask for a class, and `β` names none:

```python
ipa.rule("t -> d / _ [β]")
# RuleError: '[β]' asks for a class named 'β', and 'β' spells a registered phone (β) rather than a class...
```

The series is the alphabet's small letters and only those. `ά` is alpha with a tonos and falls outside the endpoints; `ς` is sigma at the end of a word and falls between `ρ` and `σ`, inside them — so a letter must also be the one its own capital lowercases back to. Two members that differ only in how they are drawn would be a notation whose typos are invisible.

The rule holds in both directions and the declaration always wins: declare `α` as a phone tomorrow and it stops being notation, loudly, exactly as `~` would.

## Stress is not part of a phone's identity

`features("a")`, `features("ˈa")` and `features("aː")` are one bundle: the `mode="prosodic"` features live on the unit, outside the feature bag (see [ties.md](ties.md)). So:

```python
ipa.rewrite("kˈat", "a -> ɑ")      # 'kˈɑt'  -- 'a' matches the stressed 'ˈa'
```

Prosody has a separate **namespace** on the unit. Rules can query and modify it while matching the phone's identity independently:

```
[vowel]                  any vowel, stressed or not
[vowel stress=primary]   only the stressed one
```

A query term routes to whichever namespace *declares* it, read off `Feature.mode`, so no list of prosodic feature names appears in the engine.

### Writing prosody

Assign, change, clear — the same query language on the right of the arrow:

```python
ipa.rewrite("ka",   "[vowel] -> [length=long] / _ #")     # 'kaː'   lengthen
ipa.rewrite("kaː",  "[vowel] -> [length=normal] / _ #")   # 'ka'    shorten
ipa.rewrite("at",   "[vowel] -> [stress=primary] / # _")  # 'ˈat'   assign stress
ipa.rewrite("kˌat", "[vowel] -> [stress=primary]")        # 'kˈat'  restress
ipa.rewrite("kˈat", "[vowel] -> [stress=∅]")              # 'kat'   destress
```

**Removal is `∅`.** The notation already spells "nothing" three ways for a whole unit (`t -> ∅`); `[stress=∅]` is that same word applied to one dimension of one unit instead of to the unit. No new vocabulary, and it is needed only where a feature has no unmarked value to name — `length` declares a default of `normal` and *nothing declares that value*, because a bare vowel already says it, so shortening and clearing are one operation rather than two spellings of it:

```python
f = ipa.load_ipa_features()
f.features["length"].default              # 'normal'
f.declaring_mark("length", "long")[1]     # 'ː'
f.declaring_mark("length", "normal")      # None -- so absence is how it is written
f.features["stress"].default              # None -- nothing to name, hence '∅'
```

Clearing a *segmental* feature is refused rather than guessed at: every phone has some voicing, so `[voiced=∅]` names nothing.

```python
ipa.rule("[vowel] -> [voiced=∅]")
# RuleError: '[voiced=∅]' clears 'voiced', but only prosody can be absent
```

Prosody is written in **feature space** and spelled afterwards, so a rule about one feature leaves the marks that state the others as written:

```python
ipa.rewrite("kˈa᷄", "[vowel] -> [tone=∅]")     # 'kˈa'   -- the stress mark stays
ipa.rewrite("kˈa᷄", "[vowel] -> [stress=∅]")   # 'ka᷄'   -- and the tone stays
```

A tone is a **sequence of levels**, so it is written and cleared as one thing however it was spelled: `᷄` abbreviates `˧˦` and both say `tone="mid>high"` ([tone.md](tone.md)). A rule may name a sequence on either side, and `contour` is the shape derived from one, so a rule about a direction reaches both spellings:

```python
from ipakit.form import declared_prosody
declared_prosody("᷄", f)                                # {'tone': 'mid>high'}
ipa.rewrite("ka˧˦", "[tone=mid>high] -> e")             # 'ke'
ipa.rewrite("ka˧˦", "[vowel] -> [tone=low>high>low]")   # 'ka᷈'
ipa.rewrite("ka˩˥", "[contour=rising] -> e")            # 'ke˩˥'
```

A change the inventory cannot spell does not fire, on the same rule as a segmental one that cannot be realized. `t` plus the rising-contour caron recomposes to the registered `ť`, a different phone, and the result is checked by reading it back:

```python
ipa.rewrite("t", "t -> [contour=rising]")   # 't'  -- declined, not invented
```

### A literal may name prosody too

On the **left** it is an *additional* constraint layered over the identity match, not part of the identity. So `a` goes on matching `ˈa`, while `aː` matches only the long one:

```python
ipa.rewrite("kaː",  "aː -> a")    # 'ka'
ipa.rewrite("kˈat", "ˈa -> e")    # 'ket'
```

On the **right** a literal spells a whole unit, so its silence about prosody has to be given a meaning. It means *carry it across* — `t -> ʔ` must not shorten `tː`, since length and tone are phonemic in plenty of inventories — except for a feature one of the two sides named, which is what makes `aː -> a` shorten rather than do nothing:

```python
ipa.rewrite("kætː", "t -> ʔ / _ #")   # 'kæʔː'  -- length unnamed, so kept
ipa.rewrite("kˈaː", "aː -> a")        # 'kˈa'   -- length named, stress not
ipa.rewrite("kˈaː", "ˈa -> e")        # 'keː'   -- stress named, length not
```

A right-hand side of **more than one unit** has to say *which* of them inherits, and "carry it across" does not: `rewrite("katː", "t -> ts")` used to give `'kats'`, the geminate's length dropped on the floor, while `t -> ʔ` on the same input kept it. The answer is read off where the mark is written — before its unit (`ˈa`) or after it (`aː`). A mark written before the target lands on the first of the units replacing it, one written after lands on the last: **it stays on the side of the span it was written on**, which is what `_anchors` already says of a boundary run, applied to the marks that ride a span rather than divide it.

```python
ipa.rewrite("katː", "t -> ts")   # 'katsː'  -- written after, so it lands last
ipa.rewrite("kˈai", "a -> ai")   # 'kˈaii'  -- written before, so it lands first
```

That is one rule rather than one per feature, and it lands where each feature wants to be without either position being chosen: length at the end of a coda, stress on the nucleus. It rules out putting the mark on *all* of the new units by the same reading — that would state the length twice (`tːsː`) and put two stresses inside one syllable, and a mark is a property of the position, not of whatever fills it. Which side a mark is written on is `IPAFeatures.stress_markers`, the same read `Segment.to_ipa` uses to place the glyph, so where a mark lands and where it is spelled cannot come apart.

`[vowel length=long]` says what `aː` says, so it names length the same way: `ipa.rewrite("kaː", "[vowel length=long] -> a")` is `'ka'`.

A bare suprasegmental is not expressible on either side, and says so rather than parsing and never firing:

```python
ipa.rule("∅ -> ˈ / # _")   # RuleError: 'ˈ' is prosody with no phone under it
```

A prosodic mark is a property of a position, not a position of its own, so there is nothing for an insertion to insert. `[stress=primary]` on the unit is how that is said.

## Stress goes on the nucleus

The house convention marks stress on the **nucleus**, not at the syllable boundary, so a stressed vowel is a single unit and no syllabification is required:

```python
f = ipa.load_ipa_features()
f.normalize_stress_to_nucleus("ˌkænˈtiːn")     # 'kˌæn.tˈiːn'
f.normalize_stress_to_syllable("kˌæn.tˈiːn")   # 'ˌkænˈtiːn'   -- round-trips
```

The `.` left behind is what makes that round trip possible; it records where the syllable boundary was. Do not discard it if you intend to convert back.

## Boundaries

### A syllable dot is transparent

The dot is *optional notation*: `bʌtɚ` and `bʌ.tɚ` are the same word. If `.` blocked a context, flapping would fire on one spelling and not the other — one word, two answers, decided by whether somebody typed the dots. So context scanning **steps over** transparent units the pattern does not match:

```python
spec = "t -> ɾ / [vowel stress=primary] _ [vowel]"
ipa.rewrite("bˈʌtɚ",  spec)   # 'bˈʌɾɚ'
ipa.rewrite("bˈʌ.tɚ", spec)   # 'bˈʌ.ɾɚ'   -- same rule, same site
```

A rule may still **name** the boundary, and then it is not stepped over:

```python
ipa.rewrite("at.a", "t -> ʔ / _ .")   # 'aʔ.a'
ipa.rewrite("ata",  "t -> ʔ / _ .")   # 'ata'   -- no boundary, no match
```

### Tiers nest

The `level` feature declares its values in order — `syllable`, `word`, `phrase`, `utterance` — and is ordinal. So a boundary pattern matches its level **or stronger**: a word boundary *is* a syllable boundary.

```python
asp = "[manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary]"
ipa.rewrite("pˈɪn",   asp)   # 'pʰˈɪn'   -- the form edge is a syllable margin
ipa.rewrite("ə.tˈæk", asp)   # 'ə.tʰˈæk' -- an explicit syllable margin
```

The reverse does not hold: `#` is not matched by a mere syllable break.

Every boundary glyph declares its level, so `#` reaches all of them and no rule needs to name two:

| Glyph | `level` | also declares |
| --- | --- | --- |
| `.` | `syllable` | — |
| `#` | `word` | — |
| `‿` | `word` | `linking=+` — the absence of a *pause*, not of a boundary |
| `\|` | `phrase` | `break=minor` |
| `‖` | `utterance` | `break=major` |

The two break marks sit above `word`, which follows how they are used — `|` is written as a comma-like break between phrases — and not the chart's "minor (foot) group" label, which would put it below `word`. The reasoning is recorded in `ipa.xml` beside the declaration.

So a `#` or `.` context matches a break mark, because a phrase boundary *is* a word boundary and a word boundary is a syllable boundary:

```python
ipa.rewrite("a|b", "a -> o / _ #")     # 'o|b'   -- '|' reaches 'word'
ipa.rewrite("a|b", "a -> o / _ .")     # 'o|b'   -- and 'syllable'
ipa.rewrite("a#b", "a -> o / _ |")     # 'a#b'   -- but not the reverse
ipa.rewrite("lez‿ami", "z -> ∅ / _ #") # 'le‿ami'
```

That last one is why `‿` carries a level. It stands between two words and says they are run together; with no level, `#` did not reach it and only `%` did — and `%` also catches the syllable dot, so a word-final rule written with `%` fired at an interior dot too and the optional dot changed which rules fired.

### The edges of a form are word boundaries

`_ #` fires at the end of a form without a `#` having been typed, and `# _` at the start. The edge asserts the strongest level declared by a separator (`word` in the shipped inventory), and also matches weaker levels.

### A boundary run is one boundary

A form has **one** edge, not an unbounded run of them, and the same holds of written marks: a run of them is one boundary, and the virtual edge past the end of the form is part of any run it touches. So typing a mark the form's own edge already asserts adds no information and must not change the derivation, exactly as an optional dot must not. That is the general form of the claim above:

> **Edge redundancy.** For any rule `r` and form `f` whose ends carry no boundary run, `r(f) == strip(r("#"+f)) == strip(r(f+"#")) == strip(r("#"+f+"#"))`.

```python
ipa.rewrite("kæt",     "∅ -> ə / _ #")   # 'kætə'
ipa.rewrite("#kæt#",   "∅ -> ə / _ #")   # '#kætə#'  -- one gap, and it is the inner one
ipa.rewrite("kæt##",   "∅ -> ə / _ #")   # 'kætə##'  -- a run is still one boundary
ipa.rewrite("#kæt#",   "∅ -> ə / # _")   # '#əkæt#'  -- prothesis lands inside the word
```

Two consequences worth knowing. Which gap of a run an insertion takes is the **inner** one, because there is nothing outside the form to insert into and a schwa written outside a word mark would be a second word. And a context cannot name two boundaries in a row, since there is only one there to name: `_ # #` matches nothing at all.

The run is one boundary wherever it is read, and that includes as a **target**. A rule that restates a boundary writes one mark however many were written for it, and a rule that unwrites one reports a single change over the whole run rather than one change per mark:

```python
ipa.rewrite("a.b",   ". -> #")   # 'a#b'
ipa.rewrite("a..b",  ". -> #")   # 'a#b'   -- one boundary in, one out
ipa.rewrite("a.‿b",  "‿ -> ∅")   # 'a.b'   -- a named mark takes only its own
ipa.rewrite("a.‿b",  ". -> ∅")   # 'ab'    -- the class takes the whole run
```

The target is walked as far as the pattern matches, which is what keeps the last two apart: `.` is "syllable or stronger" and reaches every mark of the run, while `‿` names one mark and leaves the dot where it was written. The site is wider than one unit, and the *rule* still states one pattern and matches one boundary — the width is a fact about how the form was spelled, not about the rule, which is why this is not the multi-unit target [metathesis needs](calculus.md).

The edge is a **word** boundary specifically, not the top of the ladder: `_ |` does not fire at the end of a form, because a phrase break is written or it is not there. `#` is the mark a form edge is an unwritten instance of, and `ipakit.form.edge_level()` reads that off `<separators>`.

## A rule may read a tier, and may not rewrite one

A **tier** is not a rung on the boundary ladder above. `level` is ordinal — a word boundary *is* a syllable boundary — and `tier` is nominal: a syllable, a mora and a morph do not nest, and nothing orders two of them. A span on a tier is an [`Interval`](form.md#an-interval-is-carried-because-no-glyph-delimits-one) carried on a `Form`, and a rule may name one **in its context only**.

The notation is a labeled bracket, which is how prosodic constituency has been written since SPE, with the label inside it:

| term | holds where |
| --- | --- |
| `<mora` | an interval on the `mora` tier **starts** |
| `mora>` | an interval on the `mora` tier **ends** |

The labels come from `<feature name="tier">`, so a language declaring a fourth tier writes it with no code change; the brackets are notation and are spelled in `rules.py`. Angle brackets because the other two pairs mean something else — `[...]` is a feature query over a unit's bundle, `(...)` marks a context item optional — and neither is a claim about structure.

This also leaves the `(?` namespace untouched. The angle alone is not
an atom: it must label a declared tier, so `<syllable` and `syllable>` cannot
be mistaken for an X-SAMPA phone even though X-SAMPA uses angle brackets in
some multi-character modifiers. Curly braces could not do this job: `{` and
`}` are X-SAMPA vowel spellings and, after an atom, already constrain that
atom's features in this language.

### A tier term claims a position, not a unit

Every other context item takes a unit. A tier term takes none: it says something about the **gap** the cursor is at, so `<syllable _` reads "the target begins a syllable" rather than "something precedes the target".

That is the choice that makes the read-only restriction livable, and it is worth stating why. The center of a rule is closed to a tier term, so a *per-unit* tier term could only ever describe a neighbor — and the statements that matter are about the target. "Aspirate a `t` that begins a syllable" would be unwritable. As a position term it is a claim about where the target sits, which is a context, so nothing is lost by the restriction.

Two consequences. A tier term can be conjoined with an ordinary item at the same position, because it consumed nothing: `[vowel] <syllable _` is a vowel before the target *and* an interval starting at the target. And two tier terms may sit together, which is a conjunction over one position and not a nesting — `mora> <syllable _` says a mora closes and a syllable opens where the target sits, in either written order, and says nothing about which contains which.

### It is a different claim from a boundary glyph

`.` and `#` are units the transcription spelled. An interval edge is asserted by a `Form`, and it may sit where no glyph is written — which is the whole point of carrying one. *Petite amie* is the case: the syllable `t‿a` starts inside a word, and no boundary pattern can name that position.

```python
from ipakit.form import Form, Interval

form = Form.parse("pətit‿ami")
syllables = [Interval("syllable", 0, 2), Interval("syllable", 2, 4),
             Interval("syllable", 4, 7), Interval("syllable", 7, 9)]
held = Form.of(form.units, syllables)

rule = ipa.rules.parse("t -> tʰ / <syllable _")
[s.start for s in rule.recognize(held)]        # [2, 4]
ipa.rules.spell(rule.apply(held)[0])           # 'pətʰitʰ‿ami'
```

Unit 4 is the `t` that opens `t‿a`. No spelling of a boundary reaches it — `.`, `#`, `%` and `‿` were all tried — because there is no boundary there: `‿` sits at unit 5, *inside* the syllable.

The converse holds too. A dot asserts a boundary and not a span, so a dotted form carries no interval and no tier term holds of it:

```python
dotted = Form.parse("pə.ti.t‿a.mi")
dotted.intervals                               # ()
rule.recognize(dotted)                         # []
```

Nothing is invented, here or in `form.py`: a form that asserts no interval is not given one, so a rule conditioned on a tier does not fire there — the same answer a margin-conditioned rule gives on an undotted word.

That is why `.` and the interval-edge term are deliberately not unified. A
dot is a stated boundary **unit**, is preserved in the output, and is stepped
over by an ordinary context; `<syllable` is a zero-width predicate over a
stated interval and consumes nothing. One may be present without the other.
Using the same spelling for both would make a rule invent an interval from a
glyph, or make an interval edge pretend that a glyph was written.

### Produce the tier, then read it

American English aspiration provides an example: a voiceless stop is
aspirated at the start of a stressed syllable. Its short statement and its
written-boundary expansion can be put beside one another without changing the
process. The shipped Spanish constraint declaration supplies the neutral
onset-and-vowel syllabification for this small structural demonstration; it
does not turn aspiration into a Spanish rule:

```python
made = ipa.syllabifier("spanish")("ata")
made.spelled()                                      # ('a', 'ta')

short = ipa.rules.parse("t -> tʰ / <syllable _")
short.rewrite(made.form)[0].to_ipa()                # 'atʰa'

long = ipa.rules.parse("t -> tʰ / . _")
long.rewrite(ipa.Form.parse(made.marks()))[0].to_ipa()  # 'a.tʰa'
```

The syllabifier is the producer: it writes `[0, 1)` and `[1, 3)` on the
`syllable` tier. The short rule reads that claim directly, so it needs no dot
and leaves none behind. The long form materializes the same margin as `.`,
then uses the older boundary-unit context. After boundary marks are projected
away the two outputs are the same segmental form. The ordering is semantic,
not presentation: **syllabify, then apply**. Applying the short rule to the
bare string `ata` finds no claimed margin and changes nothing.

### The center is closed, and the refusal is at parse time

A tier term in the target or on the right of the arrow is refused when the rule is read, not answered when it is applied. A refusal at match time would be site-dependent: fine on one form and quietly nothing on the next.

```python
ipa.rules.parse("<mora -> d")
# RuleError: '<mora -> d' names the tier 'mora' in its target, and a rule may READ a tier and may not rewrite one.
```

The restriction is the finding rather than a caution. Kaplan & Kay's restriction is on a rule's **center** and not on its contexts ([calculus.md](calculus.md)), and what leaves the finite-state tradition is rewriting a tier rather than reading one: the multi-tape treatments go beyond regular power, and that power is required precisely for structure-modifying rules ([design/tiers.md](design/tiers.md)). So a tier read in a context costs nothing in formal power, nothing in intermediates and nothing in the derivation trace.

The same line closes a hole on the change side. A **structural** feature — `level`, `tier`, `tie`, `linking`, `break` — is a property of a boundary, a juncture or a tier rather than of a segment, so no unit carries one. A query naming one was already refused; a *change* naming one was not, and `t -> [tier=mora]` parsed, fired at every `t`, wrote into a bundle that does not exist and reported nothing.

```python
ipa.rules.parse("t -> [tier=mora]")
# RuleError: '[tier=mora]' rewrites the structural feature(s) ['tier'].
```

### A tier survives the cascade, because a rewrite rebases what it moved

A rule changes the length of the sequence an interval indexes, so a cascade that kept the spans as written would have every step after the first describing a different span. `RuleSet.derive` takes a `Form` and rebases at each step, so a rule conditioned on `<syllable` finds its sites at step ten for the same reason it finds them at step one:

```python
held = Form.of(Form.parse("pətit‿ami").units, syllables)
ipa.ruleset("p -> ∅ / # _\nt -> tʰ / <syllable _").derive(held).result
# 'ətʰitʰ‿ami'   -- the deletion moved every span left, and the tier rule still fires
```

`Rule.rewrite` is the single-rule form of it: a `Form` in, a `Form` out, spans rebased. `Rule.apply` still answers with a unit sequence, which carries no tier — that is a projection of `rewrite` rather than a gap, and the two are one implementation.

The cascade pin expands a vowel *inside* the first stated syllable before it
reads the next margin:

```python
rules = ipa.ruleset("a -> ai / # _\nt -> tʰ / <syllable _")
rules.derive(made.form).result                      # 'aitʰa'
```

The first interval moves from `[0, 1)` to `[0, 2)` and the second from
`[1, 3)` to `[2, 4)`. Rule two therefore sees the carried start at position
2. It does not resyllabify the rewritten string and it does not retain the
stale position 1; both answers would be a second claim about the structure.

**The policy is one sentence: an interval may lose material to an edit and may never gain material from outside itself.** It is the only reading available where a rule may read a tier and may not write one, because an edit says what happened to the *units* and says nothing about the tier. Three consequences, and each is a case with a test:

- An edit **wholly outside** a span never joins it. So an insertion sitting exactly on an edge lands outside, and the epenthetic unit is on **no** tier rather than on the one it abuts — [form.md](form.md)'s rule that an unspecified tier is not invented, read from this side. Nothing said which mora it belongs to, and intervals do not tile.
- An edit **inside** a span stretches or shrinks it, coextensive or not. `a͜ɪ -> ai` under a mora gives one mora over two units. That is determined arithmetic and not a claim: "a long vowel is two morae" is a well-formedness statement about a language's tier, and deriving it here would be the structure creation a rule may not do.
- An endpoint **strictly inside a rewritten span** has no image, and `rebase` refuses with a `RebaseError` naming the span, the edit and the rule. It is reachable — a boundary target covers the whole run it opens, so `. -> #` on `a..b` is one edit over `[1, 3)` — and no shipped rule reaches it.

The first two policies and their opposites differ in **no spelling anywhere in the shipped corpus** and in the spans of a large minority of it. Only a tier read can tell them apart, which is why each is declared and tested as its own case rather than left to whichever formula fell out.

### What a tier term does not do yet

- **A term names an edge, not membership.** `<mora>` is refused rather than read as one of the two. Membership is true of nearly every position a span covers and so states almost nothing, while both cases the shipped sets reach for are edges.
- **`RuleSet.variants` refuses a form carrying an interval.** A variant is keyed by its spelling, and two branches that spell alike with different spans are two structures and one key; merging them would drop a tier reading in silence. `derive` is the cascade that carries a tier.
- **`Form.without_boundaries()` still refuses one.** Removing a position moves every index after it, and `rebase` lives beside `Edit` in the rule engine, which `form.py` sits below rather than above.
- **Association is not here at all.** What a stranded tone or a compensatory length does after a deletion is language-particular, is not endpoint arithmetic, and is the structure-modifying capability the extra formal power was for ([design/tiers.md](design/tiers.md)).

## `∅` is nothing; a zero is a position with no content

These are two different things, not two spellings of one. `∅` in a rule is **the empty string** — `rules.NULL`, alongside `0` and `Ø`. On the left it means "insert here"; on the right it means "delete this". A **zero** is a declared symbol in `ipa.xml`'s `<zeros>` block: a slot the transcription keeps open with nothing in it. `le∅ʃjɛ̃` has five sounds and six positions.

The glyph is the same character, and that is a spelling accident rather than an identity. `∅` on the left of an arrow stays the empty string — freeing it would silently change every shipped insertion rule, and `∅ -> ə` is epenthesis in two of them. A rule that wants to *emit* a zero says so in brackets, where brackets already mean *described, not spelled*:

```python
ipa.rewrite("lez", "z -> ∅ / _ #", keep_zeros=True)       # 'le'    -- the /z/ is gone
ipa.rewrite("lez", "z -> [zero] / _ #", keep_zeros=True)  # 'le∅'   -- a /z/ was here and could surface
```

`keep_zeros=True` runs through this section and the next, because what they ask about is the form a rule *wrote*. A pronunciation carries no zero, and the rewrite that takes it back out is [below](#the-surface-carries-no-zero).

The second is what a latent consonant needs. French liaison's /z/ is not absent from the word, it is unpronounced in this environment, and a derivation that records where it was can put it back. `[zero]` is read off the data — `zero` is the element class those symbols carry, and the symbol written is the one `<zeros>` declares — so neither the word nor the glyph is spelled in the engine.

A zero is a position, so it can be filled or unwritten, and it has no feature bundle to change:

```python
ipa.rewrite("le∅ʃ", "[zero] -> z")        # 'lezʃ'  -- filled
ipa.rewrite("le∅ʃ", "[zero] -> ∅")        # 'leʃ'   -- unwritten
ipa.rule("[zero] -> [voiced=+]")          # RuleError: a zero is a position with no content, so it has no bundle
ipa.rule("∅ -> [zero] / a _ b")           # RuleError: an insertion had none to lose, so there is nothing here for it to record
```

### A null is not an environment

A zero is opaque by default: it is a position, and positions block.

```python
ipa.rewrite("leʃ",  "e -> a / _ ʃ", keep_zeros=True)      # 'laʃ'
ipa.rewrite("le∅ʃ", "e -> a / _ ʃ", keep_zeros=True)      # 'le∅ʃ'  -- the zero is in the way
```

It cannot be named in an environment. All four null spellings are refused,
because an environment names what stands there and nothing stands at a
deletion site:

```python
ipa.rule("e -> a / _ ∅ ʃ")  # RuleError: 'e -> a / _ ∅ ʃ' names a null at position 11 in its environment. An environment names what stands there, and nothing stands at a deletion site; if zero-width context was meant, spell it with an optional element '(X)'.
```

Parentheses make one unit pattern a variable-width environment item. The
postfix forms are:

| Form | Units consumed |
| --- | --- |
| `(X)` or `(X)?` | zero or one |
| `(X)*` | zero or more |
| `(X)+` | one or more |
| `(X){n}` | exactly `n` |
| `(X){n,}` | at least `n` |
| `(X){,m}` | at most `m` |
| `(X){n,m}` | from `n` through `m`, inclusive |

`(X)?` preserves that spelling when a parsed query is serialized; it has the
same readings as `(X)`. Every open upper bound is capped by the form's length.
The wrapper is general over literals, bundles, brace constraints, and `*`:

```python
ipa.rewrite("cdae", "a -> b / c (d) _ e")  # 'cdbe'
ipa.rewrite("cae",  "a -> b / c (d) _ e")  # 'cbe'
```

Parentheses keep these forms distinct from bare `*`, which still means exactly
one arbitrary segment:

```python
ipa.rewrite("stra", "a -> [stress=primary] / # ([-vowel])* _")  # 'strˈa'
```


### The surface carries no zero

A zero holds a position, and holding the position is what makes a deletion site visible in a trace. A *pronunciation* has no room for a position with nothing in it. So a derivation carries the zero and the surface form does not, and what takes it out is **a rewrite**, applied after every rule of the cascade and after every step is recorded:

```python
ipa.rules.surface().rules[0].source            # '[zero] -> ∅ ; surface'
ipa.rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]")  # 'leami'
```

That it is a rewrite is the design and not the implementation. It is one rule, in this notation, run through this parser, and a caller can write it out for themselves:

```python
ipa.rewrite("le∅ami", "[zero] -> ∅")   # 'leami'
```

Three things follow from that. The projection composes, because a rule set composes. It is expressible, so [calculus.md](calculus.md)'s claim that the operations are closed over the carrier stays true of the map from a derivation to a pronunciation — a surface projection living *beside* the notation would have been an escape hatch from exactly that claim. And it reads off the declaration: `[zero]` is the element class `<zeros>` gives its members, so an inventory that declares no zero gets the empty rule set, which is the identity.

It removes zeros and **nothing else**. A constituent left holding no segment stays written, and `validate_ipa` reports it as the empty constituent it now is:

```python
ipa.rewrite("a.∅.b", "[zero] -> ∅")                       # 'a..b'
[d["code"] for d in ipa.validate_ipa("a..b")]             # ['empty_constituent']
```

Collapsing the boundary run as well would be a second statement, and this is one rule.

**`keep_zeros=True` declines it**, on `rewrite`, `derive`, `variants`, the three `RuleSet` methods and `--keep-zeros` on the command line. A caller reading a derivation wants the zero and a caller asking for a pronunciation does not, so neither may be out of reach:

```python
ipa.rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]", keep_zeros=True)  # 'le∅ami'
ipa.derive("lezami", "z -> [zero] / [vowel] _ [vowel]").steps[-1].rule     # 'surface'
```

The zero is in the trace where the rule wrote it either way — the step above it is the one that put it there, and the `surface` step is what the answer is. Where a derivation writes no zero the step is not recorded at all, so a trace of a rule set that has nothing to do with zeros is the trace it has always been, `--all` included.

## What a rule can do

```
t -> ɾ                       feature-equivalent literal substitution
t -> [manner=tap voiced=+]   a feature change
aː -> a                      a literal naming prosody on the left
[vowel] -> [length=long]     a prosodic change
[vowel] -> [stress=∅]        clearing prosody
∅ -> ə / C _ C               epenthesis  (insertion)
ə -> ∅ / ˈV C _              elision     (deletion)
z -> [zero] / _ #            latency     (a recorded empty position)
n -> [place=α] / _ [place=α] assimilation (an agreement variable)
```

A feature change is realized through `respell` where the result is a **registered** phone, and otherwise by composing the marks that declare it:

```python
f.respell("l", velarized="+")            # 'ɫ'   -- registered wins
f.respell("t", release="aspirated")      # None  -- tʰ is not registered
f.compose_unit("t", release="aspirated") # 'tʰ'  -- composed from declared marks
```

`compose_unit` asks `declaring_mark` which glyph carries a value (most specific first), emits marks in the order `<modes>` declares, and verifies by reading the result back. A change the inventory can spell **neither** way does not fire, rather than inventing a symbol.

**A change that is already true is a no-op**, on both routes. `respell("ɫ", velarized="+")` has always been `'ɫ'`; `compose_unit` used to append the mark anyway, so a rule firing on a unit that already carried the value doubled it — the shipped American English set spelled *hidden* `ˈhɪdⁿn̩̩`, because its nasal-release and syllabic-nasal rules both reach the same nasal, and the German set wrote a devoicing ring on consonants that were voiceless to begin with. The read-back could not see it: a doubled mark reads back carrying the requested value and moving nothing, so the guard measured the bundle while the defect was in the spelling, and `validate_ipa` was reporting `duplicate_diacritic` all along.

```python
f.compose_unit("ɪ̃", nasalized="+")                   # 'ɪ̃'   -- not 'ɪ̃̃'
f.compose_unit("s", voiced="-")                       # 's'   -- /s/ is voiceless already
f.compose_unit("ɪ̃", nasalized="+", release="aspirated")  # 'ɪ̃ʰ'  -- writes only the new half
```

A change naming a *prosodic* feature takes a third route, because neither of those two can carry it — and both are right about what they spell. Prosody lives on the unit, outside the feature bag, so `respell` refuses the key rather than letting it into a bundle it is defined to be outside of, and `compose_unit` verifies *through* the bag and therefore answers `None`:

```python
f.respell("a", length="normal")     # ValueError: respell cannot write ['length']
f.compose_unit("a", length="long")  # None  -- verified through the bag
```

Writing prosody means changing `Segment.prosody`, which is what `ipakit.form.with_prosody` does. A change may name both namespaces at once and is split by declared mode, so each half goes where it can be realized: `[vowel] -> [backness=back length=normal]` takes `kaː` to `kɑ`.

That read-back checks that nothing *else* moved, not only that the request landed. Some marks legitimately say more than one thing: the devoicing ring declares `phonation="devoiced"` and `voiced="-"`, which is one glottal fact written at two granularities, and refusing every surplus would refuse `ɹ̥` and stop approximant devoicing firing. Which dimensions stand in that relation is declared in `ipa.xml`'s `<projections>` block, so a mark whose surplus is a genuine second dimension is refused instead: the linguolabial mark is `place="bilabial"` *and*, independently, `articulator="tongue-tip"`, so `compose_unit("s", place="bilabial")` is `None` rather than `s̼`.

### A change modifies what the rule matched

A bracketed right-hand side modifies the matched unit's named features and preserves the remaining features:

```python
ipa.rewrite("aʃa", "ʃ -> [voiced=+]")   # 'aʒa'  -- grooved, postalveolar, fricative kept
ipa.rewrite("aʈa", "ʈ -> [voiced=+]")   # 'aɖa'  -- and retroflex
```

That reading wants a unit to modify, and an **insertion** matches none. `∅ -> [manner=plosive]` parsed, found its sites and produced no edit — a rule its author believed was firing, doing nothing and saying nothing:

```python
ipa.rule("∅ -> [manner=plosive] / a _ t")
# RuleError: inserts a unit and then describes it with a feature change...
```

A query describes a class of matching units. `[manner=plosive]` includes every registered plosive, and specifying place and voicing can still leave several candidates. Even a complete feature bundle can be shared: a tied diphthong states its first element's features. Insertion therefore requires an explicit unit spelling, including any prosody:

```python
ipa.rewrite("ata", "∅ -> t / a _ t")   # 'atta'
ipa.rewrite("at",  "∅ -> ˈa / # _")    # 'ˈaat'
```

A feature modification requires a matched unit with a feature bundle. Boundaries, zeros, and insertion sites fail that requirement for their respective structural reasons.

Not expressible, deliberately: **metathesis** (reordering) and **iterative within-rule spreading** (harmony as a single rule — an ordered cascade says the same thing). SPE's **agreement variables** used to stand third on that list, and [now they are notation](#a-rule-may-bind-a-value-and-re-use-it); the shipped English set states nasal place assimilation once as a result. Metathesis did **not** come with them, and the two are worth keeping apart because they rhyme: a variable copies a feature *value* between positions the rule matched one at a time, where metathesis reorders the positions themselves, which needs a target spanning more than one unit. A pattern constrains one unit, so `ab -> ba` is refused exactly as it was before. [calculus.md](calculus.md) states those as claims about the algebra's reach, and adds the two that optionality brings: no constraint on the *result* of several optional choices, and no ranking over the set.

## Rules are ordered

Each rule sees the previous rule's output, allowing feeding and bleeding:

```python
fed     = ipa.ruleset("a -> i / _ t ; raising\nt -> ʔ / i _ ; glottalling")
starved = ipa.ruleset("t -> ʔ / i _ ; glottalling\na -> i / _ t ; raising")
fed.apply("at")      # 'iʔ'  -- raising creates the environment glottalling needs
starved.apply("at")  # 'it'  -- it arrives too late
```

Within a single rule, every site is found against a **snapshot** before any is rewritten, so a rule cannot read its own output and a pass terminates by construction:

```python
ipa.rewrite("eaaa", "a -> e / e _")   # 'eeaa', not 'eeee'
```

## A rule may be optional, and then the answer is a set

`~>` in place of the arrow says the rule *may* fire rather than that it does. One form no longer determines one form, so the answer is a **set** of forms and `variants` is where it lives:

```python
ipa.rewrite("kæt", "t ~> ʔ / _ #")            # 'kæt'
ipa.variants("kæt", "t ~> ʔ / _ #").forms     # ('kæt', 'kæʔ')
```

**Optionality is per site.** Each site the rule finds branches on its own, which is what French *devenir* needs — [dəvəniʁ], [dəvniʁ] and [dvəniʁ] are all real and the fourth combination is not:

```python
ipa.ruleset("french-liaison").variants("dəvəniʁ").forms
# ('dəvəniʁ', 'dəvniʁ', 'dvəniʁ')
```

**`rewrite`, `derive` and `rules apply` skip optional rules.** These operations return one form and consistently choose the branch where the optional rule is not taken. Thus `variants(f)[0]` equals `apply(f)`. A full trace records *not taken* separately from *no change*:

```python
ipa.derive("kæt", "t ~> ʔ / _ #").trace(all_steps=True)
# 'kæt\n  t ~> ʔ / _ #  (not taken)\n      -\n  = kæt\n  (no rule fired)'
```

The four spellings are one rule: `~` before any arrow makes it optional, and `~>` is the ASCII arrow with a wavy shaft. `~` spells nothing in the inventory — no phone, no diacritic, no separator, no break mark, and `ipa.xml` does not contain the character at all — so it collides with nothing that can appear in a rule.

Variants are finite, deterministically ordered, and bounded by a reported cap. Truncated results identify their incompleteness. [calculus.md](calculus.md) describes the closure, composition, associativity, and expressivity limits.

## Rule sets

One rule per line. Blank lines are skipped, and a line **beginning** with `#` is a comment — only at line start, since `#` is also the word boundary. A line whose whole left-hand side is `#` is a rule rather than prose: `# -> ∅` unwrites a word mark and `# -> ‿` restates one as the linking mark. A target is everything left of the arrow, so the mark is a target exactly when nothing else stands there, and prose opening with `#` has words before its arrow if it carries one at all.

```python
ipa.ruleset("""
# American English, abbreviated
t -> ɾ / [vowel] _ [vowel -primary -secondary]                 ; flapping
[manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary] ; aspiration
""")
```

Sets can ship as data. `ipakit/data/rules/*.rules` are loaded by name:

```python
from ipakit import rules
rules.available()                       # ['american-english', 'french-liaison', 'german-final-devoicing', 'japanese-moraic', 'spanish-accented-english']
rs = rules.shipped("american-english")
rs.apply("pˈɪn")                        # 'pʰˈɪ̃n'
```

## A worked example: broad to narrow

The shipped set takes a **broad** (phonemic) reading to a **narrow** (phonetic) one — the allophonic detail that is predictable from context:

```
/pˈɪn/          -> [pʰˈɪ̃n]      aspiration, then vowel nasalization
/spˈɪn/         -> [spˈɪ̃n]      no aspiration: the margin is taken by /s/
/bˈʌtɚ/         -> [bˈʌɾɚ]      tapping
/kˈæt/          -> [kʰˈæt̚]      aspiration and an unreleased coda
/klˈin/         -> [kl̥ˈĩn]      approximant devoicing after a voiceless stop
/fˈʊl/          -> [fˈʊɫ]       dark l
/ˈbʌ.tn/        -> [ˈbʌ.tⁿn̩]    nasal release, syllabic nasal
/pə.tˈe͜ɪ.to͜ʊ/   -> [pə.tʰˈe͜ɪ.ɾo͜ʊ] aspiration and tapping in one word
```

Two details affect these derivations.

**Aspiration requires a syllable margin.** In `spin`, /s/ occupies the margin and /p/ follows it, so the aspiration rule leaves /p/ unchanged. This environment uses the classical SPE treatment of contexts. Feature-value negation such as `[-voiced]` is supported; negation of context positions is outside the notation.

**Tie your diphthongs.** Whether a diphthong is tied changes what a rule sees, because untied `eɪ` is two units and a stress mark lands on the first of them. Vowel nasalization is the clear case: `ˈkaɪn` nasalizes its second element to `ˈkaɪ̃n`, while the tied `ˈka͜ɪn` is one unit the composed mark does not read back on, and is left alone.

```
/ˈkaɪn/    -> [ˈkaɪ̃n]     untied: the rule reaches the second unit
/ˈka͜ɪn/    -> [ˈka͜ɪn]     tied: one unit, and the mark does not compose
```

The tapping rule places no stress condition on its left context, so `/pə.tˈeɪ.toʊ/` and `/pə.tˈe͜ɪ.to͜ʊ/` both flap.

Tie the intended diphthongs explicitly. `ipakit.add_ties()` operates within a multi-phone segment and ties every adjacent pair: `add_ties("kæt")` produces `k͡æ͡t`. Applying it to the word above produces `p͡ə.tʰˈe͜ɪ.t͡o͜ʊ`, where tapping no longer fires. It is unsuitable for selecting diphthongs in a word.

## Underspecification

A word written without interior dots leaves its interior margins **unspecified**. Margin-conditioned rules require a stated margin:

```python
ipa.rewrite("ə.tˈæk", asp)   # 'ə.tʰˈæk'  -- margin stated
ipa.rewrite("ətˈæk",  asp)   # 'ətˈæk'    -- margin unspecified, so no claim
```

An undotted interior leaves the syllable count open.

Given a language's declarations, the [syllabifier mechanism](syllabification.md) derives primary intervals and reports conflicts with written marks. Subsequent rules can read those intervals.

## From a shell

`ipakit rules` is the notation above with no Python around it. Rules come from exactly one of `-r NOTATION` (repeatable, and repeats are an *ordered* cascade), `-s NAME` (a shipped set) or `--file FILE`. Forms are positional, or one per line on stdin when none are given.

**Quote the rule.** It contains `#`, `|` and `;`, all of which a shell reads. Single quotes throughout, and a `#` inside them is the word boundary, not a comment.

```console
$ ipakit rules list
american-english
french-liaison
german-final-devoicing
japanese-moraic
spanish-accented-english
$ ipakit rules apply -s american-english pˈɪn
pʰˈɪ̃n
$ ipakit rules apply -r 't -> ʔ / _ #' kæt
kæʔ
```

`trace` shows the rules that fired and their intermediate results. `--all` also lists unchanged steps, helping diagnose an expected rule that did not fire. The `(no change)` marker follows the rule name, keeping names aligned and leaving the default listing unchanged.

```console
$ ipakit rules trace -s american-english pə.tˈe͜ɪ.to͜ʊ
pə.tˈe͜ɪ.to͜ʊ
  tapping
      tapping: t -> ɾ @6
  = pə.tˈe͜ɪ.ɾo͜ʊ
  aspiration
      aspiration: t -> tʰ @3
  = pə.tʰˈe͜ɪ.ɾo͜ʊ
```

`variants` enumerates the results of optional rules. Its first variant matches `apply`, and the count line reports whether enumeration is complete or capped.

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

`--keep-zeros` is the surface rewrite declined, on the three commands that print a derived form. What it prints is the derivation's own answer, zero and all:

```console
$ ipakit rules apply -r 'z -> [zero] / [vowel] _ [vowel]' lezami
leami
$ ipakit rules apply --keep-zeros -r 'z -> [zero] / [vowel] _ [vowel]' lezami
le∅ami
```

`recognize` is the left of the arrow alone — where the environment holds, with nothing rewritten. Each line is the rule, the index of the target, the target, and the neighbors that licensed it; `#` there is the form's own edge, matched without one having been typed.

```console
$ ipakit rules recognize -r '[manner=plosive] -> [voiced=+] / [vowel] _ [vowel] ; voicing' atapa
atapa: 2 sites
  voicing  @1  t  a _ a
  voicing  @3  p  a _ a
```

With a rule *set*, every rule is asked against the form **as given**. No rewriting happens, so the ordering effects `apply` and `trace` show are absent: a rule that fires only on an earlier rule's output recognizes nothing here. A form with no site is reported as such and is not an error.

The indices count rule units, which keep the boundaries `convert tokenize` drops:

```console
$ ipakit rules units bˈʌ.tɚ
b ˈʌ . t ɚ
```

Forms on stdin make it a filter:

```console
$ printf 'pˈɪn\nbˈʌtɚ\nkˈæt\n' | ipakit rules apply -s american-english
pʰˈɪ̃n
bˈʌɾɚ
kʰˈæt̚
```

`-j` gives every subcommand a machine-readable form: one row per input form for `apply`, `trace`, `recognize` and `units`, so the shape does not change with the number of forms. A malformed rule is reported as `Error: ...` on stderr with exit status 1, never a traceback.

## Known limits

The following constraints apply to the native rule engine:

- **Boundary runs are atomic.** Repeated marks count as one boundary, so `##kæt` and `kæt..dɒɡ` derive as `#kæt` and `kæt.dɒɡ` do. Both parse; `validate_ipa` reports `empty_constituent` warnings without rejecting them. Balanced-bracket validation is outside this separator model. `Form.tree()` preserves delimiter provenance through `Node.opened_by` and `closed_by` (`None` for a form edge), with `Node.asserted` recording that both ends were written. See [form.md](form.md) for the model and its alternatives.
- **Prosody requires a unit.** Bare marks in targets, replacements, or contexts are refused, including `∅ -> ˈ` and `ˈ -> ∅`. Use `[stress=primary]` or `[stress=∅]` to modify the unit's prosody.
- **Prosodic composition requires a faithful read-back.** Adding a rising-contour caron to `t` produces the registered phone `ť`, so `t -> [contour=rising]` leaves `t` unchanged. The check uses the inventory's declarations; `tests/test_rules.py` sweeps phone/prosody pairs and identifies those that decline.
- **Phrase boundaries use literal marks.** `#` and `.` name levels; `|` and `‖` match their literal marks. A bracketed `[level=phrase]` cannot match a boundary because feature queries operate on segment bundles, which boundaries lack.
- **Variable width is restricted to contexts.** Variable-width targets and nested variable-width elements are refused. A change also cannot use a variable bound only inside a variable-width element; an absent element cannot supply a rewrite value. Parentheses after the name separator `;` remain part of the rule name.
- **Agreement variables range over feature values.** `[place=α]` copies a place value; whole-segment copying is unsupported, so the shipped French set has one liaison rule per latent consonant. Variables must range over one feature, be bound during recognition, and occur more than once. `-α` requires a binary feature. Violations are refused at parse time.
- **Surface projection and caps apply per call.** Splitting a cascade into two calls applies the surface rewrite twice. Use `keep_zeros=True` on the inner call when the second part needs to read zeros in the intermediate derivation.
- **Insertion requires a spelled unit.** Use `∅ -> t` or `∅ -> ˈa`. A feature change requires a matched unit, so `∅ -> [manner=plosive]` is refused at parse time. An otherwise valid feature change may still decline at a particular site if its result cannot be spelled faithfully.
- **Zeros record emptied positions.** `∅ -> [zero]` is refused because an insertion has no preceding content to record. A zero also lacks a feature bundle, so `[zero] -> [voiced=+]` is refused. Supported operations fill the position (`[zero] -> z`) or remove it (`[zero] -> ∅`).
- **Derivation traces start with the parsed form.** `Derivation.start` records what the engine read. Unregistered input is dropped with a warning, and the trace begins with the form the first rule actually received.
- **Rebuilding preserves boundary spelling and declared features.** `Form.rebuild` provides an inverse up to spelling, without reproducing the original `Boundary` objects. It uses `Boundary.features`; a level alone would lose distinctions such as `‿`'s `linking=+`.
- **An undeclared boundary level defaults to `word`.** Every shipped glyph declares its level. The fallback applies to hand-made boundaries and additions whose level is omitted.
- **Whitespace inherits the form-edge level.** Because whitespace is undeclared in `ipa.xml`, `units()` assigns it `form.edge_level()` (`word` today). A space and the form's edge therefore assert the same level to a context.
- **CLI parsing is per invocation.** Streaming forms through one invocation loads the inventory and parses the rules once. The CLI operates as a filter; batch orchestration is outside its scope.
