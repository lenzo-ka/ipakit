"""R1 superscripts are release phases, distinct from tied segments."""

from pathlib import Path

import ipakit
import pytest
from ipakit.constants import DEFAULT_IPA_FEATS
from ipakit.form import Form

RELEASES = (
    ("t", "ˢ", "sibilant", "t͡s", "Sibilant"),
    ("d", "ʳ", "trilled", "d͡r", "Trill_consonant"),
    ("d", "ʶ", "uvular", "d͡ʁ", "Uvular_consonant"),
)


@pytest.mark.parametrize(("base", "mark", "value", "tied", "href"), RELEASES)
def test_superscript_release_has_its_literal_reading(
    base: str, mark: str, value: str, tied: str, href: str
) -> None:
    ipa = ipakit.IPAFeatures()
    spelling = base + mark
    released = ipa.segment(spelling, strict=True)

    assert released.to_ipa() == spelling
    assert released.constituents[0].base == base
    assert released.constituents[0].modifiers == (mark,)
    assert released.constituents[0].approach == ()
    assert released.scalar(with_defaults=False)["release"] == value
    assert released != ipa.segment(tied, strict=True)


@pytest.mark.parametrize(("base", "mark", "value", "tied", "href"), RELEASES)
def test_superscript_release_and_tied_form_both_stay_above_zero_distance(
    base: str, mark: str, value: str, tied: str, href: str
) -> None:
    ipa = ipakit.IPAFeatures()
    spelling = base + mark

    assert 0 < ipa.segment_distance(spelling, base) <= 1
    assert 0 < ipa.segment_distance(spelling, tied) <= 1


@pytest.mark.parametrize(("base", "mark", "value", "tied", "href"), RELEASES)
def test_superscript_release_round_trips_through_form(
    base: str, mark: str, value: str, tied: str, href: str
) -> None:
    ipa = ipakit.IPAFeatures()
    spelling = base + mark
    form = Form.parse(spelling, ipa, strict=True)

    assert form.to_ipa() == spelling
    assert Form.from_json(form.to_json(), ipa).to_ipa() == spelling


@pytest.mark.parametrize(("base", "mark", "value", "tied", "href"), RELEASES)
def test_removing_each_mark_declaration_breaks_its_literal_read(
    tmp_path: Path, base: str, mark: str, value: str, tied: str, href: str
) -> None:
    declaration = f'    <diacritic name="{mark}" release="{value}" href="{href}"/>\n'
    text = DEFAULT_IPA_FEATS.read_text(encoding="utf-8")
    assert text.count(declaration) == 1
    path = tmp_path / f"ipa-without-{value}-release-mark.xml"
    path.write_text(text.replace(declaration, ""), encoding="utf-8")

    with pytest.raises(ValueError, match=f"unknown symbols.*{mark}"):
        ipakit.IPAFeatures(path).segment(base + mark, strict=True)


def test_new_release_values_do_not_claim_an_unsupported_bridge() -> None:
    ipa = ipakit.IPAFeatures()
    bridged = {spelling for bridge in ipa.bridges.values() for spelling in bridge}

    # No existing bridge equates a release phase with whole-segment
    # sibilance, trilling or uvular place. Unlike nasal and lateral release,
    # these three have no reviewed shared-dimension evidence in the model.
    assert {
        ("release", "sibilant"),
        ("release", "trilled"),
        ("release", "uvular"),
    }.isdisjoint(bridged)
