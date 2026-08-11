"""Japanese proves that the shared mechanism can be a moraizer."""

import ipakit
import pytest


@pytest.mark.parametrize(
    ("form", "syllables", "morae"),
    [
        ("pen", ("pen",), 2),
        ("hotːo", ("ho", "tːo"), 3),
        ("ɸɯdʑisaɴ", ("ɸɯ", "ʑi", "saɴ"), 4),
        ("kjoːto", ("kjoː", "to"), 3),
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


def test_unlicensed_obstruent_contrasts_with_geminate_half() -> None:
    residue = ipakit.syllabify("atɾa", "japanese")
    assert residue.spelled() == ("a", "ɾa")
    assert residue.spelled("mora") == ("a", "ɾa")
    assert residue.unsyllabified == ((1, 2),)

    geminate = ipakit.syllabify("hotːo", "japanese")
    assert geminate.spelled() == ("ho", "tːo")
    assert len(geminate.morae) == 3
    assert geminate.unsyllabified == ()


def test_every_moraic_syllable_is_tiled_by_morae_or_residue_is_reported() -> None:
    """Every segment has one mora tile inside a syllable, or a residue report."""
    for text in ("pen", "hotːo", "ɸɯdʑisaɴ", "kjoːto", "atɾa"):
        result = ipakit.syllabify(text, "japanese")
        reports = {i for start, end in result.unsyllabified for i in range(start, end)}
        length_morae = {
            mora
            for mora in result.morae
            if mora.end == mora.start + 1
            and result.form.units[mora.start].prosody.get("length") == "long"
            and any(
                other != mora and other.start <= mora.start < other.end
                for other in result.morae
            )
        }
        tiles = [mora for mora in result.morae if mora not in length_morae]
        for i, unit in enumerate(result.form.units):
            if unit.segment is None:
                continue
            containing = [s for s in result.syllables if s.start <= i < s.end]
            covered = [m for m in tiles if m.start <= i < m.end]
            assert (len(containing), len(covered), i in reports) in {
                (1, 1, False),
                (0, 0, True),
            }


def test_stated_boundary_reports_material_it_strands() -> None:
    result = ipakit.syllabify("at.ɾa", "japanese")
    assert result.spelled() == ("a", "ɾa")
    assert result.unsyllabified == ((1, 2),)
