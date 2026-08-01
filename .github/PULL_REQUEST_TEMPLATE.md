<!--
Thanks for contributing. CONTRIBUTING.md has the long version; this is the short one.
Delete any section that does not apply — an empty heading is worse than no heading.
-->

## What this changes, and why

<!-- The why matters more than the what; the diff already says the what. -->

## The measurement

<!--
Required if this could touch the metric, the inventory, or how a unit is spelled.
Not required for prose, comments, typing, or tooling.

    git switch main       && python scripts/sweep.py capture -o /tmp/before.json
    git switch my-branch  && python scripts/sweep.py capture -o /tmp/after.json
    python scripts/sweep.py diff /tmp/before.json /tmp/after.json

Paste the summary. Every mover needs an account of *why this change reaches it* —
unexplained movement is a finding, not noise. "Nothing moved" is a good result and
is worth reporting; a change briefed as matrix-moving once moved zero pairs.
-->

```
```

## Checks

- [ ] `make check` is green (say on which Python if it is not 3.12)
- [ ] Phonetic facts are declared in `ipakit/data/ipa.xml`, not in Python constants
- [ ] Derived artifacts are regenerated rather than hand-edited — `docs/tutorial.md` via `make tutorial`, `confusion.json` via `scripts/confusion.py generate --write`, the X-SAMPA table via `scripts/xsampa_table.py generate --write`, figures via `make figures` (see the table in CONTRIBUTING.md)
- [ ] `CHANGELOG.md` has an entry under **Unreleased**, one unwrapped line, marked **Breaking** if it changes existing behavior
- [ ] New tests sweep rather than sample where they can, and assert what they swept

## Anything that contradicts the documentation

<!--
If you found that a document says something the library does not do, put it here even
if you did not fix it. Documentation drifting away from behavior is a recurring
failure mode in this repository, and a contradiction found is worth more than a
contradiction quietly worked around.
-->
