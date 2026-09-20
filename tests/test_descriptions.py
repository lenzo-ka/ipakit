"""A description names one phone; every collision is an error."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from ipakit import IPAFeatures

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import check_descriptions

#: The sentence collapsed onto, in a shape no real description takes.
ONE_SENTENCE = "one sentence for two sounds"


class Altered:
    """The shipped inventory with named reads answering differently.

    A guard is tested by putting the mistake in front of it, and the
    mistake here is a *sentence* -- so the inventory, its segments and
    its bundles are the real ones, and only `describe` is moved.
    """

    def __init__(
        self,
        ipa: IPAFeatures,
        *,
        describes: dict[str, str] | None = None,
    ) -> None:
        self._ipa = ipa
        self._describes = describes or {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ipa, name)

    def describe(self, phone: str, with_defaults: bool = True) -> str:
        if phone in self._describes:
            return self._describes[phone]
        return self._ipa.describe(phone, with_defaults)


def collapse(ipa: IPAFeatures, *phones: str) -> Any:
    """The inventory with `phones` given one description between them."""
    return Altered(ipa, describes={p: ONE_SENTENCE for p in phones})


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_the_shipped_inventory_distinguishes_its_phones(ipa: IPAFeatures) -> None:
    assert check_descriptions(ipa)


def test_two_atomic_phones_may_not_share_a_sentence(ipa: IPAFeatures) -> None:
    assert not check_descriptions(collapse(ipa, "p", "t"))


def test_two_diphthongs_may_not_share_a_sentence(ipa: IPAFeatures) -> None:
    assert not check_descriptions(collapse(ipa, "a͜ɪ", "e͜ɪ"))


def test_a_diphthong_may_not_take_a_vowel_it_is_not_built_on(
    ipa: IPAFeatures,
) -> None:
    assert not check_descriptions(collapse(ipa, "e", "a͜ʊ"))


def test_a_nucleus_and_its_diphthong_may_not_share_a_sentence(
    ipa: IPAFeatures,
) -> None:
    assert not check_descriptions(collapse(ipa, "a", "a͜ɪ"))
