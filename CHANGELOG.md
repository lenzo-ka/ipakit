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
  IPA↔X-SAMPA round-trip guarantee. `from_cmu` is the canonical CMU→IPA name
  (`to_ipa` is a kept alias); the generic `ipa_to_phonemap` / `phonemap_to_ipa`
  entry points are public.
- Analysis and validation helpers (`describe`, `validate_ipa`, minimal pairs,
  nearest phones). `IPAFeatures.parse(..., strict=True)` raises on unmatched
  characters instead of dropping them silently.
- A `ipakit` command-line interface with grouped subcommands. Every `convert`
  subcommand accepts `--format`/`-j`; the eight real converters accept
  `--strict` (fail on unconvertible symbols, exit 1). Flag names are explicit
  (`features --no-lookalikes`, `analysis validate --warnings-as-errors`, with
  `--strict` kept as an alias), and `data` aliases the `analyze` group.
- Reproducible derived data (`xsampa.xml`, `confusion.json`) with
  generate/validate scripts and CI drift guards.

### Correctness & robustness

- External TSV confusion matrices treat a genuine `0` as a real value (averaged
  when both directions are present) rather than as "missing".
- A lone or dangling tie bar is not accepted as a phone by the tokenizer, so
  `validate_ipa` reports it (`malformed_tie`); well-formed composites (`t͡ʃ`)
  are unaffected.
- `DistanceModel` output files opened with `-o` are flushed/closed; ordinal
  `value_distance` guards the single-value (division-by-zero) case.
- Hot paths optimized without changing results: `word_distance` memoizes
  substitution costs, `pairwise_distances` skips the redundant half-grid,
  ordinal `value_distance` is O(1), and hierarchy building composes each phone's
  features once.

### Packaging & tooling

- `py.typed` shipped; `mypy --strict` clean. Version single-sourced from
  `ipakit.__version__`; build-system floor `setuptools>=77` for the PEP 639
  license form.
- CI across Python 3.11–3.13; docstring examples enforced via
  `--doctest-modules`.
- PyPI publishing via OIDC Trusted Publishing.

[Unreleased]: https://github.com/lenzo-ka/ipakit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lenzo-ka/ipakit/releases/tag/v0.1.0
