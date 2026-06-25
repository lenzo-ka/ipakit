"""Tests for data models."""

from ipakit import Feature, Phone, Phoneset
from ipakit.constants import STRESS_MARKERS, TIE_BAR


class TestFeatureModel:
    """Tests for Feature dataclass."""

    def test_feature_basic(self) -> None:
        f = Feature(name="manner", values=["plosive", "fricative"])
        assert f.name == "manner"
        assert "plosive" in f.values

    def test_feature_is_binary(self) -> None:
        f = Feature(name="voiced", values=["-", "+"], type="binary")
        assert f.is_binary

    def test_feature_is_ordinal(self) -> None:
        f = Feature(name="height", values=["close", "mid", "open"], type="ordinal")
        assert f.is_ordinal
        assert not f.is_binary

    def test_feature_value_distance_same(self) -> None:
        f = Feature(name="height", values=["close", "mid", "open"], type="ordinal")
        assert f.value_distance("close", "close") == 0.0

    def test_feature_value_distance_ordinal(self) -> None:
        f = Feature(name="height", values=["close", "mid", "open"], type="ordinal")
        # close to open is max distance
        assert f.value_distance("close", "open") == 1.0
        # close to mid is half
        assert f.value_distance("close", "mid") == 0.5

    def test_feature_value_distance_binary(self) -> None:
        f = Feature(name="voiced", values=["-", "+"], type="binary")
        assert f.value_distance("-", "+") == 1.0
        assert f.value_distance("+", "+") == 0.0

    def test_feature_with_description(self) -> None:
        f = Feature(
            name="manner", values=["plosive"], desc="How airflow is constricted"
        )
        assert f.desc == "How airflow is constricted"


class TestPhoneModel:
    """Tests for Phone dataclass."""

    def test_phone_basic(self) -> None:
        p = Phone(symbol="p", features={"manner": "plosive", "place": "bilabial"})
        assert p.symbol == "p"
        assert p["manner"] == "plosive"

    def test_phone_get(self) -> None:
        p = Phone(symbol="p", features={"manner": "plosive"})
        assert p.get("manner") == "plosive"
        assert p.get("voiced") is None
        assert p.get("voiced", "-") == "-"

    def test_phone_contains(self) -> None:
        p = Phone(symbol="p", features={"manner": "plosive"})
        assert "manner" in p
        assert "voiced" not in p


class TestPhonesetModel:
    """Tests for Phoneset dataclass."""

    def test_from_list(self) -> None:
        ps = Phoneset.from_list(["p", "t", "k"], name="test")
        assert ps.name == "test"
        assert len(ps) == 3

    def test_contains_uses_set(self) -> None:
        ps = Phoneset.from_list(["p", "t", "k"])
        assert "p" in ps
        assert "b" not in ps

    def test_iter(self) -> None:
        ps = Phoneset.from_list(["p", "t", "k"])
        assert list(ps) == ["p", "t", "k"]

    def test_len(self) -> None:
        ps = Phoneset.from_list(["p", "t", "k"])
        assert len(ps) == 3


class TestConstants:
    """Tests for constants."""

    def test_tie_bar_value(self) -> None:
        assert TIE_BAR == "\u0361"

    def test_stress_markers(self) -> None:
        assert STRESS_MARKERS == {"ˈ": 1, "ˌ": 2}
        assert "ˈ" in STRESS_MARKERS
        assert STRESS_MARKERS["ˈ"] == 1
        assert STRESS_MARKERS["ˌ"] == 2
