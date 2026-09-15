"""Scalar feature warnings name omitted material and a retaining read."""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path

import ipakit
import ipakit.cli
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
                key: value
                for key in ipa.diacritics[mark].features
                for value in (ipa.diacritics[mark].features[key],)
                if key in ipa.features_by_mode["prosodic"]
            }
            values = ipa.feature_values(text)
            assert all(values[key] == (value,) for key, value in asserted.items())
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

    def test_repeated_constituent_points_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a͜a"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "read() / segments()" in message
        (unit,) = ipa.segments(text, strict=True)
        assert [str(part) for part in unit.constituents] == ["a", "a"]

    def test_contradictory_prosody_points_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "aː̆"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "read() / segments()" in message
        with pytest.warns(UserWarning, match="two marks state 'length'"):
            (unit,) = ipa.segments(text, strict=True)
        assert unit.prosody == ("ː", "̆")

    def test_contradictory_segmental_marks_point_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a̺̻"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "diacritic mark(s) ['̻']" in message
        assert "read() / segments()" in message
        with pytest.warns(UserWarning, match="two marks state 'articulator'"):
            (unit,) = ipa.segments(text, strict=True)
        assert unit.constituents[0].modifiers == ("̺", "̻")

    def test_unregistered_symbol_points_to_refusal_or_import(
        self, ipa: IPAFeatures
    ) -> None:
        text = "X"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "unregistered symbol(s) ['X']" in message
        assert "strict=True / from_wild()" in message
        with pytest.raises(ValueError, match="unknown symbols"):
            ipa.read(text, strict=True)

    def test_multiple_units_point_to_a_read_that_keeps_both(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a a"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "multiple units ['a', 'a']" in message
        assert "segments()" in message
        assert [unit.to_ipa() for unit in ipa.segments(text, strict=True)] == ["a", "a"]

    def test_nonsegmental_material_points_to_the_form_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "∅"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "read()" in message
        assert ipa.read(text, strict=True).to_ipa() == text


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

    def test_every_placeable_approach_mark_is_represented(
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
                for mark in ipa.approach_marks:
                    text = mark + base
                    try:
                        segment = ipa.segment(text, strict=True)
                    except ValueError:
                        continue
                    if not any(mark in part.approach for part in segment.constituents):
                        continue
                    ipa.get_features(text)
                    checked += 1
        assert checked >= 100, "the approach-mark sweep was vacuous"

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
    def test_an_observed_loss_requires_a_warning(self, ipa: IPAFeatures) -> None:
        text = "a͜ɪ"
        with pytest.warns(FeatureNarrowingWarning):
            scalar = ipa.get_features(text)
        complete = ipa.feature_values(text)
        missing = {
            (key, value)
            for key, values in complete.items()
            for value in values
            if value != scalar.get(key)
        }
        assert missing, "the warning witness did not actually lose a feature value"


def test_package_internals_do_not_call_the_public_scalar_read() -> None:
    root = Path(ipakit.__file__).resolve().parent
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = node.func
            public = (
                isinstance(call, ast.Attribute)
                and call.attr == "get_features"
                or isinstance(call, ast.Name)
                and call.id == "features"
                or isinstance(call, ast.Attribute)
                and isinstance(call.value, ast.Name)
                and call.value.id == "ipakit"
                and call.attr == "features"
            )
            if public:
                violations.append(f"{path.relative_to(root)}:{node.lineno}")
    assert violations == []


@pytest.mark.parametrize("text", ["a͜ɪ", "aː"])
def test_features_cli_is_quiet_and_successful(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["ipakit", "features", text])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rc = ipakit.cli.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out
    assert captured.err == ""


def test_feature_values_retains_the_witnessed_length(ipa: IPAFeatures) -> None:
    assert ipa.feature_values("d̆")["length"] == ("extra-short",)


def test_feature_values_uses_the_first_contradictory_prosody_mark(
    ipa: IPAFeatures,
) -> None:
    with pytest.warns(UserWarning, match="two marks state 'length'"):
        values = ipa.feature_values("aː̆")
    assert values["length"] == ("long",)
