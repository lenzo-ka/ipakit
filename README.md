# ipakit

[![CI](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml/badge.svg)](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ipakit.svg)](https://pypi.org/project/ipakit/)
[![Python versions](https://img.shields.io/pypi/pyversions/ipakit.svg)](https://pypi.org/project/ipakit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A pure-Python IPA (International Phonetic Alphabet) phonetic toolkit:
phonetic features, distances, natural classes, and conversion between IPA and
CMU ARPABET, X-SAMPA, Kirshenbaum, and TIMIT notations.

- **Zero runtime dependencies** — all phonetic data ships as XML in the package.
- **Typed** (`py.typed`, mypy-strict clean).
- **Both a library and a CLI** (`ipakit`).

## Install

```bash
pip install ipakit
```

For development (tests, linters, and the X-SAMPA table tooling):

```bash
pip install -e ".[dev]"
```

## Quick start (Python)

```python
import ipakit

# Phonetic features and descriptions
ipakit.describe("p")            # 'voiceless bilabial plosive'
ipakit.features("p")            # {'manner': 'plosive', 'place': 'bilabial', ...}

# Phonetic distance (0.0 identical … 1.0 maximally different)
ipakit.distance("p", "b")       # 0.043   (differ only in voicing)
ipakit.nearest_phones("p", n=3) # [('ɸ', 0.005), ('f', 0.008), ('p͡f', 0.008)]
ipakit.word_similarity("kæt", "kæd")   # 0.986

# Tokenize / normalize (tie-bar affricates, diphthongs)
ipakit.tokenize("t͡ʃe͡ɪnd͡ʒ")   # ['t͡ʃ', 'e͡ɪ', 'n', 'd͡ʒ']

# Validate
ipakit.validate_ipa("kæt")      # []  (valid)
ipakit.validate_ipa("k4t")      # [{'type': 'error', 'code': 'unknown_symbol', ...}]
```

### Conversions

```python
# CMU ARPABET
ipakit.to_cmu("ˈkæt")             # ['K', 'AE1', 'T']
ipakit.to_ipa(["K", "AE1", "T"])  # 'kˈæt'

# X-SAMPA (ASCII)
ipakit.ipa_to_xsampa("t͡ʃ")        # 't_S'
ipakit.xsampa_to_ipa("t_S")        # 't͡ʃ'

# Kirshenbaum / TIMIT
ipakit.to_kirshenbaum("kæt")       # 'k&t'
ipakit.to_timit("kæt")             # ['k', 'ae', 't']

# Features straight from a non-IPA symbol (list of per-segment dicts)
ipakit.features_from_xsampa("t_S")  # [{'manner': 'affricate', 'place': 'postalveolar', ...}]
ipakit.features_from_cmu("K")       # [{'manner': 'plosive', 'place': 'velar', ...}]
```

By default converters skip symbols they can't map. Pass `strict=True` to any of
them to raise `ValueError` on unconvertible input instead:

```python
ipakit.to_cmu("k4t")                # ['K', 'T']  (the '4' is skipped)
ipakit.to_cmu("k4t", strict=True)   # ValueError: Cannot convert to CMU ARPABET: ...
```

### Distribution-aware distance

`distance()` is the **raw feature metric** — an absolute, inventory-independent
mean over phonetic features (so `distance("p", "b")` is always `0.043`). Raw
distances bunch up in a narrow band, which makes fixed thresholds hard to pick.
`normalized_distance()` renormalizes a raw distance to its **percentile** within
the bundled IPA inventory's pairwise distribution, spreading values across
`[0, 1]`:

```python
ipakit.distance("p", "b")             # 0.043   raw feature distance
ipakit.normalized_distance("p", "b")  # 0.155   percentile within bundled IPA
ipakit.normalized_distance("p", "a")  # 0.602
ipakit.confusability("p", "b")        # 0.845   complement of normalized_distance
```

For a model over a chosen reference inventory — percentiles are **relative** to
it and not comparable across inventories — use `distance_model()`:

```python
from ipakit import Phoneset

eng = ipakit.distance_model(
    Phoneset.from_list(
        ["p", "b", "t", "d", "k", "ɡ", "s", "z", "m", "n", "l", "ɹ", "a", "i", "u"],
        name="english",
    )
)
eng.distance("p", "b")                       # 0.267   percentile within this 15-phone set
eng.nearest("p", n=3)                        # [('t', 0.048), ('s', 0.086), ('k', 0.21)]
eng.word_similarity("kæt", "kæd")            # 0.956
eng.is_similar("kæt", "kæd", threshold=0.8)  # True
```

`distance_model()` also accepts `gamma` (power transform to push dissimilar
pairs apart), `sub_mode="di"` (delete+insert substitution cost for word
alignment), and `threshold` / `max_length_ratio` defaults for `is_similar`. The
raw pairwise matrix ships as `ipakit/data/confusion.json`; per-inventory models
reuse it and only re-slice the percentile distribution.

## Conventions

- **Stress is placed on the vowel** (the syllable nucleus), not the syllable
  onset: `to_ipa(["K", "AE1", "T"])` → `kˈæt`. Syllabification is preserved
  across round trips (`W AO1 T ER0` ↔ `wˈɔtɚ`).
- **Affricates and diphthongs use the tie bar** (`t͡ʃ`, `e͡ɪ`).
- **Round-trip guarantee (X-SAMPA only):** IPA written in these conventions
  round-trips through X-SAMPA (`ipa → xsampa → ipa`). The only exceptions are
  `b͡v` and `t͡θ`, where the X-SAMPA tie encoding `_` collides with a
  diacritic/tone encoding (`_v`, `_T`) — an inherent X-SAMPA ambiguity that ICU
  shares. The CMU, TIMIT, and Kirshenbaum mappings are lossy (they collapse IPA
  distinctions) and carry no round-trip guarantee.

## CLI

```text
ipakit features p                    # Get features for 'p'
ipakit describe p                    # "voiceless bilabial plosive"
ipakit convert to-cmu "kˈæt"         # IPA to CMU: K AE1 T (stress on the vowel)
ipakit convert to-ipa K AE1 T        # CMU to IPA: kˈæt
ipakit convert to-xsampa "t͡ʃ"        # IPA to X-SAMPA: t_S
ipakit query match plosive bilabial  # Find phones by feature
ipakit analysis natural-class p t k  # Shared features of a set
ipakit analysis minimal-pairs p      # Find similar phones
ipakit distance pair p b             # Raw feature distance: ~0.04
ipakit distance confusability p b    # Inventory-relative: 0.8454
ipakit distance word kæt kæd         # Word similarity: 0.9742
```

The `distance confusability`/`word` commands use the distribution-aware model;
scope them to a reference inventory with `--phoneset FILE` (one phone per line).

Most commands accept `--format json` (or `-j`) for machine-readable output.
Run `ipakit`, `ipakit <group>`, or append `help`/`-h` anywhere for usage.

## Development

```bash
pip install -e ".[dev]"
pre-commit install        # black, ruff, mypy --strict, hygiene hooks
pytest                    # unit tests + docstring examples (--doctest-modules)
```

CI (`.github/workflows/ci.yml`) mirrors these checks on every push/PR: `ruff` +
`black --check` + `mypy --strict` (the `lint` extra), `pytest` across Python
3.11–3.13 (the `test` extra), and the two derived-artifact guards below (the
`dev` extra, which adds ICU). Install a lean subset with `pip install -e
".[test]"` or `".[lint]"`.

The IPA ↔ X-SAMPA table (`ipakit/data/phonemaps/xsampa.xml`) is reproducible
from ICU transliteration plus a small set of curated overrides. `icukit-pyicu`
is a **dev-only** dependency (never imported at runtime):

```bash
python scripts/xsampa_table.py validate   # CI guard: shipped table == derived
python scripts/xsampa_table.py generate   # print the derived table
```

The global phone distance matrix (`ipakit/data/confusion.json`) is a committed
cache derived from `ipa.xml` plus the distance metric — regenerate it whenever
either changes. The test suite guards it against drift (pure stdlib, no dev dep):

```bash
python scripts/confusion.py validate         # shipped matrix == derived
python scripts/confusion.py generate --write # regenerate after a metric/data change
```

## Releasing

Publishing uses **PyPI Trusted Publishing** (OIDC) via
`.github/workflows/publish.yml` — no API tokens or stored secrets.

One-time setup:

1. **PyPI** → project `ipakit` → *Publishing* → add a Trusted Publisher: owner
   `lenzo-ka`, repository `ipakit`, workflow `publish.yml`, environment `pypi`.
   For the very first upload, add it as a *pending* publisher.
2. **TestPyPI** → same, with environment `testpypi`.
3. **GitHub** → *Settings → Environments* → create `pypi` and `testpypi`
   (optionally require a reviewer to approve `pypi` deployments).

To cut a release:

1. Bump `version` in `pyproject.toml` and commit.
2. *(Optional)* Actions → **Publish** → **Run workflow** → `testpypi` to
   dry-run the build and upload.
3. Create a GitHub Release with tag `vX.Y.Z` (matching `pyproject.toml`). The
   workflow builds the sdist + wheel, runs `twine check`, verifies the tag
   matches the version, and publishes to PyPI.

## License

MIT — see [LICENSE](LICENSE).
