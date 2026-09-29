# PHOIBLE inventories and original source data

`PhoibleBridge()` reads the shipped main CSV from development snapshot
`b92abff4f4ca2544eece4d9eff5c707f8d508d0c`. This development pin is distinct
from the PHOIBLE 2.0 release and stays fixed as upstream advances. An explicit
checkout path (including its `data/phoible.csv`) takes precedence over
`IPAKIT_PHOIBLE`, which takes precedence over the shipped main CSV. An invalid
explicit path or environment setting raises an error.

The main CSV already supplies InventoryID, ISO 639-3, Glottocode, language name
and source, so catalog ingestion and whole-source audit do not need a mapping
table. Bibliographic provenance uses `mappings/InventoryID-Bibtex.csv`; those
mapping bytes do not ship. A language or inventory operation that needs them
requires an explicit PHOIBLE checkout or `IPAKIT_PHOIBLE` and refuses with that
variable named when none is available.

```python no-run
from ipakit.bridges.phoible import PhoibleBridge
from ipakit.phoible_source import read_source, source_files, source_policy

source = PhoibleBridge()  # shipped main CSV
audit = source.audit()
source = PhoibleBridge("/path/to/phoible")  # mapping-backed provenance
english = source.language("eng")  # separate, attributed rival inventories
inventory = source.inventory(160)  # entries plus positioned refusals
original_csv = read_source("data/phoible.csv")  # exact upstream bytes
```

The frozen main CSV has 105,484 rows, 3,020 inventories and 49 columns.
All foreign feature values and original spellings remain in the source bytes,
even when house conversion refuses them. `source_files()` discovers the two
shipped CSV/BibTeX paths; `source_policy()` returns the receipt's nested
source identity and input hashes.
`read_source()` verifies compressed transport and decompressed source identity.
Missing or corrupted packaged resources raise typed extraction source errors.
The reference bibliography is included. The independent mapping tables are not;
the bridge reads bibliographic keys from the user-supplied mapping table while
using the main CSV directly for ISO 639-3, Glottocode, language name and source.

`language` returns separate doculect inventories in a spread. `inventory` retains
allophones, marginality and explicit refusal reports under the existing house
parser. House conversion has explicit limits: source members may be refused or
span multiple segments. Typed PHOIBLE feature scoring and full house expressivity
remain outside this bridge's scope. The raw source API preserves the complete
source independently of those conversion limits. External inputs carry their
own unverified provenance, separate from the shipped pin.

## Separate data terms

These resources retain their terms alongside IPAkit's BSD original-code license.
The file-scoped notice and license texts ship in `data/phoible/`: the historical
upstream MIT data notice and current dataset CC BY-SA 3.0 terms. The shipped
scope excludes mapping tables and donor `raw-data/`. See the
[packaged notice](../ipakit/data/phoible/NOTICE.txt),
[PHOIBLE attribution](https://phoible.org/about) and
[upstream notice discussion](https://github.com/phoible/dev/issues/384#issuecomment-3411788511).
Reversible gzip is transport only; decompression recovers the original editable
CSV/BibTeX bytes. The source and binary distributions both carry those sources
and notices. Redistribution and adaptations retain the applicable terms,
attribution and notices; inclusion does not relicense independent code.

## Explicit development rebuild

```sh
python scripts/dev_sources.py check phoible --source /path/to/accepted/phoible
python scripts/dev_sources.py build phoible --source /path/to/accepted/phoible
```

The offline library producer is `ipakit.extraction.phoible`; acquisition and
publication remain the existing [developer runner](development-sources.md).
Fetching is explicit, pinned and separately cached; discovery never repins.
