# Reviewing changes to ipakit

A record of how defects in this library have actually been found, written down because the method mattered more than any individual finding. Over six review rounds, thirty-three defects were fixed. **Every one was a silent wrong answer under a fully green test suite.** Not one was a crash.

That is the shape of the risk here. A phonetics library computes over data most callers cannot check by eye: nobody notices that `d(i, m̥) < d(i, m)`, or that `features("tʲ")` returned `{}`, or that a dental affricate tokenized as a cluster. The suite stays green because the wrong answer is well-formed. So the review method has to be built around producing evidence, not around reading code and forming an opinion.

## The failure modes this method exists to catch

Each of these happened, more than once.

**A test that exercises only the easy half.** A test pinned that a mark on a non-final constituent reaches the flat read — but parametrized only *additive* marks, which the trailing constituent does not state. The clobbering path for *overriding* marks was never taken. It passed for three rounds while the defect sat in the open.

**Asserting a consequence instead of measuring it.** A change was briefed as "this will move the matrix". It moved zero pairs of 9591: no registered phone spelled the affected symbols. The opposite has also happened — a change believed safe moved 3861 pairs.

**Fixing one thing and introducing another.** Making the flat projection apply every constituent's marks was right for additive marks and wrong for overriding ones, because the overlay ran after the merge and inverted the documented order. Two rounds later a reviewer found it.

**A guard that no longer guards.** The AST check for hardcoded phonetic constants missed seven shapes, including the key/value inversion of the very table it was written to reject. A guard that has quietly stopped covering a shape is worse than none, because it reads as protection.

**Documentation drifting away from behaviour.** Values quoted in prose went stale silently. Docstrings asserted invariants — *"these two are one read, not two"* — that had not been true for some time.

## What to do

### Measure, do not predict

Any change that could touch the metric gets a before/after over all 9591 pairs, and **every mover must be explained**. Not "the movement looks reasonable" — an actual account of which pairs moved and why the change reaches them. Unexplained movement is a finding, not noise.

```
pairs moved: 16 of 9591   max 0.0909
movers not involving ɚ/ɝ: 0
```

That second line is the one that matters. When it was not zero, it exposed a real mistake: eight derived diphthong entries had been given explicit features, silently disabling the derivation that keeps registered and composed values from drifting.

Fix `PYTHONHASHSEED` when measuring. The derived matrix is reproducible now, but a change that reintroduces set-ordered float summation will show up as a few hundred spurious movers at ~1e-16.

### Sweep, do not sample

Named cases test what you thought of. Prefer a sweep over generated input, and **assert the corpus size** so a silent collapse cannot make the test vacuous:

```python
assert checked > 500, "sweep did not run"
```

The strongest test in the suite builds every well-formed `base + mark + tie + base` the inventory can spell — every phone, every diacritic, both ties, **both mark positions** — keeps those that parse strictly and re-emit themselves, and compares whole bundles rather than one named key. Checked against the pre-fix tree it fails 28 named cases and 2 of 4 properties, on code that passed everything then shipped.

Where a sweep is too slow for the default run, sample deliberately and say so in the test.

### Use the one corpus, not your own

Six rounds rebuilt this sweep by hand, and the corpus drifted: two lanes a day apart reported 7921 and 8338 units, and neither could tell whether the other had a different inventory or a different definition. `scripts/sweep.py` is that enumeration written once, so counts from different lanes are comparable.

The canonical corpus is **every phone, and every phone + one diacritic, that spells itself back** — `segment(unit).to_ipa() == unit`. Today that is 139 bare + 7921 marked = 8060 units. It is defined that way rather than by strict parsing because strict parsing measures the parser's error policy as much as the inventory: that count moved 8618 -> 8340 when stress-mark binding changed, with no phone or diacritic touched, while re-emission held at 7921 across the same commits.

The workflow is three commands:

```
git switch main    && python scripts/sweep.py capture -o /tmp/before.json
git switch my-lane && python scripts/sweep.py capture -o /tmp/after.json
python scripts/sweep.py diff /tmp/before.json /tmp/after.json
```

`diff` accounts for every mover — appeared, disappeared, gained a word, lost a word, altered a word, features moved, distance-from-base moved — and checks the predicate two lanes wanted independently: no pre-existing word is lost or altered, only added. `--require-monotone` makes that gate the exit status. `sweep.py corpus` prints the definition, the counts, and the seven prosodic marks that compose with nothing, so that blind spot stays known rather than assumed shut.

The corpus total is deliberately not hardcoded: it has legitimately moved three times in this repo's history as the inventory changed. What the script asserts is shape — a floor, every phone contributing its bare unit, every phone contributing at least one marked unit, most marks contributing something — so a sweep cannot go quietly vacuous. The exact totals live in the capture, and a change in them is the first line `diff` prints.

### Write the guard as a predicate

A guard that lists today's offenders documents the present. A guard that describes the *shape* of the mistake catches the next one. Compare:

- ✗ assert `_MODE_EXCEPTIONS` is not in `segment.py`
- ✓ assert no module-level constant classifies two or more declared feature names in an unordered container

The same applies to data invariants. "No vowel may carry `retroflex`" is a class invariant over the whole inventory; "`ɚ` carries `rhotacized`" is a spot check.

### Make two things equal by construction

The most durable fixes in this codebase did not correct a value — they removed the possibility of disagreement.

Three independent copies of the secondary-articulation set lived in three modules and agreed only by habit; one of them drifted and `l` and `ɫ` came out identical. They are now one declaration in the data, read twice, so the mode partition and the metric's place table *cannot* disagree. Likewise `_SECONDARY_KEYS` is derived from `SECONDARY_PLACE` rather than maintained beside it, and the flat projection is one function rather than three implementations.

Prefer this to any amount of vigilance.

### Pin the escapes

When a guard cannot cover something, assert that it cannot, so the limit stays known rather than assumed shut:

```python
def test_the_guard_states_what_it_cannot_see(...):
    """If one of these starts being caught, this fails and the
    documented limits need updating."""
```

Coverage can then only change deliberately, in either direction.

### Let the data be wrong before the code is clever

Several defects were data errors wearing a code disguise. Clicks scored `d(p, ʘ) = 0` because they silently defaulted to a pulmonic airstream. Every vowel resolved `voiced="-"` because no vowel declared voicing and the binary default is `-`. R-colouring was spelled with two different features.

In each case correcting the data fixed the metric, and a weight or a special case would have hidden it. When a distance looks wrong, check what the data says before adjusting how it is compared.

### State what a measure does not claim

`distance` is symmetric, zero on identity and bounded, and it does **not** satisfy the triangle inequality — about 0.5% of triples violate it, some by a wide margin. That is documented, with the uses it rules out, because a caller reaching for a metric tree needs to know. See [distance.md](distance.md).

The general rule: an invariant worth relying on is worth a test, and one that does not hold is worth saying out loud.

## For an automated reviewer

Much of this review was done by delegated agents. What made that work:

- **Tell them to verify the brief, not implement it.** The most valuable agent output in this effort was contradiction: that a mark believed inert was load-bearing in the opposite direction; that a change believed matrix-moving moved nothing; that a third implementation existed which the brief treated as a bystander. A brief stated as fact gets implemented as fact.
- **Ask for the measurement, not the conclusion.** "Report the full before/after with every mover explained" produces evidence. "Check nothing broke" produces reassurance.
- **Say plainly that a clean report is an acceptable result.** Otherwise a reviewer under implicit pressure to produce findings will produce them, and the noise buries the signal in exactly the round where you most need to trust an empty answer.
- **Give one lane per agent, with the overlapping file named.** Conflicts are cheap to resolve and expensive to debug.

## Before a release

- `python -m pytest -q`
- `PYTHONHASHSEED=0 python scripts/confusion.py validate`
- `python scripts/sweep.py corpus` (the canonical corpus is intact)
- `python scripts/xsampa_table.py validate`
- `ruff check`, `black --check`, `mypy ipakit`
- The `CHANGELOG.md` **Unreleased** section names every breaking change, and every entry is one unwrapped line.
