# PHOIBLE inventories and original source data

`PhoibleBridge()` reads the shipped main CSV and mapping tables from development
snapshot `5f82b9c3fbb0b5c630de20e254c5fdad645e3e56`. This development pin is
distinct from the PHOIBLE releases and stays fixed as upstream advances. An
explicit checkout path (including its `data/phoible.csv`) takes precedence over
`IPAKIT_PHOIBLE`, which takes precedence over the shipped snapshot. An invalid
explicit path or environment setting raises an error.

The main CSV already supplies InventoryID, ISO 639-3, Glottocode, language name
and source, so catalog ingestion and whole-source audit do not need a mapping
table. Bibliographic provenance uses `mappings/InventoryID-Bibtex.csv`, which
ships with the snapshot. A selected checkout supplies its own mapping tables
and refuses, naming `IPAKIT_PHOIBLE`, when they are missing.

```python no-run
from ipakit.bridges.phoible import PhoibleBridge
from ipakit.phoible_source import read_source, source_files, source_policy

source = PhoibleBridge()  # shipped snapshot
audit = source.audit()
english = source.language("eng")  # separate, attributed rival inventories
inventory = source.inventory(160)  # entries plus positioned refusals
original_csv = read_source("data/phoible.csv")  # exact upstream bytes
```

The frozen main CSV has 105,484 rows, 3,020 inventories and 51 columns.
All foreign feature values and original spellings remain in the source bytes,
even when house conversion refuses them. `source_files()` discovers the
shipped CSV/BibTeX paths; `source_policy()` returns the receipt's nested
source identity and input hashes.
`read_source()` verifies compressed transport and decompressed source identity.
Missing or corrupted packaged resources raise typed extraction source errors.
The reference bibliography and the `mappings/InventoryID-*.csv` tables are
included. The bridge reads bibliographic keys from the mapping table and uses
the main CSV directly for ISO 639-3, Glottocode, language name and source.

`language` returns separate doculect inventories in a spread. `inventory` retains
allophones, marginality and explicit refusal reports under the existing house
parser. House conversion has explicit limits: source members may be refused or
span multiple segments. Typed PHOIBLE feature scoring and full house expressivity
remain outside this bridge's scope. The raw source API preserves the complete
source independently of those conversion limits. External inputs carry their
own unverified provenance, separate from the shipped pin.

## Separate data terms

These resources retain their terms alongside IPAkit's BSD original-code license.
PHOIBLE data and mappings are licensed under the Creative Commons Attribution
4.0 International License (CC BY 4.0). The notice and upstream `LICENSE-DATA`
text ship in `data/phoible/` as `NOTICE.txt` and `CC-BY-4.0.txt`. The shipped
scope excludes upstream code and donor `raw-data/`. See the
[packaged notice](../ipakit/data/phoible/NOTICE.txt) and
[PHOIBLE attribution](https://phoible.org/about).
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
