# Basic use of ipakit

<!-- Generated from tutorial-basics.src.md by scripts/tutorial.py. Do not edit: run `make tutorial-basics`. -->

This tutorial begins with a transcription and follows it through questions and
a sound change. It assumes some phonetics and enough Python to read a function
call. Every value shown here comes from running the code beside it.

## 1. Read a form

`read` parses a transcription into a `Form`: the value ipakit uses to keep its
spelling and structure together.

```python
import ipakit as ipa

form = ipa.read("t͡ʃãpat͡ʃa")
form.to_ipa()  # 't͡ʃãpat͡ʃa'
[unit.text for unit in form.units]  # ['t͡ʃ', 'ã', 'p', 'a', 't͡ʃ', 'a']
len(form.units), len(form.to_ipa())  # (6, 11)
```

The tie makes `t͡ʃ` one unit, and the nasal mark stays on its `a`. Unicode needs
more than one character to spell each of them; the representation already
knows where the segments are. This is the [house-style convention for tied
units](house-style.md#ties-are-units).

## 2. Ask questions

Queries can name one segment, a class, or an environment. A match gives back
the text of the unit as the form read it, so the answer keeps the input's
diacritics and ties.

```python
def matches(spec):
    return [match.text for match in ipa.corpus.find(form, spec)]

matches("t͡ʃ")  # ['t͡ʃ', 't͡ʃ']
matches("[vowel]")  # ['ã', 'a', 'a']
matches("[manner=plosive] / [vowel] _ [vowel]")  # ['p']
```

The underscore is the position being sought: the last query asks for a
plosive between vowels. Literal and bracketed targets use the same structural
search.

## 3. Features and classes

The feature bundle states why the class query found /p/. Defaults fill in the
inventory's ordinary assumptions; `with_defaults=False` shows only what this
phone declares.

```python
ipa.features("p", with_defaults=False)
# {'manner': 'plosive', 'place': 'bilabial', 'href':
# 'Voiceless_bilabial_plosive', 'class': 'phone'}
ipa.phones_matching(["plosive", "bilabial"])  # ['b', 'p', 'ɓ', 'ʘ']
```

The inventory also documents the basis it computes from. Feature definitions
carry descriptions, and phone declarations carry outbound references; these
are data rather than parallel prose.

```python
inventory = ipa.load_ipa_features()
inventory.features["manner"].desc  # 'How airflow is constricted'
ipa.wiki("t͡ʃ")
# 'https://en.wikipedia.org/wiki/Voiceless_postalveolar_affricate'
```

The [self-documentation convention](house-style.md#self-documentation) explains
why those descriptions and references live with the declarations.

## 4. Rewrite

A rewrite uses the same bracketed class and the same environment notation. This
rule voices a plosive between vowels. `derive` keeps the account of what it did.

```python
rule = ipa.rule("[manner=plosive] -> [voiced=+] / [vowel] _ [vowel]")
derivation = ipa.derive("atapa", rule)
derivation.trace()
# 'atapa\n  [manner=plosive] -> [voiced=+] / [vowel] _ [vowel]\n
# [manner=plosive] -> [voiced=+] / [vowel] _ [vowel]: t -> d @1,
# [manner=plosive] -> [voiced=+] / [vowel] _ [vowel]: p -> b @3\n  = adaba'
derivation.result  # 'adaba'
```

Both eligible plosives change in one application. Rule application is global
by default, a convention shared with the expression grammar described in
[house style](house-style.md#for-readers-who-know-regex).

## 5. Words and boundaries

In ordinary transcription, a space spells a word boundary. The source spelling
is retained, while structural queries see the boundary unit described by the
[house-style convention](house-style.md#space-spells-the-word-boundary).

```python
phrase = ipa.read("ata aka")
phrase.to_ipa()  # 'ata aka'
[unit.text for unit in phrase.units]  # ['a', 't', 'a', '#', 'a', 'k', 'a']
[match.text for match in ipa.corpus.find(phrase, "[vowel] / _ #")]
# ['a', 'a']
```

The query finds the vowel at the end of each word. It stops at the boundary
rather than treating the phrase as one uninterrupted segment sequence.

## 6. Where to go next

The [house style](house-style.md) gives the reasons for the writing conventions
used here. The [documentation index](README.md) leads to the representation,
query, and rule references; its start page also links the executable task-based
[tutorial](tutorial.md) for a wider tour of the current library.
