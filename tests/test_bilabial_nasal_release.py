"""The K4 bilabial nasal release is native, distinct, and lossless."""

from pathlib import Path

import ipakit
import pytest
from ipakit.constants import DEFAULT_IPA_FEATS
from ipakit.form import Form


def test_bilabial_nasal_release_has_its_literal_reading() -> None:
    ipa = ipakit.IPAFeatures()
    bilabial = ipa.segment("tᵐ", strict=True)
    generic = ipa.segment("tⁿ", strict=True)

    assert bilabial.to_ipa() == "tᵐ"
    assert bilabial.constituents[0].base == "t"
    assert bilabial.constituents[0].modifiers == ("ᵐ",)
    assert bilabial.constituents[0].approach == ()
    assert bilabial.scalar(with_defaults=False)["release"] == "bilabial-nasal"
    assert generic.scalar(with_defaults=False)["release"] == "nasal"
    assert bilabial != generic


def test_bilabial_nasal_release_follows_generic_nasal_host_scope() -> None:
    ipa = ipakit.IPAFeatures()
    for base in ("t", "a"):
        assert ipa.segment(base + "ᵐ", strict=True).to_ipa() == base + "ᵐ"
        assert ipa.segment(base + "ⁿ", strict=True).to_ipa() == base + "ⁿ"


def test_bilabial_nasal_release_distances_obey_identity_only_at_zero() -> None:
    ipa = ipakit.IPAFeatures()

    assert 0 < ipa.segment_distance("tᵐ", "tⁿ") <= 1
    assert 0 < ipa.segment_distance("tᵐ", "t") <= 1
    assert 0 < ipa.segment_distance("tⁿ", "t") <= 1


def test_bilabial_nasal_release_round_trips_through_form() -> None:
    ipa = ipakit.IPAFeatures()
    form = Form.parse("tᵐ", ipa, strict=True)

    assert form.to_ipa() == "tᵐ"
    assert Form.from_json(form.to_json(), ipa).to_ipa() == "tᵐ"


def test_removing_the_mark_declaration_breaks_the_literal_read(tmp_path: Path) -> None:
    declaration = (
        '    <diacritic name="ᵐ" release="bilabial-nasal" href="Nasal_release"/>\n'
    )
    text = DEFAULT_IPA_FEATS.read_text(encoding="utf-8")
    assert text.count(declaration) == 1
    path = tmp_path / "ipa-without-bilabial-nasal-release-mark.xml"
    path.write_text(text.replace(declaration, ""), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown symbols.*ᵐ"):
        ipakit.IPAFeatures(path).segment("tᵐ", strict=True)


def test_bilabial_nasal_release_is_nasal_release_to_the_metric() -> None:
    # Both marks release the stop through the nose; only the place differs.
    assert ("release", "bilabial-nasal") in ipakit.IPAFeatures().bridges["nasality"]
    assert ipakit.distance("tᵐ", "t") == ipakit.distance("tⁿ", "t")
