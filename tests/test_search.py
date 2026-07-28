"""Searching a transcription, and joining parsed units back into one.

`find` is the natural-class search over a string: the query language
`phones_matching` runs over the inventory, run over the units of a
transcription instead. `to_ipa` is the inverse of `segments`, and carries
no guarantee its parts do not. `feature_values` is the named bridge from
the flat, scalar read to the structured, multi-valued one.
"""

import ipakit
import pytest
from ipakit import IPAFeatures, Segment, Sense


class TestFindLocatesANaturalClass:
    def test_every_member_is_reported(self, ipa: IPAFeatures) -> None:
        assert [(i, unit.to_ipa()) for i, unit in ipa.find("kæt", ["plo"])] == [
            (0, "k"),
            (2, "t"),
        ]

    def test_no_member_is_an_empty_result(self, ipa: IPAFeatures) -> None:
        assert ipa.find("kæt", ["nas"]) == []

    def test_positions_index_units_not_characters(self, ipa: IPAFeatures) -> None:
        # The affricate is one unit of four characters and the stress mark
        # is no unit at all, so an index is neither a character offset nor
        # a count of glyphs.
        word = "t͡ʃˈe͜ɪnd͡ʒ"
        units = ipa.segments(word)
        found = ipa.find(word, {"manner": "vowel"})
        assert [i for i, _ in found] == [1]
        assert all(units[i] == unit for i, unit in found)

    def test_composed_units_match_like_registered_ones(self, ipa: IPAFeatures) -> None:
        # q͡χ is unregistered; it composes to an affricate and is found as one.
        assert [unit.to_ipa() for _, unit in ipa.find("aq͡χa", ["aff"])] == ["q͡χ"]

    def test_negation_excludes(self, ipa: IPAFeatures) -> None:
        voiceless = [unit.to_ipa() for _, unit in ipa.find("bpæ", ["plo", "-voi"])]
        assert voiceless == ["p"]


class TestFindSharesTheQueryLanguage:
    """One language, two search spaces -- not a second dialect."""

    WORD = "pætəkɑbzɪŋ"
    QUERIES: list[dict[str, str] | list[str]] = [
        ["plo"],
        ["plo", "-voi"],
        ["+voiced", "fricative"],
        ["vow"],
        {"manner": "nasal"},
        {"place": "bilabial", "voiced": "-"},
    ]

    @pytest.mark.parametrize("query", QUERIES)
    def test_find_selects_what_phones_matching_selects(
        self, ipa: IPAFeatures, query: dict[str, str] | list[str]
    ) -> None:
        inventory = set(ipa.phones_matching(query))
        found = {unit.to_ipa() for _, unit in ipa.find(self.WORD, query)}
        assert found == {t for t in ipa.tokenize(self.WORD) if t in inventory}

    def test_a_query_that_resolves_to_nothing_raises(self, ipa: IPAFeatures) -> None:
        # The same refusal phones_matching makes: an unresolved query would
        # otherwise report every unit as a match.
        with pytest.raises(ValueError, match="entire inventory"):
            ipa.find("kæt", ["zzz", "qqq"])

    def test_the_query_is_resolved_before_the_search(self, ipa: IPAFeatures) -> None:
        # Nothing to search is not an excuse to accept a bad query.
        with pytest.raises(ValueError, match="entire inventory"):
            ipa.find("", ["zzz"])

    def test_module_and_method_agree(self) -> None:
        assert [i for i, _ in ipakit.find("kæt", ["plo"])] == [0, 2]
        assert "find" in ipakit.__all__


class TestToIpaInvertsSegments:
    HOUSE_CANONICAL = [
        "kæt",
        "t͡ʃe͜ɪnd͡ʒ",
        "a͜ɪ͜ə",
        "t͡s͜a",
        "k͡p",
        "tʲun",
        "ã",
        "aː",
        "t̪",
        "ˈkæt",
    ]

    @pytest.mark.parametrize("text", HOUSE_CANONICAL)
    def test_round_trip(self, ipa: IPAFeatures, text: str) -> None:
        assert ipa.to_ipa(ipa.segments(text)) == text

    def test_empty(self, ipa: IPAFeatures) -> None:
        assert ipa.to_ipa([]) == ""

    def test_module_and_method_agree(self) -> None:
        assert ipakit.to_ipa(ipakit.segments("t͡s͜a")) == "t͡s͜a"
        assert "to_ipa" in ipakit.__all__

    def test_built_intent_emits_without_a_string_round_trip(
        self, ipa: IPAFeatures
    ) -> None:
        # build_segment bypasses the spellings; to_ipa spells what it built.
        fused = ipa.build_segment(["a", "ɪ"], Sense.FUSE)
        assert ipa.to_ipa([fused]) == "a͡ɪ"


class TestToIpaIsNoStrongerThanItsParts:
    """The documented losses, pinned so the docstring cannot drift."""

    @pytest.mark.parametrize("alias", ["ʧ", "ʦ", "ƛ"])
    def test_legacy_alias_spellings_come_back_canonical(
        self, ipa: IPAFeatures, alias: str
    ) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipa.to_ipa(ipa.segments(alias)) == canonical != alias

    def test_marks_belonging_to_no_unit_are_not_restored(
        self, ipa: IPAFeatures
    ) -> None:
        # The linking undertie is a relation between units, so no Segment
        # carries it and no join can put it back.
        assert ipa.to_ipa(ipa.segments("lez‿ami")) == "lezami"

    def test_stress_survives_the_join_wherever_it_stands(
        self, ipa: IPAFeatures
    ) -> None:
        # This used to assert kˈæt -> ˈkæt, which reads as a harmless
        # respelling only because a monosyllable's onset is in the
        # stressed syllable. The mark was binding leftward, so in a
        # longer word it changed syllable. It binds the unit that
        # follows it and re-emits in front of that unit, so both
        # spellings come back as written.
        assert ipa.to_ipa(ipa.segments("kˈæt")) == "kˈæt"
        assert ipa.to_ipa(ipa.segments("ˈkæt")) == "ˈkæt"


class TestFeatureValuesBridgesTheLevels:
    def test_the_scalar_read_summarizes_where_the_bag_keeps_both(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.get_features("u͜i")["backness"] == "back"
        assert ipa.feature_values("u͜i")["backness"] == ("back", "front")

    def test_it_is_the_segment_bag(self, ipa: IPAFeatures) -> None:
        assert ipa.feature_values("t͡s") == ipa.segment("t͡s").bag()

    def test_an_atomic_unit_holds_one_value_per_feature(self, ipa: IPAFeatures) -> None:
        assert all(len(v) == 1 for v in ipa.feature_values("p").values())

    def test_several_units_are_refused(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="exactly one unit"):
            ipa.feature_values("kæt")

    def test_module_and_method_agree(self) -> None:
        assert ipakit.feature_values("t͡s")["manner"] == ("plosive", "fricative")
        assert "feature_values" in ipakit.__all__


def test_a_match_carries_its_structure(ipa: IPAFeatures) -> None:
    """Why find returns units and not tokens: the structured reads a match
    is usually the prologue to are already in hand."""
    ((_, unit),) = ipa.find("kat͡ʃ", {"manner": "affricate"})
    assert isinstance(unit, Segment)
    assert unit.kind.value == "affricate"
    assert unit.left.to_ipa() == "t"
    assert unit.to_ipa() == "t͡ʃ"
