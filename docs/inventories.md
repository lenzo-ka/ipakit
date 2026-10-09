# Inventories and styles

<!-- Generated from docs/inventories.src.md and ipakit/data/inventory-cards.xml by scripts/inventory_cards.py. Do not edit: run `make inventory-cards`. -->

An `Inventory` binds a name to a `Style`, a provenance, and — where the notation has one — the finite `Phoneset` it carries, written in house IPA.

A `Style` is a strict boundary: `read()` turns one spelling from that notation into house IPA, and `spell()` turns one house-IPA phone back into that notation.

Card-bearing declaration roots state `upstream`, `upstream-url`, `artifact`, `version`, `license`, and `kind`; `Inventory.source.to_dict()` exposes those fields in a JSON-serializable form. `version` is the upstream source pin, with `unpinned` written explicitly when there is no pin. A declaration format that needs its own schema revision uses `declaration-version` instead. The human `Inventory.provenance` sentence is derived from these fields and is not stored beside them, so one fact has one spelling to keep current.

Use `inventories()` to list the available names and `inventory(name)` to load one; an unknown name is refused with the available names. eSpeak names become available when `IPAKIT_ESPEAK_NG` or the managed cache selects accepted eSpeak data.

Independent finite feature models have their own declaration boundary:
`ipakit.feature_models.available()` lists the shipped tables, and
`ipakit.feature_models.read("panphon")` reads the frozen Panphon table through
the same validated ternary codec used for supplied paths. Its data, provenance
and license notice travel in the package; the producer library is development-only.
This does not invent a house notation style or require a house feature mapping.

`ipa` is the house notation and finite shipped inventory, while `wild` is the soft IPA reader and has no finite phoneset.

CMUdict, PocketSphinx, TIMIT, MFA, and ZIPA are shipped finite inventories. With user-supplied eSpeak NG source, bare `espeak` and every generated eSpeak language are finite inventories; MFA has the union `mfa` and generated members `mfa:<name>`, while language-scoped eSpeak names have the form `espeak:en`.

These are deliberately different kinds of finite declaration. CMUdict and PocketSphinx expose a pronunciation-dictionary alphabet, TIMIT a labeled speech-corpus phoneset, MFA harmonized dictionary phone sets across languages, ZIPA a multilingual recognizer vocabulary, and eSpeak language-specific synthesis phoneme tables. House IPA is the pivot among their spellings and feature descriptions; it does not erase those construction purposes. A nearest-feature correspondence therefore means proximity only. In particular, an MFA allophone's nearest CMU phone is not evidence of the phoneme it derives from: that relation must be supplied by a declared phonological rule or correspondence, and may be one-to-many when a rule is not invertible.

Declared refusals are excluded from the phone count and available through `Inventory.refusals`; `inventory show` prints their spellings and reasons separately.

The `zipa` inventory contains the 108 base phones in ZIPA's pinned 127-token vocabulary. `ZIPABridge.read_tokens()` also reads its 15 trailing-mark tokens and `▁` word boundary, while `<blk>`, `<sos/eos>`, and `<unk>` are declared non-phone refusals. `ZIPABridge.read_original()` reads the IPAPack++ `custom.original` field, retaining spaces and tie bars; its ASCII `g` maps to house `ɡ` only at that ZIPA boundary, and the ordinary strict reader continues to refuse `g`. The reverse projection declares the recognizer vocabulary's missing ties, stress, tone, second diacritics, and the absent `̯ ̤ ̆ ̈ ˑ` marks.

Bare `espeak` is the union of the phone names generated in memory from the user's pinned eSpeak NG source, the vocabulary used by wav2vec2 eSpeak phoneme recognizers, while each `espeak:<code>` inventory retains its language's table. `EspeakBridge(code, source=...)` gives an explicit path first priority, then `IPAKIT_ESPEAK_NG`, then a valid managed build selected by the cache root. Invalid explicit or environment selections are refused without falling through, and a missing source and managed build are refused clearly. See [user-supplied sources](user-sources.md) for acquisition, build, and cache selection.

The union style reads a name to its house-IPA spelling only where every declaration carrying that name agrees, while a name found in only one declaration reads through that declaration.

The union style spells with an agreed name, preferring the name carried by the most declarations, then the shortest, then the lexically first, and refuses a phone without one by naming each ambiguous candidate and its `espeak:<code>` meanings.

When mapping inventories, an entry its selected style cannot read is reported on its own side and makes the command fail rather than being respelled as a valid entry.

Inventory order is declaration order: XML atom order for bridges, phonemap row order for CMU and TIMIT, and `IPAFeatures().phones` order for `ipa`; the eSpeak union is the exception and uses sorted house IPA.

Finite inventories contain sounds. Their construction applies the declared silence-spelling rule `Phoneset.from_file()` applies.

The registry discovers eSpeak members from the selected user source and MFA
members from their shipped declaration directory. CMUdict, PocketSphinx, the
eSpeak union when its source is available, ZIPA, and TIMIT (when its declaration
is available) are explicit registry entries; phonemap and bridge files do not all
become named inventories merely by appearing on disk.

```python
from pathlib import Path

registry_source = Path("ipakit/inventories.py").read_text(encoding="utf-8")
all(name in registry_source for name in ('"cmudict"', '"pocketsphinx"', '"espeak"', '"timit"'))  # True
```

[Praat TextGrid interchange](textgrid.md#label-styles) applies a named style strictly to segment labels and tier labels derived from them while retaining point marks in house notation.

Add a vocabulary inventory by placing its XML declaration under the matching bridge data directory; adapt the bridge only where its atom contract differs from `VocabularyBridge`. Notation-specific converters that cannot strictly read and spell one phone in both directions do not belong in this registry.

X-SAMPA and Kirshenbaum remain notation converters rather than finite inventories: their maps say how symbols are written, not which sounds a language, corpus, recognizer, or synthesizer contains. Pinyin and kana are structured vocabulary bridges whose units can contain IPA sequences, so flattening their rows into a phoneset would lose the unit boundary the declaration supplies. New interop pivots should be added as styles plus finite inventories only when an upstream inventory establishes both claims; an open-ended notation alone establishes only the style.

`convert phoneset FILE --from-style SOURCE --to-style TARGET` transcodes a declared list of phone spellings through house IPA. Both legs are strict: every source entry must read as one house phone and every house phone must have an exact target spelling, or the command reports every refusal and writes nothing. This is notation interoperation, not feature-nearest substitution, and it does not claim that the resulting phones occur in the target's finite inventory. Use `distance map` when the question is instead which target-inventory phone is structurally nearest, and read its `nearest` relation label literally.

The `ipakit inventory` group inspects this named registry; `ipakit phoible inventory` selects a PHOIBLE doculect instead.

A pronunciation dictionary can declare an ordinary finite inventory through `inventory_from_dictionary(path, style)`, or through `ipakit inventory from-dict FILE --style STYLE`. CMUdict and PocketSphinx dictionaries use their shared CMUdict reader, MFA dictionaries use their `MFABridge` line syntax, and `ipa` and `wild` use word-plus-whitespace pronunciation lines. The phones retain dictionary order and exclude the declared silence spellings (`SIL` and the house `␣`). An MFA entry whose entire pronunciation consists of non-phone aligner markers (`<s>`, `</s>`, or `spn`) is a placeholder rather than a pronunciation: the reader excludes it and records its spelling and line-specific reason in `Inventory.refusals`. A marker mixed with a phone remains an unreadable phone and refuses the dictionary with its line and entry named, as does every other unreadable phone. `refuse_unreadable=True`, spelled `--refuse-unreadable` on the command line, applies that strict rule to marker-only placeholders too. `Inventory.counts` records both the number of phone tokens and the number of dictionary entries containing each phone, with repeated tokens in one entry contributing once to `entries`; the counts cover every successfully read nonsilence phone before an optional cutoff. A style that keeps stress reads a stressed dictionary phone as a stressed house unit (`AE1` as `ˈæ`), so the derived inventory lists stressed and unstressed vowels as distinct members, which is what the dictionary itself distinguishes. Under `pocketsphinx`, a dictionary carrying stress digits is refused rather than stripped; use `cmudict` to read stress-bearing dictionary phones.

The `min_entries` option, spelled `--min-entries N` on the command line, drops phones found in fewer than `N` dictionary entries and leaves the basic behavior unchanged when omitted. This cuts a low-attestation tail; it does not identify a phonemic or real inventory, distinguish a loanword phone from an under-written allophone, or remove a rule-generated allophone that clears the cutoff. `Inventory.dropped` names each caller-requested removal with both counts and stays separate from `Inventory.refusals`, because the dictionary reader accepted the phone. Text commands report drops on standard error so their one-phone-per-line output remains a phoneset, while JSON carries `counts` and `dropped` explicitly.

The command prints a one-phone-per-line house-IPA phoneset by default and reports placeholder refusals on standard error; `--spell native` selects the dictionary notation, and `-f json` reports both spellings, provenance, refusals, attestation counts, and requested drops. The output stays separate from mapping input, so a dictionary-to-MFA mapping is an explicit pipeline: `ipakit inventory from-dict lexicon.dict --style cmudict -o lexicon.phones && ipakit distance map lexicon.phones mfa`.

## Experimental inventory views

`ipakit.inventory_views` provides the versioned, experimental `InventoryView`
adapter for registry inventories and inventories returned by
`inventory_from_dictionary()`. Each immutable view retains source identity,
provenance, declaration order, and one status per member: `present`, `filtered`,
`dropped`, `unreadable`, `refused`, `unavailable`, or `unresolved`. Dictionary
counts and drops remain attached to their members. A source without a finite
population has one explicit `unavailable` member; it is not represented as an
available empty inventory. Consumers must check the schema identifier and version.

`ipakit.inventory_comparison.inventory_comparison_report()` compares available
finite views through the existing phoneset comparison and mapping engines. Its
versioned `InventoryComparisonReport` is experimental: consumers must check the
schema identifier and version. A pair retains the pairwise report shape, while
other arities use the permutation-invariant N-way membership and coverage shape.
Summary is the default. `detail=True` adds symbol rows and strip witnesses, plus
matrices, correspondences, and optional feature terms for a pair. Mapping is
opt-in, directional, and has no implicit threshold.

### Coverage measure names and denominators

- `overlap`: symbols present in every selected input over the union of symbols
  present in at least one selected input.
- `readable/admitted`: declared source members admitted as `present` with a
  house-readable form over all declared members. Its denominator retains the
  `present`, `filtered`, `dropped`, `unreadable`, `refused`, `unavailable`, and
  `unresolved` status buckets.
- `reviewed-mapped`: members with an explicit reviewed source-native mapping over
  the `present` and `unresolved` members of views that carry that mapping
  authority. It is not applicable when no selected view carries one.
- `exact representability`: exact target-membership hits over all directed
  source-symbol opportunities between distinct selected inputs.
- `thresholded-nearest`: source symbols accepted at a caller-supplied maximum
  distance over those same directed opportunities. It is not applicable when
  the caller supplies no threshold.

These measures are separate: parser admission, reviewed authority, exact
membership, and nearest-distance acceptance do not stand in for one another.
The canonical JSON repeats each definition, numerator and denominator status
buckets, and applicability beside its result.

### Generated comparison reports

The summaries below come directly from the report object during
`make inventory-cards`; their result values are not copied into prose. They use
only the shipped CMUdict, TIMIT, and MFA English US declarations. They do not
probe live PHOIBLE, CLTS, or eSpeak sources. An absent optional source is an
explicit `unavailable` view, not an empty inventory.

### Generated pairwise summary: CMUdict and TIMIT

<!-- inventory-comparison-example: pairwise -->
```json
{
  "asymmetry": null,
  "identity": "sha256:cbd3b95b04a284900697df3cfff87583306c797da077e2f1b4a951611aa771f5",
  "inputs": {
    "a": {
      "availability": "available",
      "declared_count": 41,
      "identity": "sha256:c96d741b01fc9f77315d4f7cb34bd19a5319f218246cfa4e4ef5ed32e8ce0215",
      "kind": "pronunciation-dictionary-phone-map",
      "name": "cmudict",
      "provenance": "CMU Pronouncing Dictionary ARPAbet-to-house-IPA phonemap, explicitly unpinned (BSD-2-Clause)",
      "schema": {
        "id": "ipakit.inventory-view",
        "version": 1
      },
      "source": {
        "artifact": "ARPAbet-to-house-IPA phonemap",
        "kind": "pronunciation-dictionary-phone-map",
        "license": "BSD-2-Clause",
        "upstream": "CMU Pronouncing Dictionary",
        "upstream-url": "https://github.com/cmusphinx/cmudict",
        "version": "unpinned"
      },
      "status_counts": {
        "dropped": 0,
        "filtered": 0,
        "present": 41,
        "refused": 0,
        "unavailable": 0,
        "unreadable": 0,
        "unresolved": 0
      },
      "style": "cmudict",
      "version": "unpinned"
    },
    "b": {
      "availability": "available",
      "declared_count": 58,
      "identity": "sha256:732d0d0d898f9f14fcc9c2e75c92ba64dca89e9e18fa07ae2fb31d0fea6039fd",
      "kind": "speech-corpus-phone-map",
      "name": "timit",
      "provenance": "NISTIR 4930 §4.3 Phonetic and Phonemic Symbol Codes transcribed to house IPA, pinned at NISTIR 4930 (February 1993) (BSD-2-Clause)",
      "schema": {
        "id": "ipakit.inventory-view",
        "version": 1
      },
      "source": {
        "artifact": "Phonetic and Phonemic Symbol Codes transcribed to house IPA",
        "kind": "speech-corpus-phone-map",
        "license": "BSD-2-Clause",
        "upstream": "NISTIR 4930 §4.3",
        "upstream-url": "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir4930.pdf",
        "version": "NISTIR 4930 (February 1993)"
      },
      "status_counts": {
        "dropped": 0,
        "filtered": 0,
        "present": 58,
        "refused": 0,
        "unavailable": 0,
        "unreadable": 0,
        "unresolved": 0
      },
      "style": "timit",
      "version": "NISTIR 4930 (February 1993)"
    }
  },
  "mapping": {
    "a_to_b": {
      "ambiguous_count": 0,
      "collapse_count": 0,
      "exact_count": 41,
      "mapped_count": 41,
      "max_distance": null,
      "mean_distance": 0.0,
      "relation": "nearest",
      "source": "a",
      "source_count": 41,
      "target": "b",
      "target_count": 58,
      "total_distance": 0.0,
      "unmapped_count": 0,
      "unused_target_count": 17,
      "worst": {
        "distance": 0.0,
        "source": "i",
        "target": "i"
      }
    },
    "b_to_a": {
      "ambiguous_count": 0,
      "collapse_count": 13,
      "exact_count": 41,
      "mapped_count": 58,
      "max_distance": null,
      "mean_distance": 0.012825013604964538,
      "relation": "nearest",
      "source": "b",
      "source_count": 58,
      "target": "a",
      "target_count": 41,
      "total_distance": 0.7438507890879432,
      "unmapped_count": 0,
      "unused_target_count": 0,
      "worst": {
        "distance": 0.08695652173913043,
        "source": "ə̥",
        "target": "ə"
      }
    },
    "directional": true,
    "max_distance": null,
    "strategy": "nearest"
  },
  "membership": {
    "a_count": 41,
    "b_count": 58,
    "intersection_count": 41,
    "only_a_count": 0,
    "only_b_count": 17,
    "union_count": 58
  },
  "options": {
    "applicable_only": false,
    "detail": false,
    "feature_terms": false,
    "mapping": "nearest",
    "max_distance": null,
    "strip": "stress"
  },
  "schema": {
    "id": "ipakit.inventory-comparison-report",
    "stability": "experimental",
    "version": 1
  },
  "stripping": {
    "changed_count": 0,
    "mode": "stress"
  },
  "terms": {
    "directionality": "A -> B and B -> A are independent directional results",
    "distance": "raw-feature-distance",
    "mapping": "nearest",
    "matrix": "similarity",
    "membership": "exact-post-strip-post-tie-engine-form-membership"
  }
}
```

### Generated N-way summary: CMUdict, TIMIT, and MFA English US

<!-- inventory-comparison-example: n-way -->
```json
{
  "coverage": [
    {
      "applicable": true,
      "definition": "symbols present in every selected input divided by symbols present in at least one selected input",
      "denominator": 98,
      "name": "overlap",
      "numerator": 33,
      "status_buckets": {
        "denominator": [
          "present"
        ],
        "numerator": [
          "present"
        ]
      }
    },
    {
      "applicable": true,
      "definition": "declared source members admitted as present with a house-readable form divided by all declared source members",
      "denominator": 177,
      "name": "readable/admitted",
      "numerator": 177,
      "status_buckets": {
        "denominator": [
          "present",
          "filtered",
          "dropped",
          "unreadable",
          "refused",
          "unavailable",
          "unresolved"
        ],
        "numerator": [
          "present"
        ]
      }
    },
    {
      "applicable": false,
      "definition": "members with a reviewed source-native mapping divided by members in a view carrying that mapping authority",
      "denominator": 0,
      "name": "reviewed-mapped",
      "numerator": 0,
      "status_buckets": {
        "denominator": [],
        "numerator": []
      }
    },
    {
      "applicable": true,
      "definition": "directed source symbols present exactly in the target divided by all directed source-symbol opportunities across distinct inputs",
      "denominator": 354,
      "name": "exact representability",
      "numerator": 224,
      "status_buckets": {
        "denominator": [
          "present"
        ],
        "numerator": [
          "present"
        ]
      }
    },
    {
      "applicable": true,
      "definition": "directed source symbols with a nearest target at or below the explicit maximum distance divided by all directed source-symbol opportunities across distinct inputs",
      "denominator": 354,
      "name": "thresholded-nearest",
      "numerator": 328,
      "status_buckets": {
        "denominator": [
          "present"
        ],
        "numerator": [
          "present"
        ]
      }
    }
  ],
  "identity": "sha256:3c1c55b5020f2605de91652d35f4a293a79fe4837a609dc08cef819eecef787f",
  "inputs": {
    "input-0": {
      "availability": "available",
      "declared_count": 58,
      "identity": "sha256:732d0d0d898f9f14fcc9c2e75c92ba64dca89e9e18fa07ae2fb31d0fea6039fd",
      "kind": "speech-corpus-phone-map",
      "name": "timit",
      "provenance": "NISTIR 4930 §4.3 Phonetic and Phonemic Symbol Codes transcribed to house IPA, pinned at NISTIR 4930 (February 1993) (BSD-2-Clause)",
      "schema": {
        "id": "ipakit.inventory-view",
        "version": 1
      },
      "source": {
        "artifact": "Phonetic and Phonemic Symbol Codes transcribed to house IPA",
        "kind": "speech-corpus-phone-map",
        "license": "BSD-2-Clause",
        "upstream": "NISTIR 4930 §4.3",
        "upstream-url": "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir4930.pdf",
        "version": "NISTIR 4930 (February 1993)"
      },
      "status_counts": {
        "dropped": 0,
        "filtered": 0,
        "present": 58,
        "refused": 0,
        "unavailable": 0,
        "unreadable": 0,
        "unresolved": 0
      },
      "style": "timit",
      "version": "NISTIR 4930 (February 1993)"
    },
    "input-1": {
      "availability": "available",
      "declared_count": 41,
      "identity": "sha256:c96d741b01fc9f77315d4f7cb34bd19a5319f218246cfa4e4ef5ed32e8ce0215",
      "kind": "pronunciation-dictionary-phone-map",
      "name": "cmudict",
      "provenance": "CMU Pronouncing Dictionary ARPAbet-to-house-IPA phonemap, explicitly unpinned (BSD-2-Clause)",
      "schema": {
        "id": "ipakit.inventory-view",
        "version": 1
      },
      "source": {
        "artifact": "ARPAbet-to-house-IPA phonemap",
        "kind": "pronunciation-dictionary-phone-map",
        "license": "BSD-2-Clause",
        "upstream": "CMU Pronouncing Dictionary",
        "upstream-url": "https://github.com/cmusphinx/cmudict",
        "version": "unpinned"
      },
      "status_counts": {
        "dropped": 0,
        "filtered": 0,
        "present": 41,
        "refused": 0,
        "unavailable": 0,
        "unreadable": 0,
        "unresolved": 0
      },
      "style": "cmudict",
      "version": "unpinned"
    },
    "input-2": {
      "availability": "available",
      "declared_count": 78,
      "identity": "sha256:f0b30d06828537276e79f73d8e69467bbf6c03ff1650e68ea4b20e056ba38ab7",
      "kind": "dictionary-phone-set",
      "name": "mfa:english_us",
      "provenance": "Montreal Forced Aligner english_us_mfa dictionary v3.1.0, pinned at mfa-models@d6eff86a42c6a90b641e17dfdf7a16555b934483 (CC-BY-4.0)",
      "schema": {
        "id": "ipakit.inventory-view",
        "version": 1
      },
      "source": {
        "artifact": "english_us_mfa dictionary v3.1.0",
        "kind": "dictionary-phone-set",
        "license": "CC-BY-4.0",
        "upstream": "Montreal Forced Aligner",
        "upstream-url": "https://github.com/MontrealCorpusTools/mfa-models/tree/d6eff86a42c6a90b641e17dfdf7a16555b934483",
        "version": "mfa-models@d6eff86a42c6a90b641e17dfdf7a16555b934483"
      },
      "status_counts": {
        "dropped": 0,
        "filtered": 0,
        "present": 78,
        "refused": 0,
        "unavailable": 0,
        "unreadable": 0,
        "unresolved": 0
      },
      "style": "mfa:english_us",
      "version": "mfa-models@d6eff86a42c6a90b641e17dfdf7a16555b934483"
    }
  },
  "mapping": {
    "directional": true,
    "max_distance": 0.05,
    "ordered_pair_count": 6,
    "strategy": "nearest"
  },
  "membership": {
    "input_count": 3,
    "input_sizes": [
      58,
      41,
      78
    ],
    "shared_by_all_count": 33,
    "shared_by_subset_count": 13,
    "shared_by_subset_groups": [
      {
        "count": 8,
        "inputs": [
          "input-0",
          "input-1"
        ]
      },
      {
        "count": 5,
        "inputs": [
          "input-0",
          "input-2"
        ]
      }
    ],
    "union_count": 98,
    "unique_to_one_count": 52,
    "unique_to_one_groups": [
      {
        "count": 12,
        "input": "input-0"
      },
      {
        "count": 0,
        "input": "input-1"
      },
      {
        "count": 40,
        "input": "input-2"
      }
    ]
  },
  "options": {
    "applicable_only": false,
    "detail": false,
    "feature_terms": false,
    "mapping": "nearest",
    "max_distance": 0.05,
    "strip": "stress"
  },
  "schema": {
    "id": "ipakit.inventory-comparison-report",
    "stability": "experimental",
    "version": 1
  },
  "stripping": {
    "changed_count": 0,
    "mode": "stress"
  },
  "terms": {
    "directionality": "ordered source and target inputs are independent directional results",
    "distance": "raw-feature-distance",
    "mapping": "nearest",
    "matrix": "similarity",
    "membership": "exact-post-strip-post-tie-engine-form-membership"
  }
}
```

## Family cards

The cards group registry entries by family. A language or variety is an instance of its family, not a separate scorecard. Panphon is a shipped finite feature-model declaration with a development-only producer; it is not a house notation style.

## House IPA

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [ipakit](https://github.com/lenzo-ka/ipakit) |
| Artifact | house IPA feature and notation declaration |
| Pin | `unpinned` |
| License | `BSD-2-Clause` |
| Kind | `phonetic-feature-inventory` |
| Declarations | `ipakit/data/ipa.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 139 |

### Qualitative

The finite house inventory is the shared notation and feature space into which the library reads other phone spellings.

**Conventions.** Registered entries use the library's IPA spelling, tie, boundary, and prosody conventions; inventory order is declaration order.

**Good at.** Use it when a finite, feature-bearing reference inventory and an identity spelling boundary are wanted.

**Less good at.** It is a declared working inventory rather than a claim that every possible or attested IPA segment is registered.

### Notes

- Registered sounds become candidates for inventory search and models; a well-formed unregistered tie chain can still compose without being promoted into the finite inventory.

## Wild IPA

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [ipakit](https://github.com/lenzo-ka/ipakit) |
| Artifact | house IPA feature and notation declaration |
| Pin | `unpinned` |
| License | `BSD-2-Clause` |
| Kind | `phonetic-feature-inventory` |
| Declarations | `ipakit/data/ipa.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 0 |
| Phone counts | Not finite |

### Qualitative

The soft reader brings common external IPA-like spellings into house IPA when a caller explicitly asks for forgiving input.

**Conventions.** It applies declared lookalikes and then requires a strict house-IPA result; spelling remains house IPA.

**Good at.** Use it at an import boundary where keyboard substitutes and canonically equivalent spellings are expected.

**Less good at.** It has no finite phoneset, so it is a notation style rather than a reference inventory for mapping or distance.

### Notes

- Soft lookalikes are read only through explicit wild import, leaving strict house parsing unchanged.

## CMUdict

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [CMU Pronouncing Dictionary](https://github.com/cmusphinx/cmudict) |
| Artifact | ARPAbet-to-house-IPA phonemap |
| Pin | `unpinned` |
| License | `BSD-2-Clause` |
| Kind | `pronunciation-dictionary-phone-map` |
| Declarations | `ipakit/data/phonemaps/cmu.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 41 |

### Qualitative

The CMUdict style reads and spells the ARPAbet vocabulary used by pronunciation dictionaries for speech synthesis and lexical work.

**Conventions.** Vowel stress digits are meaningful: primary, secondary, and unstressed spellings remain distinct house units where the dictionary distinguishes them.

**Good at.** Use it for CMUdict-format lexicons whose stress markings should survive inventory derivation and round trips.

**Less good at.** The mapping is an explicit finite ARPAbet boundary, not a general parser for arbitrary ASCII phonetic notation.

### Notes

- `AH0` and `AH1` read as distinct house units, preserving the stress contrast the dictionary writes.

## PocketSphinx

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [CMU Pronouncing Dictionary](https://github.com/cmusphinx/cmudict) |
| Artifact | ARPAbet-to-house-IPA phonemap |
| Pin | `unpinned` |
| License | `BSD-2-Clause` |
| Kind | `pronunciation-dictionary-phone-map` |
| Declarations | `ipakit/data/phonemaps/cmu.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 41 |

### Qualitative

The PocketSphinx style presents the CMU phone vocabulary under the stressless convention expected by recognizer dictionaries.

**Conventions.** It shares the declared CMU phone map while refusing stress digits and recognizing the style's silence and boundary labels.

**Good at.** Use it for stressless PocketSphinx lexicons where accepting a stress-bearing token would overstate what the notation commits to.

**Less good at.** It intentionally does not repair a CMUdict pronunciation by stripping stress; the `cmudict` style is the appropriate reader when digits carry information.

### Notes

- Stress digits are refused rather than silently discarded, so a dictionary in the neighboring convention fails clearly.

## TIMIT

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [NISTIR 4930 §4.3](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir4930.pdf) |
| Artifact | Phonetic and Phonemic Symbol Codes transcribed to house IPA |
| Pin | `NISTIR 4930 (February 1993)` |
| License | `BSD-2-Clause` |
| Kind | `speech-corpus-phone-map` |
| Declarations | `ipakit/data/phonemaps/timit.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 58 |

### Qualitative

The TIMIT style reads and spells the corpus's acoustic-phonetic segment labels in house IPA.

**Conventions.** Main labels provide canonical spellings; closure, epenthetic, syllabic, and pause labels are accepted as declared extras without replacing the canonical choice.

**Good at.** Use it for TIMIT label interchange and for a finite sound inventory in the corpus's transcription convention.

**Less good at.** Several corpus labels can describe the same house sound or structural material, so label count and finite phone count answer different questions.

### Notes

- The declaration retains closure and pause labels for corpus interchange, while the inventory applies the shared silence rule and counts sounds.

## eSpeak NG

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [eSpeak NG](https://github.com/espeak-ng/espeak-ng/tree/4870adfa25b1a32b4361592f1be8a40337c58d6c/phsource) |
| Artifact | per-language synthesis-phoneme-table artifacts built from the user's eSpeak NG checkout |
| Pin | `espeak-ng@4870adfa25b1a32b4361592f1be8a40337c58d6c` |
| License | `GPL-3.0-or-later` |
| Kind | `synthesis-phoneme-table` |
| Declarations | user-supplied eSpeak NG `phsource` (one per language table) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | `espeak` plus one `espeak:<code>` per language table |
| Finite inventories | every registered entry, when a checkout is supplied |

### Qualitative

The language-scoped inventories expose eSpeak NG's compact synthesis phoneme tables, and the family union supplies the vocabulary emitted by eSpeak-based recognizers.

**Conventions.** Each language resolves eSpeak table inheritance into native mnemonics; the union reads a mnemonic only where every declaration carrying it agrees on one house phone.

**Good at.** Use a language member for synthesis-facing text in that table's convention, or the union for cross-language recognizer vocabulary coverage.

**Less good at.** A shared mnemonic can mean different sounds in different language tables, so the union deliberately refuses an ambiguous read or spelling instead of choosing one language silently.

### Notes

- The union ranks agreed spellings by declaration coverage, length, and lexical order; selecting `espeak:<code>` retains a language table's own answer where tables disagree.

## Montreal Forced Aligner

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/mfa-models/tree/d6eff86a42c6a90b641e17dfdf7a16555b934483) |
| Artifact | 40 declared artifacts across 40 declarations (from MFA phone-set union of selected dictionaries through vietnamese_mfa dictionary v3.0.0) |
| Pin | `mfa-models@d6eff86a42c6a90b641e17dfdf7a16555b934483` |
| License | `CC-BY-4.0` |
| Kind | `dictionary-phone-set` |
| Declarations | `ipakit/data/bridges/mfa/*.xml` (40) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 40 |
| Finite inventories | 40 |
| Phone counts | 843 in `mfa` union; 35–182 across 39 scoped members |
| Pinned en-US dictionary phone types | 78 |
| Pinned en-US dictionary phone tokens | 452,813 |
| Pinned en-US dictionary at `min_entries=50` | 74 kept; 4 dropped |
| Pinned en-US marker-only entries | 4 |

### Qualitative

The language and variety members carry the phone sets of freely shared MFA pronunciation dictionaries, while the union provides a broad aligner-facing vocabulary.

**Conventions.** Dictionary tokens are segmented; each declared MFA phone becomes one house unit, with ties added when one MFA token is written by several IPA characters.

**Good at.** Use a language member with its matching aligner dictionary, and derive an attested inventory from a dictionary when token or entry weight matters.

**Less good at.** The family union combines doculects, while a declared member records membership rather than how broadly each phone is attested in its dictionary.

### Notes

- In the pinned en-US dictionary, the smallest frequency-ranked prefix reaching 99% of `452,813` phone tokens contains `58` of `78` phones.
- The low-attestation tail contains xenophones in loans and names, including `pʷ` in `8` entries and `ɡʷ` in `48`, alongside ordinary English allophony written for few eligible words; an entry cutoff locates this tail but cannot interpret it.
- `ɱ` occurs in `1` dictionary entry and `1` token, as an alternate for *infection*; it is labiodental assimilation, not a xenophone. Recording that assimilation for one word is a reasonable lexicographic judgment, while its rarity measures how often the variant was written rather than whether English has the sound.
- The `4` marker-only entries — `<cutoff>, <unk>, [bracketed], [laughter]` — serve the aligner rather than pronounce words, so dictionary ingestion excludes them from phone counts and reports each one.

## ZIPA / IPAPack++

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [ZIPA](https://github.com/lingjzhu/zipa/blob/d6f7cbc74b29ab7cb0248a5cf2d93f116d79721d/ipa_simplified/unigram_127.vocab) |
| Artifact | ipa_simplified/unigram_127.vocab |
| Pin | `lingjzhu/zipa@d6f7cbc74b29ab7cb0248a5cf2d93f116d79721d` |
| License | `MIT` |
| Kind | `recognizer-phone-vocabulary` |
| Declarations | `ipakit/data/bridges/zipa/zipa.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 108 |

### Qualitative

The pinned multilingual recognizer vocabulary reads ZIPA label streams and preserves the richer ties and word boundaries in IPAPack++ original transcriptions.

**Conventions.** The 108 base labels are finite phones, 15 bare diacritics attach as trailing marks, `▁` is a word boundary, and the three control labels are non-phone refusals.

**Good at.** Use it at ZIPA and IPAPack++ boundaries where the recognizer's token inventory and its projection losses must remain explicit.

**Less good at.** The vocabulary has no stress or tone, carries at most one diacritic per phone, omits five observed diacritics, and represents tied affricates as base sequences.

### Notes

- ASCII `g` maps to house `ɡ` only through this bridge; strict house IPA remains unchanged.

## Panphon

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [Panphon](https://github.com/dmort27/panphon) |
| Artifact | ipa_all.csv and feature_weights.csv |
| Pin | `0.22.2` |
| License | `MIT` |
| Kind | `phonetic-feature-table` |
| Declarations | `ipakit/data/feature-models/panphon.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Shipped feature models | 1 — named finite declaration; not a house style |
| Declared segment rows | 6367 |
| Declared features | 24 |
| Supplied feature weights | 22 |

### Qualitative

The shipped finite declaration supports model-relative operations and comparisons using Panphon's own feature geometry, without a runtime Panphon dependency or a mandatory house pivot.

**Conventions.** Its generated table preserves Panphon's ternary feature values, source spelling normalization, weight order, and declared round-trip losses. It is a named feature model, not a house notation style.

**Good at.** Use it to compare feature systems and cost policies on common inputs while keeping Panphon's own data visible and reproducible.

**Less good at.** It is a compatibility target rather than a correctness oracle: unsupported segments can be dropped by Panphon, and a ternary zero does not distinguish several kinds of underspecification.

### Notes

- The declaration contains `6367` segment rows over `24` features and `22` supplied weights; generation normalizes every segment key to NFD and refuses a duplicate normalized key.
- Feature and weight order differ at the tail, and the generated declaration retains that order instead of quietly repairing the comparison target.

<!-- SPDX identifiers checked: 50. -->
