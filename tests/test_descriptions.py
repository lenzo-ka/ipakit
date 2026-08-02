"""A description names one phone, and the one collapse that is by design.

`describe` is the sentence a reader is given for a symbol, so two phones
sharing one is a phone the library cannot say out loud. One collapse is
intended: a diphthong's flat projection is its nucleus, so `a͜ɪ` reads
back as `a`'s sentence and no describer got it wrong.

The exception saying so has to be a predicate over the *shape* of that
collapse, in the sense `docs/reviewing.md` gives -- one atomic member,
every other member a diphthong opening on it and carrying its bundle.
Asking only which `kind` values the group holds is not that predicate:
`{"atomic"} <= {"atomic", "diphthong"}`, so it excuses two consonants
with one sentence between them, which is every collision the check is
for. The four cases below are the four ways the collapse can fail to be
the intended one, and each is put in front of the guard rather than
described to it.

Nothing here asserts that the shipped inventory *has* a violation. It
does not, and `test_the_shipped_inventory_distinguishes_its_phones` is
what says so -- with the companion below it, which fails if the
exception ever stops being reached, so a guard that is passing because
it excuses everything and a guard that is passing because the data is
clean stay distinguishable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from ipakit import IPAFeatures

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import (  # noqa: E402
    _nucleus_and_its_diphthongs,
    check_descriptions,
)

#: The sentence collapsed onto, in a shape no real description takes.
ONE_SENTENCE = "one sentence for two sounds"


class Altered:
    """The shipped inventory with named reads answering differently.

    A guard is tested by putting the mistake in front of it, and the
    mistake here is a *sentence* -- so the inventory, its segments and
    its bundles are the real ones, and only `describe` (and, for the
    bundle clause, `get_features`) is moved.
    """

    def __init__(
        self,
        ipa: IPAFeatures,
        *,
        describes: dict[str, str] | None = None,
        features: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._ipa = ipa
        self._describes = describes or {}
        self._features = features or {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ipa, name)

    def describe(self, phone: str, with_defaults: bool = True) -> str:
        if phone in self._describes:
            return self._describes[phone]
        return self._ipa.describe(phone, with_defaults)

    def get_features(self, phone: str, with_defaults: bool = True) -> dict[str, str]:
        if phone in self._features:
            return dict(self._features[phone])
        return self._ipa.get_features(phone, with_defaults)


def collapse(ipa: IPAFeatures, *phones: str, **kwargs: Any) -> Any:
    """The inventory with `phones` given one description between them."""
    return Altered(ipa, describes={p: ONE_SENTENCE for p in phones}, **kwargs)


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_the_shipped_inventory_distinguishes_its_phones(ipa: IPAFeatures) -> None:
    assert check_descriptions(ipa)


def test_the_exception_is_reached(ipa: IPAFeatures) -> None:
    """The nucleus-and-diphthongs collapse is in the data, not hypothetical.

    Without this, every test below would keep passing on an inventory
    that had lost its diphthongs, and the exception would be dead code
    nobody could tell from a working one.
    """
    excused = [
        p
        for p in ipa.phones
        if _nucleus_and_its_diphthongs(
            ipa, [q for q in ipa.phones if ipa.describe(q) == ipa.describe(p)]
        )
        and ipa.segment(p).kind.value == "diphthong"
    ]
    assert len(excused) > 4, f"only {len(excused)} diphthongs reach the exception"


def test_two_atomic_phones_may_not_share_a_sentence(ipa: IPAFeatures) -> None:
    """The case an exception asking only about kinds lets through."""
    assert not check_descriptions(collapse(ipa, "p", "t"))


def test_two_diphthongs_may_not_share_a_sentence(ipa: IPAFeatures) -> None:
    """No nucleus between them, so nothing is projecting onto anything."""
    assert not check_descriptions(collapse(ipa, "a͜ɪ", "e͜ɪ"))


def test_a_diphthong_may_not_take_a_vowel_it_is_not_built_on(
    ipa: IPAFeatures,
) -> None:
    """`a͜ʊ` opens on `a`; reading as `e` would be the describer wrong."""
    assert not check_descriptions(collapse(ipa, "e", "a͜ʊ"))


def test_a_diphthong_whose_bundle_left_its_nucleus_may_not_share_it(
    ipa: IPAFeatures,
) -> None:
    """The shape of the eight-diphthongs defect, wearing the right kinds.

    `a͜ɪ` is a diphthong opening on `a` and still describes as `a` does,
    so every structural clause holds; what has gone is the reason -- the
    flat projection is no longer the nucleus's bundle.
    """
    drifted = dict(ipa.get_features("a")) | {"nasalized": "+"}
    assert not check_descriptions(Altered(ipa, features={"a͜ɪ": drifted}))


def test_a_nucleus_and_its_own_diphthongs_are_excused(ipa: IPAFeatures) -> None:
    """The collapse the exception is for, with every clause satisfied."""
    assert _nucleus_and_its_diphthongs(ipa, ["a", "a͜ɪ", "a͜ʊ"])
    assert not _nucleus_and_its_diphthongs(ipa, ["p", "t"])
    assert not _nucleus_and_its_diphthongs(ipa, ["a͜ɪ", "e͜ɪ"])
    assert not _nucleus_and_its_diphthongs(ipa, ["e", "a͜ʊ"])
