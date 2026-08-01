# Supplement-level bridges: assessment

Should a supplemental inventory be allowed to declare `<bridges>` — and, secondarily, `<projections>` — where today it may declare only symbols?

**Verdict: DON'T ADMIT, and the reason is measured rather than categorical.** A bridge really does put no key in any symbol's feature bundle; that half of the case for it holds exactly. But the metric does not read bundles, it reads *comparison bundles*, and a bridge puts a derived key in every one of those — which makes it a term in the denominator of every distance the inventory can compute, including distances between phones the supplement never named. A supplement that adds three phones moves no existing distance. A supplement that adds one three-line bridge moves up to 98% of them.

What the request actually wants — perturb the feature space, keep the shipped data still, be told what moved — is worth having and is mostly already possible. What is missing is not a grammar change. It is a **fingerprint**, so that a perturbed inventory reading the shipped matrix is refused instead of silently answering, and a **report**, so that "what did my three lines do" has an answer. Both are needed whether or not bridges are ever admitted anywhere, and both are cheap.

The assessment is read-only. Nothing in this lane changed code, data, or tests.

## Summary of findings

| Question | Finding |
|---|---|
| Does a bridge change any symbol's feature bundle? | **No. 0 of 8,616 corpus units, in every experiment.** The premise of the case for admitting it is true. |
| Does it change distances anyway? | **Yes, by adding a term to the denominator of every comparison.** 694 to 9,413 of 9,591 pairs, depending on the bridge. |
| Does it reach pairs the supplement never named? | **Yes. 9,005 of 9,591 pairs** under the `glottality` experiment involve two phones neither of which spells the bridge. |
| Can a bridge *remove* a dimension? | **Yes.** `posteriority` made `retroflex` a carried feature, dropping it from the per-key comparison outright. |
| Are bridges order-independent? | **Yes. 0 pairs differ** between two orderings of the same two bridges. That half of the case holds too. |
| Are supplements confined to the caller's instance? | **Yes**, confirmed independently: module-level `distance` and the shipped matrix do not move. |
| Does `phones` in `confusion.json` half-detect a bridged inventory? | **No.** Under all three experiments the phone list is byte-identical. It detects membership drift only. |
| Can a mismatch be detected cheaply? | **Yes. 1.9 ms**, from a digest of what the metric reads off the file's own phones — membership-independent, and it separates all three experiments. |
| Do projections earn admission? | **No**, and for a reason the shipped comment does not give: a projection moves 37 of 139 phones' glottal aperture in the tract figures. |

## The experiments

Three bridges, each spliced into a copy of `ipa.xml` and loaded with `IPAFeatures(xml_path=...)`. Nothing else differs between the two inventories being compared.

**`posteriority`** is the brief's own motivating hypothesis, "what if retroflex and postalveolar are one dimension", written as data:

```xml
<bridge name="posteriority">
  <spelling feature="retroflex" value="+"/>
  <spelling feature="place" value="postalveolar"/>
</bridge>
```

**`glottality`** is the bridge [distance.md](../distance.md) §5 says is wanted and cannot be expressed — `place=glottal` unified with `release=glottal`. It is included because it is the one a reader of the documentation would try first, and because it is the case the documentation already predicts will go wrong for phonetic reasons. It goes wrong for a second reason as well.

**`ghost`** names two `(feature, value)` pairs no registered symbol declares — `airstream="pulmonic"` and `rounded="-"`. It is the degenerate case: a bridge that unifies nothing anybody wrote down. The default fill puts both keys in nearly every bundle regardless, which is exactly why it is not inert.

## 1. The metric argument reaches bridges

The loader's stated reason for the refusal is that "a bundle key is a term in the metric". Read literally, against `IPAFeatures.get_features`, that does not describe a bridge: the bridge declarations are loaded into `self.bridges`, and nothing in the read path consults them. Measured over the canonical corpus, that is exactly right.

Read against `ipakit/metric.py`, it describes a bridge precisely. `_metric_bundle` ends with

```python
for bridge, spellings in features.bridges.items():
    feats[bridge] = "+" if any(bundle.get(f) == v for f, v in spellings) else "-"
```

so every bridge contributes a key to every comparison bundle, for every phone, whether or not that phone has anything to do with the dimension. `bundle_distance` then takes `keys = sorted(set(f1) | set(f2))` and divides by `len(keys)`. One more bridge is one more key in every union and one more unit in every denominator. A pair that reads the new bridge the same way on both sides contributes nothing to the numerator and one to the denominator, so its distance *shrinks* — which is why the effect is not confined to the phones the bridge is about.

The measurement, over the canonical corpus (`python scripts/sweep.py corpus`: 8,616 units = 139 bare phones + 8,477 marked) and the full pairwise matrix over the 139 registered phones:

| experiment | bundles moved / 8,616 | pairs moved / 9,591 | of those, pairs where neither phone spells the bridge | sweep `d_from_base` moved / 8,616 | nearest-neighbor flips / 139 | keys dropped from comparison |
|---|---|---|---|---|---|---|
| `posteriority` | 0 | 694 | 0 | 12 | 14 | `retroflex` |
| `glottality` | 0 | 9,413 | 9,005 | 4,982 | 7 | — |
| `ghost` | 0 | 9,413 | 0 | 4,982 | 1 | — |

The one line that settles it:

```
glottality:  d(a, b)  0.260000 -> 0.248696
ghost:       d(a, b)  0.260000 -> 0.248696
```

Neither /a/ nor /b/ is glottal, and neither is postalveolar, retroflex, or anything else the experiments are about. They move because the denominator moved.

`posteriority` looks tame at 694 pairs, and the reason it does is worse than the number. Adding it made `retroflex` a **carried** feature: every informative value of `retroflex` is now claimed by a bridge, so `excluded_keys` drops it from the per-key comparison. One key left as another arrived, the denominator held, and only the pairs whose *value* changed moved. So the least disruptive of the three experiments is the one that silently deleted an existing dimension from the metric. "A bridge adds no dimension" is true; it can subtract one.

Where the effect does land, it lands hard, and it lands on exactly the phones a phonologist would be looking at:

```
posteriority, nearest-neighbor flips
  s: ʃ -> ɕ      ʂ: s -> ʃ      ʈ: t -> ɧ      t͡s: t͡ʃ -> t͡ɕ
  z: ʒ -> ʑ      ʃ: ɕ -> ʂ      ʐ: ɽ -> ʒ      d͡z: d͡ʒ -> d͡ʑ
```

That is a real, legible, interesting result — it is the answer to the hypothesis. The problem is not that the experiment is uninformative. The problem is that it arrived together with 680 other moved pairs and a dimension quietly leaving the model, and nothing said so.

The 178 pairs that survive a uniform bridge unchanged are the 138 involving `␣`, which takes no bridge features because silence is not a speech sound, plus 40 whose distance is set by the alignment structure rather than by the per-key sum — a gap against a diphthong or an affricate.

**Conclusion for question 1: the metric argument was not applied to bridges by category. It applies to them, by a route the loader's own sentence does not name.** The sentence should be corrected either way; see §8.

## 2. Blast radius

Supplements are constructor-time only, into a caller-owned instance. Confirmed independently of the claim in [supplements.md](../supplements.md): `ipakit/__init__.py` builds every module-level call on `_get_ipa()`, which is `IPAFeatures()` with no supplements, and `DistanceModel.global_` reads `data/confusion.json`, which `scripts/confusion.py derive` builds from a bare `IPAFeatures()` with a comment saying why.

```
module-level distance(s, ʃ), before and after building a supplemented instance: 0.009000 / 0.009000
ipakit.load_ipa_features() phones: 139
```

So nothing shipped moves, and nothing in another caller's process moves. That much of the brief's framing holds.

What a bridge changes that a symbol does not is what happens *inside* the caller's own instance, and the difference is categorical rather than one of degree:

| supplement contents | existing pairwise distances moved / 9,591 | new pairs added |
|---|---|---|
| `docs/examples/aspirated-stops.xml` (3 phones) | 0 | 420 |
| one `<bridge>` (`glottality`) | 9,413 | 0 |

A supplement of symbols is *purely additive*: it adds rows and columns and leaves every cell that was already there alone. That is what makes the property [supplements.md](../supplements.md) states — "adding a supplement can only turn a `None` into an answer" — true, and it is what makes the merge worth calling additive and order-independent.

A supplement carrying a bridge adds no rows and rewrites nearly every cell. Admitting it into `<supplement>` would make that document's own sentence false, and would leave the word "supplement" describing two mechanisms with opposite properties. The instance being the caller's own is not a defense here; the caller is precisely the person surprised. A student who wrote three lines about retroflexion, and finds that /a/–/b/ moved, has been told nothing by the library about why.

That is the answer to "is it acceptable, or does it need a guard": it needs a guard, and the guard is a different name. A perturbation of the feature space is not a supplement to it.

## 3. The fingerprint

This is the part that has to land regardless of the verdict, because the failure it prevents exists today.

`confusion.json` records `version`, `reference`, `space`, `phones`, `triangle`. Nothing in that says which feature space the triangle was derived from, and `from_matrix_file` checks nothing against the inventory in hand. So:

```
bridged inventory reading the shipped matrix: warnings=0
  confusability(s, ʃ):  shipped matrix 0.9982   own derived matrix 0.9447
  confusability(ʂ, s):  shipped matrix 0.9561   own derived matrix 0.9590
```

Two plausible numbers, no diagnostic, and no way for the caller to tell which one they got. This is the defect shape [reviewing.md](../reviewing.md) exists to catch, and `DistanceModel.derive` plus `.save()` already make the *right* answer available — what is missing is the refusal of the wrong one.

**Does `phones` already half-do the job?** No. Under all three experiments the phone list is byte-identical: same 139 entries, same order. `phones` detects membership drift, which is the supplement-of-symbols case; it is blind to the bridge case by construction, because a bridge changes no membership.

**What has to be recorded.** A digest of what the metric actually reads off each phone — the `_metric_bundle` output, features and place components — taken over **the phone list the file itself carries**. Deriving it that way rather than listing "the declarations the metric depends on" keeps it in the repository's idiom: it calls the metric, so it cannot go stale against a change to `metric.py`, and nobody has to maintain a list of what counts.

```
digest over the file's own 139 phones:  9c3ec3e8d710601c   (1.9 ms)
  same digest from a supplemented inventory (142 phones):  9c3ec3e8d710601c   same=True
  posteriority   2fc40bb2870ad646   differs
  glottality     bf61a07ae980a5e1   differs
  ghost          197e8523e8916e6c   differs
  DistanceModel.derive cost, for comparison:  0.99 s
```

Keying it to the file's own phone list is what makes it membership-independent: a supplemented inventory reading a matrix derived before the supplement gets the *same* digest, correctly, because the extra phones are not in the file's list and `phones` is already the check for those. The two fields then answer two questions and do not overlap.

**Where it goes.** One more key beside `phones` in the matrix format, written by `DistanceModel.save` and by `scripts/confusion.py derive`, so the shipped file and a caller's derived file carry it on the same terms. `space` is taken (`distance` / `similarity`); `metric` is free and says what it is.

**What `from_matrix_file` does on mismatch: refuse.** A percentile from the wrong reference distribution is a well-formed wrong answer, and the caller has nothing to notice it by — 0.9982 and 0.9447 are both perfectly reasonable-looking confusabilities for /s/ and /ʃ/. A warning is the right strength only where the caller can act without it; here they cannot.

**Absence is not mismatch.** A file with no `metric` key is accepted without comment. `from_matrix_file` also reads TSV grids of empirical confusion data, which are not derived from the metric at all and have nothing to agree with; refusing those would be refusing the mechanism's main external use. Every matrix ipakit writes carries the key, so the silent case is exactly the case that should be silent.

`scripts/confusion.py validate` gains the same comparison for free, and with it catches a change to `metric.py` that happened to leave every cell inside the tolerance.

## 4. What moved

From the owner's point of view this is the deliverable: run an experiment, be told its consequences. The good news is that almost all of it exists and none of it needs to be new machinery.

**The unit should be the pair, ranked by magnitude, with a count first and the top movers under it** — the shape `scripts/sweep.py diff` already reports for units and `scripts/confusion.py validate` already reports as a bare count ("DRIFT: N matrix cells differ"). What that count is missing is which cells and by how much.

**Nearest-neighbor flips are the second unit, and for a student they are the better one.** `d(s, ʃ) 0.009000 -> 0.014000` is a number. `s: ʃ -> ɕ` is a claim about the world, in the vocabulary the hypothesis was written in, and it is short enough to read all of: 14 flips out of 139 phones for `posteriority`, 7 for `glottality`, 1 for `ghost`. A report that leads with the flip list and follows with the ranked pair movers tells a three-line experiment's author what they did in about two screens.

**Where it belongs: `scripts/`, as a `diff` subcommand on `scripts/confusion.py`.** The CLI reads the shipped inventory only, which [supplements.md](../supplements.md) already records as a limit, so a perturbation report has no home there. The library should not grow a reporting surface for the same reason `sweep.py` is a script and not a module. And `confusion.py` already owns this file format: `_load_matrix_json`, `triangles_match` and the tolerance are all there, so the diff is a ranking over `zip(a["triangle"], b["triangle"])` plus a nearest-neighbor pass, reusing rather than reinventing.

The workflow is then symmetrical with the one `review-state.md` already prescribes for units:

```
python scripts/confusion.py generate --write         # or DistanceModel.derive(ipa).save(path)
python scripts/confusion.py diff before.json after.json
python scripts/sweep.py diff before.json after.json  # descriptions and d_from_base, over composed units
```

The sweep half matters more than it looks. `posteriority` moved 12 of 8,616 units' distance from their own base, and `glottality` moved 4,982 — the same experiment reads completely differently depending on which unit you count in, and a report that gave only one of them would flatter or damn the hypothesis by choice of denominator.

## 5. Projections

**Refuse, and not for symmetry.** Three reasons, in order of weight.

**A projection must be total over its fine feature.** The loader refuses one that leaves any value unmapped, and it is right to: a partial projection would leave the rest of the values looking like an independent dimension. So a supplement's projection can only be a statement about *every* value of a feature the base declares — which is redefinition of what the base said, not an extension of it. Supplements already refuse redefinition for symbols, on the stronger ground that "which file wins" must not depend on load order. A projection is the same refusal with a different noun.

**The claim that it is read by the write side only is not true today.** `ipa.xml` says so beside the block, and `compose_unit` is indeed the main reader, but `ipakit/tract.py` reads it twice. `glottal_aperture` finds the glottal scale as *the ordinal feature a projection refines*, and `unmodelled` suppresses marks for any feature a projection names. Measured, with a second projection added over `length`:

```
bundles moved:            0 of 139
pairwise distances moved: 0 of 9,591
glottal_aperture moved:  37 of 139     c f h k p q s t x ç ... : 1.0 -> 0.333
unmodelled marks moved:   0 of 139
```

So the metric is untouched, exactly as the brief predicts — and 37 phones are drawn with the vocal folds somewhere else. `docs/figures` is a checked-in derived artifact regenerated by `make figures`, so a projection is a change to shipped drawings arriving through a file that declares no geometry.

**The mechanism that picks the scale is fragile at two.** `glottal_aperture` selects with `next(... for name in sorted({fine for fine, _ in features.projections}) ...)`, so with more than one projection the glottal model goes to whichever fine feature sorts first alphabetically. With the one projection `ipa.xml` ships, that is a correct and rather elegant derivation. With two it is arbitrary, and arbitrary in a way no error message would mention. This is a pre-existing fragility rather than a consequence of admitting anything, and it is worth fixing on its own account; see §8.

None of the three is fatal on its own. Together they say a projection is a statement about the whole feature space made by a file that is not allowed to describe the feature space, and that its consequences land somewhere nobody looking at the file would think to check.

## 6. The degenerate cases

Every case below was produced by putting the construction into a copy of `ipa.xml` and loading it, because that is where the code paths are today. Each is what a supplement-level bridge would inherit.

**Two bridges over overlapping spellings — silent double charge.** A second bridge naming exactly `laterality`'s two spellings loads without comment, and the dimension is then counted twice:

```
d(l, t)  0.191667 -> 0.230159
d(l, n)  0.191667 -> 0.230159
d(a, b)  0.260000 -> 0.248696     (9,413 of 9,591 pairs moved)
```

Two supplements that each declare "their own" bridge over `channel="lateral"` — which is what two people working on lateral phonology would both write — would double the weight of laterality in the metric and say nothing. **This must be a refusal, not a merge.** A merge would be worse: it would need a rule for which name survives, and the answer would depend on load order, which is the failure this repository has shipped before. The right shape already exists in the loader — `<notations>` refuses a symbol listed under two conventions, for word-for-word the same reason.

**A bridge redeclaring an existing bridge's name — silent replacement.** Today `self.bridges[bname] = ...` overwrites:

```
<bridge name="laterality"><spelling feature="channel" value="grooved"/></bridge>
  laterality now spells: (('channel', 'grooved'),)
  2,672 of 9,591 pairs moved;  d(l, t)  0.191667 -> 0.141667
```

Laterality stopped meaning laterality, and `/l/` moved *toward* `/t/`. **Refusal**, matching the symbol-collision rule a supplement already applies and naming both files.

**A bridge naming a `(feature, value)` that exists but no symbol spells — loads, and moves almost everything.** This is the `ghost` experiment: 9,413 of 9,591 pairs, one nearest-neighbor flip, no error. The loader already refuses an *undeclared* feature and an *undeclared* value; declared-but-unspelled passes both checks. It is worth being precise about why it is not harmless: `rounded="-"` and `airstream="pulmonic"` are written on no symbol but are supplied to nearly every bundle by the default fill, so the derived binary is near-constant across the inventory — a key that says the same thing about everything, dividing every distance by one more. **A refusal is too strong** (a supplement may legitimately bridge a spelling only its own new phones carry) but the case should be reported, and the report in §4 reports it by construction: a bridge that moves every pair by the same shrinking factor has an unmistakable signature.

**A bridge shadowing a declared feature — already refused, verified.** The check exists and it covers the case that looked most dangerous:

```
<bridge name="articulator">  ->  ValueError: bridge 'articulator' collides with a declared feature;
                                 a bridge is derived for comparison and must not shadow one
```

`_metric_bundle` writes a derived `articulator` key into the comparison bundle after resolving the active organ, and a bridge of that name would clobber it. It cannot, because `articulator` is itself declared in `<features>` and the collision check catches it. Correct for the right reason, not by luck — but it is worth noting that the guard's scope is "declared features", and the set of derived keys the metric writes happens to be a subset of that. Should a future derived key not be a declared feature, the guard would not cover it.

**Order independence — holds.** Two bridges, both orderings, same file otherwise:

```
0 pairs differ between the orders
```

`bundle_distance` sorts its key union and `excluded_keys` returns a frozenset, so bridge declaration order does not reach the metric. This half of the brief's claim is correct and survives everything above: if bridges were admitted, two supplements in either order would give the same distances. The problems are collision and blast radius, not ordering.

## 7. The grammar

Admitting `<bridges>` to `supplement.rng` is the cheapest part of the whole proposal, which is worth saying plainly because it is not an argument for doing it.

The `bridges` define in `ipa.rng` is copyable as it stands: `<bridge>` takes `name`, optional `desc` and `href`, and one or more `<spelling>` with `feature`, `value` and an optional `port`. Adding it to `supplement.rng` means the define plus one more branch in the `<choice>` inside `<oneOrMore>` at `<start>`.

Stating that shape names nothing the inventory declares. `feature` and `value` are attribute *names* here and their contents stay `<text/>`, so no feature name and no feature value is copied into the grammar. The two no-smuggling tests both survive:

- `test_no_grammar_names_the_inventory` is scoped to `SYMBOL_ELEMENTS` — `phone`, `diacritic`, `suprasegmental`, `separator`, `zero`. A `<bridge>` is not one, so its attribute names are never compared against the inventory. `ipa.rng` already carries this exact define and passes.
- `test_no_grammar_enumerates_a_declared_value` looks at `<rng:value>` text anywhere in any grammar. The define contains none; `port` constrains through `<data type="decimal">`, not an enumeration.

The parametrized refusal test would need `"bridges"` dropped from its list, leaving the other five. That is the honest accounting of the change and also the reason to be careful: the test's own docstring explains that the blocks are named *there* and not in the grammar because "this test is where the consequence for each of them is checked". Removing an entry from that list removes the place where the consequence for bridges was written down. It should not be removed without §1's measurements being written down somewhere in its place.

The larger cost is in the loader, and it is structural rather than laborious. `_load_supplement` refuses any section `<classes>` does not name, which is why it needs no list of the forbidden and why a new kind of declaration in `ipa.xml` cannot sail through it. Admitting `<bridges>` means special-casing one section name against that rule, and the property "a supplement holds symbol sections, and the class list says which" stops being true. `supplement.rng`'s own comment makes the same point about the whitelist. That property is worth more than the grammar edit costs.

## 8. What follows

Five things follow from the verdict, in the order they should be done. None was applied in this lane.

### (a) The fingerprint, first and independently

§3, in full: a `metric` key in the matrix format, written by `DistanceModel.save` and `scripts/confusion.py`, checked by `from_matrix_file` with a refusal on disagreement and silence on absence, and checked by `scripts/confusion.py validate`.

This is not contingent on anything else here. The hazard it closes exists today for any caller who follows [supplements.md](../supplements.md)'s own instructions and derives a matrix for a supplemented inventory: nothing stops that inventory from being handed the shipped one instead, and nothing tells them it happened.

### (b) The report, second

§4: `scripts/confusion.py diff`, reporting a count, the ranked pair movers, and the nearest-neighbor flips, over two files in the format `save` already writes.

Also not contingent. It is the missing half of `sweep.py diff` — the sweep covers composed units and their descriptions, and nothing covers the matrix except a bare drift count. Any change to `metric.py` or to `ipa.xml` would be easier to review with it, which is a stronger argument for building it than the experiment loop is.

### (c) The perturbation file, third, and only if still wanted

With (a) and (b) in place, the loop the brief describes already runs. Every measurement in this document was produced by splicing a `<bridge>` into a copy of `ipa.xml` and loading it with `IPAFeatures(xml_path=...)` — the mechanism exists, [supplements.md](../supplements.md) already names it ("if you need to change what the base declares, edit a copy of `ipa.xml` and load that"), and nothing shipped moves when you use it.

The real cost of that route is the one this repository is least tolerant of: it is a whole-file copy, and a copy drifts. A student's `retroflex-hypothesis.xml` is a copy of the whole inventory of which three lines are the hypothesis, and next release it is a copy of last release's inventory.

If that cost is judged to bite, the answer is a **separate root element with its own constructor argument** — not `<bridges>` inside `<supplement>`. The reasons are §2 and §6 together: what such a file does is not additive, not monotone, and not confined to what it declares, so it should not be called by the name of a mechanism whose documented property is all three. A distinct root also gives the collision rules in §6 somewhere to live without loading them onto the supplement loader, and it keeps `_load_supplement`'s "sections `<classes>` names, and nothing else" rule intact.

Whatever it is called, it should refuse a bridge that collides with a declared feature (already done), a bridge that redeclares another bridge's name, and a bridge whose spellings overlap another bridge's — and it should print the §4 report on load, because a file whose entire purpose is to move the metric should say what it moved.

### (d) The sentence the loader gives for the refusal

`_load_supplement`'s docstring, `supplement.rng`'s header, [supplements.md](../supplements.md) and the parametrized test all give one reason: "a bundle key is a term in the metric". §1 shows that reason is exact for `<features>` and does not name what is wrong with `<bridges>` — a bridge is a term in the metric *without* being a bundle key, which is precisely the gap the case for admitting it walked through.

The refusal is right. Its stated reason is one sentence short. Something like: *a bundle key is a term in the metric, and so is a bridge, which derives one — a file that could declare either could reshape every distance in the inventory it was merely meant to extend.* Not applied here; the change belongs to whoever picks it up, along with a pointer to this document.

### (e) `glottal_aperture` picks its scale alphabetically

Turned up by §5 and unrelated to supplements. With one projection the derivation is correct and there is nothing to fix today. With two, `sorted()` decides which feature is the glottal scale, silently. Either the selection should be by something meaningful — the projection whose coarse feature the tract model actually reads — or the ambiguity should be refused at load, the way a symbol under two notations is.

## Reproducing the measurements

Every number here was taken under `PYTHONHASHSEED=0` against this worktree, on `main`. The recipe, in full:

```python
# splice one <bridge> into a copy of the shipped inventory
text = (DATA_DIR / "ipa.xml").read_text()
Path("variant.xml").write_text(text.replace("  </bridges>", BLOCK + "\n  </bridges>", 1))

base, alt = IPAFeatures(), IPAFeatures(xml_path="variant.xml")

# bundles: scripts/sweep.py owns the corpus definition -- import it, do not rewrite it
import sweep
units = sweep.corpus(base); sweep.check_corpus(base, units)
moved = [u for u, _, _ in units if base.get_features(u) != alt.get_features(u)]

# distances: the same triangle scripts/confusion.py derives
phones = list(base.phones)
m1, m2 = base.pairwise_distances(phones), alt.pairwise_distances(phones)
```

The corpus counts come from `python scripts/sweep.py corpus`. The pairwise tolerance is `scripts/confusion.py`'s `TOLERANCE = 1e-9`, for the reason given there. The blast-radius comparison in §2 uses the checked-in `docs/examples/aspirated-stops.xml`. The projection measurement in §5 splices a second `<projection>` over `length` into `<projections>` and reads `ipakit.tract.glottal_aperture` and `ipakit.tract.unmodelled` over the 139 registered phones; `length` was chosen because it is ordinal and sorts before `phonation`, which is what makes it take the glottal scale over — the experiment is about the selection mechanism, not about a phonetic claim.
