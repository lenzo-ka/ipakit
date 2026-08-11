"""Spanish proves that margin constraints can derive the inventory."""

import ipakit
import pytest


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("kasa", ("ka", "sa")),
        ("atɾas", ("a", "tɾas")),
        ("atlas", ("a", "tlas")),
        ("akta", ("ak", "ta")),
        ("poeta", ("po", "e", "ta")),
        ("pwe͜i", ("pwe͜i",)),
    ],
)
def test_margins_and_nuclei_are_derived_from_constraints(form, expected) -> None:
    assert ipakit.syllabify(form, "spanish").spelled() == expected


def test_linking_allows_cross_word_resyllabification() -> None:
    result = ipakit.syllabify("los‿otɾos", "spanish")
    assert result.spelled() == ("lo", "s‿o", "tɾos")
    assert result.marks() == "lo.s‿o.tɾos"


def test_hash_does_not_allow_cross_word_resyllabification() -> None:
    assert ipakit.syllabify("los#otɾos", "spanish").spelled() == (
        "los",
        "o",
        "tɾos",
    )


def test_japanese_and_spanish_disagree_on_the_same_form() -> None:
    assert ipakit.syllabify("atɾa", "japanese").spelled() == ("at", "ɾa")
    assert ipakit.syllabify("atɾa", "spanish").spelled() == ("a", "tɾa")
