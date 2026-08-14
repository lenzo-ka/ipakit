# Supplemental inventories

`ipa.xml` is the inventory ipakit ships. A **supplement** is a second XML file merged over it at load time, adding symbols the shipped file does not register. The motivating case is registering a composed segment — `tʰ`, `ɪ̃`, `t̚` — as a first-class phone.

The worked example on this page ships inside the package, at [aspirated-stops.xml](../ipakit/data/supplements/aspirated-stops.xml), so an installed ipakit carries an instance of the format and not only the grammar for it. It is asked for by name, the way a shipped rule set is, rather than by a path into `site-packages`:

```python
import ipakit
inventory = ipakit.load_ipa_features(supplements=["aspirated-stops"])
len(inventory.phones) - len(ipakit.load_ipa_features().phones)
# 3
ipakit.available_supplements()
# ['aspirated-stops']
```

A supplement of your own is passed as a path. `ipakit.supplement_path("aspirated-stops")` is where the shipped one landed in your copy — to read, or to copy as a starting point.

The instance that comes back is the caller's own. The module-level functions (`ipakit.distance`, `ipakit.confusability`, `ipakit.describe`), the shipped distance matrix, and every derived artifact in the package are built from the bare inventory and never see a supplement.

## What registering buys, and what it does not

Most of what "register this segment" sounds like it buys, you already have. A composed unit is accepted as **input** everywhere a registered phone is, with no supplement anywhere:

```python
ipakit.describe("tʰ")
# 'voiceless aspirated alveolar plosive'
round(ipakit.distance("tʰ", "t"), 4)
# 0.0476
round(ipakit.confusability("tʰ", "t"), 4)
# 0.9642
[p for p, _ in ipakit.nearest_phones("tʰ", n=3)]
# ['t', 'ȶ', 'p']
```

What registering adds is **membership** — being one of the phones the library counts, ranks and normalizes against. Concretely, four things.

**The reference distribution.** `confusability`, `normalized_distance` and `DistanceModel` return a *percentile within a reference inventory*, and that inventory is a set of registered phones. `distance_model(reference=[...])` re-slices the shipped matrix, so a member that matrix has no row for is dropped from the reference CDF, with a warning:

```python
narrow = ipakit.distance_model(reference=["p", "t", "k", "tʰ", "s", "a"])
narrow.reference_phones
# ['p', 't', 'k', 's', 'a']
```

The percentiles that model returns are the surviving subset's, and are byte-identical to a model built without ever naming `tʰ`. There is no way for a composed unit to be part of a reference distribution without registering it.

**The write side.** `to_phone` and `respell` answer only with registered phones. (`compose_unit` exists to fill that gap and returns `tʰ`; registering is what makes `respell` — and so a feature-changing rewrite rule — answer directly.)

```python
ipakit.respell("t", release="aspirated")
# None
inventory.respell("t", release="aspirated")
# 'tʰ'
```

**The result pools.** `nearest_phones`, `minimal_pairs` and `hierarchy` draw their *answers* from the phone table. A composed unit can be the question but never the answer.

**The listings.** Inventory statistics, `Phoneset` construction, and anything that iterates the inventory.

If none of those is what you want, compose the unit and skip this document.

## Writing one

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

The root element is `<supplement>`, not `<ipa>`, so handing a whole inventory where a supplement is wanted — or the reverse — is refused at load rather than half-merged. A whole replacement inventory is a different call: `load_ipa_features(xml_path=...)`.

Inside it, a supplement may declare entries in **the element sections `<classes>` already names** — `<phones>`, `<diacritics>`, `<suprasegmentals>`, `<separators>`, `<zeros>` — and nothing else. A `<features>`, `<types>`, `<bridges>` or `<projections>` block is a load-time refusal.

That line is the whole safety property. Every attribute on a declaring element lands in that symbol's feature bundle, and a bundle key is a term in the metric: a file that could declare a new feature would silently reshape every distance in the inventory it was merely meant to extend. A supplement adds symbols to a space; it does not redefine the space.

Both halves of that — the sections a supplement may hold and the declarations it may not — are stated as a RELAX NG grammar, `supplement.rng`, which ships in the package beside the worked example; `python -c 'from ipakit import SUPPLEMENTS_DIR; print(SUPPLEMENTS_DIR / "supplement.rng")'` says where your copy of it is. Validating against it (`xmllint --noout --relaxng`, or `lxml.etree.RelaxNG`) answers the structural half of the question before the loader is ever called.

### An entry that declares nothing derives from its spelling

`<phone name="tʰ"/>` states no features, so it is registered with the bundle `tʰ` already composes to:

```python
ipakit.features("tʰ") == inventory.get_features("tʰ")
# True
```

The registered reading and the composed reading are then the same object rather than two copies of one fact — which is the rule tied entries such as `t͡ʃ` already load under, applied to the general case. The alternative, retyping the bundle beside the symbol, is exactly the kind of second copy [reviewing.md](reviewing.md) is a record of.

An entry that *does* state features is a sound the base inventory cannot spell, and is taken as written:

```xml
<phone name="ƛ" manner="affricate" place="alveolar" channel="lateral"/>
```

A spelling that states nothing and composes to nothing is refused, because registering it would quietly create a phone the metric reads as all defaults.

### Merge semantics

**Additive, and order-independent.** A supplement adds symbols. A symbol the base file — or an earlier supplement — already declares is refused, naming both files. Two supplements may not share a name.

The refusal is deliberate. If a supplement could redefine `t`, then which file wins would depend on load order, and "the answer depends on declaration order and says so nowhere" is a failure this repository has shipped before. If you need to change what the base declares, edit a copy of `ipa.xml` and load that as the inventory.

**Aliases work as they do in the base file.** `alias="…"` on a supplement entry adds normalization entries, subject to the same collision refusal.

### Provenance does not ride on the entries

Which supplement a symbol came from is held beside the symbols, not on them:

```python
inventory.supplement_of["tʰ"]
# 'aspirated-stops'
sorted(inventory.supplements)
# ['aspirated-stops']
"supplement" in inventory.get_features("tʰ")
# False
```

That is measured rather than cautious: putting provenance on declaring elements once moved thirty-seven distances while `confusion.json` stayed byte-identical, because every attribute there lands in the feature bundle. `<notations>` in `ipa.xml` records the same finding beside itself, and is the model this follows.

## What a supplement does to `to_phone`

`to_phone` ranks every candidate over the whole phone table, so a new entry can beat an existing winner. That is measurable and silent: an Americanist `č` carrying `t͡ʃ`'s features spells them without a tie, so it wins on constituent count, and twenty-five bundles that answered `t͡ʃ` would answer `č` — on a call that did not change, in code that merely loaded a second file.

So the ranking asks **which file the candidate came from, first**: the base inventory before any supplement, and only then fewest extra features, fewest constituents, declaration order. A supplement entry answers where the base could not, and nowhere else.

The consequence is a property worth relying on: **adding a supplement can only turn a `None` into an answer.** It is swept over the whole unit corpus in `tests/test_supplements.py`, in both directions — that the change is monotone, and that removing the rank key is what lets the twenty-five movers through.

It also means a supplement cannot be used to *re-spell* the base inventory. `č` will not displace `t͡ʃ` as the answer to a bundle both satisfy. If that is what you want, you want your own `ipa.xml`.

## What a supplement does to the metric

`distance` is inventory-independent — it compares two feature bundles and does not consult the inventory — so it does not move.

Everything **normalized** does move, by design. `confusability`, `normalized_distance`, `nearest` and `DistanceModel.global_` return a percentile within a reference distribution, and a supplemented inventory has a different distribution: three extra phones are three phones' worth of new pairs in the CDF. The same raw distance therefore reads as a different percentile. That is the point of registering, and it is also why a supplemented inventory must carry **its own derived data**.

The shipped `data/confusion.json` is the bare inventory's matrix and stays that way. `DistanceModel.global_` reads it; `DistanceModel.for_phoneset` re-slices it and cannot help, since a supplemented phone has no row in it. The constructor for a supplemented inventory is `derive`:

```python
from ipakit import DistanceModel
model = DistanceModel.derive(inventory)
model.reference_name
# 'ipa+aspirated-stops'
"tʰ" in model.reference_phones
# True
model.confusability("tʰ", "t") == ipakit.confusability("tʰ", "t")
# False
```

`derive` costs a full pairwise pass, about a second at inventory scale. `save` writes the same upper-triangle format `data/confusion.json` ships in, and `from_matrix_file` reads it back, so a supplemented inventory's matrix is a checked-in derived artifact exactly as the shipped one is:

```python
from pathlib import Path
from tempfile import mkdtemp
saved = model.save(Path(mkdtemp()) / "confusion.json")
DistanceModel.from_matrix_file(inventory, saved).reference_phones == model.reference_phones
# True
```

Regenerate it whenever the supplement or the metric changes. Percentiles are not comparable across inventories, which is why the model's `reference_name` says which files it was built from.

A saved matrix also records the feature space it was derived in, and a reader refuses one derived in another — see [distance.md](distance.md) §11. That check is deliberately blind to supplements, which matters here because it also guards `DistanceModel.global_`, and a supplemented inventory reads the shipped matrix through it. It digests what the metric reads off the phones *the file itself lists*, and a supplement declares no feature, type or bridge, so a supplemented inventory agrees with the shipped matrix and with any matrix derived before the supplement was written. It should: the space did not move, only the membership, and membership is what `phones` records. The case the refusal is for is the other one this page names — editing a copy of `ipa.xml`, and not regenerating what was derived from the original.

## Limits

- **The command line reads the shipped inventory only.** Supplements are a Python-level facility.
- **A supplement cannot declare features, types, classes, modes, bridges or projections.** By design; see above.
- **A supplement cannot redeclare a symbol.** By design; a replacement inventory is the tool for that.
- **A supplement entry never outranks the base in `to_phone`.** By design; see above.
- **The shipped derived artifacts — `confusion.json`, the X-SAMPA table, the figures, the tutorial — are the bare inventory's** and are validated against it. A supplemented inventory's equivalents are yours to derive and keep.

## See also

- [tutorial.md](tutorial.md) §11 — the same ground as a worked example.
- [distance.md](distance.md) — what the metric claims, and the difference between a distance and a percentile.
- [ties.md](ties.md) — how a composed unit is put together, and why a registered composite and a composed one must agree.
- [reviewing.md](reviewing.md) — the method behind the sweeps this document quotes.
