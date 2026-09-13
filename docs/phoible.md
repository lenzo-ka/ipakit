# PHOIBLE inventories and original source data

`PhoibleBridge()` and `ipakit phoible` use the shipped development snapshot by
default: `b92abff4f4ca2544eece4d9eff5c707f8d508d0c`. This development pin is
distinct from the PHOIBLE 2.0 release and stays fixed as upstream advances.
An explicit checkout path (including its `data/phoible.csv`) takes precedence
over `IPAKIT_PHOIBLE`, which takes precedence over the shipped data. An invalid
explicit path or environment setting raises an error. The default reads local
packaged resources, with no provider installation, checkout or network required.

```python
from ipakit.bridges.phoible import PhoibleBridge
from ipakit.phoible_source import read_source, source_files, source_policy

source = PhoibleBridge()
english = source.language("eng")  # separate, attributed rival inventories
inventory = source.inventory(160)  # entries plus positioned refusals
original_csv = read_source("data/phoible.csv")  # exact upstream bytes
```

The complete frozen source has 105,484 rows, 3,020 inventories and 49 columns.
All foreign feature values and original spellings remain in the source bytes,
even when house conversion refuses them. `source_files()` discovers the four
original CSV/BibTeX paths; `source_policy()` returns the revision and hashes.
`read_source()` verifies compressed transport and decompressed source identity.
Missing or corrupted packaged resources raise typed extraction source errors.
The independent original mapping tables and reference bibliography are included.
The bridge's inventory provenance comes from those mappings; 782 InventoryIDs
have literal metadata differences from the main CSV, including case and Unicode
differences. Both versions of that metadata are preserved as supplied upstream.

`language` returns separate doculect inventories in a spread. `inventory` retains
allophones, marginality and explicit refusal reports under the existing house
parser. House conversion has explicit limits: source members may be refused or
span multiple segments. Typed PHOIBLE feature scoring and full house expressivity
remain outside this bridge's scope. The raw source API preserves the complete
source independently of those conversion limits. External inputs carry their
own unverified provenance, separate from the shipped pin.

## Separate data terms

These resources retain their component licenses alongside IPAkit's BSD
original-code license.
The complete file-scoped notice and license texts ship in `data/phoible/`:
historical upstream MIT data notice, current dataset CC BY-SA 3.0 terms, and
the extant GPLv3 notice for unchanged mapping tables. This is a separately
licensed source-data aggregate; its component terms apply individually. The
shipped scope excludes donor `raw-data/`. See the [packaged notice](../ipakit/data/phoible/NOTICE.txt),
[PHOIBLE attribution](https://phoible.org/about) and
[upstream notice discussion](https://github.com/phoible/dev/issues/384#issuecomment-3411788511).
Reversible gzip is transport only; decompression recovers the original editable
CSV/BibTeX bytes. The source and binary distributions both carry those sources
and notices. Redistribution and adaptations retain the applicable component
terms, attribution and notices; inclusion does not relicense independent code.

## Explicit development rebuild

```sh
python scripts/dev_sources.py check phoible --source /path/to/accepted/phoible
python scripts/dev_sources.py build phoible --source /path/to/accepted/phoible
```

The offline library producer is `ipakit.extraction.phoible`; acquisition and
publication remain the existing [developer runner](development-sources.md).
Fetching is explicit, pinned and separately cached; discovery never repins.
