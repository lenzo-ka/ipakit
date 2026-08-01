# Forms: the transcription before anything is projected away

`ipakit.segments` answers *what sounds are in this?* — and to answer it, drops what is not a sound: the word mark, the syllable break, the space.

```python
import ipakit as ipa

ipa.to_ipa(ipa.segments("#kæt.dɒɡ#"))   # 'kætdɒɡ'
```

That is the right answer to that question. The problem is that it is a **projection** and does not say so, and a caller who needed the whole transcription has already lost it by the time they notice. `ipakit.form.Form` is the unprojected reading: every position the transcription had, sounds and boundaries alike, spelling back out byte-identical for well-formed input. Everything narrower is reachable from it *by name*, and each name says what it drops.

The engine that consumes this is [rules.md](rules.md); this document is the representation underneath it, and the commitments that representation makes.

## The three projections

```python
from ipakit.form import Form

form = Form.parse("#kæt.dɒɡ#")
form.to_ipa()                          # '#kæt.dɒɡ#'
form.to_ipa() == "#kæt.dɒɡ#"           # True
[s.to_ipa() for s in form.segments]    # ['k', 'æ', 't', 'd', 'ɒ', 'ɡ']
form.phones                            # ('k', 'æ', 't', 'd', 'ɒ', 'ɡ')
```

| projection | drops | keeps |
| --- | --- | --- |
| `to_ipa()` | nothing — round-trips | everything |
| `segments` | boundaries | prosody, which rides on each `Segment` |
| `phones` | boundaries **and** attributes | the phone's identity name |

`phones` is identity, and prosody is not part of an identity. `a`, `ˈa` and `aː` are one phone, for the reason [ties.md](ties.md) gives: the six `mode="prosodic"` features live on the unit, outside the feature bag.

```python
[Form.parse(x).phones for x in ("a", "ˈa", "aː")]   # [('a',), ('a',), ('a',)]
```

That is the same fact the rule engine relies on when the pattern `a` matches a stressed `ˈa`. It is stated once, in the data, and read here rather than restated.

Carry the widest projection you can and collapse at the point of use.

## `Boundary` and `Attribute` are the two non-sounds, and they attach differently

A **`Boundary`** is a relation *between* segments, linearized into the string as a character. An **`Attribute`** is a value riding *on* one segment. That is the whole difference, and it is why there are two classes rather than one bag of leftovers.

```python
Form.parse("#kæt.dɒɡ#").boundaries[1]
# Boundary(text='.', level='syllable', at=3, features={'level': 'syllable', 'href': 'Syllable', 'class': 'separator'})

Form.parse("ˈaːkæt").attributes
# (Attribute(feature='stress', value='primary', at=0, glyph='ˈ'), Attribute(feature='length', value='long', at=0, glyph='ː'))
```

Both record **where they sat** — `Boundary.at` counts the segments before it, `Attribute.at` indexes the segment it rides on — so both survive the projection that dropped them, and a collapsed reading can be put back together:

```python
src = "lez‿a.mi"
form = Form.parse(src)
back = Form.rebuild(form.segments, form.boundaries)
back.to_ipa() == src                    # True
back.boundaries == form.boundaries      # True
```

`rebuild` is an inverse, not a re-spelling. It puts the boundary back from `Boundary.features` — everything the mark declared — rather than from `Boundary.level`, because a level cannot say that `‿` *links* or that `|` is a *minor* break. Rebuilding from the level alone spelled each mark correctly and described it wrongly: the same spelling, a different unit, which is exactly the kind of error a `to_ipa()` round-trip check cannot see.

Recoverability is not tidiness. The syllable break is what `normalize_stress_to_syllable` reads to turn nucleus-marked stress back into syllable-marked stress, so a form that has been collapsed and cannot be rebuilt has lost its stress positions.

Each attribute names the mark that declared it (`glyph`), resolved per glyph rather than off the merged bundle, so `ˈaː` carries a stress from `ˈ` and a length from `ː` — not both from both. That resolution happens when the unit is built, against the inventory the caller named, so one `Form` cannot give two answers for one glyph.

## An unspecified tier is not invented

The syllable dot is optional notation. A word written without one has **unspecified** syllabification — not one syllable. Inventing a node there would state a claim the transcription never made, which is the collapse error inverted: instead of silently dropping structure, silently adding it.

Specification is **per node**, not per form. One word may state its syllables while its neighbor does not:

```python
def spell_tree(node, depth=0):
    print("  " * depth + repr(node))
    for child in node:
        spell_tree(child, depth + 1)

spell_tree(Form.parse("kæt dɒ.ɡi").tree())
# Node(form, 2 children, 'kætdɒɡi')
#   Node(word, 3 children, 'kæt')
#     Node(segment, 'k')
#     Node(segment, 'æ')
#     Node(segment, 't')
#   Node(word, 2 children, 'dɒɡi')
#     Node(syllable, 2 children, 'dɒ')
#       Node(segment, 'd')
#       Node(segment, 'ɒ')
#     Node(syllable, 2 children, 'ɡi')
#       Node(segment, 'ɡ')
#       Node(segment, 'i')
```

`kæt` has no syllable tier at all; `dɒ.ɡi` has two syllables. The rule engine reads the same policy from the other end — a margin-conditioned rule does not fire where the margin was never stated:

```python
asp = "[manner=plosive voiced=-] -> [release=aspirated] / . _ [vowel stress=primary]"
ipa.rewrite("ə.tˈæk", asp)   # 'ə.tʰˈæk'   margin stated
ipa.rewrite("ətˈæk",  asp)   # 'ətˈæk'     margin unspecified, so no claim
```

The direction here is **unspecified**, and later **underspecified** — a tier that is absent because nothing said anything about it, distinct from a tier that is present and empty. That distinction is what makes it safe to add structure later without re-reading old transcriptions as having asserted something they did not.

## The tier ladder, and where a form's edges sit

`ipa.xml` declares `<feature name="level">` with its values **in order**, and the feature is ordinal. The tree's nesting is that declaration, not a constant in `form.py`, so declaring a further value extends the tree with no code change.

```python
from ipakit.form import tiers, edge_tier

f = ipa.load_ipa_features()
f.features["level"].values       # ['syllable', 'word', 'phrase', 'utterance']
f.features["level"].is_ordinal   # True
tiers()                          # ('utterance', 'phrase', 'word', 'syllable')
```

Every boundary glyph declares which tier it terminates:

| glyph | `level` | also declares |
| --- | --- | --- |
| `.` | `syllable` | — |
| `#` | `word` | — |
| `‿` | `word` | `linking=+` — the absence of a *pause*, not of a boundary |
| `\|` | `phrase` | `break=minor` |
| `‖` | `utterance` | `break=major` |

Because the ladder is ordinal, a boundary pattern matches its level **or stronger**: a phrase boundary *is* a word boundary, and a word boundary *is* a syllable boundary. The reverse does not hold. All four of the shipped separating marks are preserved by `units()` and spell back out:

```python
from ipakit.form import units

[(u.text, u.level) for u in units("a|b")]
# [('a', None), ('|', 'phrase'), ('b', None)]
[(u.text, u.level) for u in units("lez‿ami")]
# [('l', None), ('e', None), ('z', None), ('‿', 'word'), ('a', None), ('m', None), ('i', None)]
```

### `edge_tier()`: a form edge is an unwritten `#`, not an unwritten `‖`

Running off the end of a form is a **word** edge. It is not "the outermost declared tier" — `|` and `‖` declare levels above `word`, and a form with no break mark in it is not thereby one phrase, for the same reason an undotted word has no syllable tier.

```python
edge_tier()   # 'word'
```

That is read off `<separators>` — the strongest level a *separator* spells — rather than stated in Python, so declaring a stronger separator moves the edge with it. The distinction is load-bearing in both directions:

```python
ipa.rewrite("kæt", "t -> ʔ / _ #")   # 'kæʔ'   the edge is a word boundary
ipa.rewrite("kæt", "t -> ʔ / _ .")   # 'kæʔ'   and therefore a syllable one
ipa.rewrite("kæt", "t -> ʔ / _ |")   # 'kæt'   a phrase break is written, or it is not there
ipa.rewrite("kæt", "t -> ʔ / _ ‖")   # 'kæt'
```

Before `edge_tier()` existed, `tree()` took depth 0 to be the outermost tier, which was the same thing only while `word` happened to be outermost. Declaring `phrase` and `utterance` above it would have stopped a bare `kæt` from having a word at all. Whitespace, which `ipa.xml` does not declare, takes its level from the same read rather than a literal `"word"`, so a space and the form's own end cannot come to disagree about what an edge asserts.

## `Node.opened_by`, `closed_by`, `asserted`

A node records **which delimiter supplied each end of its span**, with `None` meaning the form's own edge — a boundary that was inferred rather than written.

```python
def brackets(text):
    return [(n.to_ipa(),
             n.opened_by.text if n.opened_by else None,
             n.closed_by.text if n.closed_by else None,
             n.asserted)
            for n in Form.parse(text).tree().at("word")]

brackets("kæt")       # [('kæt', None, None, False)]
brackets("#kæt#")     # [('kæt', '#', '#', True)]
brackets("kæt dɒɡ")   # [('kæt', None, ' ', False), ('dɒɡ', ' ', None, False)]
```

This is **provenance, not shape**. `#kæt#` and `kæt` are the same word and give the same tree; what distinguishes them is only whether the delimiters were typed. A node's brackets *are* its span endpoints, so recording them adds no structure. A leaf and the root are never `asserted` — a segment has no delimiters, and the form is what the edges are the edges *of*.

None of these delimiters enters `Form.units`. That sequence stays the faithful read of what was **spelled**, and it is what `rules.Site` indices point into.

## Why boundaries are atomic separators and not a Dyck bracketing

This question recurs, so here is the answer with the measurements attached. A `Form` reads `#`, `.`, `|`, `‖` and `‿` as **atomic separators**: one character standing between two positions. It does not read them as paired brackets forming a Dyck word, and that is a decision rather than an oversight.

**1. Balance is vacuous under a parser-generated bracketing, so it buys no checks.** The bracketing is not in the input; it is derived from the separators by `tree()`. An edge and a separator are one character doing two jobs, so there is nothing an author can write that comes out unbalanced. Every one of these is the same tree:

```python
{repr(Form.parse(s).tree()) for s in ("kæt", "#kæt", "kæt#", "#kæt#", "##kæt")}
# {"Node(form, 1 children, 'kæt')"}
```

A balance check over that set has nothing to reject. And the one genuine ill-formedness in the neighborhood — a same-level run delimiting no segment — is already caught, by a validator over the atomic reading rather than by a grammar:

```python
[d["code"] for d in ipa.validate_ipa("kæt..dɒɡ")]   # ['empty_constituent']
[d["code"] for d in ipa.validate_ipa("##kæt")]      # ['empty_constituent']
[d["code"] for d in ipa.validate_ipa("#.#")]        # ['no_segments']
[d["code"] for d in ipa.validate_ipa("kæt.dɒɡ")]    # []
```

So the check a bracketing is usually reached for is available without one, and adding one would not add a second.

**2. A Dyck word is strictly nested by definition, so it would entrench strict layering rather than relax it.** The complaint that motivates "make the brackets explicit" is usually that the tiers are too rigid. A bracketing is the wrong instrument for that: nesting is what a Dyck word *is*. Adopting it would write the strict layer hypothesis into the representation, and the phenomena that need relaxing are exactly the ones a nested reading cannot state.

**3. The honest model for tier independence is autosegmental, not syntactic** — multi-tier intervals over a shared segmental spine, where a syllable interval and a word interval may overlap without either containing the other. That is the same direction [gestural-model.md](gestural-model.md) is heading in for the segment: parallel tiers over a shared timeline, matched by what they are about rather than by containment. If tier independence is ever wanted, that is the change to make, and it is not a bracketing.

### Enchaînement is the concrete case

French *petite amie* → `pə.ti.ta.mi`. This is pure **resyllabification**: the segmental string is byte-identical and only the `.` positions move.

```python
"".join(Form.parse("pə.tit‿a.mi").phones)     # 'pətitami'
"".join(Form.parse("pə.ti.t‿a.mi").phones)    # 'pətitami'
```

The syllable `ta` needs a `t` that belongs to *petite* and an `a` that belongs to *amie* — one syllable spanning a word boundary. `tree()` cannot represent it, and the reason is structural rather than incidental: it splits on `word` first, because `word` is above `syllable` in the ordinal ladder, so anything crossing a word boundary is cut in two before the syllable tier is reached.

```python
[n.to_ipa() for n in Form.parse("pə.ti.t‿a.mi").tree().at("syllable")]
# ['pə', 'ti', 't', 'a', 'mi']
```

Five syllables, not four: the `ta` was split into `t` and `a` by the word division. Writing the resyllabified form without the word boundary gets the syllables right and loses the words instead:

```python
[n.to_ipa() for n in Form.parse("pə.ti.ta.mi").tree().at("syllable")]
# ['pə', 'ti', 'ta', 'mi']
[n.to_ipa() for n in Form.parse("pə.ti.ta.mi").tree().at("word")]
# ['pətitami']
```

Neither spelling states both facts, and no bracketing would let it, because the two constituents genuinely overlap. The string is not the limit here — `Form.units` reads `pə.ti.t‿a.mi` faithfully, boundaries and all, and `rules.py` operates on that flat sequence without ever building a tree. `tree()` is the projection that cannot say it, which is the same lesson as the top of this document: the tree is a narrower read, and it should say what it drops.

## Known limits

- **Boundaries are atomic separators, not a balanced bracketing** (above). `Form.parse` accepts `##kæt` and `kæt..dɒɡ` without complaint; `validate_ipa` warns on both, and neither layer rejects them.
- **`tree()` cannot represent a constituent that crosses a stronger boundary** (enchaînement, above). `Form.units` can; the tree is the read that cannot.
- **`Form.rebuild` is an inverse up to spelling.** `Boundary` equality is not object equality with the original, though it does reproduce each boundary *unit* — text and declared features — from `Boundary.features`.
- **`Boundary.level` falls back to `word` where a mark declares none.** Every shipped glyph declares one, so only a hand-made `Boundary`, or a mark added without a level, reaches it.
- **Whitespace is not declared in `ipa.xml`**, so `units()` assigns it `edge_tier()` rather than a declared literal. That is a code-side convention, and it is stated here so it stays known.
- **A stress mark standing before a separator is read two ways.** `segments("kæt.ˈ.dɒɡ")` binds the mark to `d`; `Form.parse` flushes at the separator, is handed a bare mark, calls it unbound and drops it — so that form does not spell itself back out, which is the one thing `Form` advertises. Pinned by a test that fails when it is fixed.
