# ipakit

[![CI](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml/badge.svg)](https://github.com/lenzo-ka/ipakit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ipakit.svg)](https://pypi.org/project/ipakit/)
[![Python versions](https://img.shields.io/pypi/pyversions/ipakit.svg)](https://pypi.org/project/ipakit/)
[![License: BSD 2-Clause](https://img.shields.io/badge/License-BSD_2--Clause-blue.svg)](LICENSE)

ipakit is a framework for computing over structured symbolic phonetic
representations, and for reconciling the systems that describe speech. IPA is
its first vocabulary in that representation.

At the center is a timed, structured tier graph whose vocabulary and relations
come from declarations. IPA text, machine notations, feature databases,
dictionary pronunciations, aligner output, rewrite layers, and rendering views
meet there as distinct layers. Each bridge states what it
can preserve in each direction, carries provenance forward, and keeps competing
accounts as data. If two sources give a word different forms, the disagreement
remains available to query.

One grammar does the recognizing and the rewriting. A query is a rule without
the arrow, so the engine that answers “where does this match?” is the engine
that decides “what does this become?” Agreement variables, optional elements,
and bounded spans belong to that shared grammar.

Rules also have a calculus. Derivations retain enough evidence to replay;
optional rules enumerate their variants under an explicit cap; `derives()`
returns a witness, an exhaustive refusal, or a refusal qualified by work left
unexplored. Invertibility classifies each rule against the inventory the caller
declares while leaving the rule language whole.

The symbolic representation bottoms out in articulation. The tract geometry
that drives figures and animation has been measured against instrumental data,
with the instrument's blind spots left visible. The symbols check the geometry,
and the measurements check the symbolic claims; neither is a decorative view
of the other.

Corpora make collections part of the same computation. They store cited and
derived forms, expose structural queries at the shell, and test rule systems
against paired forms. That is also the substrate on which rule induction can
run; the inducer itself remains a separate concern.

The package uses tiergraph for graph navigation; its phonetic data and geometry
ship as declarations. It is typed, and the Python API and `ipakit` command expose the
same model. See [the canonical representation](docs/representation.md),
[corpus queries](docs/corpus.md), [rewrite rules](docs/rules.md), and the
[articulatory model](docs/tract-anatomy.md).

**New here? Start with the [tutorial](docs/tutorial.md)** — it is organized by task and shows the command line and the Python API side by side for each one. Every value on that page is produced by executing the call beside it.

## Documentation

- **[docs/tutorial.md](docs/tutorial.md)** — getting things done, from install to applying rule sets.
- **[docs/README.md](docs/README.md)** — index of every document, what it is for, and the order to read them.
- Reference: [representation.md](docs/representation.md) (the canonical graph), [ties.md](docs/ties.md) (the unit model), [form.md](docs/form.md) (compatibility projections), [rules.md](docs/rules.md) (the rewrite notation), [distance.md](docs/distance.md) (what the metric does and does not claim).

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

# Respell a phone under a feature change — feature algebra, realized back to IPA
ipakit.respell("t", voiced="+")     # 'd'   (voice a voiceless stop)
ipakit.respell("θ", voiced="+")     # 'ð'
ipakit.respell("p", place="velar")  # 'k'   (shift the place of articulation)
ipakit.respell("d", manner="nasal") # 'n'   (a stop becomes its nasal)
ipakit.respell("i", rounded="+")    # 'y'   (round a front vowel)
ipakit.respell("t", manner="nasal") # None  (unattested — no phone spells it)

# Phonetic distance (0.0 identical … 1.0 maximally different)
ipakit.distance("p", "b")       # small: differ only in voicing
ipakit.nearest_phones("p", n=3) # [(phone, distance), ...] closest first
ipakit.word_similarity("kæt", "kæd")   # near 1.0: a minimal pair
ipakit.sequence_distance(["k", "a", "t"], ["k", "æ", "t"])  # over pre-tokenized phones
ipakit.nearest_pronunciation("kat", ["kæt", "kɑt"])   # best-matching acceptable variant

# Tokenize / normalize (tie-bar affricates, diphthongs)
ipakit.tokenize("t͡ʃe͜ɪnd͡ʒ")   # ['t͡ʃ', 'e͜ɪ', 'n', 'd͡ʒ']

# Structured segments (typed ties; see docs/ties.md)
# `segment` gives one Segment, `segments` a list, `segmented` a spaced string
seg = ipakit.segment("t͡s͜a")     # one unit: fused onset + vowel, sequentially bound
seg.kind.value                          # 'chain'
seg.left.kind.value                     # 'affricate'
seg.right.to_ipa()                      # 'a'
seg.left_features()["manner"]           # 'affricate'  (edge feature reads)
ipakit.segment("u͜i").bag()["backness"]  # ('back', 'front')

# Search a transcription for a feature pattern (same query language as
# phones_matching, which searches the inventory), then join units back
ipakit.find("t͡ʃe͜ɪnd͡ʒ", ["vow"])          # [(1, Segment(e͜ɪ))]
ipakit.to_ipa(ipakit.segments("kæt"))     # 'kæt'
ipakit.feature_values("u͜i")["backness"]   # ('back', 'front') — features() is the scalar read

# Validate
ipakit.validate_ipa("kæt")      # []  (valid)
ipakit.validate_ipa("k4t")      # [{'type': 'error', 'code': 'unknown_symbol', ...}]
```

### Conversions

```python
# CMU ARPABET — one symbol per segment, so a tie decides where the segments are
ipakit.to_cmu("ˈkæt")             # ['K', 'AE1', 'T']
ipakit.from_cmu(["K", "AE1", "T"])  # 'kˈæt'
ipakit.to_cmu("nˈɔ͜ɪŋ")            # ['N', 'OY1', 'NG']   tied: one vowel
ipakit.to_cmu("nˈɔɪŋ")             # ['N', 'AO1', 'IH0', 'NG']   untied: two

# X-SAMPA (ASCII)
ipakit.to_xsampa("t͡ʃ")        # 't_S'
ipakit.from_xsampa("t_S")        # 't͡ʃ'

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
ipakit.to_cmu("k4t", strict=True)   # ValueError: Cannot convert to CMU ARPABET: unknown symbols ['4']
ipakit.to_cmu("ø", strict=True)     # ValueError: Cannot convert to CMU ARPABET: ...
```

Two layers report, and each speaks for itself: `4` is registered nowhere, which
the tokenizer says, and `ø` is well-formed IPA that ARPABET has no symbol for,
which the converter says.

Tokenization follows the same policy, and is never silent about it: a character
registered nowhere is dropped with a warning, and `strict=True` raises instead —
which is what makes `to_ipa(segments(x, strict=True)) == x` a guarantee rather
than a hope, for `x` written in house style. The qualifiers are both load-bearing.
Without `strict=True` the equation is over whatever survived the drop, which is
the thing the warning is telling you about; and a legacy ligature alias comes back
as the spelling it abbreviates, so `to_ipa(segments("ʧa", strict=True))` is `t͡ʃa`
rather than `ʧa` — the sound is preserved and the spelling is canonicalized, which
is what `from_wild` is for.

```python
ipakit.tokenize("kæQt")                # ['k', 'æ', 't'] + UserWarning naming 'Q'
ipakit.tokenize("kæQt", strict=True)   # ValueError: ... unknown symbols ['Q']
```

### Wild text comes in through one door

Default parsing is strict house style: ASCII stand-ins for IPA are read
literally, not silently rewritten, so `!` stays an exclamation mark rather than
becoming the click `ǃ`. `from_wild` is where wild spellings are read as IPA —
tie conventions and the keyboard alike:

```python
ipakit.is_valid_ipa("'gu:d")  # False -- ' g : are not IPA; validate_ipa names each
ipakit.from_wild("'gu:d")     # 'ˈɡuːd'  -- ' is primary stress, not the ejective ʼ
ipakit.from_wild("kæt!")      # 'kæt!'   -- ! could be a click or downstep; no guess made
```

See [docs/ties.md](docs/ties.md) for the full soft-read table and the reasoning
behind `'` and `!`.

### Distribution-aware distance

`distance()` is the **raw feature metric** — an absolute, inventory-independent
mean over phonetic features, so a given pair scores the same whatever inventory
you loaded. Raw
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

Distances are **structural**: two segments are close when they are made similarly — same articulator, similar position in the vocal tract, similar constriction. That correlates with perceptual confusability but does not model it. Exact values are pinned in the test suite rather than quoted here: a change that moves them fails CI, where prose would go stale in silence. [docs/distance.md](docs/distance.md) documents the representation, the comparison, and what the numbers do and do not mean.

`distance_model()` also accepts `gamma` (an exponent on the percentile; it reorders no phone pair, and its real effect is to reprice substitutions against gaps in word alignment — [docs/distance.md](docs/distance.md) §9 is what it is and is not good for), `insert_cost` / `delete_cost` for word alignment, and `threshold` / `max_length_ratio` defaults for `is_similar`. The raw pairwise matrix ships as `ipakit/data/confusion.json`; per-inventory models reuse it and only re-slice the percentile distribution.

`insert_cost` and `delete_cost` may be a flat price or a `CostSchedule`, which prices each phone on its own — because a schwa and a released stop are not the same kind of loss. Which phones are droppable is a fact about a language, so a schedule is language-relative and no default one ships; `directional_word_distance(reference, hypothesis)` is the entry point that names its reference side, and every result reports the schedule it was computed under. [docs/distance.md](docs/distance.md) §10 is what a schedule is and is not comparable across.

A word comparison reports `coverage` — the shorter token count over the longer — beside its `similarity`, and never inside it. Length is charged once, by the gaps the alignment pays for; a length ratio multiplied into the score would charge it twice and would destroy the one thing the ratio says, which is whether a low score means "different throughout" or "one is a truncation".

## Conventions

- **Stress is placed on the vowel** (the syllable nucleus), not the syllable
  onset: `from_cmu(["K", "AE1", "T"])` → `kˈæt`. Syllabification is preserved
  across round trips (`W AO1 T ER0` ↔ `wˈɔtɚ`).
- **Ties are typed** (house convention; see [docs/ties.md](docs/ties.md)): the over-tie fuses constituents into one timing slot (affricates and double articulations: `t͡ʃ`, `k͡p`), the under-tie binds a sequence into one unit (diphthongs, morae: `e͜ɪ`, `a͜ɪ͜ə`), and the over-tie binds tighter in mixed chains (`t͡s͜a`). The glyph is authoritative everywhere; text written in other conventions (where the glyphs are typographic variants, and where the keyboard stands in for the phonetic alphabet) imports explicitly via `ipakit.from_wild` — default parsing never rewrites its input. Tie *presence* is contrastive: `t͡s` is one segment, `ts` is a cluster.
- **Round-trip guarantee (X-SAMPA only):** IPA written in these conventions round-trips through X-SAMPA (`ipa → xsampa → ipa`), **up to tie sense**: X-SAMPA has a single tie encoding, so the under-tie projects onto the over-tie at the boundary and round trips return canonical over-tie spellings (`t͜s → t_s → t͡s`); the sequential/simultaneous distinction survives only in IPA. Every other exception is enumerated here, and the suite asserts the round-trip failure set is *exactly* this list over two spaces — the registered inventory, and the composed forms built from it (every registered base carrying one registered mark, in either position; every adjacent pair of bases) — so nothing can join it in silence. The accepted ligature alias spellings (`ʧ`, `ʦ`, `ƛ`) convert as the thing they spell and come back canonical; they sit outside that inventory, so a second test sweeps the alias map to keep them out of the dropped set.
  - *Ambiguous* — `b͡v`, `t͡θ`, `ŋ͡m` come back as `b̬`, `t˥`, `ŋ̻`: the tie encoding `_` collides with a diacritic/tone encoding (`_v`, `_T`, `_m`). Inherent to X-SAMPA; ICU shares it.
  - *Ambiguous on composition* (see [docs/ties.md](docs/ties.md)) — the table is not prefix-free, so a join between two encodings can spell a key a third entry already claims and longest-match reads that one. `` ` `` is both the rhotacized modifier and X-SAMPA's retroflex suffix, so a base plus `ʴ` spells the retroflex phone and the sound changes: `dʴ lʴ nʴ rʴ sʴ tʴ zʴ ɹʴ t͡sʴ d͡zʴ` come back `ɖ ɭ ɳ ɽ ʂ ʈ ʐ ɻ t͡ʂ d͡ʐ`. `ǀǀ → ǁ` and `ǀǁ → ǁǀ`, because `|\|\` (the alveolar lateral click) is two `|\` (the dental one). In three more the sound survives and only a redundant spelling of it does not — `əʴ → ɚ`, `ɜʴ → ɝ`, `tʼ → ť` — which is the canonicalization `from_wild` is there to do, X-SAMPA being an ASCII convention for writing IPA rather than a phoneset beside it. Writing loses nothing at a join (`to_xsampa` of a join is the join of the `to_xsampa`s, over both spaces), so each of these is the reader re-segmenting, not the writer dropping.
  - *Redundant spelling* — `˞`, `̀`, `́`, `̄`, `ʻ` are dropped: X-SAMPA has one encoding where IPA has two, and in a bijective table it belongs to the house-canonical spelling — `ʴ` (`` ` ``), the tone bars `˨`/`˦`/`˧` (`_L`/`_H`/`_M`), `ʰ` (`_h`). Written that way, the sound round-trips exactly.
  - *Unencodable* — `ⱱ`, `ˀ`, `ᵊ`, `^` are dropped: X-SAMPA has no notation for the labiodental flap (X-SAMPA predates the IPA's 2005 adoption of the symbol, and the standard chart marks that cell as having none), for glottalization, or for schwa release, and unit prominence is house IPA notation that X-SAMPA never had. An invented spelling would collide with notation already in use, so these stay unmapped rather than approximated.
  - *Declined rather than impossible* — `ʱ` is dropped too, and for a different reason worth keeping separate from the four above. It had a curated encoding, `_hh`, which extended X-SAMPA's `_h`, so `ʰh` and `ʰɦ` both read back as `ʱ`: an ambiguity ipakit introduced rather than one the standard has. IPA is the primary notation and X-SAMPA a convenience, so declining to spell one mark there costs less than inventing an ambiguity to keep it.

  A dropped symbol takes its neighbors' adjacency with it (`kⱱt → kt`), which is what `strict=True` is for: `to_xsampa("kⱱt", strict=True)` raises `ValueError` naming the symbol instead. The CMU, TIMIT, and Kirshenbaum mappings are lossy (they collapse IPA distinctions) and carry no round-trip guarantee; Kirshenbaum has no labiodental-flap notation either.

## CLI

```text
ipakit features p                    # Get features for 'p'
ipakit describe p                    # "voiceless bilabial plosive"
ipakit convert to-cmu "kˈæt"         # IPA to CMU: K AE1 T (stress on the vowel)
ipakit convert from-cmu K AE1 T        # CMU to IPA: kˈæt
ipakit convert to-xsampa "t͡ʃ"        # IPA to X-SAMPA: t_S
ipakit query match plosive bilabial  # Find phones by feature
ipakit analysis natural-class p t k  # Shared features of a set
ipakit analysis minimal-pairs p      # Find similar phones
ipakit distance pair p b             # Raw structural distance
ipakit distance confusability p b    # Inventory-relative confusability
ipakit distance word kæt kæd         # Word similarity
ipakit distance seq "k a t" "k æ t" # Distance over pre-tokenized phone sequences
ipakit distance nearest kat kæt kɑt  # Best-matching acceptable variant
ipakit rules apply -s american-english pˈɪn    # Broad to narrow: pʰˈɪ̃n
ipakit rules trace -s american-english bˈʌtɚ   # Which rule fired, and where
ipakit rules recognize -r 't -> ʔ / _ #' kæt   # Where it holds, nothing rewritten
ipakit tract draw t -o t.svg         # Mid-sagittal figure for one phone
ipakit tract heads                   # Head shapes a figure can be drawn on
```

The `distance confusability`/`word` commands use the distribution-aware model;
scope them to a reference inventory with `--phoneset FILE` (one phone per line).

`ipakit rules` applies context-sensitive rewrite rules (`A -> B / C _ D`): a
shipped set with `-s`, notation with `-r` (repeatable, and an ordered cascade), a
file with `--file`, and forms one per line on stdin when none are given.
Single-quote the notation — it contains `#`, `|` and `;`, and the name separator
is `;` because `|` is a legal context item. See [docs/rules.md](docs/rules.md).

Most commands accept `--format json` (or `-j`) for machine-readable output.
Run `ipakit`, `ipakit <group>`, or append `help`/`-h` anywhere for usage.

Exit status is uniform across every subcommand: `0` succeeded and the input was
read in full, `1` the command failed, `2` the command line was not understood,
and `3` it ran but part of the input could not be read and was dropped — with
what was dropped named on stderr. `--lax` reports `0` for that last case.

[docs/tutorial.md](docs/tutorial.md) walks the CLI and the API through the same
tasks, so a command here can be traced to the call behind it.

## Development

```bash
pip install -e ".[dev]"   # or ".[test]" / ".[lint]" for a lean subset
pre-commit install        # black, ruff, mypy --strict, hygiene hooks
pytest                    # unit tests + docstring examples
```

CI (`.github/workflows/ci.yml`) mirrors these on every push/PR across Python
3.12–3.13, and validates the committed derived artifacts (the IPA ↔ X-SAMPA
table and the phone-distance matrix) against their generators in `scripts/`.

## License

BSD 2-Clause — see [LICENSE](LICENSE).
