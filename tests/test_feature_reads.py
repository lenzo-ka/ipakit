"""The flat read and the structured read are one read.

`get_features` used to resolve only registered phones and tie-bar
chains, so a base carrying a diacritic -- ordinary transcription like
`tʲ`, `ã`, `tʰ` -- returned `{}`, the same answer it gives for garbage.
The structured level read those strings correctly the whole time, so the
two levels disagreed about the same string.
"""

import ipakit
import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


MODIFIED = ["tʲ", "ã", "tʰ", "n̩", "eː", "á", "t̪", "kʷ"]


class TestModifiedUnitsRead:
    def test_diacritic_bearing_units_have_features(self, ipa: IPAFeatures) -> None:
        for unit in MODIFIED:
            assert ipa.get_features(unit), unit

    def test_the_modifier_reaches_the_bundle(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tʲ")["palatalized"] == "+"
        assert ipa.get_features("ã")["nasalized"] == "+"
        assert ipa.get_features("tʰ")["release"] == "aspirated"
        assert ipa.get_features("n̩")["syllabic"] == "+"

    def test_base_features_survive_the_modifier(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tʲ")["manner"] == "plosive"
        assert ipa.get_features("tʲ")["place"] == "alveolar"


class TestLevelsAgree:
    """The property the fix buys: one string, one answer."""

    def test_agreement_over_base_by_diacritic(self, ipa: IPAFeatures) -> None:
        # The sweep that exposed the defect: nearly every combination
        # disagreed, because the flat side returned {}.
        checked = 0
        for base in "t a k s n l i u".split():
            for mark in ipa.diacritics:
                unit = base + mark
                # Well-formed IPA only. A dangling tie ("t͡") is malformed
                # -- the structured side is the lenient one there, parsing
                # it as a bare "t", and the flat side is right to refuse.
                if any(i["type"] == "error" for i in ipa.validate_ipa(unit)):
                    continue
                try:
                    structured = ipa.segment(unit).scalar()
                except ValueError:
                    continue
                checked += 1
                assert ipa.get_features(unit) == structured, unit
        assert checked > 100, "sweep did not run"

    def test_agreement_over_the_registered_inventory(self, ipa: IPAFeatures) -> None:
        for symbol in ipa.phones:
            assert ipa.get_features(symbol) == ipa.segment(symbol).scalar(), symbol


class TestUnresolvableStaysUnresolvable:
    """Reading more must not mean accepting anything."""

    def test_unknown_input_is_still_empty(self, ipa: IPAFeatures) -> None:
        for junk in ["4", "Q", "NOTAPHONE", ""]:
            assert ipa.get_features(junk) == {}, junk

    def test_a_parse_that_drops_input_is_refused(self, ipa: IPAFeatures) -> None:
        # Tokenization discards characters it does not know, so "q͡X"
        # parses to "q". Accepting that would report the features of a
        # different unit than the caller wrote.
        assert ipa.get_features("q͡X") == {}
        assert "q͡X" not in ipa
        assert ipa.get_features("q͡χ"), "the real composed unit still reads"

    def test_containment_matches_what_can_be_read(self, ipa: IPAFeatures) -> None:
        # __contains__ documents itself as "what get_features resolves";
        # nearest_phones gates on it, so drift here silently refuses
        # input the rest of the API accepts.
        for unit in [*MODIFIED, "t", "q͡χ", "4", "q͡X", "NOTAPHONE"]:
            assert (unit in ipa) == bool(ipa.get_features(unit)), unit


class TestDownstreamNoLongerLies:
    """Each of these returned a wrong or empty answer via the {} sentinel."""

    def test_natural_class_does_not_assert_over_a_dropped_member(self) -> None:
        # It filtered out the member it could not read and reported the
        # class of what remained -- claiming both phones were plain.
        shared = ipakit.natural_class(["tʲ", "t"])
        assert shared.get("manner") == "plosive"
        assert "palatalized" not in shared

    def test_natural_class_finds_a_real_shared_class(self) -> None:
        shared = ipakit.natural_class(["ã", "ẽ"])
        assert shared.get("nasalized") == "+"
        assert shared.get("manner") == "vowel"

    def test_minimal_pairs_and_neighbours_resolve(self) -> None:
        assert ipakit.minimal_pairs("tʲ")
        assert ipakit.nearest_phones("tʲ", n=3)

    def test_realizing_a_modified_bundle_does_not_answer_silence(self) -> None:
        # features("tʰ") was {}, and to_phone({}) matches the silence
        # phone, so the pair composed into a confident wrong answer.
        assert ipakit.to_phone(ipakit.features("tʰ")) != "␣"


class TestProsodyIsTheDocumentedException:
    """Prosodic marks belong to the unit, not to its feature bag."""

    def test_a_prosodic_unit_reads_its_base_features(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("eː")["manner"] == "vowel"
        assert ipa.get_features("eː") == ipa.get_features("e")

    def test_the_mark_is_carried_as_prosody(self, ipa: IPAFeatures) -> None:
        assert ipa.segment("eː").prosody == ("ː",)

    def test_compose_differs_only_here(self, ipa: IPAFeatures) -> None:
        # The one documented divergence between scalar() and compose().
        assert ipa.compose("eː")[0]["length"] == "long"
        assert ipa.segment("eː").scalar()["length"] == "normal"
