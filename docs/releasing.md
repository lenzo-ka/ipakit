# Releasing ipakit

*Internal maintainer note — not part of the user-facing docs.*

Publishing uses **PyPI Trusted Publishing** (OIDC) via
`.github/workflows/publish.yml` — no API tokens or stored secrets.

## One-time setup

1. **PyPI** → project `ipakit` → *Publishing* → add a Trusted Publisher: owner
   `lenzo-ka`, repository `ipakit`, workflow `publish.yml`, environment `pypi`.
   For the very first upload, add it as a *pending* publisher (the project does
   not exist on PyPI yet, so a normal publisher can't be attached).
2. **TestPyPI** → same, with environment `testpypi`.
3. **GitHub** → *Settings → Environments* → create `pypi` and `testpypi`
   (optionally require a reviewer to approve `pypi` deployments).

## Cutting a release

1. Bump the version. The single source of truth is `ipakit/__init__.py`
   (`__version__ = "X.Y.Z"`); `pyproject.toml` reads it dynamically, so do **not**
   edit a version there. Commit the bump.
2. Move the `## [Unreleased]` entries in `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading.
3. *(Optional)* Actions → **Publish** → **Run workflow** → `testpypi` to
   dry-run the build and upload.
4. Create a GitHub Release with tag `vX.Y.Z` (the tag must equal
   `ipakit.__version__` with a leading `v`). Publishing the release triggers the
   workflow, which builds the sdist + wheel, runs `twine check`, asserts the tag
   matches the version, and uploads to PyPI via OIDC.

## Notes

- **CI must be green first**: `ci.yml` (lint / test 3.11–3.13 / ICU guards) runs
  on the push; only cut the release once it passes.
- **PyPI is immutable**: you cannot overwrite `X.Y.Z`. If a build is bad, bump to
  `X.Y.Z+1` (or a post-release `X.Y.Z.postN`).
