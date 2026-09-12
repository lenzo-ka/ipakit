# CLTS/BIPA declaration census and comparisons

CLTS/BIPA interoperability starts with the two systems' declarations, not
guessed symbol equivalences. The development instrument reads an external
[CLTS checkout](https://github.com/cldf-clts/clts); no CLTS data is bundled.

```sh
python scripts/interop.py --clts /path/to/clts declarations
```

This emits deterministic JSON (`ipakit-clts-declaration-census`, version 1).
It reads the master `pkg/transcriptionsystems/features.json` separately from
the derived `data/features.tsv` and observed `data/sounds.tsv`. Qualified
identities retain unit kind, feature name, and value: two features sharing a
value spelling are not merged. Native values come from the existing
`load_ipa_features()` declaration loader, retaining declared applicability,
mode, locus, type, axis, sequence support, and value order.

The output includes SHA-256 hashes of the consumed declaration/catalog
files, both directional queues, observed counts by sound kind, and up to five
sorted catalog sound IDs per CLTS feature/value. A master declaration without
a catalog witness remains present. A catalog feature absent from the master
is explicitly marked `declared: false`; it is not silently promoted into a
declaration. Missing inputs, malformed domains, duplicate identities, ragged
tables, and dangling feature references fail nonzero without emitting a report.
Exit zero means the census ran, **not** that semantic correspondences passed.

Every entry currently has `status: unclassified` and no targets. This is an
audit foundation, not a conversion map or a claim that the target cannot
express a source distinction. Reviewed directional mappings, preconditions,
loss accounting, and enhancement dispositions remain separate work.

## Population boundary

This census covers finite feature/value declarations and feature occurrences
in the supplied sound catalog. Composite catalog kinds remain counted, with
their component feature contexts. Unit kinds lacking master domains are
listed explicitly. Productive composition rules, tier/host relationships,
and native combined or sequence-valued expressions are outside this census;
they must be audited before claiming a complete interoperability model.
The tool requires no `pyclts` import or runtime dependency.

## CLTS's own similarity

```sh
python scripts/interop.py --clts /path/to/clts similarity
```

This existing comparison needs the optional `pyclts` development dependency
(`pip install -e '.[interop]'`). CLTS's `Sound.similarity` is unweighted
Jaccard similarity over feature-value names: intersection size divided by
union size. The comparison uses `1 - similarity` so that smaller scores mean
closer sounds on both axes. It does not replace native `ipakit.distance`,
whose declared feature geometry distinguishes differences that a set overlap
does not. Neither a correlation nor nearest-neighbor agreement establishes
perceptual equivalence.

The population is registered native phone spellings directly resolved by
BIPA, with unknowns and markers excluded; it does not apply house spelling
normalization. Output identifies the resolver version and hashes native data
and CLTS transcription-system files, then reports pair counts, score
resolution, rank correlation, and nearest-neighbor agreement. Equal nearest
scores use first native declaration order, not agreement between complete
tie sets. These results are measurements of the supplied sources, not frozen
claims about every release or all possible phones.

Upstream implementation: [pyclts sound models](https://github.com/cldf-clts/pyclts/blob/master/src/pyclts/models.py).
CLTS's inventory-level similarity methods are a separate API; this command
compares sound pairs, not inventories.
