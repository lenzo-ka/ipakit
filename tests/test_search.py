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
        with pytest.raises(ValueError, match="resolves to no feature term"):
            ipa.find("kæt", ["zzz", "qqq"])

    def test_one_bad_term_beside_a_good_one_raises(self, ipa: IPAFeatures) -> None:
        # And the mixed query: dropping the bad term and searching on what
        # is left is a NARROWER query silently widened, which is worse
        # than a vacuous one because the answer still looks right.
        with pytest.raises(ValueError, match="'zzz' resolves to no feature term"):
            ipa.find("kæt", ["plosive", "zzz"])

    def test_the_query_is_resolved_before_the_search(self, ipa: IPAFeatures) -> None:
        # Nothing to search is not an excuse to accept a bad query.
        with pytest.raises(ValueError, match="resolves to no feature term"):
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
        "kˈæt",
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
        # longer word it changed syllable. Segment projection now emits
        # the mark on the nucleus; Form retains the independent spelling.
        assert ipa.to_ipa(ipa.segments("kˈæt")) == "kˈæt"
        assert ipa.to_ipa(ipa.segments("ˈkæt")) == "kˈæt"
        assert ipa.read("ˈkæt").to_ipa() == "ˈkæt"


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


class TestProsodicTermsAreAskedOfTheProsody:
    """A query naming stress or length is put to the unit's prosody.

    `find` matched every term against `Segment.scalar`, the read that has
    prosody taken out of it by design -- `features("a") ==
    features("ˈa")`. So a prosodic term could only ever be answered about
    a phone that never carries one: `["primary"]` found nothing, and
    `["-primary", "-secondary"]`, which is the spelling the resolver's own
    diagnostic recommends and the shipped American English rule set
    writes, reported "carries no stress" of a unit carrying primary
    stress. The negation is the half that matters: an empty answer is
    visibly wrong, a full one is not.
    """

    def test_a_stressed_unit_is_found_by_its_stress(self, ipa: IPAFeatures) -> None:
        assert [(i, u.to_ipa()) for i, u in ipa.find("ˈa a", ["primary"])] == [
            (0, "ˈa")
        ]

    def test_the_negation_excludes_the_unit_that_carries_it(
        self, ipa: IPAFeatures
    ) -> None:
        found = ipa.find("ˈa a", ["-primary", "-secondary"])
        assert [(i, u.to_ipa()) for i, u in found] == [(1, "a")]

    def test_length_is_asked_of_the_unit_and_not_of_the_bag(
        self, ipa: IPAFeatures
    ) -> None:
        # `aː` and `a` share a feature bag, so nothing in it can tell them
        # apart; the mark rides on the unit and that is where it is read.
        assert ipa.get_features("aː") == ipa.get_features("a")
        assert [u.to_ipa() for _, u in ipa.find("aː a", ["long"])] == ["aː"]

    def test_both_namespaces_in_one_query(self, ipa: IPAFeatures) -> None:
        found = ipa.find("ˈaː ˈk a", ["vowel", "primary", "long"])
        assert [u.to_ipa() for _, u in found] == ["ˈaː"]

    def test_the_split_is_the_one_rules_makes(self, ipa: IPAFeatures) -> None:
        """One partition, not two agreeing by habit.

        `ipakit.rules.Pattern` splits a resolved query the same way to
        decide what it asks of `Unit.prosody`. If these two drift, one
        query gets two answers depending on whether it was written to
        `find` or to a rule -- which is the shape of defect this repo has
        had most often.
        """
        from ipakit.rules import _is_prosodic

        names = sorted(ipa.features)
        segmental, prosodic = ipa._split_by_mode(dict.fromkeys(names, "x"))
        assert sorted(prosodic) == [n for n in names if _is_prosodic(n, ipa)]
        assert set(segmental) | set(prosodic) == set(names)
        assert not set(segmental) & set(prosodic)
        assert len(names) > 20, "sweep did not run"

    @pytest.mark.slow
    def test_it_holds_over_every_prosody_the_data_declares(
        self, ipa: IPAFeatures
    ) -> None:
        """Swept, not sampled: every mark that states prosody, on a base.

        For each such unit and each key its prosody states, asking for the
        value it holds finds it and asking for any other value of the same
        feature does not. Written as a dict so the sweep measures the
        prosody read and not the bare-term resolver, which answers with
        the first feature declaring a name and so would put ``mid`` to
        whichever of ``tone`` and ``height`` the data lists first.
        """
        import warnings

        from ipakit.form import _prosodic_features

        from tests.corpus import prosody_bearing_units

        checked = 0
        # The corpus carries pairs that contradict each other deliberately
        # -- two lengths, a fall over rising levels -- and each reports
        # itself. That is the behavior under test elsewhere, not here.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for unit in prosody_bearing_units():
                stated = _prosodic_features(ipa.segment(unit), ipa)
                for key, value in stated.items():
                    feature = ipa.features[key]
                    if value not in feature.values_set:
                        continue  # a contour or a level run, not a bare value
                    found = [u.to_ipa() for _, u in ipa.find(unit, {key: value})]
                    assert found == [unit], (unit, key, value)
                    for other in sorted(feature.values_set - {value}):
                        assert ipa.find(unit, {key: other}) == [], (unit, key, other)
                    checked += 1
        assert checked > 200, f"sweep did not run: {checked}"
