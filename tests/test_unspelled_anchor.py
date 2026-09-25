"""The metric anchors a prosodic feature on its declared unspelled value."""

from types import SimpleNamespace

import ipakit
import pytest
from ipakit.metric import _prosodic_anchor


def test_a_declared_unspelled_value_is_the_metric_anchor():
    ipa = ipakit.IPAFeatures()
    assert ipa.unspelled_values, "no feature declares an unspelled value"
    for name, value in ipa.unspelled_values.items():
        assert _prosodic_anchor(ipa, name) == value


def test_no_mark_spells_a_declared_unspelled_value():
    ipa = ipakit.IPAFeatures()
    for name, value in ipa.unspelled_values.items():
        spellers = [
            m for m, e in ipa.diacritics.items() if e.features.get(name) == value
        ]
        assert (
            spellers == []
        ), f"{name}={value} is declared unspelled but {spellers} spell it"


def test_a_mark_spelling_the_unspelled_value_is_refused():
    ipa = ipakit.IPAFeatures()
    name, value = next(iter(ipa.unspelled_values.items()))
    ipa.diacritics = {
        **ipa.diacritics,
        "\ue000": SimpleNamespace(features={name: value}),
    }
    with pytest.raises(ValueError, match=f"declares unspelled={value!r}"):
        ipa._validate_unspelled_values()


class _Inventory:
    """A minimal inventory: hashable, as the cached anchor requires."""

    def __init__(self, values, marks, unspelled):
        self.features = {"f": _Feature(values)}
        self.diacritics = {m: _Entry({"f": v}) for m, v in marks.items()}
        self.unspelled_values = unspelled


class _Feature:
    def __init__(self, values):
        self.values = values


class _Entry:
    def __init__(self, features):
        self.features = features


def test_the_declaration_decides_where_inference_cannot():
    # Two values are unmarked, so inference alone finds no single anchor;
    # the declaration names which one an unmarked unit reads as.
    declared = _Inventory(("a", "b", "c"), {"x": "c"}, {"f": "a"})
    inferred = _Inventory(("a", "b", "c"), {"x": "c"}, {})
    assert _prosodic_anchor(declared, "f") == "a"
    assert _prosodic_anchor(inferred, "f") is None
