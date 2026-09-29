"""The house spelling for the voiced retroflex implosive."""

from __future__ import annotations

from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.constants import DEFAULT_IPA_FEATS

DECLARATION = (
    '<phone name="ᶑ" manner="plosive" place="alveolar" voiced="+" '
    'retroflex="+" airstream="implosive" href="Voiced_retroflex_implosive"/>'
)


def test_voiced_retroflex_implosive_reads_strictly_and_round_trips(
    ipa: IPAFeatures,
) -> None:
    assert ipa.to_ipa(ipa.segments("ᶑ", strict=True)) == "ᶑ"
    for text in ("ᶑː", "ᶑ˥", "ᶑ̥"):
        assert ipa.to_ipa(ipa.segments(text, strict=True)) == text


def test_voiced_retroflex_implosive_has_exactly_the_ruled_features(
    ipa: IPAFeatures,
) -> None:
    stated = ipa.get_features("ᶑ", with_defaults=False)
    assert {key: value for key, value in stated.items() if key in ipa.features} == {
        "manner": "plosive",
        "place": "alveolar",
        "voiced": "+",
        "retroflex": "+",
        "airstream": "implosive",
    }
    assert stated["href"] == "Voiced_retroflex_implosive"


def test_voiced_retroflex_implosive_is_distinct_from_its_neighbors(
    ipa: IPAFeatures,
) -> None:
    ruled = ipa.segment("ᶑ", strict=True)
    for other in ("ɗ", "ɖ", "ɗ̠"):
        assert ruled != ipa.segment(other, strict=True)
        assert ipa.distance("ᶑ", other) > 0


def test_removing_the_declaration_removes_strict_readability(tmp_path: Path) -> None:
    text = DEFAULT_IPA_FEATS.read_text(encoding="utf-8")
    assert text.count(DECLARATION) == 1, "the declaration moved; fix this test"
    path = tmp_path / "ipa.xml"
    path.write_text(text.replace(DECLARATION, ""), encoding="utf-8")
    without = IPAFeatures(xml_path=path)
    with pytest.raises(ValueError):
        without.segments("ᶑ", strict=True)
