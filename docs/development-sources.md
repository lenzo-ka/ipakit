# External source development

Frozen runtime data and optional live providers are different capabilities.
Reading shipped MFA declarations requires neither a source checkout nor a
development package. Rebuilding them requires the accepted external dataset.
No library import or ordinary ipakit command installs packages or fetches data.

## Library ownership

`ipakit.extraction.mfa.build(source: Path)` validates local MFA metadata and
returns a `BuildResult` containing repository-relative artifact paths and bytes.
It does not write files. `result.stale(root)` compares those artifacts and the
producer's explicitly owned file patterns against a destination. The result's
`SourceIdentity` reuses structured `SourceMetadata` and records consumed hashes.
No second parser or independent feature mapping is hidden in the update script.

`ipakit.extraction.mfa.require_pin(source, dictionary=True)` additionally checks
the full en-US dictionary used by inventory cards. Metadata-only generation
uses the default `dictionary=False`; it does not consume the dictionary.
Missing data, a wrong revision and changed content raise catchable
`SourceMissingError`, `SourceVersionError` and `SourceContentError`, respectively,
all subclasses of `SourceError`/`ValueError`, with distinct `.code` values.
Neither this library path nor its MFA producer requires optional packages.

The existing `scripts/mfa_vocabularies.py generate|check` commands delegate to
this library. `scripts/inventory_cards.py` uses the same validator and the
existing dictionary/inventory APIs. MFA's original curated exceptions, license
checks and generated artifact bytes remain unchanged.
Curated source-specific reductions, notes and examples are declared in
`ipakit/data/mfa-curation.json`, not per-symbol Python tables. The builder checks
them against the selected upstream inventories before rendering.

## Developer orchestration

Run these from a source checkout:

```sh
python scripts/dev_sources.py status all
python scripts/dev_sources.py fetch mfa
python scripts/dev_sources.py check mfa
python scripts/dev_sources.py build mfa
python scripts/dev_sources.py discover mfa
```

`fetch` and `discover` explicitly authorize network access. `fetch` uses
`~/.cache/ipakit/sources/mfa/<accepted-revision>` by default; `--cache DIR`
changes its cache parent. It populates only a new directory and validates
consumed bytes after acquisition. Existing sources are validated without reset,
checkout, pull or repair. Failed acquisition leaves its directory available for
inspection; use a new cache location after investigating it. Symlinked
acquisition destinations are refused. Package installation and global upgrades
are not implemented by this first producer.

For offline operations, `--source PATH` reads an existing clone or archive;
it is forbidden with `fetch`. `--output PATH` selects the build/check destination.
`build` writes producer-owned artifacts and removes stray files only within its
declared output patterns, matching the existing MFA generator's ownership.
Use a staging output directory when reviewing candidate content. Publication
refuses symbolic-link artifact paths; it is not a transactional multi-file write.

`discover` queries upstream HEAD without fetching objects or changing the
accepted revision/digests. A different HEAD is a **candidate**, not proof of
ancestry, compatibility, a newer release, or license approval. Reviewing and
repinning source content remains a normal code/data change. The accepted MFA
revision and content digests are owned by the library producer; scripts import
them instead of maintaining a second pin registry. Dependency support ranges
remain in `pyproject.toml` and are not resolved input-content locks.

## Honest partial support

Every command emits JSON with the requested operation, each source's status,
expected/observed identity where verified, diagnostics and an aggregate
`complete` flag. `status` succeeds at reporting missing sources but leaves
`complete: false`. Requested unsupported operations, missing inputs and errors
make build/check/fetch/discover exit nonzero. `check` also exits nonzero for
artifact differences; a successful `build` may report `changed`.

This first lifecycle adapter is **MFA only**. `all` includes explicit unsupported
entries for the census's eSpeak, Panphon, ICU, CLTS, inventory-card, CMU-dictionary,
PHOIBLE, ipa-dict, XRMB and internal-generator paths. Those entries are an
operation-support boundary, not a duplicate inventory or dependency registry.
Existing tools for these sources still work independently. CLTS awaits its
actual artifact producer contract; the runner does not invent it. Supporting
test/lint packages and the optional PocketSphinx runtime engine are not inventory
sources to regenerate.

The updater does not grant redistribution rights. Provider-specific accepted
licenses, provenance, source notices and release review remain in force. An SPDX
syntax check is not a compatibility decision. No source version or licensing
policy is changed by introducing the runner.
