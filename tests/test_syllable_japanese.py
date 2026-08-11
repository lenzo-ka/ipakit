"""Japanese proves that the shared mechanism can be a moraizer."""

import ipakit
import pytest


@pytest.mark.parametrize(
    ("form", "syllables", "morae"),
    [
        ("pen", ("pen",), 2),
        ("hotːo", ("ho", "tːo"), 3),
        ("toːkjo", ("toː", "kjo"), 3),
        ("ko͜i", ("ko͜i",), 1),
    ],
)
def test_declared_moraic_analysis(form, syllables, morae) -> None:
    result = ipakit.syllabify(form, "japanese")
    assert result.spelled() == syllables
    assert len(result.morae) == morae


def test_the_rule_sets_attested_pair_is_measured_after_adaptation() -> None:
    rules = ipakit.ruleset("japanese-moraic")
    for source, expected in (("pɛn", 2), ("hɑt", 3)):
        adapted = ipakit.rewrite(source, rules)
        assert len(ipakit.syllabify(adapted, "japanese").morae) == expected


def test_mora_and_syllable_are_both_primary_intervals() -> None:
    result = ipakit.syllabify("hotːo", "japanese")
    assert {interval.tier for interval in result.form.intervals} == {
        "mora",
        "syllable",
    }
