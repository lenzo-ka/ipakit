"""One enumeration of the sweep corpus, imported rather than rebuilt.

``docs/reviewing.md`` records what happens otherwise: six review rounds
rebuilt a sweep by hand and the corpus drifted, with two lanes a day
apart reporting 7921 and 8338 units and neither able to tell whether the
other had a different inventory or a different definition. The form and
rules tests each had their own copy of this function; this is that copy,
once.

The predicate is ``scripts/sweep.py``'s: a unit belongs if it spells
itself back. What differs is the *extent* -- this module offers the bare
phones, which is what these tests sweep, and says so rather than
implying parity with the whole canonical corpus.

Sweeps also assert **shape**, not only a floor. A count above a
threshold cannot tell that a whole class has gone missing, and one class
here carries a specific guard: the tie-bar compounds are the only phones
that exercise ``Unit.core``'s promise to keep a tie bar, so a sweep that
silently lost them would still "run" while that promise went unchecked.
"""

from __future__ import annotations

import functools

import ipakit
from ipakit.form import declared_prosody

FEATURES = ipakit.load_ipa_features()

#: Multi-constituent phones: tie-bar affricates and the tied diphthongs.
#: Named because they are a guard, not merely a subset.
#: The tie glyphs, asked of the declaration rather than pasted here.
#: ``ipa.xml`` declares a ``tie`` feature whose values are spelled by two
#: marks, so the question "which characters are ties" has an answer in the
#: data. An earlier version of this line pasted a raw combining character
#: inline, which is the shape ``test_declared_not_hardcoded.py`` exists to
#: reject; the version after it read the declaration here, one loop of its
#: own. That loop now lives on the inventory as ``tie_bars``, so this is
#: the same answer read rather than a second asking, and the tests that
#: need the glyphs at module level share this one name.
TIES = FEATURES.tie_bars

TIED = tuple(p for p in FEATURES.phones if TIES & set(p))


def self_spelling_phones() -> list[str]:
    """Every registered phone that spells itself back.

    The *bare* half of the canonical corpus, not the whole of it.
    ``scripts/sweep.py corpus`` prints the full definition and the
    counts, which move when the inventory does.
    """
    return [p for p in FEATURES.phones if FEATURES.segment(p).to_ipa() == p]


#: Marks that state prosody, asked of the declaration rather than listed:
#: ``declared_prosody`` filters a mark's bundle to the ``mode="prosodic"``
#: keys, so ``ʰ`` comes back empty and a mark declared later joins the
#: sweeps without this line being edited.
PROSODIC_MARKS = tuple(m for m in FEATURES.diacritics if declared_prosody(m, FEATURES))

#: How much of the two-mark half to sweep: one base in this many. See
#: :func:`prosody_bearing_units` for why sampling is defensible here and
#: what it costs.
PAIR_STRIDE = 7


def _spells_itself(unit: str) -> bool:
    try:
        return FEATURES.segment(unit).to_ipa() == unit
    except Exception:  # noqa: BLE001 - not self-spelling either way
        return False


def prosody_bearing_units(pair_stride: int = PAIR_STRIDE) -> list[str]:
    """Self-spelling units carrying prosody: one mark over every base, two
    over a share of them.

    The canonical corpus is a base plus **one** mark, and one mark cannot
    contradict itself -- so a sweep over it can say nothing about a
    contour written against the levels underneath it, which is where
    ``with_prosody`` returned the opposite contour from the one asserted.
    This is the same predicate over the extent that reaches it.

    The second mark is swept over every ``pair_stride``-th base rather
    than every one, and that is a deliberate sample rather than a tuned
    number: what interacts here is a pair of *marks*, and the base enters
    only through Unicode recomposition, which the one-mark half covers
    over every base there is. Swept whole the pairs are an order of
    magnitude more units and slow enough to be felt in the default run.
    """
    out: list[str] = []
    for index, base in enumerate(self_spelling_phones()):
        for mark in PROSODIC_MARKS:
            unit = base + mark
            if not _spells_itself(unit):
                continue
            out.append(unit)
            if index % pair_stride:
                continue
            out.extend(
                unit + second
                for second in PROSODIC_MARKS
                if _spells_itself(unit + second)
            )
    return out


@functools.lru_cache(maxsize=1)
def single_mark_units() -> tuple[str, ...]:
    """Every self-spelling base + one mark, in **either** position.

    ``scripts/sweep.py``'s canonical corpus, plus the position it does not
    try. A mark goes where it binds, and two of the shipped ones bind
    forward, so a suffix-only sweep can spell no stressed unit at all --
    and a sweep that cannot spell one cannot tell a term about stress from
    a term about nothing. Over the suffix-only extent ``[-primary]``
    matched every unit and was indistinguishable from ``[-normal]``, which
    was a defect and is what these sweeps exist to catch.

    Neither position is named here: both are tried and what spells itself
    back is kept, so a mark declared later lands in the sweep on whichever
    side it binds.

    Memoized because it parses every base against every mark twice and is
    swept more than once.
    """
    return tuple(
        unit
        for base in self_spelling_phones()
        for mark in FEATURES.diacritics
        for unit in (base + mark, mark + base)
        if _spells_itself(unit)
    )


def assert_swept(checked: int, phones: list[str] | None = None) -> None:
    """Assert a sweep both ran and covered the classes it needs to.

    ``checked`` guards against a silent collapse to nothing. The class
    check guards against the subtler failure: a sweep that still clears a
    floor while a whole shape has dropped out of it.
    """
    assert checked >= 130, f"sweep covered only {checked} units"
    if phones is not None:
        missing = [p for p in TIED if p not in phones]
        assert not missing, f"tied phones absent from the sweep: {missing[:5]}"
        assert len(TIED) >= 20, f"only {len(TIED)} tied phones declared"
