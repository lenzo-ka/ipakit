"""A mark already supplied by its base changes no feature read.

The spelling remains lossless: redundancy is a fact about the assembled
bundle, not a reason to reject or delete what was written.
"""

from __future__ import annotations

import warnings

import pytest
from ipakit.features import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


@pytest.mark.parametrize(
    ("base", "marked"),
    [
        pytest.param("ŋ", "ŋ̃", id="nasality-bridge"),
        pytest.param("w", "wʷ", id="protrusion-bridge"),
        pytest.param("l", "lˡ", id="laterality-bridge"),
        pytest.param("ɡ", "ɡˠ", id="secondary-place"),
    ],
)
def test_a_redundant_mark_keeps_the_bases_bundle_and_description(
    ipa: IPAFeatures, base: str, marked: str
) -> None:
    """Every equivalence is read from a bridge or secondary-place declaration."""
    assert ipa.get_features(marked) == ipa.get_features(base)
    assert ipa.describe(marked) == ipa.describe(base)
    assert ipa.segment(marked).to_ipa() == marked


@pytest.mark.parametrize(
    ("base", "marked", "expected"),
    [
        pytest.param("t", "tʷ", 0.051746031746031755, id="new-protrusion"),
        pytest.param("ɕ", "ɕʲ", 0.00253968253968254, id="new-palatal-place"),
        pytest.param("t", "tˡ", 0.09090909090909091, id="new-laterality"),
    ],
)
def test_a_mark_that_supplies_a_new_component_still_changes_and_costs(
    ipa: IPAFeatures, base: str, marked: str, expected: float
) -> None:
    assert ipa.get_features(marked) != ipa.get_features(base)
    assert ipa.distance(base, marked) == pytest.approx(expected)


def test_the_declared_sweep_has_no_bundle_flip_at_zero(ipa: IPAFeatures) -> None:
    """The 33 bridge/place restatements join the 51 already absorbed cases."""
    marks = {
        "labialized": "ʷ",
        "velarized": "ˠ",
        "palatalized": "ʲ",
        "pharyngealized": "ˤ",
        "rhotacized": "˞",
        "nasalized": "̃",
    }
    absorbed = priced = flip_zero = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for phone in ipa.phones:
            for feature, mark in marks.items():
                marked = phone + mark
                if ipa.describe(marked).startswith("unknown"):
                    continue
                distance = ipa.distance(phone, marked)
                plain = ipa.get_features(phone)
                modified = ipa.get_features(marked)
                if plain.get(feature) == modified.get(feature):
                    absorbed += 1
                elif distance == 0:
                    flip_zero += 1
                else:
                    priced += 1
    assert (absorbed, priced, flip_zero) == (84, 750, 0)
