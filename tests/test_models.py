"""Tests for data models."""

from ipakit import Feature, IPAFeatures, Phone, Phoneset
from ipakit.models import _silence_spellings


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

    def test_from_file_drops_every_declared_silence(self, tmp_path) -> None:
        """Silence is dropped by what the data says it is, not by glyph.

        The filter was ``not in ("SIL", "␣")``: a registered phone named
        in a comparison inside a classmethod, where the guard over
        module-level constants could not see it. ``␣`` is declared
        ``manner="silence"``, so the set is read off that and a second
        silence phone would be dropped by the same rule.
        """
        ipa = IPAFeatures()
        silences = [
            symbol
            for symbol, phone in ipa.phones.items()
            if (phone.features or {}).get("manner") == "silence"
        ]
        assert silences, "no silence phone is declared: the check would be vacuous"
        assert set(silences) <= _silence_spellings()
        path = tmp_path / "phones.txt"
        path.write_text("p\n\n" + "\n".join(["SIL", *silences]) + "\nt\n")
        assert Phoneset.from_file(path).phones == ["p", "t"]


class TestConstants:
    """Tests for constants."""

    def test_tie_marks_derived(self) -> None:
        # Derived from ipa.xml's `tie` feature and the marks declaring its
        # values, the way `stress_markers` reads the stress glyphs. These
        # two characters used to be spelled out in `constants.py`.
        ipa = IPAFeatures()
        assert ipa.tie_marks == {
            "simultaneous": "\u0361",
            "sequential": "\u035c",
        }
        assert (ipa.tie_bar, ipa.seq_tie) == ("\u0361", "\u035c")
        assert ipa.tie_bars == frozenset({"\u0361", "\u035c"})

    def test_stress_markers_derived(self) -> None:
        # Derived from ipa.xml's `stress` feature (value shorts are the levels).
        assert IPAFeatures().stress_markers == {"ˈ": 1, "ˌ": 2}
