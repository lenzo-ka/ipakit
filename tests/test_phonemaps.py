"""The phonemap loader, and the TIMIT and Kirshenbaum conversions over it."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import ipakit
import pytest
from ipakit import phonemaps
from ipakit.constants import PHONEMAPS_DIR
from ipakit.phonemaps import (
    _load_phonemap,
    from_kirshenbaum,
    from_timit,
    to_kirshenbaum,
    to_timit,
)


def _phonemap_files() -> list[Path]:
    """Every shipped phonemap, found by sweeping the directory.

    Swept rather than listed, so a sixth notation is covered the day its
    file lands rather than the day somebody remembers to name it here.
    """
    return sorted(PHONEMAPS_DIR.glob("*.xml"))


def _rows(path: Path) -> tuple[str | None, list[tuple[str, str]]]:
    """A phonemap's own rows, read without the loader under test.

    Reading the file a second way is the point: a test that asks the
    loader what it loaded and compares that with itself cannot tell a
    table apart from an empty one.
    """
    root = ET.parse(path).getroot()
    column = root.get("to")
    sections = [root]
    if (extras := root.find("extras")) is not None:
        sections.append(extras)
    return column, [
        (elem.get("ipa", ""), elem.get(column, "") if column else "")
        for section in sections
        for elem in section.findall("map")
    ]


class TestEveryShippedPhonemapLoads:
    """A phonemap that loads nothing is the silent wrong answer here.

    A table whose declared column is not the one its rows spell matches
    no row and comes back as two empty dicts, which every caller reads as
    "no mapping exists for anything" rather than "this did not load". So
    the claim is over the whole directory, not over the file that made it
    worth stating.
    """

    def test_every_phonemap_loads_a_non_empty_table(self) -> None:
        files = _phonemap_files()
        assert len(files) > 4, f"sweep found only {len(files)} phonemaps"
        for path in files:
            forward, reverse = _load_phonemap(path.stem)
            assert forward, f"{path.name} loaded no IPA -> target mappings"
            assert reverse, f"{path.name} loaded no target -> IPA mappings"

    def test_both_tables_agree_with_the_files_own_rows(self) -> None:
        checked = 0
        for path in _phonemap_files():
            column, rows = _rows(path)
            assert column, f"{path.name} does not declare the column it maps to"
            expected_forward: dict[str, str] = {}
            expected_reverse: dict[str, str] = {}
            for ipa, target in rows:
                assert ipa, f"{path.name} has a row with no IPA side"
                assert target, f"{path.name}: row {ipa!r} carries no {column!r}"
                expected_forward.setdefault(ipa, target)
                expected_reverse.setdefault(target, ipa)
                checked += 1
            forward, reverse = _load_phonemap(path.stem)
            assert forward == expected_forward, path.name
            assert reverse == expected_reverse, path.name
        assert checked > 300, f"sweep read only {checked} rows"


class TestLookalikesThroughThePublicLoader:
    """The soft-read table is a phonemap, and reads like one."""

    def test_the_four_soft_reads(self) -> None:
        forward, reverse = _load_phonemap("lookalikes")
        assert forward == {"ɡ": "g", "ː": ":", "ʔ": "?", "ˈ": "'"}
        assert reverse == {"g": "ɡ", ":": "ː", "?": "ʔ", "'": "ˈ"}

    def test_the_inventory_reads_the_same_table(self) -> None:
        """One reader, so the inventory and the loader cannot disagree."""
        _, reverse = _load_phonemap("lookalikes")
        assert ipakit.IPAFeatures().lookalikes == reverse

    def test_the_soft_reads_still_apply(self) -> None:
        assert ipakit.normalize_lookalikes("g'a:?") == "ɡˈaːʔ"
        assert ipakit.from_wild("g'a:?") == "ɡˈaːʔ"
        assert ipakit.normalize_lookalikes("kæt!") == "kæt!"


@pytest.fixture
def phonemap_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A directory the loader reads instead of the shipped one.

    The cache is cleared on the way in and on the way out, so a
    constructed phonemap cannot be served to a later test and the
    shipped ones are re-read afterwards.
    """
    monkeypatch.setattr(phonemaps, "PHONEMAPS_DIR", tmp_path)
    _load_phonemap.cache_clear()
    yield tmp_path
    _load_phonemap.cache_clear()


MISDECLARED = [
    pytest.param(
        "widget",
        '<phonemap description="t" to="widget"><map ipa="a" wodget="A"/></phonemap>',
        "wodget",
        id="column the rows do not spell",
    ),
    pytest.param(
        "widget",
        '<phonemap description="t"><map ipa="a" widget="A"/></phonemap>',
        "declares no",
        id="no `to`, even where the stem would have matched",
    ),
    pytest.param(
        "widget",
        '<phonemap description="t" to="widget"></phonemap>',
        "no rows",
        id="a table with no rows",
    ),
    pytest.param(
        "widget",
        '<phonemap description="t" to="widget"><map ipa="a" widget="A"/>'
        '<map ipa="b" wodget="B"/></phonemap>',
        "wodget",
        id="one row of many spelling the column wrong",
    ),
]


@pytest.mark.parametrize(("name", "document", "wanted"), MISDECLARED)
def test_a_phonemap_that_maps_nothing_is_refused(
    phonemap_dir: Path, name: str, document: str, wanted: str
) -> None:
    """Loading is where a mismatched column is caught, not conversion.

    Stated over a constructed file rather than over ``lookalikes.xml``,
    so it is the general case that is pinned: a sixth phonemap arriving
    with a column nothing spells fails on arrival.
    """
    (phonemap_dir / f"{name}.xml").write_text(document, encoding="utf-8")
    with pytest.raises(ValueError, match=wanted):
        _load_phonemap(name)


def test_a_well_declared_phonemap_still_loads(phonemap_dir: Path) -> None:
    """The converse, so the refusals above are not refusing everything."""
    (phonemap_dir / "widget.xml").write_text(
        '<phonemap description="t" to="widget"><map ipa="a" widget="A"/></phonemap>',
        encoding="utf-8",
    )
    assert _load_phonemap("widget") == ({"a": "A"}, {"A": "a"})


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
        assert to_timit("e͜ɪ") == ["ey"]
        assert to_timit("o͜ʊ") == ["ow"]
        assert to_timit("a͜ɪ") == ["ay"]

    def test_from_timit_basic(self) -> None:
        assert from_timit(["k", "ae", "t"]) == "kæt"
        assert from_timit(["p"]) == "p"
        assert from_timit(["sh"]) == "ʃ"

    def test_from_timit_word(self) -> None:
        assert from_timit(["hh", "eh", "l", "ow"]) == "hɛlo͜ʊ"

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
