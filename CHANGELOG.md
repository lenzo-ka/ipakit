# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
