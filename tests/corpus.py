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

import ipakit

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
