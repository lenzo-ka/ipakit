# Language-relative syllabification

## 1. The constructor, not a universal syllabifier

`syllabifier(language)` reads a language declaration and returns a `Form → Intervals` mechanism.

The declarations live in `ipakit/data/syllables/` because nucleus, margin, and mora claims are phonology rather than rewrite operations; the RELAX NG grammar beside them makes that boundary executable, while Mandarin's members remain in the Pinyin bridge that owns the syllabary.

Span expressions use the landed rule vocabulary, including shared agreement variables, and do two jobs: a matching span validates a candidate and the first matching suffix locates its edge.

The result writes `syllable` intervals and, for Japanese, `mora` intervals; `marks()` is only the text fallback.

## 2. Evidence already in the transcription

A written `.` fixes an edge and derivation resumes on either side; the free derivation is still run and a disagreement becomes a `Conflict`.

A `#` blocks a syllable, while `‿` is deliberately crossable; stress rides a unit and therefore makes that unit a nucleus even if a language's ordinary nucleus query does not reach it.

No boundary is rebuilt or replaced, so a dot beside a richer carrier keeps the carrier's `level` and `features` intact.

## 3. Japanese: morae first

The Japanese declaration restates the analysis in `japanese-moraic.rules`: `(C)(j)V`, an independent nasal mora, a geminate's first half, a second mora for a long vowel, and one unit for a tied diphthong.

```python
import ipakit

ja = ipakit.syllabifier("japanese")
ja("pen").spelled(), len(ja("pen").morae)       # (("pen",), 2)
ja("hotːo").spelled(), len(ja("hotːo").morae)   # (("ho", "tːo"), 3)
```

The checked demonstration has 4 forms, 6 syllables, 9 morae, and 0 conflicts.

## 4. Mandarin: membership is the analysis

Mandarin is the strict endpoint: the constructor reads the IPA members owned by `pinyin.xml`, chooses the longest declared member, and refuses a residue rather than repairing it.

Tone is absent from membership because it rides the syllable unit.

```python
cmn = ipakit.syllabifier("mandarin")
cmn("ma˥ma˨˩˦").spelled()       # ("ma˥", "ma˨˩˦")
cmn("mla").unsyllabified        # ((0, 3),)
```

The checked demonstration has 3 valid forms, 5 syllables, and 0 conflicts; the refusal control adds 1 unsyllabified form.

## 5. Spanish: margins without an attestation list

Spanish declares any single consonant and obstruent-plus-liquid clusters as onsets, so onset maximization derives the inventory from constraints alone; no attestation list was needed.

Untied vowel units are separate nuclei and tied vowel sequences remain one unit, leaving diphthong versus hiatus where the transcription and nucleus machinery put it.

```python
es = ipakit.syllabifier("spanish")
es("poeta").spelled()           # ("po", "e", "ta")
es("los‿otɾos").spelled()       # ("lo", "s‿o", "tɾos")
es("los‿otɾos").marks()         # "lo.s‿o.tɾos"
```

The checked demonstration has 5 forms, 12 syllables, and 1 conflict; the conflicting `at.ɾa` is honored while the report records Spanish's freely derived `a.tɾa`.

## 6. Disagreement is the evidence

One IPA string produces three honest answers:

| Language | `/atɾa/` |
|---|---|
| Japanese | `at.ɾa` |
| Mandarin | no member; unsyllabified |
| Spanish | `a.tɾa` |

The difference is the point: one constructor bends to a moraic declaration, an enumeration, and derivable margins without hiding any of them in Python.

## 7. Metric firewall

The 139-phone upper triangle contains 9,591 pairs; this lane moved 0, the stored fingerprint still equals the derived fingerprint, and `confusion.json` remains byte-unchanged at SHA-256 `aecabe393e38b23dd23f6dbb44b11226bb34a7839f103f709890de432f7827bb`.

The live control changed the declared plosive offset from `1.00` to `0.99` in a temporary inventory, made the same instrument report 3,251 movers, and then vanished with the temporary file.

Sonority never entered these three derivations or the metric.

## 8. Limits

English, lexicon harvesting, curation deltas, strata, and their inspection loop are phase 2 and are not present here.
