# User-supplied sources

IPAkit ships the PHOIBLE dataset, bibliography and mapping tables used by its
PHOIBLE bridge. It does not ship eSpeak NG phoneme tables. To use an eSpeak
inventory, fetch or provide the pinned eSpeak NG source and build declarations
into a managed cache.

The `ipakit source` commands currently manage eSpeak only. They do not replace
the separate developer workflows that regenerate data shipped in the wheel.

## Managed fetch and build

This workflow lets IPAkit fetch its accepted eSpeak NG pin into the source
cache and build the declarations beside it:

```sh
ipakit source fetch espeak --cache <cache-directory>
ipakit source build espeak --cache <cache-directory>
ipakit source status espeak --cache <cache-directory>
ipakit source receipt espeak --cache <cache-directory> -f json
```

`fetch` is the only installed source command that uses the network. It requires
Git on `PATH`, acquires the exact accepted revision and never builds tables.
After `fetch` finishes, disconnecting from the network does not change the
behavior of `build`, `status`, `receipt` or an eSpeak inventory read. Those
operations never fetch.

Existing source directories are validated but never repaired, updated or
deleted. A failed acquisition does not publish a partial source directory.

The equivalent module-scoped Python API is:

```python no-run
from ipakit import sources

sources.fetch("espeak", cache_dir="<cache-directory>")
sources.build("espeak", cache_dir="<cache-directory>")
state = sources.status("espeak", cache_dir="<cache-directory>")
record = sources.receipt("espeak", cache_dir="<cache-directory>")
```

## Build from an existing source

If the accepted eSpeak NG source is already available, skip `fetch`. Give the
source to `build` directly or set `IPAKIT_ESPEAK_NG`:

```sh
ipakit source build espeak \
  --source <accepted-espeak-source> \
  --cache <cache-directory>
```

```sh
IPAKIT_ESPEAK_NG=<accepted-espeak-source> \
  ipakit source build espeak --cache <cache-directory>
```

The source must match the revision accepted by the installed IPAkit version.
`build` is offline. It validates and hashes every input it consumes, renders
the declarations in a private staging directory, verifies the receipt and
artifact hashes, and then publishes the complete directory atomically.

Applications may also read a validated source directly without publishing a
managed build:

```python no-run
from ipakit.bridges.espeak import EspeakBridge

bridge = EspeakBridge("<language-code>", source="<accepted-espeak-source>")
```

## Selection and cache precedence

An eSpeak runtime read selects, in order:

1. The explicit `source=` argument.
2. `IPAKIT_ESPEAK_NG`.
3. The valid managed build selected by the cache root.

An explicit argument or environment setting that is missing or invalid is an
error. IPAkit does not silently fall through to a managed build. A build uses
the same first two choices, then a source previously acquired by `fetch`.

The cache root is selected, in order:

1. `--cache` or `cache_dir=`.
2. `IPAKIT_SOURCE_CACHE`.
3. `$XDG_CACHE_HOME/ipakit` when `XDG_CACHE_HOME` is set.
4. The user's standard `.cache/ipakit` directory.

Imports and command-parser construction do not inspect the cache. A cache is
read only when an operation or inventory needs it.

## Cache layout

The accepted commit and table format are directory components. There is no
mutable `current` link:

```text
<cache-root>/
  sources/
    espeak/<accepted-commit>/
      .git/
      COPYING
      phsource/
  tables/
    espeak/<accepted-commit>/format-<format>/
      receipt.json
      <language-code>.xml
      ...
```

Other commits and formats may remain beside the current one. IPAkit never
deletes them automatically. Source acquisition refuses a symbolic-link
destination but permits a symbolic-link cache parent. Table publication
refuses any symbolic link on the destination path.

## Receipts and reproducibility

Every managed table directory has one validated `receipt.json`. The receipt
records the upstream URL, accepted tag and commit or source hash, hashes for
all consumed inputs, the extractor identity, the IPAkit version, table format,
UTC build time, artifact hashes and the hash of the source license notice. A
local source or cache path is never recorded. The source notice is hashed but
is not copied into the table directory.

Rebuilding the same source produces byte-identical declaration artifacts. The
receipt fingerprint changes because it covers the build time; artifact SHA-256
values are the reproducible identities. `ipakit source receipt` refuses a
missing or invalid receipt. Runtime reads verify the receipt and hash only the
table they use; inventory listing reads the receipt without loading every
table.

## Status and stale builds

`status` is offline, read-only and exits successfully whenever it can report a
state. Its states are `missing`, `source-only`, `ready`, `stale-pin`,
`stale-format` and `invalid`. JSON output sets `complete` to `false` unless the
selected build is ready.

Illustrative stale reports use sample revisions but match the rendered fields
and spacing:

```text
espeak  stale-pin      tag=1.52.0 revision=01234567… format=1; eSpeak NG tables in the cache were built from 0123456789abcdef; this ipakit expects 4870adfa25b1a32b4361592f1be8a40337c58d6c (tag 1.52.0). Run 'ipakit source fetch espeak' then 'ipakit source build espeak'. Nothing was rebuilt.
espeak  stale-format   tag=1.52.0 revision=4870adfa… format=2 required=1; eSpeak NG tables in the cache are format 2; this ipakit reads format 1. Run 'ipakit source build espeak'. Nothing was rebuilt.
```

A stale build is never served, rebuilt or removed implicitly. Run the command
named by the report when that action is wanted. Reading an unrelated inventory
does not load or validate optional eSpeak data.

## PHOIBLE in installed packages

PHOIBLE is not a user-source provider for `ipakit source`. The wheel includes
the pinned main CSV, reference bibliography and mapping tables. `PhoibleBridge`
selects an explicit `path=` first, then `IPAKIT_PHOIBLE`, then the shipped
snapshot. As with eSpeak, an invalid explicit path or environment setting is an
error rather than a reason to fall through. See [PHOIBLE inventories](phoible.md)
for its source scope, provenance and separate data terms.
