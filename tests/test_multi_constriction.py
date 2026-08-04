"""A reading carries every constriction, and a rhotic states none it can place.

#183: the tract-x reading was one point, so a segment making two constrictions
was compared at their average -- ``w`` between the lips and the velum, where
nothing closes. The reading is now the set of every constriction's arc,
compared by best-match; and a rhotic, whose constriction the evidence gives no
single arc for (docs/design/vowel-constriction.md section 6), states no
locatable arc at all, so the metric withholds the term rather than inventing a
position.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.metric import (
    _UNLOCALIZED,
    _arc_distance,
    _tract_x,
    _Unlocalized,
)


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def _x(ipa: IPAFeatures, phone: str) -> object:
    return _tract_x(ipa, ipa.get_features(phone))


class TestTheReadingCarriesEveryConstriction:
    def test_a_single_constriction_is_a_one_tuple(self, ipa: IPAFeatures) -> None:
        x = _x(ipa, "i")
        assert isinstance(x, tuple) and len(x) == 1

    def test_a_double_articulation_is_two_points_not_their_average(
        self, ipa: IPAFeatures
    ) -> None:
        x = _x(ipa, "w")
        assert isinstance(x, tuple) and len(x) == 2
        assert x == tuple(sorted(x))
        # the lips and the dorsum, not the 0.225 midpoint the average gave
        assert not any(abs(v - 0.225) < 1e-9 for v in x)

    def test_a_click_closes_at_its_place_and_the_velum(self, ipa: IPAFeatures) -> None:
        assert len(_x(ipa, "ǃ")) == 2  # type: ignore[arg-type]

    def test_the_labial_velars_are_two_points(self, ipa: IPAFeatures) -> None:
        for p in ("k͡p", "ɡ͡b", "ŋ͡m"):
            assert len(_x(ipa, p)) == 2, p  # type: ignore[arg-type]


class TestBestMatchIsBackwardCompatibleOnSingletons:
    def test_over_one_tuples_it_is_the_absolute_difference(self) -> None:
        # This is why every single-constriction pair is bit-identical: the
        # set reduction collapses to the subtraction it replaced.
        assert _arc_distance((0.3,), (0.7,)) == abs(0.3 - 0.7)
        assert _arc_distance((0.5,), (0.5,)) == 0.0

    def test_it_is_symmetric_and_bounded(self) -> None:
        a, b = (0.0, 0.45), (0.17,)
        assert _arc_distance(a, b) == _arc_distance(b, a)
        assert 0.0 <= _arc_distance(a, b) <= 1.0


class TestTheRhoticStatesNoLocatableArc:
    def test_the_rhotics_are_unlocalized(self, ipa: IPAFeatures) -> None:
        assert _x(ipa, "ɝ") is _UNLOCALIZED
        assert _x(ipa, "ɚ") is _UNLOCALIZED

    def test_a_plain_central_vowel_still_has_a_point(self, ipa: IPAFeatures) -> None:
        x = _x(ipa, "ə")
        assert isinstance(x, tuple) and not isinstance(x, _Unlocalized)


class TestTheDeclarationIsLoadBearingAndGeneric:
    """The control: the behavior comes from the XML attribute, not from code.

    A zero (the rhotics unlocalized) is only a result beside a live non-zero:
    remove the declaration and the rhotic relocalizes; add it to another
    feature and a phone stating *that* unlocalizes. Neither the fact nor the
    feature name is written in Python.
    """

    def _patched(
        self,
        ipa: IPAFeatures,
        tmp_path: Path,
        feature: str,
        set_attr: dict[str, str] | None = None,
        del_attr: str | None = None,
    ) -> IPAFeatures:
        tree = ET.parse(ipa.xml_path)
        elem = tree.getroot().find(f".//feature[@name='{feature}']")
        assert elem is not None
        for k, v in (set_attr or {}).items():
            elem.set(k, v)
        if del_attr is not None:
            del elem.attrib[del_attr]
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return IPAFeatures(path)

    def test_removing_it_relocalizes_the_rhotic(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        assert _x(ipa, "ɝ") is _UNLOCALIZED  # with the declaration
        patched = self._patched(ipa, tmp_path, "rhotacized", del_attr="constriction")
        x = _tract_x(patched, patched.get_features("ɝ"))
        assert not isinstance(x, _Unlocalized)  # the live non-zero
        assert isinstance(x, tuple) and len(x) >= 1

    def test_the_metric_reads_the_attribute_not_the_name_rhotacized(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        # Declare it on `voiced` (binary, default '-'): a voiced phone then
        # states an unlocalized constriction, a voiceless one does not.
        patched = self._patched(
            ipa, tmp_path, "voiced", set_attr={"constriction": "unlocalized"}
        )
        assert _tract_x(patched, patched.get_features("b")) is _UNLOCALIZED
        assert not isinstance(
            _tract_x(patched, patched.get_features("p")), _Unlocalized
        )
