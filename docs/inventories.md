# Inventories and styles

An `Inventory` binds a name to a `Style`, a provenance, and — where the notation has one — the finite `Phoneset` it carries, written in house IPA.

A `Style` is a strict boundary: `read()` turns one spelling from that notation into house IPA, and `spell()` turns one house-IPA phone back into that notation.

Use `inventories()` to list the shipped names and `inventory(name)` to load one; an unknown name is refused with the available names.

`ipa` is the house notation and finite shipped inventory, while `wild` is the soft IPA reader and has no finite phoneset.

CMUdict, PocketSphinx, TIMIT, MFA, bare `espeak`, and every declared eSpeak language are finite inventories; language-scoped eSpeak names have the form `espeak:en`.

Bare `espeak` is the union of the phone names in every shipped eSpeak NG declaration, the vocabulary used by wav2vec2 eSpeak phoneme recognizers, while each `espeak:<code>` inventory retains its language's table.

The union style reads a name to its house-IPA spelling only where every declaration carrying that name agrees, while a name found in only one declaration reads through that declaration.

The union style spells with an agreed name, preferring the name carried by the most declarations, then the shortest, then the lexically first, and refuses a phone without one by naming each ambiguous candidate and its `espeak:<code>` meanings.

Inventory order is declaration order: XML atom order for bridges, phonemap row order for CMU and TIMIT, and `IPAFeatures().phones` order for `ipa`; the eSpeak union is the exception and uses sorted house IPA.

Finite inventories contain sounds. Their construction applies the declared silence-spelling rule `Phoneset.from_file()` applies.

The registry discovers its eSpeak, phonemap and bridge members from the declaration directories, so an added eSpeak declaration makes its language visible without a name being written anywhere else.

Add a vocabulary inventory by placing its XML declaration under the matching bridge data directory; adapt the bridge only where its atom contract differs from `VocabularyBridge`. Notation-specific converters that cannot strictly read and spell one phone in both directions do not belong in this registry.

The `ipakit inventory` group inspects this named registry; `ipakit phoible inventory` selects a PHOIBLE doculect instead.
