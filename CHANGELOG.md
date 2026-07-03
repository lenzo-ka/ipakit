# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `from_cmu` as the canonical CMU→IPA function name (`to_ipa` kept as an alias).
- Generic `ipa_to_phonemap` / `phonemap_to_ipa` are now part of the public API.
- CLI: every `convert` subcommand accepts `--format`/`-j`; the eight real
  converters accept `--strict` (fail on unconvertible symbols, exit 1).
- CLI: `data` alias for the `analyze` group.
- `IPAFeatures.parse(..., strict=True)` raises on unmatched characters instead
  of dropping them silently.

### Changed

- Packaging: version is single-sourced from `ipakit.__version__` (dynamic);
  build-system floor raised to `setuptools>=77` for the PEP 639 license form.
- CLI: clearer flag names — `features --no-lookalikes` and
  `analysis validate --warnings-as-errors` (old `--strict` spellings still work).

### Fixed

- External TSV confusion matrices: a genuine `0` is treated as a real value
  (averaged when both directions are present) rather than as "missing".
- `DistanceModel` output files opened with `-o` are now flushed/closed.
- Guard against a division-by-zero for a hypothetical single-value ordinal
  feature.

### Performance

- `word_distance` memoizes substitution costs per alignment; `pairwise_distances`
  skips the redundant half of the grid; ordinal `value_distance` is O(1);
  hierarchy building composes each phone's features once. All byte-identical.

## [0.1.0] - 2026-07-03

Initial public release.

### Added

- IPA feature model loaded from a data-driven inventory (`IPAFeatures`), with
  tokenization, feature lookup, natural-class queries, and hierarchy building.
- Phonetic distance: feature-based `distance` / `word_distance`, plus a
  distribution-aware `DistanceModel` separating an inventory-independent
  confusion matrix from an inventory-relative percentile CDF (`confusability`,
  `normalized_distance`, `is_similar`).
- Conversions between IPA and CMU/ARPAbet, X-SAMPA, TIMIT, and Kirshenbaum,
  with a consistent `strict=` error policy across all converters and a tested
  IPA↔X-SAMPA round-trip guarantee.
- Analysis and validation helpers (`describe`, `validate_ipa`, minimal pairs,
  nearest phones).
- A `ipakit` command-line interface with grouped subcommands.
- Reproducible derived data (`xsampa.xml`, `confusion.json`) with
  generate/validate scripts and CI drift guards.

### Packaging & tooling

- `py.typed` shipped; `mypy --strict` clean.
- CI across Python 3.11–3.13; docstring examples enforced via
  `--doctest-modules`.
- PyPI publishing via OIDC Trusted Publishing.

[Unreleased]: https://github.com/lenzo-ka/ipakit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lenzo-ka/ipakit/releases/tag/v0.1.0
