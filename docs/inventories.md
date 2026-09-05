# Inventories and styles

An `Inventory` binds a name to a `Style`, a provenance, and — where the notation has one — the finite `Phoneset` it carries, written in house IPA.

A `Style` is a strict boundary: `read()` turns one spelling from that notation into house IPA, and `spell()` turns one house-IPA phone back into that notation.

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

Add a vocabulary inventory by placing its XML declaration under the matching bridge data directory; adapt the bridge only where its atom contract differs from `VocabularyBridge`. Notation-specific converters that cannot strictly read and spell one phone in both directions do not belong in this registry.

The `ipakit inventory` group inspects this named registry; `ipakit phoible inventory` selects a PHOIBLE doculect instead.

A pronunciation dictionary can declare an ordinary finite inventory through `inventory_from_dictionary(path, style)`, or through `ipakit inventory from-dict FILE --style STYLE`. CMUdict and PocketSphinx dictionaries use their shared CMUdict reader, MFA dictionaries use their `MFABridge` line syntax, and `ipa` and `wild` use word-plus-whitespace pronunciation lines. The phones retain dictionary order, exclude the declared silence spellings (`SIL` and the house `␣`), and refuse other aligner markers (`<s>`, `</s>`, and `spn`) as unreadable phones; an unreadable phone names its line and entry rather than being dropped. A style that keeps stress reads a stressed dictionary phone as a stressed house unit (`AE1` as `ˈæ`), so the derived inventory lists stressed and unstressed vowels as distinct members, which is what the dictionary itself distinguishes. Under `pocketsphinx`, a dictionary carrying stress digits is refused rather than stripped; use `cmudict` to read stress-bearing dictionary phones.

The command prints a one-phone-per-line house-IPA phoneset by default; `--spell native` selects the dictionary notation, and `-f json` reports both spellings and provenance. The output stays separate from mapping input, so a dictionary-to-MFA mapping is an explicit pipeline: `ipakit inventory from-dict lexicon.dict --style cmudict -o lexicon.phones && ipakit distance map lexicon.phones mfa`.
