"""Mandarin proves the strict, enumerated end of the mechanism."""

import ipakit


def test_pinyin_syllabary_members_are_valid_by_construction() -> None:
    result = ipakit.syllabify("ma˥ma˨˩˦", "mandarin")
    assert result.spelled() == ("ma˥", "ma˨˩˦")
    assert not result.unsyllabified


def test_tone_rides_the_syllable_without_changing_membership() -> None:
    plain = ipakit.syllabify("ma", "mandarin")
    toned = ipakit.syllabify("ma˥", "mandarin")
    assert [(i.start, i.end) for i in plain.syllables] == [(0, 2)]
    assert [(i.start, i.end) for i in toned.syllables] == [(0, 2)]


def test_a_nonmember_is_refused_rather_than_repaired() -> None:
    result = ipakit.syllabify("mla", "mandarin")
    assert not result.syllables
    assert result.unsyllabified == ((0, 3),)


def test_the_inventory_is_read_from_the_pinyin_declaration() -> None:
    declaration = ipakit.language("mandarin")
    assert {"ma", "ʈ͡ʂʊŋ", "kuɔ"} <= declaration.syllables
    assert declaration.provenance.startswith("Strict membership")
