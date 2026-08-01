# Contributing to ipakit

Issues, challenges and pull requests are all welcome, and so is the kind of contribution that contains no code at all.

Two sorts of people work on this library. One knows Python and wants the tests to pass. The other knows phonetics and can tell that `[pʰˈɪ̃n]` is right and that some other derivation is wrong. **Both are contributing, and the second is harder to replace.** This document tries to be readable to both: where something needs a command, the command is written out; where something needs a phonological judgment, no Python is required to offer it.

## Challenges are welcome — bring a measurement

Most projects cannot invite you to argue with their design, because they have nothing to settle the argument with. This one can.

**If you think a derivation, a distance, a feature bundle or a transcription convention is wrong, say so.** Open an issue, name your variety or your reference, and give the form you expect. That is a complete contribution. You do not have to write the fix.

The one thing we ask in return is that a change to *behavior* comes with a measurement rather than an argument from plausibility, because that is the only thing that has ever worked here. [docs/reviewing.md](docs/reviewing.md) is the record of why: across six rounds of review, **every single defect found was a silent wrong answer under a fully green test suite**. Not one was a crash. A phonetics library computes over data most callers cannot check by eye, so a wrong answer is well-formed, the suite stays green, and the only thing that catches it is evidence.

Read that document before changing anything. This file does not restate it; it tells you which parts of it apply to which kind of contribution.

## Getting set up

```bash
git clone https://github.com/lenzo-ka/ipakit
cd ipakit
pip install -e ".[dev]"     # or ".[test]" / ".[lint]" for a lean subset
pip install pre-commit && pre-commit install    # optional; runs the style tools on commit
make check
```

`make check` is the gate. It runs the style tools (`ruff`, `black --check`, `mypy --strict`), the test suite, the invariants, both data validators, the tutorial regeneration check, and the check on values quoted in the documentation. `.github/workflows/ci.yml` runs the suite across Python 3.11, 3.12 and 3.13, and the style tools and the derived-artifact guards on 3.12.

Run `make check` **before** you start as well as after. If it is already red on a clean tree, that is a finding in itself — please open an issue rather than working around it.

There are no runtime dependencies. The `dev` extra pulls a bundled ICU only so `scripts/xsampa_table.py` can re-derive the X-SAMPA table; `ipakit` itself never imports it.

## The method, in the two commands you will actually run

The full account is [docs/reviewing.md](docs/reviewing.md). The operational summary is this.

### Measure, do not predict

Any change that could touch the metric, the inventory, or how a unit is spelled gets a before/after over the whole corpus, and **every mover must be explained**. Not "the movement looks reasonable" — an account of which units moved and why your change reaches them. Unexplained movement is a finding, not noise.

```bash
git switch main       && python scripts/sweep.py capture -o /tmp/before.json
git switch my-branch  && python scripts/sweep.py capture -o /tmp/after.json
python scripts/sweep.py diff /tmp/before.json /tmp/after.json
```

Add `--require-monotone` to make "no pre-existing unit was lost or altered, only added" the exit status. `python scripts/sweep.py corpus` prints the corpus definition and today's counts.

Use `scripts/sweep.py` rather than rolling your own enumeration. That is not fussiness: six review rounds each rebuilt the same sweep by hand and the corpus drifted, until two people a day apart reported 7921 and 8338 units and neither could tell whether the other had a different inventory or a different definition. `sweep.py` is that enumeration written once, so two people's numbers are comparable. It re-execs itself under `PYTHONHASHSEED=0`, so you do not have to remember; `scripts/invariants.py` does not, which is why the `Makefile` sets it.

Paste the diff summary into the pull request. A measurement showing that **nothing** moved is a good result and worth reporting.

### Sweep, do not sample

Named cases test what the author thought of. Where you can, prefer a sweep over generated input, and assert the size of what you swept so a silent collapse cannot make the test vacuous:

```python
assert checked > 500, "sweep did not run"
```

`tests/corpus.py` is the shared enumeration for tests. Where a sweep is too slow for the default run, sample deliberately and say so in the test.

## Three house rules

### 1. Put the phonetics in the data

**Declare a phonetic fact in `ipakit/data/ipa.xml` and derive from it. Do not smuggle it into Python.**

This is the rule most likely to reject a first patch, so it is worth knowing before you write code. A set of feature names, a symbol-to-behavior table, a list of "the secondary articulations", a mapping from a value to a label — if it states a fact about speech sounds, it belongs in the data, where it is declared once and read wherever it is needed. Three separate copies of the secondary-articulation set once lived in three modules and agreed only by habit; one drifted, and `l` and `ɫ` came out identical.

`tests/test_declared_not_hardcoded.py` enforces this, and it is a **predicate over the source**, not a list of today's offenders: it looks for the shape of a smuggled constant, so a new one fails too. Read its docstring — it explains what the guard looks for and, deliberately, what it cannot see.

The corollary for adding a phonetic fact: the change is usually an edit to `ipa.xml` plus a regenerated artifact, and only rarely a change to `ipakit/*.py`.

### 2. Registered wins; composition is the fallback

This is the working rule for *when to add XML at all*.

**Reading** resolves a registered symbol first, and composes on the fly otherwise. `q͡χ` is not in `ipa.xml`, and `describe("q͡χ")` is still "voiceless uvular affricate", because a tie-joined sequence of known phones composes. **Writing** does the same in the same order — the rule engine tries `respell`, which only ever returns a registered symbol, before `compose_unit`, which builds a spelling out of the marks that declare the value:

```python
f.respell("l", velarized="+")             # 'ɫ'    -- registered wins
f.compose_unit("l", velarized="+")        # 'lˠ'   -- what composition would have said
f.respell("t", release="aspirated")       # None   -- tʰ is not registered
f.compose_unit("t", release="aspirated")  # 'tʰ'   -- so composition serves it
```

So **composition already covers the long tail, and registering a compound is not how you make it work — it is how you make it findable.** Only registered phones are:

- enumerated by `phones_matching` and `ipakit query match` (`ipakit query match affricate uvular` reports no match, though `q͡χ` composes perfectly well);
- in the candidate set for `nearest_phones` and `minimal_pairs`;
- rows and columns of `ipakit/data/confusion.json`;
- able to carry an alias spelling (`ʧ` reads as `t͡ʃ`) and a reference `href`;
- the canonical form `from_wild` normalizes a wild spelling to (`from_wild("t͜s")` is `t͡s`).

**Register** a compound that a user would expect to *find* — a phone of the IPA chart, or one that a standard inventory or a common transcription convention treats as a unit, or one with a ligature spelling that should normalize. `p͡f`, `t͡ɕ`, `t͡s` are registered for that reason. **Do not register** a chain that composition already spells correctly and that nobody would look up. `q͡χ` being absent is the intended state, not an omission.

Two things to know before you add one:

- **A registered tied entry carries no feature attributes.** Its features are derived at load, by the same composer that serves unregistered chains, under the entry's tie sense. Registration is a *cache* of composition, so the two cannot drift; `tests/test_tie_convergence.py` fails if you hand-encode features onto a tied entry. Give it a spelling, its aliases and its `href`, and let the loader do the rest.
- **Registering changes the inventory, so it is a measured change.** `distance()` is absolute and inventory-independent, and will not move. `normalized_distance()`, `confusability()` and every model built on them are **percentiles within the loaded inventory**, so adding a single phone moves them for *every* pair. `ipakit/data/confusion.json` must be regenerated in the same commit, and a sweep before/after belongs in the pull request.

### 3. Derived artifacts are regenerated, never hand-edited

Several files in the tree are outputs. Editing one by hand produces a change that looks fine in review and fails `make check`.

| Artifact | Regenerate with | Guarded by |
| --- | --- | --- |
| `docs/tutorial.md` | `make tutorial` (source is `docs/tutorial.src.md`) | `python scripts/tutorial.py check` — byte-identical |
| `ipakit/data/confusion.json` | `python scripts/confusion.py generate --write` | `python scripts/confusion.py validate` |
| `ipakit/data/phonemaps/xsampa.xml` | `python scripts/xsampa_table.py generate --write` (the flag warns that it drops the file's hand grouping and comments — restore them) | `python scripts/xsampa_table.py validate` |
| `docs/figures/*.svg` | `make figures` | `tests/test_tract_figures.py` |

The tutorial deserves a note of its own, because it is the page a newcomer is most likely to want to fix. **Every value on it is produced by executing the call beside it**, and the byte-identical comparison *is* the test. So a correction goes in `docs/tutorial.src.md` and then `make tutorial`; a hand-edit to `docs/tutorial.md` will be overwritten and will fail the gate on the way.

Values quoted in the hand-written documents (`README.md` and `docs/*.md`) are checked too, by `scripts/docexamples.py`. Documentation drifting away from behavior is a recurring failure mode here, not a hypothetical one.

## What you might be contributing

### A defect report, or a phonological challenge

No code needed, and these are among the most valuable things the project receives. Pick the matching template under **New issue**.

For a defect, please give **the command and its output** rather than a description of them. "`ipakit describe tʲ` prints X, I expected Y" can be acted on immediately; "descriptions of palatalized stops seem wrong" takes a round trip to reach the same place.

For a challenge to a derivation — "this is not what my variety does" — the template asks for the variety or reference and the form you expect. You are the evidence here; the numbers are our job.

### A phone, a diacritic, or a correction to `ipa.xml`

Read house rules 1 and 2 first. Then:

1. Make the edit in `ipakit/data/ipa.xml`. A phone declares its features as attributes; a diacritic declares the features it contributes, and **its mode is read off those features** — a mark is a release phase because it declares `release=…`, and a secondary articulation because it declares a feature whose mode is `secondary`. There is no per-symbol exception table, and adding one will be rejected by the guard.
2. Capture a sweep before and after (see above).
3. Regenerate `confusion.json`, and the X-SAMPA table if the symbol has an X-SAMPA spelling.
4. `make check`.
5. In the pull request, say what the fact is and where it comes from — a reference, a chart, a description. Data errors have worn a code disguise here more than once, so the provenance matters more than the diff.

Correcting an existing value is as welcome as adding a new one. Several of the strongest fixes in this repository were data errors: clicks scored zero distance from plosives because they silently defaulted to a pulmonic airstream, and every vowel resolved as voiceless because no vowel declared voicing.

### A rule set

The shipped sets in `ipakit/data/rules/*.rules` are **data, not code**. Adding one needs the rewrite notation ([docs/rules.md](docs/rules.md)) and knowledge of a language, and no Python at all.

```bash
ipakit rules apply -s american-english "pˈɪn"    # pʰˈɪ̃n
ipakit rules trace -s american-english "bˈʌtɚ"   # which rule fired, and where
```

What a good rule set looks like here:

- **The file argues its choices in prose.** Read `ipakit/data/rules/german-final-devoicing.rules` as the model. It is one rule, and most of the file explains why the condition is a syllable coda (`_ .`) rather than a word edge (`_ #`), with the four forms that distinguish the two formulations written out. A set that states what it does without saying why is half a contribution.
- **The file records the traps.** Each shipped set names a spelling that looks right and fails silently, and `tests/test_rule_sets.py` pins those, so the warnings cannot go stale while still being read as warnings.
- **The tests assert whole derived forms**, not "something changed". A mis-ordered cascade, a bled literal or an epenthetic vowel of the wrong quality all produce well-formed IPA that only a reader who knows the language can see is wrong. Add your derivation table to `tests/test_rule_sets.py`, one line per word.
- **Say which orderings are load-bearing**, and expect that claim to be measured: the tests permute the named dependencies and sweep every pairwise transposition.

New sets are chosen for what they force the notation to do at least as much as for the language. If a set exercises an operation or a context shape nothing shipped exercises yet, say so — that is the argument for merging it.

### A change to the rewrite engine, the metric, or the parser

The measured path, in full: read [docs/reviewing.md](docs/reviewing.md), sweep before and after, explain every mover, and add the test as a predicate over a swept corpus rather than as a named case.

Two specific warnings from that document. A guard that lists today's offenders documents the present; write one that describes the *shape* of the mistake. And where a guard cannot cover something, add a test asserting that it cannot, so the limit stays known rather than assumed shut.

### A documentation change

Prose fixes are welcome and need no measurement — with the two exceptions above: `docs/tutorial.md` is generated from `docs/tutorial.src.md`, and any value you quote in `README.md` or `docs/*.md` will be executed and compared by `scripts/docexamples.py`.

## Sending the change

Work on a branch; do not commit to `main`.

**Commits.** A lowercase area prefix, then a sentence saying what changed and, where it is not obvious, *why*. The log reads as prose:

```
rules: say it about the syllable, not about the segment beside it
data: say which symbols are not on the chart, and keep it out of the bag
compose: answer the question asked, or answer nothing
```

**`CHANGELOG.md`.** Add an entry under **Unreleased** for anything a user would notice. One unwrapped line per entry — no hard line breaks inside a bullet. Mark a change to existing behavior **Breaking**, a change to the shipped data **Breaking, data**, and a rename **Breaking, naming**.

**The pull request** should say:

- what changed and why;
- the measurement, if the change could touch the metric, the inventory or a spelling — the sweep diff summary, with every mover accounted for;
- that `make check` is green, and on what Python;
- anything you found that contradicts the documentation. That is a finding, and we would rather have it in the PR than not at all.

There is no CLA to sign. Contributions are accepted under the project's [BSD 2-Clause license](LICENSE).

**First contribution?** A typo fix, a clearer sentence, or one wrong derivation reported carefully are all real contributions, and none of them require you to understand the rest of this document. Say in the issue or PR that it is your first — it changes nothing about how the change is judged, but it tells us to explain rather than assume.

## Where things live

- `ipakit/` — the library. `ipakit/data/ipa.xml` is the feature declaration everything reads; `ipakit/data/rules/*.rules` are the shipped rule sets; `ipakit/cli/` is the `ipakit` command; `ipakit/tract.py` is the tract model and `ipakit/tract_svg.py` draws it.
- `tests/` — the suite. `tests/corpus.py` is the one enumeration the sweeps share.
- `scripts/` — the measurements, the generators and the documentation guards. `sweep.py` is the canonical corpus, `invariants.py` the properties the library is supposed to hold, `confusion.py` / `xsampa_table.py` / `tutorial.py` the artifact generators, and `docexamples.py` the check on quoted values. `tract_svg.py` here is a shim over the package module and holds no drawing of its own: `scripts/` ships in neither the wheel nor the importable half of the sdist, and an installed ipakit has to be able to draw.
- `docs/` — [docs/README.md](docs/README.md) is the index, and says what each document is for and the order to read them in.

## Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Disagreement about phonetics is expected and welcome; the standard is that you argue with the claim.
