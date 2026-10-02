# Lane F documentation report

## Result

Lane F is complete in `/Users/lenzo/.claude/worktrees/ipakit/xinv-f-docs` at base commit `1c80103fce1bc342c79bbc9c49002fa9f8643dec`. The worktree has the eight intended modified tracked files and no new repository files. No git write was performed.

The inventory documentation now contains canonical pairwise and N-way summary reports generated from the report objects. The examples use the shipped CMUdict and TIMIT declarations plus MFA English US. They do not read live PHOIBLE, CLTS, or eSpeak data. No optional-source example was added, so there is no environment-dependent availability result in the generated examples.

## Survey and reuse

Before implementation, I read the authoritative cross-inventory report and the lane A through E briefs, reports, and review records. I reused:

- `scripts/inventory_cards.py` and its source-to-generated-document byte check;
- the existing `InventoryComparisonReport.to_json()` canonical serializer;
- the shipped registry inventory views and their source metadata;
- the existing `make check` documentation checks, including tutorial generation, `docexamples.py`, and `docquotes.py`;
- the existing derived-artifact baseline and manifest machinery.

New work is limited to report-example assembly inside the inventory-card generator, a single source marker, prose describing the report and coverage contract, schema/identity assertions for both generated JSON blocks, the regenerated documentation and derived-artifact receipt, and one terse changelog entry. No separate documentation generator was introduced.

## Documentation behavior

`docs/inventories.src.md` now explains that the schema is experimental and versioned, distinguishes pairwise from N-way reports, and names these coverage measures with their denominators and applicability:

- `overlap`: all-input intersection over the union;
- `readable/admitted`: present, house-readable declared members over all declared members, retaining every admission status bucket in the denominator;
- `reviewed-mapped`: reviewed mappings over present and unresolved members of views carrying mapping authority;
- `exact representability`: exact target-membership hits over directed source-symbol opportunities between distinct inputs;
- `thresholded-nearest`: caller-threshold-accepted symbols over the same directed opportunities, not applicable without a threshold.

The generated JSON repeats each definition, numerator, denominator, status buckets, and applicability. Machine result values occur only in generated report output, not hand-maintained prose.

`docs/distance.md` no longer duplicates a large hand-copied comparison result or interprets those copied rows. It links to the generator-owned reports and retains a runnable CMUdict/TIMIT API and CLI example. Its TSV description was also aligned with the typed records emitted after the matrix.

The examples are fixed by the shipped declarations and canonical report serializer. The CMUdict declaration's own upstream provenance says `unpinned`, so the prose deliberately does not make a stronger upstream-pinning claim than the data supports.

## Tests and receipts

`tests/test_inventory_cards.py` parses both fenced JSON examples, checks the experimental schema identifier and version, recomputes each canonical identity fingerprint, checks the selected inventory names, and asserts that all five coverage records carry numerator, denominator, definition, and status-bucket fields. It also prevents a machine result such as `union_count` from being copied into the hand-written source.

Focused validation passed:

```text
.venv/bin/python -m pytest -n 0 tests/test_inventory_cards.py tests/test_inventory_comparison_nway.py
14 passed in 1.35s
```

Additional checks passed before the full gate: inventory-card byte comparison, lint, documentation examples, quotation checks, derived-artifact verification, and `git diff --check`. The regenerated `tests/tiergraph/baselines/derived-artifacts.json` changes only the byte count and SHA-256 for `docs/inventories.md`; its manifest digest was regenerated accordingly.

## Required gate

Executed exactly as required:

```sh
MFA_MODELS=/Users/lenzo/dev/lenzo/ipakit-refs/mfa-models PYTHON=.venv/bin/python nice -n 19 make check
```

Result: exit 0. The sandbox reported `nice: setpriority: Operation not permitted`, but the command continued actively and did not stall. The gate passed lint, the normal test suite, all invariants, generated-data checks, inventory-card byte comparison, tutorial checks, 471 documentation values, and 39 locally checkable quotations. No full slow suite was run.

Gate tail:

```text
39 quotations checked against the document each one cites
476 attributed to something this cannot read -- a book, a handout, a URL, or nothing -- and left alone
every quotation is in the document it cites
gate subject [executed]: ipakit_path=/Users/lenzo/.claude/worktrees/ipakit/xinv-f-docs/ipakit/__init__.py; ipakit_commit=1c80103fce1bc342c79bbc9c49002fa9f8643dec; ipakit_dirty=yes; tiergraph_path=/Users/lenzo/.claude/worktrees/ipakit/xinv-f-docs/.venv/lib/python3.13/site-packages/tiergraph/__init__.py; tiergraph_version=0.5.0
```

Final tracked status:

```text
 M CHANGELOG.md
 M docs/distance.md
 M docs/inventories.md
 M docs/inventories.src.md
 M scripts/inventory_cards.py
 M tests/test_inventory_cards.py
 M tests/tiergraph/baselines/MANIFEST.sha256
 M tests/tiergraph/baselines/derived-artifacts.json
```

Final scope checks found no reference-library path or `MFA_MODELS` value in the repository diff, and `git diff --check` exited 0.
