# ipakit documentation

Start with the [tutorial](tutorial.md). Everything else here is reference or design, and
assumes you already know why you are reading it.

## Start here

| | |
| --- | --- |
| [tutorial.md](tutorial.md) | **Getting things done.** Organized by task — name a sound, compare two, search the inventory, convert notations, split a transcription, apply allophonic rules, write your own. Shows the CLI and the API side by side for each. Every value on the page is produced by running the call beside it. |

The tutorial is a **derived artifact**: the prose lives in `tutorial.src.md`, and
`make tutorial` regenerates the page by executing every example. `make check` fails if a
single byte differs, so the page cannot drift away from what the library does.

`ipakit notebook` writes the same material out as a Jupyter notebook, with the answers
left out for you to produce. `make notebook` renders it from `tutorial.src.md` into
`ipakit/notebooks/`, so it ships in the package and reaches a reader who has no
checkout; its cells are the blocks the page executes, which is what keeps the two
renderings from disagreeing.

## Reference — how the representation works

Read in this order if you are working on the library itself; dip in by name if you are
using it.

| | |
| --- | --- |
| [ties.md](ties.md) | **The unit model.** Tie bars, diacritics, what a `Segment` is made of, and why prosodic features live on the unit rather than in the feature bag. The foundation the other documents assume. |
| [form.md](form.md) | **The whole transcription.** `Form` is the reading that drops nothing; `segments` and `phones` are projections of it that each say what they drop. Boundaries versus attributes, and the tier tree. |
| [tone.md](tone.md) | **Pitch.** A contour is a *sequence of tone levels* rather than a value, so the diacritic and tone-letter spellings of one contour read as one thing; what a bare caron does not say; and where the IPA chart's tone-letter equivalents disagree with its own level column. |
| [rules.md](rules.md) | **The rewrite notation.** `A -> B / C _ D` in full: feature queries, boundaries and tiers, insertion and deletion, the trace, and the known limits — which are a queue, not a disclaimer. |
| [calculus.md](calculus.md) | **Form to *set* of forms.** What the optional arrow `A ~> B` opens: optionality per site, the closure and the identity, whether composition is associative and where the cap stops it, whether the set is finite, and how a truncation is reported. What the algebra cannot express is said near the top rather than in a footnote. |
| [distance.md](distance.md) | **What the metric claims.** How the distance is computed, its two real limits, and — stated plainly — that it does **not** satisfy the triangle inequality, with the uses that rules out. |
| [supplements.md](supplements.md) | **Extending the inventory.** Registering a sound `ipa.xml` does not: what that buys that composition already gives you and what it does not, what a supplemental file may declare, how it merges, what it does to `to_phone`'s choice of winner and to the reference distribution, and how to carry your own derived matrix. |

## Reference — the articulatory model

| | |
| --- | --- |
| [tract-anatomy.md](tract-anatomy.md) | The declared vocal-tract geometry: articulators, constrictions, the nasal branch, the jaw, and what the posture does and does not carry. |
| [tract-reference.md](tract-reference.md) | The labeled key to the mid-sagittal figures. |
| [tract-figures.md](tract-figures.md) | The figures in [figures/](figures/), what each shows, how `make figures` draws them, and how to draw your own — from Python, from a notebook, or from the command line. |
| [articulatory-data.md](articulatory-data.md) | The model measured against an external corpus (X-Ray Microbeam). What that corpus can ground, what it cannot see, and why its blind spots are facts about the instrument rather than about phonetics. |
| [gestural-model.md](gestural-model.md) | Design notes on the gestural reading, and the candidate improvements the metric would need external confusion data to fit. |

## Working on ipakit

| | |
| --- | --- |
| [reviewing.md](reviewing.md) | **Read this before changing anything.** How defects in this library have actually been found — every one a silent wrong answer under a green suite. Measure rather than predict; sweep rather than sample; make two things equal by construction. |
| [releasing.md](releasing.md) | The release checklist. |

## The shape of the repository

- `ipakit/` — the library. `ipakit/data/ipa.xml` is the feature declaration everything reads; `ipakit/data/rules/*.rules` are the shipped rule sets. Each XML document has a RELAX NG grammar beside it stating its shape — see [reviewing.md](reviewing.md).
- `ipakit/cli/` — the `ipakit` command. One subcommand group per task area.
- `ipakit/tract.py` — the tract model, read by the metric. `ipakit/tract_svg.py` draws it; they are separate so nothing that computes a distance can reach a stylesheet.
- `scripts/` — the measurements, the generators, and the documentation guards. `sweep.py` is the canonical corpus, `invariants.py` the data guards, `tutorial.py` the artifact generator, and `docexamples.py` checks every value quoted in the hand-written documents against what the library actually returns. `tract_svg.py` here is a command line over the package module, which is where the drawing itself lives, because `scripts/` reaches nobody who installed ipakit.
- `tests/` — the suite. `tests/corpus.py` is the one enumeration the sweeps share.

Derived artifacts are **regenerated, never hand-edited**: `docs/figures/*.svg`
(`make figures`), `docs/tutorial.md` (`make tutorial`),
`ipakit/notebooks/ipakit-tutorial.ipynb` (`make notebook`), `ipakit/data/confusion.json`
and the X-SAMPA table. `make check` runs every gate a release runs, and validates each of
those derivations still produces what is checked in.
