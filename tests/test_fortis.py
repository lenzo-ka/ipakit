import sys
from pathlib import Path
from types import MappingProxyType

import pytest
from ipakit import (
    Form,
    is_valid_ipa,
    load_ipa_features,
    segment_distance,
    segments,
    validate_ipa,
)
from ipakit.tract import constrictions, unmodeled

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import check_no_locus_feature_admits_its_own_exponent

IPA = load_ipa_features()


def test_strong_articulation_is_one_fortis_unit() -> None:
    (marked,) = segments("k͈", strict=True)
    (plain,) = segments("k", strict=True)
    assert marked.scalar()["fortis"] == "+"
    assert plain.scalar()["fortis"] == "-"


@pytest.mark.parametrize("unit", ["p͈", "t͈", "k͈", "s͈", "t͡ɕ͈", "k͈ʷ", "t͈ʲ", "t͈ː"])
def test_korean_fortis_series_parses_strictly(unit: str) -> None:
    form = Form.parse(unit, strict=True)
    assert len(form.units) == 1
    assert form.to_ipa() == unit


@pytest.mark.parametrize("unit", ["a͈", "m͈"])
def test_fortis_refuses_non_obstruents_by_the_declared_rule(unit: str) -> None:
    with pytest.raises(ValueError, match="fortis.*obstruent"):
        Form.parse(unit, strict=True)


@pytest.mark.parametrize("unit", ["ʔ͈", "h͈", "ɦ͈"])
def test_fortis_refuses_its_declared_locus(unit: str) -> None:
    with pytest.raises(ValueError, match="fortis.*locus.*glottal.*place.*glottal"):
        Form.parse(unit, strict=True)


@pytest.mark.parametrize("unit", ["ʔ͈", "h͈", "ɦ͈"])
def test_lax_fortis_drops_its_declared_locus_audibly(unit: str) -> None:
    with pytest.warns(UserWarning, match="dropped.*unplaced mark"):
        assert segments(unit) == []


@pytest.mark.parametrize("unit", ["ʜ͈", "ʢ͈"])
def test_epiglottals_do_not_collide_with_the_glottal_locus(unit: str) -> None:
    assert Form.parse(unit, strict=True).to_ipa() == unit


def test_locus_invariant_refuses_a_loaded_declaration_that_disappears(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ipa = load_ipa_features()
    ipa.features["fortis"].locus = None
    ipa.features["rhotacized"].locus = "labiodental"
    assert not check_no_locus_feature_admits_its_own_exponent(ipa)
    assert "fortis declares locus='glottal'" in capsys.readouterr().out


def test_locus_invariant_allows_an_inventory_without_a_locus_host() -> None:
    ipa = load_ipa_features()
    ipa.features["rhotacized"].locus = "labiodental"
    assert check_no_locus_feature_admits_its_own_exponent(ipa)


def test_locus_invariant_refuses_a_table_with_no_locus_at_all(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The shape the defect arrived in: the rule absent from the data
    # entirely, where a per-feature guard has no feature to report on.
    ipa = load_ipa_features()
    stripped = tmp_path / "ipa.xml"
    stripped.write_text(
        Path(ipa.xml_path)
        .read_text(encoding="utf-8")
        .replace(' locus="glottal"', "", 1),
        encoding="utf-8",
    )
    ipa.xml_path = stripped
    for feature in ipa.features.values():
        feature.locus = None
    assert not check_no_locus_feature_admits_its_own_exponent(ipa)
    assert "this check is vacuous" in capsys.readouterr().out


def test_locus_invariant_refuses_candidates_without_an_assertion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ipa = load_ipa_features()
    mark = ipa.diacritics["͈"]
    mark.features = MappingProxyType(
        {name: value for name, value in mark.features.items() if name != "fortis"}
    )
    assert not check_no_locus_feature_admits_its_own_exponent(ipa)
    assert "fortis has applicable phones" in capsys.readouterr().out


@pytest.mark.parametrize("unit", ["a͈", "m͈"])
def test_lax_fortis_drops_non_obstruents_audibly(unit: str) -> None:
    with pytest.warns(UserWarning, match="dropped.*unplaced mark"):
        assert segments(unit) == []


@pytest.mark.parametrize("unit", ["a͈", "m͈", "a͈͡p", "m͈͡p"])
def test_validation_reports_fortis_on_non_obstruents(unit: str) -> None:
    (issue,) = validate_ipa(unit)
    assert issue["type"] == "error"
    assert issue["code"] == "invalid_diacritic"
    assert "fortis" in issue["message"]
    assert "obstruent" in issue["message"]
    assert issue["position"] == "1"
    assert issue["symbol"] == "͈"
    assert is_valid_ipa(unit) is False


@pytest.mark.parametrize("unit", ["a̺", "a̺͡p"])
def test_preexisting_applicability_rule_agrees_on_both_modifier_paths(
    unit: str,
) -> None:
    ipa = load_ipa_features()
    # The shipped channel/retroflex declarations occur on base phones, not
    # modifier marks. Give the existing apical mark the existing retroflex
    # feature in this private inventory so both modifier routes exercise the
    # pre-existing applies="consonant" rule without changing shipped data.
    ipa.features["manner"].value_classes["consonant"] = frozenset(
        value for value in ipa.features["manner"].values if value != "vowel"
    )
    mark = ipa.diacritics["̺"]
    mark.features = MappingProxyType(
        {**mark.features, "retroflex": "+", "articulator": "tongue-tip"}
    )
    with pytest.warns(UserWarning, match="dropped.*unplaced mark"):
        assert ipa.segments(unit) == []
    with pytest.raises(ValueError, match="retroflex.*consonant"):
        ipa.segments(unit, strict=True)


def test_fortis_is_one_laryngeal_feature_step() -> None:
    plain_fortis = segment_distance("k", "k͈")
    plain_aspirated = segment_distance("k", "kʰ")
    fortis_aspirated = segment_distance("k͈", "kʰ")
    assert plain_fortis > 0
    assert plain_fortis == pytest.approx(plain_aspirated, rel=0.1)
    assert fortis_aspirated > plain_fortis
    assert fortis_aspirated > plain_aspirated
    assert segment_distance("p͈", "t͈") == pytest.approx(segment_distance("p", "t"))


def test_fortis_is_an_annotation_and_not_a_constriction() -> None:
    marked = IPA.get_features("k͈", with_defaults=False)
    plain = IPA.get_features("k", with_defaults=False)
    assert constrictions(IPA, marked) == constrictions(IPA, plain)
    assert [(mark.feature, mark.kind) for mark in unmodeled(IPA, marked)] == [
        ("fortis", "unmodeled")
    ]
