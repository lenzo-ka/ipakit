"""The scalar feature read reports every construction that loses information."""

from __future__ import annotations

import warnings

import ipakit
import pytest
from ipakit import FeatureNarrowingWarning, IPAFeatures
from ipakit.segment import Sense, modifier_mode


def _one_warning(call, text: str) -> str:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        call()
    narrowed = [w for w in caught if w.category is FeatureNarrowingWarning]
    assert len(narrowed) == 1, (text, caught)
    message = str(narrowed[0].message)
    assert repr(text) in message
    assert "feature_values" in message
    return message


class TestNarrowingByConstruction:
    def test_every_sequential_phone_names_the_constituents_after_the_cut(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        for symbol in ipa.phones:
            segment = ipa.segment(symbol)
            if Sense.SEQ not in segment.junctures:
                continue
            cut = list(segment.junctures).index(Sense.SEQ) + 1
            dropped = [str(c) for c in segment.constituents[cut:]]
            message = _one_warning(
                lambda symbol=symbol: ipa.get_features(symbol), symbol
            )
            assert "sequential constituent" in message
            assert all(repr(part) in message for part in dropped)
            checked += 1
        assert checked >= 8, "the sequential inventory sweep was vacuous"

    def test_every_prosodic_mark_warns_and_is_kept_by_feature_values(
        self, ipa: IPAFeatures
    ) -> None:
        marks = [
            mark for mark in ipa.diacritics if modifier_mode(ipa, mark) == "prosodic"
        ]
        for mark in marks:
            text = mark + "a" if mark in ipa.stress_markers else "a" + mark
            message = _one_warning(lambda text=text: ipa.get_features(text), text)
            assert "prosodic mark" in message
            asserted = {
                key
                for key in ipa.diacritics[mark].features
                if key in ipa.features_by_mode["prosodic"]
            }
            assert asserted <= ipa.feature_values(text).keys()
        assert len(marks) >= 20, "the prosodic-mark sweep was vacuous"

    @pytest.mark.parametrize(
        ("text", "phrase"),
        [
            ("^a", "structural mark"),
            ("a|", "structural mark"),
            ("a͡", "structural mark"),
            ("̃a", "unplaced diacritic"),
            ("qX", "unregistered symbol"),
            ("a̺̻", "diacritic mark"),
            ("a a", "multiple units"),
            ("∅", "non-segmental symbol"),
        ],
    )
    def test_other_unrepresented_material_is_named(
        self, ipa: IPAFeatures, text: str, phrase: str
    ) -> None:
        assert phrase in _one_warning(lambda: ipa.get_features(text), text)

    def test_all_losses_in_one_call_make_one_warning(self, ipa: IPAFeatures) -> None:
        text = "ˈa͜ɪ|"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "prosodic mark" in message
        assert "sequential constituent" in message
        assert "structural mark" in message


class TestNonNarrowingStaysSilent:
    def test_plain_phones_and_simultaneous_compositions_stay_silent(
        self, ipa: IPAFeatures
    ) -> None:
        simultaneous = [
            symbol
            for symbol in ipa.phones
            if (segment := ipa.segment(symbol)).junctures
            and Sense.SEQ not in segment.junctures
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ipa.get_features("p")
            ipa.get_features("u͡i")
            for symbol in simultaneous:
                ipa.get_features(symbol)
        assert len(simultaneous) >= 10, "the simultaneous sweep was vacuous"

    def test_every_placeable_segmental_mark_is_represented(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        atomic = [
            symbol
            for symbol in ipa.phones
            if Sense.SEQ not in ipa.segment(symbol).junctures
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for base in atomic:
                for mark in ipa.diacritics:
                    if modifier_mode(ipa, mark) in {"prosodic", "structural"}:
                        continue
                    text = base + mark
                    try:
                        segment = ipa.segment(text, strict=True)
                    except ValueError:
                        continue
                    if segment.to_ipa() != text:
                        continue
                    ipa.get_features(text)
                    checked += 1
        assert checked > 4_000, "the segmental-mark sweep was vacuous"

    def test_a_semantically_redundant_mark_stays_silent(self, ipa: IPAFeatures) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert ipa.get_features("ã̃")["nasalized"] == "+"


class TestCallBoundary:
    def test_top_level_warning_points_here(self) -> None:
        with pytest.warns(FeatureNarrowingWarning) as caught:
            ipakit.features("d̆")
        assert caught[0].filename == __file__

    def test_inventory_warning_points_here(self, ipa: IPAFeatures) -> None:
        with pytest.warns(FeatureNarrowingWarning) as caught:
            ipa.get_features("a͜ɪ")
        assert caught[0].filename == __file__

    def test_internal_feature_consumers_do_not_spray(self, ipa: IPAFeatures) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert ipa.segment("d̆").scalar()["manner"] == "plosive"
            assert ipa.describe("a͜ɪ")
            assert ipa.natural_class(["d̆", "d"])
            assert ipa.distance("d", "d̆") > 0


class TestTheWarningGuardIsCausal:
    def test_removing_the_report_makes_the_warning_oracle_fail(
        self, ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ipa, "_feature_omissions", lambda phone: [])
        with pytest.raises(AssertionError):
            _one_warning(lambda: ipa.get_features("a͜ɪ"), "a͜ɪ")


def test_feature_values_retains_the_witnessed_length(ipa: IPAFeatures) -> None:
    assert ipa.feature_values("d̆")["length"] == ("extra-short",)
