"""Tests for TIMIT and Kirshenbaum phonemap conversions."""

import ipakit
from ipakit.phonemaps import (
    from_kirshenbaum,
    from_timit,
    to_kirshenbaum,
    to_timit,
)


class TestTIMIT:
    """Tests for TIMIT phoneset conversion."""

    def test_to_timit_consonants(self) -> None:
        assert to_timit("p") == ["p"]
        assert to_timit("b") == ["b"]
        assert to_timit("t") == ["t"]
        assert to_timit("d") == ["d"]
        assert to_timit("k") == ["k"]
        assert to_timit("ɡ") == ["g"]

    def test_to_timit_vowels(self) -> None:
        assert to_timit("i") == ["iy"]
        assert to_timit("ɪ") == ["ih"]
        assert to_timit("ɛ") == ["eh"]
        assert to_timit("æ") == ["ae"]
        assert to_timit("ɑ") == ["aa"]
        assert to_timit("u") == ["uw"]

    def test_to_timit_word(self) -> None:
        result = to_timit("kæt")
        assert result == ["k", "ae", "t"]

    def test_to_timit_fricatives(self) -> None:
        assert to_timit("s") == ["s"]
        assert to_timit("z") == ["z"]
        assert to_timit("ʃ") == ["sh"]
        assert to_timit("ʒ") == ["zh"]
        assert to_timit("θ") == ["th"]
        assert to_timit("ð") == ["dh"]

    def test_to_timit_affricates(self) -> None:
        assert to_timit("t͡ʃ") == ["ch"]
        assert to_timit("d͡ʒ") == ["jh"]

    def test_to_timit_nasals(self) -> None:
        assert to_timit("m") == ["m"]
        assert to_timit("n") == ["n"]
        assert to_timit("ŋ") == ["ng"]

    def test_to_timit_diphthongs(self) -> None:
        assert to_timit("e͡ɪ") == ["ey"]
        assert to_timit("o͡ʊ") == ["ow"]
        assert to_timit("a͡ɪ") == ["ay"]

    def test_from_timit_basic(self) -> None:
        assert from_timit(["k", "ae", "t"]) == "kæt"
        assert from_timit(["p"]) == "p"
        assert from_timit(["sh"]) == "ʃ"

    def test_from_timit_word(self) -> None:
        assert from_timit(["hh", "eh", "l", "ow"]) == "hɛlo͡ʊ"

    def test_round_trip(self) -> None:
        original = "kæt"
        timit = to_timit(original)
        back = from_timit(timit)
        assert back == original

    def test_module_exports(self) -> None:
        assert ipakit.to_timit("kæt") == ["k", "ae", "t"]
        assert ipakit.from_timit(["k", "ae", "t"]) == "kæt"


class TestKirshenbaum:
    """Tests for Kirshenbaum ASCII-IPA conversion."""

    def test_to_kirshenbaum_basic(self) -> None:
        assert to_kirshenbaum("p") == "p"
        assert to_kirshenbaum("b") == "b"
        assert to_kirshenbaum("t") == "t"

    def test_to_kirshenbaum_special(self) -> None:
        assert to_kirshenbaum("ʃ") == "S"
        assert to_kirshenbaum("ʒ") == "Z"
        assert to_kirshenbaum("θ") == "T"
        assert to_kirshenbaum("ð") == "D"
        assert to_kirshenbaum("ŋ") == "N"

    def test_to_kirshenbaum_vowels(self) -> None:
        assert to_kirshenbaum("ɛ") == "E"
        assert to_kirshenbaum("æ") == "&"
        assert to_kirshenbaum("ɑ") == "A"
        assert to_kirshenbaum("ə") == "@"
        assert to_kirshenbaum("ɪ") == "I"
        assert to_kirshenbaum("ʊ") == "U"

    def test_to_kirshenbaum_word(self) -> None:
        assert to_kirshenbaum("kæt") == "k&t"
        assert to_kirshenbaum("ʃɑk") == "SAk"

    def test_to_kirshenbaum_affricates(self) -> None:
        assert to_kirshenbaum("t͡ʃ") == "tS"
        assert to_kirshenbaum("d͡ʒ") == "dZ"

    def test_from_kirshenbaum_basic(self) -> None:
        assert from_kirshenbaum("p") == "p"
        assert from_kirshenbaum("S") == "ʃ"
        assert from_kirshenbaum("T") == "θ"
        assert from_kirshenbaum("N") == "ŋ"

    def test_from_kirshenbaum_word(self) -> None:
        assert from_kirshenbaum("k&t") == "kæt"
        assert from_kirshenbaum("SAk") == "ʃɑk"

    def test_from_kirshenbaum_affricates(self) -> None:
        assert from_kirshenbaum("tS") == "t͡ʃ"
        assert from_kirshenbaum("dZ") == "d͡ʒ"

    def test_round_trip_simple(self) -> None:
        # Simple consonants and vowels should round-trip
        for phone in ["p", "t", "k", "s", "m", "n", "l"]:
            assert from_kirshenbaum(to_kirshenbaum(phone)) == phone

    def test_module_exports(self) -> None:
        assert ipakit.to_kirshenbaum("ʃɑk") == "SAk"
        assert ipakit.from_kirshenbaum("SAk") == "ʃɑk"
