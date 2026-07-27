# ipakit

[![CI](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml/badge.svg)](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ipakit.svg)](https://pypi.org/project/ipakit/)
[![Python versions](https://img.shields.io/pypi/pyversions/ipakit.svg)](https://pypi.org/project/ipakit/)
[![License: BSD 2-Clause](https://img.shields.io/badge/License-BSD_2--Clause-blue.svg)](LICENSE)

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
ipakit.distance("p", "b")       # small: differ only in voicing
ipakit.nearest_phones("p", n=3) # [(phone, distance), ...] closest first
ipakit.word_similarity("kæt", "kæd")   # near 1.0: a minimal pair

# Tokenize / normalize (tie-bar affricates, diphthongs)
ipakit.tokenize("t͡ʃe͜ɪnd͡ʒ")   # ['t͡ʃ', 'e͜ɪ', 'n', 'd͡ʒ']

# Structured segments (typed ties; see docs/ties.md)
seg = ipakit.parse_segment("t͡s͜a")     # one unit: fused onset + vowel, sequentially bound
seg.kind.value                          # 'chain'
seg.left.kind.value                     # 'affricate'
seg.right.to_ipa()                      # 'a'
seg.left_features()["manner"]           # 'affricate'  (edge feature reads)
ipakit.parse_segment("u͜i").bag()["backness"]  # ('back', 'front')

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
ipakit.distance("p", "b")             # raw structural distance
ipakit.normalized_distance("p", "b")  # its percentile within the bundled inventory
ipakit.confusability("p", "b")        # the complement of normalized_distance
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
eng.distance("p", "b")                       # percentile within THIS inventory, not the full one
eng.nearest("p", n=3)                        # nearest phones drawn from this inventory
eng.word_similarity("kæt", "kæd")
eng.is_similar("kæt", "kæd", threshold=0.8)  # True
```

Distances are **structural**: two segments are close when they are made similarly — same articulator, similar position in the vocal tract, similar constriction. That correlates with perceptual confusability but does not model it. [docs/distance.md](docs/distance.md) documents the representation, the comparison, and what the numbers do and do not mean.

`distance_model()` also accepts `gamma` (power transform to push dissimilar
pairs apart), `sub_mode="di"` (delete+insert substitution cost for word
alignment), and `threshold` / `max_length_ratio` defaults for `is_similar`. The
raw pairwise matrix ships as `ipakit/data/confusion.json`; per-inventory models
reuse it and only re-slice the percentile distribution.

## Conventions

- **Stress is placed on the vowel** (the syllable nucleus), not the syllable
  onset: `to_ipa(["K", "AE1", "T"])` → `kˈæt`. Syllabification is preserved
  across round trips (`W AO1 T ER0` ↔ `wˈɔtɚ`).
- **Ties are typed** (house convention; see [docs/ties.md](docs/ties.md)): the over-tie fuses constituents into one timing slot (affricates and double articulations: `t͡ʃ`, `k͡p`), the under-tie binds a sequence into one unit (diphthongs, morae: `e͜ɪ`, `a͜ɪ͜ə`), and the over-tie binds tighter in mixed chains (`t͡s͜a`). The glyph is authoritative everywhere; text written in other conventions (where the glyphs are typographic variants) imports explicitly via `ipakit.from_wild`. Tie *presence* is contrastive: `t͡s` is one segment, `ts` is a cluster.
Exact values are pinned in the test suite rather than quoted here: a change that moves them fails CI, where prose would go stale in silence. See [docs/distance.md](docs/distance.md) for the model.

- **Round-trip guarantee (X-SAMPA only):** IPA written in these conventions
  round-trips through X-SAMPA (`ipa → xsampa → ipa`), **up to tie sense**:
  X-SAMPA has a single tie encoding, so the under-tie projects onto the
  over-tie at the boundary and round trips return canonical over-tie
  spellings (`t͜s → t_s → t͡s`); the sequential/simultaneous distinction
  survives only in IPA. The other exceptions are `b͡v`, `t͡θ`, and `ŋ͡m`,
  where the X-SAMPA tie encoding `_` collides with a diacritic/tone encoding
  (`_v`, `_T`, `_m`) — an inherent X-SAMPA ambiguity that ICU shares. The CMU, TIMIT, and Kirshenbaum mappings are lossy (they collapse IPA
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
ipakit distance pair p b             # Raw structural distance
ipakit distance confusability p b    # Inventory-relative confusability
ipakit distance word kæt kæd         # Word similarity
```

The `distance confusability`/`word` commands use the distribution-aware model;
scope them to a reference inventory with `--phoneset FILE` (one phone per line).

Most commands accept `--format json` (or `-j`) for machine-readable output.
Run `ipakit`, `ipakit <group>`, or append `help`/`-h` anywhere for usage.

## Development

```bash
pip install -e ".[dev]"   # or ".[test]" / ".[lint]" for a lean subset
pre-commit install        # black, ruff, mypy --strict, hygiene hooks
pytest                    # unit tests + docstring examples
```

CI (`.github/workflows/ci.yml`) mirrors these on every push/PR across Python
3.11–3.13, and validates the committed derived artifacts (the IPA ↔ X-SAMPA
table and the phone-distance matrix) against their generators in `scripts/`.

## License

BSD 2-Clause — see [LICENSE](LICENSE).
