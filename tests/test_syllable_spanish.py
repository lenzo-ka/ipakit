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
        ("ptan", ("tan",)),
        ("stan", ("tan",)),
        ("apta", ("ap", "ta")),
        ("asta", ("as", "ta")),
        ("tɾes", ("tɾes",)),
        ("plan", ("plan",)),
        ("pwe͜i", ("we͜i",)),
    ],
)
def test_margins_and_nuclei_are_derived_from_constraints(form, expected) -> None:
    assert ipakit.syllabify(form, "spanish").spelled() == expected


def test_unlicensed_word_initial_material_is_reported() -> None:
    assert ipakit.syllabify("ptan", "spanish").unsyllabified == ((0, 1),)
    assert ipakit.syllabify("stan", "spanish").unsyllabified == ((0, 1),)


def test_every_segment_is_in_exactly_one_syllable_or_reported() -> None:
    """Constraints mode accounts for every segment unit exactly once."""
    for text in ("ptan", "stan", "apta", "asta", "tɾes", "plan", "pwe͜i"):
        result = ipakit.syllabify(text, "spanish")
        reports = {i for start, end in result.unsyllabified for i in range(start, end)}
        for i, unit in enumerate(result.form.units):
            if unit.segment is None:
                continue
            containing = [s for s in result.syllables if s.start <= i < s.end]
            assert (len(containing), i in reports) in {(1, False), (0, True)}


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
    assert ipakit.syllabify("atɾa", "japanese").spelled() == ("a", "ɾa")
    assert ipakit.syllabify("atɾa", "spanish").spelled() == ("a", "tɾa")
