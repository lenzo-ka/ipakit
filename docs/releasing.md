# Releasing ipakit

*Internal maintainer note — not part of the user-facing docs or the published
package.*

Publishing is automated via `.github/workflows/publish.yml` using **PyPI Trusted
Publishing (OIDC)** — no API tokens. You cut a GitHub Release; the workflow
builds, checks, and uploads. This doc is the operator checklist.

---

## One-time setup (before the first release)

Do these once. The automation cannot run until they exist.

### 1. GitHub repository

- Create/confirm the repo at `github.com/lenzo-ka/ipakit` (the `[project.urls]`
  in `pyproject.toml` already point there).
- Push `main`.

### 2. PyPI trusted publisher  ⚠️ pending-publisher gotcha

`ipakit` does **not** exist on PyPI yet (first release). You cannot attach a
trusted publisher to a project that doesn't exist, so use a **pending
publisher**:

- PyPI → account → **Publishing** → *Add a pending publisher*:
  - PyPI Project Name: `ipakit`
  - Owner: `lenzo-ka`   Repository: `ipakit`
  - Workflow name: `publish.yml`
  - Environment name: `pypi`

After the first successful upload the pending publisher becomes a normal one
automatically.

### 3. GitHub Environment

Repo → **Settings → Environments** → create the `pypi` environment (the publish
job references it; the OIDC identity is scoped to it).

---

## Cutting a release

1. **Set the version** — single source of truth is `ipakit/__init__.py`:
   ```python
   __version__ = "X.Y.Z"
   ```
   (`pyproject.toml` reads it dynamically; do not edit a version there.)

2. **Update `CHANGELOG.md`** — move the `## [Unreleased]` entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading (and fix the compare/tag links at the
   bottom). The changelog currently ships as an empty skeleton.

3. **Verify locally** (all must be clean):
   ```bash
   pytest -q && mypy ipakit && ruff check . && black --check .
   python -m build && twine check dist/*
   python -c "import importlib.metadata as m, ipakit; \
     assert m.version('ipakit') == ipakit.__version__"
   rm -rf dist build
   ```

4. **Commit + tag**:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag vX.Y.Z          # tag must equal ipakit.__version__ with a leading v
   git push && git push --tags
   ```

5. **Publish** — create a **GitHub Release** for tag `vX.Y.Z` (Releases → Draft
   a new release). Publishing the release triggers `publish.yml`, which:
   - builds sdist + wheel,
   - runs `twine check`,
   - **asserts the tag matches `ipakit.__version__`** (fails the release
     otherwise),
   - uploads to PyPI via OIDC.

6. **Verify**: `pip install ipakit==X.Y.Z` and `python -c "import ipakit; print(ipakit.__version__)"`.

---

## Notes / gotchas

- **Tag ↔ version**: the release step compares `${TAG#v}` against
  `ipakit.__version__`. A mismatch fails the build — bump the version *and*
  tag together.
- **Data files**: `to-cmu`/xsampa/phonemap XML and `confusion.json` ship via
  `[tool.setuptools.package-data]`. Confirm they're in the sdist:
  `tar -tzf dist/*.tar.gz | grep -E 'data/'`.
- **PEP 639 license**: `license = "BSD-2-Clause"` requires `setuptools>=77` (already the
  build-system floor). Don't lower it.
- **CI must be green first**: `ci.yml` (lint / test 3.11–3.13 / ICU guards) runs
  on the push; only cut the release once it passes.
- **Dev-only ICU**: the X-SAMPA table guard needs `icukit-pyicu` (`import icu`),
  pulled by `.[dev]`/`.[icu]` — never a runtime dependency.
- **Re-releases**: PyPI is immutable — you cannot overwrite `X.Y.Z`. If a build
  is bad, bump to `X.Y.Z+1` (or a post-release `X.Y.Z.postN`).
