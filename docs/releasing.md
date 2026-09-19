# Releasing ipakit

*Maintainer checklist, included in the source distribution.*

Publishing is automated via `.github/workflows/publish.yml` using **PyPI Trusted
Publishing (OIDC)** — no API tokens. You cut a GitHub Release; the workflow
builds, checks, and uploads. This doc is the operator checklist.

---

## Publishing setup

GitHub and PyPI publication have already succeeded, including version 0.2.0 on
2026-09-07. The first-release pending-publisher instructions are no longer the
normal release path. Recheck these settings if repository ownership, workflows
or environments change; past publication does not verify current settings.

### 1. GitHub repository

- Confirm the repo at `github.com/lenzo-ka/ipakit` (the `[project.urls]`
  in `pyproject.toml` already point there).
- Push `main`.

### 2. PyPI trusted publisher

`ipakit` exists on PyPI. Its trusted-publishing identity must match:

- PyPI project → **Publishing**:
  - PyPI Project Name: `ipakit`
  - Owner: `lenzo-ka`   Repository: `ipakit`
  - Workflow name: `publish.yml`
  - Environment name: `pypi`

Do not create a new pending publisher for an already-published project.

### 3. GitHub Environment

Repo → **Settings → Environments** → confirm the `pypi` environment (the publish
job references it; the OIDC identity is scoped to it).

---

## Cutting a release

Freeze the intended release scope first. Only landed, verified features belong
in its changelog. Qualify dependency changes against installed published packages;
a successful source-checkout test is not proof that a dependency release ships
the required API. Inspect package, hook and contract-test dependency declarations
together. Use a separate clean release worktree and preserve original source-data
bytes, provenance and license notices when regenerating derived artifacts.

1. **Set the version** — single source of truth is `ipakit/__init__.py`:
   ```python
   __version__ = "X.Y.Z"
   ```
   (`pyproject.toml` reads it dynamically; do not edit a version there.)

2. **Update `CHANGELOG.md`** — move the `## [Unreleased]` entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading (and fix the compare/tag links at the
   bottom).

3. **Regenerate what carries the version.** `tests/tiergraph/baselines/derived-artifacts.json`
   records the version it was captured under, so bumping step 1 makes it stale
   and the manifest digest covering it stale with it:
   ```bash
   PYTHONHASHSEED=0 python scripts/tiergraph_capture.py artifacts
   ```
   Then update only that file's line in `tests/tiergraph/baselines/MANIFEST.sha256`.
   Do **not** run `tiergraph_capture.py manifest` here: it globs the gitignored
   `captures/` directory, so a manifest regenerated in a working checkout gains
   entries a clean clone cannot reproduce.

   A digest mismatch on `captures/confusion-derived.json` means a stale local
   capture, not a regression: regenerate it with `PYTHONHASHSEED=0` and compare
   against the committed value before believing the message. Working in the main
   checkout is what exposes you to this; the captures directory is untracked and
   shared across everything you have run there.

4. **Verify locally** (all must be clean):
   ```bash
   make check          # use the release worktree and required pinned live sources
   python scripts/check_hrefs.py   # the shipped hrefs still point at live articles
   python -m build --outdir /path/to/fresh/release-artifacts
   python -m twine check /path/to/fresh/release-artifacts/*
   ```

Run the gate and build sequentially in a shared source worktree. An sdist build
creates a temporary staging tree that recursive test collection can discover;
wait for the gate to finish before starting the build.

`check_hrefs.py` checks the release's Wikipedia links over the network. It runs
separately from the offline gate and exits 2 when the API is unreachable.

Read actual gate conclusions and skipped populations. The default test selection
and the full slow suite are different scopes; a skipped check is not a pass.
Install the built wheel in a fresh environment, then verify distribution metadata
equals `ipakit.__version__`, the installed dependency version is correct, and
imports resolve inside that environment rather than a source checkout. Exercise
resource lookup and representative CLI commands there. Inspect both archives:
filenames, metadata, expected resources, full source-test support and notices.
Retain the verified artifacts or remove only the exact inspected output directory;
do not erase a shared build directory or stage unrelated files.

Check collection and fixture-dependent tests from the unpacked source archive
without a checkout on `PYTHONPATH`. Tests, scripts and documentation support files
must travel with it. Git-provenance gates still require a real checkout: the
source archives omit `.git` by design.

5. **Commit, land on green, then tag**:
   ```bash
   git status --porcelain
   ```

Commit only the explicit release paths when they have changed; do not force an
empty commit when a release-preparation PR already carries the complete change.
Require the reviewed local gate and applicable exact-head CI to pass before
landing. Confirm the resulting main commit and its version before creating and
pushing only the intended `vX.Y.Z` tag. Do not push unrelated local tags. Tagging
and publication require release authorization, not merely preparation approval.

6. **Publish** — publish a **GitHub Release** for tag `vX.Y.Z` (Releases → Draft
   a new release). Publishing the release triggers `publish.yml`, which:
   - builds sdist + wheel,
   - runs `twine check`,
   - **asserts the tag matches `ipakit.__version__`** (fails the release
     otherwise),
   - uploads to PyPI via OIDC.

7. **Verify**: `pip install ipakit==X.Y.Z` and `python -c "import ipakit; print(ipakit.__version__)"`.

---

## Notes / gotchas

- **Tag ↔ version**: the release step compares `${TAG#v}` against
  `ipakit.__version__`. A mismatch fails the build — bump the version *and*
  tag together.
- **Data files and licenses**: inspect the source-derived inventory census in
  the actual wheel/sdist, not merely whether a `data/` directory exists. Include
  bridge declarations, canonical Panphon XML, finite CLTS artifacts and PHOIBLE
  source resources with their hashes and separately scoped notices. The code's
  BSD license does not relicense third-party data. Preserve the precise Panphon
  and PHOIBLE large-file and verbatim-notice hook exceptions.
- **Source distribution**: `MANIFEST.in` includes `CHANGELOG.md`, Makefile,
  conftest, tests, scripts and documentation. This checklist itself ships there;
  do not describe the sdist as package-only. The wheel has its separately declared
  package resources. Use the packaging tests and inspect both actual archives.
- **PEP 639 license**: this project's build configuration requires
  `setuptools>=84.0.0` (already the build-system floor). Don't lower it.

  ```python
  import tomllib
  from pathlib import Path

  build_requires = tomllib.loads(Path("pyproject.toml").read_text())["build-system"]["requires"]
  build_requires  # ['setuptools>=84.0.0']
  ```
- **CI must be green first**: `ci.yml` (lint / test 3.12–3.13 / ICU guards) runs
  on the push; only cut the release once it passes.
- **Dev-only ICU**: the X-SAMPA table guard needs `icukit-pyicu` (`import icu`),
  pulled by `.[dev]`/`.[icu]` — never a runtime dependency.
- **Re-releases**: PyPI is immutable — you cannot overwrite `X.Y.Z`. If a build
  is bad, bump to `X.Y.Z+1` (or a post-release `X.Y.Z.postN`).
