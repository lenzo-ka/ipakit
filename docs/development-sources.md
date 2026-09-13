# External source development

Shipped MFA declarations and the frozen CLTS core are available directly at
runtime. Rebuilding them requires the accepted external dataset. Package
installation and data acquisition are explicit development steps; ordinary
imports and commands use the resources already present.

## Library ownership

`ipakit.extraction.mfa.build(source: Path)` validates local MFA metadata and
returns a `BuildResult` containing repository-relative artifact paths and bytes.
The caller controls file publication. `result.stale(root)` compares those artifacts and the
producer's explicitly owned file patterns against a destination. The result's
`SourceIdentity` reuses structured `SourceMetadata` and records consumed hashes.
The update script delegates parsing and feature mapping to this producer.

`ipakit.extraction.mfa.require_pin(source, dictionary=True)` additionally checks
the full en-US dictionary used by inventory cards. Metadata-only generation
uses the default `dictionary=False` and consumes metadata only.
Missing data, a wrong revision and changed content raise catchable
`SourceMissingError`, `SourceVersionError` and `SourceContentError`, respectively,
all subclasses of `SourceError`/`ValueError`, with distinct `.code` values.
This library path and its MFA producer use the core dependencies.

The existing `scripts/mfa_vocabularies.py generate|check` commands delegate to
this library. `scripts/inventory_cards.py` uses the same validator and the
existing dictionary/inventory APIs. MFA's original curated exceptions, license
checks and generated artifact bytes remain unchanged.
Curated source-specific reductions, notes and examples are declared in
`ipakit/data/mfa-curation.json`. The builder checks
them against the selected upstream inventories before rendering.

`ipakit.clts.build_core(source)` returns the same shared result contract for the
approved frozen CLTS core domain. `source_policy()` owns its accepted revision,
input hashes, resolver requirements and source attribution; `validate_source()`
checks the local Git checkout without importing pyclts. Building/checking the
artifact additionally requires the exact resolver version and contents accepted
by that policy. Missing pyclts reports `resolver-unavailable`; wrong versions and
changed contents retain their distinct source errors. Install the resolver
explicitly before building. CLTS support here covers the frozen core domain;
productive and full semantic import are outside its scope.

## Developer orchestration

`ipakit.extraction.phoible.build(source)` builds the separately licensed frozen
PHOIBLE source aggregate through the same `BuildResult`/`SourceIdentity`
contract. `ipakit.phoible_source.source_policy()` owns its single revision/hash
policy. Checkout revisions and every consumed data/notice hash are validated;
archives require the same exact content. The builder preserves original source
bytes in deterministic gzip transport, without parsing or filtering inventories.
Its adapter supports status/fetch/build/check/discover with the same managed
per-revision cache and read-only existing-destination behavior. See
[PHOIBLE source scope and notices](phoible.md).

Run these from a source checkout:

```sh
python scripts/dev_sources.py status all
python scripts/dev_sources.py fetch mfa
python scripts/dev_sources.py check mfa
python scripts/dev_sources.py build mfa
python scripts/dev_sources.py discover mfa
python scripts/dev_sources.py fetch clts
python scripts/dev_sources.py check clts
python scripts/dev_sources.py build mfa clts
python scripts/dev_sources.py discover clts
```

`fetch` and `discover` explicitly authorize network access. `fetch` uses
`~/.cache/ipakit/sources/<producer>/<accepted-revision>` by default; `--cache DIR`
changes its cache parent. It populates only a new directory and validates
consumed bytes after acquisition. Existing sources are validated without reset,
checkout, pull or repair. Failed acquisition leaves its directory available for
inspection; use a new cache location after investigating it. Symlinked
acquisition destinations are refused. Package installation and global upgrades
remain manual development steps. MFA retains its sparse dictionary acquisition; CLTS sparse
paths are derived from every input in its packaged source policy, including
source-credit files. Both use the same acquisition and publication machinery.

For offline operations, `--source PATH` reads an existing source (MFA accepts a
clone or validated archive; CLTS requires a Git checkout). It requires exactly
one selected producer and an operation other than `fetch`. Multi-producer
commands, including `all`, use separate revision caches for each provider's
inputs. `--output PATH` selects the build/check destination.
`build` writes producer-owned artifacts and removes stray files only within its
declared output patterns, matching the existing MFA generator's ownership.
Use a staging output directory when reviewing candidate content. Publication
refuses symbolic-link artifact paths and publishes files individually, without
a multi-file transaction.

`discover` queries upstream HEAD without fetching objects or changing the
accepted revision/digests. A different HEAD is a candidate requiring review of
ancestry, compatibility, release status and license approval. Reviewing and
repinning source content follows the normal code/data change process. The accepted
revision and content digests are owned by the library producer; scripts import
them. Dependency support ranges remain in `pyproject.toml`; the producer's
revision and digests identify the resolved input content.

## Honest partial support

Every command emits JSON with the requested operation, each source's status,
expected/observed identity where verified, diagnostics and an aggregate
`complete` flag. `status` succeeds at reporting missing sources but leaves
`complete: false`. Requested unsupported operations, missing inputs and errors
make build/check/fetch/discover exit nonzero. `check` also exits nonzero for
artifact differences; a successful `build` may report `changed`.

Lifecycle adapters currently support **MFA, the frozen CLTS core and PHOIBLE's
accepted source aggregate**. `all` includes explicit unsupported
entries for the census's eSpeak, Panphon, ICU, inventory-card, CMU-dictionary,
ipa-dict, XRMB and internal-generator paths. Those entries record
operation support; inventories and dependencies retain their existing registries.
Existing tools for these sources still work independently. A CLTS `status`
result of `available` validates source inputs; use `check` to verify resolver
installation and artifact freshness too. Supporting
test/lint packages and the optional PocketSphinx runtime engine are not inventory
sources to regenerate.

Redistribution requires the provider-specific accepted licenses, provenance,
source notices and release review. SPDX syntax validation checks the identifier;
license compatibility requires a separate decision. The runner follows the
existing source-version and licensing policies.
