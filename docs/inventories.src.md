# Inventories and styles

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
