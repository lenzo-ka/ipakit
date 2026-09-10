# Inventories and styles

<!-- Generated from docs/inventories.src.md and ipakit/data/inventory-cards.xml by scripts/inventory_cards.py. Do not edit: run `make inventory-cards`. -->

An `Inventory` binds a name to a `Style`, a provenance, and — where the notation has one — the finite `Phoneset` it carries, written in house IPA.

A `Style` is a strict boundary: `read()` turns one spelling from that notation into house IPA, and `spell()` turns one house-IPA phone back into that notation.

Card-bearing declaration roots state `upstream`, `upstream-url`, `artifact`, `version`, `license`, and `kind`; `Inventory.source.to_dict()` exposes those fields in a JSON-serializable form. `version` is the upstream source pin, with `unpinned` written explicitly when there is no pin. A declaration format that needs its own schema revision uses `declaration-version` instead. The human `Inventory.provenance` sentence is derived from these fields and is not stored beside them, so one fact has one spelling to keep current.

Use `inventories()` to list the shipped names and `inventory(name)` to load one; an unknown name is refused with the available names.

`ipa` is the house notation and finite shipped inventory, while `wild` is the soft IPA reader and has no finite phoneset.

CMUdict, PocketSphinx, TIMIT, MFA, bare `espeak`, and every declared eSpeak language are finite inventories; MFA has the union `mfa` and generated members `mfa:<name>`, while language-scoped eSpeak names have the form `espeak:en`.

Declared refusals are excluded from the phone count and available through `Inventory.refusals`; `inventory show` prints their spellings and reasons separately.

Bare `espeak` is the union of the phone names in every shipped eSpeak NG declaration, the vocabulary used by wav2vec2 eSpeak phoneme recognizers, while each `espeak:<code>` inventory retains its language's table.

The union style reads a name to its house-IPA spelling only where every declaration carrying that name agrees, while a name found in only one declaration reads through that declaration.

The union style spells with an agreed name, preferring the name carried by the most declarations, then the shortest, then the lexically first, and refuses a phone without one by naming each ambiguous candidate and its `espeak:<code>` meanings.

When mapping inventories, an entry its selected style cannot read is reported on its own side and makes the command fail rather than being respelled as a valid entry.

Inventory order is declaration order: XML atom order for bridges, phonemap row order for CMU and TIMIT, and `IPAFeatures().phones` order for `ipa`; the eSpeak union is the exception and uses sorted house IPA.

Finite inventories contain sounds. Their construction applies the declared silence-spelling rule `Phoneset.from_file()` applies.

The registry discovers its eSpeak, MFA, phonemap and bridge members from the declaration directories, so an added eSpeak or MFA declaration becomes visible without a name being written anywhere else.

[Praat TextGrid interchange](textgrid.md#label-styles) applies a named style strictly to segment labels and tier labels derived from them while retaining point marks in house notation.

Add a vocabulary inventory by placing its XML declaration under the matching bridge data directory; adapt the bridge only where its atom contract differs from `VocabularyBridge`. Notation-specific converters that cannot strictly read and spell one phone in both directions do not belong in this registry.

The `ipakit inventory` group inspects this named registry; `ipakit phoible inventory` selects a PHOIBLE doculect instead.

A pronunciation dictionary can declare an ordinary finite inventory through `inventory_from_dictionary(path, style)`, or through `ipakit inventory from-dict FILE --style STYLE`. CMUdict and PocketSphinx dictionaries use their shared CMUdict reader, MFA dictionaries use their `MFABridge` line syntax, and `ipa` and `wild` use word-plus-whitespace pronunciation lines. The phones retain dictionary order and exclude the declared silence spellings (`SIL` and the house `␣`). An MFA entry whose entire pronunciation consists of non-phone aligner markers (`<s>`, `</s>`, or `spn`) is a placeholder rather than a pronunciation: the reader excludes it and records its spelling and line-specific reason in `Inventory.refusals`. A marker mixed with a phone remains an unreadable phone and refuses the dictionary with its line and entry named, as does every other unreadable phone. `refuse_unreadable=True`, spelled `--refuse-unreadable` on the command line, applies that strict rule to marker-only placeholders too. `Inventory.counts` records both the number of phone tokens and the number of dictionary entries containing each phone, with repeated tokens in one entry contributing once to `entries`; the counts cover every successfully read nonsilence phone before an optional cutoff. A style that keeps stress reads a stressed dictionary phone as a stressed house unit (`AE1` as `ˈæ`), so the derived inventory lists stressed and unstressed vowels as distinct members, which is what the dictionary itself distinguishes. Under `pocketsphinx`, a dictionary carrying stress digits is refused rather than stripped; use `cmudict` to read stress-bearing dictionary phones.

The `min_entries` option, spelled `--min-entries N` on the command line, drops phones found in fewer than `N` dictionary entries and leaves the basic behavior unchanged when omitted. This cuts a low-attestation tail; it does not identify a phonemic or real inventory, distinguish a loanword phone from an under-written allophone, or remove a rule-generated allophone that clears the cutoff. `Inventory.dropped` names each caller-requested removal with both counts and stays separate from `Inventory.refusals`, because the dictionary reader accepted the phone. Text commands report drops on standard error so their one-phone-per-line output remains a phoneset, while JSON carries `counts` and `dropped` explicitly.

The command prints a one-phone-per-line house-IPA phoneset by default and reports placeholder refusals on standard error; `--spell native` selects the dictionary notation, and `-f json` reports both spellings, provenance, refusals, attestation counts, and requested drops. The output stays separate from mapping input, so a dictionary-to-MFA mapping is an explicit pipeline: `ipakit inventory from-dict lexicon.dict --style cmudict -o lexicon.phones && ipakit distance map lexicon.phones mfa`.

## Family cards

The cards group registry entries by family. A language or variety is an instance of its family, not a separate scorecard. Panphon appears only as the development comparison declaration generated from the `[dev]` dependency; it is neither a shipped inventory nor a style.

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
| Phone counts | 138 |

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
| Upstream | [TIMIT Acoustic-Phonetic Continuous Speech Corpus](https://catalog.ldc.upenn.edu/LDC93S1) |
| Artifact | TIMIT 61-phone-to-house-IPA phonemap |
| Pin | `LDC93S1` |
| License | `LicenseRef-LDC-TIMIT` |
| Kind | `speech-corpus-phone-map` |
| Declarations | `ipakit/data/phonemaps/timit.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 1 |
| Finite inventories | 1 |
| Phone counts | 50 |

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
| Artifact | 1.52.0 phsource phoneme tables; 1.52.0 phsource/phonemes and phsource/ph_english |
| Pin | `espeak-ng@4870adfa25b1a32b4361592f1be8a40337c58d6c` |
| License | `GPL-3.0-or-later` |
| Kind | `synthesis-phoneme-table` |
| Declarations | `ipakit/data/bridges/espeak/*.xml` (129) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Registry entries | 130 |
| Finite inventories | 130 |
| Phone counts | 560 in `espeak` union; 56–144 across 129 scoped members |

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

## Panphon (development comparison)

### Declared source

| Field | Value |
| --- | --- |
| Upstream | [Panphon](https://github.com/dmort27/panphon/tree/0.22.2) |
| Artifact | ipa_all.csv and feature_weights.csv |
| Pin | `0.22.2` |
| License | `MIT` |
| Kind | `phonetic-feature-table` |
| Declarations | `tests/panphon/panphon.xml` (1) |

### Quantitative

| Measure | Value |
| --- | ---: |
| Shipped registry entries | 0 — development comparison only |
| Declared segment rows | 6367 |
| Declared features | 24 |
| Supplied feature weights | 22 |

### Qualitative

The dev-only declaration is a comparison target for running Panphon's feature geometry through the same declared machinery as the house system.

**Conventions.** Its generated table preserves Panphon's ternary feature values, source spelling normalization, weight order, and declared round-trip losses without promoting it to a shipped style or inventory.

**Good at.** Use it to compare feature systems and cost policies on common inputs while keeping Panphon's own data visible and reproducible.

**Less good at.** It is a compatibility target rather than a correctness oracle: unsupported segments can be dropped by Panphon, and a ternary zero does not distinguish several kinds of underspecification.

### Notes

- The declaration contains `6367` segment rows over `24` features and `22` supplied weights; generation normalizes every segment key to NFD and refuses a duplicate normalized key.
- Feature and weight order differ at the tail, and the generated declaration retains that order instead of quietly repairing the comparison target.

<!-- SPDX identifiers checked: 176. -->
