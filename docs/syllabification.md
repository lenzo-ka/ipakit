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

The syllable tier is grouped over the mora tier: a moraic syllable is a concatenation of morae, and material no declared mora licenses is reported rather than absorbed into a syllable.

```python
import ipakit

ja = ipakit.syllabifier("japanese")
ja("pen").spelled(), len(ja("pen").morae)       # (("pen",), 2)
ja("hotːo").spelled(), len(ja("hotːo").morae)   # (("ho", "tːo"), 3)
ja("atɾa").spelled(), ja("atɾa").unsyllabified  # (("a", "ɾa"), ((1, 2),))
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

Those same constraints validate margins at word edges as well as between nuclei. Thus `stan` becomes `tan`, with the initial `s` reported as unsyllabified: word-initial `/st/` is the classic Spanish impossibility that motivates epenthesis. A language that declares coda spans gets the symmetric validation at its right edge; declaring no codas, as Spanish currently does, leaves codas unconstrained.

Untied vowel units are separate nuclei and tied vowel sequences remain one unit, leaving diphthong versus hiatus where the transcription and nucleus machinery put it.

```python
es = ipakit.syllabifier("spanish")
es("poeta").spelled()           # ("po", "e", "ta")
es("los‿otɾos").spelled()       # ("lo", "s‿o", "tɾos")
es("los‿otɾos").marks()         # "lo.s‿o.tɾos"
es("stan").spelled(), es("stan").unsyllabified  # (("tan",), ((0, 1),))
```

The checked demonstration has 5 forms, 12 syllables, and 1 conflict; the conflicting `at.ɾa` is honored while the report records Spanish's freely derived `a.tɾa`.

## 6. English: the curation loop is the declaration

English uses the same constraints mechanism, but its clusters come from data rather than a universal onset table.

`scripts/syllable_curation.py` reads a corpus produced by `ingest_cmudict`, harvests every word-initial consonant sequence with its frequency and exemplars, derives the sonority model from the declared `manner` constriction coordinates and `obstruent` class, and writes both `english.xml` and the dated report in `docs/data/`; both outputs say not to edit them by hand.

The full 2026-08-11 run used CMUdict commit `74790861f652b15e4ac49015a90074ad62a27690`, accepted 135,166 forms with no ingest refusals, and produced this attestation grid:

| Constraint classification | Attested | Unattested declared gap |
|---|---:|---:|
| legal | 89 | 1 singleton constraint |
| illegal, requiring curation | 61 | — |

The queue resolved to 18 native exceptions, 1 borrowing, 39 marginal entries, and 3 explicit transcription-noise refusals.

The four recorded iterations are the constraint baseline, native exceptions, borrowings, and marginal evidence; their inventory deltas and changed-form counts are recorded in the generated report rather than summarized from memory.

Strictness names admitted labeled strata: `strict` admits `native`, `permissive` admits `native+borrowing+marginal`, and the default admits all three; an unlabeled onset is core and is admitted at every strictness, so the three declarations from phase 1 behave exactly as before.

`/ʃm/` is the canonical exhibit: CMUdict supplies 66 word-initial tokens, led by *schmader*, and curation retains the productive Yiddish/German pattern as a borrowing.

```python
strict = ipakit.syllabifier("english", strictness="strict")
permissive = ipakit.syllabifier("english", strictness="permissive")
strict("ʃmˈɑlts").spelled(), strict("ʃmˈɑlts").unsyllabified
# (("mˈɑlts",), ((0, 1),))
permissive("ʃmˈɑlts").spelled(), permissive("ʃmˈɑlts").unsyllabified
# (("ʃmˈɑlts",), ())
strict("ŋtˈɑ").spelled(), strict("ŋtˈɑ").unsyllabified
# (("tˈɑ",), ((0, 1),))
```

The stressed `/ɑ/` is a nucleus in both demonstrations, and the final control shows the same no-absorption property as the other languages: the unlicensed initial `/ŋ/` is reported rather than folded into the following syllable.

The ipa-dict en_US cross-check used commit `43c3570eb3553bdd19fccd2bd0091534889af023`: all 125,927 entries were shared.  The comparison re-seated syllable-initial stress on the following nucleus in 128,670 pronunciation forms, without changing the bridge's stored forms.  After that explicit normalization, 35,977 words agree and 89,950 disagree.  `normalize()` is not a word-level diphthong detector—its whitespace groups assert whole units—so no diphthong tying was applied; that remains the normalize tie-report follow-up.

The residual disagreements are separated by cause.  Stress-seat contributes 0 after normalization.  Untied-diphthong nucleation contributes 18,966: for example *'bout* is `bˈa͜ʊt` against `bˈa.ʊt`, and diagnostic tying of the registered vowel pair removes the difference.  Genuine boundary differences contribute 1,511: *aardvark* is `ˈɑɹ.dvˌɑɹk` against `ˈɑɹd.vˌɑɹk` with otherwise identical forms.  The other 69,473 retain a segmental, prosodic, or unclassified transcription difference; examples include *'til* (`tˈɪl` against `tˈɪɫ`) and *'twas* (`twˈʌz` against `twˈəz`).  Thus the boundary bucket, rather than the old convention-dominated total, is the syllabification evidence exposed by this cross-check.

## 7. Disagreement is the evidence

One IPA string produces three honest answers:

| Language | `/atɾa/` |
|---|---|
| Japanese | `a.ɾa`; `t` is reported as unlicensed residue |
| Mandarin | no member; unsyllabified |
| Spanish | `a.tɾa`; margins validated medially and at word edges |

The difference is the point: the moraic declaration reports residue, the enumeration refuses the form wholesale, and the constraints declaration syllabifies exactly what its derived margins license, reporting edge residue such as the `s` of `stan`. Three analyses produce three different honest behaviors without hiding any of them in Python.

## 8. Metric firewall

The 139-phone upper triangle contains 9,591 pairs; this lane moved 0, the stored fingerprint still equals the derived fingerprint, and `confusion.json` was byte-unchanged at the SHA-256 it carried while this lane ran, `f490f57876f92f9275eb9916c7ac199fad230e3463d665135059b93b53e9ef61`. That hash is no longer the file's: `7387c16` deliberately charged fusion constituent arity, changed `ipakit/metric.py`, and regenerated the artifact to `560cfcd8bca23d7d787e38c8a9515c192603197c4c347a58b149cbc450936d51`. The claim above is what this lane verified, against the file as it then stood; the later move is a different change and not a breach of this firewall.

The live control changed the declared plosive offset from `1.00` to `0.99` in a temporary inventory, made the same instrument report 4,325 movers, and then vanished with the temporary file.

Sonority never entered these three derivations or the metric.

## 9. Limits

The English declaration is a claim about the pinned CMUdict version, not a universal English inventory; rerunning the generator on another lexicon version is expected to reopen its curation queue.
