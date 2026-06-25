# ipakit Feature Roadmap

Prioritized additions for the IPA phonetic features toolkit.

---

## Priority 1: High Impact, Low Effort ✅ COMPLETE

### 1.1 `describe(phone)` — Human-readable description ✅
Generate standard IPA naming conventions from features.

```python
ipakit.describe("p")   # "voiceless bilabial plosive"
ipakit.describe("ɛ")   # "open-mid front unrounded vowel"
ipakit.describe("t͡ʃ")  # "voiceless postalveolar affricate"
```

**CLI**: `ipakit describe p` or `ipakit desc ŋ -f json`

---

### 1.2 `natural_class(phones)` — Find unifying features ✅
Given a set of phones, return features they all share.

```python
ipakit.natural_class(["p", "t", "k"])
# {"manner": "plosive", "voiced": "-"}

ipakit.natural_class(["i", "e", "ɛ", "æ"])
# {"manner": "vowel", "backness": "front"}
```

**CLI**: `ipakit analysis natural-class p t k` or `ipakit an nc m n ŋ`

---

### 1.3 `minimal_pairs(phone)` — Phones differing by one feature ✅
Find phonetically similar phones for teaching/analysis.

```python
ipakit.minimal_pairs("p")
# [("b", "voiced", "+"), ("t", "place", "alveolar"), ...]

ipakit.nearest_phones("p", n=5)
# [("ɸ", 0.08), ("f", 0.10), ...]
```

**CLI**: `ipakit analysis minimal-pairs p` or `ipakit an mp s`

**CLI**: `ipakit analysis nearest ɛ -n 5` or `ipakit an near p`

---

## Priority 2: High Impact, Medium Effort

### 2.1 `word_distance(ipa1, ipa2)` — Phonetic edit distance
Levenshtein-style distance using phonetic feature costs.

```python
ipakit.word_distance("kæt", "kæd")   # Small (minimal pair)
ipakit.word_distance("kæt", "dɒɡ")   # Large (different word)

# Options:
ipakit.word_distance("kæt", "kæd", weighted=True)   # Use feature distance
ipakit.word_distance("kæt", "kæd", weighted=False)  # Standard Levenshtein
```

**Why**: Core for pronunciation assessment, ASR error analysis, fuzzy matching.

---

### 2.2 `syllabify(ipa)` — Syllable boundaries
Split IPA string into syllables using sonority sequencing principle.

```python
ipakit.syllabify("hɛloʊ")      # ["hɛ", "loʊ"]
ipakit.syllabify("ɪnˈkɹɛdəbəl") # ["ɪn", "ˈkɹɛ", "də", "bəl"]

# With options:
ipakit.syllabify("hɛloʊ", return_structure=True)
# [{"onset": "h", "nucleus": "ɛ", "coda": ""}, ...]
```

**Why**: Needed for stress placement, TTS, linguistic analysis.

---

### 2.3 `validate_ipa(ipa)` — Check well-formedness ✅
Validate IPA strings for structural issues.

```python
ipakit.validate_ipa("kæt")     # [] (valid)
ipakit.validate_ipa("k@t")     # [{"type": "error", "code": "unknown_symbol", ...}]
ipakit.is_valid_ipa("kæt")     # True
ipakit.is_valid_ipa("k@t")     # False
```

**CLI**: `ipakit analysis validate "kæt"` or `ipakit an val "k@t" -f json`

**Note**: Language-specific phonotactics (e.g., onset constraints) could be added later.

---

## Priority 3: Medium Impact, Low Effort

### 3.1 Additional phoneme mappings ✅
Expand conversion support beyond CMU and X-SAMPA.

| Format | Status | Description |
|--------|--------|-------------|
| TIMIT | ✅ | Speech corpus standard |
| Kirshenbaum | ✅ | ASCII-IPA for email/plain text |
| Worldbet | ⏳ | Cross-linguistic ASCII (future) |
| Epitran | ❌ | Skip (G2P tool, not encoding) |

```python
ipakit.to_timit("kæt")           # ["k", "ae", "t"]
ipakit.from_timit(["k", "ae", "t"])  # "kæt"

ipakit.to_kirshenbaum("ʃɑk")     # "SAk"
ipakit.from_kirshenbaum("SAk")   # "ʃɑk"
```

**CLI**:
- `ipakit convert to-timit "kæt"` / `ipakit c from-timit k ae t`
- `ipakit convert to-kirshenbaum "ʃɑk"` / `ipakit c from-kirsh "SAk"`

---

### 3.2 `sonority(phone)` — Sonority index
Return sonority value for sonority sequencing.

```python
ipakit.sonority("a")   # 10 (most sonorous)
ipakit.sonority("l")   # 7
ipakit.sonority("s")   # 3
ipakit.sonority("p")   # 1 (least sonorous)
```

**Why**: Foundation for syllabification; simple lookup table.

---

## Priority 4: Medium Impact, Medium Effort

### 4.1 `vowel_chart()` / `consonant_table()` — IPA chart generation
Generate standard IPA layout visualizations.

```python
# Text output
ipakit.vowel_chart()
#        front  central  back
# close    i  y    ɨ  ʉ    ɯ  u
# ...

ipakit.consonant_table(phones=["p", "b", "t", "d", "k", "ɡ"])
#              bilabial  alveolar  velar
# plosive      p  b      t  d      k  ɡ

# Or generate SVG/HTML
ipakit.vowel_chart(format="svg")
```

**Why**: Documentation, teaching materials, inventory visualization.

---

### 4.2 `compare_inventories(inv1, inv2)` — Phoneme inventory comparison
Compare two language inventories.

```python
english = ["p", "b", "t", "d", "k", "ɡ", "θ", "ð", ...]
spanish = ["p", "b", "t", "d", "k", "ɡ", "x", ...]

ipakit.compare_inventories(english, spanish)
# {
#   "only_english": ["θ", "ð", "ʒ", ...],
#   "only_spanish": ["x", "ɲ", "ʎ", ...],
#   "shared": ["p", "b", "t", "d", ...],
#   "similarity": 0.72
# }
```

**Why**: Contrastive analysis, L2 pronunciation difficulty prediction.

---

## Priority 5: Larger Scope (Future)

### 5.1 Language phoneme inventories
Bundled or loadable language-specific data.

```python
ipakit.inventory("english")   # Phoneset with ~44 phonemes
ipakit.inventory("japanese")  # Phoneset with ~22 phonemes

# With metadata
inv = ipakit.inventory("english")
inv.consonants   # ["p", "b", "t", ...]
inv.vowels       # ["i", "ɪ", "e", ...]
inv.allophones   # {"t": ["ɾ", "ʔ"], ...}
```

**Why**: Language-specific operations, comparative phonology.

---

### 5.2 Allophone rules
Language-specific phoneme → allophone mappings.

```python
ipakit.allophones("t", language="american_english")
# ["t", "ɾ", "ʔ", "tʰ"]

ipakit.allophone_context("t", "ɾ", language="american_english")
# "Intervocalic position after stressed vowel"
```

**Why**: Advanced phonological analysis, dialect modeling.

---

### 5.3 External integrations
Bridges to other tools.

```python
# Epitran G2P
ipakit.from_epitran("hello", language="eng-Latn")

# Phonemizer
ipakit.from_phonemizer("hello", backend="espeak")

# Praatpy (acoustics)
ipakit.acoustic_features("hello.wav")
```

**Why**: Integration with ML/NLP pipelines.

---

## Summary Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| `describe()` | High | Low | P1 |
| `natural_class()` | High | Low | P1 |
| `minimal_pairs()` | Medium | Low | P1 |
| `word_distance()` | High | Medium | P2 |
| `syllabify()` | High | Medium | P2 |
| `validate_ipa()` | Medium | Medium | P2 |
| Additional mappings | Medium | Low | P3 |
| `sonority()` | Medium | Low | P3 |
| `vowel_chart()` | Medium | Medium | P4 |
| `compare_inventories()` | Medium | Medium | P4 |
| Language inventories | High | High | P5 |
| Allophone rules | Medium | High | P5 |
| External integrations | High | High | P5 |

---

## Notes

- P1 items can likely be done in a day each
- P2 items need more design thought (edge cases)
- P3-P4 are nice-to-haves that round out the toolkit
- P5 items are significant scope expansions
